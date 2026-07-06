"""
Reranker integration for recipe suggestions.

Wraps circuitforge_core.reranker to score recipe candidates against a
natural-language query built from the user's pantry, constraints, and
preferences. Paid+ tier only; free tier returns None (caller keeps
existing sort). All exceptions are caught and logged — the reranker
must never break recipe suggestions.

Environment:
    CF_RERANKER_MOCK=1  — force mock backend (tests, no model required)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.schemas.recipe import RecipeRequest, RecipeSuggestion

log = logging.getLogger(__name__)

# Tiers that get reranker access.
_RERANKER_TIERS: frozenset[str] = frozenset({"paid", "premium", "local"})

# Minimum candidates worth reranking — below this the cross-encoder
# overhead is not justified and the overlap sort is fine.
_MIN_CANDIDATES: int = 3


@dataclass(frozen=True)
class RerankerInput:
    """Intermediate representation passed to the reranker."""
    query: str
    candidates: list[str]
    suggestion_ids: list[int]  # parallel to candidates, for re-mapping


# ── Query builder ─────────────────────────────────────────────────────────────

def build_query(req: RecipeRequest) -> str:
    """Build a natural-language query string from the recipe request.

    Encodes the user's full context so the cross-encoder can score
    relevance, dietary fit, and expiry urgency in a single pass.
    Only non-empty segments are included.
    """
    parts: list[str] = []

    if req.pantry_items:
        parts.append(f"Recipe using: {', '.join(req.pantry_items)}")

    if req.exclude_ingredients:
        parts.append(f"Avoid: {', '.join(req.exclude_ingredients)}")

    if req.allergies:
        parts.append(f"Allergies: {', '.join(req.allergies)}")

    if req.constraints:
        parts.append(f"Dietary: {', '.join(req.constraints)}")

    if req.category:
        parts.append(f"Category: {req.category}")

    if req.style_id:
        parts.append(f"Style: {req.style_id}")

    if req.complexity_filter:
        parts.append(f"Prefer: {req.complexity_filter}")

    if req.hard_day_mode:
        parts.append("Prefer: easy, minimal effort")

    # Secondary pantry items carry a state label (e.g. "stale", "overripe")
    # that helps the reranker favour recipes suited to those specific states.
    if req.secondary_pantry_items:
        expiry_parts = [f"{name} ({state})" for name, state in req.secondary_pantry_items.items()]
        parts.append(f"Use soon: {', '.join(expiry_parts)}")
    elif req.expiry_first:
        parts.append("Prefer: recipes that use expiring items first")

    return ". ".join(parts) + "." if parts else "Recipe."


# ── Candidate builder ─────────────────────────────────────────────────────────

def build_candidate_string(suggestion: RecipeSuggestion) -> str:
    """Build a candidate string for a single recipe suggestion.

    Format: "{title}. Ingredients: {comma-joined ingredients}"
    Matched ingredients appear before missing ones.
    Directions excluded to stay within BGE's 512-token window.
    """
    ingredients = suggestion.matched_ingredients + suggestion.missing_ingredients
    if not ingredients:
        return suggestion.title
    return f"{suggestion.title}. Ingredients: {', '.join(ingredients)}"


# ── Input assembler ───────────────────────────────────────────────────────────

def build_reranker_input(
    req: RecipeRequest,
    suggestions: list[RecipeSuggestion],
) -> RerankerInput:
    """Assemble query and candidate strings for the reranker."""
    query = build_query(req)
    candidates: list[str] = []
    ids: list[int] = []
    for s in suggestions:
        candidates.append(build_candidate_string(s))
        ids.append(s.id)
    return RerankerInput(query=query, candidates=candidates, suggestion_ids=ids)


# ── cf-core seam (isolated for monkeypatching in tests) ──────────────────────

def _do_rerank(query: str, candidates: list[str], top_n: int = 0):
    """Thin wrapper around cf-core rerank(). Extracted so tests can patch it."""
    from circuitforge_core.reranker import rerank
    return rerank(query, candidates, top_n=top_n)


# ── Public entry point ────────────────────────────────────────────────────────

def rerank_suggestions(
    req: RecipeRequest,
    suggestions: list[RecipeSuggestion],
) -> list[RecipeSuggestion] | None:
    """Rerank suggestions using the cf-core cross-encoder.

    Returns a reordered list with rerank_score populated, or None when:
    - Tier is not paid+ (free tier keeps overlap sort)
    - Fewer than _MIN_CANDIDATES suggestions (not worth the overhead)
    - Any exception is raised (graceful fallback to existing sort)

    The caller should treat None as "keep existing sort order".
    Original suggestions are never mutated.
    """
    if req.tier not in _RERANKER_TIERS:
        return None

    if len(suggestions) < _MIN_CANDIDATES:
        return None

    try:
        rinput = build_reranker_input(req, suggestions)
        results = _do_rerank(rinput.query, rinput.candidates, top_n=0)

        # Map reranked results back to RecipeSuggestion objects using the
        # candidate string as key (build_candidate_string is deterministic).
        candidate_map: dict[str, RecipeSuggestion] = {
            build_candidate_string(s): s for s in suggestions
        }

        reranked: list[RecipeSuggestion] = []
        for rr in results:
            suggestion = candidate_map.get(rr.candidate)
            if suggestion is not None:
                reranked.append(suggestion.model_copy(
                    update={"rerank_score": round(float(rr.score), 4)}
                ))

        if len(reranked) < len(suggestions):
            log.warning(
                "Reranker lost %d/%d suggestions during mapping, falling back",
                len(suggestions) - len(reranked),
                len(suggestions),
            )
            return None

        return reranked

    except Exception:
        log.exception("Reranker failed, falling back to overlap sort")
        return None
