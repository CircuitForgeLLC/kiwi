"""Tests for GET /templates, GET /template-candidates, POST /build endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """FastAPI test client with a seeded in-memory DB."""
    import os
    os.environ["KIWI_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["CLOUD_MODE"] = "false"
    from app.main import app
    from app.db.store import Store
    store = Store(tmp_path / "test.db")
    store.conn.execute(
        "INSERT INTO products (name, barcode) VALUES (?,?)", ("chicken breast", None)
    )
    store.conn.execute(
        "INSERT INTO inventory_items (product_id, location, status) VALUES (1,'pantry','available')"
    )
    store.conn.execute(
        "INSERT INTO products (name, barcode) VALUES (?,?)", ("flour tortilla", None)
    )
    store.conn.execute(
        "INSERT INTO inventory_items (product_id, location, status) VALUES (2,'pantry','available')"
    )
    store.conn.commit()
    return TestClient(app)


def test_get_templates_returns_13(client):
    resp = client.get("/api/v1/recipes/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 13


def test_get_templates_shape(client):
    resp = client.get("/api/v1/recipes/templates")
    t = next(t for t in resp.json() if t["id"] == "burrito_taco")
    assert t["icon"] == "🌯"
    assert len(t["role_sequence"]) >= 2
    assert t["role_sequence"][0]["required"] is True


def test_get_template_candidates_returns_shape(client):
    resp = client.get(
        "/api/v1/recipes/template-candidates",
        params={"template_id": "burrito_taco", "role": "tortilla or wrap"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "compatible" in data
    assert "other" in data
    assert "available_tags" in data


def test_post_build_returns_recipe(client):
    resp = client.post("/api/v1/recipes/build", json={
        "template_id": "burrito_taco",
        "role_overrides": {
            "tortilla or wrap": "flour tortilla",
            "protein": "chicken breast",
        }
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == -1
    assert len(data["directions"]) > 0


def test_post_build_unknown_template_returns_404(client):
    resp = client.post("/api/v1/recipes/build", json={
        "template_id": "does_not_exist",
        "role_overrides": {}
    })
    assert resp.status_code == 404
