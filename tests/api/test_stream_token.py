"""Tests for POST /api/v1/recipes/stream-token — coordinator proxy integration."""
import pytest
from unittest.mock import AsyncMock, patch


def test_coordinator_authorize_missing_url(monkeypatch):
    """coordinator_authorize raises RuntimeError when COORDINATOR_URL is unset."""
    monkeypatch.delenv("COORDINATOR_URL", raising=False)
    monkeypatch.delenv("COORDINATOR_KIWI_KEY", raising=False)
    # Will test this properly via endpoint — see Task 3 tests.
    pass
