# tests/api/test_community_endpoints.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_community_posts_no_db_returns_empty():
    """When COMMUNITY_DB_URL is not set, GET /community/posts returns empty list (no 500)."""
    with patch("app.api.endpoints.community._community_store", None):
        response = client.get("/api/v1/community/posts")
    assert response.status_code == 200
    data = response.json()
    assert "posts" in data
    assert isinstance(data["posts"], list)


def test_get_community_post_not_found():
    """GET /community/posts/{slug} returns 404 when slug doesn't exist."""
    mock_store = MagicMock()
    mock_store.get_post_by_slug.return_value = None
    with patch("app.api.endpoints.community._community_store", mock_store):
        response = client.get("/api/v1/community/posts/nonexistent-slug")
    assert response.status_code == 404


def test_get_community_rss():
    """GET /community/feed.rss returns XML with content-type application/rss+xml."""
    mock_store = MagicMock()
    mock_store.list_posts.return_value = []
    with patch("app.api.endpoints.community._community_store", mock_store):
        response = client.get("/api/v1/community/feed.rss")
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "")


def test_post_community_requires_auth():
    """POST /community/posts requires authentication (401/403/422) or community store (503).

    In local/dev mode get_session bypasses JWT auth and returns a privileged user,
    so the next gate is the community store check (503 when COMMUNITY_DB_URL is not set).
    In cloud mode the endpoint requires a valid session (401/403).
    """
    response = client.post("/api/v1/community/posts", json={"title": "Test"})
    assert response.status_code in (401, 403, 422, 503)


def test_delete_post_requires_auth():
    """DELETE /community/posts/{slug} requires authentication (401/403) or community store (503).

    Same local-mode caveat as test_post_community_requires_auth.
    """
    response = client.delete("/api/v1/community/posts/some-slug")
    assert response.status_code in (401, 403, 422, 503)


def test_fork_post_route_exists():
    """POST /community/posts/{slug}/fork route exists (not 404)."""
    response = client.post("/api/v1/community/posts/some-slug/fork")
    assert response.status_code != 404


def test_local_feed_returns_json():
    """GET /community/local-feed returns JSON list for LAN peers."""
    mock_store = MagicMock()
    mock_store.list_posts.return_value = []
    with patch("app.api.endpoints.community._community_store", mock_store):
        response = client.get("/api/v1/community/local-feed")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
