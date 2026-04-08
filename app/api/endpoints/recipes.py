"""Recipe suggestion and browser endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cloud_session import CloudUser, get_session
from app.db.store import Store
from app.models.schemas.recipe import RecipeRequest, RecipeResult
from app.services.recipe.browser_domains import (
    DOMAINS,
    get_category_names,
    get_domain_labels,
    get_keywords_for_category,
)
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


@router.get("/browse/domains")
async def list_browse_domains(
    session: CloudUser = Depends(get_session),
) -> list[dict]:
    """Return available domain schemas for the recipe browser."""
    return get_domain_labels()


@router.get("/browse/{domain}")
async def list_browse_categories(
    domain: str,
    session: CloudUser = Depends(get_session),
) -> list[dict]:
    """Return categories with recipe counts for a given domain."""
    if domain not in DOMAINS:
        raise HTTPException(status_code=404, detail=f"Unknown domain '{domain}'.")

    keywords_by_category = {
        cat: get_keywords_for_category(domain, cat)
        for cat in get_category_names(domain)
    }

    def _get(db_path: Path) -> list[dict]:
        store = Store(db_path)
        try:
            return store.get_browser_categories(domain, keywords_by_category)
        finally:
            store.close()

    return await asyncio.to_thread(_get, session.db)


@router.get("/browse/{domain}/{category}")
async def browse_recipes(
    domain: str,
    category: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    pantry_items: Annotated[str | None, Query()] = None,
    session: CloudUser = Depends(get_session),
) -> dict:
    """Return a paginated list of recipes for a domain/category.

    Pass pantry_items as a comma-separated string to receive match_pct
    badges on each result.
    """
    if domain not in DOMAINS:
        raise HTTPException(status_code=404, detail=f"Unknown domain '{domain}'.")

    keywords = get_keywords_for_category(domain, category)
    if not keywords:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown category '{category}' in domain '{domain}'.",
        )

    pantry_list = (
        [p.strip() for p in pantry_items.split(",") if p.strip()]
        if pantry_items
        else None
    )

    def _browse(db_path: Path) -> dict:
        store = Store(db_path)
        try:
            result = store.browse_recipes(
                keywords=keywords,
                page=page,
                page_size=page_size,
                pantry_items=pantry_list,
            )
            store.log_browser_telemetry(
                domain=domain,
                category=category,
                page=page,
                result_count=result["total"],
            )
            return result
        finally:
            store.close()

    return await asyncio.to_thread(_browse, session.db)


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
