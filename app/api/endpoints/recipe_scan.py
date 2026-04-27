"""Recipe scanner endpoints (kiwi#9).

POST /recipes/scan       -- scan photo(s) -> structured recipe JSON (not saved)
POST /recipes/scan/save  -- save a confirmed scanned recipe to user_recipes
GET  /recipes/user       -- list user-created recipes
GET  /recipes/user/{id}  -- get a single user recipe
DELETE /recipes/user/{id} -- delete a user recipe

BSL 1.1 -- recipe_scan requires Paid tier or BYOK.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.cloud_session import CloudUser, get_session
from app.core.config import settings
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.recipe_scan import (
    ScannedIngredientSchema,
    ScannedRecipeResponse,
    ScannedRecipeSaveRequest,
    UserRecipeResponse,
)
from app.tiers import can_use

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"
}
_MAX_FILE_SIZE_MB = 20


async def _save_upload_temp(file: UploadFile) -> Path:
    """Write upload to a temp path under UPLOAD_DIR. Caller is responsible for cleanup."""
    settings.ensure_dirs()
    dest = settings.UPLOAD_DIR / f"scan_{uuid.uuid4()}_{file.filename}"
    async with aiofiles.open(dest, "wb") as f:
        await f.write(await file.read())
    return dest


def _result_to_response(result) -> ScannedRecipeResponse:
    """Convert ScannedRecipeResult (dataclass) to Pydantic response schema."""
    return ScannedRecipeResponse(
        title=result.title,
        subtitle=result.subtitle,
        servings=result.servings,
        cook_time=result.cook_time,
        source_note=result.source_note,
        ingredients=[
            ScannedIngredientSchema(
                name=i.name,
                qty=i.qty,
                unit=i.unit,
                raw=i.raw,
                in_pantry=i.in_pantry,
            )
            for i in result.ingredients
        ],
        steps=result.steps,
        notes=result.notes,
        tags=result.tags,
        pantry_match_pct=result.pantry_match_pct,
        confidence=result.confidence,
        warnings=result.warnings,
    )


def _row_to_user_recipe(row: dict) -> UserRecipeResponse:
    """Convert a store row dict to UserRecipeResponse."""
    return UserRecipeResponse(
        id=row["id"],
        title=row["title"],
        subtitle=row.get("subtitle"),
        servings=row.get("servings"),
        cook_time=row.get("cook_time"),
        source_note=row.get("source_note"),
        ingredients=[
            ScannedIngredientSchema(**i) if isinstance(i, dict) else i
            for i in (row.get("ingredients") or [])
        ],
        steps=row.get("steps") or [],
        notes=row.get("notes"),
        tags=row.get("tags") or [],
        source=row.get("source", "manual"),
        pantry_match_pct=row.get("pantry_match_pct"),
        created_at=row["created_at"],
    )


# ── Scan endpoint ──────────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScannedRecipeResponse)
async def scan_recipe(
    files: Annotated[list[UploadFile], File(...)],
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Scan one or more recipe photos and return a structured recipe for review.

    Accepts 1-4 images. Multi-page recipes (e.g. ingredients on page 1,
    directions on page 2) work best when all pages are submitted together.

    The response is NOT saved automatically -- the user reviews and edits it,
    then calls POST /recipes/scan/save to persist.

    Tier: Paid (or BYOK).
    """
    if not can_use("recipe_scan", session.tier, session.has_byok):
        raise HTTPException(
            status_code=403,
            detail=(
                "Recipe scanning requires Paid tier or a configured vision backend (BYOK). "
                "Set ANTHROPIC_API_KEY or connect to a cf-orch vision service."
            ),
        )

    if not files:
        raise HTTPException(status_code=422, detail="At least one image file is required.")
    if len(files) > 4:
        raise HTTPException(status_code=422, detail="Maximum 4 images per scan request.")

    for f in files:
        ct = (f.content_type or "").lower()
        if ct and ct not in _ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type: {ct}. Supported: JPEG, PNG, WebP, HEIC.",
            )

    # Save uploads to temp files
    saved_paths: list[Path] = []
    try:
        for f in files:
            saved_paths.append(await _save_upload_temp(f))

        # Get pantry item names for cross-reference
        inventory = await asyncio.to_thread(store.list_inventory)
        pantry_names = [item["product_name"] for item in inventory if item.get("product_name")]

        # Run scanner (blocks on VLM -- use to_thread)
        from app.services.recipe.recipe_scanner import RecipeScanner

        def _run_scan():
            scanner = RecipeScanner()
            return scanner.scan(saved_paths, pantry_names=pantry_names)

        try:
            result = await asyncio.to_thread(_run_scan)
        except ValueError as exc:
            msg = str(exc)
            if "not_a_recipe" in msg:
                raise HTTPException(
                    status_code=422,
                    detail="The image does not appear to contain a recipe. "
                           "Please photograph a recipe card, cookbook page, or handwritten note.",
                )
            raise HTTPException(status_code=422, detail=msg)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            )

        return _result_to_response(result)

    finally:
        # Clean up temp files
        for p in saved_paths:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


# ── Save endpoint ──────────────────────────────────────────────────────────────

@router.post("/scan/save", response_model=UserRecipeResponse, status_code=201)
async def save_scanned_recipe(
    body: ScannedRecipeSaveRequest,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Save a user-reviewed (possibly edited) scanned recipe.

    The body is the ScannedRecipeResponse (or a user-edited version of it).
    Returns the persisted UserRecipe with an assigned ID.

    Tier: Free (saving your own recipe doesn't require vision access).
    """
    def _save():
        return store.create_user_recipe(
            title=body.title,
            subtitle=body.subtitle,
            servings=body.servings,
            cook_time=body.cook_time,
            source_note=body.source_note,
            ingredients=[i.model_dump() for i in body.ingredients],
            steps=body.steps,
            notes=body.notes,
            tags=body.tags,
            source=body.source,
            pantry_match_pct=None,
        )

    row = await asyncio.to_thread(_save)
    return _row_to_user_recipe(row)


# ── User recipe list / get / delete ───────────────────────────────────────────

@router.get("/user", response_model=list[UserRecipeResponse])
async def list_user_recipes(
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """List all user-created recipes (scanned + manually entered), newest first."""
    rows = await asyncio.to_thread(store.list_user_recipes)
    return [_row_to_user_recipe(r) for r in rows]


@router.get("/user/{recipe_id}", response_model=UserRecipeResponse)
async def get_user_recipe(
    recipe_id: int,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Get a single user recipe by ID."""
    row = await asyncio.to_thread(store.get_user_recipe, recipe_id)
    if not row:
        raise HTTPException(status_code=404, detail="User recipe not found.")
    return _row_to_user_recipe(row)


@router.delete("/user/{recipe_id}", status_code=204)
async def delete_user_recipe(
    recipe_id: int,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Delete a user recipe by ID."""
    deleted = await asyncio.to_thread(store.delete_user_recipe, recipe_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User recipe not found.")
    return JSONResponse(status_code=204, content=None)
