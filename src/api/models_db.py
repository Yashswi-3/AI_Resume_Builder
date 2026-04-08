from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
import uuid

from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlmodel import Field, SQLModel


JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

ATS_JOB_STATUS_QUEUED = "queued"
ATS_JOB_STATUS_PROCESSING = "processing"
ATS_JOB_STATUS_COMPLETED = "completed"
ATS_JOB_STATUS_FAILED = "failed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(sa_column=Column(String(255), unique=True, index=True, nullable=False))
    hashed_password: str = Field(sa_column=Column(String(255), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ResumeJob(SQLModel, table=True):
    __tablename__ = "resume_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, nullable=False)
    status: str = Field(default=JOB_STATUS_QUEUED, sa_column=Column(String(32), nullable=False, index=True))
    template_key: str = Field(default="classic", sa_column=Column(String(32), nullable=False))
    request_payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    result_payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    record_id: uuid.UUID | None = Field(default=None, foreign_key="resume_records.id", index=True)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    pdf_path: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class ResumeRecord(SQLModel, table=True):
    __tablename__ = "resume_records"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, nullable=False)
    template_key: str = Field(default="classic", sa_column=Column(String(32), nullable=False))
    title: str = Field(default="Resume", sa_column=Column(String(255), nullable=False))
    input_payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    output_payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    markdown_content: str = Field(default="", sa_column=Column(Text, nullable=False))
    diagnostics: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    ats_result: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    jd_result: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    pdf_path: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class ATSOptimizeJob(SQLModel, table=True):
    __tablename__ = "ats_optimize_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    status: str = Field(default=ATS_JOB_STATUS_QUEUED, sa_column=Column(String(32), nullable=False, index=True))
    request_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    pdf_path: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
