"""Recipe suggestion and browser endpoints."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import json as _json_mod
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.cloud_session import CloudUser, _auth_label, get_session

log = logging.getLogger(__name__)
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.recipe import (
    AssemblyTemplateOut,
    BuildRequest,
    LeftoversResponse,
    RecipeJobStatus,
    RecipeRequest,
    RecipeResult,
    RecipeSuggestion,
    RoleCandidatesResponse,
    StreamTokenRequest,
    StreamTokenResponse,
)
from app.services.coordinator_proxy import CoordinatorError, coordinator_authorize
from app.api.endpoints.imitate import _build_recipe_prompt
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
from app.services.recipe.time_effort import parse_time_effort
from app.services.recipe.sensory import build_sensory_exclude
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


def _build_stream_prompt(db_path: Path, level: int) -> str:
    """Fetch pantry + user settings from DB and build the recipe prompt.

    Runs in a thread (called via asyncio.to_thread) so it can use sync Store.
    """
    import datetime

    store = Store(db_path)
    try:
        items = store.list_inventory(status="available")
        pantry_names = [i["product_name"] for i in items if i.get("product_name")]

        today = datetime.date.today()
        expiring_names = [
            i["product_name"]
            for i in items
            if i.get("product_name")
            and i.get("expiry_date")
            and (datetime.date.fromisoformat(i["expiry_date"]) - today).days <= 3
        ]

        settings: dict = {}
        try:
            rows = store.conn.execute("SELECT key, value FROM user_settings").fetchall()
            settings = {r["key"]: r["value"] for r in rows}
        except Exception:
            pass

        constraints_raw = settings.get("dietary_constraints", "")
        constraints = [c.strip() for c in constraints_raw.split(",") if c.strip()] if constraints_raw else []
        allergies_raw = settings.get("allergies", "")
        allergies = [a.strip() for a in allergies_raw.split(",") if a.strip()] if allergies_raw else []

        return _build_recipe_prompt(pantry_names, expiring_names, constraints, allergies, level)
    finally:
        store.close()


async def _stream_recipe_sse(db_path: Path, req: RecipeRequest):
    """Async generator that yields SSE events for a streaming recipe request.

    Phase 1 (thread): classify pantry items using a temporary Store.
    Phase 2 (async):  stream tokens from LLM via LLMRecipeGenerator.stream_generate().
    """
    def _prep(db_path: Path) -> tuple[list, list[str]]:
        from app.services.recipe.element_classifier import IngredientClassifier
        store = Store(db_path)
        try:
            classifier = IngredientClassifier(store)
            profiles = classifier.classify_batch(req.pantry_items)
            gaps = classifier.identify_gaps(profiles)
            return profiles, gaps
        finally:
            store.close()

    try:
        profiles, gaps = await asyncio.to_thread(_prep, db_path)
    except Exception as exc:
        yield f"data: {_json_mod.dumps({'error': str(exc)})}\n\n"
        return

    from app.services.recipe.llm_recipe import LLMRecipeGenerator
    gen = LLMRecipeGenerator(None)
    try:
        async for token in gen.stream_generate(req, profiles, gaps):
            yield f"data: {_json_mod.dumps({'chunk': token})}\n\n"
        yield f"data: {_json_mod.dumps({'done': True})}\n\n"
    except Exception as exc:
        yield f"data: {_json_mod.dumps({'error': str(exc)})}\n\n"


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
    stream: bool = Query(default=False),
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

    if stream and req.level in (3, 4):
        return StreamingResponse(
            _stream_recipe_sse(session.db, req),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if req.level in (3, 4) and async_mode:
        return await _enqueue_recipe_job(session, req)

    result = await asyncio.to_thread(_suggest_in_thread, session.db, req)
    if orch_fallback:
        result = result.model_copy(update={"orch_fallback": True})
    return result


@router.post("/stream-token", response_model=StreamTokenResponse)
async def get_stream_token(
    req: StreamTokenRequest,
    session: CloudUser = Depends(get_session),
) -> StreamTokenResponse:
    """Issue a one-time stream token for LLM recipe generation.

    Tier-gated (Paid or BYOK). Builds the prompt from pantry + user settings,
    then calls the cf-orch coordinator to obtain a stream URL. Returns
    immediately — the frontend opens EventSource to the stream URL directly.
    """
    if not can_use("recipe_suggestions", session.tier, session.has_byok):
        raise HTTPException(
            status_code=403,
            detail="Streaming recipe generation requires Paid tier or a configured LLM backend.",
        )
    if req.level == 4 and not req.wildcard_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Level 4 (Wildcard) streaming requires wildcard_confirmed=true.",
        )

    prompt = await asyncio.to_thread(_build_stream_prompt, session.db, req.level)

    try:
        result = await coordinator_authorize(prompt=prompt, caller="kiwi-recipe", ttl_s=300)
    except CoordinatorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return StreamTokenResponse(
        stream_url=result.stream_url,
        token=result.token,
        expires_in_s=result.expires_in_s,
    )


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
    required_ingredient: Annotated[str | None, Query(max_length=100)] = None,
    session: CloudUser = Depends(get_session),
) -> dict:
    """Return a paginated list of recipes for a domain/category.

    Pass pantry_items as a comma-separated string to receive match_pct badges.
    Pass subcategory to narrow within a category that has subcategories.
    Pass q to filter by title substring. Pass sort for ordering (default/alpha/alpha_desc/match).
    sort=match orders by pantry coverage DESC; falls back to default when no pantry_items.
    Pass required_ingredient to restrict results to recipes that must include that ingredient.
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
            # Load sensory preferences
            sensory_prefs_json = store.get_setting("sensory_preferences")
            sensory_exclude = build_sensory_exclude(sensory_prefs_json)

            result = store.browse_recipes(
                keywords=keywords,
                page=page,
                page_size=page_size,
                pantry_items=pantry_list,
                q=q or None,
                sort=sort,
                sensory_exclude=sensory_exclude,
                required_ingredient=required_ingredient or None,
            )

            # ── Attach time/effort signals to each browse result ────────────────
            import json as _json
            for recipe_row in result.get("recipes", []):
                directions_raw = recipe_row.get("directions") or []
                if isinstance(directions_raw, str):
                    try:
                        directions_raw = _json.loads(directions_raw)
                    except Exception:
                        directions_raw = []
                if directions_raw:
                    _profile = parse_time_effort(
                        directions_raw,
                        ingredients=recipe_row.get("ingredients") or [],
                        ingredient_names=recipe_row.get("ingredient_names") or [],
                    )
                    recipe_row["active_min"] = _profile.active_min
                    recipe_row["passive_min"] = _profile.passive_min
                else:
                    recipe_row["active_min"] = None
                    recipe_row["passive_min"] = None
                # Remove directions from browse payload — not needed by the card UI
                recipe_row.pop("directions", None)

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
                            import json as _json_c
                            for recipe_row in recipes:
                                directions_raw = recipe_row.get("directions") or []
                                if isinstance(directions_raw, str):
                                    try:
                                        directions_raw = _json_c.loads(directions_raw)
                                    except Exception:
                                        directions_raw = []
                                if directions_raw:
                                    _profile = parse_time_effort(
                                        directions_raw,
                                        ingredients=recipe_row.get("ingredients") or [],
                                        ingredient_names=recipe_row.get("ingredient_names") or [],
                                    )
                                    recipe_row["active_min"] = _profile.active_min
                                    recipe_row["passive_min"] = _profile.passive_min
                                else:
                                    recipe_row["active_min"] = None
                                    recipe_row["passive_min"] = None
                                recipe_row.pop("directions", None)
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

    # Normalize corpus record into RecipeSuggestion shape so RecipeDetailPanel
    # can render it without knowing it came from a direct DB lookup.
    ingredient_names = recipe.get("ingredient_names") or []
    if isinstance(ingredient_names, str):
        import json as _json
        try:
            ingredient_names = _json.loads(ingredient_names)
        except Exception:
            ingredient_names = []

    _directions_for_te = recipe.get("directions") or []
    if isinstance(_directions_for_te, str):
        import json as _json2
        try:
            _directions_for_te = _json2.loads(_directions_for_te)
        except Exception:
            _directions_for_te = []

    _ingredients_for_te = recipe.get("ingredients") or []
    if isinstance(_ingredients_for_te, str):
        import json as _json3
        try:
            _ingredients_for_te = _json3.loads(_ingredients_for_te)
        except Exception:
            _ingredients_for_te = []

    _ingredient_names_for_te = recipe.get("ingredient_names") or []
    if isinstance(_ingredient_names_for_te, str):
        import json as _json4
        try:
            _ingredient_names_for_te = _json4.loads(_ingredient_names_for_te)
        except Exception:
            _ingredient_names_for_te = []

    if _directions_for_te:
        _te = parse_time_effort(
            _directions_for_te,
            ingredients=_ingredients_for_te,
            ingredient_names=_ingredient_names_for_te,
        )
        _time_effort_out: dict | None = {
            "active_min": _te.active_min,
            "passive_min": _te.passive_min,
            "total_min": _te.total_min,
            "effort_label": _te.effort_label,
            "equipment": _te.equipment,
            "step_analyses": [
                {
                    "is_passive": sa.is_passive,
                    "detected_minutes": sa.detected_minutes,
                    "prep_min": sa.prep_min,
                }
                for sa in _te.step_analyses
            ],
        }
    else:
        _time_effort_out = None

    return {
        "id": recipe.get("id"),
        "title": recipe.get("title", ""),
        "match_count": 0,
        "matched_ingredients": ingredient_names,
        "missing_ingredients": [],
        "directions": recipe.get("directions") or [],
        "prep_notes": [],
        "swap_candidates": [],
        "element_coverage": {},
        "notes": recipe.get("notes") or "",
        "level": 1,
        "is_wildcard": False,
        "nutrition": None,
        "source_url": recipe.get("source_url") or None,
        "complexity": None,
        "estimated_time_min": None,
        "time_effort": _time_effort_out,
    }


@router.post("/{recipe_id}/leftovers", response_model=LeftoversResponse)
async def get_leftovers_shelf_life(
    recipe_id: int,
    session: CloudUser = Depends(get_session),
) -> LeftoversResponse:
    """Return cooked-leftover shelf-life estimate for a recipe.

    Free tier: deterministic lookup (FDA/USDA table).
    Deterministic path always runs; no tier gate needed.
    """
    def _get(db_path: Path, rid: int) -> LeftoversResponse:
        from app.services.leftovers_predictor import predict_leftovers_from_row
        store = Store(db_path)
        try:
            recipe = store.get_recipe(rid)
        finally:
            store.close()
        if recipe is None:
            raise HTTPException(status_code=404, detail="Recipe not found.")
        result = predict_leftovers_from_row(recipe)
        return LeftoversResponse(
            fridge_days=result.fridge_days,
            freeze_days=result.freeze_days,
            freeze_by_day=result.freeze_by_day,
            storage_advice=result.storage_advice,
        )

    return await asyncio.to_thread(_get, session.db, recipe_id)
