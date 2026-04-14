"""Tests for the heimdall_orch service module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_orch_response(
    allowed: bool, calls_used: int = 0, calls_total: int = 60, topup_calls: int = 0
) -> MagicMock:
    """Helper to create a mock response object."""
    mock = MagicMock()
    mock.ok = True
    mock.json.return_value = {
        "allowed": allowed,
        "calls_used": calls_used,
        "calls_total": calls_total,
        "topup_calls": topup_calls,
        "period_start": "2026-04-14",
        "resets_on": "2026-05-14",
    }
    return mock


def test_check_orch_budget_returns_allowed_when_ok() -> None:
    """check_orch_budget() returns the response when the call succeeds."""
    with patch("app.services.heimdall_orch.requests.post") as mock_post:
        mock_post.return_value = _make_orch_response(allowed=True, calls_used=5)
        from app.services.heimdall_orch import check_orch_budget

        result = check_orch_budget("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["allowed"] is True
    assert result["calls_used"] == 5


def test_check_orch_budget_returns_denied_when_exhausted() -> None:
    """check_orch_budget() returns allowed=False when budget is exhausted."""
    with patch("app.services.heimdall_orch.requests.post") as mock_post:
        mock_post.return_value = _make_orch_response(allowed=False, calls_used=60, calls_total=60)
        from app.services.heimdall_orch import check_orch_budget

        result = check_orch_budget("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["allowed"] is False


def test_check_orch_budget_fails_open_on_network_error() -> None:
    """Network failure must never block the user — check_orch_budget fails open."""
    with patch("app.services.heimdall_orch.requests.post", side_effect=Exception("timeout")):
        from app.services import heimdall_orch

        result = heimdall_orch.check_orch_budget("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["allowed"] is True


def test_check_orch_budget_fails_open_on_http_error() -> None:
    """HTTP error responses fail open."""
    with patch("app.services.heimdall_orch.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        from app.services import heimdall_orch

        result = heimdall_orch.check_orch_budget("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["allowed"] is True


def test_get_orch_usage_returns_data() -> None:
    """get_orch_usage() returns the response data on success."""
    with patch("app.services.heimdall_orch.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "calls_used": 10,
            "topup_calls": 0,
            "calls_total": 60,
            "period_start": "2026-04-14",
            "resets_on": "2026-05-14",
        }
        mock_get.return_value = mock_resp
        from app.services.heimdall_orch import get_orch_usage

        result = get_orch_usage("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["calls_used"] == 10


def test_get_orch_usage_returns_zeros_on_error() -> None:
    """get_orch_usage() returns zeros when the call fails (non-blocking)."""
    with patch("app.services.heimdall_orch.requests.get", side_effect=Exception("timeout")):
        from app.services import heimdall_orch

        result = heimdall_orch.get_orch_usage("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["calls_used"] == 0
    assert result["calls_total"] == 0


def test_get_orch_usage_returns_zeros_on_http_error() -> None:
    """get_orch_usage() returns zeros on HTTP errors (non-blocking)."""
    with patch("app.services.heimdall_orch.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        from app.services import heimdall_orch

        result = heimdall_orch.get_orch_usage("CFG-KIWI-XXXX-XXXX-XXXX", "kiwi")

    assert result["calls_used"] == 0
    assert result["calls_total"] == 0
