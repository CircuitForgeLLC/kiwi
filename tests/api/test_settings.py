"""Tests for user settings endpoints."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.cloud_session import get_session
from app.db.session import get_store
from app.main import app
from app.models.schemas.recipe import RecipeRequest
from app.services.recipe.recipe_engine import RecipeEngine

client = TestClient(app)


def _make_session(tier: str = "free", has_byok: bool = False) -> MagicMock:
    mock = MagicMock()
    mock.tier = tier
    mock.has_byok = has_byok
    return mock


def _make_store() -> MagicMock:
    mock = MagicMock()
    mock.get_setting.return_value = None
    mock.set_setting.return_value = None
    mock.search_recipes_by_ingredients.return_value = []
    mock.check_and_increment_rate_limit.return_value = (True, 1)
    return mock


@pytest.fixture()
def tmp_store() -> MagicMock:
    session_mock = _make_session()
    store_mock = _make_store()
    app.dependency_overrides[get_session] = lambda: session_mock
    app.dependency_overrides[get_store] = lambda: store_mock
    yield store_mock
    app.dependency_overrides.clear()


def test_set_and_get_cooking_equipment(tmp_store: MagicMock) -> None:
    """PUT then GET round-trips the cooking_equipment value."""
    equipment_json = '["oven", "stovetop"]'

    # PUT stores the value
    put_resp = client.put(
        "/api/v1/settings/cooking_equipment",
        json={"value": equipment_json},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["key"] == "cooking_equipment"
    assert put_resp.json()["value"] == equipment_json
    tmp_store.set_setting.assert_called_once_with("cooking_equipment", equipment_json)

    # GET returns the stored value
    tmp_store.get_setting.return_value = equipment_json
    get_resp = client.get("/api/v1/settings/cooking_equipment")
    assert get_resp.status_code == 200
    assert get_resp.json()["value"] == equipment_json


def test_get_missing_setting_returns_404(tmp_store: MagicMock) -> None:
    """GET an allowed key that was never set returns 404."""
    tmp_store.get_setting.return_value = None
    resp = client.get("/api/v1/settings/cooking_equipment")
    assert resp.status_code == 404


def test_hard_day_mode_uses_equipment_setting(tmp_store: MagicMock) -> None:
    """RecipeEngine.suggest() respects cooking_equipment from store when hard_day_mode=True."""
    equipment_json = '["microwave"]'
    tmp_store.get_setting.return_value = equipment_json

    engine = RecipeEngine(store=tmp_store)
    req = RecipeRequest(
        pantry_items=["rice", "water"],
        level=1,
        constraints=[],
        hard_day_mode=True,
    )

    result = engine.suggest(req)

    # Engine should have read the equipment setting
    tmp_store.get_setting.assert_called_with("cooking_equipment")
    # Result is a valid RecipeResult (no crash)
    assert result is not None
    assert hasattr(result, "suggestions")


def test_put_unknown_key_returns_422(tmp_store: MagicMock) -> None:
    """PUT to an unknown settings key returns 422."""
    resp = client.put(
        "/api/v1/settings/nonexistent_key",
        json={"value": "something"},
    )
    assert resp.status_code == 422


def test_put_null_value_returns_422(tmp_store: MagicMock) -> None:
    """PUT with a null value returns 422 (Pydantic validation)."""
    resp = client.put(
        "/api/v1/settings/cooking_equipment",
        json={"value": None},
    )
    assert resp.status_code == 422
