"""Tests for the /orch-usage proxy endpoint."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.cloud_session import CloudUser, get_session
from app.main import app


def _make_session(license_key=None, tier="paid"):
    return CloudUser(
        user_id="user-1",
        tier=tier,
        db=Path("/tmp/kiwi_test.db"),
        has_byok=False,
        license_key=license_key,
    )


def test_orch_usage_returns_data_for_lifetime_user():
    """GET /orch-usage with a lifetime key returns usage data."""
    app.dependency_overrides[get_session] = lambda: _make_session(
        license_key="CFG-KIWI-TEST-0000-0000"
    )
    client = TestClient(app)

    with patch("app.api.endpoints.orch_usage.get_orch_usage") as mock_usage:
        mock_usage.return_value = {
            "calls_used": 10,
            "topup_calls": 0,
            "calls_total": 60,
            "period_start": "2026-04-14",
            "resets_on": "2026-05-14",
        }
        resp = client.get("/api/v1/orch-usage")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls_used"] == 10
    assert data["calls_total"] == 60


def test_orch_usage_returns_null_for_subscription_user():
    """GET /orch-usage with no license_key returns null."""
    app.dependency_overrides[get_session] = lambda: _make_session(
        license_key=None, tier="paid"
    )
    client = TestClient(app)
    resp = client.get("/api/v1/orch-usage")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() is None
