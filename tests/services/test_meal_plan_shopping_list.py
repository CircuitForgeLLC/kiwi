# tests/services/test_meal_plan_shopping_list.py
"""Unit tests for shopping_list.py — no network, no DB."""
from __future__ import annotations

import pytest
from app.services.meal_plan.shopping_list import GapItem, compute_shopping_list


def _recipe(ingredient_names: list[str], ingredients: list[str]) -> dict:
    return {"ingredient_names": ingredient_names, "ingredients": ingredients}


def _inv_item(name: str, quantity: float, unit: str) -> dict:
    return {"name": name, "quantity": quantity, "unit": unit}


def test_item_in_pantry_is_covered():
    recipes = [_recipe(["pasta"], ["500g pasta"])]
    inventory = [_inv_item("pasta", 400, "g")]
    gaps, covered = compute_shopping_list(recipes, inventory)
    assert len(covered) == 1
    assert covered[0].ingredient_name == "pasta"
    assert covered[0].covered is True
    assert len(gaps) == 0


def test_item_not_in_pantry_is_gap():
    recipes = [_recipe(["chicken breast"], ["300g chicken breast"])]
    inventory = []
    gaps, covered = compute_shopping_list(recipes, inventory)
    assert len(gaps) == 1
    assert gaps[0].ingredient_name == "chicken breast"
    assert gaps[0].covered is False
    assert gaps[0].needed_raw == "300g"


def test_duplicate_ingredient_across_recipes_deduplicates():
    recipes = [
        _recipe(["onion"], ["2 onions"]),
        _recipe(["onion"], ["1 onion"]),
    ]
    inventory = []
    gaps, _ = compute_shopping_list(recipes, inventory)
    names = [g.ingredient_name for g in gaps]
    assert names.count("onion") == 1


def test_empty_plan_returns_empty_lists():
    gaps, covered = compute_shopping_list([], [])
    assert gaps == []
    assert covered == []
