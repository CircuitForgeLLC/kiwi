"""LLM-driven recipe generator for Levels 3 and 4."""
from __future__ import annotations

import logging
import os
from contextlib import nullcontext
from typing import TYPE_CHECKING

from openai import OpenAI

if TYPE_CHECKING:
    from app.db.store import Store

from app.models.schemas.recipe import RecipeRequest, RecipeResult, RecipeSuggestion
from app.services.recipe.element_classifier import IngredientProfile
from app.services.recipe.style_adapter import StyleAdapter

logger = logging.getLogger(__name__)


def _filter_allergies(pantry_items: list[str], allergies: list[str]) -> list[str]:
    """Return pantry items with allergy matches removed (bidirectional substring)."""
    if not allergies:
        return list(pantry_items)
    return [
        item for item in pantry_items
        if not any(
            allergy.lower() in item.lower() or item.lower() in allergy.lower()
            for allergy in allergies
        )
    ]


class LLMRecipeGenerator:
    def __init__(self, store: "Store") -> None:
        self._store = store
        self._style_adapter = StyleAdapter()

    def build_level3_prompt(
        self,
        req: RecipeRequest,
        profiles: list[IngredientProfile],
        gaps: list[str],
    ) -> str:
        """Build a structured element-scaffold prompt for Level 3."""
        allergy_list = req.allergies
        safe_pantry = _filter_allergies(req.pantry_items, allergy_list)

        covered_elements: list[str] = []
        for profile in profiles:
            for element in profile.elements:
                if element not in covered_elements:
                    covered_elements.append(element)

        lines: list[str] = [
            "You are a creative chef. Generate a recipe using the ingredients below.",
            "",
            f"Pantry items: {', '.join(safe_pantry)}",
        ]

        if req.constraints:
            lines.append(f"Dietary constraints: {', '.join(req.constraints)}")

        if allergy_list:
            lines.append(f"IMPORTANT — must NOT contain: {', '.join(allergy_list)}")

        lines.append("")
        lines.append(f"Covered culinary elements: {', '.join(covered_elements) or 'none'}")

        if gaps:
            lines.append(
                f"Missing elements to address: {', '.join(gaps)}. "
                "Incorporate ingredients or techniques to fill these gaps."
            )

        if req.style_id:
            template = self._style_adapter.get(req.style_id)
            if template:
                lines.append(f"Cuisine style: {template.name}")
                if template.aromatics:
                    lines.append(f"Preferred aromatics: {', '.join(template.aromatics[:4])}")

        lines += [
            "",
            "Reply in this format:",
            "Title: <recipe name>",
            "Ingredients: <comma-separated list>",
            "Directions: <numbered steps>",
            "Notes: <optional tips>",
        ]

        return "\n".join(lines)

    def build_level4_prompt(
        self,
        req: RecipeRequest,
    ) -> str:
        """Build a minimal wildcard prompt for Level 4."""
        allergy_list = req.allergies
        safe_pantry = _filter_allergies(req.pantry_items, allergy_list)

        lines: list[str] = [
            "Surprise me with a creative, unexpected recipe.",
            f"Ingredients available: {', '.join(safe_pantry)}",
        ]

        if req.constraints:
            lines.append(f"Constraints: {', '.join(req.constraints)}")

        if allergy_list:
            lines.append(f"Must NOT contain: {', '.join(allergy_list)}")

        lines += [
            "Treat any mystery ingredient as a wildcard — use your imagination.",
            "Title: <name> | Ingredients: <list> | Directions: <steps>",
        ]

        return "\n".join(lines)

    _MODEL_CANDIDATES: list[str] = ["Ouro-2.6B-Thinking", "Ouro-1.4B"]

    def _get_llm_context(self):
        """Return a sync context manager that yields an Allocation or None.

        When CF_ORCH_URL is set, uses CFOrchClient to acquire a vLLM allocation
        (which handles service lifecycle and VRAM). Falls back to nullcontext(None)
        when the env var is absent or CFOrchClient raises on construction.
        """
        cf_orch_url = os.environ.get("CF_ORCH_URL")
        if cf_orch_url:
            try:
                from circuitforge_core.resources import CFOrchClient
                client = CFOrchClient(cf_orch_url)
                return client.allocate(
                    service="vllm",
                    model_candidates=self._MODEL_CANDIDATES,
                    ttl_s=300.0,
                    caller="kiwi-recipe",
                )
            except Exception as exc:
                logger.debug("CFOrchClient init failed, falling back to direct URL: %s", exc)
        return nullcontext(None)

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM, using CFOrchClient allocation when CF_ORCH_URL is set.

        With CF_ORCH_URL set: acquires a vLLM allocation via CFOrchClient and
        calls the OpenAI-compatible API directly against the allocated service URL.
        Without CF_ORCH_URL: falls back to LLMRouter using its configured backends.
        """
        try:
            with self._get_llm_context() as alloc:
                if alloc is not None:
                    base_url = alloc.url.rstrip("/") + "/v1"
                    client = OpenAI(base_url=base_url, api_key="any")
                    model = alloc.model or "__auto__"
                    if model == "__auto__":
                        model = client.models.list().data[0].id
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return resp.choices[0].message.content or ""
                else:
                    from circuitforge_core.llm.router import LLMRouter
                    router = LLMRouter()
                    return router.complete(prompt)
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return ""

    def _parse_response(self, response: str) -> dict[str, str | list[str]]:
        """Parse LLM response text into structured recipe fields."""
        result: dict[str, str | list[str]] = {
            "title": "",
            "ingredients": [],
            "directions": "",
            "notes": "",
        }

        current_key: str | None = None
        buffer: list[str] = []

        def _flush(key: str | None, buf: list[str]) -> None:
            if key is None or not buf:
                return
            text = " ".join(buf).strip()
            if key == "ingredients":
                result["ingredients"] = [i.strip() for i in text.split(",") if i.strip()]
            else:
                result[key] = text

        for line in response.splitlines():
            lower = line.lower().strip()
            if lower.startswith("title:"):
                _flush(current_key, buffer)
                current_key, buffer = "title", [line.split(":", 1)[1].strip()]
            elif lower.startswith("ingredients:"):
                _flush(current_key, buffer)
                current_key, buffer = "ingredients", [line.split(":", 1)[1].strip()]
            elif lower.startswith("directions:"):
                _flush(current_key, buffer)
                current_key, buffer = "directions", [line.split(":", 1)[1].strip()]
            elif lower.startswith("notes:"):
                _flush(current_key, buffer)
                current_key, buffer = "notes", [line.split(":", 1)[1].strip()]
            elif current_key and line.strip():
                buffer.append(line.strip())

        _flush(current_key, buffer)
        return result

    def generate(
        self,
        req: RecipeRequest,
        profiles: list[IngredientProfile],
        gaps: list[str],
    ) -> RecipeResult:
        """Generate a recipe via LLM and return a RecipeResult."""
        if req.level == 4:
            prompt = self.build_level4_prompt(req)
        else:
            prompt = self.build_level3_prompt(req, profiles, gaps)

        response = self._call_llm(prompt)

        if not response:
            return RecipeResult(suggestions=[], element_gaps=gaps)

        parsed = self._parse_response(response)

        raw_directions = parsed.get("directions", "")
        directions_list: list[str] = (
            [s.strip() for s in raw_directions.split(".") if s.strip()]
            if isinstance(raw_directions, str)
            else list(raw_directions)
        )
        raw_notes = parsed.get("notes", "")
        notes_str: str = raw_notes if isinstance(raw_notes, str) else ""

        all_ingredients: list[str] = list(parsed.get("ingredients", []))
        pantry_set = {item.lower() for item in (req.pantry_items or [])}
        missing = [i for i in all_ingredients if i.lower() not in pantry_set]

        suggestion = RecipeSuggestion(
            id=0,
            title=parsed.get("title") or "LLM Recipe",
            match_count=len(req.pantry_items),
            element_coverage={},
            missing_ingredients=missing,
            directions=directions_list,
            notes=notes_str,
            level=req.level,
            is_wildcard=(req.level == 4),
        )

        return RecipeResult(
            suggestions=[suggestion],
            element_gaps=gaps,
        )
