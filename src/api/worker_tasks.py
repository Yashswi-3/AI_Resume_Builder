from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlmodel import Session, select

from src.api.config import get_api_settings
from src.api.db import get_engine
from src.api.mappers import from_domain_resume_output, to_domain_resume_input
from src.api.models_db import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PROCESSING,
    ResumeJob,
    ResumeRecord,
    utc_now,
)
from src.api.runtime import get_resume_runtime
from src.api.schemas import ResumeGenerationRequest


def run_resume_job(job_id: str) -> None:
    try:
        parsed_job_id = UUID(str(job_id))
    except ValueError:
        return

    engine = get_engine()
    runtime = get_resume_runtime()
    settings = get_api_settings()

    with Session(engine) as session:
        job = session.exec(select(ResumeJob).where(ResumeJob.id == parsed_job_id)).first()
        if not job:
            return

        job.status = JOB_STATUS_PROCESSING
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)

        try:
            request = ResumeGenerationRequest.model_validate(job.request_payload)
            resume_input = to_domain_resume_input(request.resume_input)

            resume_output = runtime.generator.generate(resume_input)
            markdown = runtime.formatter.to_markdown(
                resume_input,
                resume_output,
                template_key=request.template_key,
            )
            pdf_bytes = runtime.pdf_renderer.render(
                resume_input,
                resume_output,
                template_key=request.template_key,
            )

            ats_result = runtime.ats_analyzer.analyze(markdown, resume_input.job_description)
            jd_result = runtime.jd_matcher.match(markdown, resume_input.job_description)

            storage_root = Path(settings.storage_dir)
            pdf_dir = storage_root / "pdf"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = ""
            if pdf_bytes:
                pdf_file = pdf_dir / f"{job.id}.pdf"
                pdf_file.write_bytes(pdf_bytes)
                pdf_path = str(pdf_file)

            output_payload = from_domain_resume_output(resume_output)
            diagnostics = dict(resume_output.raw_response or {})

            record = ResumeRecord(
                user_id=job.user_id,
                template_key=request.template_key,
                title=resume_input.personal_info.full_name.strip() or "Resume",
                input_payload=request.resume_input.model_dump(),
                output_payload=output_payload.model_dump(),
                markdown_content=markdown,
                diagnostics=diagnostics,
                ats_result=ats_result,
                jd_result=jd_result,
                pdf_path=pdf_path,
            )
            session.add(record)
            session.commit()
            session.refresh(record)

            job.status = JOB_STATUS_COMPLETED
            job.record_id = record.id
            job.pdf_path = pdf_path
            job.result_payload = {
                "resume_output": output_payload.model_dump(),
                "markdown": markdown,
                "ats_result": ats_result,
                "jd_result": jd_result,
                "diagnostics": diagnostics,
            }
            job.error_message = ""
            job.updated_at = utc_now()

            session.add(job)
            session.commit()
        except Exception as error:
            job.status = JOB_STATUS_FAILED
            job.error_message = str(error)
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
