"""Tests for LLMRecipeGenerator — prompt builders and allergy filtering."""
from __future__ import annotations

import pytest

from app.models.schemas.recipe import RecipeRequest
from app.services.recipe.element_classifier import IngredientProfile


def _make_store():
    """Create a minimal in-memory Store."""
    from app.db.store import Store
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store = Store.__new__(Store)
    store.conn = conn
    return store


def test_build_level3_prompt_contains_element_scaffold():
    """Level 3 prompt includes element coverage, pantry items, and constraints."""
    from app.services.recipe.llm_recipe import LLMRecipeGenerator

    store = _make_store()
    gen = LLMRecipeGenerator(store)

    req = RecipeRequest(
        pantry_items=["butter", "mushrooms"],
        level=3,
        constraints=["vegetarian"],
    )
    profiles = [
        IngredientProfile(name="butter", elements=["Richness"]),
        IngredientProfile(name="mushrooms", elements=["Depth"]),
    ]
    gaps = ["Brightness", "Aroma"]

    prompt = gen.build_level3_prompt(req, profiles, gaps)

    assert "Richness" in prompt
    assert "Depth" in prompt
    assert "Brightness" in prompt
    assert "butter" in prompt
    assert "vegetarian" in prompt


def test_build_level4_prompt_contains_pantry_and_constraints():
    """Level 4 prompt is concise and includes key context."""
    from app.services.recipe.llm_recipe import LLMRecipeGenerator

    store = _make_store()
    gen = LLMRecipeGenerator(store)

    req = RecipeRequest(
        pantry_items=["pasta", "eggs", "mystery ingredient"],
        level=4,
        constraints=["no gluten"],
        allergies=["gluten"],
        wildcard_confirmed=True,
    )

    prompt = gen.build_level4_prompt(req)

    assert "mystery" in prompt.lower()
    assert "gluten" in prompt.lower()
    assert len(prompt) < 1500


def test_allergy_items_excluded_from_prompt():
    """Allergy items are listed as forbidden AND filtered from pantry shown to LLM."""
    from app.services.recipe.llm_recipe import LLMRecipeGenerator

    store = _make_store()
    gen = LLMRecipeGenerator(store)

    req = RecipeRequest(
        pantry_items=["olive oil", "peanuts", "garlic"],
        level=3,
        constraints=[],
        allergies=["peanuts"],
    )
    profiles = [
        IngredientProfile(name="olive oil", elements=["Richness"]),
        IngredientProfile(name="peanuts", elements=["Texture"]),
        IngredientProfile(name="garlic", elements=["Aroma"]),
    ]
    gaps: list[str] = []

    prompt = gen.build_level3_prompt(req, profiles, gaps)

    # Check peanuts are in the exclusion section but NOT in the pantry section
    lines = prompt.split("\n")
    pantry_line = next((l for l in lines if l.startswith("Pantry")), "")
    exclusion_line = next(
        (l for l in lines if "must not" in l.lower()),
        "",
    )
    assert "peanuts" not in pantry_line.lower()
    assert "peanuts" in exclusion_line.lower()
    assert "olive oil" in prompt.lower()


def test_generate_returns_result_when_llm_responds(monkeypatch):
    """generate() returns RecipeResult with title when LLM returns a valid response."""
    from app.services.recipe.llm_recipe import LLMRecipeGenerator
    from app.models.schemas.recipe import RecipeResult

    store = _make_store()
    gen = LLMRecipeGenerator(store)

    canned_response = (
        "Title: Mushroom Butter Pasta\n"
        "Ingredients: butter, mushrooms, pasta\n"
        "Directions: Cook pasta. Sauté mushrooms in butter. Combine.\n"
        "Notes: Add parmesan to taste.\n"
    )
    monkeypatch.setattr(gen, "_call_llm", lambda prompt: canned_response)

    req = RecipeRequest(
        pantry_items=["butter", "mushrooms", "pasta"],
        level=3,
        constraints=["vegetarian"],
    )
    profiles = [
        IngredientProfile(name="butter", elements=["Richness"]),
        IngredientProfile(name="mushrooms", elements=["Depth"]),
    ]
    gaps = ["Brightness"]

    result = gen.generate(req, profiles, gaps)

    assert isinstance(result, RecipeResult)
    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.title == "Mushroom Butter Pasta"
    assert "butter" in suggestion.missing_ingredients
    assert len(suggestion.directions) > 0
    assert "parmesan" in suggestion.notes.lower()
    assert result.element_gaps == ["Brightness"]
