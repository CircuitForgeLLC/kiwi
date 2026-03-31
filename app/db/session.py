"""
FastAPI dependency that provides a Store instance per request.

Local mode: opens a Store at settings.DB_PATH.
Cloud mode: opens a Store at the per-user DB path from the CloudUser session.
"""
from __future__ import annotations

from typing import Generator

from fastapi import Depends

from app.cloud_session import CloudUser, get_session
from app.db.store import Store


def get_store(session: CloudUser = Depends(get_session)) -> Generator[Store, None, None]:
    """FastAPI dependency — yields a Store for the current user, closes on completion."""
    store = Store(session.db)
    try:
        yield store
    finally:
        store.close()
