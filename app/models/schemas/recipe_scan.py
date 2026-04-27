"""Pydantic schemas for the recipe scanner (kiwi#9).

Scan input → photo(s).
Scan output → ScannedRecipeResponse (for review + editing before save).
Save input → ScannedRecipeSaveRequest.
User recipe output → UserRecipeResponse (after save).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── Ingredient in a scanned recipe ────────────────────────────────────────────

class ScannedIngredientSchema(BaseModel):
    """One ingredient line extracted from a recipe photo."""
    name: str                      # normalized generic name ("ranch dressing")
    qty: str | None = None         # quantity as string, preserving fractions ("1/2", "¼")
    unit: str | None = None        # unit of measure; null for countable items
    raw: str | None = None         # verbatim original line from the image
    in_pantry: bool = False        # True if this ingredient matches something in the pantry


# ── Scan response (returned immediately, not persisted) ───────────────────────

class ScannedRecipeResponse(BaseModel):
    """Structured recipe extracted from photo(s). Returned for user review before save."""
    title: str | None = None
    subtitle: str | None = None    # e.g. "with Broccoli & Ranch Dressing"
    servings: str | None = None    # kept as string: "2", "4-6", "serves 8"
    cook_time: str | None = None   # kept as string: "25 min", "1 hour"
    source_note: str | None = None # e.g. "Purple Carrot", "Betty Crocker"
    ingredients: list[ScannedIngredientSchema] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    pantry_match_pct: int = 0      # 0-100: percentage of ingredients found in pantry
    confidence: str = "medium"     # "high" | "medium" | "low"
    warnings: list[str] = Field(default_factory=list)


# ── Save request ──────────────────────────────────────────────────────────────

class ScannedRecipeSaveRequest(BaseModel):
    """User-reviewed (possibly edited) recipe data to persist as a user recipe."""
    title: str
    subtitle: str | None = None
    servings: str | None = None
    cook_time: str | None = None
    source_note: str | None = None
    ingredients: list[ScannedIngredientSchema]
    steps: list[str]
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str = "scan"           # "scan" | "manual"


# ── User recipe (persisted) ───────────────────────────────────────────────────

class UserRecipeResponse(BaseModel):
    """A user-created or user-scanned recipe stored in user_recipes table."""
    id: int
    title: str
    subtitle: str | None = None
    servings: str | None = None
    cook_time: str | None = None
    source_note: str | None = None
    ingredients: list[ScannedIngredientSchema]
    steps: list[str]
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str
    pantry_match_pct: int | None = None
    created_at: str
