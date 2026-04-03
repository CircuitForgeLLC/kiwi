"""
Kiwi application config.
Uses circuitforge-core for env loading; no pydantic-settings dependency.
"""
from __future__ import annotations

import os
from pathlib import Path

from circuitforge_core.config.settings import load_env

# Load .env from the repo root (two levels up from app/core/)
_ROOT = Path(__file__).resolve().parents[2]
load_env(_ROOT / ".env")


class Settings:
    # API
    API_PREFIX: str = os.environ.get("API_PREFIX", "/api/v1")
    PROJECT_NAME: str = "Kiwi — Pantry Intelligence"

    # CORS
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "").split(",")
        if o.strip()
    ]

    # File storage
    DATA_DIR: Path = Path(os.environ.get("DATA_DIR", str(_ROOT / "data")))
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    PROCESSING_DIR: Path = DATA_DIR / "processing"
    ARCHIVE_DIR: Path = DATA_DIR / "archive"

    # Database
    DB_PATH: Path = Path(os.environ.get("DB_PATH", str(DATA_DIR / "kiwi.db")))

    # Processing
    MAX_CONCURRENT_JOBS: int = int(os.environ.get("MAX_CONCURRENT_JOBS", "4"))
    USE_GPU: bool = os.environ.get("USE_GPU", "true").lower() in ("1", "true", "yes")
    GPU_MEMORY_LIMIT: int = int(os.environ.get("GPU_MEMORY_LIMIT", "6144"))

    # Quality
    MIN_QUALITY_SCORE: float = float(os.environ.get("MIN_QUALITY_SCORE", "50.0"))

    # CF-core resource coordinator (VRAM lease management)
    COORDINATOR_URL: str = os.environ.get("COORDINATOR_URL", "http://localhost:7700")

    # Hosted cf-orch coordinator — bearer token for managed cloud GPU inference (Paid+)
    # CFOrchClient reads CF_LICENSE_KEY automatically; exposed here for startup validation.
    CF_LICENSE_KEY: str | None = os.environ.get("CF_LICENSE_KEY")

    # Feature flags
    ENABLE_OCR: bool = os.environ.get("ENABLE_OCR", "false").lower() in ("1", "true", "yes")

    # Runtime
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
    CLOUD_MODE: bool = os.environ.get("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
    DEMO_MODE: bool = os.environ.get("DEMO_MODE", "false").lower() in ("1", "true", "yes")

    def ensure_dirs(self) -> None:
        for d in (self.UPLOAD_DIR, self.PROCESSING_DIR, self.ARCHIVE_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
