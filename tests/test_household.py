"""Tests for household session resolution in cloud_session.py."""
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CLOUD_MODE", "false")

import app.cloud_session as cs
from app.cloud_session import (
    CloudUser,
    _user_db_path,
)


def test_clouduser_has_household_fields():
    u = CloudUser(
        user_id="u1", tier="premium", db=Path("/tmp/u1.db"),
        has_byok=False, household_id="hh-1", is_household_owner=True
    )
    assert u.household_id == "hh-1"
    assert u.is_household_owner is True


def test_clouduser_household_defaults_none():
    u = CloudUser(user_id="u1", tier="free", db=Path("/tmp/u1.db"), has_byok=False)
    assert u.household_id is None
    assert u.is_household_owner is False


def test_user_db_path_personal(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "CLOUD_DATA_ROOT", tmp_path)
    result = cs._user_db_path("abc123")
    assert result == tmp_path / "abc123" / "kiwi.db"


def test_user_db_path_household(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "CLOUD_DATA_ROOT", tmp_path)
    result = cs._user_db_path("abc123", household_id="hh-xyz")
    assert result == tmp_path / "household_hh-xyz" / "kiwi.db"


# ── Integration tests (require router) ─────────────────────────────────

def test_create_household_requires_premium():
    """Non-premium users cannot create a household."""
    from app.main import app
    from app.cloud_session import get_session
    import tempfile, pathlib

    db = pathlib.Path(tempfile.mktemp(suffix=".db"))
    from app.db.store import Store
    Store(str(db))

    free_user = CloudUser(user_id="u1", tier="free", db=db, has_byok=False)
    app.dependency_overrides[get_session] = lambda: free_user
    client = TestClient(app)
    resp = client.post("/api/v1/household/create")
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_invite_generates_token():
    """Invite endpoint returns a token and URL for owner in a household."""
    from app.main import app
    from app.cloud_session import get_session
    import tempfile, pathlib

    db = pathlib.Path(tempfile.mktemp(suffix=".db"))
    from app.db.store import Store
    Store(str(db))

    session = CloudUser(
        user_id="owner-1", tier="premium", db=db,
        has_byok=False, household_id="hh-test", is_household_owner=True
    )
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/v1/household/invite")
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "invite_url" in data
    assert len(data["token"]) == 64  # 32 bytes hex
    app.dependency_overrides.clear()


def test_accept_invalid_token_returns_404():
    """Accepting a non-existent token returns 404."""
    from app.main import app
    from app.cloud_session import get_session
    import tempfile, pathlib

    db = pathlib.Path(tempfile.mktemp(suffix=".db"))
    from app.db.store import Store
    Store(str(db))

    session = CloudUser(user_id="new-user", tier="free", db=db, has_byok=False)
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/v1/household/accept", json={
        "household_id": "hh-test",
        "token": "deadbeef" * 8,
    })
    assert resp.status_code == 404
    app.dependency_overrides.clear()
