import hashlib
import os
import re
import tempfile
from typing import Callable, Dict, List, Optional, Tuple

import streamlit as st

from src.domain.models import (
    EducationItem,
    ExperienceItem,
    PersonalInfo,
    ProjectItem,
    ResumeInput,
)
from src.utils.text_utils import split_blocks, split_csv_or_lines, split_lines


SECTION_NOISE_TOKENS = {
    "skills",
    "skill",
    "education",
    "work experience",
    "experience",
    "projects",
    "project",
    "certifications",
    "certification",
    "achievements",
    "achievement",
    "hievements",
    "professional information",
    "personal information",
}

DURATION_PATTERN = re.compile(
    r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4})\s*(?:-|to|–|—)\s*(present|current|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4})\b",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")

ROLE_HINTS = {
    "intern",
    "engineer",
    "developer",
    "analyst",
    "associate",
    "manager",
    "lead",
    "chair",
    "vice chair",
    "founder",
    "office",
    "product",
    "operations",
}

COMPANY_HINTS = {
    "private limited",
    "pvt",
    "inc",
    "llc",
    "ltd",
    "university",
    "education",
    "technologies",
    "systems",
    "labs",
    "solutions",
}

LOCATION_HINTS = {
    "remote",
    "india",
    "bangalore",
    "bengaluru",
    "delhi",
    "mumbai",
    "pune",
    "noida",
    "hyderabad",
    "onsite",
    "hybrid",
}

TECH_HINTS = {
    "python",
    "streamlit",
    "gemini",
    "tensorflow",
    "opencv",
    "react",
    "node",
    "mongodb",
    "sql",
    "docker",
    "api",
    "fastapi",
    "flask",
    "javascript",
    "java",
    "c++",
}

ACTION_VERBS = {
    "built",
    "designed",
    "implemented",
    "improved",
    "developed",
    "managed",
    "coordinated",
    "led",
    "launched",
    "optimized",
    "automated",
    "deployed",
    "tested",
    "delivered",
    "created",
}

HEADER_NOISE_TOKENS = {
    "testing",
    "quality",
    "support",
    "management",
    "development",
    "report",
    "outreach",
}

SEMANTIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "for",
    "of",
    "in",
    "on",
    "with",
    "using",
    "from",
    "by",
    "across",
    "through",
}

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"\+?\d[\d\s().-]{8,}\d")
URL_PATTERN = re.compile(r"(https?://\S+|www\.\S+|(?:linkedin|github)\.com/\S+)", re.IGNORECASE)

SECTION_HEADING_ALIASES: Dict[str, set[str]] = {
    "professional_summary": {
        "summary",
        "professional summary",
        "career summary",
        "objective",
        "career objective",
        "profile",
        "professional profile",
        "about",
        "about me",
    },
    "skills": {
        "skills",
        "technical skills",
        "core skills",
        "core competencies",
        "tech stack",
        "technologies",
        "technical expertise",
    },
    "education": {
        "education",
        "academic background",
        "academic qualifications",
        "qualifications",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "internship experience",
    },
    "projects": {
        "projects",
        "project",
        "project experience",
        "academic projects",
        "personal projects",
    },
    "certifications": {
        "certifications",
        "certification",
        "certificates",
        "licenses",
        "license",
    },
    "achievements": {
        "achievements",
        "achievement",
        "accomplishments",
        "awards",
        "honors",
    },
}

FORM_FIELD_KEYS = {
    "full_name": "resume_form_full_name",
    "email": "resume_form_email",
    "phone": "resume_form_phone",
    "location": "resume_form_location",
    "linkedin": "resume_form_linkedin",
    "github": "resume_form_github",
    "portfolio": "resume_form_portfolio",
    "career_summary": "resume_form_career_summary",
    "target_role": "resume_form_target_role",
    "target_company": "resume_form_target_company",
    "tone": "resume_form_tone",
    "job_description": "resume_form_job_description",
    "skills_raw": "resume_form_skills",
    "education_raw": "resume_form_education",
    "experience_raw": "resume_form_experience",
    "projects_raw": "resume_form_projects",
    "certifications_raw": "resume_form_certifications",
    "achievements_raw": "resume_form_achievements",
}

UPLOAD_SIGNATURE_KEY = "resume_upload_signature"


def _normalize_line_for_filter(line: str) -> str:
    value = line.strip().lower()
    value = value.lstrip("#-*• ").strip()
    value = value.strip(" :.-")
    return value


def _is_noise_line(line: str) -> bool:
    normalized = _normalize_line_for_filter(line)
    if not normalized:
        return True
    if normalized in SECTION_NOISE_TOKENS:
        return True
    if normalized.replace(" ", "") in {"workexperience", "personalinformation", "professionalinformation"}:
        return True
    return False


