import json
import re
from typing import Any, Dict, List, Sequence, Tuple

from src.domain.models import ResumeInput, ResumeOutput
from src.prompts.resume_prompt import (
    CLEANING_OUTPUT_SCHEMA,
    RESPONSE_SCHEMA,
    SECTION_OUTPUT_SCHEMAS,
    build_ats_cleaning_prompt,
    build_section_generation_prompt,
)
from src.services.ai.gemini_client import GeminiClient


RESPONSE_KEYS = list(RESPONSE_SCHEMA.keys())

NOISE_TOKENS = {
    "skills",
    "skill",
    "education",
    "experience",
    "work experience",
    "projects",
    "project",
    "certifications",
    "certification",
    "achievements",
    "achievement",
    "professional information",
    "personal information",
    "professional summary",
}

SECTION_MAX_ITEMS = {
    "professional_summary": 2,
    "skills": 14,
    "education": 3,
    "certifications": 5,
    "achievements": 5,
}

MAX_BULLETS_PER_BLOCK = 3
MAX_LINES_PER_EXPERIENCE_BLOCK = 4
MAX_LINES_PER_PROJECT_BLOCK = 4
MAX_EXPERIENCE_BLOCKS = 4
MAX_PROJECT_BLOCKS = 4

PLACEHOLDER_TOKENS = {
    "organization",
    "company",
    "core technologies",
    "n/a",
    "na",
    "tbd",
}

DURATION_PATTERN = re.compile(
    r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4})\s*(?:-|to|–|—)\s*(present|current|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{4}|\d{4})\b",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")

ROLE_HINT_TOKENS = {
    "intern",
    "engineer",
    "developer",
    "analyst",
    "associate",
    "manager",
    "lead",
    "chair",
    "founder",
    "product",
    "operations",
}

COMPANY_HINT_TOKENS = {
    "private limited",
    "pvt",
    "inc",
    "llc",
    "ltd",
    "technologies",
    "education",
    "systems",
    "labs",
    "solutions",
    "university",
}

