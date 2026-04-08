from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


ResumeTemplateKey = Literal["classic", "compact", "modern"]
JobStatus = Literal["queued", "processing", "completed", "failed"]


class PersonalInfoPayload(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    location: str = ""


class EducationItemPayload(BaseModel):
    degree: str = ""
    institution: str = ""
    duration: str = ""
    location: str = ""
    details: str = ""


class ExperienceItemPayload(BaseModel):
    role: str = ""
    company: str = ""
    duration: str = ""
    location: str = ""
    bullet_points: List[str] = Field(default_factory=list)


class ProjectItemPayload(BaseModel):
    name: str = ""
    technologies: str = ""
    year: str = ""
    bullet_points: List[str] = Field(default_factory=list)


class ResumeInputPayload(BaseModel):
    personal_info: PersonalInfoPayload
    career_summary: str = ""
    target_role: str = ""
    target_company: str = ""
    job_description: str = ""
    tone: str = "professional"
    skills: List[str] = Field(default_factory=list)
    education: List[EducationItemPayload] = Field(default_factory=list)
    experiences: List[ExperienceItemPayload] = Field(default_factory=list)
    projects: List[ProjectItemPayload] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class ResumeOutputPayload(BaseModel):
    professional_summary: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class ATSResultPayload(BaseModel):
    score: int | None = None
    recommendations: List[str] = Field(default_factory=list)
    message: str = ""


class JDResultPayload(BaseModel):
    match_score: int | None = None
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    message: str = ""


class ParseUploadResponse(BaseModel):
    prefill: Dict[str, str] = Field(default_factory=dict)
    resume_input: ResumeInputPayload
    extracted_text_preview: str = ""


class ResumeGenerationRequest(BaseModel):
    resume_input: ResumeInputPayload
    template_key: ResumeTemplateKey = "classic"


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ResumeJobQueuedResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    queue_backend: str


class ResumeJobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    template_key: ResumeTemplateKey
    created_at: datetime
    updated_at: datetime
    error_message: str = ""
    result_payload: Dict[str, Any] = Field(default_factory=dict)
    record_id: UUID | None = None
    pdf_download_url: str = ""


class ResumeRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_key: str
    title: str
    markdown_content: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    ats_result: Dict[str, Any] = Field(default_factory=dict)
    jd_result: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ATSAnalyzeResponse(BaseModel):
    score: int
    verdict: Literal["reject", "borderline", "strong"]
    breakdown: Dict[str, int] = Field(default_factory=dict)
    keyword_gaps: List[str] = Field(default_factory=list)
    weak_sections: Dict[str, str] = Field(default_factory=dict)
    recruiter_adjustments: Dict[str, int] = Field(default_factory=dict)
    reason: str = ""


class ATSOptimizeQueuedResponse(BaseModel):
    job_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    queue_backend: str


class ATSOptimizedResumePayload(BaseModel):
    skills: str = ""
    experience: str = ""
    projects: str = ""
    education: str = ""
    summary: str = ""


class ATSOptimizeStatusResponse(BaseModel):
    job_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    error_message: str = ""
    result: ATSOptimizedResumePayload | None = None
    created_at: datetime
    updated_at: datetime
