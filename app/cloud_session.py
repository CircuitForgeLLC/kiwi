"""Cloud session resolution for Kiwi FastAPI.

Delegates JWT validation, Heimdall provisioning, tier resolution, and guest
session management to circuitforge_core.CloudSessionFactory. Kiwi-specific
CloudUser (per-user DB path, household data, BYOK flag) and DB helpers are
kept here.

FastAPI usage:
    @app.get("/api/v1/inventory/items")
    def list_items(session: CloudUser = Depends(get_session)):
        store = Store(session.db)
        ...
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from circuitforge_core.cloud_session import CloudSessionFactory as _CoreFactory
from circuitforge_core.cloud_session import detect_byok
from fastapi import Depends, HTTPException, Request, Response

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

CLOUD_MODE: bool = os.environ.get("CLOUD_MODE", "").lower() in ("1", "true", "yes")
CLOUD_DATA_ROOT: Path = Path(os.environ.get("CLOUD_DATA_ROOT", "/devl/kiwi-cloud-data"))

_LOCAL_KIWI_DB: Path = Path(os.environ.get("KIWI_DB", "data/kiwi.db"))

TIERS = ["free", "paid", "premium", "ultra"]

_core = _CoreFactory(product="kiwi", byok_detector=detect_byok)


def _auth_label(user_id: str) -> str:
    """Classify a user_id into a short tag for structured log lines. No PII emitted."""
    if user_id in ("local", "local-dev"):
        return "local"
    if user_id.startswith("anon-"):
        return "anon"
    return "authed"


# ── Domain ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CloudUser:
    user_id: str      # Directus UUID, or "local"
    tier: str         # free | paid | premium | ultra | local
    db: Path          # per-user SQLite DB path
    has_byok: bool    # True if a configured LLM backend is present in llm.yaml
    household_id: str | None = None
    is_household_owner: bool = False
    license_key: str | None = None  # key_display for lifetime/founders keys; None for subscription/free


# ── DB path helpers ───────────────────────────────────────────────────────────

def _user_db_path(user_id: str, household_id: str | None = None) -> Path:
    if household_id:
        path = CLOUD_DATA_ROOT / f"household_{household_id}" / "kiwi.db"
    else:
        path = CLOUD_DATA_ROOT / user_id / "kiwi.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _anon_guest_db_path(guest_id: str) -> Path:
    """Per-session DB for unauthenticated guest visitors.

    Each anonymous visitor gets an isolated SQLite DB keyed by their guest UUID
    cookie, so shopping lists and affiliate interactions never bleed across sessions.
    """
    path = CLOUD_DATA_ROOT / f"anon-{guest_id}" / "kiwi.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_session(request: Request, response: Response) -> CloudUser:
    """FastAPI dependency — resolves the current user from the request.

    Delegates auth/tier resolution to cf-core CloudSessionFactory, then maps
    the result to Kiwi's CloudUser with per-user DB path and household data.

    Local mode: fully-privileged "local" user pointing at local DB.
    Cloud mode: validates X-CF-Session JWT, provisions license, resolves tier.
    Dev bypass: CLOUD_AUTH_BYPASS_IPS match returns a "local-dev" session.
    Anonymous: per-session UUID cookie (cf_guest_id) isolates each guest's data.
    """
    core_user = _core.resolve(request, response)
    uid, tier, has_byok = core_user.user_id, core_user.tier, core_user.has_byok

    if not CLOUD_MODE or uid in ("local", "local-dev"):
        # local-dev gets a writable path under CLOUD_DATA_ROOT; local uses KIWI_DB
        db = _user_db_path(uid) if uid == "local-dev" else _LOCAL_KIWI_DB
        return CloudUser(user_id=uid, tier=tier, db=db, has_byok=has_byok)

    if uid.startswith("anon-"):
        guest_id = uid[len("anon-"):]
        return CloudUser(
            user_id=uid, tier=tier,
            db=_anon_guest_db_path(guest_id),
            has_byok=has_byok,
        )

    household_id = core_user.meta.get("household_id")
    is_owner = core_user.meta.get("is_household_owner", False)
    license_key = core_user.meta.get("license_key")
    log.debug("Resolved %s session uid=%s tier=%s household=%s", _auth_label(uid), uid[:8], tier, household_id)
    return CloudUser(
        user_id=uid, tier=tier,
        db=_user_db_path(uid, household_id=household_id),
        has_byok=has_byok,
        household_id=household_id,
        is_household_owner=is_owner,
        license_key=license_key,
    )


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