def _clean_simple_lines(lines: List[str]) -> List[str]:
    return [line for line in lines if not _is_noise_line(line)]


def _strip_list_prefix(line: str) -> str:
    return line.lstrip("-*• ").strip().strip("()").strip()


def _truncate_words(text: str, max_words: int) -> str:
    words = [word for word in text.split() if word]
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(".,:;-")


def _pop_first_match(values: List[str], predicate: Callable[[str], bool]) -> str:
    for index, value in enumerate(values):
        if predicate(value):
            return values.pop(index)
    return ""


def _looks_like_duration(line: str) -> bool:
    text = _strip_list_prefix(line)
    lowered = text.lower()
    if DURATION_PATTERN.search(text):
        return True
    return bool(YEAR_PATTERN.search(text)) and ("-" in text or " to " in lowered or "present" in lowered)


def _looks_like_company(line: str) -> bool:
    text = _strip_list_prefix(line)
    lowered = text.lower()
    if not text or _looks_like_duration(text):
        return False
    role_hint = _has_hint_token(lowered, ROLE_HINTS)
    company_hint = _has_hint_token(lowered, COMPANY_HINTS)
    if role_hint and not company_hint:
        return False
    if "," in text and not company_hint:
        return False
    if _has_hint_token(lowered, HEADER_NOISE_TOKENS) and not company_hint:
        return False
    if company_hint:
        return True
    words = text.split()
    if len(words) <= 7 and words and words[0][:1].isupper() and words[-1][:1].isupper():
        return True
    return False


def _looks_like_role(line: str) -> bool:
    text = _strip_list_prefix(line)
    lowered = text.lower()
    if not text or _looks_like_duration(text):
        return False
    if not text[:1].isupper():
        return False
    if "," in text and "/" not in text:
        return False
    words = text.split()
    if len(words) > 12:
        return False
    if re.search(r"\d", text):
        return False
    if _has_hint_token(lowered, ACTION_VERBS):
        return False
    return _has_hint_token(lowered, ROLE_HINTS)


def _looks_like_institution(line: str) -> bool:
    text = _strip_list_prefix(line).lower()
    if not text:
        return False
    return any(token in text for token in {"university", "college", "institute", "school", "academy", "uni"})


def _semantic_key(text: str) -> str:
    normalized = _normalize_line_for_filter(text)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    tokens = [token for token in normalized.split() if token and token not in SEMANTIC_STOPWORDS]
    if not tokens:
        return normalized
    return " ".join(tokens[:8])


def _looks_like_location(line: str) -> bool:
    text = _strip_list_prefix(line)
    lowered = text.lower()
    if not text or _looks_like_duration(text):
        return False
    if _has_hint_token(lowered, ROLE_HINTS):
        return False
    if _has_hint_token(lowered, COMPANY_HINTS):
        return False
    if _has_hint_token(lowered, HEADER_NOISE_TOKENS):
        return False
    if _has_hint_token(lowered, LOCATION_HINTS):
        return True
    if "," in text and len(text.split()) <= 8:
        return True
    return False


def _looks_like_technologies(line: str) -> bool:
    text = _strip_list_prefix(line)
    lowered = text.lower()
    if not text or _looks_like_duration(text):
        return False
    if _has_hint_token(lowered, TECH_HINTS):
        return True
    if "," in text and len(text.split(",")) >= 2 and len(text.split()) <= 22:
        return True
    return False


def _has_hint_token(text: str, hints: set[str]) -> bool:
    lowered = (text or "").lower()
    for hint in hints:
        token = str(hint).strip().lower()
        if not token:
            continue
        if " " in token:
            if token in lowered:
                return True
            continue
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return True
    return False


def _rank_highlights(lines: List[str], max_items: int = 8, max_words: int = 24) -> List[str]:
    scored: List[Tuple[int, int, str]] = []

    for index, raw_line in enumerate(lines):
        text = _strip_list_prefix(raw_line)
        if not text or _is_noise_line(text):
            continue

        lowered = text.lower()
        words = text.split()
        if len(words) < 4:
            continue

        score = 0
        if any(token in lowered for token in ACTION_VERBS):
            score += 2
        if re.search(r"\d", text):
            score += 2
        if any(token in lowered for token in {"product", "system", "platform", "api", "testing", "deployment", "team"}):
            score += 1

        scored.append((score, index, _truncate_words(text, max_words)))

    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: List[str] = []
    seen = set()
    semantic_seen = set()
    for _, _, text in scored:
        key = text.lower()
        if key in seen:
            continue
        meaning = _semantic_key(text)
        if meaning and meaning in semantic_seen:
            continue
        seen.add(key)
        if meaning:
            semantic_seen.add(meaning)
        selected.append(text)
        if len(selected) >= max_items:
            break

    return selected


