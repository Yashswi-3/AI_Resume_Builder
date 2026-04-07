from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from src.api.db import get_session
from src.api.intake import parse_resume_text_to_prefill, prefill_to_resume_input_payload
from src.api.models_db import ResumeJob, ResumeRecord, User
from src.api.queueing import enqueue_resume_job
from src.api.schemas import (
    ParseUploadResponse,
    ResumeGenerationRequest,
    ResumeJobQueuedResponse,
    ResumeJobStatusResponse,
    ResumeRecordResponse,
)
from src.api.security import get_current_user
from src.services.resume.parsing.parser import extract_text_from_docx, extract_text_from_pdf


router = APIRouter(prefix="/resumes", tags=["resumes"])


def _assert_supported_extension(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX uploads are supported.",
        )
    return suffix


@router.post("/parse-upload", response_model=ParseUploadResponse)
async def parse_upload(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    del current_user

    suffix = _assert_supported_extension(file.filename or "")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(content)
            tmp_path = handle.name

        if suffix == ".pdf":
            raw_text = extract_text_from_pdf(tmp_path)
        else:
            raw_text = extract_text_from_docx(tmp_path)

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse uploaded file: {error}",
        ) from error
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()

    prefill = parse_resume_text_to_prefill(raw_text)
    resume_input = prefill_to_resume_input_payload(prefill)

    return ParseUploadResponse(
        prefill=prefill,
        resume_input=resume_input,
        extracted_text_preview=raw_text[:1400],
    )


@router.post("/jobs", response_model=ResumeJobQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
def create_generation_job(
    payload: ResumeGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    job = ResumeJob(
        user_id=current_user.id,
        status="queued",
        template_key=payload.template_key,
        request_payload=payload.model_dump(),
        result_payload={},
    )

    session.add(job)
    session.commit()
    session.refresh(job)

    backend = enqueue_resume_job(str(job.id))
    return ResumeJobQueuedResponse(job_id=job.id, status="queued", queue_backend=backend)


@router.get("/jobs/{job_id}", response_model=ResumeJobStatusResponse)
def get_generation_job(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    job = session.exec(
        select(ResumeJob).where(ResumeJob.id == job_id).where(ResumeJob.user_id == current_user.id)
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    pdf_download_url = ""
    if job.record_id and job.pdf_path:
        pdf_download_url = f"/api/v1/resumes/records/{job.record_id}/pdf"

    return ResumeJobStatusResponse(
        job_id=job.id,
        status=job.status,
        template_key=job.template_key,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
        result_payload=job.result_payload,
        record_id=job.record_id,
        pdf_download_url=pdf_download_url,
    )


@router.get("/records", response_model=list[ResumeRecordResponse])
def list_records(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 20,
):
    safe_limit = min(max(limit, 1), 100)
    records = session.exec(
        select(ResumeRecord)
        .where(ResumeRecord.user_id == current_user.id)
        .order_by(ResumeRecord.created_at.desc())
        .limit(safe_limit)
    ).all()
    return [ResumeRecordResponse.model_validate(record) for record in records]


@router.get("/records/{record_id}", response_model=ResumeRecordResponse)
def get_record(
    record_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    record = session.exec(
        select(ResumeRecord).where(ResumeRecord.id == record_id).where(ResumeRecord.user_id == current_user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return ResumeRecordResponse.model_validate(record)


@router.get("/records/{record_id}/pdf")
def get_record_pdf(
    record_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    record = session.exec(
        select(ResumeRecord).where(ResumeRecord.id == record_id).where(ResumeRecord.user_id == current_user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    pdf_path = Path(record.pdf_path)
    if not record.pdf_path or not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"resume-{record.id}.pdf",
    )
