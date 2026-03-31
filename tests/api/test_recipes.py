import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.cloud_session import get_session
from app.db.session import get_store

client = TestClient(app)


def _make_session(tier: str = "free", has_byok: bool = False) -> MagicMock:
    mock = MagicMock()
    mock.tier = tier
    mock.has_byok = has_byok
    return mock


def _make_store() -> MagicMock:
    mock = MagicMock()
    mock.search_recipes_by_ingredients.return_value = [
        {
            "id": 1,
            "title": "Butter Pasta",
            "ingredient_names": ["butter", "pasta"],
            "element_coverage": {"Richness": 0.5},
            "match_count": 2,
            "directions": ["mix and heat"],
        }
    ]
    mock.check_and_increment_rate_limit.return_value = (True, 1)
    return mock


@pytest.fixture(autouse=True)
def override_deps():
    session_mock = _make_session()
    store_mock = _make_store()
    app.dependency_overrides[get_session] = lambda: session_mock
    app.dependency_overrides[get_store] = lambda: store_mock
    yield session_mock, store_mock
    app.dependency_overrides.clear()


def test_suggest_returns_200():
    resp = client.post("/api/v1/recipes/suggest", json={
        "pantry_items": ["butter", "pasta"],
        "level": 1,
        "constraints": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert "element_gaps" in data
    assert "grocery_list" in data
    assert "grocery_links" in data


def test_suggest_level4_requires_wildcard_confirmed():
    resp = client.post("/api/v1/recipes/suggest", json={
        "pantry_items": ["butter"],
        "level": 4,
        "constraints": [],
        "wildcard_confirmed": False,
    })
    assert resp.status_code == 400


def test_suggest_level3_requires_paid_tier(override_deps):
    session_mock, _ = override_deps
    session_mock.tier = "free"
    session_mock.has_byok = False
    resp = client.post("/api/v1/recipes/suggest", json={
        "pantry_items": ["butter"],
        "level": 3,
        "constraints": [],
    })
    assert resp.status_code == 403
