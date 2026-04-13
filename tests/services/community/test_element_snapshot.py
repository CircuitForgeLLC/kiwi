# tests/services/community/test_element_snapshot.py
import pytest
from unittest.mock import MagicMock
from app.services.community.element_snapshot import compute_snapshot, ElementSnapshot


def make_mock_store(recipe_rows: list[dict]) -> MagicMock:
    store = MagicMock()
    store.get_recipes_by_ids.return_value = recipe_rows
    return store


RECIPE_ROW = {
    "id": 1,
    "name": "Spaghetti Carbonara",
    "ingredient_names": ["pasta", "eggs", "guanciale", "pecorino"],
    "keywords": ["italian", "quick", "dinner"],
    "category": "dinner",
    "fat": 22.0,
    "protein": 18.0,
    "moisture": 45.0,
    "seasoning_score": 0.7,
    "richness_score": 0.8,
    "brightness_score": 0.2,
    "depth_score": 0.6,
    "aroma_score": 0.5,
    "structure_score": 0.9,
    "texture_profile": "creamy",
}


def test_compute_snapshot_basic():
    store = make_mock_store([RECIPE_ROW])
    snap = compute_snapshot(recipe_ids=[1], store=store)
    assert isinstance(snap, ElementSnapshot)
    assert 0.0 <= snap.seasoning_score <= 1.0
    assert snap.texture_profile == "creamy"


def test_compute_snapshot_averages_multiple_recipes():
    row2 = {**RECIPE_ROW, "id": 2, "seasoning_score": 0.3, "richness_score": 0.2}
    store = make_mock_store([RECIPE_ROW, row2])
    snap = compute_snapshot(recipe_ids=[1, 2], store=store)
    # seasoning: average of 0.7 and 0.3 = 0.5
    assert abs(snap.seasoning_score - 0.5) < 0.01


def test_compute_snapshot_allergen_flags_detected():
    row = {**RECIPE_ROW, "ingredient_names": ["pasta", "eggs", "milk", "shrimp", "peanuts"]}
    store = make_mock_store([row])
    snap = compute_snapshot(recipe_ids=[1], store=store)
    assert "gluten" in snap.allergen_flags   # pasta
    assert "dairy" in snap.allergen_flags    # milk
    assert "shellfish" in snap.allergen_flags  # shrimp
    assert "nuts" in snap.allergen_flags     # peanuts


def test_compute_snapshot_dietary_tags_vegetarian():
    row = {**RECIPE_ROW, "ingredient_names": ["pasta", "eggs", "tomato", "basil"]}
    store = make_mock_store([row])
    snap = compute_snapshot(recipe_ids=[1], store=store)
    assert "vegetarian" in snap.dietary_tags


def test_compute_snapshot_no_recipes_returns_defaults():
    store = make_mock_store([])
    snap = compute_snapshot(recipe_ids=[], store=store)
    assert snap.seasoning_score == 0.0
    assert snap.dietary_tags == ()
    assert snap.allergen_flags == ()


def test_element_snapshot_immutable():
    store = make_mock_store([RECIPE_ROW])
    snap = compute_snapshot(recipe_ids=[1], store=store)
    with pytest.raises((AttributeError, TypeError)):
        snap.seasoning_score = 0.0  # type: ignore
