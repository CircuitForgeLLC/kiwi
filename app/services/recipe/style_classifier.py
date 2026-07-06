# app/services/recipe/style_classifier.py
# BSL 1.1 — LLM feature
"""LLM style-tag classifier for saved recipes.

Reads recipe title, ingredients, and directions and suggests 3–5 style tags
from the curated vocabulary shared with SaveRecipeModal.vue.

Cloud (CF_ORCH_URL set): allocates a cf-text service via cf-orch (2 GB VRAM).
Local: falls back to LLMRouter (ollama / vllm / openai-compat).
"""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import nullcontext
from typing import Any

logger = logging.getLogger(__name__)

_SERVICE_TYPE = "cf-text"
_TTL_S = 60.0
_CALLER = "kiwi-style-classify"

# Canonical vocabulary — must stay in sync with SUGGESTED_TAGS in SaveRecipeModal.vue.
STYLE_TAG_VOCAB: frozenset[str] = frozenset({
    "comforting", "light", "spicy", "umami", "sweet", "savory", "rich",
    "crispy", "creamy", "hearty", "quick", "hands-off", "meal-prep-friendly",
    "fancy", "one-pot",
})

_SYSTEM_PROMPT = """\
You are a culinary tagger. Given a recipe, suggest 3 to 5 style tags that best \
describe its character. You MUST only use tags from this list:

comforting, light, spicy, umami, sweet, savory, rich, crispy, creamy, hearty, \
quick, hands-off, meal-prep-friendly, fancy, one-pot

Return ONLY a JSON array of strings, no explanation. Example:
["comforting", "hearty", "one-pot"]
"""


def _build_router():
    """Return (router, context_manager) for style classify tasks.

    Tries cf-orch cf-text allocation first; falls back to LLMRouter.
    Returns (None, nullcontext) if no backend is available.
    """
    cf_orch_url = os.environ.get("CF_ORCH_URL")
    if cf_orch_url:
        try:
            from circuitforge_orch.client import CFOrchClient

            from app.services.meal_plan.llm_router import _OrchTextRouter  # reuse adapter
            client = CFOrchClient(cf_orch_url)
            ctx = client.allocate(service=_SERVICE_TYPE, ttl_s=_TTL_S, caller=_CALLER)
            alloc = ctx.__enter__()
            if alloc is not None:
                return _OrchTextRouter(alloc.url), ctx
        except Exception as exc:
            logger.debug("cf-orch allocation failed for style classify, falling back: %s", exc)

    try:
        from circuitforge_core.llm.router import LLMRouter
        return LLMRouter(), nullcontext(None)
    except FileNotFoundError:
        logger.debug("LLMRouter: no llm.yaml — style classifier LLM disabled")
        return None, nullcontext(None)
    except Exception as exc:
        logger.debug("LLMRouter init failed: %s", exc)
        return None, nullcontext(None)


def _parse_tags(raw: str) -> list[str]:
    """Extract valid vocab tags from raw LLM output.

    Tries JSON parse first; falls back to extracting any vocab word present
    in the response text so minor formatting deviations still work.
    """
    # Strip markdown fences
    raw = re.sub(r"```[a-z]*", "", raw).strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [t for t in parsed if isinstance(t, str) and t in STYLE_TAG_VOCAB][:5]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: scan for vocab words
    found = [t for t in STYLE_TAG_VOCAB if re.search(rf"\b{re.escape(t)}\b", raw, re.IGNORECASE)]
    return sorted(found, key=lambda t: raw.lower().index(t.lower()))[:5]


def classify_style(recipe: dict[str, Any]) -> list[str]:
    """Return 3–5 suggested style tags for *recipe*.

    *recipe* is a Store row dict with at least ``title``, ``ingredient_names``
    (list[str]), and ``directions`` (list[str] or str).

    Returns an empty list if no LLM backend is available.
    """
    router, ctx = _build_router()
    if router is None:
        return []

    title = recipe.get("title") or "Unknown"
    ingredients = recipe.get("ingredient_names") or []
    if isinstance(ingredients, str):
        try:
            ingredients = json.loads(ingredients)
        except Exception:
            ingredients = [ingredients]

    directions = recipe.get("directions") or []
    if isinstance(directions, str):
        try:
            directions = json.loads(directions)
        except Exception:
            directions = [directions]

    user_prompt = (
        f"Recipe: {title}\n"
        f"Ingredients: {', '.join(str(i) for i in ingredients[:20])}\n"
        f"Steps: {' '.join(str(d) for d in directions[:8])[:600]}"
    )

    try:
        with ctx:
            raw = router.complete(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=64,
                temperature=0.3,
            )
        return _parse_tags(raw)
    except Exception as exc:
        logger.warning("Style classifier LLM call failed: %s", exc)
        return []
