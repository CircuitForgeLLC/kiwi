"""Tests for household session resolution in cloud_session.py."""
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

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
