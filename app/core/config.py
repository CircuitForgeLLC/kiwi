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

    # Pre-computed browse counts cache (small SQLite, separate from corpus).
    # Written by the nightly refresh task and by infer_recipe_tags.py.
    # Set BROWSE_COUNTS_PATH to a bind-mounted path if you want the host
    # pipeline to share counts with the container without re-running FTS.
    BROWSE_COUNTS_PATH: Path = Path(
        os.environ.get("BROWSE_COUNTS_PATH", str(DATA_DIR / "browse_counts.db"))
    )

    # Magpie data flywheel — ingest endpoint for anonymized recipe signals
    # Set MAGPIE_INGEST_URL to enable; leave unset (or None) to disable silently.
    MAGPIE_INGEST_URL: str | None = os.environ.get("MAGPIE_INGEST_URL") or None

    # Community feature settings
    COMMUNITY_DB_URL: str | None = os.environ.get("COMMUNITY_DB_URL") or None
    COMMUNITY_PSEUDONYM_SALT: str = os.environ.get(
        "COMMUNITY_PSEUDONYM_SALT", "kiwi-default-salt-change-in-prod"
    )
    COMMUNITY_CLOUD_FEED_URL: str = os.environ.get(
        "COMMUNITY_CLOUD_FEED_URL",
        "https://menagerie.circuitforge.tech/kiwi/api/v1/community/posts",
    )

    # Processing
    MAX_CONCURRENT_JOBS: int = int(os.environ.get("MAX_CONCURRENT_JOBS", "4"))
    USE_GPU: bool = os.environ.get("USE_GPU", "true").lower() in ("1", "true", "yes")
    GPU_MEMORY_LIMIT: int = int(os.environ.get("GPU_MEMORY_LIMIT", "6144"))

    # Quality
    MIN_QUALITY_SCORE: float = float(os.environ.get("MIN_QUALITY_SCORE", "50.0"))

    # CF-core resource coordinator (VRAM lease management — lease broker, not inference)
    COORDINATOR_URL: str = os.environ.get("COORDINATOR_URL", "http://localhost:7700")

    # GPU inference server URL
    # Priority: GPU_SERVER_URL env var → CF_ORCH_URL env var (backward compat)
    #           → https://orch.circuitforge.tech when CF_LICENSE_KEY is present (Paid+)
    # Resolved value is written back to os.environ["CF_ORCH_URL"] at startup so
    # all service-layer callers that read CF_ORCH_URL directly see the right URL.
    GPU_SERVER_URL: str | None = (
        os.environ.get("GPU_SERVER_URL")
        or os.environ.get("CF_ORCH_URL")
        or (
            "https://orch.circuitforge.tech"
            if os.environ.get("CF_LICENSE_KEY")
            else None
        )
    )

    # Hosted cf-orch coordinator — bearer token for managed cloud GPU inference (Paid+)
    # CFOrchClient reads CF_LICENSE_KEY automatically; exposed here for startup validation.
    CF_LICENSE_KEY: str | None = os.environ.get("CF_LICENSE_KEY")

    # E2E test account — analytics logging is suppressed for this user_id so test
    # runs don't pollute session counts.  Set to the Directus UUID of the test user.
    E2E_TEST_USER_ID: str | None = os.environ.get("E2E_TEST_USER_ID") or None

    # ActivityPub federation (optional; disabled by default)
    AP_ENABLED: bool = os.environ.get("AP_ENABLED", "false").lower() in ("1", "true", "yes")
    AP_HOST: str = os.environ.get("AP_HOST", "")          # e.g. kiwi.circuitforge.tech
    CLOUD_DATA_ROOT: Path = Path(os.environ.get("CLOUD_DATA_ROOT", "/devl/kiwi-cloud-data"))
    AP_KEY_PATH: Path = Path(
        os.environ.get("AP_KEY_PATH", str(CLOUD_DATA_ROOT / "ap_keys" / "instance.pem"))
    )
    # Fernet key for Mastodon access token encryption (base64-urlsafe, 32 bytes)
    # Leave unset to skip encryption (dev only)
    AP_TOKEN_ENCRYPTION_KEY: str | None = os.environ.get("AP_TOKEN_ENCRYPTION_KEY") or None

    # Feature flags
    ENABLE_OCR: bool = os.environ.get("ENABLE_OCR", "false").lower() in ("1", "true", "yes")
    # Use OrchestratedScheduler (coordinator-aware, multi-GPU fan-out) instead of
    # LocalScheduler. Defaults to true in CLOUD_MODE; can be set independently
    # for multi-GPU local rigs that don't need full cloud auth.
    USE_ORCH_SCHEDULER: bool | None = (
        None if os.environ.get("USE_ORCH_SCHEDULER") is None
        else os.environ.get("USE_ORCH_SCHEDULER", "").lower() in ("1", "true", "yes")
    )

    # Runtime
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
    CLOUD_MODE: bool = os.environ.get("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
    DEMO_MODE: bool = os.environ.get("DEMO_MODE", "false").lower() in ("1", "true", "yes")

    def ensure_dirs(self) -> None:
        for d in (self.UPLOAD_DIR, self.PROCESSING_DIR, self.ARCHIVE_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()

# Normalise GPU_SERVER_URL into CF_ORCH_URL so every service-layer caller that
# reads os.environ.get("CF_ORCH_URL") sees the resolved value, including the
# Paid+ cloud default injected above.
if settings.GPU_SERVER_URL:
    os.environ["CF_ORCH_URL"] = settings.GPU_SERVER_URL
