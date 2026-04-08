from dataclasses import dataclass
from functools import lru_cache

from src.config.settings import get_settings
from src.features.ats.analyzer import ATSAnalyzer
from src.features.job_matching.matcher import JobDescriptionMatcher
from src.services.ai.gemini_client import GeminiClient
from src.services.pdf.renderer import ResumePdfRenderer
from src.services.resume_optimizer import ResumeOptimizer
from src.services.resume.formatter import ResumeFormatter
from src.services.resume.generator import ResumeGenerator


@dataclass(frozen=True)
class ResumeRuntime:
    generator: ResumeGenerator
    formatter: ResumeFormatter
    pdf_renderer: ResumePdfRenderer
    ats_analyzer: ATSAnalyzer
    jd_matcher: JobDescriptionMatcher
    resume_optimizer: ResumeOptimizer


@lru_cache
def get_resume_runtime() -> ResumeRuntime:
    settings = get_settings()
    client = GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
    )

    return ResumeRuntime(
        generator=ResumeGenerator(
            gemini_client=client,
            temperature=settings.generation_temperature,
            max_output_tokens=settings.generation_max_tokens,
        ),
        formatter=ResumeFormatter(),
        pdf_renderer=ResumePdfRenderer(),
        ats_analyzer=ATSAnalyzer(),
        jd_matcher=JobDescriptionMatcher(),
        resume_optimizer=ResumeOptimizer(gemini_client=client),
    )
