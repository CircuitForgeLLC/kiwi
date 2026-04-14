"""Tests that orch budget gating is wired into the suggest endpoint."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.cloud_session import CloudUser, get_session
from app.main import app


def _make_session(
    tier: str = "paid",
    has_byok: bool = False,
    license_key: str | None = "CFG-KIWI-TEST-TEST-TEST",
) -> CloudUser:
    return CloudUser(
        user_id="test-user",
        tier=tier,
        db=Path("/tmp/kiwi_test.db"),
        has_byok=has_byok,
        license_key=license_key,
    )


@patch("app.api.endpoints.recipes._suggest_in_thread")
@patch("app.services.heimdall_orch.requests.post")
def test_orch_budget_exhausted_downgrades_to_l2(mock_post, mock_suggest):
    """When orch budget is denied, L3 request is downgraded to L2 and orch_fallback=True."""
    deny_resp = MagicMock()
    deny_resp.ok = True
    deny_resp.json.return_value = {
        "allowed": False, "calls_used": 60, "calls_total": 60,
        "topup_calls": 0, "period_start": "2026-04-14", "resets_on": "2026-05-14",
    }
    mock_post.return_value = deny_resp

    fallback_result = MagicMock()
    fallback_result.suggestions = []
    fallback_result.element_gaps = []
    fallback_result.grocery_list = []
    fallback_result.grocery_links = []
    fallback_result.rate_limited = False
    fallback_result.rate_limit_count = 0
    fallback_result.orch_fallback = False
    fallback_result.model_copy.return_value = fallback_result
    mock_suggest.return_value = fallback_result

    app.dependency_overrides[get_session] = lambda: _make_session(tier="paid")
    client = TestClient(app)
    resp = client.post("/api/v1/recipes/suggest", json={
        "pantry_items": ["chicken", "rice"],
        "level": 3,
        "tier": "paid",
    })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    # The engine should have been called with level=2 (downgraded from 3)
    called_req = mock_suggest.call_args[0][1]
    assert called_req.level == 2


@patch("app.api.endpoints.recipes._suggest_in_thread")
@patch("app.services.heimdall_orch.requests.post")
def test_orch_budget_allowed_passes_l3_through(mock_post, mock_suggest):
    allow_resp = MagicMock()
    allow_resp.ok = True
    allow_resp.json.return_value = {
        "allowed": True, "calls_used": 5, "calls_total": 60,
        "topup_calls": 0, "period_start": "2026-04-14", "resets_on": "2026-05-14",
    }
    mock_post.return_value = allow_resp

    ok_result = MagicMock()
    ok_result.suggestions = []
    ok_result.element_gaps = []
    ok_result.grocery_list = []
    ok_result.grocery_links = []
    ok_result.rate_limited = False
    ok_result.rate_limit_count = 0
    ok_result.orch_fallback = False
    mock_suggest.return_value = ok_result

    app.dependency_overrides[get_session] = lambda: _make_session(tier="paid")
    client = TestClient(app)
    resp = client.post("/api/v1/recipes/suggest", json={
        "pantry_items": ["chicken", "rice"],
        "level": 3,
        "tier": "paid",
    })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    called_req = mock_suggest.call_args[0][1]
    assert called_req.level == 3


@patch("app.api.endpoints.recipes._suggest_in_thread")
def test_no_orch_check_for_local_tier(mock_suggest):
    """Local sessions never hit the orch check."""
    ok_result = MagicMock()
    ok_result.suggestions = []
    ok_result.element_gaps = []
    ok_result.grocery_list = []
    ok_result.grocery_links = []
    ok_result.rate_limited = False
    ok_result.rate_limit_count = 0
    ok_result.orch_fallback = False
    mock_suggest.return_value = ok_result

    app.dependency_overrides[get_session] = lambda: _make_session(tier="local", license_key=None)
    client = TestClient(app)
    with patch("app.services.heimdall_orch.requests.post") as mock_check:
        client.post("/api/v1/recipes/suggest", json={
            "pantry_items": ["chicken"],
            "level": 3,
            "tier": "local",
        })
        mock_check.assert_not_called()
    app.dependency_overrides.clear()


@patch("app.api.endpoints.recipes._suggest_in_thread")
def test_no_orch_check_when_license_key_is_none(mock_suggest):
    """Subscription users (no license_key) skip the orch check."""
    ok_result = MagicMock()
    ok_result.suggestions = []
    ok_result.element_gaps = []
    ok_result.grocery_list = []
    ok_result.grocery_links = []
    ok_result.rate_limited = False
    ok_result.rate_limit_count = 0
    ok_result.orch_fallback = False
    mock_suggest.return_value = ok_result

    app.dependency_overrides[get_session] = lambda: _make_session(tier="paid", license_key=None)
    client = TestClient(app)
    with patch("app.services.heimdall_orch.requests.post") as mock_check:
        client.post("/api/v1/recipes/suggest", json={
            "pantry_items": ["chicken"],
            "level": 3,
            "tier": "paid",
        })
        mock_check.assert_not_called()
    app.dependency_overrides.clear()
