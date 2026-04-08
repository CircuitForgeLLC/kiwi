"""Saved recipe bookmark endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.cloud_session import CloudUser, get_session
from app.db.store import Store
from app.models.schemas.saved_recipe import (
    CollectionMemberRequest,
    CollectionRequest,
    CollectionSummary,
    SavedRecipeSummary,
    SaveRecipeRequest,
    UpdateSavedRecipeRequest,
)
from app.tiers import can_use

router = APIRouter()


def _in_thread(db_path: Path, fn):
    """Run a Store operation in a worker thread with its own connection."""
    store = Store(db_path)
    try:
        return fn(store)
    finally:
        store.close()


def _to_summary(row: dict, store: Store) -> SavedRecipeSummary:
    collection_ids = store.get_saved_recipe_collection_ids(row["id"])
    return SavedRecipeSummary(
        id=row["id"],
        recipe_id=row["recipe_id"],
        title=row.get("title", ""),
        saved_at=row["saved_at"],
        notes=row.get("notes"),
        rating=row.get("rating"),
        style_tags=row.get("style_tags") or [],
        collection_ids=collection_ids,
    )


# ── save / unsave ─────────────────────────────────────────────────────────────

@router.post("", response_model=SavedRecipeSummary)
async def save_recipe(
    req: SaveRecipeRequest,
    session: CloudUser = Depends(get_session),
) -> SavedRecipeSummary:
    def _run(store: Store) -> SavedRecipeSummary:
        row = store.save_recipe(req.recipe_id, req.notes, req.rating)
        return _to_summary(row, store)

    return await asyncio.to_thread(_in_thread, session.db, _run)


@router.delete("/{recipe_id}", status_code=204)
async def unsave_recipe(
    recipe_id: int,
    session: CloudUser = Depends(get_session),
) -> None:
    await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.unsave_recipe(recipe_id)
    )


@router.patch("/{recipe_id}", response_model=SavedRecipeSummary)
async def update_saved_recipe(
    recipe_id: int,
    req: UpdateSavedRecipeRequest,
    session: CloudUser = Depends(get_session),
) -> SavedRecipeSummary:
    def _run(store: Store) -> SavedRecipeSummary:
        if not store.is_recipe_saved(recipe_id):
            raise HTTPException(status_code=404, detail="Recipe not saved.")
        row = store.update_saved_recipe(
            recipe_id, req.notes, req.rating, req.style_tags
        )
        return _to_summary(row, store)

    return await asyncio.to_thread(_in_thread, session.db, _run)


@router.get("", response_model=list[SavedRecipeSummary])
async def list_saved_recipes(
    sort_by: str = "saved_at",
    collection_id: int | None = None,
    session: CloudUser = Depends(get_session),
) -> list[SavedRecipeSummary]:
    def _run(store: Store) -> list[SavedRecipeSummary]:
        rows = store.get_saved_recipes(sort_by=sort_by, collection_id=collection_id)
        return [_to_summary(r, store) for r in rows]

    return await asyncio.to_thread(_in_thread, session.db, _run)


# ── collections (Paid) ────────────────────────────────────────────────────────

@router.get("/collections", response_model=list[CollectionSummary])
async def list_collections(
    session: CloudUser = Depends(get_session),
) -> list[CollectionSummary]:
    rows = await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.get_collections()
    )
    return [CollectionSummary(**r) for r in rows]


@router.post("/collections", response_model=CollectionSummary)
async def create_collection(
    req: CollectionRequest,
    session: CloudUser = Depends(get_session),
) -> CollectionSummary:
    if not can_use("recipe_collections", session.tier):
        raise HTTPException(
            status_code=403,
            detail="Collections require Paid tier.",
        )
    row = await asyncio.to_thread(
        _in_thread, session.db,
        lambda s: s.create_collection(req.name, req.description),
    )
    return CollectionSummary(**row)


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: int,
    session: CloudUser = Depends(get_session),
) -> None:
    if not can_use("recipe_collections", session.tier):
        raise HTTPException(status_code=403, detail="Collections require Paid tier.")
    await asyncio.to_thread(
        _in_thread, session.db, lambda s: s.delete_collection(collection_id)
    )


@router.patch("/collections/{collection_id}", response_model=CollectionSummary)
async def rename_collection(
    collection_id: int,
    req: CollectionRequest,
    session: CloudUser = Depends(get_session),
) -> CollectionSummary:
    if not can_use("recipe_collections", session.tier):
        raise HTTPException(status_code=403, detail="Collections require Paid tier.")
    row = await asyncio.to_thread(
        _in_thread, session.db,
        lambda s: s.rename_collection(collection_id, req.name, req.description),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found.")
    return CollectionSummary(**row)


@router.post("/collections/{collection_id}/members", status_code=204)
async def add_to_collection(
    collection_id: int,
    req: CollectionMemberRequest,
    session: CloudUser = Depends(get_session),
) -> None:
    if not can_use("recipe_collections", session.tier):
        raise HTTPException(status_code=403, detail="Collections require Paid tier.")
    await asyncio.to_thread(
        _in_thread, session.db,
        lambda s: s.add_to_collection(collection_id, req.saved_recipe_id),
    )


@router.delete(
    "/collections/{collection_id}/members/{saved_recipe_id}", status_code=204
)
async def remove_from_collection(
    collection_id: int,
    saved_recipe_id: int,
    session: CloudUser = Depends(get_session),
) -> None:
    if not can_use("recipe_collections", session.tier):
        raise HTTPException(status_code=403, detail="Collections require Paid tier.")
    await asyncio.to_thread(
        _in_thread, session.db,
        lambda s: s.remove_from_collection(collection_id, saved_recipe_id),
    )
