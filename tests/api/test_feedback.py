"""Tests for the /feedback endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /feedback/status ──────────────────────────────────────────────────────────

def test_status_disabled_when_no_token(monkeypatch):
    monkeypatch.delenv("FORGEJO_API_TOKEN", raising=False)
    monkeypatch.setattr("app.core.config.settings.DEMO_MODE", False)
    res = client.get("/api/v1/feedback/status")
    assert res.status_code == 200
    assert res.json() == {"enabled": False}


def test_status_enabled_when_token_set(monkeypatch):
    monkeypatch.setenv("FORGEJO_API_TOKEN", "test-token")
    monkeypatch.setattr("app.core.config.settings.DEMO_MODE", False)
    res = client.get("/api/v1/feedback/status")
    assert res.status_code == 200
    assert res.json() == {"enabled": True}


def test_status_disabled_in_demo_mode(monkeypatch):
    monkeypatch.setenv("FORGEJO_API_TOKEN", "test-token")
    monkeypatch.setattr("app.core.config.settings.DEMO_MODE", True)
    res = client.get("/api/v1/feedback/status")
    assert res.status_code == 200
    assert res.json() == {"enabled": False}


# ── POST /feedback ────────────────────────────────────────────────────────────

def test_submit_returns_503_when_no_token(monkeypatch):
    monkeypatch.delenv("FORGEJO_API_TOKEN", raising=False)
    res = client.post("/api/v1/feedback", json={
        "title": "Test", "description": "desc", "type": "bug",
    })
    assert res.status_code == 503


def test_submit_returns_403_in_demo_mode(monkeypatch):
    monkeypatch.setenv("FORGEJO_API_TOKEN", "test-token")
    monkeypatch.setattr("app.core.config.settings.DEMO_MODE", True)
    res = client.post("/api/v1/feedback", json={
        "title": "Test", "description": "desc", "type": "bug",
    })
    assert res.status_code == 403


def test_submit_creates_issue(monkeypatch):
    monkeypatch.setenv("FORGEJO_API_TOKEN", "test-token")
    monkeypatch.setenv("FORGEJO_REPO", "Circuit-Forge/kiwi")
    monkeypatch.setattr("app.core.config.settings.DEMO_MODE", False)

    # Mock the two Forgejo HTTP calls: label fetch + issue create
    label_response = MagicMock()
    label_response.ok = True
    label_response.json.return_value = [
        {"id": 1, "name": "beta-feedback"},
        {"id": 2, "name": "needs-triage"},
        {"id": 3, "name": "bug"},
    ]

    issue_response = MagicMock()
    issue_response.ok = True
    issue_response.json.return_value = {"number": 42, "html_url": "https://example.com/issues/42"}

    with patch("app.api.endpoints.feedback.requests.get", return_value=label_response), \
         patch("app.api.endpoints.feedback.requests.post", return_value=issue_response):
        res = client.post("/api/v1/feedback", json={
            "title": "Something broke",
            "description": "It broke when I tapped X",
            "type": "bug",
            "repro": "1. Open app\n2. Tap X",
            "tab": "pantry",
        })

    assert res.status_code == 200
    data = res.json()
    assert data["issue_number"] == 42
    assert data["issue_url"] == "https://example.com/issues/42"


def test_submit_returns_502_on_forgejo_error(monkeypatch):
    monkeypatch.setenv("FORGEJO_API_TOKEN", "test-token")
    monkeypatch.setattr("app.core.config.settings.DEMO_MODE", False)

    label_response = MagicMock()
    label_response.ok = True
    label_response.json.return_value = []

    bad_response = MagicMock()
    bad_response.ok = False
    bad_response.text = "forbidden"

    with patch("app.api.endpoints.feedback.requests.get", return_value=label_response), \
         patch("app.api.endpoints.feedback.requests.post", return_value=bad_response):
        res = client.post("/api/v1/feedback", json={
            "title": "Oops", "description": "desc", "type": "other",
        })

    assert res.status_code == 502
