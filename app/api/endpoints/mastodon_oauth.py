# app/api/endpoints/mastodon_oauth.py
# MIT License
#
# Mastodon OAuth flow endpoints:
#   POST   /social/mastodon/connect     — Start OAuth (dynamic app registration)
#   GET    /social/mastodon/callback    — OAuth callback, exchange code for token
#   DELETE /social/mastodon/disconnect  — Revoke and remove stored token
#   GET    /social/mastodon/status      — Check connection status

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.cloud_session import CloudUser, get_session
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social/mastodon", tags=["mastodon"])


def _redirect_uri() -> str:
    host = settings.AP_HOST or "localhost:8512"
    return f"https://{host}/api/v1/social/mastodon/callback"


# In-memory pending state: maps state_token → {instance_url, client_id, client_secret, user_id}
# A real deployment would persist this in a short-TTL cache or DB.
_pending: dict[str, dict] = {}


@router.post("/connect")
async def connect_mastodon(body: dict, session: CloudUser = Depends(get_session)):
    """Start the Mastodon OAuth flow.

    Body: {"instance_url": "https://mastodon.social"}
    Returns: {"authorize_url": "..."}
    """
    import secrets

    from app.services.ap.mastodon import build_authorize_url, register_app

    instance_url = (body.get("instance_url") or "").strip().rstrip("/")
    if not instance_url.startswith("https://"):
        raise HTTPException(status_code=422, detail="instance_url must be an https:// URL.")

    redirect_uri = _redirect_uri()
    try:
        app_creds = await asyncio.to_thread(register_app, instance_url, redirect_uri)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not register with Mastodon instance: {exc}"
        ) from exc

    state = secrets.token_urlsafe(24)
    _pending[state] = {
        "instance_url": instance_url,
        "client_id": app_creds["client_id"],
        "client_secret": app_creds["client_secret"],
        "user_id": session.user_id,
    }

    authorize_url = build_authorize_url(
        instance_url=instance_url,
        client_id=app_creds["client_id"],
        redirect_uri=redirect_uri + f"?state={state}",
    )
    return {"authorize_url": authorize_url, "state": state}


@router.get("/callback")
async def mastodon_callback(code: str | None = None, state: str | None = None):
    """OAuth callback. Exchanges auth code for access token and stores it."""
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    pending = _pending.pop(state, None)
    if pending is None:
        raise HTTPException(status_code=400, detail="Unknown or expired OAuth state.")

    from app.services.ap.mastodon import exchange_code, store_token

    redirect_uri = _redirect_uri() + f"?state={state}"
    try:
        access_token = await asyncio.to_thread(
            exchange_code,
            pending["instance_url"],
            pending["client_id"],
            pending["client_secret"],
            code,
            redirect_uri,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}") from exc

    await asyncio.to_thread(
        store_token,
        settings.DB_PATH,
        pending["user_id"],
        pending["instance_url"],
        access_token,
        settings.AP_TOKEN_ENCRYPTION_KEY,
    )

    # Redirect to frontend settings page after successful connect
    return RedirectResponse(url="/#/settings?mastodon=connected", status_code=302)


@router.delete("/disconnect", status_code=204)
async def disconnect_mastodon(session: CloudUser = Depends(get_session)):
    """Remove the stored Mastodon token."""
    from app.services.ap.mastodon import delete_token
    await asyncio.to_thread(delete_token, settings.DB_PATH, session.user_id)


@router.get("/status")
async def mastodon_status(session: CloudUser = Depends(get_session)):
    """Return connection status and instance URL (no token value)."""
    from app.services.ap.mastodon import get_token
    result = await asyncio.to_thread(
        get_token,
        settings.DB_PATH,
        session.user_id,
        settings.AP_TOKEN_ENCRYPTION_KEY,
    )
    if result is None:
        return {"connected": False, "instance_url": None}
    instance_url, _ = result
    return {"connected": True, "instance_url": instance_url}
