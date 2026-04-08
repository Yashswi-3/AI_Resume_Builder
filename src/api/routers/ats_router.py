from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from src.api.config import get_api_settings
from src.api.db import get_session
from src.api.models_db import (
    ATS_JOB_STATUS_COMPLETED,
    ATS_JOB_STATUS_QUEUED,
    ATSOptimizeJob,
    utc_now,
)
from src.api.queueing import enqueue_ats_optimize_job
from src.api.runtime import get_resume_runtime
from src.api.schemas import (
    ATSAnalyzeResponse,
    ATSOptimizedResumePayload,
    ATSOptimizeQueuedResponse,
    ATSOptimizeStatusResponse,
)
from src.domain.ats_models import OptimizedResume
from src.domain.models import PersonalInfo, ResumeInput, ResumeOutput
from src.features.ats.jd_loader import get_role, get_roles_map, parse_jd_text
from src.services.resume.parsing.parser import parse_resume


router = APIRouter(prefix="/ats", tags=["ats"])


def _is_supported_upload(upload: UploadFile) -> bool:
    mime_type = (upload.content_type or "").lower()
    file_name = (upload.filename or "").lower()
    return (
        "pdf" in mime_type
        or "word" in mime_type
        or "docx" in mime_type
        or file_name.endswith(".pdf")
        or file_name.endswith(".docx")
    )


def _resolve_role(role_id: str, jd_text: str):
    role_id = (role_id or "").strip()
    jd_text = (jd_text or "").strip()
    if bool(role_id) == bool(jd_text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of role_id or jd_text.",
        )

    if role_id:
        try:
            return get_role(role_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return parse_jd_text(jd_text)


@router.post("/analyze", response_model=ATSAnalyzeResponse)
async def analyze_resume(
    file: UploadFile = File(...),
    role_id: str = Form(default=""),
    jd_text: str = Form(default=""),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    if not _is_supported_upload(file):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF and DOCX are supported.")

    mime_type = file.content_type or ("application/pdf" if (file.filename or "").lower().endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    role_spec = _resolve_role(role_id=role_id, jd_text=jd_text)
    resume_data = parse_resume(file_bytes=content, mime_type=mime_type)
    result = get_resume_runtime().ats_analyzer.analyze_v2(resume_data=resume_data, role_spec=role_spec)
    return ATSAnalyzeResponse(**result.to_dict())


@router.post("/optimize", response_model=ATSOptimizeQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def optimize_resume(
    file: UploadFile = File(...),
    score_result: str = Form(...),
    session: Session = Depends(get_session),
    role_id: str = Form(default=""),
    jd_text: str = Form(default=""),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if not _is_supported_upload(file):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF and DOCX are supported.")

    mime_type = file.content_type or (
        "application/pdf"
        if (file.filename or "").lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    try:
        parsed_score = json.loads(score_result)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="score_result must be valid JSON.") from error

    _resolve_role(role_id=role_id, jd_text=jd_text)

    job = ATSOptimizeJob(
        status=ATS_JOB_STATUS_QUEUED,
        request_payload={
            "resume_bytes": list(content),
            "mime_type": mime_type,
            "role_id": (role_id or "").strip(),
            "jd_text": (jd_text or "").strip(),
            "score_result": parsed_score,
        },
        result_payload={},
        error_message="",
        updated_at=utc_now(),
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    backend = enqueue_ats_optimize_job(str(job.id))
    return ATSOptimizeQueuedResponse(job_id=job.id, status=ATS_JOB_STATUS_QUEUED, queue_backend=backend)


@router.get("/optimize/{job_id}/status", response_model=ATSOptimizeStatusResponse)
def optimize_status(job_id: UUID, session: Annotated[Session, Depends(get_session)]):
    job = session.exec(select(ATSOptimizeJob).where(ATSOptimizeJob.id == job_id)).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    result = None
    if job.status == ATS_JOB_STATUS_COMPLETED:
        optimized_payload = (job.result_payload or {}).get("optimized_resume", {})
        result = ATSOptimizedResumePayload(**optimized_payload)

    return ATSOptimizeStatusResponse(
        job_id=job.id,
        status=job.status,
        error_message=job.error_message,
        result=result,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/roles")
def list_roles() -> dict[str, Any]:
    payload = get_roles_map()
    return payload.get("roles", {})


@router.get("/export/{job_id}")
def export_pdf(job_id: UUID, session: Annotated[Session, Depends(get_session)]):
    settings = get_api_settings()
    runtime = get_resume_runtime()

    job = session.exec(select(ATSOptimizeJob).where(ATSOptimizeJob.id == job_id)).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != ATS_JOB_STATUS_COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Optimize job is not completed yet")

    optimized = (job.result_payload or {}).get("optimized_resume") or {}
    optimized_resume = OptimizedResume(**optimized)

    resume_output = ResumeOutput(
        professional_summary=[line.strip() for line in optimized_resume.summary.splitlines() if line.strip()],
        skills=[item.strip() for item in optimized_resume.skills.replace("\n", ",").split(",") if item.strip()],
        education=[line.strip() for line in optimized_resume.education.splitlines() if line.strip()],
        experience=[line.strip() for line in optimized_resume.experience.splitlines() if line.strip()],
        projects=[line.strip() for line in optimized_resume.projects.splitlines() if line.strip()],
    )

    resume_input = ResumeInput(personal_info=PersonalInfo(full_name="Optimized Resume"))
    pdf_bytes = runtime.pdf_renderer.render(resume_input=resume_input, resume_output=resume_output)
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate PDF")

    storage_root = Path(settings.storage_dir)
    pdf_dir = storage_root / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"ats-{job.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    job.pdf_path = str(pdf_path)
    job.updated_at = utc_now()
    session.add(job)
    session.commit()

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"ats-optimized-{job.id}.pdf",
    )
