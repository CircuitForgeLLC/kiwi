"""Magpie data-flywheel hook.

Fires anonymized recipe-signal events to the Magpie ingest endpoint when a
user saves or rates a recipe.  This is the Kiwi side of the flywheel — Magpie
does not have a receiver endpoint yet, so the hook stubs out gracefully: if
``MAGPIE_INGEST_URL`` is unset, or the request fails for any reason, it logs
at DEBUG level and returns without raising.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_INGEST_PATH = "/api/v1/ingest/recipe-signal"


async def fire_recipe_signal(
    db_path: Path,
    recipe_id: int,
    rating: int | None,
    style_tags: list[str],
) -> None:
    """Post an anonymized recipe signal to Magpie if the user has opted in.

    Args:
        db_path:    Path to the user's SQLite database.
        recipe_id:  Internal Kiwi recipe ID being rated/saved.
        rating:     Star rating (0–5) or None if not yet rated.
        style_tags: Style tags applied to the saved recipe.
    """
    from app.core.config import settings

    if not settings.MAGPIE_INGEST_URL:
        return

    # Check per-user opt-in via a short-lived Store (own connection, own thread
    # context is fine — this runs in the async event loop as a background task
    # so we open and close the connection immediately).
    from app.db.store import Store

    try:
        store = Store(db_path)
        try:
            opt_in = store.get_setting("magpie_opt_in")
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001
        logger.debug("magpie_hook: could not read magpie_opt_in setting: %s", exc)
        return

    if opt_in != "true":
        return

    # Fetch the recipe to get its external_id (source URL slug / corpus key).
    try:
        store = Store(db_path)
        try:
            recipe = store.get_recipe(recipe_id)
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001
        logger.debug("magpie_hook: could not fetch recipe %d: %s", recipe_id, exc)
        return

    if recipe is None:
        logger.debug("magpie_hook: recipe %d not found, skipping", recipe_id)
        return

    external_id: str | None = recipe.get("external_id") if isinstance(recipe, dict) else getattr(recipe, "external_id", None)
    if not external_id:
        # Corpus recipe not yet enriched with a source identifier — skip quietly.
        logger.debug("magpie_hook: recipe %d has no external_id, skipping", recipe_id)
        return

    payload = {
        "product": "kiwi",
        "signal": "recipe_rating",
        "external_id": external_id,
        "rating": rating,
        "style_tags": style_tags,
    }

    url = settings.MAGPIE_INGEST_URL.rstrip("/") + _INGEST_PATH

    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(url, json=payload)
            logger.debug(
                "magpie_hook: POST %s → %d", url, response.status_code
            )
    except Exception as exc:  # noqa: BLE001
        # Magpie may not have a receiver yet — log and swallow.
        logger.debug("magpie_hook: ingest request failed (stub): %s", exc)
