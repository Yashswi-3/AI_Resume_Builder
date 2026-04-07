# Implementation Plan and Delivery Map

## Phase 1: API + Validation

Status: Implemented

- FastAPI app with health and versioned routes.
- Structured request/response schemas.
- Resume upload parsing endpoint with deterministic mapping.
- Resume generation endpoint redesigned as queued job creation.

## Phase 2: Frontend Product UX

Status: Implemented

- Next.js TypeScript frontend with Tailwind styling.
- Auth forms (register/login), upload parse action, full form editing.
- Async generate flow with status polling.
- Preview and diagnostics rendering with PDF download.
- Template switch (`classic`, `compact`, `modern`) in UI and backend.

## Phase 3: Auth + DB + Queue

Status: Implemented

- SQL-backed models for users, jobs, and resume records.
- JWT-based auth and protected endpoints.
- Queue-backed processing (`Redis + RQ`) with worker process.
- Job lifecycle states (`queued`, `processing`, `completed`, `failed`).

## Phase 4: Diagnostics + Templates + Hardening

Status: Implemented (base)

- Generation diagnostics stored and returned in job payload.
- ATS and JD optimization results persisted per record.
- Template-aware markdown/PDF output ordering.
- Dockerized services for API, worker, database, cache, and frontend.

## What Not To Do (Enforced)

- Do not call Gemini directly from frontend.
- Do not use Streamlit as the public web product surface.
- Do not let AI and parser co-own structure mutation.
- Do not deploy generation as a purely synchronous monolith without queueing.

## Operational Follow-up

- Set strong production `JWT_SECRET`.
- Use managed Postgres and Redis in cloud environments.
- Configure object storage for PDFs at scale.
- Add API rate limiting and abuse protections at gateway level.
- Add CI for lint/test/build on both Python and frontend stacks.
