"""
Tests for app.services.recipe.reranker.

All tests use CF_RERANKER_MOCK=1 -- no model weights required.
The mock reranker scores by Jaccard similarity of query tokens vs candidate
tokens, which is deterministic and fast.
"""
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_reranker(monkeypatch):
    """Force mock backend and reset the cf-core singleton before/after each test."""
    monkeypatch.setenv("CF_RERANKER_MOCK", "1")
    try:
        from circuitforge_core.reranker import reset_reranker
        reset_reranker()
        yield
        reset_reranker()
    except ImportError:
        yield


def _make_request(**kwargs):
    from app.models.schemas.recipe import RecipeRequest
    defaults = dict(pantry_items=["chicken", "rice"], tier="paid")
    defaults.update(kwargs)
    return RecipeRequest(**defaults)


def _make_suggestion(id: int, title: str, matched: list[str], missing: list[str] | None = None, match_count: int | None = None):
    from app.models.schemas.recipe import RecipeSuggestion
    mi = missing or []
    return RecipeSuggestion(
        id=id,
        title=title,
        match_count=match_count if match_count is not None else len(matched),
        matched_ingredients=matched,
        missing_ingredients=mi,
    )


# ── TestBuildQuery ────────────────────────────────────────────────────────────

class TestBuildQuery:
    def test_basic_pantry(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(pantry_items=["chicken", "rice", "broccoli"])
        query = build_query(req)
        assert "chicken" in query
        assert "rice" in query
        assert "broccoli" in query

    def test_exclude_ingredients_included(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(exclude_ingredients=["cilantro", "fish sauce"])
        query = build_query(req)
        assert "cilantro" in query
        assert "fish sauce" in query

    def test_allergies_separate_from_exclude(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(allergies=["shellfish"], exclude_ingredients=["cilantro"])
        query = build_query(req)
        # Both should appear, and they should be in separate labeled segments
        assert "shellfish" in query
        assert "cilantro" in query
        allergy_pos = query.index("shellfish")
        exclude_pos = query.index("cilantro")
        assert allergy_pos != exclude_pos

    def test_allergies_labeled_separately(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(allergies=["peanuts"], exclude_ingredients=[])
        query = build_query(req)
        assert "Allergies" in query or "allerg" in query.lower()

    def test_constraints_included(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(constraints=["gluten-free", "dairy-free"])
        query = build_query(req)
        assert "gluten-free" in query
        assert "dairy-free" in query

    def test_category_included(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(category="Soup")
        query = build_query(req)
        assert "Soup" in query

    def test_complexity_filter_included(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(complexity_filter="easy")
        query = build_query(req)
        assert "easy" in query

    def test_hard_day_mode_signal(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(hard_day_mode=True)
        query = build_query(req)
        assert "easy" in query.lower() or "minimal" in query.lower() or "effort" in query.lower()

    def test_secondary_pantry_items_expiry(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(secondary_pantry_items={"bread": "stale", "banana": "overripe"})
        query = build_query(req)
        assert "bread" in query
        assert "banana" in query
        # State labels add specificity for the cross-encoder
        assert "stale" in query or "overripe" in query

    def test_expiry_first_without_secondary(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(expiry_first=True, secondary_pantry_items={})
        query = build_query(req)
        assert "expir" in query.lower()

    def test_style_id_included(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(style_id="mediterranean")
        query = build_query(req)
        assert "mediterranean" in query.lower()

    def test_empty_pantry_returns_fallback(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(pantry_items=[])
        query = build_query(req)
        assert len(query) > 0  # never empty string

    def test_no_duplicate_separators(self):
        from app.services.recipe.reranker import build_query
        req = _make_request(
            pantry_items=["egg"],
            allergies=["nuts"],
            constraints=["vegan"],
            complexity_filter="easy",
        )
        query = build_query(req)
        assert ".." not in query  # no doubled periods from empty segments


# ── TestBuildCandidateString ──────────────────────────────────────────────────

class TestBuildCandidateString:
    def test_title_and_ingredients(self):
        from app.services.recipe.reranker import build_candidate_string
        s = _make_suggestion(1, "Chicken Fried Rice", ["chicken", "rice"], ["soy sauce"])
        candidate = build_candidate_string(s)
        assert candidate.startswith("Chicken Fried Rice")
        assert "chicken" in candidate
        assert "rice" in candidate
        assert "soy sauce" in candidate

    def test_title_only_when_no_ingredients(self):
        from app.services.recipe.reranker import build_candidate_string
        s = _make_suggestion(2, "Mystery Dish", [], [])
        candidate = build_candidate_string(s)
        assert candidate == "Mystery Dish"
        assert "Ingredients:" not in candidate

    def test_matched_before_missing(self):
        from app.services.recipe.reranker import build_candidate_string
        s = _make_suggestion(3, "Pasta Dish", ["pasta", "butter"], ["parmesan", "cream"])
        candidate = build_candidate_string(s)
        pasta_pos = candidate.index("pasta")
        parmesan_pos = candidate.index("parmesan")
        assert pasta_pos < parmesan_pos


# ── TestBuildRerankerInput ────────────────────────────────────────────────────

class TestBuildRerankerInput:
    def test_parallel_ids_and_candidates(self):
        from app.services.recipe.reranker import build_reranker_input
        req = _make_request()
        suggestions = [
            _make_suggestion(10, "Recipe A", ["chicken"]),
            _make_suggestion(20, "Recipe B", ["rice"]),
            _make_suggestion(30, "Recipe C", ["broccoli"]),
        ]
        rinput = build_reranker_input(req, suggestions)
        assert len(rinput.candidates) == 3
        assert len(rinput.suggestion_ids) == 3
        assert rinput.suggestion_ids == [10, 20, 30]

    def test_query_matches_build_query(self):
        from app.services.recipe.reranker import build_query, build_reranker_input
        req = _make_request(pantry_items=["egg", "cheese"], constraints=["vegetarian"])
        suggestions = [_make_suggestion(1, "Omelette", ["egg", "cheese"])]
        rinput = build_reranker_input(req, suggestions)
        assert rinput.query == build_query(req)


# ── TestRerankSuggestions ─────────────────────────────────────────────────────

class TestRerankSuggestions:
    def test_free_tier_returns_none(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="free")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(5)]
        result = rerank_suggestions(req, suggestions)
        assert result is None

    def test_paid_tier_returns_reranked_list(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="paid", pantry_items=["chicken", "rice"])
        suggestions = [
            _make_suggestion(1, "Chicken Fried Rice", ["chicken", "rice"]),
            _make_suggestion(2, "Chocolate Cake", ["flour", "sugar", "cocoa"]),
            _make_suggestion(3, "Chicken Soup", ["chicken", "broth"]),
        ]
        result = rerank_suggestions(req, suggestions)
        assert result is not None
        assert len(result) == len(suggestions)

    def test_rerank_score_is_populated(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="paid")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(4)]
        result = rerank_suggestions(req, suggestions)
        assert result is not None
        assert all(s.rerank_score is not None for s in result)
        assert all(isinstance(s.rerank_score, float) for s in result)

    def test_too_few_candidates_returns_none(self):
        from app.services.recipe.reranker import _MIN_CANDIDATES, rerank_suggestions
        req = _make_request(tier="paid")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(_MIN_CANDIDATES - 1)]
        result = rerank_suggestions(req, suggestions)
        assert result is None

    def test_premium_tier_gets_reranker(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="premium")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(4)]
        result = rerank_suggestions(req, suggestions)
        assert result is not None

    def test_local_tier_gets_reranker(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="local")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(4)]
        result = rerank_suggestions(req, suggestions)
        assert result is not None

    def test_preserves_all_suggestion_fields(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="paid")
        original = _make_suggestion(
            id=42,
            title="Garlic Butter Pasta",
            matched=["pasta", "butter", "garlic"],
            missing=["parmesan"],
            match_count=3,
        )
        result = rerank_suggestions(req, [original, original, original, original])
        assert result is not None
        found = next((s for s in result if s.id == 42), None)
        assert found is not None
        assert found.title == "Garlic Butter Pasta"
        assert found.matched_ingredients == ["pasta", "butter", "garlic"]
        assert found.missing_ingredients == ["parmesan"]
        assert found.match_count == 3

    def test_graceful_fallback_on_exception(self, monkeypatch):
        # Simulate reranker raising at runtime
        import app.services.recipe.reranker as reranker_mod
        from app.services.recipe.reranker import rerank_suggestions
        def _boom(query, candidates, top_n=0):
            raise RuntimeError("model exploded")
        monkeypatch.setattr(reranker_mod, "_do_rerank", _boom)
        req = _make_request(tier="paid")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(4)]
        result = rerank_suggestions(req, suggestions)
        assert result is None

    def test_original_suggestions_not_mutated(self):
        from app.services.recipe.reranker import rerank_suggestions
        req = _make_request(tier="paid")
        suggestions = [_make_suggestion(i, f"Recipe {i}", ["chicken"]) for i in range(4)]
        originals = [s.model_copy() for s in suggestions]
        rerank_suggestions(req, suggestions)
        for original, after in zip(originals, suggestions):
            assert original.rerank_score == after.rerank_score  # None == None (no mutation)
