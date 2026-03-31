"""Recipe suggestion endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.cloud_session import CloudUser, get_session
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.recipe import RecipeRequest, RecipeResult
from app.services.recipe.recipe_engine import RecipeEngine
from app.tiers import can_use

router = APIRouter()


@router.post("/suggest", response_model=RecipeResult)
async def suggest_recipes(
    req: RecipeRequest,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
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
    engine = RecipeEngine(store)
    return await asyncio.to_thread(engine.suggest, req)


@router.get("/{recipe_id}")
async def get_recipe(recipe_id: int, store: Store = Depends(get_store)) -> dict:
    recipe = await asyncio.to_thread(store.get_recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe
