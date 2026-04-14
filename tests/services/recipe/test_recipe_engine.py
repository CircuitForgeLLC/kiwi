import pytest, json
from tests.services.recipe.test_element_classifier import store_with_profiles
from tests.db.test_store_recipes import store_with_recipes


def test_level1_returns_ranked_suggestions(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest
    engine = RecipeEngine(store_with_recipes)
    req = RecipeRequest(
        pantry_items=["butter", "parmesan"],
        level=1,
        constraints=[],
    )
    result = engine.suggest(req)
    assert len(result.suggestions) > 0
    assert result.suggestions[0].title == "Butter Pasta"


def test_level1_expiry_first_requires_rate_limit_free(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest
    engine = RecipeEngine(store_with_recipes)
    for _ in range(5):
        req = RecipeRequest(
            pantry_items=["butter"],
            level=1,
            constraints=[],
            expiry_first=True,
            tier="free",
        )
        result = engine.suggest(req)
        assert result.rate_limited is False
    req = RecipeRequest(
        pantry_items=["butter"],
        level=1,
        constraints=[],
        expiry_first=True,
        tier="free",
    )
    result = engine.suggest(req)
    assert result.rate_limited is True


def test_level2_returns_swap_candidates(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest
    store_with_recipes.conn.execute("""
        INSERT INTO substitution_pairs
          (original_name, substitute_name, constraint_label, fat_delta, occurrence_count)
        VALUES (?,?,?,?,?)
    """, ("butter", "coconut oil", "vegan", -1.0, 12))
    store_with_recipes.conn.commit()

    engine = RecipeEngine(store_with_recipes)
    req = RecipeRequest(
        pantry_items=["butter", "parmesan"],
        level=2,
        constraints=["vegan"],
    )
    result = engine.suggest(req)
    swapped = [s for s in result.suggestions if s.swap_candidates]
    assert len(swapped) > 0


def test_element_gaps_reported(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest
    engine = RecipeEngine(store_with_recipes)
    req = RecipeRequest(pantry_items=["butter"], level=1, constraints=[])
    result = engine.suggest(req)
    assert isinstance(result.element_gaps, list)


def test_grocery_list_max_missing(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest
    engine = RecipeEngine(store_with_recipes)
    # Butter Pasta needs butter, pasta, parmesan. We have only butter → missing 2
    req = RecipeRequest(
        pantry_items=["butter"],
        level=1,
        constraints=[],
        max_missing=2,
    )
    result = engine.suggest(req)
    assert all(len(s.missing_ingredients) <= 2 for s in result.suggestions)
    assert isinstance(result.grocery_list, list)


def test_hard_day_mode_filters_complex_methods(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest, _classify_method_complexity
    # Test the classifier directly
    assert _classify_method_complexity(["mix all ingredients", "stir to combine"]) == "easy"
    assert _classify_method_complexity(["sauté onions", "braise for 2 hours"]) == "involved"

    # With hard_day_mode, involved recipes should be filtered out
    # Seed a hard recipe into the store
    store_with_recipes.conn.execute("""
        INSERT INTO recipes (external_id, title, ingredients, ingredient_names,
                             directions, category, keywords, element_coverage)
        VALUES (?,?,?,?,?,?,?,?)
    """, ("99", "Braised Short Ribs",
          '["butter","beef ribs"]', '["butter","beef ribs"]',
          '["braise short ribs for 3 hours","reduce sauce"]',
          "Meat", '[]', '{"Richness":0.8}'))
    store_with_recipes.conn.commit()

    engine = RecipeEngine(store_with_recipes)
    req_hard = RecipeRequest(pantry_items=["butter"], level=1, constraints=[], hard_day_mode=True)
    result = engine.suggest(req_hard)
    titles = [s.title for s in result.suggestions]
    assert "Braised Short Ribs" not in titles


def test_grocery_links_free_tier(store_with_recipes):
    from app.services.recipe.recipe_engine import RecipeEngine, RecipeRequest
    engine = RecipeEngine(store_with_recipes)
    req = RecipeRequest(pantry_items=["butter"], level=1, constraints=[], max_missing=5)
    result = engine.suggest(req)
    # Links may be empty if no retailer env vars set, but structure must be correct
    assert isinstance(result.grocery_links, list)
    for link in result.grocery_links:
        assert hasattr(link, "ingredient")
        assert hasattr(link, "retailer")
        assert hasattr(link, "url")


def test_suggest_returns_no_assembly_results(store_with_recipes):
    """Assembly templates (negative IDs) must no longer appear in suggest() output."""
    from app.services.recipe.recipe_engine import RecipeEngine
    from app.models.schemas.recipe import RecipeRequest
    engine = RecipeEngine(store_with_recipes)
    req = RecipeRequest(
        pantry_items=["flour tortilla", "chicken", "salsa", "rice"],
        level=1,
        constraints=[],
    )
    result = engine.suggest(req)
    assembly_ids = [s.id for s in result.suggestions if s.id < 0]
    assert assembly_ids == [], f"Found assembly results in suggest(): {assembly_ids}"
