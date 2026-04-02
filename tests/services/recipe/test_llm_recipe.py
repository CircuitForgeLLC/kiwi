"""Tests for LLMRecipeGenerator — prompt builders and allergy filtering."""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# CFOrchClient integration tests
# ---------------------------------------------------------------------------

@dataclass
class _FakeAllocation:
    allocation_id: str = "alloc-test-1"
    service: str = "vllm"
    node_id: str = "node-1"
    gpu_id: int = 0
    model: str | None = "Ouro-2.6B-Thinking"
    url: str = "http://test:8000"
    started: bool = True
    warm: bool = True


def test_recipe_gen_uses_cf_orch_when_env_set(monkeypatch):
    """When CF_ORCH_URL is set, _call_llm uses alloc.url+/v1 as the OpenAI base_url."""
    from app.services.recipe.llm_recipe import LLMRecipeGenerator

    store = _make_store()
    gen = LLMRecipeGenerator(store)

    fake_alloc = _FakeAllocation()

    @contextmanager
    def _fake_llm_context():
        yield fake_alloc

    captured = {}

    # Fake OpenAI that records the base_url it was constructed with
    class _FakeOpenAI:
        def __init__(self, *, base_url, api_key):
            captured["base_url"] = base_url
            msg = MagicMock()
            msg.content = "Title: Test\nIngredients: a\nDirections: do it.\nNotes: none."
            choice = MagicMock()
            choice.message = msg
            completion = MagicMock()
            completion.choices = [choice]
            self.chat = MagicMock()
            self.chat.completions = MagicMock()
            self.chat.completions.create = MagicMock(return_value=completion)

    # Patch _get_llm_context directly so no real HTTP call is made
    monkeypatch.setattr(gen, "_get_llm_context", _fake_llm_context)

    with patch("app.services.recipe.llm_recipe.OpenAI", _FakeOpenAI):
        gen._call_llm("make me a recipe")

    assert captured.get("base_url") == "http://test:8000/v1"


def test_recipe_gen_falls_back_without_cf_orch(monkeypatch):
    """When CF_ORCH_URL is not set, _call_llm falls back to LLMRouter."""
    from app.services.recipe.llm_recipe import LLMRecipeGenerator

    store = _make_store()
    gen = LLMRecipeGenerator(store)

    monkeypatch.delenv("CF_ORCH_URL", raising=False)

    router_called = {}

    def _fake_complete(prompt, **_kwargs):
        router_called["prompt"] = prompt
        return "Title: Direct\nIngredients: x\nDirections: go.\nNotes: ok."

    fake_router = MagicMock()
    fake_router.complete.side_effect = _fake_complete

    # Patch where LLMRouter is imported inside _call_llm
    with patch("circuitforge_core.llm.router.LLMRouter", return_value=fake_router):
        gen._call_llm("direct path prompt")

    assert router_called.get("prompt") == "direct path prompt"
