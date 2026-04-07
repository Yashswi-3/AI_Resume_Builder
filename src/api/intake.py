from __future__ import annotations

from typing import Dict

from src.api.schemas import ResumeInputPayload
from src.ui.forms import (
    _build_prefill_from_resume_text,
    _parse_education,
    _parse_experience,
    _parse_projects,
)
from src.utils.text_utils import split_csv_or_lines, split_lines


def parse_resume_text_to_prefill(raw_text: str) -> Dict[str, str]:
    return _build_prefill_from_resume_text(raw_text)


def prefill_to_resume_input_payload(prefill: Dict[str, str]) -> ResumeInputPayload:
    skills = split_csv_or_lines(prefill.get("skills_raw", ""))
    education_items = _parse_education(prefill.get("education_raw", ""))
    experience_items = _parse_experience(prefill.get("experience_raw", ""))
    project_items = _parse_projects(prefill.get("projects_raw", ""))

    certifications = [line.strip() for line in split_lines(prefill.get("certifications_raw", "")) if line.strip()]
    achievements = [line.strip() for line in split_lines(prefill.get("achievements_raw", "")) if line.strip()]

    return ResumeInputPayload(
        personal_info={
            "full_name": prefill.get("full_name", ""),
            "email": prefill.get("email", ""),
            "phone": prefill.get("phone", ""),
            "linkedin": prefill.get("linkedin", ""),
            "github": prefill.get("github", ""),
            "portfolio": prefill.get("portfolio", ""),
            "location": prefill.get("location", ""),
        },
        career_summary=prefill.get("career_summary", ""),
        skills=skills,
        education=[
            {
                "degree": item.degree,
                "institution": item.institution,
                "duration": item.duration,
                "location": item.location,
                "details": item.details,
            }
            for item in education_items
        ],
        experiences=[
            {
                "role": item.role,
                "company": item.company,
                "duration": item.duration,
                "location": item.location,
                "bullet_points": list(item.bullet_points),
            }
            for item in experience_items
        ],
        projects=[
            {
                "name": item.name,
                "technologies": item.technologies,
                "year": item.year,
                "bullet_points": list(item.bullet_points),
            }
            for item in project_items
        ],
        certifications=certifications,
        achievements=achievements,
    )
