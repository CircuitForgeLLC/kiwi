"""User settings endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.cloud_session import CloudUser, get_session
from app.db.session import get_store
from app.db.store import Store

router = APIRouter()

_ALLOWED_KEYS = frozenset({"cooking_equipment"})


class SettingBody(BaseModel):
    value: str


@router.get("/{key}")
async def get_setting(
    key: str,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> dict:
    """Return the stored value for a settings key."""
    if key not in _ALLOWED_KEYS:
        raise HTTPException(status_code=422, detail=f"Unknown settings key: '{key}'.")
    value = store.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return {"key": key, "value": value}


@router.put("/{key}")
async def set_setting(
    key: str,
    body: SettingBody,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> dict:
    """Upsert a settings key-value pair."""
    if key not in _ALLOWED_KEYS:
        raise HTTPException(status_code=422, detail=f"Unknown settings key: '{key}'.")
    store.set_setting(key, body.value)
    return {"key": key, "value": body.value}
