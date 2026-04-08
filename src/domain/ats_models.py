from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExperienceEntry:
    title: str = ""
    company: str = ""
    duration: str = ""
    location: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class ProjectEntry:
    name: str = ""
    technologies: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ResumeData:
    skills: list[str] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    raw_text: str = ""
    section_map: dict[str, str] = field(default_factory=dict)


@dataclass
class RoleSpec:
    role_id: str
    display_name: str
    category: str
    required: list[str] = field(default_factory=list)
    preferred: list[str] = field(default_factory=list)
    seniority_keywords: dict[str, list[str]] = field(default_factory=dict)
    synonyms: dict[str, list[str]] = field(default_factory=dict)
    experience_threshold_years: int = 0
    section_weights: dict[str, float] = field(default_factory=dict)
    high_impact_keywords: list[str] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    skills_match: float = 0.0
    experience_relevance: float = 0.0
    project_alignment: float = 0.0
    format_quality: float = 0.0

    def to_percentage_dict(self) -> dict[str, int]:
        return {
            "skills": round(self.skills_match * 100),
            "experience": round(self.experience_relevance * 100),
            "projects": round(self.project_alignment * 100),
            "format": round(self.format_quality * 100),
        }


@dataclass
class ScoreResult:
    score: int
    verdict: str
    breakdown: ScoreBreakdown
    keyword_gaps: list[str] = field(default_factory=list)
    weak_sections: dict[str, str] = field(default_factory=dict)
    recruiter_adjustments: dict[str, int] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["breakdown"] = self.breakdown.to_percentage_dict()
        return payload


@dataclass
class OptimizedResume:
    skills: str = ""
    experience: str = ""
    projects: str = ""
    education: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "skills": self.skills,
            "experience": self.experience,
            "projects": self.projects,
            "education": self.education,
            "summary": self.summary,
        }
