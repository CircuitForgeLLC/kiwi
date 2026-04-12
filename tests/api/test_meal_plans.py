# tests/api/test_meal_plans.py
"""Integration tests for /api/v1/meal-plans/ endpoints."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.cloud_session import get_session
from app.db.session import get_store
from app.main import app

client = TestClient(app)


def _make_session(tier: str = "free") -> MagicMock:
    m = MagicMock()
    m.tier = tier
    m.has_byok = False
    return m


def _make_store() -> MagicMock:
    m = MagicMock()
    m.create_meal_plan.return_value = {
        "id": 1, "week_start": "2026-04-14",
        "meal_types": ["dinner"], "created_at": "2026-04-12T10:00:00",
    }
    m.list_meal_plans.return_value = []
    m.get_meal_plan.return_value = None
    m.get_plan_slots.return_value = []
    m.upsert_slot.return_value = {
        "id": 1, "plan_id": 1, "day_of_week": 0, "meal_type": "dinner",
        "recipe_id": 42, "recipe_title": "Pasta", "servings": 2.0, "custom_label": None,
    }
    m.get_inventory.return_value = []
    m.get_plan_recipes.return_value = []
    m.get_prep_session_for_plan.return_value = None
    m.create_prep_session.return_value = {
        "id": 1, "plan_id": 1, "scheduled_date": "2026-04-13",
        "status": "draft", "created_at": "2026-04-12T10:00:00",
    }
    m.get_prep_tasks.return_value = []
    m.bulk_insert_prep_tasks.return_value = []
    return m


@pytest.fixture()
def free_session():
    session = _make_session("free")
    store = _make_store()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


@pytest.fixture()
def paid_session():
    session = _make_session("paid")
    store = _make_store()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


def test_create_plan_free_tier_locks_to_dinner(free_session):
    resp = client.post("/api/v1/meal-plans/", json={
        "week_start": "2026-04-14", "meal_types": ["breakfast", "dinner"]
    })
    assert resp.status_code == 200
    # Free tier forced to dinner-only regardless of request
    free_session.create_meal_plan.assert_called_once_with("2026-04-14", ["dinner"])


def test_create_plan_paid_tier_respects_meal_types(paid_session):
    resp = client.post("/api/v1/meal-plans/", json={
        "week_start": "2026-04-14", "meal_types": ["breakfast", "lunch", "dinner"]
    })
    assert resp.status_code == 200
    paid_session.create_meal_plan.assert_called_once_with(
        "2026-04-14", ["breakfast", "lunch", "dinner"]
    )


def test_list_plans_returns_200(free_session):
    resp = client.get("/api/v1/meal-plans/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_upsert_slot_returns_200(free_session):
    free_session.get_meal_plan.return_value = {
        "id": 1, "week_start": "2026-04-14", "meal_types": ["dinner"],
        "created_at": "2026-04-12T10:00:00",
    }
    resp = client.put(
        "/api/v1/meal-plans/1/slots/0/dinner",
        json={"recipe_id": 42, "servings": 2.0},
    )
    assert resp.status_code == 200


def test_get_shopping_list_returns_200(free_session):
    free_session.get_meal_plan.return_value = {
        "id": 1, "week_start": "2026-04-14", "meal_types": ["dinner"],
        "created_at": "2026-04-12T10:00:00",
    }
    resp = client.get("/api/v1/meal-plans/1/shopping-list")
    assert resp.status_code == 200
    body = resp.json()
    assert "gap_items" in body
    assert "covered_items" in body
