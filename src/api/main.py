from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import get_api_settings
from src.api.db import init_db
from src.api.routers.auth import router as auth_router
from src.api.routers.resumes import router as resumes_router


def create_app() -> FastAPI:
    settings = get_api_settings()

    app = FastAPI(
        title="AI Resume Builder API",
        version="1.0.0",
        description="Production API for ATS-focused resume generation.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(resumes_router, prefix=settings.api_prefix)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
