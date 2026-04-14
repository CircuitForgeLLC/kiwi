"""Kiwi — /api/v1/imitate/samples endpoint for Avocet Imitate tab.

Returns the actual assembled prompt Kiwi sends to its LLM for recipe generation,
including the full pantry context (expiry-first ordering), dietary constraints
(from user_settings if present), and the Level 3 format instructions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.cloud_session import get_session, CloudUser
from app.db.store import Store

router = APIRouter()

_LEVEL3_FORMAT = [
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

_LEVEL4_FORMAT = [
    "",
    "Reply using EXACTLY this plain-text format — no markdown, no bold:",
    "Title: <name of the dish>",
    "Ingredients: <comma-separated list>",
    "Directions:",
    "1. <first step>",
    "2. <second step>",
    "Notes: <optional tips>",
]


def _read_user_settings(store: Store) -> dict:
    """Read all key/value pairs from user_settings table."""
    try:
        rows = store.conn.execute("SELECT key, value FROM user_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def _build_recipe_prompt(
    pantry_names: list[str],
    expiring_names: list[str],
    constraints: list[str],
    allergies: list[str],
    level: int = 3,
) -> str:
    """Assemble the recipe generation prompt matching Kiwi's Level 3/4 format."""
    # Expiring items first, then remaining pantry items (deduped)
    expiring_set = set(expiring_names)
    ordered = list(expiring_names) + [n for n in pantry_names if n not in expiring_set]

    if not ordered:
        ordered = pantry_names

    if level == 4:
        lines = [
            "Surprise me with a creative, unexpected recipe.",
            "Only use ingredients that make culinary sense together. "
            "Do not force flavoured/sweetened items (vanilla yoghurt, flavoured syrups, jam) into savoury dishes.",
            f"Ingredients available: {', '.join(ordered)}",
        ]
        if constraints:
            lines.append(f"Constraints: {', '.join(constraints)}")
        if allergies:
            lines.append(f"Must NOT contain: {', '.join(allergies)}")
        lines.append("Treat any mystery ingredient as a wildcard — use your imagination.")
        lines += _LEVEL4_FORMAT
    else:
        lines = [
            "You are a creative chef. Generate a recipe using the ingredients below.",
            "IMPORTANT: When you use a pantry item, list it in Ingredients using its exact name "
            "from the pantry list. Do not add adjectives, quantities, or cooking states "
            "(e.g. use 'butter', not 'unsalted butter' or '2 tbsp butter').",
            "IMPORTANT: Only use pantry items that make culinary sense for the dish. "
            "Do NOT force flavoured/sweetened items (vanilla yoghurt, fruit yoghurt, jam, "
            "dessert sauces, flavoured syrups) into savoury dishes.",
            "IMPORTANT: Do not default to the same ingredient repeatedly across dishes. "
            "If a pantry item does not genuinely improve this specific dish, leave it out.",
            "",
            f"Pantry items: {', '.join(ordered)}",
        ]
        if expiring_names:
            lines.append(
                f"Priority — use these soon (expiring): {', '.join(expiring_names)}"
            )
        if constraints:
            lines.append(f"Dietary constraints: {', '.join(constraints)}")
        if allergies:
            lines.append(f"IMPORTANT — must NOT contain: {', '.join(allergies)}")
        lines += _LEVEL3_FORMAT

    return "\n".join(lines)


@router.get("/samples")
async def imitate_samples(
    limit: int = 5,
    level: int = 3,
    session: CloudUser = Depends(get_session),
):
    """Return assembled recipe generation prompts for Avocet's Imitate tab.

    Each sample includes:
      system_prompt  empty (Kiwi uses no system context)
      input_text     full Level 3/4 prompt with pantry items, expiring items,
                     dietary constraints, and format instructions
      output_text    empty (no prior LLM output stored per-request)

    level: 3 (structured with element biasing context) or 4 (wildcard creative)
    limit: max number of distinct prompt variants to return (varies by pantry state)
    """
    limit = max(1, min(limit, 10))
    store = Store(session.db)

    # Full pantry for context
    all_items = store.list_inventory()
    pantry_names = [r["product_name"] for r in all_items if r.get("product_name")]

    # Expiring items as priority ingredients
    expiring = store.expiring_soon(days=14)
    expiring_names = [r["product_name"] for r in expiring if r.get("product_name")]

    # Dietary constraints from user_settings (keys: constraints, allergies)
    settings = _read_user_settings(store)
    import json as _json
    try:
        constraints = _json.loads(settings.get("dietary_constraints", "[]")) or []
    except Exception:
        constraints = []
    try:
        allergies = _json.loads(settings.get("dietary_allergies", "[]")) or []
    except Exception:
        allergies = []

    if not pantry_names:
        return {"samples": [], "total": 0, "type": f"recipe_level{level}"}

    # Build prompt variants: one per expiring item as the "anchor" ingredient,
    # plus one general pantry prompt. Cap at limit.
    samples = []
    seen_anchors: set[str] = set()

    for item in (expiring[:limit - 1] if expiring else []):
        anchor = item.get("product_name", "")
        if not anchor or anchor in seen_anchors:
            continue
        seen_anchors.add(anchor)

        # Put this item first in the list for the prompt
        ordered_expiring = [anchor] + [n for n in expiring_names if n != anchor]
        prompt = _build_recipe_prompt(pantry_names, ordered_expiring, constraints, allergies, level)

        samples.append({
            "id": item.get("id", 0),
            "anchor_item": anchor,
            "expiring_count": len(expiring_names),
            "pantry_count": len(pantry_names),
            "system_prompt": "",
            "input_text": prompt,
            "output_text": "",
        })

    # One general prompt using all expiring as priority
    if len(samples) < limit:
        prompt = _build_recipe_prompt(pantry_names, expiring_names, constraints, allergies, level)
        samples.append({
            "id": 0,
            "anchor_item": "full pantry",
            "expiring_count": len(expiring_names),
            "pantry_count": len(pantry_names),
            "system_prompt": "",
            "input_text": prompt,
            "output_text": "",
        })

    return {"samples": samples, "total": len(samples), "type": f"recipe_level{level}"}
