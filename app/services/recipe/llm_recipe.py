"""LLM-driven recipe generator for Levels 3 and 4."""
from __future__ import annotations

import logging
import os
import re
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
            "IMPORTANT: When you use a pantry item, list it in Ingredients using its exact name from the pantry list. Do not add adjectives, quantities, or cooking states (e.g. use 'butter', not 'unsalted butter' or '2 tbsp butter').",
            "IMPORTANT: Only use pantry items that make culinary sense for the dish. Do NOT force flavoured/sweetened items (vanilla yoghurt, fruit yoghurt, jam, dessert sauces, flavoured syrups) into savoury dishes. Plain yoghurt, plain cream, and plain dairy are fine in savoury cooking.",
            "IMPORTANT: Do not default to the same ingredient repeatedly across dishes. If a pantry item does not genuinely improve this specific dish, leave it out.",
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
            "Reply using EXACTLY this plain-text format — no markdown, no bold, no extra commentary:",
            "Title: <name of the dish>",
            "Ingredients: <comma-separated list>",
            "Directions:",
            "1. <first step>",
            "2. <second step>",
            "3. <continue for each step>",
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
            "Only use ingredients that make culinary sense together. Do not force flavoured/sweetened items (vanilla yoghurt, flavoured syrups, jam) into savoury dishes.",
            f"Ingredients available: {', '.join(safe_pantry)}",
        ]

        if req.constraints:
            lines.append(f"Constraints: {', '.join(req.constraints)}")

        if allergy_list:
            lines.append(f"Must NOT contain: {', '.join(allergy_list)}")

        lines += [
            "Treat any mystery ingredient as a wildcard — use your imagination.",
            "Reply using EXACTLY this plain-text format — no markdown, no bold:",
            "Title: <name of the dish>",
            "Ingredients: <comma-separated list>",
            "Directions:",
            "1. <first step>",
            "2. <second step>",
            "Notes: <optional tips>",
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
                from circuitforge_orch.client import CFOrchClient
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
        Allocation failure falls through to LLMRouter rather than silently returning "".
        Without CF_ORCH_URL: uses LLMRouter directly.
        """
        ctx = self._get_llm_context()
        alloc = None
        try:
            alloc = ctx.__enter__()
        except Exception as exc:
            logger.debug("cf-orch allocation failed, falling back to LLMRouter: %s", exc)
            ctx = None  # __enter__ raised — do not call __exit__

        try:
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
                return LLMRouter().complete(prompt)
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return ""
        finally:
            if ctx is not None:
                try:
                    ctx.__exit__(None, None, None)
                except Exception:
                    pass

    # Strips markdown bold/italic markers so "**Directions:**" parses like "Directions:"
    _MD_BOLD = re.compile(r"\*{1,2}([^*]+)\*{1,2}")

    def _strip_md(self, text: str) -> str:
        return self._MD_BOLD.sub(r"\1", text).strip()

    def _parse_response(self, response: str) -> dict[str, str | list[str]]:
        """Parse LLM response text into structured recipe fields.

        Handles both plain-text and markdown-formatted responses. Directions are
        preserved as newline-separated text so the caller can split on step numbers.
        """
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
            if key == "directions":
                result["directions"] = "\n".join(buf)
            elif key == "ingredients":
                text = " ".join(buf)
                result["ingredients"] = [i.strip() for i in text.split(",") if i.strip()]
            else:
                result[key] = " ".join(buf).strip()

        for raw_line in response.splitlines():
            line = self._strip_md(raw_line)
            lower = line.lower()
            if lower.startswith("title:"):
                _flush(current_key, buffer)
                current_key, buffer = "title", [line.split(":", 1)[1].strip()]
            elif lower.startswith("ingredients:"):
                _flush(current_key, buffer)
                current_key, buffer = "ingredients", [line.split(":", 1)[1].strip()]
            elif lower.startswith("directions:"):
                _flush(current_key, buffer)
                rest = line.split(":", 1)[1].strip()
                current_key, buffer = "directions", ([rest] if rest else [])
            elif lower.startswith("notes:"):
                _flush(current_key, buffer)
                current_key, buffer = "notes", [line.split(":", 1)[1].strip()]
            elif current_key and line.strip():
                buffer.append(line.strip())
            elif current_key is None and line.strip() and ":" not in line:
                # Before any section header: a 2-10 word colon-free line is the dish name
                words = line.split()
                if 2 <= len(words) <= 10 and not result["title"]:
                    result["title"] = line.strip()

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
        if isinstance(raw_directions, str):
            # Split on newlines; strip leading step numbers ("1.", "2.", "- ", "* ")
            _step_prefix = re.compile(r"^\s*(?:\d+[.)]\s*|[-*]\s+)")
            directions_list = [
                _step_prefix.sub("", s).strip()
                for s in raw_directions.splitlines()
                if s.strip()
            ]
        else:
            directions_list = list(raw_directions)
        raw_notes = parsed.get("notes", "")
        notes_str: str = raw_notes if isinstance(raw_notes, str) else ""

        all_ingredients: list[str] = list(parsed.get("ingredients", []))
        pantry_set = {item.lower() for item in (req.pantry_items or [])}

        # Strip leading quantities/units (e.g. "2 cups rice" → "rice") before
        # checking against pantry, since LLMs return formatted ingredient strings.
        _qty_re = re.compile(
            r"^\s*[\d½¼¾⅓⅔]+[\s/\-]*"          # leading digits or fractions
            r"(?:cup|cups|tbsp|tsp|tablespoon|teaspoon|oz|lb|lbs|g|kg|"
            r"can|cans|clove|cloves|bunch|package|pkg|slice|slices|"
            r"piece|pieces|pinch|dash|handful|head|heads|large|small|medium"
            r")s?\b[,\s]*",
            re.IGNORECASE,
        )
        missing = []
        for ing in all_ingredients:
            bare = _qty_re.sub("", ing).strip().lower()
            if bare not in pantry_set and ing.lower() not in pantry_set:
                missing.append(bare or ing)

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
