from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from src.api.config import get_api_settings
from src.api import models_db  # noqa: F401


@lru_cache
def get_engine():
    settings = get_api_settings()
    connect_args = {}

    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "", 1)
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False

    return create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as session:
        yield session
