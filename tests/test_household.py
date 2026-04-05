"""Tests for household session resolution in cloud_session.py."""
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

os.environ.setdefault("CLOUD_MODE", "false")

from app.cloud_session import (
    CloudUser,
    _user_db_path,
    CLOUD_DATA_ROOT,
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


def test_user_db_path_personal():
    path = _user_db_path("abc123", household_id=None)
    assert path == CLOUD_DATA_ROOT / "abc123" / "kiwi.db"


def test_user_db_path_household():
    path = _user_db_path("abc123", household_id="hh-xyz")
    assert path == CLOUD_DATA_ROOT / "household_hh-xyz" / "kiwi.db"
