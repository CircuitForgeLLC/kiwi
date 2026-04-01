"""LLM-driven recipe generator for Levels 3 and 4."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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

    def _acquire_vram_lease(self) -> str | None:
        """Request a VRAM lease from the CF-core coordinator. Best-effort — returns None if unavailable."""
        try:
            import httpx
            from app.core.config import settings
            from app.tasks.runner import VRAM_BUDGETS

            budget_mb = int(VRAM_BUDGETS.get("recipe_llm", 4.0) * 1024)
            coordinator = settings.COORDINATOR_URL

            nodes_resp = httpx.get(f"{coordinator}/api/nodes", timeout=2.0)
            if nodes_resp.status_code != 200:
                return None
            nodes = nodes_resp.json().get("nodes", [])
            if not nodes:
                return None

            best_node = best_gpu = best_free = None
            for node in nodes:
                for gpu in node.get("gpus", []):
                    free = gpu.get("vram_free_mb", 0)
                    if best_free is None or free > best_free:
                        best_node = node["node_id"]
                        best_gpu = gpu["gpu_id"]
                        best_free = free
            if best_node is None:
                return None

            lease_resp = httpx.post(
                f"{coordinator}/api/leases",
                json={
                    "node_id": best_node,
                    "gpu_id": best_gpu,
                    "mb": budget_mb,
                    "service": "kiwi",
                    "priority": 5,
                },
                timeout=3.0,
            )
            if lease_resp.status_code == 200:
                lease_id = lease_resp.json()["lease"]["lease_id"]
                logger.debug("Acquired VRAM lease %s for recipe_llm (%d MB)", lease_id, budget_mb)
                return lease_id
        except Exception as exc:
            logger.debug("VRAM lease acquire failed (non-fatal): %s", exc)
        return None

    def _release_vram_lease(self, lease_id: str) -> None:
        """Release a VRAM lease. Best-effort."""
        try:
            import httpx
            from app.core.config import settings
            httpx.delete(f"{settings.COORDINATOR_URL}/api/leases/{lease_id}", timeout=3.0)
            logger.debug("Released VRAM lease %s", lease_id)
        except Exception as exc:
            logger.debug("VRAM lease release failed (non-fatal): %s", exc)

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM router with a VRAM lease held for the duration."""
        lease_id = self._acquire_vram_lease()
        try:
            from circuitforge_core.llm.router import LLMRouter
            router = LLMRouter()
            return router.complete(prompt)
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return ""
        finally:
            if lease_id:
                self._release_vram_lease(lease_id)

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

        suggestion = RecipeSuggestion(
            id=0,
            title=parsed.get("title") or "LLM Recipe",
            match_count=len(req.pantry_items),
            element_coverage={},
            missing_ingredients=list(parsed.get("ingredients", [])),
            directions=directions_list,
            notes=notes_str,
            level=req.level,
            is_wildcard=(req.level == 4),
        )

        return RecipeResult(
            suggestions=[suggestion],
            element_gaps=gaps,
        )