def _parse_loose_experience(lines: List[str]) -> ExperienceItem:
    role = ""
    company = ""
    duration = ""
    location = ""
    remaining: List[str] = []

    for raw_line in lines:
        line = _strip_list_prefix(raw_line)
        if not line or _is_noise_line(line):
            continue

        if "|" in line:
            parts = [part.strip() for part in line.split("|")]
            role = role or (parts[0] if len(parts) > 0 else "")
            company = company or (parts[1] if len(parts) > 1 else "")
            duration = duration or (parts[2] if len(parts) > 2 else "")
            location = location or (parts[3] if len(parts) > 3 else "")
            continue

        if not duration and _looks_like_duration(line):
            duration = line
            continue
        if not company and _looks_like_company(line):
            company = line
            continue
        if not location and _looks_like_location(line):
            location = line
            continue
        if not role and _looks_like_role(line):
            role = line
            continue

        remaining.append(line)

    if not role:
        role = _pop_first_match(
            remaining,
            lambda value: _looks_like_role(value)
            or (
                1 < len(value.split()) <= 8
                and not _looks_like_duration(value)
                and not _looks_like_company(value)
                and not re.search(r"\d", value)
                and not any(token in value.lower() for token in ACTION_VERBS)
            ),
        )
    if not company:
        company = _pop_first_match(remaining, _looks_like_company)
    if not duration:
        duration = _pop_first_match(remaining, _looks_like_duration)
    if not location:
        location = _pop_first_match(remaining, _looks_like_location)

    bullets = _rank_highlights(remaining, max_items=8, max_words=24)
    if not bullets:
        bullets = [_truncate_words(line, 24) for line in remaining[:3] if len(line.split()) >= 5]

    return ExperienceItem(
        role=role,
        company=company,
        duration=duration,
        location=location,
        bullet_points=bullets,
    )


def _parse_loose_project(lines: List[str]) -> ProjectItem:
    name = ""
    technologies = ""
    year = ""
    remaining: List[str] = []

    for raw_line in lines:
        line = _strip_list_prefix(raw_line)
        if not line or _is_noise_line(line):
            continue

        if "|" in line:
            parts = [part.strip() for part in line.split("|")]
            name = name or (parts[0] if len(parts) > 0 else "")
            technologies = technologies or (parts[1] if len(parts) > 1 else "")
            year = year or (parts[2] if len(parts) > 2 else "")
            continue

        if not year and YEAR_PATTERN.search(line):
            year_match = YEAR_PATTERN.search(line)
            year = year_match.group(0) if year_match else ""
            continue
        if not technologies and _looks_like_technologies(line):
            technologies = line
            continue
        if not name and len(line.split()) <= 10 and not _looks_like_duration(line):
            name = line
            continue

        remaining.append(line)

    if not name:
        name = _pop_first_match(
            remaining,
            lambda value: 1 < len(value.split()) <= 10
            and not _looks_like_duration(value)
            and not _looks_like_technologies(value)
            and not any(token in value.lower() for token in ACTION_VERBS),
        )
    if not technologies:
        technologies = _pop_first_match(remaining, _looks_like_technologies)
    if not year:
        year_line = _pop_first_match(remaining, lambda value: bool(YEAR_PATTERN.search(value)))
        year_match = YEAR_PATTERN.search(year_line)
        year = year_match.group(0) if year_match else ""

    bullets = _rank_highlights(remaining, max_items=8, max_words=24)
    if not bullets:
        bullets = [_truncate_words(line, 24) for line in remaining[:3] if len(line.split()) >= 5]

    return ProjectItem(name=name, technologies=technologies, year=year, bullet_points=bullets)


def _parse_education(raw_text: str) -> List[EducationItem]:
    items: List[EducationItem] = []
    for line in _clean_simple_lines(split_lines(raw_text)):
        cleaned_line = _strip_list_prefix(line)
        parts = [part.strip() for part in cleaned_line.split("|")]

        if len(parts) == 1 and "," in cleaned_line:
            comma_parts = [part.strip() for part in cleaned_line.split(",") if part.strip()]
            first = comma_parts[0] if len(comma_parts) > 0 else ""
            second = comma_parts[1] if len(comma_parts) > 1 else ""
            details = ", ".join(comma_parts[2:]) if len(comma_parts) > 2 else ""

            if _looks_like_institution(first) and second:
                parts = [second, first, "", "", details]
            else:
                parts = [first, second, "", "", details]

        degree = parts[0] if len(parts) > 0 else ""
        institution = parts[1] if len(parts) > 1 else ""
        duration = parts[2] if len(parts) > 2 else ""
        location = parts[3] if len(parts) > 3 else ""
        details = parts[4] if len(parts) > 4 else ""

        if degree and _looks_like_institution(degree) and institution and not _looks_like_institution(institution):
            degree, institution = institution, degree

        if duration and not _looks_like_duration(duration):
            details = ", ".join(part for part in [duration, details] if part)
            duration = ""

        items.append(
            EducationItem(
                degree=degree,
                institution=institution,
                duration=duration,
                location=location,
                details=details,
            )
        )
    return [item for item in items if any([item.degree, item.institution, item.duration, item.location, item.details])]


