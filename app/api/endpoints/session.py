"""Session bootstrap endpoint — called once per app load by the frontend.

Logs auth= + tier= for log-based analytics without client-side tracking.
See Circuit-Forge/kiwi#86.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.cloud_session import CloudUser, _auth_label, get_session
from app.core.config import settings

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/bootstrap")
def session_bootstrap(session: CloudUser = Depends(get_session)) -> dict:
    """Record auth type and tier for log-based analytics.

    Expected log output:
        INFO:app.api.endpoints.session: session auth=authed tier=paid
        INFO:app.api.endpoints.session: session auth=anon tier=free

    E2E test sessions (E2E_TEST_USER_ID) are logged at DEBUG so they don't
    pollute analytics counts while still being visible when DEBUG=true.
    """
    is_test = bool(settings.E2E_TEST_USER_ID and session.user_id == settings.E2E_TEST_USER_ID)
    logger = log.debug if is_test else log.info
    logger("session auth=%s tier=%s%s", _auth_label(session.user_id), session.tier, " e2e=true" if is_test else "")
    return {
        "auth": _auth_label(session.user_id),
        "tier": session.tier,
        "has_byok": session.has_byok,
    }
