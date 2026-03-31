"""Pydantic schemas for the recipe engine API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SwapCandidate(BaseModel):
    original_name: str
    substitute_name: str
    constraint_label: str
    explanation: str
    compensation_hints: list[dict] = Field(default_factory=list)


class RecipeSuggestion(BaseModel):
    id: int
    title: str
    match_count: int
    element_coverage: dict[str, float] = Field(default_factory=dict)
    swap_candidates: list[SwapCandidate] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)
    level: int = 1
    is_wildcard: bool = False


class RecipeResult(BaseModel):
    suggestions: list[RecipeSuggestion]
    element_gaps: list[str]
    grocery_list: list[str] = Field(default_factory=list)
    rate_limited: bool = False
    rate_limit_count: int = 0


class RecipeRequest(BaseModel):
    pantry_items: list[str]
    level: int = Field(default=1, ge=1, le=4)
    constraints: list[str] = Field(default_factory=list)
    expiry_first: bool = False
    hard_day_mode: bool = False
    max_missing: int | None = None
    style_id: str | None = None
    tier: str = "free"
    has_byok: bool = False
    wildcard_confirmed: bool = False
