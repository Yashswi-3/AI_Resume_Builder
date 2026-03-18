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


_load_env_file()


def _read_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


@dataclass(frozen=True)
class Settings:
    app_title: str
    app_subtitle: str
    app_icon: str
    gemini_api_key: str
    gemini_model: str
    gemini_timeout_seconds: int
    gemini_max_retries: int
    generation_temperature: float
    generation_max_tokens: int


@lru_cache
def get_settings() -> Settings:
    timeout_raw = _read_env("GEMINI_TIMEOUT_SECONDS", default="60")
    retries_raw = _read_env("GEMINI_MAX_RETRIES", default="2")
    temperature_raw = _read_env("GENERATION_TEMPERATURE", default="0.35")
    tokens_raw = _read_env("GENERATION_MAX_TOKENS", default="1400")

    try:
        timeout = int(timeout_raw)
    except ValueError:
        timeout = 60

    try:
        retries = int(retries_raw)
    except ValueError:
        retries = 2

    try:
        temperature = float(temperature_raw)
    except ValueError:
        temperature = 0.35

    try:
        max_tokens = int(tokens_raw)
    except ValueError:
        max_tokens = 1400

    return Settings(
        app_title=_read_env("APP_TITLE", default="AI Resume Builder"),
        app_subtitle=_read_env(
            "APP_SUBTITLE",
            default="Build ATS-friendly resumes with Gemini AI and export to PDF.",
        ),
        app_icon=_read_env("APP_ICON", default=":memo:"),
        gemini_api_key=_read_env("GEMINI_API_KEY", "gemini_api_key", default=""),
        gemini_model=_read_env("GEMINI_MODEL", "gemini_model", default=""),
        gemini_timeout_seconds=timeout,
        gemini_max_retries=max(0, retries),
        generation_temperature=temperature,
        generation_max_tokens=max_tokens,
    )
