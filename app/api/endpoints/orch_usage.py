"""Proxy endpoint: exposes cf-orch call budget to the Kiwi frontend.

Only lifetime/founders users have a license_key — subscription and free
users receive null (no budget UI shown).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.cloud_session import CloudUser, get_session
from app.services.heimdall_orch import get_orch_usage

router = APIRouter()


@router.get("")
async def orch_usage_endpoint(
    session: CloudUser = Depends(get_session),
) -> dict | None:
    """Return the current period's orch usage for the authenticated user.

    Returns null if the user has no lifetime/founders license key (i.e. they
    are on a subscription or free plan — no budget cap applies to them).
    """
    if session.license_key is None:
        return None
    return get_orch_usage(session.license_key, "kiwi")
