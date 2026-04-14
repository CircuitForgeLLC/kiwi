# tests/services/test_meal_plan_prep_scheduler.py
"""Unit tests for prep_scheduler.py — no DB or network."""
from __future__ import annotations

import pytest
from app.services.meal_plan.prep_scheduler import PrepTask, build_prep_tasks


def _recipe(id_: int, name: str, prep_time: int | None, cook_time: int | None, equipment: str) -> dict:
    return {
        "id": id_, "name": name,
        "prep_time": prep_time, "cook_time": cook_time,
        "_equipment": equipment,  # test helper field
    }


def _slot(slot_id: int, recipe: dict, day: int = 0) -> dict:
    return {"id": slot_id, "recipe_id": recipe["id"], "day_of_week": day,
            "meal_type": "dinner", "servings": 2.0}


def test_builds_task_per_slot():
    recipe = _recipe(1, "Pasta", 10, 20, "stovetop")
    tasks = build_prep_tasks(
        slots=[_slot(1, recipe)],
        recipes=[recipe],
    )
    assert len(tasks) == 1
    assert tasks[0].task_label == "Pasta"
    assert tasks[0].duration_minutes == 30  # prep + cook


def test_oven_tasks_scheduled_first():
    oven_recipe = _recipe(1, "Roast Chicken", 10, 60, "oven")
    stove_recipe = _recipe(2, "Rice", 2, 20, "stovetop")
    tasks = build_prep_tasks(
        slots=[_slot(1, stove_recipe), _slot(2, oven_recipe)],
        recipes=[stove_recipe, oven_recipe],
    )
    orders = {t.task_label: t.sequence_order for t in tasks}
    assert orders["Roast Chicken"] < orders["Rice"]


def test_missing_corpus_time_leaves_duration_none():
    recipe = _recipe(1, "Mystery Dish", None, None, "stovetop")
    tasks = build_prep_tasks(slots=[_slot(1, recipe)], recipes=[recipe])
    assert tasks[0].duration_minutes is None


def test_sequence_order_is_contiguous_from_one():
    recipes = [_recipe(i, f"Recipe {i}", 10, 10, "stovetop") for i in range(1, 4)]
    slots = [_slot(i, r) for i, r in enumerate(recipes, 1)]
    tasks = build_prep_tasks(slots=slots, recipes=recipes)
    orders = sorted(t.sequence_order for t in tasks)
    assert orders == [1, 2, 3]
