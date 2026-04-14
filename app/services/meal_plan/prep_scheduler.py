# app/services/meal_plan/prep_scheduler.py
"""Sequence prep tasks for a batch cooking session.

Pure function — no DB or network calls. Sorts tasks by equipment priority
(oven first to maximise oven utilisation) then assigns sequence_order.
"""
from __future__ import annotations

from dataclasses import dataclass

_EQUIPMENT_PRIORITY = {"oven": 0, "stovetop": 1, "cold": 2, "no-heat": 3}
_DEFAULT_PRIORITY = 4


@dataclass(frozen=True)
class PrepTask:
    recipe_id: int | None
    slot_id: int | None
    task_label: str
    duration_minutes: int | None
    sequence_order: int
    equipment: str | None
    is_parallel: bool = False
    notes: str | None = None
    user_edited: bool = False


def _total_minutes(recipe: dict) -> int | None:
    prep = recipe.get("prep_time")
    cook = recipe.get("cook_time")
    if prep is None and cook is None:
        return None
    return (prep or 0) + (cook or 0)


def _equipment(recipe: dict) -> str | None:
    # Corpus recipes don't have an explicit equipment field; use test helper
    # field if present, otherwise infer from cook_time (long = oven heuristic).
    if "_equipment" in recipe:
        return recipe["_equipment"]
    minutes = _total_minutes(recipe)
    if minutes and minutes >= 45:
        return "oven"
    return "stovetop"


def build_prep_tasks(slots: list[dict], recipes: list[dict]) -> list[PrepTask]:
    """Return a sequenced list of PrepTask objects from plan slots + recipe rows.

    Algorithm:
    1. Build a recipe_id → recipe dict lookup.
    2. Create one task per slot that has a recipe assigned.
    3. Sort by equipment priority (oven first).
    4. Assign contiguous sequence_order starting at 1.
    """
    if not slots or not recipes:
        return []

    recipe_map: dict[int, dict] = {r["id"]: r for r in recipes}
    raw_tasks: list[tuple[int, dict]] = []  # (priority, kwargs)

    for slot in slots:
        recipe_id = slot.get("recipe_id")
        if not recipe_id:
            continue
        recipe = recipe_map.get(recipe_id)
        if not recipe:
            continue

        eq = _equipment(recipe)
        priority = _EQUIPMENT_PRIORITY.get(eq or "", _DEFAULT_PRIORITY)
        raw_tasks.append((priority, {
            "recipe_id": recipe_id,
            "slot_id": slot.get("id"),
            "task_label": recipe.get("name", f"Recipe {recipe_id}"),
            "duration_minutes": _total_minutes(recipe),
            "equipment": eq,
        }))

    raw_tasks.sort(key=lambda t: t[0])
    return [
        PrepTask(
            recipe_id=kw["recipe_id"],
            slot_id=kw["slot_id"],
            task_label=kw["task_label"],
            duration_minutes=kw["duration_minutes"],
            sequence_order=i,
            equipment=kw["equipment"],
        )
        for i, (_, kw) in enumerate(raw_tasks, 1)
    ]
