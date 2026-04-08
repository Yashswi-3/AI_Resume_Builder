from __future__ import annotations

import re
from typing import Iterable

from src.domain.ats_models import ExperienceEntry, ProjectEntry


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _build_skill_set(skills: Iterable[str]) -> set[str]:
    return {_normalize(skill) for skill in skills if _normalize(skill)}


def _normalize_synonyms(synonyms: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, aliases in (synonyms or {}).items():
        canonical = _normalize(key)
        if not canonical:
            continue
        alias_values = [_normalize(alias) for alias in aliases if _normalize(alias)]
        normalized[canonical] = alias_values
    return normalized


def _term_in_skills(term: str, skill_set: set[str]) -> bool:
    if not term:
        return False
    for skill in skill_set:
        if term == skill or term in skill or skill in term:
            return True
    return False


def keyword_score(
    resume_skills: list[str],
    role_required: list[str],
    role_preferred: list[str],
    synonyms: dict[str, list[str]],
) -> float:
    skill_set = _build_skill_set(resume_skills)
    synonym_map = _normalize_synonyms(synonyms)

    def _is_match(keyword: str) -> bool:
        normalized = _normalize(keyword)
        if not normalized:
            return False
        if _term_in_skills(normalized, skill_set):
            return True
        for alias in synonym_map.get(normalized, []):
            if _term_in_skills(alias, skill_set):
                return True
        return False

    required_hits = sum(1 for item in role_required if _is_match(item))
    preferred_hits = sum(1 for item in role_preferred if _is_match(item))

    required_score = required_hits / max(1, len(role_required))
    preferred_score = preferred_hits / max(1, len(role_preferred))
    return max(0.0, min(1.0, (required_score * 0.7) + (preferred_score * 0.3)))


def experience_score(experience_entries: list[ExperienceEntry], role_seniority_keywords: dict[str, list[str]]) -> float:
    if not experience_entries:
        return 0.0

    text_blob = " ".join(
        [
            " ".join(entry.bullets)
            + " "
            + entry.title
            + " "
            + entry.company
            + " "
            + entry.duration
            for entry in experience_entries
        ]
    ).lower()

    senior_signal = 0.0
    for level, words in role_seniority_keywords.items():
        if any((word or "").lower() in text_blob for word in words):
            if level == "senior":
                senior_signal = max(senior_signal, 1.0)
            elif level == "mid":
                senior_signal = max(senior_signal, 0.75)
            elif level == "junior":
                senior_signal = max(senior_signal, 0.5)

    quant_hits = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|x|k|m|years?|months?)\b", text_blob))
    quant_signal = min(1.0, quant_hits / 8)
    return max(0.0, min(1.0, (senior_signal * 0.6) + (quant_signal * 0.4)))


def project_score(project_entries: list[ProjectEntry], role_preferred: list[str]) -> float:
    if not project_entries:
        return 0.0

    preferred_set = {_normalize(item) for item in role_preferred if _normalize(item)}
    if not preferred_set:
        return 0.5

    project_text = " ".join(
        [project.name + " " + " ".join(project.technologies) + " " + project.description for project in project_entries]
    ).lower()

    hits = 0
    for keyword in preferred_set:
        if keyword in project_text:
            hits += 1

    return max(0.0, min(1.0, hits / max(1, min(12, len(preferred_set)))))


def format_score(raw_text: str) -> float:
    text = raw_text or ""
    if not text.strip():
        return 0.0

    section_hits = 0
    for section in ["skills", "experience", "projects", "education", "summary"]:
        if re.search(rf"(^|\n)\s*{section}\s*[:\n]", text, re.IGNORECASE):
            section_hits += 1

    has_email = bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
    has_linkedin = "linkedin" in text.lower()
    parseability = min(1.0, len(text) / 2500)

    structure = section_hits / 5
    contact = 1.0 if (has_email or has_linkedin) else 0.0
    return max(0.0, min(1.0, (structure * 0.5) + (parseability * 0.35) + (contact * 0.15)))
