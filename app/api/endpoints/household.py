"""Household management endpoints — shared pantry for Premium users."""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends, HTTPException

from app.cloud_session import CloudUser, CLOUD_DATA_ROOT, HEIMDALL_URL, HEIMDALL_ADMIN_TOKEN, get_session
from app.db.store import Store
from app.models.schemas.household import (
    HouseholdAcceptRequest,
    HouseholdAcceptResponse,
    HouseholdCreateResponse,
    HouseholdInviteResponse,
    HouseholdMember,
    HouseholdRemoveMemberRequest,
    HouseholdStatusResponse,
    MessageResponse,
)

log = logging.getLogger(__name__)
router = APIRouter()

_INVITE_TTL_DAYS = 7
_KIWI_BASE_URL = os.environ.get("KIWI_BASE_URL", "https://menagerie.circuitforge.tech/kiwi")


def _require_premium(session: CloudUser = Depends(get_session)) -> CloudUser:
    if session.tier not in ("premium", "ultra", "local"):
        raise HTTPException(status_code=403, detail="Household features require Premium tier.")
    return session


def _require_household_owner(session: CloudUser = Depends(_require_premium)) -> CloudUser:
    if not session.is_household_owner or not session.household_id:
        raise HTTPException(status_code=403, detail="Only the household owner can perform this action.")
    return session


def _household_store(household_id: str) -> Store:
    """Open the household DB directly (used during invite acceptance)."""
    from pathlib import Path
    db_path = CLOUD_DATA_ROOT / f"household_{household_id}" / "kiwi.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return Store(db_path)


def _heimdall_post(path: str, body: dict) -> dict:
    """Call Heimdall admin API. Returns response dict or raises HTTPException."""
    if not HEIMDALL_ADMIN_TOKEN:
        log.warning("HEIMDALL_ADMIN_TOKEN not set — household Heimdall call skipped")
        return {}
    try:
        resp = requests.post(
            f"{HEIMDALL_URL}{path}",
            json=body,
            headers={"Authorization": f"Bearer {HEIMDALL_ADMIN_TOKEN}"},
            timeout=10,
        )
        if not resp.ok:
            raise HTTPException(status_code=502, detail=f"Heimdall error: {resp.text}")
        return resp.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Heimdall unreachable: {exc}")


@router.post("/create", response_model=HouseholdCreateResponse)
async def create_household(session: CloudUser = Depends(_require_premium)):
    """Create a new household. The calling user becomes owner."""
    if session.household_id:
        raise HTTPException(status_code=409, detail="You are already in a household.")
    data = _heimdall_post("/admin/household/create", {"owner_user_id": session.user_id})
    household_id = data.get("household_id", "local-household")
    return HouseholdCreateResponse(
        household_id=household_id,
        message="Household created. Share an invite link to add members.",
    )


@router.get("/status", response_model=HouseholdStatusResponse)
async def household_status(session: CloudUser = Depends(_require_premium)):
    """Return current user's household membership status."""
    if not session.household_id:
        return HouseholdStatusResponse(in_household=False)

    members: list[HouseholdMember] = []
    if HEIMDALL_ADMIN_TOKEN:
        try:
            resp = requests.get(
                f"{HEIMDALL_URL}/admin/household/{session.household_id}",
                headers={"Authorization": f"Bearer {HEIMDALL_ADMIN_TOKEN}"},
                timeout=5,
            )
            if resp.ok:
                raw = resp.json()
                for m in raw.get("members", []):
                    members.append(HouseholdMember(
                        user_id=m["user_id"],
                        joined_at=m.get("joined_at", ""),
                        is_owner=m["user_id"] == raw.get("owner_user_id"),
                    ))
        except Exception as exc:
            log.warning("Could not fetch household members: %s", exc)

    return HouseholdStatusResponse(
        in_household=True,
        household_id=session.household_id,
        is_owner=session.is_household_owner,
        members=members,
    )


@router.post("/invite", response_model=HouseholdInviteResponse)
async def create_invite(session: CloudUser = Depends(_require_household_owner)):
    """Generate a one-time invite token valid for 7 days."""
    store = Store(session.db)
    token = secrets.token_hex(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=_INVITE_TTL_DAYS)).isoformat()
    store.conn.execute(
        """INSERT INTO household_invites (token, household_id, created_by, expires_at)
           VALUES (?, ?, ?, ?)""",
        (token, session.household_id, session.user_id, expires_at),
    )
    store.conn.commit()
    invite_url = f"{_KIWI_BASE_URL}/#/join?household_id={session.household_id}&token={token}"
    return HouseholdInviteResponse(token=token, invite_url=invite_url, expires_at=expires_at)


@router.post("/accept", response_model=HouseholdAcceptResponse)
async def accept_invite(
    body: HouseholdAcceptRequest,
    session: CloudUser = Depends(get_session),
):
    """Accept a household invite. Opens the household DB directly to validate the token."""
    if session.household_id:
        raise HTTPException(status_code=409, detail="You are already in a household.")

    hh_store = _household_store(body.household_id)
    now = datetime.now(timezone.utc).isoformat()
    row = hh_store.conn.execute(
        """SELECT token, expires_at, used_at FROM household_invites
           WHERE token = ? AND household_id = ?""",
        (body.token, body.household_id),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if row["used_at"] is not None:
        raise HTTPException(status_code=410, detail="Invite already used.")
    if row["expires_at"] < now:
        raise HTTPException(status_code=410, detail="Invite has expired.")

    hh_store.conn.execute(
        "UPDATE household_invites SET used_at = ?, used_by = ? WHERE token = ?",
        (now, session.user_id, body.token),
    )
    hh_store.conn.commit()

    _heimdall_post("/admin/household/add-member", {
        "household_id": body.household_id,
        "user_id": session.user_id,
    })

    return HouseholdAcceptResponse(
        message="You have joined the household. Reload the app to switch to the shared pantry.",
        household_id=body.household_id,
    )


@router.post("/leave", response_model=MessageResponse)
async def leave_household(session: CloudUser = Depends(_require_premium)) -> MessageResponse:
    """Leave the current household (non-owners only)."""
    if not session.household_id:
        raise HTTPException(status_code=400, detail="You are not in a household.")
    if session.is_household_owner:
        raise HTTPException(status_code=400, detail="The household owner cannot leave. Delete the household instead.")
    _heimdall_post("/admin/household/remove-member", {
        "household_id": session.household_id,
        "user_id": session.user_id,
    })
    return MessageResponse(message="You have left the household. Reload the app to return to your personal pantry.")


@router.post("/remove-member", response_model=MessageResponse)
async def remove_member(
    body: HouseholdRemoveMemberRequest,
    session: CloudUser = Depends(_require_household_owner),
) -> MessageResponse:
    """Remove a member from the household (owner only)."""
    if body.user_id == session.user_id:
        raise HTTPException(status_code=400, detail="Use /leave to remove yourself.")
    _heimdall_post("/admin/household/remove-member", {
        "household_id": session.household_id,
        "user_id": body.user_id,
    })
    return MessageResponse(message=f"Member {body.user_id} removed from household.")
