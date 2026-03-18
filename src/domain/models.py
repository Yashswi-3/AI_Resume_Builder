from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PersonalInfo:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    location: str = ""


@dataclass
class EducationItem:
    degree: str = ""
    institution: str = ""
    duration: str = ""
    location: str = ""
    details: str = ""


@dataclass
class ExperienceItem:
    role: str = ""
    company: str = ""
    duration: str = ""
    location: str = ""
    bullet_points: List[str] = field(default_factory=list)


@dataclass
class ProjectItem:
    name: str = ""
    technologies: str = ""
    year: str = ""
    bullet_points: List[str] = field(default_factory=list)


@dataclass
class ResumeInput:
    personal_info: PersonalInfo
    career_summary: str = ""
    target_role: str = ""
    target_company: str = ""
    job_description: str = ""
    tone: str = "professional"
    skills: List[str] = field(default_factory=list)
    education: List[EducationItem] = field(default_factory=list)
    experiences: List[ExperienceItem] = field(default_factory=list)
    projects: List[ProjectItem] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)

    def to_prompt_payload(self) -> Dict[str, Any]:
        return {
            "personal_information": {
                "full_name": self.personal_info.full_name,
                "email": self.personal_info.email,
                "phone": self.personal_info.phone,
                "linkedin": self.personal_info.linkedin,
                "github": self.personal_info.github,
                "portfolio": self.personal_info.portfolio,
                "location": self.personal_info.location,
            },
            "career_summary": self.career_summary,
            "targeting": {
                "target_role": self.target_role,
                "target_company": self.target_company,
                "tone": self.tone,
            },
            "job_description": self.job_description,
            "skills": self.skills,
            "education": [
                {
                    "degree": item.degree,
                    "institution": item.institution,
                    "duration": item.duration,
                    "location": item.location,
                    "details": item.details,
                }
                for item in self.education
            ],
            "work_experience": [
                {
                    "role": item.role,
                    "company": item.company,
                    "duration": item.duration,
                    "location": item.location,
                    "bullet_points": item.bullet_points,
                }
                for item in self.experiences
            ],
            "projects": [
                {
                    "name": item.name,
                    "technologies": item.technologies,
                    "year": item.year,
                    "bullet_points": item.bullet_points,
                }
                for item in self.projects
            ],
            "certifications": self.certifications,
            "achievements": self.achievements,
        }


@dataclass
class ResumeOutput:
    professional_summary: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    education: List[str] = field(default_factory=list)
    experience: List[str] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ResumeOutput":
        def _normalize_list(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            text = str(value).strip()
            return [text] if text else []

        return cls(
            professional_summary=_normalize_list(payload.get("professional_summary")),
            skills=_normalize_list(payload.get("skills")),
            education=_normalize_list(payload.get("education")),
            experience=_normalize_list(payload.get("experience")),
            projects=_normalize_list(payload.get("projects")),
            certifications=_normalize_list(payload.get("certifications")),
            achievements=_normalize_list(payload.get("achievements")),
            raw_response=payload,
        )
