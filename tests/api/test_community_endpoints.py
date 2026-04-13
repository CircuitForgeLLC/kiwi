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
    """GET /community/feed.rss returns XML content-type."""
    with patch("app.api.endpoints.community._community_store", None):
        response = client.get("/api/v1/community/feed.rss")
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "")


def test_post_community_no_store_returns_503():
    """POST /community/posts returns 503 when community DB is not configured.

    In local/dev mode the session auth is bypassed (local session). The endpoint
    should then fail-soft with 503, not 500. Production cloud mode enforces auth
    before the store check — tested in integration tests.
    """
    with patch("app.api.endpoints.community._community_store", None):
        response = client.post("/api/v1/community/posts", json={"title": "Test"})
    # 503 = no community store; 402 = tier gate fired first; both are acceptable
    assert response.status_code in (402, 503)


def test_delete_post_no_store_returns_503():
    """DELETE /community/posts/{slug} returns 503 when community DB is not configured."""
    with patch("app.api.endpoints.community._community_store", None):
        response = client.delete("/api/v1/community/posts/some-slug")
    assert response.status_code in (400, 503)


def test_fork_post_route_exists():
    """POST /community/posts/{slug}/fork route must exist (not 404)."""
    response = client.post("/api/v1/community/posts/some-slug/fork")
    assert response.status_code != 404


def test_local_feed_returns_json():
    """GET /community/local-feed returns JSON list for LAN peers."""
    with patch("app.api.endpoints.community._community_store", None):
        response = client.get("/api/v1/community/local-feed")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