def _is_valid_experience_item(item: ExperienceItem) -> bool:
    role_key = _normalize_line_for_filter(item.role)
    company_key = _normalize_line_for_filter(item.company)

    if not role_key and not company_key:
        return False
    if role_key and company_key and role_key == company_key:
        return False
    if item.role and "," in item.role and "/" not in item.role:
        return False
    if item.role and re.search(r"\d", item.role) and len(item.role.split()) > 4:
        return False
    if item.company and _looks_like_role(item.company) and not _looks_like_company(item.company):
        return False
    return True


def _is_valid_project_item(item: ProjectItem) -> bool:
    name_key = _normalize_line_for_filter(item.name)
    tech_key = _normalize_line_for_filter(item.technologies)
    if not name_key:
        return False
    if name_key in {"project", "application", "app", "system", "website"}:
        return False
    if name_key and tech_key and name_key == tech_key:
        return False
    return True


def _parse_experience(raw_text: str) -> List[ExperienceItem]:
    items: List[ExperienceItem] = []
    for block in split_blocks(raw_text):
        lines = _clean_simple_lines([line.strip() for line in block.splitlines() if line.strip()])
        if not lines:
            continue

        header_parts = [part.strip() for part in _strip_list_prefix(lines[0]).split("|")]
        if len(header_parts) >= 2:
            bullets = _rank_highlights(lines[1:], max_items=8, max_words=24)
            candidate = ExperienceItem(
                role=header_parts[0] if len(header_parts) > 0 else "",
                company=header_parts[1] if len(header_parts) > 1 else "",
                duration=header_parts[2] if len(header_parts) > 2 else "",
                location=header_parts[3] if len(header_parts) > 3 else "",
                bullet_points=bullets,
            )
            if _is_valid_experience_item(candidate):
                items.append(candidate)
            continue

        parsed = _parse_loose_experience(lines)
        if any([parsed.role, parsed.company, parsed.duration, parsed.location, parsed.bullet_points]) and _is_valid_experience_item(parsed):
            items.append(parsed)

    return [item for item in items if any([item.role, item.company, item.duration, item.location, item.bullet_points])]


def _parse_projects(raw_text: str) -> List[ProjectItem]:
    items: List[ProjectItem] = []
    for block in split_blocks(raw_text):
        lines = _clean_simple_lines([line.strip() for line in block.splitlines() if line.strip()])
        if not lines:
            continue

        header_parts = [part.strip() for part in _strip_list_prefix(lines[0]).split("|")]
        if len(header_parts) >= 2:
            bullets = _rank_highlights(lines[1:], max_items=8, max_words=24)
            candidate = ProjectItem(
                name=header_parts[0] if len(header_parts) > 0 else "",
                technologies=header_parts[1] if len(header_parts) > 1 else "",
                year=header_parts[2] if len(header_parts) > 2 else "",
                bullet_points=bullets,
            )
            if _is_valid_project_item(candidate):
                items.append(candidate)
            continue

        parsed = _parse_loose_project(lines)
        if any([parsed.name, parsed.technologies, parsed.year, parsed.bullet_points]) and _is_valid_project_item(parsed):
            items.append(parsed)

    return [item for item in items if any([item.name, item.technologies, item.year, item.bullet_points])]


