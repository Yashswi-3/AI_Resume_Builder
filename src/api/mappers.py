from typing import Any, Dict

from src.api.schemas import ResumeInputPayload, ResumeOutputPayload
from src.domain.models import (
    EducationItem,
    ExperienceItem,
    PersonalInfo,
    ProjectItem,
    ResumeInput,
    ResumeOutput,
)


def to_domain_resume_input(payload: ResumeInputPayload) -> ResumeInput:
    return ResumeInput(
        personal_info=PersonalInfo(
            full_name=payload.personal_info.full_name,
            email=payload.personal_info.email,
            phone=payload.personal_info.phone,
            linkedin=payload.personal_info.linkedin,
            github=payload.personal_info.github,
            portfolio=payload.personal_info.portfolio,
            location=payload.personal_info.location,
        ),
        career_summary=payload.career_summary,
        target_role=payload.target_role,
        target_company=payload.target_company,
        job_description=payload.job_description,
        tone=payload.tone,
        skills=list(payload.skills),
        education=[
            EducationItem(
                degree=item.degree,
                institution=item.institution,
                duration=item.duration,
                location=item.location,
                details=item.details,
            )
            for item in payload.education
        ],
        experiences=[
            ExperienceItem(
                role=item.role,
                company=item.company,
                duration=item.duration,
                location=item.location,
                bullet_points=list(item.bullet_points),
            )
            for item in payload.experiences
        ],
        projects=[
            ProjectItem(
                name=item.name,
                technologies=item.technologies,
                year=item.year,
                bullet_points=list(item.bullet_points),
            )
            for item in payload.projects
        ],
        certifications=list(payload.certifications),
        achievements=list(payload.achievements),
    )


def from_domain_resume_output(output: ResumeOutput) -> ResumeOutputPayload:
    return ResumeOutputPayload(
        professional_summary=list(output.professional_summary),
        skills=list(output.skills),
        education=list(output.education),
        experience=list(output.experience),
        projects=list(output.projects),
        certifications=list(output.certifications),
        achievements=list(output.achievements),
        raw_response=dict(output.raw_response or {}),
    )


def output_payload_to_dict(payload: ResumeOutputPayload) -> Dict[str, Any]:
    return payload.model_dump()
