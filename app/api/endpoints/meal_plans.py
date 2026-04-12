# app/api/endpoints/meal_plans.py
"""Meal plan CRUD, shopping list, and prep session endpoints."""
from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.cloud_session import CloudUser, get_session
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.meal_plan import (
    CreatePlanRequest,
    GapItem,
    PlanSummary,
    PrepSessionSummary,
    PrepTaskSummary,
    ShoppingListResponse,
    SlotSummary,
    UpdatePrepTaskRequest,
    UpsertSlotRequest,
    VALID_MEAL_TYPES,
)
from app.services.meal_plan.affiliates import get_retailer_links
from app.services.meal_plan.prep_scheduler import build_prep_tasks
from app.services.meal_plan.shopping_list import compute_shopping_list
from app.tiers import can_use

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _slot_summary(row: dict) -> SlotSummary:
    return SlotSummary(
        id=row["id"],
        plan_id=row["plan_id"],
        day_of_week=row["day_of_week"],
        meal_type=row["meal_type"],
        recipe_id=row.get("recipe_id"),
        recipe_title=row.get("recipe_title"),
        servings=row["servings"],
        custom_label=row.get("custom_label"),
    )


def _plan_summary(plan: dict, slots: list[dict]) -> PlanSummary:
    meal_types = plan.get("meal_types") or ["dinner"]
    if isinstance(meal_types, str):
        meal_types = json.loads(meal_types)
    return PlanSummary(
        id=plan["id"],
        week_start=plan["week_start"],
        meal_types=meal_types,
        slots=[_slot_summary(s) for s in slots],
        created_at=plan["created_at"],
    )


def _prep_task_summary(row: dict) -> PrepTaskSummary:
    return PrepTaskSummary(
        id=row["id"],
        recipe_id=row.get("recipe_id"),
        task_label=row["task_label"],
        duration_minutes=row.get("duration_minutes"),
        sequence_order=row["sequence_order"],
        equipment=row.get("equipment"),
        is_parallel=bool(row.get("is_parallel", False)),
        notes=row.get("notes"),
        user_edited=bool(row.get("user_edited", False)),
    )


# ── plan CRUD ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=PlanSummary)
async def create_plan(
    req: CreatePlanRequest,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> PlanSummary:
    # Free tier is locked to dinner-only; paid+ may configure meal types
    if can_use("meal_plan_config", session.tier):
        meal_types = [t for t in req.meal_types if t in VALID_MEAL_TYPES] or ["dinner"]
    else:
        meal_types = ["dinner"]

    plan = await asyncio.to_thread(store.create_meal_plan, str(req.week_start), meal_types)
    slots = await asyncio.to_thread(store.get_plan_slots, plan["id"])
    return _plan_summary(plan, slots)


@router.get("/", response_model=list[dict])
async def list_plans(
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> list[dict]:
    return await asyncio.to_thread(store.list_meal_plans)


@router.get("/{plan_id}", response_model=PlanSummary)
async def get_plan(
    plan_id: int,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> PlanSummary:
    plan = await asyncio.to_thread(store.get_meal_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    slots = await asyncio.to_thread(store.get_plan_slots, plan_id)
    return _plan_summary(plan, slots)


# ── slots ─────────────────────────────────────────────────────────────────────

@router.put("/{plan_id}/slots/{day_of_week}/{meal_type}", response_model=SlotSummary)
async def upsert_slot(
    plan_id: int,
    day_of_week: int,
    meal_type: str,
    req: UpsertSlotRequest,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> SlotSummary:
    if meal_type not in VALID_MEAL_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid meal_type '{meal_type}'.")
    plan = await asyncio.to_thread(store.get_meal_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    row = await asyncio.to_thread(
        store.upsert_slot,
        plan_id, day_of_week, meal_type,
        req.recipe_id, req.servings, req.custom_label,
    )
    return _slot_summary(row)


@router.delete("/{plan_id}/slots/{slot_id}", status_code=204)
async def delete_slot(
    plan_id: int,
    slot_id: int,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> None:
    plan = await asyncio.to_thread(store.get_meal_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    await asyncio.to_thread(store.delete_slot, slot_id)


# ── shopping list ─────────────────────────────────────────────────────────────

@router.get("/{plan_id}/shopping-list", response_model=ShoppingListResponse)
async def get_shopping_list(
    plan_id: int,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> ShoppingListResponse:
    plan = await asyncio.to_thread(store.get_meal_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    recipes = await asyncio.to_thread(store.get_plan_recipes, plan_id)
    inventory = await asyncio.to_thread(store.list_inventory)

    gaps, covered = compute_shopping_list(recipes, inventory)

    # Enrich gap items with retailer links
    def _to_schema(item, enrich: bool) -> GapItem:
        links = get_retailer_links(item.ingredient_name) if enrich else []
        return GapItem(
            ingredient_name=item.ingredient_name,
            needed_raw=item.needed_raw,
            have_quantity=item.have_quantity,
            have_unit=item.have_unit,
            covered=item.covered,
            retailer_links=links,
        )

    gap_items = [_to_schema(g, enrich=True) for g in gaps]
    covered_items = [_to_schema(c, enrich=False) for c in covered]

    disclosure = (
        "Some links may be affiliate links. Purchases through them support Kiwi development."
        if gap_items else None
    )

    return ShoppingListResponse(
        plan_id=plan_id,
        gap_items=gap_items,
        covered_items=covered_items,
        disclosure=disclosure,
    )


# ── prep session ──────────────────────────────────────────────────────────────

@router.post("/{plan_id}/prep-session", response_model=PrepSessionSummary)
async def create_prep_session(
    plan_id: int,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> PrepSessionSummary:
    plan = await asyncio.to_thread(store.get_meal_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    slots = await asyncio.to_thread(store.get_plan_slots, plan_id)
    recipes = await asyncio.to_thread(store.get_plan_recipes, plan_id)
    prep_tasks = build_prep_tasks(slots=slots, recipes=recipes)

    scheduled_date = date.today().isoformat()
    prep_session = await asyncio.to_thread(
        store.create_prep_session, plan_id, scheduled_date
    )
    session_id = prep_session["id"]

    task_dicts = [
        {
            "recipe_id": t.recipe_id,
            "slot_id": t.slot_id,
            "task_label": t.task_label,
            "duration_minutes": t.duration_minutes,
            "sequence_order": t.sequence_order,
            "equipment": t.equipment,
            "is_parallel": t.is_parallel,
            "notes": t.notes,
        }
        for t in prep_tasks
    ]
    inserted = await asyncio.to_thread(store.bulk_insert_prep_tasks, session_id, task_dicts)

    return PrepSessionSummary(
        id=prep_session["id"],
        plan_id=prep_session["plan_id"],
        scheduled_date=prep_session["scheduled_date"],
        status=prep_session["status"],
        tasks=[_prep_task_summary(r) for r in inserted],
    )


@router.patch(
    "/{plan_id}/prep-session/tasks/{task_id}",
    response_model=PrepTaskSummary,
)
async def update_prep_task(
    plan_id: int,
    task_id: int,
    req: UpdatePrepTaskRequest,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> PrepTaskSummary:
    updated = await asyncio.to_thread(
        store.update_prep_task,
        task_id,
        duration_minutes=req.duration_minutes,
        sequence_order=req.sequence_order,
        notes=req.notes,
        equipment=req.equipment,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return _prep_task_summary(updated)
