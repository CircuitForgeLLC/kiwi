"""
FastAPI dependency that provides a Store instance per request.

Local mode: opens a Store at settings.DB_PATH.
Cloud mode: opens a Store at the per-user DB path from the CloudUser session.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
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


def get_db(session: CloudUser = Depends(get_session)) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency — yields the raw sqlite3.Connection for the current user.

    Used by make_corrections_router() from circuitforge-core, which expects a
    dependency that yields a sqlite3.Connection directly.
    """
    store = Store(session.db)
    try:
        yield store.conn
    finally:
        store.close()
