"""Shopping list endpoints.

Free tier for all users (anonymous guests included — shopping list is the
primary affiliate revenue surface). Confirm-purchase action is also Free:
it moves a checked item into pantry inventory without a tier gate so the
flow works for anyone who signs up or browses without an account.

Routes:
  GET    /shopping              — list items (with affiliate links)
  POST   /shopping              — add item manually
  PATCH  /shopping/{id}         — update (check/uncheck, rename, qty)
  DELETE /shopping/{id}         — remove single item
  DELETE /shopping/checked       — clear all checked items
  DELETE /shopping/all           — clear entire list
  POST   /shopping/from-recipe   — bulk add gaps from a recipe
  POST   /shopping/{id}/confirm  — confirm purchase → add to pantry inventory
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.cloud_session import CloudUser, get_session
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.shopping import (
    BulkAddFromRecipeRequest,
    ConfirmPurchaseRequest,
    ShoppingItemCreate,
    ShoppingItemResponse,
    ShoppingItemUpdate,
)
from app.services.recipe.grocery_links import GroceryLinkBuilder

log = logging.getLogger(__name__)
router = APIRouter()


def _enrich(item: dict, builder: GroceryLinkBuilder) -> ShoppingItemResponse:
    """Attach live affiliate links to a raw store row."""
    links = builder.build_links(item["name"])
    return ShoppingItemResponse(
        **{**item, "checked": bool(item.get("checked", 0))},
        grocery_links=[{"ingredient": l.ingredient, "retailer": l.retailer, "url": l.url} for l in links],
    )


def _in_thread(db_path, fn):
    store = Store(db_path)
    try:
        return fn(store)
    finally:
        store.close()


# ── List ──────────────────────────────────────────────────────────────────────

def _locale_from_store(store: Store) -> str:
    return store.get_setting("shopping_locale") or "us"


@router.get("", response_model=list[ShoppingItemResponse])
async def list_shopping_items(
    include_checked: bool = True,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
):
    locale = await asyncio.to_thread(_in_thread, session.db, _locale_from_store)
    builder = GroceryLinkBuilder(tier=session.tier, has_byok=session.has_byok, locale=locale)
    items = await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.list_shopping_items(include_checked)
    )
    return [_enrich(i, builder) for i in items]


# ── Add manually ──────────────────────────────────────────────────────────────

@router.post("", response_model=ShoppingItemResponse, status_code=status.HTTP_201_CREATED)
async def add_shopping_item(
    body: ShoppingItemCreate,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
):
    builder = GroceryLinkBuilder(tier=session.tier, has_byok=session.has_byok, locale=_locale_from_store(store))
    item = await asyncio.to_thread(
        _in_thread,
        session.db,
        lambda s: s.add_shopping_item(
            name=body.name,
            quantity=body.quantity,
            unit=body.unit,
            category=body.category,
            notes=body.notes,
            source=body.source,
            recipe_id=body.recipe_id,
            sort_order=body.sort_order,
        ),
    )
    return _enrich(item, builder)


# ── Bulk add from recipe ───────────────────────────────────────────────────────

@router.post("/from-recipe", response_model=list[ShoppingItemResponse], status_code=status.HTTP_201_CREATED)
async def add_from_recipe(
    body: BulkAddFromRecipeRequest,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
):
    """Add missing ingredients from a recipe to the shopping list.

    Runs pantry gap analysis and adds only the items the user doesn't have
    (unless include_covered=True). Skips duplicates already on the list.
    """
    from app.services.meal_plan.shopping_list import compute_shopping_list

    def _run(store: Store):
        recipe = store.get_recipe(body.recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        inventory = store.list_inventory()
        gaps, covered = compute_shopping_list([recipe], inventory)
        targets = (gaps + covered) if body.include_covered else gaps

        # Avoid duplicates already on the list
        existing = {i["name"].lower() for i in store.list_shopping_items()}
        added = []
        for gap in targets:
            if gap.ingredient_name.lower() in existing:
                continue
            item = store.add_shopping_item(
                name=gap.ingredient_name,
                quantity=None,
                unit=gap.have_unit,
                source="recipe",
                recipe_id=body.recipe_id,
            )
            added.append(item)
        return added

    builder = GroceryLinkBuilder(tier=session.tier, has_byok=session.has_byok, locale=_locale_from_store(store))
    items = await asyncio.to_thread(_in_thread, session.db, _run)
    return [_enrich(i, builder) for i in items]


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{item_id}", response_model=ShoppingItemResponse)
async def update_shopping_item(
    item_id: int,
    body: ShoppingItemUpdate,
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
):
    builder = GroceryLinkBuilder(tier=session.tier, has_byok=session.has_byok, locale=_locale_from_store(store))
    item = await asyncio.to_thread(
        _in_thread,
        session.db,
        lambda s: s.update_shopping_item(item_id, **body.model_dump(exclude_none=True)),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Shopping item not found")
    return _enrich(item, builder)


# ── Confirm purchase → pantry ─────────────────────────────────────────────────

@router.post("/{item_id}/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_purchase(
    item_id: int,
    body: ConfirmPurchaseRequest,
    session: CloudUser = Depends(get_session),
):
    """Confirm a checked item was purchased and add it to pantry inventory.

    Human approval step: the user explicitly confirms what they actually bought
    before it lands in their pantry. Returns the new inventory item.
    """
    def _run(store: Store):
        shopping_item = store.get_shopping_item(item_id)
        if not shopping_item:
            raise HTTPException(status_code=404, detail="Shopping item not found")

        qty = body.quantity if body.quantity is not None else (shopping_item.get("quantity") or 1.0)
        unit = body.unit or shopping_item.get("unit") or "count"
        category = shopping_item.get("category")

        product = store.get_or_create_product(
            name=shopping_item["name"],
            category=category,
        )
        inv_item = store.add_inventory_item(
            product_id=product["id"],
            location=body.location,
            quantity=qty,
            unit=unit,
            source="manual",
        )
        # Mark the shopping item checked and leave it for the user to clear
        store.update_shopping_item(item_id, checked=True)
        return inv_item

    return await asyncio.to_thread(_in_thread, session.db, _run)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_item(
    item_id: int,
    session: CloudUser = Depends(get_session),
):
    deleted = await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.delete_shopping_item(item_id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Shopping item not found")


@router.delete("/checked", status_code=status.HTTP_204_NO_CONTENT)
async def clear_checked(session: CloudUser = Depends(get_session)):
    await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.clear_checked_shopping_items()
    )


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all(session: CloudUser = Depends(get_session)):
    await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.clear_all_shopping_items()
    )
