import json
from typing import Any, Dict

from src.domain.models import ResumeInput


RESPONSE_SCHEMA = {
    "professional_summary": ["..."],
    "skills": ["..."],
    "education": ["..."],
    "experience": ["..."],
    "projects": ["..."],
    "certifications": ["..."],
    "achievements": ["..."],
}


CLEANING_OUTPUT_SCHEMA = {
    "professional_summary_seed": "...",
    "skills": ["..."],
    "education": ["Degree | Institution | Duration | Location | Details"],
    "experience": [
        {
            "role": "...",
            "company": "...",
            "duration": "...",
            "location": "...",
            "highlights": ["..."],
        }
    ],
    "projects": [
        {
            "name": "...",
            "technologies": "...",
            "year": "...",
            "highlights": ["..."],
        }
    ],
    "certifications": ["..."],
    "achievements": ["..."],
    "job_description_keywords": ["..."],
}


SECTION_OUTPUT_SCHEMAS = {
    "professional_summary": {"items": ["impact line 1", "impact line 2"]},
    "skills": {"items": ["skill_one", "skill_two", "skill_three"]},
    "education": {"items": ["Degree | Institution | Duration | Location | Details"]},
    "experience": {
        "items": [
            {
                "role": "...",
                "company": "...",
                "duration": "...",
                "location": "...",
                "bullets": ["...", "...", "..."],
            }
        ]
    },
    "projects": {
        "items": [
            {
                "name": "...",
                "technologies": "...",
                "year": "...",
                "bullets": ["...", "...", "..."],
            }
        ]
    },
    "certifications": {"items": ["..."]},
    "achievements": {"items": ["..."]},
}


def _target_context_from_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    targeting = payload.get("targeting", {})
    role = str(targeting.get("target_role", "")).strip()
    company = str(targeting.get("target_company", "")).strip()
    tone = str(targeting.get("tone", "professional")).strip() or "professional"
    job_description = str(payload.get("job_description", "")).strip()
    return {
        "role": role,
        "company": company,
        "tone": tone,
        "job_description": job_description,
    }


def _target_line(role: str, company: str) -> str:
    target_line_parts = [part for part in [role, company] if part]
    if len(target_line_parts) == 2:
        return " at ".join(target_line_parts)
    if target_line_parts:
        return target_line_parts[0]
    return "General software role"


def build_ats_cleaning_prompt(
    resume_input: ResumeInput,
    local_clean_payload: Dict[str, Any],
) -> tuple[str, str]:
    raw_payload = resume_input.to_prompt_payload()
    context = _target_context_from_payload(raw_payload)

    system_prompt = (
        "You are an ATS resume data normalization engine. "
        "Your job is to clean noisy user input into structured, high-signal facts for resume generation. "
        "Do not invent companies, roles, dates, metrics, or achievements. "
        "Extract structure from messy text and compress verbose paragraphs into concise factual highlights."
    )

    user_prompt = (
        "Normalize and clean the resume input into ATS-ready structured JSON.\n\n"
        "Return rules:\n"
        "1) Return valid JSON only. No markdown, no prose.\n"
        "2) Use this exact schema:\n"
        f"{json.dumps(CLEANING_OUTPUT_SCHEMA, indent=2)}\n"
        "3) Remove section labels, repeated lines, placeholders, and noise lines before structuring.\n"
        "4) Fix obvious spelling/formatting mistakes conservatively; do not alter factual meaning.\n"
        "5) If experience/project content is massive, summarize aggressively and keep only high-impact facts.\n"
        "6) Keep max 4 experience items and max 4 project items, ordered by relevance and recency.\n"
        "7) Experience headers must map cleanly: role, company, duration, location. Avoid duplicated values across fields.\n"
        "8) Project headers must map cleanly: name, technologies, year. Avoid generic names like Project/App/System.\n"
        "9) Keep max 3 highlights per experience/project and each highlight <= 22 words.\n"
        "10) Use concrete, ATS-friendly bullets with action verbs and measurable context when available.\n"
        "11) Move extracurricular or event-only lines to achievements unless they are true professional roles.\n"
        "12) Extract JD keywords into job_description_keywords for ATS alignment.\n"
        "13) Never use placeholders like Organization, Company, Core Technologies, or N/A.\n"
        "14) If a field cannot be inferred confidently, leave it empty instead of guessing.\n\n"
        f"Target context: {_target_line(context['role'], context['company'])}\n"
        f"Requested tone: {context['tone']}\n"
        "Job description context (may be empty):\n"
        f"{context['job_description'] or 'N/A'}\n\n"
        "Raw user payload JSON:\n"
        f"{json.dumps(raw_payload, indent=2)}\n\n"
        "Local pre-cleaned fallback JSON:\n"
        f"{json.dumps(local_clean_payload, indent=2)}"
    )

    return system_prompt, user_prompt


