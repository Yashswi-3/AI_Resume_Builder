from __future__ import annotations

import json

from src.domain.ats_models import OptimizedResume, ResumeData, RoleSpec


def build_ats_optimizer_prompt(
    resume_data: ResumeData,
    role_spec: RoleSpec,
    keyword_gaps: list[str],
) -> tuple[str, str]:
    system_prompt = (
        "You are an ATS resume optimizer. "
        "You will receive original resume sections, target role spec, and keyword gaps. "
        "Only rewrite structure and phrasing; do not invent any new experience, skill, project, education, or achievement."
    )

    source_payload = {
        "resume_sections": {
            "summary": resume_data.section_map.get("summary", ""),
            "skills": resume_data.section_map.get("skills", ""),
            "experience": resume_data.section_map.get("experience", ""),
            "projects": resume_data.section_map.get("projects", ""),
            "education": resume_data.section_map.get("education", ""),
        },
        "target_role": {
            "role_id": role_spec.role_id,
            "display_name": role_spec.display_name,
            "required": role_spec.required,
            "preferred": role_spec.preferred,
            "high_impact_keywords": role_spec.high_impact_keywords,
        },
        "keyword_gaps": keyword_gaps,
    }

    output_schema = OptimizedResume().to_dict()

    user_prompt = (
        "Rules you MUST follow:\n"
        "1. Only use information present in the original resume. Do not add any experience, skills, project, education, or achievement that is not in the original.\n"
        "2. Rewrite each section to be more ATS-parseable and keyword-aligned to the role.\n"
        "3. Use exact keywords from the gaps list where they are genuinely present in the context.\n"
        "4. Return structured JSON only. Schema:\n"
        f"{json.dumps(output_schema, indent=2)}\n\n"
        "Input context:\n"
        f"{json.dumps(source_payload, indent=2)}"
    )

    return system_prompt, user_prompt
