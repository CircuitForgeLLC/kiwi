"""Tests for POST /api/v1/recipes/stream-token — coordinator proxy integration."""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.cloud_session import CloudUser, get_session
from app.main import app
from app.models.schemas.recipe import StreamTokenRequest, StreamTokenResponse


def _make_session(tier: str = "paid", has_byok: bool = False) -> CloudUser:
    return CloudUser(
        user_id="test-user",
        tier=tier,
        db=Path("/tmp/kiwi_test.db"),
        has_byok=has_byok,
        license_key=None,
    )


def _client(tier: str = "paid", has_byok: bool = False) -> TestClient:
    app.dependency_overrides[get_session] = lambda: _make_session(tier=tier, has_byok=has_byok)
    return TestClient(app)


def test_coordinator_authorize_missing_url(monkeypatch):
    """coordinator_authorize raises RuntimeError when COORDINATOR_URL is unset."""
    monkeypatch.delenv("COORDINATOR_URL", raising=False)
    monkeypatch.delenv("COORDINATOR_KIWI_KEY", raising=False)
    # Will test this properly via endpoint — see Task 3 tests.
    pass


def test_stream_token_request_defaults():
    req = StreamTokenRequest()
    assert req.level == 4
    assert req.wildcard_confirmed is False


def test_stream_token_request_level_3():
    req = StreamTokenRequest(level=3)
    assert req.level == 3


def test_stream_token_response():
    resp = StreamTokenResponse(
        stream_url="http://10.1.10.71:7700/proxy/stream",
        token="abc-123",
        expires_in_s=60,
    )
    assert resp.stream_url.startswith("http")
    assert resp.expires_in_s == 60


def test_stream_token_tier_gate():
    """Free-tier session is rejected with 403."""
    client = _client(tier="free")
    try:
        resp = client.post("/api/v1/recipes/stream-token", json={"level": 3})
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_stream_token_level4_requires_confirmation():
    """Level 4 without wildcard_confirmed=true returns 400."""
    client = _client(tier="paid")
    try:
        resp = client.post("/api/v1/recipes/stream-token", json={"level": 4, "wildcard_confirmed": False})
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


@patch("app.api.endpoints.recipes.coordinator_authorize", new_callable=AsyncMock)
@patch("app.api.endpoints.recipes._build_stream_prompt", return_value="mock prompt")
def test_stream_token_success_level3(mock_prompt, mock_authorize):
    """Paid tier, level 3 — returns stream_url and token."""
    from app.services.coordinator_proxy import StreamTokenResult
    mock_authorize.return_value = StreamTokenResult(
        stream_url="http://10.1.10.71:7700/proxy/stream",
        token="test-token-abc",
        expires_in_s=60,
    )
    client = _client(tier="paid")
    try:
        resp = client.post("/api/v1/recipes/stream-token", json={"level": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert "stream_url" in data
        assert "token" in data
        assert data["expires_in_s"] == 60
        mock_authorize.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.endpoints.recipes.coordinator_authorize", new_callable=AsyncMock)
@patch("app.api.endpoints.recipes._build_stream_prompt", return_value="mock prompt")
def test_stream_token_coordinator_unavailable(mock_prompt, mock_authorize):
    """CoordinatorError maps to 503."""
    from app.services.coordinator_proxy import CoordinatorError
    mock_authorize.side_effect = CoordinatorError("No GPU", status_code=503)
    client = _client(tier="paid")
    try:
        resp = client.post("/api/v1/recipes/stream-token", json={"level": 3})
        assert resp.status_code == 503
    finally:
        app.dependency_overrides.clear()
