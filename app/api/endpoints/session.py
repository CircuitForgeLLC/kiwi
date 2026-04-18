"""Session bootstrap endpoint — called once per app load by the frontend.

Logs auth= + tier= for log-based analytics without client-side tracking.
See Circuit-Forge/kiwi#86.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.cloud_session import CloudUser, _auth_label, get_session

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/bootstrap")
def session_bootstrap(session: CloudUser = Depends(get_session)) -> dict:
    """Record auth type and tier for log-based analytics.

    Expected log output:
        INFO:app.api.endpoints.session: session auth=authed tier=paid
        INFO:app.api.endpoints.session: session auth=anon tier=free
    """
    log.info("session auth=%s tier=%s", _auth_label(session.user_id), session.tier)
    return {
        "auth": _auth_label(session.user_id),
        "tier": session.tier,
        "has_byok": session.has_byok,
    }
