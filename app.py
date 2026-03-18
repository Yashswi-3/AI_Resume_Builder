import hashlib

import streamlit as st

from src.config.settings import get_settings
from src.features.ats.analyzer import ATSAnalyzer
from src.features.job_matching.matcher import JobDescriptionMatcher
from src.services.ai.gemini_client import GeminiClient
from src.services.pdf.renderer import ResumePdfRenderer
from src.services.resume.formatter import ResumeFormatter
from src.services.resume.generator import ResumeGenerator
from src.ui.forms import render_resume_form
from src.ui.preview import render_resume_preview

SESSION_KEYS = [
    "resume_input",
    "resume_output",
    "resume_markdown",
    "resume_pdf",
    "resume_hash",
    "ats_result",
    "jd_result",
]


@st.cache_resource
def build_resume_generator(
    api_key: str,
    model: str,
    timeout_seconds: int,
    max_retries: int,
    temperature: float,
    max_tokens: int,
) -> ResumeGenerator:
    client = GeminiClient(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    return ResumeGenerator(
        gemini_client=client,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )


@st.cache_resource
def build_resume_formatter() -> ResumeFormatter:
    return ResumeFormatter()


@st.cache_resource
def build_pdf_renderer() -> ResumePdfRenderer:
    return ResumePdfRenderer()


def initialize_session_state():
    for key in SESSION_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None


def clear_session_state():
    for key in SESSION_KEYS:
        st.session_state[key] = None


def resolve_api_key(settings) -> str:
    key_from_secrets = ""
    try:
        key_from_secrets = st.secrets.get("gemini_api_key", "")
    except Exception:
        key_from_secrets = ""
    return settings.gemini_api_key or key_from_secrets


def resolve_model(settings) -> str:
    model_from_secrets = ""
    try:
        model_from_secrets = st.secrets.get("gemini_model", "")
    except Exception:
        model_from_secrets = ""
    return settings.gemini_model or model_from_secrets


def render_sidebar():
    st.sidebar.header("System Overview")
    st.sidebar.markdown(
        "- UI Layer: Streamlit form + preview\n"
        "- AI Layer: Gemini prompt + generation service\n"
        "- Formatting Layer: Markdown resume composer\n"
        "- Export Layer: PDF renderer\n"
        "- Config Layer: .env settings"
    )

    st.sidebar.subheader("Optimization Engine")
    st.sidebar.caption("ATS scoring and JD matching run automatically after generation.")

    ats_result = st.session_state.get("ats_result")
    jd_result = st.session_state.get("jd_result")

    if ats_result and ats_result.get("score") is not None:
        st.sidebar.metric("ATS Score", f"{ats_result['score']}/100")
    if jd_result and jd_result.get("match_score") is not None:
        st.sidebar.metric("JD Match", f"{jd_result['match_score']}/100")

    resume_output = st.session_state.get("resume_output")
    raw = (resume_output.raw_response if resume_output else {}) or {}
    if raw.get("mode"):
        st.sidebar.caption(
            "Generation mode: "
            + str(raw.get("mode"))
            + (f" | model: {raw.get('model_used')}" if raw.get("model_used") else "")
        )


def run_optimization_analyses(markdown: str, job_description: str) -> tuple[dict, dict]:
    ats_result = ATSAnalyzer().analyze(markdown, job_description)
    jd_result = JobDescriptionMatcher().match(markdown, job_description)
    return ats_result, jd_result


def render_optimization_insights():
    ats_result = st.session_state.get("ats_result")
    jd_result = st.session_state.get("jd_result")

    if not ats_result and not jd_result:
        return

    st.divider()
    st.subheader("Optimization Insights")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ATS Score")
        if ats_result and ats_result.get("score") is not None:
            st.metric("Overall", f"{ats_result['score']}/100")
            for item in ats_result.get("recommendations", [])[:4]:
                st.write(f"- {item}")
        else:
            st.info((ats_result or {}).get("message", "ATS analysis is not available yet."))

    with col2:
        st.markdown("### JD Match")
        if jd_result and jd_result.get("match_score") is not None:
            st.metric("Match", f"{jd_result['match_score']}/100")
            matched = jd_result.get("matched_keywords", [])
            missing = jd_result.get("missing_keywords", [])
            if matched:
                st.caption("Matched keywords: " + ", ".join(matched[:8]))
            if missing:
                st.caption("Missing keywords: " + ", ".join(missing[:8]))
            for item in jd_result.get("recommendations", [])[:3]:
                st.write(f"- {item}")
        else:
            st.info((jd_result or {}).get("message", "Add a job description to enable matching."))


def render_generation_diagnostics():
    resume_output = st.session_state.get("resume_output")
    raw = (resume_output.raw_response if resume_output else {}) or {}
    if not raw:
        return

    st.divider()
    st.subheader("Generation Diagnostics")
    st.caption(
        "Use this panel to confirm whether Gemini generated the resume directly or fallback logic was used."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Mode", str(raw.get("mode", "unknown")))
    with col2:
        st.metric("Provider", str(raw.get("provider", "local")))
    with col3:
        st.metric("Model", str(raw.get("model_used", "n/a")))

    if raw.get("endpoint_used"):
        st.caption("Endpoint: " + str(raw.get("endpoint_used")))

    if raw.get("quality_issues"):
        st.caption("Quality checks triggered: " + ", ".join(raw.get("quality_issues", [])))

    if raw.get("error"):
        st.warning("Generation error context: " + str(raw.get("error")))

    if raw.get("errors"):
        with st.expander("Detailed model errors"):
            for item in raw.get("errors", [])[:3]:
                st.write(f"- {item}")


def main():
    settings = get_settings()

    st.set_page_config(
        page_title=settings.app_title,
        page_icon=settings.app_icon,
        layout="centered",
        initial_sidebar_state="expanded",
    )

    initialize_session_state()
    render_sidebar()

    st.title(settings.app_title)
    st.caption(settings.app_subtitle)

    api_key = resolve_api_key(settings)
    selected_model = resolve_model(settings)

    generator = build_resume_generator(
        api_key=api_key,
        model=selected_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
        temperature=settings.generation_temperature,
        max_tokens=settings.generation_max_tokens,
    )
    formatter = build_resume_formatter()
    pdf_renderer = build_pdf_renderer()

    submitted, resume_input = render_resume_form()

    if submitted and resume_input is not None:
        with st.spinner("Generating ATS-friendly resume..."):
            resume_output = generator.generate(resume_input)
            markdown = formatter.to_markdown(resume_input, resume_output)
            pdf_bytes = pdf_renderer.render(resume_input, resume_output)
            ats_result, jd_result = run_optimization_analyses(markdown, resume_input.job_description)

        st.session_state.resume_input = resume_input
        st.session_state.resume_output = resume_output
        st.session_state.resume_markdown = markdown
        st.session_state.resume_pdf = pdf_bytes
        st.session_state.resume_hash = hashlib.md5(markdown.encode()).hexdigest()
        st.session_state.ats_result = ats_result
        st.session_state.jd_result = jd_result

        mode = (resume_output.raw_response or {}).get("mode")
        if mode == "dummy":
            st.info("Test mode detected: generated a local dummy resume because all inputs were 'test'.")
        elif mode == "fallback":
            st.warning("AI response parsing failed once; showing a reliable fallback resume output.")
        elif mode == "fallback_incomplete_ai":
            st.warning("AI output was incomplete, so a complete resume was rebuilt from your provided input data.")
        elif mode == "ai_sectional":
            st.info("Generated using the new ATS cleaning + section-specialized AI pipeline.")
        elif mode == "ai_sectional_partial":
            st.warning(
                "Sectional AI generation partially failed for one or more sections; "
                "affected sections were rebuilt from cleaned input data."
            )
        elif mode == "ai_sectional_recovered":
            st.info("Sectional AI output was recovered after quality checks and retry.")
        elif mode == "ai_repaired":
            st.info("AI response needed JSON repair once; normalized result is shown.")
        elif mode == "ai_recovered":
            st.info("AI initially returned low-quality content, then successfully recovered with a second Gemini pass.")

    if st.session_state.resume_markdown:
        render_resume_preview(st.session_state.resume_markdown, st.session_state.resume_pdf)
        render_generation_diagnostics()
        render_optimization_insights()

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Regenerate from Current Inputs") and st.session_state.resume_input is not None:
                with st.spinner("Regenerating resume..."):
                    resume_output = generator.generate(st.session_state.resume_input)
                    markdown = formatter.to_markdown(st.session_state.resume_input, resume_output)
                    pdf_bytes = pdf_renderer.render(st.session_state.resume_input, resume_output)
                    ats_result, jd_result = run_optimization_analyses(
                        markdown,
                        st.session_state.resume_input.job_description,
                    )

                st.session_state.resume_output = resume_output
                st.session_state.resume_markdown = markdown
                st.session_state.resume_pdf = pdf_bytes
                st.session_state.resume_hash = hashlib.md5(markdown.encode()).hexdigest()
                st.session_state.ats_result = ats_result
                st.session_state.jd_result = jd_result
                st.rerun()

        with col2:
            if st.button("Start Over"):
                clear_session_state()
                st.rerun()


if __name__ == "__main__":
    main()
