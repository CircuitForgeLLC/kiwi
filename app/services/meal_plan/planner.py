# app/services/meal_plan/planner.py
"""Plan and slot orchestration — thin layer over Store.

No FastAPI imports. Provides helpers used by the API endpoint.
"""
from __future__ import annotations

from app.db.store import Store
from app.models.schemas.meal_plan import VALID_MEAL_TYPES


def create_plan(store: Store, week_start: str, meal_types: list[str]) -> dict:
    """Create a plan, filtering meal_types to valid values only."""
    valid = [t for t in meal_types if t in VALID_MEAL_TYPES]
    if not valid:
        valid = ["dinner"]
    return store.create_meal_plan(week_start, valid)


def get_plan_with_slots(store: Store, plan_id: int) -> dict | None:
    """Return a plan row with its slots list attached, or None."""
    plan = store.get_meal_plan(plan_id)
    if plan is None:
        return None
    slots = store.get_plan_slots(plan_id)
    return {**plan, "slots": slots}
