"""Recipe suggestion and browser endpoints."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cloud_session import CloudUser, _auth_label, get_session

log = logging.getLogger(__name__)
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.recipe import (
    AssemblyTemplateOut,
    BuildRequest,
    RecipeJobStatus,
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
    category_has_subcategories,
    get_category_names,
    get_domain_labels,
    get_keywords_for_category,
    get_keywords_for_subcategory,
    get_subcategory_names,
)
from app.services.recipe.recipe_engine import RecipeEngine
from app.services.heimdall_orch import check_orch_budget
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


async def _enqueue_recipe_job(session: CloudUser, req: RecipeRequest):
    """Queue an async recipe_llm job and return 202 with job_id.

    Falls back to synchronous generation in CLOUD_MODE (scheduler polls only
    the shared settings DB, not per-user DBs — see snipe#45 / kiwi backlog).
    """
    import json
    import uuid
    from fastapi.responses import JSONResponse
    from app.cloud_session import CLOUD_MODE
    from app.tasks.runner import insert_task

    if CLOUD_MODE:
        log.warning("recipe_llm async jobs not supported in CLOUD_MODE — falling back to sync")
        result = await asyncio.to_thread(_suggest_in_thread, session.db, req)
        return result

    job_id = f"rec_{uuid.uuid4().hex}"

    def _create(db_path: Path) -> int:
        store = Store(db_path)
        try:
            row = store.create_recipe_job(job_id, session.user_id, req.model_dump_json())
            return row["id"]
        finally:
            store.close()

    int_id = await asyncio.to_thread(_create, session.db)
    params_json = json.dumps({"job_id": job_id})
    task_id, is_new = insert_task(session.db, "recipe_llm", int_id, params=params_json)
    if is_new:
        from app.tasks.scheduler import get_scheduler
        get_scheduler(session.db).enqueue(task_id, "recipe_llm", int_id, params_json)

    return JSONResponse(content={"job_id": job_id, "status": "queued"}, status_code=202)


@router.post("/suggest")
async def suggest_recipes(
    req: RecipeRequest,
    async_mode: bool = Query(default=False, alias="async"),
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
):
    log.info("recipes auth=%s tier=%s level=%s", _auth_label(session.user_id), session.tier, req.level)
    # Inject session-authoritative tier/byok immediately — client-supplied values are ignored.
    # Also read stored unit_system preference; default to metric if not set.
    unit_system = store.get_setting("unit_system") or "metric"
    req = req.model_copy(update={"tier": session.tier, "has_byok": session.has_byok, "unit_system": unit_system})
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

    # Orch budget check for lifetime/founders keys — downgrade to L2 (local) if exhausted.
    # Subscription and local/BYOK users skip this check entirely.
    orch_fallback = False
    if (
        req.level in (3, 4)
        and session.license_key is not None
        and not session.has_byok
        and session.tier != "local"
    ):
        budget = check_orch_budget(session.license_key, "kiwi")
        if not budget.get("allowed", True):
            req = req.model_copy(update={"level": 2})
            orch_fallback = True

    if req.level in (3, 4) and async_mode:
        return await _enqueue_recipe_job(session, req)

    result = await asyncio.to_thread(_suggest_in_thread, session.db, req)
    if orch_fallback:
        result = result.model_copy(update={"orch_fallback": True})
    return result


@router.get("/jobs/{job_id}", response_model=RecipeJobStatus)
async def get_recipe_job_status(
    job_id: str,
    session: CloudUser = Depends(get_session),
) -> RecipeJobStatus:
    """Poll the status of an async recipe generation job.

    Returns 404 when job_id is unknown or belongs to a different user.
    On status='done' with suggestions=[], the LLM returned empty — client
    should show a 'no recipe generated, try again' message.
    """
    def _get(db_path: Path) -> dict | None:
        store = Store(db_path)
        try:
            return store.get_recipe_job(job_id, session.user_id)
        finally:
            store.close()

    row = await asyncio.to_thread(_get, session.db)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    result = None
    if row["status"] == "done" and row["result"]:
        result = RecipeResult.model_validate_json(row["result"])

    return RecipeJobStatus(
        job_id=row["job_id"],
        status=row["status"],
        result=result,
        error=row["error"],
    )


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

    cat_names = get_category_names(domain)
    keywords_by_category = {cat: get_keywords_for_category(domain, cat) for cat in cat_names}
    has_subs = {cat: category_has_subcategories(domain, cat) for cat in cat_names}

    def _get(db_path: Path) -> list[dict]:
        store = Store(db_path)
        try:
            return store.get_browser_categories(domain, keywords_by_category, has_subs)
        finally:
            store.close()

    return await asyncio.to_thread(_get, session.db)


@router.get("/browse/{domain}/{category}/subcategories")
async def list_browse_subcategories(
    domain: str,
    category: str,
    session: CloudUser = Depends(get_session),
) -> list[dict]:
    """Return [{subcategory, recipe_count}] for a category that supports subcategories."""
    if domain not in DOMAINS:
        raise HTTPException(status_code=404, detail=f"Unknown domain '{domain}'.")
    if not category_has_subcategories(domain, category):
        return []

    subcat_names = get_subcategory_names(domain, category)
    keywords_by_subcat = {
        sub: get_keywords_for_subcategory(domain, category, sub)
        for sub in subcat_names
    }

    def _get(db_path: Path) -> list[dict]:
        store = Store(db_path)
        try:
            return store.get_browser_subcategories(domain, keywords_by_subcat)
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
    subcategory: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    sort: Annotated[str, Query(pattern="^(default|alpha|alpha_desc|match)$")] = "default",
    session: CloudUser = Depends(get_session),
) -> dict:
    """Return a paginated list of recipes for a domain/category.

    Pass pantry_items as a comma-separated string to receive match_pct badges.
    Pass subcategory to narrow within a category that has subcategories.
    Pass q to filter by title substring. Pass sort for ordering (default/alpha/alpha_desc/match).
    sort=match orders by pantry coverage DESC; falls back to default when no pantry_items.
    """
    if domain not in DOMAINS:
        raise HTTPException(status_code=404, detail=f"Unknown domain '{domain}'.")

    if category == "_all":
        keywords = None  # unfiltered browse
    elif subcategory:
        keywords = get_keywords_for_subcategory(domain, category, subcategory)
        if not keywords:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown subcategory '{subcategory}' in '{category}'.",
            )
    else:
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
                q=q or None,
                sort=sort,
            )

            # Community tag fallback: if FTS returned nothing for a subcategory,
            # check whether accepted community tags exist for this location and
            # fetch those corpus recipes directly by ID.
            if result["total"] == 0 and subcategory and keywords:
                try:
                    from app.api.endpoints.community import _get_community_store
                    cs = _get_community_store()
                    if cs is not None:
                        community_ids = cs.get_accepted_recipe_ids_for_subcategory(
                            domain=domain,
                            category=category,
                            subcategory=subcategory,
                        )
                        if community_ids:
                            offset = (page - 1) * page_size
                            paged_ids = community_ids[offset: offset + page_size]
                            recipes = store.fetch_recipes_by_ids(paged_ids, pantry_list)
                            result = {
                                "recipes": recipes,
                                "total": len(community_ids),
                                "page": page,
                                "community_tagged": True,
                            }
                except Exception as exc:
                    logger.warning("community tag fallback failed: %s", exc)

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