def _normalize_heading_candidate(line: str) -> str:
    cleaned = _strip_list_prefix(line).strip().rstrip(":").strip()
    cleaned = re.sub(r"[^A-Za-z\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _detect_section_heading(line: str) -> Optional[str]:
    candidate = _normalize_heading_candidate(line)
    if not candidate:
        return None

    for section_name, aliases in SECTION_HEADING_ALIASES.items():
        if candidate in aliases:
            return section_name

    if len(candidate.split()) <= 4:
        for section_name, aliases in SECTION_HEADING_ALIASES.items():
            for alias in aliases:
                if candidate.startswith(alias + " "):
                    return section_name
    return None


def _split_heading_and_inline_content(line: str) -> Tuple[Optional[str], str]:
    stripped = _strip_list_prefix(line).strip()
    if not stripped:
        return None, ""

    if ":" in stripped:
        left, right = stripped.split(":", 1)
        heading = _detect_section_heading(left)
        if heading:
            return heading, right.strip()

    heading = _detect_section_heading(stripped)
    if heading:
        return heading, ""
    return None, ""


def _collapse_blank_lines(lines: List[str]) -> List[str]:
    collapsed: List[str] = []
    previous_blank = False

    for line in lines:
        value = line.strip()
        if not value:
            if collapsed and not previous_blank:
                collapsed.append("")
            previous_blank = True
            continue

        collapsed.append(value)
        previous_blank = False

    while collapsed and not collapsed[0]:
        collapsed.pop(0)
    while collapsed and not collapsed[-1]:
        collapsed.pop()
    return collapsed


def _extract_resume_sections(raw_text: str) -> Tuple[Dict[str, str], List[str]]:
    section_lines: Dict[str, List[str]] = {
        "professional_summary": [],
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "achievements": [],
    }
    preamble_lines: List[str] = []
    current_section: Optional[str] = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_section and section_lines[current_section] and section_lines[current_section][-1] != "":
                section_lines[current_section].append("")
            continue

        heading, inline_content = _split_heading_and_inline_content(line)
        if heading:
            current_section = heading
            if inline_content:
                section_lines[current_section].append(inline_content)
            continue

        if current_section:
            section_lines[current_section].append(line)
        else:
            preamble_lines.append(line)

    sections: Dict[str, str] = {}
    for section_name, lines in section_lines.items():
        sections[section_name] = "\n".join(_collapse_blank_lines(lines)).strip()

    return sections, preamble_lines


def _extract_skills(raw_text: str) -> List[str]:
    if not raw_text:
        return []

    candidates: List[str] = []
    for line in split_lines(raw_text):
        cleaned_line = _strip_list_prefix(line)
        if not cleaned_line or _is_noise_line(cleaned_line):
            continue

        pieces = [piece.strip() for piece in re.split(r"[,|;/•]+", cleaned_line) if piece.strip()]
        if not pieces:
            continue

        if len(pieces) == 1 and len(cleaned_line.split()) > 6 and not _has_hint_token(cleaned_line.lower(), TECH_HINTS):
            continue

        for piece in pieces:
            if _is_noise_line(piece):
                continue
            if len(piece) > 45:
                continue
            if len(piece.split()) > 4 and not _has_hint_token(piece.lower(), TECH_HINTS):
                continue
            candidates.append(piece.strip(".,"))

    return split_csv_or_lines(",".join(candidates))[:24]


def _extract_simple_list(raw_text: str, max_items: int = 12) -> List[str]:
    values: List[str] = []
    seen = set()

    for line in split_lines(raw_text):
        cleaned_line = _strip_list_prefix(line)
        if not cleaned_line or _is_noise_line(cleaned_line):
            continue

        parts = [part.strip() for part in re.split(r"[;|]", cleaned_line) if part.strip()]
        if len(parts) == 1 and "," in cleaned_line and len(cleaned_line.split(",")) <= 4:
            parts = [part.strip() for part in cleaned_line.split(",") if part.strip()]

        for part in parts:
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(part)
            if len(values) >= max_items:
                return values

    return values


def _looks_like_contact_line(line: str) -> bool:
    lowered = line.lower()
    if EMAIL_PATTERN.search(line):
        return True
    if URL_PATTERN.search(line):
        return True
    if any(token in lowered for token in {"linkedin", "github", "portfolio", "phone", "contact"}):
        return True
    return False


def _extract_personal_info(raw_text: str, preamble_lines: List[str]) -> Dict[str, str]:
    top_lines = [line.strip() for line in raw_text.splitlines() if line.strip()][:24]
    details: Dict[str, str] = {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
    }

    def _normalize_phone(text: str) -> str:
        match = PHONE_PATTERN.search(text)
        if not match:
            return ""
        candidate = match.group(0).strip()
        digit_count = len(re.sub(r"\D", "", candidate))
        if digit_count < 10 or digit_count > 15:
            return ""
        return candidate

    for line in top_lines:
        lowered = line.lower()
        if not details["email"] and "email" in lowered and ":" in line:
            maybe_email = line.split(":", 1)[1].strip()
            email_match = EMAIL_PATTERN.search(maybe_email)
            if email_match:
                details["email"] = email_match.group(0)

        if not details["phone"] and "phone" in lowered and ":" in line:
            details["phone"] = _normalize_phone(line.split(":", 1)[1])

        if not details["location"] and "location" in lowered and ":" in line:
            details["location"] = line.split(":", 1)[1].strip()

    if not details["email"]:
        email_match = EMAIL_PATTERN.search(raw_text)
        if email_match:
            details["email"] = email_match.group(0)

    if not details["phone"]:
        details["phone"] = _normalize_phone(raw_text)

    for raw_url in URL_PATTERN.findall(raw_text):
        url = raw_url.strip().rstrip(").,;")
        normalized = url if re.match(r"https?://", url, re.IGNORECASE) else f"https://{url}"
        lowered = normalized.lower()
        if "linkedin.com" in lowered and not details["linkedin"]:
            details["linkedin"] = normalized
        elif "github.com" in lowered and not details["github"]:
            details["github"] = normalized
        elif not details["portfolio"]:
            details["portfolio"] = normalized

    if not details["location"]:
        for line in top_lines:
            cleaned_line = line.strip()
            lowered = cleaned_line.lower()
            if _looks_like_contact_line(cleaned_line) or _detect_section_heading(cleaned_line):
                continue
            if "," in cleaned_line and len(cleaned_line.split()) <= 8 and not re.search(r"\d", cleaned_line):
                details["location"] = cleaned_line
                break
            if _has_hint_token(lowered, LOCATION_HINTS) and len(cleaned_line.split()) <= 8:
                details["location"] = cleaned_line
                break

    if not details["full_name"]:
        name_candidates = preamble_lines[:8] + top_lines[:8]
        for line in name_candidates:
            cleaned_line = _strip_list_prefix(line)
            words = [word for word in cleaned_line.split() if word]
            if not cleaned_line:
                continue
            if _looks_like_contact_line(cleaned_line) or _detect_section_heading(cleaned_line):
                continue
            if re.search(r"\d", cleaned_line):
                continue
            if len(words) < 2 or len(words) > 5:
                continue
            details["full_name"] = cleaned_line
            break

    return details


def _format_education_for_form(items: List[EducationItem]) -> str:
    lines: List[str] = []
    for item in items:
        parts = [item.degree, item.institution, item.duration, item.location, item.details]
        while parts and not parts[-1]:
            parts.pop()
        if not any(parts):
            continue
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_experience_for_form(items: List[ExperienceItem]) -> str:
    blocks: List[str] = []
    for item in items:
        parts = [item.role, item.company, item.duration, item.location]
        while parts and not parts[-1]:
            parts.pop()
        block_lines: List[str] = []
        if any(parts):
            block_lines.append(" | ".join(parts))
        for bullet in item.bullet_points:
            cleaned_bullet = _strip_list_prefix(bullet)
            if cleaned_bullet:
                block_lines.append(f"- {cleaned_bullet}")
        if block_lines:
            blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def _format_projects_for_form(items: List[ProjectItem]) -> str:
    blocks: List[str] = []
    for item in items:
        parts = [item.name, item.technologies, item.year]
        while parts and not parts[-1]:
            parts.pop()
        block_lines: List[str] = []
        if any(parts):
            block_lines.append(" | ".join(parts))
        for bullet in item.bullet_points:
            cleaned_bullet = _strip_list_prefix(bullet)
            if cleaned_bullet:
                block_lines.append(f"- {cleaned_bullet}")
        if block_lines:
            blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def _build_prefill_from_resume_text(raw_text: str) -> Dict[str, str]:
    sections, preamble_lines = _extract_resume_sections(raw_text)
    personal_info = _extract_personal_info(raw_text, preamble_lines)

    summary_lines = _clean_simple_lines(split_lines(sections.get("professional_summary", "")))
    if not summary_lines:
        summary_lines = [
            _strip_list_prefix(line)
            for line in preamble_lines
            if len(line.split()) >= 6 and not _looks_like_contact_line(line)
        ]

    skills = _extract_skills(sections.get("skills", ""))
    if not skills:
        skills = _extract_simple_list(sections.get("skills", ""), max_items=20)
    if not skills:
        skills = _extract_skills(raw_text)

    education_text = sections.get("education", "")
    experience_text = sections.get("experience", "")
    projects_text = sections.get("projects", "")

    education_items = _parse_education(education_text)
    experience_items = _parse_experience(experience_text)
    project_items = _parse_projects(projects_text)

    if not education_items:
        education_items = _parse_education(raw_text)
    if not experience_items:
        experience_items = _parse_experience(raw_text)
    if not project_items:
        project_items = _parse_projects(raw_text)

    certifications = _extract_simple_list(sections.get("certifications", ""), max_items=12)
    achievements = _extract_simple_list(sections.get("achievements", ""), max_items=12)

    return {
        "full_name": personal_info.get("full_name", ""),
        "email": personal_info.get("email", ""),
        "phone": personal_info.get("phone", ""),
        "location": personal_info.get("location", ""),
        "linkedin": personal_info.get("linkedin", ""),
        "github": personal_info.get("github", ""),
        "portfolio": personal_info.get("portfolio", ""),
        "career_summary": "\n".join(summary_lines[:4]).strip(),
        "skills_raw": ", ".join(skills),
        "education_raw": _format_education_for_form(education_items) or education_text,
        "experience_raw": _format_experience_for_form(experience_items) or experience_text,
        "projects_raw": _format_projects_for_form(project_items) or projects_text,
        "certifications_raw": "\n".join(certifications),
        "achievements_raw": "\n".join(achievements),
    }


def _init_form_state_defaults() -> None:
    defaults = {
        FORM_FIELD_KEYS["full_name"]: "",
        FORM_FIELD_KEYS["email"]: "",
        FORM_FIELD_KEYS["phone"]: "",
        FORM_FIELD_KEYS["location"]: "",
        FORM_FIELD_KEYS["linkedin"]: "",
        FORM_FIELD_KEYS["github"]: "",
        FORM_FIELD_KEYS["portfolio"]: "",
        FORM_FIELD_KEYS["career_summary"]: "",
        FORM_FIELD_KEYS["target_role"]: "",
        FORM_FIELD_KEYS["target_company"]: "",
        FORM_FIELD_KEYS["tone"]: "professional",
        FORM_FIELD_KEYS["job_description"]: "",
        FORM_FIELD_KEYS["skills_raw"]: "",
        FORM_FIELD_KEYS["education_raw"]: "",
        FORM_FIELD_KEYS["experience_raw"]: "",
        FORM_FIELD_KEYS["projects_raw"]: "",
        FORM_FIELD_KEYS["certifications_raw"]: "",
        FORM_FIELD_KEYS["achievements_raw"]: "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _apply_prefill_to_form_state(prefill: Dict[str, str]) -> None:
    field_mapping = {
        "full_name": FORM_FIELD_KEYS["full_name"],
        "email": FORM_FIELD_KEYS["email"],
        "phone": FORM_FIELD_KEYS["phone"],
        "location": FORM_FIELD_KEYS["location"],
        "linkedin": FORM_FIELD_KEYS["linkedin"],
        "github": FORM_FIELD_KEYS["github"],
        "portfolio": FORM_FIELD_KEYS["portfolio"],
        "career_summary": FORM_FIELD_KEYS["career_summary"],
        "skills_raw": FORM_FIELD_KEYS["skills_raw"],
        "education_raw": FORM_FIELD_KEYS["education_raw"],
        "experience_raw": FORM_FIELD_KEYS["experience_raw"],
        "projects_raw": FORM_FIELD_KEYS["projects_raw"],
        "certifications_raw": FORM_FIELD_KEYS["certifications_raw"],
        "achievements_raw": FORM_FIELD_KEYS["achievements_raw"],
    }
    for source_field, state_key in field_mapping.items():
        st.session_state[state_key] = prefill.get(source_field, "")


def _validate_resume_input(resume_input: ResumeInput) -> List[str]:
    errors: List[str] = []

    if not resume_input.personal_info.full_name.strip():
        errors.append("Full Name is required.")
    if not resume_input.personal_info.email.strip():
        errors.append("Email is required.")

    has_content = any(
        [
            resume_input.career_summary.strip(),
            resume_input.skills,
            resume_input.education,
            resume_input.experiences,
            resume_input.projects,
            resume_input.certifications,
            resume_input.achievements,
        ]
    )
    if not has_content:
        errors.append("Add at least one professional section (skills, education, experience, projects, etc.).")

    return errors


def render_resume_form() -> Tuple[bool, Optional[ResumeInput]]:
    st.subheader("Resume Input")
    st.caption("Fill structured sections. For Education/Experience/Projects, follow the format hints below.")

    _init_form_state_defaults()

    # --- Resume upload section temporarily disabled ---
    # uploaded_file = st.file_uploader(
    #     "Upload your existing resume (PDF or DOCX)",
    #     type=["pdf", "docx"],
    #     help="Optional: Upload to auto-fill fields from your current resume.",
    # )
    #
    # if uploaded_file is not None:
    #     file_ext = os.path.splitext(uploaded_file.name)[-1].lower()
    #     file_bytes = uploaded_file.getvalue()
    #     file_hash = hashlib.md5(file_bytes).hexdigest() if file_bytes else ""
    #     upload_signature = f"{uploaded_file.name}:{len(file_bytes)}:{file_hash}"
    #
    #     if st.session_state.get(UPLOAD_SIGNATURE_KEY) != upload_signature:
    #         with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
    #             tmp_file.write(file_bytes)
    #             tmp_path = tmp_file.name
    #
    #         try:
    #             if file_ext == ".pdf":
    #                 import pdfplumber
    #
    #                 with pdfplumber.open(tmp_path) as pdf:
    #                     extracted_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    #             elif file_ext == ".docx":
    #                 import docx
    #
    #                 document = docx.Document(tmp_path)
    #                 extracted_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    #             else:
    #                 extracted_text = ""
    #
    #             if not extracted_text.strip():
    #                 st.warning("Uploaded file could not be parsed into readable text.")
    #             else:
    #                 prefill = _build_prefill_from_resume_text(extracted_text)
    #                 _apply_prefill_to_form_state(prefill)
    #                 st.session_state[UPLOAD_SIGNATURE_KEY] = upload_signature
    #                 st.success("Resume parsed successfully. Fields are auto-filled; review and refine before generating.")
    #         except Exception as error:
    #             st.error(f"Failed to extract and map resume data: {error}")
    #         finally:
    #             os.unlink(tmp_path)

    with st.form("resume_input_form"):
        st.markdown("### Personal Information")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", key=FORM_FIELD_KEYS["full_name"])
            email = st.text_input("Email", key=FORM_FIELD_KEYS["email"])
            phone = st.text_input("Phone Number", key=FORM_FIELD_KEYS["phone"])
            location = st.text_input("Location", key=FORM_FIELD_KEYS["location"])
        with col2:
            linkedin = st.text_input("LinkedIn URL", key=FORM_FIELD_KEYS["linkedin"])
            github = st.text_input("GitHub URL", key=FORM_FIELD_KEYS["github"])
            portfolio = st.text_input("Portfolio URL", key=FORM_FIELD_KEYS["portfolio"])


        st.markdown("### Professional Information")
        career_summary = st.text_area(
            "Career Summary / Objective",
            height=110,
            key=FORM_FIELD_KEYS["career_summary"],
        )
        target_col1, target_col2 = st.columns(2)
        with target_col1:
            target_role = st.text_input(
                "Target Role (optional)",
                placeholder="Software Engineer",
                key=FORM_FIELD_KEYS["target_role"],
            )
            target_company = st.text_input(
                "Target Company (optional)",
                placeholder="Google",
                key=FORM_FIELD_KEYS["target_company"],
            )
        with target_col2:
            tone = st.selectbox(
                "Resume Tone",
                options=["professional", "confident", "concise", "impact-focused"],
                key=FORM_FIELD_KEYS["tone"],
            )

        job_description = st.text_area(
            "Target Job Description (optional but recommended)",
            placeholder="Paste the JD here for keyword matching and ATS optimization.",
            height=130,
            key=FORM_FIELD_KEYS["job_description"],
        )

        skills_raw = st.text_area(
            "Skills (comma or new line separated)",
            placeholder="Python, Streamlit, Machine Learning, SQL",
            height=100,
            key=FORM_FIELD_KEYS["skills_raw"],
        )

        st.markdown("### Education")
        education_raw = st.text_area(
            "One entry per line: Degree | Institution | Duration | Location | Details",
            placeholder="B.Tech CSE | Bennett University | 2022-2026 | Greater Noida | CGPA: 8.66",
            height=100,
            key=FORM_FIELD_KEYS["education_raw"],
        )

        st.markdown("### Work Experience")
        experience_raw = st.text_area(
            "One role per block.\nFirst line: Role | Company | Duration | Location\nNext lines: bullet points.\nSeparate blocks by a blank line.",
            placeholder="Software Intern | ABC Tech | Jan 2025 - Present | Remote\nBuilt X feature\nImproved Y by 20%",
            height=150,
            key=FORM_FIELD_KEYS["experience_raw"],
        )

        st.markdown("### Projects")
        projects_raw = st.text_area(
            "One project per block.\nFirst line: Project Name | Technologies | Year\nNext lines: bullet points.\nSeparate blocks by a blank line.",
            placeholder="AI Resume Builder | Python, Streamlit, Gemini API | 2026\nBuilt modular architecture\nImplemented PDF export",
            height=150,
            key=FORM_FIELD_KEYS["projects_raw"],
        )

        st.markdown("### Certifications")
        certifications_raw = st.text_area(
            "One certification per line",
            placeholder="Google AI Essentials\nAWS Cloud Practitioner",
            height=90,
            key=FORM_FIELD_KEYS["certifications_raw"],
        )

        st.markdown("### Achievements")
        achievements_raw = st.text_area(
            "One achievement per line",
            placeholder="Won 1st place in university hackathon",
            height=90,
            key=FORM_FIELD_KEYS["achievements_raw"],
        )

        submitted = st.form_submit_button("Generate ATS Resume")

    if not submitted:
        return False, None

    resume_input = ResumeInput(
        personal_info=PersonalInfo(
            full_name=full_name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            linkedin=linkedin.strip(),
            github=github.strip(),
            portfolio=portfolio.strip(),
            location=location.strip(),
        ),
        career_summary=career_summary.strip(),
        target_role=target_role.strip(),
        target_company=target_company.strip(),
        job_description=job_description.strip(),
        tone=tone.strip().lower(),
        skills=split_csv_or_lines(skills_raw),
        education=_parse_education(education_raw),
        experiences=_parse_experience(experience_raw),
        projects=_parse_projects(projects_raw),
        certifications=_clean_simple_lines(split_lines(certifications_raw)),
        achievements=_clean_simple_lines(split_lines(achievements_raw)),
    )

    errors = _validate_resume_input(resume_input)
    if errors:
        for error in errors:
            st.error(error)
        return False, None

    return True, resume_input