LOCATION_HINT_TOKENS = {
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

TECH_HINT_TOKENS = {
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

ACTION_VERB_TOKENS = {
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
    "into",
}


class ResumeGenerator:
    def __init__(
        self,
        gemini_client: GeminiClient,
        temperature: float = 0.35,
        max_output_tokens: int = 1400,
    ):
        self.gemini_client = gemini_client
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def generate(self, resume_input: ResumeInput) -> ResumeOutput:
        if self.is_test_input(resume_input):
            return self._dummy_output()

        try:
            local_clean_payload = self._build_local_cleaning_payload(resume_input)
            cleaned_payload, cleaning_meta = self._run_cleaning_pass(resume_input, local_clean_payload)

            data, section_meta = self._generate_sectional_payload(cleaned_payload)
            data = self._enrich_with_input_data(resume_input, data)
            data = self._enforce_section_constraints(data)

            quality_issues = self._quality_issues(data, resume_input)
            if quality_issues:
                recovered = self._recover_low_quality_output(resume_input, cleaned_payload, quality_issues)
                if recovered is not None:
                    return ResumeOutput.from_dict(recovered)

                diagnostics = self._build_diagnostics_metadata(
                    error_message="Low quality AI output after sectional generation.",
                    quality_issues=quality_issues,
                )
                return self._fallback_output(
                    resume_input,
                    mode="fallback_incomplete_ai",
                    metadata=diagnostics,
                )

            data["mode"] = "ai_sectional" if not section_meta["errors"] else "ai_sectional_partial"
            data["cleaning_mode"] = cleaning_meta.get("mode", "local_cleaned")
            data["section_calls"] = section_meta.get("section_calls", 0)
            data["successful_sections"] = section_meta.get("successful_sections", [])

            diagnostics_errors = []
            diagnostics_errors.extend(cleaning_meta.get("errors", []))
            diagnostics_errors.extend(section_meta.get("errors", []))
            if diagnostics_errors:
                data["errors"] = diagnostics_errors[:8]

            call_details = section_meta.get("last_call_details") or cleaning_meta.get("last_call_details") or {}
            self._attach_call_details(data, call_details)

            return ResumeOutput.from_dict(data)
        except Exception as error:
            diagnostics = self._build_diagnostics_metadata(error_message=str(error))
            return self._fallback_output(resume_input, mode="fallback", metadata=diagnostics)

    def _run_cleaning_pass(
        self,
        resume_input: ResumeInput,
        local_clean_payload: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        errors: List[str] = []
        last_call_details: Dict[str, Any] = {}
        text = ""

        try:
            system_prompt, user_prompt = build_ats_cleaning_prompt(resume_input, local_clean_payload)
            text = self.gemini_client.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=max(0.15, self.temperature - 0.1),
                max_output_tokens=min(self.max_output_tokens, 1200),
                response_mime_type="application/json",
            )
            last_call_details = self.gemini_client.get_last_call_details()
            parsed = self._parse_response_json(text)
            cleaned = self._normalize_cleaning_payload(parsed, local_clean_payload)
            return cleaned, {
                "mode": "ai_cleaned",
                "errors": errors,
                "last_call_details": last_call_details,
            }
        except Exception as error:
            errors.append(f"cleaning_pass:{self._safe_error(error)}")

        if text:
            try:
                repaired = self._repair_json_with_gemini(text, CLEANING_OUTPUT_SCHEMA)
                last_call_details = self.gemini_client.get_last_call_details()
                parsed = self._parse_response_json(repaired)
                cleaned = self._normalize_cleaning_payload(parsed, local_clean_payload)
                return cleaned, {
                    "mode": "ai_cleaned_repaired",
                    "errors": errors,
                    "last_call_details": last_call_details,
                }
            except Exception as repair_error:
                errors.append(f"cleaning_repair:{self._safe_error(repair_error)}")

        return local_clean_payload, {
            "mode": "local_cleaned",
            "errors": errors,
            "last_call_details": last_call_details,
        }

    def _generate_sectional_payload(
        self,
        cleaned_payload: Dict[str, Any],
        temperature_override: float | None = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        payload: Dict[str, Any] = {}
        section_errors: List[str] = []
        successful_sections: List[str] = []
        last_call_details: Dict[str, Any] = {}

        for section_name in RESPONSE_KEYS:
            try:
                values = self._generate_single_section(
                    section_name=section_name,
                    cleaned_payload=cleaned_payload,
                    temperature_override=temperature_override,
                )
                if not values:
                    raise ValueError("section returned no values")

                payload[section_name] = values
                successful_sections.append(section_name)
                last_call_details = self.gemini_client.get_last_call_details()
            except Exception as error:
                payload[section_name] = self._fallback_section_from_cleaned(section_name, cleaned_payload)
                section_errors.append(f"{section_name}:{self._safe_error(error)}")
                last_call_details = self.gemini_client.get_last_call_details()

        payload = self._enforce_section_constraints(payload)

        return payload, {
            "errors": section_errors,
            "successful_sections": successful_sections,
            "section_calls": len(RESPONSE_KEYS),
            "last_call_details": last_call_details,
        }

    def _generate_single_section(
        self,
        section_name: str,
        cleaned_payload: Dict[str, Any],
        temperature_override: float | None = None,
    ) -> List[str]:
        if section_name not in RESPONSE_KEYS:
            raise ValueError(f"Unsupported section: {section_name}")

        system_prompt, user_prompt = build_section_generation_prompt(section_name, cleaned_payload)
        token_budget = self._section_token_budget(section_name)
        text = self.gemini_client.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature_override if temperature_override is not None else self.temperature,
            max_output_tokens=token_budget,
            response_mime_type="application/json",
        )

        try:
            parsed = self._parse_response_json(text)
        except Exception:
            repaired = self._repair_json_with_gemini(text, SECTION_OUTPUT_SCHEMAS[section_name])
            parsed = self._parse_response_json(repaired)

        values = self._normalize_generated_section(section_name, parsed, cleaned_payload)
        if not values:
            raise ValueError("normalized section is empty")
        return values

    def _section_token_budget(self, section_name: str) -> int:
        preferred = {
            "professional_summary": 360,
            "skills": 320,
            "education": 340,
            "experience": 950,
            "projects": 850,
            "certifications": 260,
            "achievements": 280,
        }
        return max(220, min(self.max_output_tokens, preferred.get(section_name, 420)))

    def _normalize_generated_section(
        self,
        section_name: str,
        parsed_payload: Dict[str, Any],
        cleaned_payload: Dict[str, Any],
    ) -> List[str]:
        if section_name in {"professional_summary", "skills", "certifications", "achievements"}:
            raw_items = parsed_payload.get("items", parsed_payload.get(section_name, []))
            max_items = SECTION_MAX_ITEMS.get(section_name, 8)
            return self._compress_lines(self._normalize_list(raw_items), max_items=max_items, max_words=24)

        if section_name == "education":
            raw_items = parsed_payload.get("items", parsed_payload.get("education", []))
            lines = self._normalize_education_lines(raw_items, cleaned_payload.get("education", []))
            return lines[: SECTION_MAX_ITEMS["education"]]

        if section_name == "experience":
            raw_entries = parsed_payload.get("items", parsed_payload.get("experience", []))
            entries = self._normalize_experience_entries(raw_entries, cleaned_payload.get("experience", []))
            return self._flatten_experience_entries(entries)

        if section_name == "projects":
            raw_entries = parsed_payload.get("items", parsed_payload.get("projects", []))
            entries = self._normalize_project_entries(raw_entries, cleaned_payload.get("projects", []))
            return self._flatten_project_entries(entries)

        return []

    def _fallback_section_from_cleaned(self, section_name: str, cleaned_payload: Dict[str, Any]) -> List[str]:
        if section_name == "professional_summary":
            seed = self._clean_basic_text(cleaned_payload.get("professional_summary_seed", ""))
            lines = self._extract_sentence_points(seed, max_items=2, max_words=24)
            if len(lines) < 2 and seed:
                lines = self._compress_lines([seed], max_items=2, max_words=24)
            if len(lines) < 2:
                role = self._clean_basic_text(cleaned_payload.get("target_role", "")) or "Software Engineer"
                lines.append(f"Final-year candidate targeting {role} roles with strong technical foundations.")
                lines.append("Builds ATS-focused, impact-oriented resume content from structured achievements.")
            return lines[:2]

        if section_name == "skills":
            return self._compress_lines(
                cleaned_payload.get("skills", []),
                max_items=SECTION_MAX_ITEMS["skills"],
                max_words=5,
            )

        if section_name == "education":
            return self._normalize_education_lines(
                cleaned_payload.get("education", []),
                cleaned_payload.get("education", []),
            )[: SECTION_MAX_ITEMS["education"]]

        if section_name == "experience":
            return self._flatten_experience_entries(cleaned_payload.get("experience", []))

        if section_name == "projects":
            return self._flatten_project_entries(cleaned_payload.get("projects", []))

        if section_name == "certifications":
            return self._compress_lines(
                cleaned_payload.get("certifications", []),
                max_items=SECTION_MAX_ITEMS["certifications"],
                max_words=12,
            )

        if section_name == "achievements":
            return self._compress_lines(
                cleaned_payload.get("achievements", []),
                max_items=SECTION_MAX_ITEMS["achievements"],
                max_words=22,
            )

        return []

    def _build_local_cleaning_payload(self, resume_input: ResumeInput) -> Dict[str, Any]:
        summary_seed = self._clean_basic_text(resume_input.career_summary)
        skills = self._clean_simple_list(resume_input.skills, max_items=24, max_words=5)
        education = self._build_education_lines(resume_input)
        experiences = self._build_experience_entries(resume_input)
        projects = self._build_project_entries(resume_input)
        certifications = self._clean_simple_list(resume_input.certifications, max_items=10, max_words=12)
        achievements = self._clean_simple_list(resume_input.achievements, max_items=10, max_words=22)

        return {
            "professional_summary_seed": summary_seed,
            "skills": skills,
            "education": education,
            "experience": experiences,
            "projects": projects,
            "certifications": certifications,
            "achievements": achievements,
            "job_description_keywords": self._extract_keywords_from_job_description(resume_input.job_description),
            "target_role": self._clean_basic_text(resume_input.target_role),
            "target_company": self._clean_basic_text(resume_input.target_company),
            "tone": self._clean_basic_text(resume_input.tone) or "professional",
            "job_description": self._clean_basic_text(resume_input.job_description),
        }

    def _build_education_lines(self, resume_input: ResumeInput) -> List[str]:
        lines: List[str] = []
        for item in resume_input.education:
            degree = self._clean_basic_text(item.degree)
            institution = self._clean_basic_text(item.institution)
            duration = self._clean_basic_text(item.duration)
            location = self._clean_basic_text(item.location)
            details = self._clean_basic_text(item.details)

            if degree and not institution and "," in degree:
                parts = [part.strip() for part in degree.split(",") if part.strip()]
                if len(parts) >= 2:
                    institution = institution or self._clean_basic_text(parts[0])
                    degree = self._clean_basic_text(parts[1])
                    trailing = [self._clean_basic_text(part) for part in parts[2:]]
                    details = details or ", ".join(part for part in trailing if part)

            parts = [degree, institution, duration, location, details]
            while parts and not parts[-1]:
                parts.pop()

            line = " | ".join(part for part in parts if part)
            if line:
                lines.append(line)

        return self._normalize_education_lines(lines, lines)

    def _build_experience_entries(self, resume_input: ResumeInput) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for item in resume_input.experiences:
            role = self._clean_basic_text(item.role)
            company = self._clean_basic_text(item.company)
            duration = self._clean_basic_text(item.duration)
            location = self._clean_basic_text(item.location)

            highlights = self._prioritize_highlights(item.bullet_points, max_items=10, max_words=26)
            if not highlights and role:
                highlights = self._extract_sentence_points(role, max_items=6, max_words=24)

            if len(role.split()) > 12:
                role = self._truncate_words(role, 8)

            if any([role, company, duration, location, highlights]):
                entries.append(
                    {
                        "role": role,
                        "company": company,
                        "duration": duration,
                        "location": location,
                        "highlights": highlights,
                    }
                )

        return self._normalize_experience_entries(entries, entries)

    def _build_project_entries(self, resume_input: ResumeInput) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for item in resume_input.projects:
            name = self._clean_basic_text(item.name)
            technologies = self._clean_basic_text(item.technologies)
            year = self._clean_basic_text(item.year)

            highlights = self._prioritize_highlights(item.bullet_points, max_items=8, max_words=24)
            if not highlights and name:
                highlights = self._extract_sentence_points(name, max_items=4, max_words=20)

            if any([name, technologies, year, highlights]):
                entries.append(
                    {
                        "name": name,
                        "technologies": technologies,
                        "year": year,
                        "highlights": highlights,
                    }
                )

        return self._normalize_project_entries(entries, entries)

    def _normalize_cleaning_payload(
        self,
        payload: Dict[str, Any],
        fallback_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        summary_seed = self._clean_basic_text(payload.get("professional_summary_seed", ""))
        if not summary_seed:
            summary_seed = self._clean_basic_text(fallback_payload.get("professional_summary_seed", ""))

        skills = self._clean_simple_list(payload.get("skills", []), max_items=24, max_words=5)
        if not skills:
            skills = list(fallback_payload.get("skills", []))

        education = self._normalize_education_lines(
            payload.get("education", []),
            fallback_payload.get("education", []),
        )

        experience = self._normalize_experience_entries(
            payload.get("experience", []),
            fallback_payload.get("experience", []),
        )

        projects = self._normalize_project_entries(
            payload.get("projects", []),
            fallback_payload.get("projects", []),
        )

        certifications = self._clean_simple_list(
            payload.get("certifications", []),
            max_items=10,
            max_words=12,
        )
        if not certifications:
            certifications = list(fallback_payload.get("certifications", []))

        achievements = self._clean_simple_list(
            payload.get("achievements", []),
            max_items=10,
            max_words=22,
        )
        if not achievements:
            achievements = list(fallback_payload.get("achievements", []))

        keywords = self._clean_simple_list(payload.get("job_description_keywords", []), max_items=20, max_words=4)
        if not keywords:
            keywords = list(fallback_payload.get("job_description_keywords", []))

        return {
            "professional_summary_seed": summary_seed,
            "skills": skills,
            "education": education,
            "experience": experience,
            "projects": projects,
            "certifications": certifications,
            "achievements": achievements,
            "job_description_keywords": keywords,
            "target_role": fallback_payload.get("target_role", ""),
            "target_company": fallback_payload.get("target_company", ""),
            "tone": fallback_payload.get("tone", "professional"),
            "job_description": fallback_payload.get("job_description", ""),
        }

    def _normalize_experience_entries(
        self,
        value: Any,
        fallback_entries: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        raw_entries = value if isinstance(value, list) else []
        fallback_normalized = [
            normalized
            for normalized in (self._normalize_single_experience_entry(raw) for raw in fallback_entries)
            if normalized
        ]

        entries: List[Dict[str, Any]] = []

        for index, raw in enumerate(raw_entries):
            normalized = self._normalize_single_experience_entry(raw)
            fallback = fallback_normalized[index] if index < len(fallback_normalized) else {}
            merged = self._merge_experience_entries(normalized, fallback)
            if merged:
                entries.append(merged)

        if not entries:
            entries = fallback_normalized

        if entries and len(entries) < MAX_EXPERIENCE_BLOCKS:
            existing_keys = {self._experience_entry_key(entry) for entry in entries}
            for fallback in fallback_normalized:
                key = self._experience_entry_key(fallback)
                if key in existing_keys:
                    continue
                entries.append(fallback)
                existing_keys.add(key)
                if len(entries) >= MAX_EXPERIENCE_BLOCKS:
                    break

        return entries[:MAX_EXPERIENCE_BLOCKS]

    def _normalize_single_experience_entry(self, raw: Any) -> Dict[str, Any]:
        role = ""
        company = ""
        duration = ""
        location = ""
        highlights: List[str] = []

        if isinstance(raw, dict):
            role = self._clean_basic_text(raw.get("role", ""))
            company = self._clean_basic_text(raw.get("company", ""))
            duration = self._clean_basic_text(raw.get("duration", ""))
            location = self._clean_basic_text(raw.get("location", ""))
            highlights = self._prioritize_highlights(
                raw.get("bullets", raw.get("highlights", raw.get("points", []))),
                max_items=8,
                max_words=24,
            )
        elif isinstance(raw, str):
            text = self._clean_basic_text(raw)
            if "|" in text:
                parts = [part.strip() for part in text.split("|")]
                role = self._clean_basic_text(parts[0] if len(parts) > 0 else "")
                company = self._clean_basic_text(parts[1] if len(parts) > 1 else "")
                duration = self._clean_basic_text(parts[2] if len(parts) > 2 else "")
                location = self._clean_basic_text(parts[3] if len(parts) > 3 else "")
            else:
                highlights = self._extract_sentence_points(text, max_items=6, max_words=22)

        inferred = self._infer_experience_fields([role, company, duration, location, *highlights])
        role = role or inferred.get("role", "")
        company = company or inferred.get("company", "")
        duration = duration or inferred.get("duration", "")
        location = location or inferred.get("location", "")
        return self._sanitize_experience_entry(role, company, duration, location, highlights)

    def _normalize_project_entries(
        self,
        value: Any,
        fallback_entries: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        raw_entries = value if isinstance(value, list) else []
        fallback_normalized = [
            normalized
            for normalized in (self._normalize_single_project_entry(raw) for raw in fallback_entries)
            if normalized
        ]

        entries: List[Dict[str, Any]] = []

        for index, raw in enumerate(raw_entries):
            normalized = self._normalize_single_project_entry(raw)
            fallback = fallback_normalized[index] if index < len(fallback_normalized) else {}
            merged = self._merge_project_entries(normalized, fallback)
            if merged:
                entries.append(merged)

        if not entries:
            entries = fallback_normalized

        if entries and len(entries) < MAX_PROJECT_BLOCKS:
            existing_keys = {self._project_entry_key(entry) for entry in entries}
            for fallback in fallback_normalized:
                key = self._project_entry_key(fallback)
                if key in existing_keys:
                    continue
                entries.append(fallback)
                existing_keys.add(key)
                if len(entries) >= MAX_PROJECT_BLOCKS:
                    break

        return entries[:MAX_PROJECT_BLOCKS]

    def _normalize_single_project_entry(self, raw: Any) -> Dict[str, Any]:
        name = ""
        technologies = ""
        year = ""
        highlights: List[str] = []

        if isinstance(raw, dict):
            name = self._clean_basic_text(raw.get("name", ""))
            technologies = self._clean_basic_text(raw.get("technologies", ""))
            year = self._clean_basic_text(raw.get("year", ""))
            highlights = self._prioritize_highlights(
                raw.get("bullets", raw.get("highlights", raw.get("points", []))),
                max_items=8,
                max_words=24,
            )
        elif isinstance(raw, str):
            text = self._clean_basic_text(raw)
            if "|" in text:
                parts = [part.strip() for part in text.split("|")]
                name = self._clean_basic_text(parts[0] if len(parts) > 0 else "")
                technologies = self._clean_basic_text(parts[1] if len(parts) > 1 else "")
                year = self._clean_basic_text(parts[2] if len(parts) > 2 else "")
            else:
                highlights = self._extract_sentence_points(text, max_items=6, max_words=22)

        inferred = self._infer_project_fields([name, technologies, year, *highlights])
        name = name or inferred.get("name", "")
        technologies = technologies or inferred.get("technologies", "")
        year = year or inferred.get("year", "")
        return self._sanitize_project_entry(name, technologies, year, highlights)

    def _merge_experience_entries(self, primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        source_primary = primary or {}
        source_fallback = fallback or {}

        role = self._clean_basic_text(source_primary.get("role", "")) or self._clean_basic_text(
            source_fallback.get("role", "")
        )
        company = self._clean_basic_text(source_primary.get("company", "")) or self._clean_basic_text(
            source_fallback.get("company", "")
        )
        duration = self._clean_basic_text(source_primary.get("duration", "")) or self._clean_basic_text(
            source_fallback.get("duration", "")
        )
        location = self._clean_basic_text(source_primary.get("location", "")) or self._clean_basic_text(
            source_fallback.get("location", "")
        )

        combined_highlights = []
        combined_highlights.extend(source_primary.get("highlights", source_primary.get("bullets", [])))
        combined_highlights.extend(source_fallback.get("highlights", source_fallback.get("bullets", [])))
        highlights = self._prioritize_highlights(combined_highlights, max_items=8, max_words=24)

        inferred = self._infer_experience_fields([role, company, duration, location, *highlights])
        role = role or inferred.get("role", "")
        company = company or inferred.get("company", "")
        duration = duration or inferred.get("duration", "")
        location = location or inferred.get("location", "")
        return self._sanitize_experience_entry(role, company, duration, location, highlights)

    def _merge_project_entries(self, primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        source_primary = primary or {}
        source_fallback = fallback or {}

        name = self._clean_basic_text(source_primary.get("name", "")) or self._clean_basic_text(
            source_fallback.get("name", "")
        )
        technologies = self._clean_basic_text(source_primary.get("technologies", "")) or self._clean_basic_text(
            source_fallback.get("technologies", "")
        )
        year = self._clean_basic_text(source_primary.get("year", "")) or self._clean_basic_text(
            source_fallback.get("year", "")
        )

        combined_highlights = []
        combined_highlights.extend(source_primary.get("highlights", source_primary.get("bullets", [])))
        combined_highlights.extend(source_fallback.get("highlights", source_fallback.get("bullets", [])))
        highlights = self._prioritize_highlights(combined_highlights, max_items=8, max_words=24)

        inferred = self._infer_project_fields([name, technologies, year, *highlights])
        name = name or inferred.get("name", "")
        technologies = technologies or inferred.get("technologies", "")
        year = year or inferred.get("year", "")
        return self._sanitize_project_entry(name, technologies, year, highlights)

    def _experience_entry_key(self, entry: Dict[str, Any]) -> str:
        role = self._normalize_for_noise(entry.get("role", ""))
        company = self._normalize_for_noise(entry.get("company", ""))
        duration = self._normalize_for_noise(entry.get("duration", ""))
        return f"{role}|{company}|{duration}"

    def _project_entry_key(self, entry: Dict[str, Any]) -> str:
        name = self._normalize_for_noise(entry.get("name", ""))
        technologies = self._normalize_for_noise(entry.get("technologies", ""))
        year = self._normalize_for_noise(entry.get("year", ""))
        return f"{name}|{technologies}|{year}"

    def _sanitize_experience_entry(
        self,
        role: str,
        company: str,
        duration: str,
        location: str,
        highlights: Sequence[str],
    ) -> Dict[str, Any]:
        role = self._clean_basic_text(role)
        company = self._clean_basic_text(company)
        duration = self._clean_basic_text(duration)
        location = self._clean_basic_text(location)

        highlights_clean = self._prioritize_highlights(highlights, max_items=8, max_words=24)

        if role and self._normalize_for_noise(role) in PLACEHOLDER_TOKENS:
            role = ""
        if company and self._normalize_for_noise(company) in PLACEHOLDER_TOKENS:
            company = ""

        if company and self._looks_like_role(company) and not self._looks_like_company(company):
            company = ""

        if role and company and self._normalize_for_noise(role) == self._normalize_for_noise(company):
            if self._looks_like_company(role) and not self._looks_like_company(company):
                role = ""
            else:
                company = ""

        if not duration or not location:
            inferred_from_highlights = self._infer_experience_fields(highlights_clean)
            duration = duration or inferred_from_highlights.get("duration", "")
            location = location or inferred_from_highlights.get("location", "")

        if self._is_low_quality_experience_header(role, company):
            return {}

        header_values = {self._normalize_for_noise(value) for value in [role, company, duration, location] if value}
        highlights_clean = [
            line for line in highlights_clean if self._normalize_for_noise(line) not in header_values
        ]

        if not any([role, company, duration, location, highlights_clean]):
            return {}

        return {
            "role": role,
            "company": company,
            "duration": duration,
            "location": location,
            "highlights": highlights_clean,
        }

    def _sanitize_project_entry(
        self,
        name: str,
        technologies: str,
        year: str,
        highlights: Sequence[str],
    ) -> Dict[str, Any]:
        name = self._clean_basic_text(name)
        technologies = self._clean_basic_text(technologies)
        year = self._clean_basic_text(year)
        highlights_clean = self._prioritize_highlights(highlights, max_items=8, max_words=24)

        if name and self._normalize_for_noise(name) in PLACEHOLDER_TOKENS:
            name = ""
        if technologies and self._normalize_for_noise(technologies) in PLACEHOLDER_TOKENS:
            technologies = ""

        if name and technologies and self._normalize_for_noise(name) == self._normalize_for_noise(technologies):
            technologies = ""

        if not year:
            inferred = self._infer_project_fields([name, technologies, *highlights_clean])
            year = inferred.get("year", "")

        if self._is_low_quality_project_header(name, technologies):
            return {}

        header_values = {self._normalize_for_noise(value) for value in [name, technologies, year] if value}
        highlights_clean = [
            line for line in highlights_clean if self._normalize_for_noise(line) not in header_values
        ]

        if not any([name, technologies, year, highlights_clean]):
            return {}

        return {
            "name": name,
            "technologies": technologies,
            "year": year,
            "highlights": highlights_clean,
        }

    def _is_low_quality_experience_header(self, role: str, company: str) -> bool:
        role_clean = self._clean_basic_text(role)
        company_clean = self._clean_basic_text(company)
        role_key = self._normalize_for_noise(role_clean)
        company_key = self._normalize_for_noise(company_clean)

        if not role_key and not company_key:
            return True
        if role_key and company_key and role_key == company_key:
            return True
        if role_clean and len(role_clean.split()) > 14:
            return True
        if role_clean and "," in role_clean and "/" not in role_clean:
            return True
        if company_clean and len(company_clean.split()) > 10 and not self._looks_like_company(company_clean):
            return True
        if role_clean and re.search(r"\d", role_clean) and len(role_clean.split()) > 4:
            return True
        return False

    def _is_low_quality_project_header(self, name: str, technologies: str) -> bool:
        name_clean = self._clean_basic_text(name)
        technologies_clean = self._clean_basic_text(technologies)
        name_key = self._normalize_for_noise(name_clean)

        if not name_key:
            return True
        if name_key in {"project", "application", "app", "system", "website"}:
            return True
        if name_clean and len(name_clean.split()) > 14:
            return True
        if name_clean and technologies_clean and self._normalize_for_noise(name_clean) == self._normalize_for_noise(
            technologies_clean
        ):
            return True
        return False

    def _infer_experience_fields(self, candidates: Sequence[str]) -> Dict[str, str]:
        role = ""
        company = ""
        duration = ""
        location = ""

        cleaned_candidates = [self._clean_basic_text(value) for value in candidates]
        cleaned_candidates = [value for value in cleaned_candidates if value and not self._is_noise_line(value)]

        for value in cleaned_candidates:
            if not duration and self._looks_like_duration(value):
                duration = value
                continue
            if not location and self._looks_like_location(value):
                location = value
                continue
            if not company and self._looks_like_company(value):
                company = value
                continue
            if not role and self._looks_like_role(value):
                role = value

        if not role:
            for value in cleaned_candidates:
                if self._looks_like_duration(value) or self._looks_like_company(value):
                    continue
                if 1 < len(value.split()) <= 10:
                    role = value
                    break

        if not company:
            for value in cleaned_candidates:
                if self._looks_like_company(value):
                    company = value
                    break

        return {
            "role": role,
            "company": company,
            "duration": duration,
            "location": location,
        }

    def _infer_project_fields(self, candidates: Sequence[str]) -> Dict[str, str]:
        name = ""
        technologies = ""
        year = ""

        cleaned_candidates = [self._clean_basic_text(value) for value in candidates]
        cleaned_candidates = [value for value in cleaned_candidates if value and not self._is_noise_line(value)]

        for value in cleaned_candidates:
            if not year:
                year_match = YEAR_PATTERN.search(value)
                if year_match:
                    year = year_match.group(0)
                    continue
            if not technologies and self._looks_like_technologies(value):
                technologies = value
                continue
            if not name and len(value.split()) <= 12 and not self._looks_like_duration(value):
                name = value

        if not name:
            for value in cleaned_candidates:
                if self._looks_like_technologies(value) or self._looks_like_duration(value):
                    continue
                if 1 < len(value.split()) <= 12:
                    name = value
                    break

        if not technologies:
            for value in cleaned_candidates:
                if self._looks_like_technologies(value):
                    technologies = value
                    break

        return {
            "name": name,
            "technologies": technologies,
            "year": year,
        }

    def _looks_like_duration(self, text: str) -> bool:
        value = self._clean_basic_text(text)
        lowered = value.lower()
        if not value:
            return False
        if DURATION_PATTERN.search(value):
            return True
        return bool(YEAR_PATTERN.search(value)) and (
            "-" in value or " to " in lowered or "present" in lowered or "current" in lowered
        )

    def _looks_like_company(self, text: str) -> bool:
        value = self._clean_basic_text(text)
        lowered = value.lower()
        if not value or self._looks_like_duration(value):
            return False
        role_hint = self._has_hint_token(lowered, ROLE_HINT_TOKENS)
        company_hint = self._has_hint_token(lowered, COMPANY_HINT_TOKENS)
        if role_hint and not company_hint:
            return False
        if "," in value and not company_hint:
            return False
        if self._has_hint_token(lowered, HEADER_NOISE_TOKENS) and not company_hint:
            return False
        if company_hint:
            return True
        words = value.split()
        return len(words) <= 7 and words and words[0][:1].isupper() and words[-1][:1].isupper()

    def _looks_like_role(self, text: str) -> bool:
        value = self._clean_basic_text(text)
        lowered = value.lower()
        if not value or self._looks_like_duration(value):
            return False
        if not value[:1].isupper():
            return False
        if "," in value and "/" not in value:
            return False
        if len(value.split()) > 12:
            return False
        if re.search(r"\d", value):
            return False
        if self._has_hint_token(lowered, ACTION_VERB_TOKENS):
            return False
        return self._has_hint_token(lowered, ROLE_HINT_TOKENS)

    def _looks_like_institution(self, text: str) -> bool:
        value = self._clean_basic_text(text)
        lowered = value.lower()
        if not value:
            return False
        return any(token in lowered for token in {"university", "college", "institute", "school", "academy", "uni"})

    def _looks_like_location(self, text: str) -> bool:
        value = self._clean_basic_text(text)
        lowered = value.lower()
        if not value or self._looks_like_duration(value):
            return False
        if self._has_hint_token(lowered, ROLE_HINT_TOKENS):
            return False
        if self._has_hint_token(lowered, COMPANY_HINT_TOKENS):
            return False
        if self._has_hint_token(lowered, HEADER_NOISE_TOKENS):
            return False
        if self._has_hint_token(lowered, LOCATION_HINT_TOKENS):
            return True
        return "," in value and len(value.split()) <= 8

    def _looks_like_technologies(self, text: str) -> bool:
        value = self._clean_basic_text(text)
        lowered = value.lower()
        if not value or self._looks_like_duration(value):
            return False
        if self._has_hint_token(lowered, TECH_HINT_TOKENS):
            return True
        return "," in value and len(value.split(",")) >= 2 and len(value.split()) <= 22

    def _has_hint_token(self, text: str, hints: Sequence[str]) -> bool:
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

    def _prioritize_highlights(self, values: Any, max_items: int, max_words: int) -> List[str]:
        lines = self._normalize_list(values)
        scored: List[Tuple[int, int, str]] = []

        for index, raw_line in enumerate(lines):
            text = self._clean_basic_text(raw_line)
            text = self._clean_basic_text(text.lstrip("-*• "))
            if not text or self._is_noise_line(text):
                continue

            normalized = self._normalize_for_noise(text)
            if normalized in PLACEHOLDER_TOKENS:
                continue

            words = text.split()
            if len(words) < 4:
                continue

            lowered = text.lower()
            score = 0
            if any(token in lowered for token in ACTION_VERB_TOKENS):
                score += 2
            if re.search(r"\d", text):
                score += 2
            if any(
                token in lowered
                for token in {"product", "system", "platform", "api", "testing", "release", "team", "users", "students"}
            ):
                score += 1

            scored.append((score, index, self._truncate_words(text, max_words)))

        if not scored:
            return self._compress_lines(lines, max_items=max_items, max_words=max_words)

        scored.sort(key=lambda item: (-item[0], item[1]))

        selected: List[str] = []
        seen = set()
        semantic_seen = set()
        for _, _, text in scored:
            normalized = self._normalize_for_noise(text)
            if not normalized or normalized in seen or normalized in PLACEHOLDER_TOKENS:
                continue

            semantic_key = self._semantic_line_key(text)
            if semantic_key and semantic_key in semantic_seen:
                continue

            seen.add(normalized)
            if semantic_key:
                semantic_seen.add(semantic_key)
            selected.append(text)
            if len(selected) >= max_items:
                break

        return selected

    def _normalize_education_lines(self, value: Any, fallback_lines: Sequence[str]) -> List[str]:
        raw_items: List[Any] = []
        if isinstance(value, list):
            raw_items = value
        elif value is not None:
            raw_items = [value]

        lines: List[str] = []
        for item in raw_items:
            if isinstance(item, dict):
                degree = self._clean_basic_text(item.get("degree", ""))
                institution = self._clean_basic_text(item.get("institution", ""))
                duration = self._clean_basic_text(item.get("duration", ""))
                location = self._clean_basic_text(item.get("location", ""))
                details = self._clean_basic_text(item.get("details", ""))
                if degree and self._looks_like_institution(degree) and institution and not self._looks_like_institution(institution):
                    degree, institution = institution, degree
            else:
                degree, institution, duration, location, details = self._parse_education_line(
                    self._clean_basic_text(self._stringify_item(item))
                )

            parts = [degree, institution, duration, location, details]
            while parts and not parts[-1]:
                parts.pop()
            line = " | ".join(part for part in parts if part)

            if line and not self._is_noise_line(line):
                lines.append(line)

        if not lines:
            lines = [self._clean_basic_text(line) for line in fallback_lines if self._clean_basic_text(line)]

        return self._compress_lines(lines, max_items=SECTION_MAX_ITEMS["education"], max_words=28)

    def _parse_education_line(self, line: str) -> Tuple[str, str, str, str, str]:
        text = self._clean_basic_text(line)
        if not text:
            return "", "", "", "", ""

        degree = ""
        institution = ""
        duration = ""
        location = ""
        details = ""

        if "|" in text:
            parts = [self._clean_basic_text(part) for part in text.split("|")]
            degree = parts[0] if len(parts) > 0 else ""
            institution = parts[1] if len(parts) > 1 else ""
            duration = parts[2] if len(parts) > 2 else ""
            location = parts[3] if len(parts) > 3 else ""
            details = " | ".join(part for part in parts[4:] if part).strip()
        else:
            parts = [self._clean_basic_text(part) for part in text.split(",") if self._clean_basic_text(part)]
            if parts:
                first = parts[0] if len(parts) > 0 else ""
                second = parts[1] if len(parts) > 1 else ""
                trailing = parts[2:] if len(parts) > 2 else []

                if self._looks_like_institution(first) and second:
                    institution = first
                    degree = second
                else:
                    degree = first
                    institution = second

                details = ", ".join(part for part in trailing if part)

        if degree and self._looks_like_institution(degree) and institution and not self._looks_like_institution(institution):
            degree, institution = institution, degree

        if duration and not self._looks_like_duration(duration):
            details = ", ".join(part for part in [duration, details] if part)
            duration = ""

        return degree, institution, duration, location, details

    def _flatten_experience_entries(self, entries: Sequence[Dict[str, Any]]) -> List[str]:
        lines: List[str] = []
        for entry in list(entries)[:MAX_EXPERIENCE_BLOCKS]:
            role = self._clean_basic_text(entry.get("role", ""))
            company = self._clean_basic_text(entry.get("company", ""))
            duration = self._clean_basic_text(entry.get("duration", ""))
            location = self._clean_basic_text(entry.get("location", ""))

            if self._is_low_quality_experience_header(role, company):
                continue

            header = " | ".join([role, company, duration, location])
            lines.append(header)

            highlights = self._prioritize_highlights(
                entry.get("highlights", entry.get("bullets", [])),
                max_items=MAX_BULLETS_PER_BLOCK,
                max_words=24,
            )
            lines.extend(highlights[:MAX_BULLETS_PER_BLOCK])

        return self._limit_section_blocks(
            lines,
            min_parts=4,
            max_lines_per_block=MAX_LINES_PER_EXPERIENCE_BLOCK,
            max_blocks=MAX_EXPERIENCE_BLOCKS,
        )

    def _flatten_project_entries(self, entries: Sequence[Dict[str, Any]]) -> List[str]:
        lines: List[str] = []
        for entry in list(entries)[:MAX_PROJECT_BLOCKS]:
            name = self._clean_basic_text(entry.get("name", ""))
            technologies = self._clean_basic_text(entry.get("technologies", ""))
            year = self._clean_basic_text(entry.get("year", ""))

            if self._is_low_quality_project_header(name, technologies):
                continue

            header = " | ".join([name, technologies, year])
            lines.append(header)

            highlights = self._prioritize_highlights(
                entry.get("highlights", entry.get("bullets", [])),
                max_items=MAX_BULLETS_PER_BLOCK,
                max_words=24,
            )
            lines.extend(highlights[:MAX_BULLETS_PER_BLOCK])

        return self._limit_section_blocks(
            lines,
            min_parts=3,
            max_lines_per_block=MAX_LINES_PER_PROJECT_BLOCK,
            max_blocks=MAX_PROJECT_BLOCKS,
        )

    def _enforce_section_constraints(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        constrained: Dict[str, Any] = dict(payload)

        constrained["professional_summary"] = self._compress_lines(
            constrained.get("professional_summary", []),
            max_items=SECTION_MAX_ITEMS["professional_summary"],
            max_words=24,
        )

        constrained["skills"] = self._compress_lines(
            constrained.get("skills", []),
            max_items=SECTION_MAX_ITEMS["skills"],
            max_words=5,
        )

        constrained["education"] = self._normalize_education_lines(
            constrained.get("education", []),
            constrained.get("education", []),
        )

        constrained["experience"] = self._limit_section_blocks(
            constrained.get("experience", []),
            min_parts=4,
            max_lines_per_block=MAX_LINES_PER_EXPERIENCE_BLOCK,
            max_blocks=MAX_EXPERIENCE_BLOCKS,
        )

        constrained["projects"] = self._limit_section_blocks(
            constrained.get("projects", []),
            min_parts=3,
            max_lines_per_block=MAX_LINES_PER_PROJECT_BLOCK,
            max_blocks=MAX_PROJECT_BLOCKS,
        )

        constrained["certifications"] = self._compress_lines(
            constrained.get("certifications", []),
            max_items=SECTION_MAX_ITEMS["certifications"],
            max_words=12,
        )

        constrained["achievements"] = self._compress_lines(
            constrained.get("achievements", []),
            max_items=SECTION_MAX_ITEMS["achievements"],
            max_words=22,
        )

        return constrained

    def _limit_section_blocks(
        self,
        lines: Sequence[str],
        min_parts: int,
        max_lines_per_block: int,
        max_blocks: int,
    ) -> List[str]:
        normalized_lines = self._normalize_list(lines)

        blocks: List[Dict[str, Any]] = []
        current_block: Dict[str, Any] | None = None

        for line in normalized_lines:
            parts = [part.strip() for part in line.split("|")]
            is_header = len(parts) >= min_parts and bool(parts[0])

            if is_header:
                if current_block is not None:
                    blocks.append(current_block)

                header = " | ".join(self._clean_basic_text(part) for part in parts[:min_parts])
                current_block = {"header": header, "bullets": []}
                continue

            if current_block is None:
                continue

            bullet = self._clean_basic_text(line.lstrip("- ").strip())
            if bullet:
                current_block["bullets"].append(self._truncate_words(bullet, 24))

        if current_block is not None:
            blocks.append(current_block)

        if not blocks:
            return []

        result: List[str] = []
        seen_headers = set()
        for block in blocks[:max_blocks]:
            header = self._clean_basic_text(block.get("header", ""))
            header_key = self._normalize_for_noise(header)
            if not header_key or header_key in seen_headers:
                continue

            seen_headers.add(header_key)
            result.append(header)

            allowed_bullets = max(0, max_lines_per_block - 1)
            if allowed_bullets == 0:
                continue

            seen_bullets = set()
            added_bullets = 0
            for bullet in block["bullets"]:
                cleaned_bullet = self._clean_basic_text(bullet)
                if not cleaned_bullet:
                    continue
                bullet_key = self._semantic_line_key(cleaned_bullet)
                if bullet_key and bullet_key in seen_bullets:
                    continue
                if bullet_key:
                    seen_bullets.add(bullet_key)
                result.append(self._truncate_words(cleaned_bullet, 24))
                added_bullets += 1
                if added_bullets >= allowed_bullets:
                    break

        return result

    def _extract_keywords_from_job_description(self, text: str) -> List[str]:
        normalized = self._clean_basic_text(text).lower()
        if not normalized:
            return []

        phrases = [
            "software engineer",
            "backend development",
            "distributed systems",
            "machine learning",
            "api design",
            "scalable systems",
            "cross-functional",
        ]

        selected = [phrase for phrase in phrases if phrase in normalized]
        return selected[:12]

    def _compress_lines(self, lines: Sequence[str], max_items: int, max_words: int) -> List[str]:
        compressed: List[str] = []
        seen = set()
        semantic_seen = set()

        for raw_line in lines:
            text = self._clean_basic_text(self._stringify_item(raw_line))
            if not text or self._is_noise_line(text):
                continue

            trimmed = self._truncate_words(text, max_words)
            key = trimmed.lower()
            if key in seen:
                continue

            semantic_key = self._semantic_line_key(trimmed)
            if semantic_key and semantic_key in semantic_seen:
                continue

            seen.add(key)
            if semantic_key:
                semantic_seen.add(semantic_key)
            compressed.append(trimmed)
            if len(compressed) >= max_items:
                break

        return compressed

    def _clean_simple_list(self, values: Any, max_items: int, max_words: int) -> List[str]:
        lines = self._normalize_list(values)
        return self._compress_lines(lines, max_items=max_items, max_words=max_words)

    def _extract_sentence_points(self, text: str, max_items: int, max_words: int) -> List[str]:
        cleaned = self._clean_basic_text(text)
        if not cleaned:
            return []

        raw_parts = re.split(r"[\n\r]+|[.;]|//|\u2022", cleaned)
        points = [part.strip() for part in raw_parts if part and part.strip()]
        return self._compress_lines(points, max_items=max_items, max_words=max_words)

    def _semantic_line_key(self, text: str) -> str:
        normalized = self._normalize_for_noise(text)
        if not normalized:
            return ""

        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        tokens = [token for token in normalized.split() if token and token not in SEMANTIC_STOPWORDS]
        if not tokens:
            return normalized
        return " ".join(tokens[:8])

    def _truncate_words(self, text: str, max_words: int) -> str:
        words = [word for word in text.split() if word]
        if len(words) <= max_words:
            return " ".join(words)
        return " ".join(words[:max_words]).rstrip(".,:;-")

    def _clean_basic_text(self, text: Any) -> str:
        value = str(text or "")
        value = value.replace("\r", " ").replace("\n", " ")
        value = value.replace("//", " ")
        value = value.replace("| |", "|")
        value = re.sub(r"\s+", " ", value)
        value = value.strip(" -|\t")
        return value.strip()

    def _is_noise_line(self, text: str) -> bool:
        normalized = self._normalize_for_noise(text)
        return not normalized or normalized in NOISE_TOKENS

    def _normalize_for_noise(self, text: str) -> str:
        value = (text or "").strip().lower()
        value = value.lstrip("#-*• ").strip()
        value = value.strip(" :.-")
        return value

    def _safe_error(self, error: Exception) -> str:
        return str(error).replace("\n", " ").strip()[:120]

    def _attach_call_details(self, payload: Dict[str, Any], call_details: Dict[str, Any]):
        payload["provider"] = "gemini"
        if call_details.get("model"):
            payload["model_used"] = call_details.get("model")
        if call_details.get("endpoint"):
            payload["endpoint_used"] = call_details.get("endpoint")
        if call_details.get("attempts") is not None:
            payload["attempts"] = call_details.get("attempts")

    def is_test_input(self, resume_input: ResumeInput) -> bool:
        values: List[str] = []
        payload = resume_input.to_prompt_payload()
        targeting = payload.get("targeting")
        if isinstance(targeting, dict) and "tone" in targeting:
            payload = dict(payload)
            payload["targeting"] = dict(targeting)
            payload["targeting"].pop("tone", None)

        def _collect(node: Any):
            if isinstance(node, str):
                cleaned = node.strip().lower()
                if cleaned:
                    values.append(cleaned)
                return
            if isinstance(node, list):
                for item in node:
                    _collect(item)
                return
            if isinstance(node, dict):
                for value in node.values():
                    _collect(value)

        _collect(payload)
        return bool(values) and all(value == "test" for value in values)

    def _parse_response_json(self, text: str) -> Dict[str, Any]:
        content = text.strip()

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content).strip()
            content = re.sub(r"```$", "", content).strip()

        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]

        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Gemini response is not a JSON object")
        return data

    def _repair_json_with_gemini(self, invalid_output: str, schema: Dict[str, Any]) -> str:
        repair_system = (
            "You are a strict JSON repair assistant. "
            "Return valid JSON only with the exact schema."
        )
        repair_user = (
            "Repair the following model output into valid JSON.\n\n"
            "Rules:\n"
            "1) Return JSON only.\n"
            "2) Use this exact schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            "3) Keep all facts faithful to the source text.\n"
            "4) If fields are missing, return empty arrays/strings per schema.\n\n"
            "Source output to repair:\n"
            f"{invalid_output}"
        )
        return self.gemini_client.generate_text(
            system_prompt=repair_system,
            user_prompt=repair_user,
            temperature=0.1,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json",
        )

    def _normalize_list(self, value: Any) -> List[str]:
        if value is None:
            return []

        raw_items: List[Any]
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            raw_items = lines if len(lines) > 1 else [value]
        else:
            raw_items = [value]

        cleaned: List[str] = []
        for item in raw_items:
            text = self._stringify_item(item)
            if text:
                cleaned.append(text)
        return cleaned

    def _stringify_item(self, value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, (int, float, bool)):
            return str(value).strip()

        if isinstance(value, list):
            parts = [self._stringify_item(item) for item in value]
            merged = "; ".join(part for part in parts if part)
            return merged.strip()

        if isinstance(value, dict):
            parts = [self._stringify_item(item) for item in value.values()]
            merged = " | ".join(part for part in parts if part)
            return merged.strip()

        return str(value).strip()

    def _enrich_with_input_data(self, resume_input: ResumeInput, payload: Dict[str, Any]) -> Dict[str, Any]:
        baseline_output = self._fallback_output(resume_input, mode="baseline")
        baseline = {
            "professional_summary": baseline_output.professional_summary,
            "skills": baseline_output.skills,
            "education": baseline_output.education,
            "experience": baseline_output.experience,
            "projects": baseline_output.projects,
            "certifications": baseline_output.certifications,
            "achievements": baseline_output.achievements,
        }

        enriched: Dict[str, Any] = {}
        for key in RESPONSE_KEYS:
            ai_values = payload.get(key, [])
            enriched[key] = list(ai_values) if isinstance(ai_values, list) else self._normalize_list(ai_values)
            if not enriched[key]:
                enriched[key] = list(baseline.get(key, []))

        summary_text = " ".join(enriched["professional_summary"]).strip()
        career_summary = resume_input.career_summary.strip()
        if career_summary and len(summary_text) < 80:
            if career_summary not in enriched["professional_summary"]:
                enriched["professional_summary"].insert(0, career_summary)

        if len(enriched["professional_summary"]) < 2:
            for line in baseline["professional_summary"]:
                if line not in enriched["professional_summary"]:
                    enriched["professional_summary"].append(line)
                if len(enriched["professional_summary"]) >= 2:
                    break

        for key, value in payload.items():
            if key not in RESPONSE_KEYS:
                enriched[key] = value

        return enriched

    def _quality_issues(self, payload: Dict[str, Any], resume_input: ResumeInput) -> List[str]:
        issues: List[str] = []
        filled_sections = sum(1 for key in RESPONSE_KEYS if payload.get(key))
        total_lines = sum(len(payload.get(key, [])) for key in RESPONSE_KEYS)

        if filled_sections < 5 or total_lines < 12:
            issues.append("too_few_sections_or_lines")

        if resume_input.skills and not payload.get("skills"):
            issues.append("missing_skills")
        if resume_input.experiences and not payload.get("experience"):
            issues.append("missing_experience")
        if resume_input.projects and not payload.get("projects"):
            issues.append("missing_projects")

        truncated_summary = any(self._is_truncated_line(line) for line in payload.get("professional_summary", []))
        if truncated_summary:
            issues.append("truncated_summary")

        verbose_lines = any(
            len((line or "").strip()) > 220
            for section in ["experience", "projects"]
            for line in payload.get(section, [])
            if "|" not in (line or "")
        )
        if verbose_lines:
            issues.append("verbose_bullets")

        if self._has_placeholder_content(payload.get("experience", [])) or self._has_placeholder_content(
            payload.get("projects", [])
        ):
            issues.append("placeholder_content")

        if self._has_sparse_headers(payload.get("experience", []), min_parts=4):
            issues.append("sparse_experience_headers")

        if self._has_sparse_headers(payload.get("projects", []), min_parts=3):
            issues.append("sparse_project_headers")

        if self._has_redundant_headers(payload.get("experience", []), min_parts=4):
            issues.append("redundant_experience_headers")

        if self._has_redundant_headers(payload.get("projects", []), min_parts=3):
            issues.append("redundant_project_headers")

        return issues

    def _is_truncated_line(self, line: str) -> bool:
        stripped = (line or "").strip()
        if not stripped:
            return True
        if len(stripped.split()) <= 3:
            return True

        endings = {"to", "and", "with", "for", "of", "in", "on", "by", "at"}
        if stripped.lower().split(" ")[-1].strip(".,:;!?()[]{}") in endings:
            return True
        return False

    def _has_placeholder_content(self, lines: Sequence[str]) -> bool:
        for line in lines:
            for token in str(line or "").split("|"):
                normalized = self._normalize_for_noise(token)
                if normalized in PLACEHOLDER_TOKENS:
                    return True
        return False

    def _has_sparse_headers(self, lines: Sequence[str], min_parts: int) -> bool:
        for line in lines:
            if "|" not in (line or ""):
                continue

            parts = [self._clean_basic_text(part) for part in str(line).split("|")]
            if len(parts) < min_parts:
                continue

            filled = sum(1 for part in parts[:min_parts] if part)
            if filled <= 1:
                return True

        return False

    def _has_redundant_headers(self, lines: Sequence[str], min_parts: int) -> bool:
        for line in lines:
            if "|" not in (line or ""):
                continue

            parts = [self._normalize_for_noise(part) for part in str(line).split("|")]
            if len(parts) < min_parts:
                continue

            first = parts[0]
            second = parts[1] if len(parts) > 1 else ""
            if first and second and first == second:
                return True

        return False

    def _recover_low_quality_output(
        self,
        resume_input: ResumeInput,
        cleaned_payload: Dict[str, Any],
        quality_issues: List[str],
    ) -> Dict[str, Any] | None:
        retry_temperature = max(0.16, self.temperature - 0.12)

        try:
            payload, section_meta = self._generate_sectional_payload(
                cleaned_payload,
                temperature_override=retry_temperature,
            )
            payload = self._enrich_with_input_data(resume_input, payload)
            payload = self._enforce_section_constraints(payload)

            if self._quality_issues(payload, resume_input):
                return None

            payload["mode"] = "ai_sectional_recovered"
            payload["quality_issues"] = list(quality_issues)
            payload["section_calls"] = section_meta.get("section_calls", 0)
            payload["successful_sections"] = section_meta.get("successful_sections", [])

            if section_meta.get("errors"):
                payload["errors"] = list(section_meta.get("errors", []))[:8]

            self._attach_call_details(payload, section_meta.get("last_call_details", {}))
            return payload
        except Exception:
            return None

    def _build_diagnostics_metadata(
        self,
        error_message: str,
        quality_issues: List[str] | None = None,
    ) -> Dict[str, Any]:
        details = self.gemini_client.get_last_call_details()
        metadata: Dict[str, Any] = {
            "provider": "gemini",
            "error": (error_message or "")[:240],
        }

        if details.get("model"):
            metadata["model_used"] = details.get("model")
        if details.get("endpoint"):
            metadata["endpoint_used"] = details.get("endpoint")
        if details.get("attempts") is not None:
            metadata["attempts"] = details.get("attempts")
        if details.get("errors"):
            metadata["errors"] = list(details.get("errors", []))[:3]
        if quality_issues:
            metadata["quality_issues"] = list(quality_issues)

        return metadata

    def _fallback_output(
        self,
        resume_input: ResumeInput,
        mode: str = "fallback",
        metadata: Dict[str, Any] | None = None,
    ) -> ResumeOutput:
        cleaned_payload = self._build_local_cleaning_payload(resume_input)

        payload = {
            "professional_summary": self._fallback_section_from_cleaned("professional_summary", cleaned_payload),
            "skills": self._fallback_section_from_cleaned("skills", cleaned_payload),
            "education": self._fallback_section_from_cleaned("education", cleaned_payload),
            "experience": self._fallback_section_from_cleaned("experience", cleaned_payload),
            "projects": self._fallback_section_from_cleaned("projects", cleaned_payload),
            "certifications": self._fallback_section_from_cleaned("certifications", cleaned_payload),
            "achievements": self._fallback_section_from_cleaned("achievements", cleaned_payload),
        }
        payload = self._enforce_section_constraints(payload)

        raw_response: Dict[str, Any] = {"mode": mode}
        if metadata:
            raw_response.update(metadata)

        return ResumeOutput(
            professional_summary=payload["professional_summary"],
            skills=payload["skills"],
            education=payload["education"],
            experience=payload["experience"],
            projects=payload["projects"],
            certifications=payload["certifications"],
            achievements=payload["achievements"],
            raw_response=raw_response,
        )

    def _dummy_output(self) -> ResumeOutput:
        return ResumeOutput(
            professional_summary=[
                "Entry-level AI/ML engineer focused on building practical, user-facing applications.",
                "Experienced in Python, Streamlit, API integration, and ATS-friendly content generation.",
            ],
            skills=[
                "Python",
                "Streamlit",
                "REST APIs",
                "Prompt Engineering",
                "Data Structures",
                "Problem Solving",
            ],
            education=[
                "B.Tech in Computer Science | Demo University | 2022-2026",
            ],
            experience=[
                "AI Intern | Demo Labs | 2025-Present | Remote",
                "Designed and shipped internal tools for text generation and workflow automation.",
                "Improved output quality through structured prompts and validation checks.",
            ],
            projects=[
                "AI Resume Builder | Python, Streamlit, Gemini API | 2026",
                "Built modular architecture for data collection, AI generation, and PDF export.",
                "Implemented robust fallback handling for model and API compatibility.",
            ],
            certifications=["Google AI Essentials (Demo)"],
            achievements=["Validated end-to-end resume generation using built-in test mode."],
            raw_response={"mode": "dummy"},
        )
