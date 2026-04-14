"""Recipe suggestion and browser endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cloud_session import CloudUser, get_session
from app.db.store import Store
from app.models.schemas.recipe import (
    AssemblyTemplateOut,
    BuildRequest,
    RecipeRequest,
    RecipeResult,
    RecipeSuggestion,
    RoleCandidatesResponse,
)
from app.services.recipe.assembly_recipes import (
    build_from_selection,
    get_role_candidates,
    get_templates_for_api,
)
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


@router.get("/templates", response_model=list[AssemblyTemplateOut])
async def list_assembly_templates() -> list[dict]:
    """Return all 13 assembly templates with ordered role sequences.

    Cache-friendly: static data, no per-user state.
    """
    return get_templates_for_api()


@router.get("/template-candidates", response_model=RoleCandidatesResponse)
async def get_template_role_candidates(
    template_id: str = Query(..., description="Template slug, e.g. 'burrito_taco'"),
    role: str = Query(..., description="Role display name, e.g. 'protein'"),
    prior_picks: str = Query(default="", description="Comma-separated prior selections"),
    session: CloudUser = Depends(get_session),
) -> dict:
    """Return pantry-matched candidates for one wizard step."""
    def _get(db_path: Path) -> dict:
        store = Store(db_path)
        try:
            items = store.list_inventory(status="available")
            pantry_set = {
                item["product_name"]
                for item in items
                if item.get("product_name")
            }
            pantry_list = list(pantry_set)
            prior = [p.strip() for p in prior_picks.split(",") if p.strip()]
            profile_index = store.get_element_profiles(pantry_list + prior)
            return get_role_candidates(
                template_slug=template_id,
                role_display=role,
                pantry_set=pantry_set,
                prior_picks=prior,
                profile_index=profile_index,
            )
        finally:
            store.close()

    return await asyncio.to_thread(_get, session.db)


@router.post("/build", response_model=RecipeSuggestion)
async def build_recipe(
    req: BuildRequest,
    session: CloudUser = Depends(get_session),
) -> RecipeSuggestion:
    """Build a recipe from explicit role selections."""
    def _build(db_path: Path) -> RecipeSuggestion | None:
        store = Store(db_path)
        try:
            items = store.list_inventory(status="available")
            pantry_set = {
                item["product_name"]
                for item in items
                if item.get("product_name")
            }
            suggestion = build_from_selection(
                template_slug=req.template_id,
                role_overrides=req.role_overrides,
                pantry_set=pantry_set,
            )
            if suggestion is None:
                return None
            # Persist to recipes table so the result can be saved/bookmarked.
            # external_id encodes template + selections for stable dedup.
            import hashlib as _hl, json as _js
            sel_hash = _hl.md5(
                _js.dumps(req.role_overrides, sort_keys=True).encode()
            ).hexdigest()[:8]
            external_id = f"assembly:{req.template_id}:{sel_hash}"
            real_id = store.upsert_built_recipe(
                external_id=external_id,
                title=suggestion.title,
                ingredients=suggestion.matched_ingredients,
                directions=suggestion.directions,
            )
            return suggestion.model_copy(update={"id": real_id})
        finally:
            store.close()

    result = await asyncio.to_thread(_build, session.db)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Template not found or required ingredient missing.",
        )
    return result


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
