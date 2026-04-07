from dataclasses import dataclass
from functools import lru_cache
import os


def _load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def _read_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _read_list_env(*names: str, default: str = "") -> tuple[str, ...]:
    raw = _read_env(*names, default=default)
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(values)


_load_env_file()


@dataclass(frozen=True)
class ApiSettings:
    api_prefix: str
    environment: str
    host: str
    port: int
    cors_origins: tuple[str, ...]
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiry_minutes: int
    database_url: str
    redis_url: str
    queue_name: str
    storage_dir: str


@lru_cache
def get_api_settings() -> ApiSettings:
    try:
        port = int(_read_env("API_PORT", default="8000"))
    except ValueError:
        port = 8000

    try:
        jwt_expiry_minutes = int(_read_env("JWT_EXPIRY_MINUTES", default="1440"))
    except ValueError:
        jwt_expiry_minutes = 1440

    default_origins = "http://localhost:3000,http://127.0.0.1:3000"
    return ApiSettings(
        api_prefix=_read_env("API_PREFIX", default="/api/v1"),
        environment=_read_env("APP_ENV", default="development"),
        host=_read_env("API_HOST", default="0.0.0.0"),
        port=port,
        cors_origins=_read_list_env("CORS_ORIGINS", default=default_origins),
        jwt_secret=_read_env("JWT_SECRET", default="change-me-in-production"),
        jwt_algorithm=_read_env("JWT_ALGORITHM", default="HS256"),
        jwt_expiry_minutes=max(5, jwt_expiry_minutes),
        database_url=_read_env("DATABASE_URL", default="sqlite:///./data/app.db"),
        redis_url=_read_env("REDIS_URL", default="redis://localhost:6379/0"),
        queue_name=_read_env("QUEUE_NAME", default="resume_jobs"),
        storage_dir=_read_env("STORAGE_DIR", default="./data/storage"),
    )
