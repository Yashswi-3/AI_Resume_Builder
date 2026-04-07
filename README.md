# AI Resume Builder

Production-ready ATS resume platform with:

- FastAPI backend
- Next.js frontend
- Gemini-powered section generation
- Queue-backed async job processing
- SQL persistence for users, jobs, and records
- PDF export

## Current Product Architecture

- `src/api/main.py`: FastAPI application entrypoint
- `src/api/routers/auth.py`: register/login/current-user endpoints
- `src/api/routers/resumes.py`: upload parse, generation jobs, status polling, records, PDF download
- `src/api/worker_tasks.py`: queued resume generation task execution
- `src/api/worker.py`: RQ worker process entrypoint
- `src/services/resume/generator.py`: deterministic + AI rewrite resume pipeline
- `src/services/resume/formatter.py`: template-aware markdown composition
- `src/services/pdf/renderer.py`: template-aware PDF rendering
- `web/`: Next.js frontend app

## Rollout Status

Implemented from the practical rollout plan:

1. FastAPI endpoints with request/response schema validation.
2. Next.js frontend with form, upload parse, preview, and generate flow.
3. Auth, database persistence, queue-backed jobs, and async polling.
4. Diagnostics payload, template switching, and deployment hardening.

## What Is Enforced

- Frontend does not call Gemini directly.
- Public product flow does not depend on Streamlit.
- Deterministic parsing remains the structural source of truth.
- Generation is queue-based for long-running workloads.

## Quick Start (Local)

1. Install Python dependencies:

  `python -m pip install -r requirements.txt`

2. Create env file:

  `cp .env.example .env`

3. Run API:

  `uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000`

4. Run worker (separate terminal):

  `python -m src.api.worker`

5. Run frontend:

  `cd web && npm install && npm run dev`

6. Open:

  `http://localhost:3000`

## Docker Compose Launch

Set `GEMINI_API_KEY` in your shell or `.env`, then run:

`docker compose up --build`

Services:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

## Legacy Streamlit

`app.py` remains available for local/internal debugging, but the production path is API + Next.js.

## Additional Documentation

- `docs/REPO_AUDIT.md`
- `docs/IMPLEMENTATION_PLAN.md`
