# Repository Audit

## Current Assets Reused

- Core generation engine: `src/services/resume/generator.py`
- AI provider integration: `src/services/ai/gemini_client.py`
- ATS scoring: `src/features/ats/analyzer.py`
- JD matching: `src/features/job_matching/matcher.py`
- PDF renderer: `src/services/pdf/renderer.py`
- Domain contracts: `src/domain/models.py`

## Prior Constraints Identified

- UI and parsing logic were intertwined in Streamlit form code.
- Generation relied on synchronous request flow with in-memory session state.
- No persistent user/auth model.
- No async queue-backed job model for long-running generation.
- No production API boundary for external clients.

## Production Gaps Closed in This Refactor

- Added API service boundary (`FastAPI`) under `src/api/`.
- Added persistence with relational DB models (`SQLModel`).
- Added authentication (register/login/JWT).
- Added queued job processing with Redis/RQ + local thread fallback.
- Added async polling endpoints and resume records storage.
- Added frontend app (`Next.js`) for non-Streamlit product UX.
- Added deployment artifacts (`Dockerfile.api`, `Dockerfile.worker`, `docker-compose.yml`).

## Remaining Optional Enhancements

- Social login and email verification.
- Billing and usage metering.
- S3-compatible object storage for PDFs.
- End-to-end tests for API + frontend integration.
- Admin dashboard and moderation/rate controls.
