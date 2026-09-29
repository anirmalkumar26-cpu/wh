from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(WORKSPACE_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("WH_DATABASE_URL", f"sqlite:///{(WORKSPACE_ROOT / 'backend' / 'data' / 'wh.db').as_posix()}")
    jwt_secret: str = os.getenv("WH_JWT_SECRET", "development-only-change-me")
    access_token_minutes: int = int(os.getenv("WH_ACCESS_TOKEN_MINUTES", "20"))
    refresh_token_days: int = int(os.getenv("WH_REFRESH_TOKEN_DAYS", "14"))
    ai_provider: str = os.getenv("WH_AI_PROVIDER", "auto").lower()
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("WH_GEMINI_MODEL", "gemini-2.5-flash")
    ai_timeout_seconds: int = int(os.getenv("WH_AI_TIMEOUT_SECONDS", "30"))
    environment: str = os.getenv("WH_ENV", "development").lower()
    video_engine_path: Path = Path(os.getenv("WH_VIDEO_ENGINE_PATH", str(WORKSPACE_ROOT / "a")))
    video_jobs_path: Path = Path(os.getenv("WH_VIDEO_JOBS_PATH", str(WORKSPACE_ROOT / "backend" / "data" / "video_jobs")))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("WH_CORS_ORIGINS", "").split(",") if origin.strip()
    )


settings = Settings()
