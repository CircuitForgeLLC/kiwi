"""Cloud session resolution for Kiwi FastAPI.

Local mode (CLOUD_MODE unset/false): returns a local CloudUser with no auth
checks, full tier access, and DB path pointing to settings.DB_PATH.

Cloud mode (CLOUD_MODE=true): validates the cf_session JWT injected by Caddy
as X-CF-Session, resolves user_id, auto-provisions a free Heimdall license on
first visit, fetches the tier, and returns a per-user DB path.

FastAPI usage:
    @app.get("/api/v1/inventory/items")
    def list_items(session: CloudUser = Depends(get_session)):
        store = Store(session.db)
        ...
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import jwt as pyjwt
import requests
import yaml
from fastapi import Depends, HTTPException, Request

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

CLOUD_MODE: bool = os.environ.get("CLOUD_MODE", "").lower() in ("1", "true", "yes")
CLOUD_DATA_ROOT: Path = Path(os.environ.get("CLOUD_DATA_ROOT", "/devl/kiwi-cloud-data"))
DIRECTUS_JWT_SECRET: str = os.environ.get("DIRECTUS_JWT_SECRET", "")
HEIMDALL_URL: str = os.environ.get("HEIMDALL_URL", "https://license.circuitforge.tech")
HEIMDALL_ADMIN_TOKEN: str = os.environ.get("HEIMDALL_ADMIN_TOKEN", "")

_LOCAL_KIWI_DB: Path = Path(os.environ.get("KIWI_DB", "data/kiwi.db"))

_TIER_CACHE: dict[str, tuple[str, float]] = {}
_TIER_CACHE_TTL = 300  # 5 minutes

TIERS = ["free", "paid", "premium", "ultra"]


# ── Domain ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CloudUser:
    user_id: str      # Directus UUID, or "local"
    tier: str         # free | paid | premium | ultra | local
    db: Path          # per-user SQLite DB path
    has_byok: bool    # True if a configured LLM backend is present in llm.yaml


# ── JWT validation ─────────────────────────────────────────────────────────────

def _extract_session_token(header_value: str) -> str:
    m = re.search(r'(?:^|;)\s*cf_session=([^;]+)', header_value)
    return m.group(1).strip() if m else header_value.strip()


def validate_session_jwt(token: str) -> str:
    """Validate cf_session JWT and return the Directus user_id."""
    try:
        payload = pyjwt.decode(
            token,
            DIRECTUS_JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["id", "exp"]},
        )
        return payload["id"]
    except Exception as exc:
        log.debug("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Session invalid or expired")


# ── Heimdall integration ──────────────────────────────────────────────────────

def _ensure_provisioned(user_id: str) -> None:
    if not HEIMDALL_ADMIN_TOKEN:
        return
    try:
        requests.post(
            f"{HEIMDALL_URL}/admin/provision",
            json={"directus_user_id": user_id, "product": "kiwi", "tier": "free"},
            headers={"Authorization": f"Bearer {HEIMDALL_ADMIN_TOKEN}"},
            timeout=5,
        )
    except Exception as exc:
        log.warning("Heimdall provision failed for user %s: %s", user_id, exc)


def _fetch_cloud_tier(user_id: str) -> str:
    now = time.monotonic()
    cached = _TIER_CACHE.get(user_id)
    if cached and (now - cached[1]) < _TIER_CACHE_TTL:
        return cached[0]

    if not HEIMDALL_ADMIN_TOKEN:
        return "free"
    try:
        resp = requests.post(
            f"{HEIMDALL_URL}/admin/cloud/resolve",
            json={"directus_user_id": user_id, "product": "kiwi"},
            headers={"Authorization": f"Bearer {HEIMDALL_ADMIN_TOKEN}"},
            timeout=5,
        )
        tier = resp.json().get("tier", "free") if resp.ok else "free"
    except Exception as exc:
        log.warning("Heimdall tier resolve failed for user %s: %s", user_id, exc)
        tier = "free"

    _TIER_CACHE[user_id] = (tier, now)
    return tier


def _user_db_path(user_id: str) -> Path:
    path = CLOUD_DATA_ROOT / user_id / "kiwi.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ── BYOK detection ────────────────────────────────────────────────────────────

_LLM_CONFIG_PATH = Path.home() / ".config" / "circuitforge" / "llm.yaml"


def _detect_byok(config_path: Path = _LLM_CONFIG_PATH) -> bool:
    """Return True if at least one enabled non-vision LLM backend is configured.

    Reads the same llm.yaml that LLMRouter uses. Local (Ollama, vLLM) and
    API-key backends both count — the policy is "user is supplying compute",
    regardless of where that compute lives.
    """
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        return any(
            b.get("enabled", True) and b.get("type") != "vision_service"
            for b in cfg.get("backends", {}).values()
        )
    except Exception:
        return False


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_session(request: Request) -> CloudUser:
    """FastAPI dependency — resolves the current user from the request.

    Local mode: fully-privileged "local" user pointing at local DB.
    Cloud mode: validates X-CF-Session JWT, provisions license, resolves tier.
    """
    has_byok = _detect_byok()

    if not CLOUD_MODE:
        return CloudUser(user_id="local", tier="local", db=_LOCAL_KIWI_DB, has_byok=has_byok)

    raw_header = (
        request.headers.get("x-cf-session", "")
        or request.headers.get("cookie", "")
    )
    if not raw_header:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = _extract_session_token(raw_header)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = validate_session_jwt(token)
    _ensure_provisioned(user_id)
    tier = _fetch_cloud_tier(user_id)
    return CloudUser(user_id=user_id, tier=tier, db=_user_db_path(user_id), has_byok=has_byok)


def require_tier(min_tier: str):
    """Dependency factory — raises 403 if tier is below min_tier."""
    min_idx = TIERS.index(min_tier)

    def _check(session: CloudUser = Depends(get_session)) -> CloudUser:
        if session.tier == "local":
            return session
        try:
            if TIERS.index(session.tier) < min_idx:
                raise HTTPException(
                    status_code=403,
                    detail=f"This feature requires {min_tier} tier or above.",
                )
        except ValueError:
            raise HTTPException(status_code=403, detail="Unknown tier.")
        return session

    return _check