def build_section_generation_prompt(
    section_name: str,
    cleaned_payload: Dict[str, Any],
) -> tuple[str, str]:
    section_schema = SECTION_OUTPUT_SCHEMAS.get(section_name)
    if section_schema is None:
        raise ValueError(f"Unsupported section name: {section_name}")

    base_context = {
        "target_role": cleaned_payload.get("target_role", ""),
        "target_company": cleaned_payload.get("target_company", ""),
        "tone": cleaned_payload.get("tone", "professional"),
        "job_description": cleaned_payload.get("job_description", ""),
        "job_description_keywords": cleaned_payload.get("job_description_keywords", []),
    }

    if section_name == "professional_summary":
        section_source = {
            "professional_summary_seed": cleaned_payload.get("professional_summary_seed", ""),
            "skills": cleaned_payload.get("skills", []),
            "experience": cleaned_payload.get("experience", []),
        }
        section_rules = (
            "Write exactly 2 concise lines. "
            "Each line should be ATS-friendly and role-aligned. "
            "No generic fluff."
        )
    elif section_name == "skills":
        section_source = {
            "skills": cleaned_payload.get("skills", []),
            "experience": cleaned_payload.get("experience", []),
            "projects": cleaned_payload.get("projects", []),
        }
        section_rules = (
            "Return 8-14 high-signal ATS skills. "
            "Prefer specific technical terms over generic traits."
        )
    elif section_name == "education":
        section_source = {"education": cleaned_payload.get("education", [])}
        section_rules = (
            "Return concise education lines in this format: "
            "Degree | Institution | Duration | Location | Details. "
            "Keep degree and institution distinct, and keep CGPA/details in Details."
        )
    elif section_name == "experience":
        section_source = {"experience": cleaned_payload.get("experience", [])}
        section_rules = (
            "For each experience item, return role/company/duration/location and 1-3 bullets. "
            "Return at most 4 items and sort by recency/relevance. "
            "Do not repeat the same text for both role and company. "
            "Drop noisy lines that are not true professional work history. "
            "Hard constraint: each experience block must be <= 4 lines total "
            "(header + max 3 bullets). "
            "If source content is massive, summarize to top impact points only. "
            "Do not repeat near-identical bullets across items."
        )
    elif section_name == "projects":
        section_source = {"projects": cleaned_payload.get("projects", [])}
        section_rules = (
            "For each project, return name/technologies/year and 1-3 bullets. "
            "Return at most 4 projects and prioritize strongest technical impact projects. "
            "Project name must be specific and not a generic placeholder. "
            "Hard constraint: each project block must be <= 4 lines total "
            "(header + max 3 bullets). "
            "If source content is massive, summarize to top impact points only. "
            "Do not repeat near-identical bullets across projects."
        )
    elif section_name == "certifications":
        section_source = {"certifications": cleaned_payload.get("certifications", [])}
        section_rules = "Return concise certification lines only."
    else:
        section_source = {"achievements": cleaned_payload.get("achievements", [])}
        section_rules = (
            "Return concise achievement bullets with outcomes or recognition context when available."
        )

    system_prompt = (
        "You are an ATS-focused resume writer specialized in one section at a time. "
        "Be factual, concise, and keyword-aware. "
        "Do not invent facts or placeholders."
    )

    user_prompt = (
        f"Generate only the '{section_name}' section.\n\n"
        "Output rules:\n"
        "1) Return valid JSON only.\n"
        "2) Use this exact schema:\n"
        f"{json.dumps(section_schema, indent=2)}\n"
        "3) Keep wording concise and ATS-friendly.\n"
        "4) Start bullets with strong action verbs where possible.\n"
        "5) Preserve user facts; do not fabricate details.\n"
        "6) Never output placeholders like Organization, Company, Core Technologies, TBD, or N/A.\n"
        "7) Never output duplicate or near-duplicate bullet lines.\n"
        f"8) {section_rules}\n\n"
        "Targeting and JD context:\n"
        f"{json.dumps(base_context, indent=2)}\n\n"
        "Section source data:\n"
        f"{json.dumps(section_source, indent=2)}"
    )

    return system_prompt, user_prompt
