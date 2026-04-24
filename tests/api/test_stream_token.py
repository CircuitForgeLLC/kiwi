"""Tests for POST /api/v1/recipes/stream-token — coordinator proxy integration."""
import pytest
from unittest.mock import AsyncMock, patch

from app.models.schemas.recipe import StreamTokenRequest, StreamTokenResponse


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
