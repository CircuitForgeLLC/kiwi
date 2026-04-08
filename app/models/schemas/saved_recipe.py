"""Pydantic schemas for saved recipes and collections."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SaveRecipeRequest(BaseModel):
    recipe_id: int
    notes: str | None = None
    rating: int | None = Field(None, ge=0, le=5)


class UpdateSavedRecipeRequest(BaseModel):
    notes: str | None = None
    rating: int | None = Field(None, ge=0, le=5)
    style_tags: list[str] = Field(default_factory=list)


class SavedRecipeSummary(BaseModel):
    id: int
    recipe_id: int
    title: str
    saved_at: str
    notes: str | None
    rating: int | None
    style_tags: list[str]
    collection_ids: list[int] = Field(default_factory=list)


class CollectionSummary(BaseModel):
    id: int
    name: str
    description: str | None
    member_count: int
    created_at: str


class CollectionRequest(BaseModel):
    name: str
    description: str | None = None


class CollectionMemberRequest(BaseModel):
    saved_recipe_id: int
