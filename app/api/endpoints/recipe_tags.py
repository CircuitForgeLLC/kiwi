# app/api/endpoints/recipe_tags.py
"""Community subcategory tagging for corpus recipes.

Users can tag a recipe they're viewing with a domain/category/subcategory
from the browse taxonomy. Tags require a community pseudonym and reach
public visibility once two independent users have tagged the same recipe
to the same location (upvotes >= 2).

All tiers may submit and upvote tags — community contribution is free.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.endpoints.community import _get_community_store
from app.api.endpoints.session import get_session
from app.cloud_session import CloudUser
from app.services.recipe.browser_domains import DOMAINS

logger = logging.getLogger(__name__)
router = APIRouter()

ACCEPT_THRESHOLD = 2


# ── Request / response models ──────────────────────────────────────────────────

class TagSubmitBody(BaseModel):
    recipe_id: int
    domain: str
    category: str
    subcategory: str | None = None
    pseudonym: str


class TagResponse(BaseModel):
    id: int
    recipe_id: int
    domain: str
    category: str
    subcategory: str | None
    pseudonym: str
    upvotes: int
    accepted: bool


def _to_response(row: dict) -> TagResponse:
    return TagResponse(
        id=row["id"],
        recipe_id=int(row["recipe_ref"]),
        domain=row["domain"],
        category=row["category"],
        subcategory=row.get("subcategory"),
        pseudonym=row["pseudonym"],
        upvotes=row["upvotes"],
        accepted=row["upvotes"] >= ACCEPT_THRESHOLD,
    )


def _validate_location(domain: str, category: str, subcategory: str | None) -> None:
    """Raise 422 if (domain, category, subcategory) isn't in the known taxonomy."""
    if domain not in DOMAINS:
        raise HTTPException(status_code=422, detail=f"Unknown domain '{domain}'.")
    cats = DOMAINS[domain].get("categories", {})
    if category not in cats:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{category}' in domain '{domain}'.",
        )
    if subcategory is not None:
        subcats = cats[category].get("subcategories", {})
        if subcategory not in subcats:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown subcategory '{subcategory}' in '{domain}/{category}'.",
            )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/recipes/community-tags/{recipe_id}", response_model=list[TagResponse])
async def list_recipe_tags(
    recipe_id: int,
    session: CloudUser = Depends(get_session),
) -> list[TagResponse]:
    """Return all community tags for a corpus recipe, accepted ones first."""
    store = _get_community_store()
    if store is None:
        return []
    tags = store.list_tags_for_recipe(recipe_id)
    return [_to_response(r) for r in tags]


@router.post("/recipes/community-tags", response_model=TagResponse, status_code=201)
async def submit_recipe_tag(
    body: TagSubmitBody,
    session: CloudUser = Depends(get_session),
) -> TagResponse:
    """Tag a corpus recipe with a browse taxonomy location.

    Requires the user to have a community pseudonym set. Returns 409 if this
    user has already tagged this recipe to this exact location.
    """
    store = _get_community_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Community features are not available on this instance.",
        )

    _validate_location(body.domain, body.category, body.subcategory)

    try:
        import psycopg2.errors  # type: ignore[import]
        row = store.submit_recipe_tag(
            recipe_id=body.recipe_id,
            domain=body.domain,
            category=body.category,
            subcategory=body.subcategory,
            pseudonym=body.pseudonym,
        )
        return _to_response(row)
    except Exception as exc:
        if "unique" in str(exc).lower() or "UniqueViolation" in type(exc).__name__:
            raise HTTPException(
                status_code=409,
                detail="You have already tagged this recipe to this location.",
            )
        logger.error("submit_recipe_tag failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to submit tag.")


@router.post("/recipes/community-tags/{tag_id}/upvote", response_model=TagResponse)
async def upvote_recipe_tag(
    tag_id: int,
    pseudonym: str,
    session: CloudUser = Depends(get_session),
) -> TagResponse:
    """Upvote an existing community tag.

    Returns 409 if this pseudonym has already voted on this tag.
    Returns 404 if the tag doesn't exist.
    """
    store = _get_community_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Community features unavailable.")

    tag_row = store.get_recipe_tag_by_id(tag_id)
    if tag_row is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found.")

    try:
        new_upvotes = store.upvote_recipe_tag(tag_id, pseudonym)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found.")
    except Exception as exc:
        if "unique" in str(exc).lower() or "UniqueViolation" in type(exc).__name__:
            raise HTTPException(status_code=409, detail="You have already voted on this tag.")
        logger.error("upvote_recipe_tag failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to upvote tag.")

    tag_row["upvotes"] = new_upvotes
    return _to_response(tag_row)
