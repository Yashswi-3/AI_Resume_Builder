# AI Resume Builder (Streamlit + Gemini)

This project is a complete redevelopment of the resume builder as a modular AI application.

## Highlights

- Clean modular architecture (UI, AI service, formatter, PDF, config).
- Legacy top-level pipeline removed; app now runs only on the modular `src/` architecture.
- Gemini API integration with robust model and endpoint fallback plus retry handling.
- ATS-friendly resume generation using strict JSON schema and repair fallback.
- Streamlit UI for structured data input, preview, and PDF download.
- Target-role and job-description aware generation controls.
- Built-in ATS scoring and job description keyword matching insights.
- Built-in test mode: if all non-empty inputs are `test`, a dummy resume is generated locally.

## Architecture

- `app.py`: Streamlit entrypoint and orchestration.
- `src/config/settings.py`: Environment-driven configuration.
- `src/domain/models.py`: Dataclasses for input/output contracts.
- `src/prompts/resume_prompt.py`: Prompt engineering and JSON schema constraints.
- `src/services/ai/gemini_client.py`: Gemini API client.
- `src/services/resume/generator.py`: AI generation, JSON parsing, fallback and dummy logic.
- `src/services/resume/formatter.py`: Resume markdown composer.
- `src/services/pdf/renderer.py`: ATS-friendly PDF generation.
- `src/ui/forms.py`: Structured input collection and parsing.
- `src/ui/preview.py`: Markdown preview and PDF download UI.
- `src/features/ats/analyzer.py`: ATS score calculator and recommendations.
- `src/features/job_matching/matcher.py`: JD keyword match scoring and gap detection.

## Setup

1. Install dependencies:

   python -m pip install -r requirements.txt

2. Create `.env` from `.env.example` and add your Gemini key:

   GEMINI_API_KEY=your_real_key
  GEMINI_MAX_RETRIES=2

3. Run the application:

   streamlit run app.py

## Input Formats

- Skills: comma-separated or one per line.
- Target role/company and JD fields are optional but recommended for tailored results.
- Education: one line per entry
  - `Degree | Institution | Duration | Location | Details`
- Work Experience: one block per role, separated by blank lines
  - First line: `Role | Company | Duration | Location`
  - Next lines: bullet points
- Projects: one block per project, separated by blank lines
  - First line: `Project Name | Technologies | Year`
  - Next lines: bullet points
- Certifications and Achievements: one per line.

## Run Command

Use exactly this command from project root:

streamlit run app.py
