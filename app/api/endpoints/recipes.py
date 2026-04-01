"""Recipe suggestion endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.cloud_session import CloudUser, get_session
from app.db.store import Store
from app.models.schemas.recipe import RecipeRequest, RecipeResult
from app.services.recipe.recipe_engine import RecipeEngine
from app.tiers import can_use

router = APIRouter()


def _suggest_in_thread(db_path: Path, req: RecipeRequest) -> RecipeResult:
    """Run recipe suggestion in a worker thread with its own Store connection.

    SQLite connections cannot be shared across threads. This function creates
    a fresh Store (and therefore a fresh sqlite3.Connection) in the same thread
    where it will be used, avoiding ProgrammingError: SQLite objects created in
    a thread can only be used in that same thread.
    """
    store = Store(db_path)
    try:
        return RecipeEngine(store).suggest(req)
    finally:
        store.close()


@router.post("/suggest", response_model=RecipeResult)
async def suggest_recipes(
    req: RecipeRequest,
    session: CloudUser = Depends(get_session),
) -> RecipeResult:
    # Inject session-authoritative tier/byok immediately — client-supplied values are ignored.
    req = req.model_copy(update={"tier": session.tier, "has_byok": session.has_byok})
    if req.level == 4 and not req.wildcard_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Level 4 (Wildcard) requires wildcard_confirmed=true.",
        )
    if req.level in (3, 4) and not can_use("recipe_suggestions", req.tier, req.has_byok):
        raise HTTPException(
            status_code=403,
            detail="LLM recipe levels require Paid tier or a configured LLM backend.",
        )
    if req.style_id and not can_use("style_picker", req.tier):
        raise HTTPException(status_code=403, detail="Style picker requires Paid tier.")
    return await asyncio.to_thread(_suggest_in_thread, session.db, req)


@router.get("/{recipe_id}")
async def get_recipe(recipe_id: int, session: CloudUser = Depends(get_session)) -> dict:
    def _get(db_path: Path, rid: int) -> dict | None:
        store = Store(db_path)
        try:
            return store.get_recipe(rid)
        finally:
            store.close()

    recipe = await asyncio.to_thread(_get, session.db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe
