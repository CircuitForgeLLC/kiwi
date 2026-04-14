"""Pydantic schemas for the recipe engine API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SwapCandidate(BaseModel):
    original_name: str
    substitute_name: str
    constraint_label: str
    explanation: str
    compensation_hints: list[dict] = Field(default_factory=list)


class NutritionPanel(BaseModel):
    """Per-recipe macro summary. All values are per-serving when servings is known,
    otherwise for the full recipe. None means data is unavailable."""
    calories: float | None = None
    fat_g: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    servings: float | None = None
    estimated: bool = False  # True when nutrition was inferred from ingredient profiles


class RecipeSuggestion(BaseModel):
    id: int
    title: str
    match_count: int
    element_coverage: dict[str, float] = Field(default_factory=dict)
    swap_candidates: list[SwapCandidate] = Field(default_factory=list)
    matched_ingredients: list[str] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)
    prep_notes: list[str] = Field(default_factory=list)
    notes: str = ""
    level: int = 1
    is_wildcard: bool = False
    nutrition: NutritionPanel | None = None
    source_url: str | None = None


class GroceryLink(BaseModel):
    ingredient: str
    retailer: str
    url: str


class RecipeResult(BaseModel):
    suggestions: list[RecipeSuggestion]
    element_gaps: list[str]
    grocery_list: list[str] = Field(default_factory=list)
    grocery_links: list[GroceryLink] = Field(default_factory=list)
    rate_limited: bool = False
    rate_limit_count: int = 0


class NutritionFilters(BaseModel):
    """Optional per-serving upper bounds for macro filtering. None = no filter."""
    max_calories: float | None = None
    max_sugar_g: float | None = None
    max_carbs_g: float | None = None
    max_sodium_mg: float | None = None


class RecipeRequest(BaseModel):
    pantry_items: list[str]
    level: int = Field(default=1, ge=1, le=4)
    constraints: list[str] = Field(default_factory=list)
    expiry_first: bool = False
    hard_day_mode: bool = False
    max_missing: int | None = None
    style_id: str | None = None
    category: str | None = None
    tier: str = "free"
    has_byok: bool = False
    wildcard_confirmed: bool = False
    allergies: list[str] = Field(default_factory=list)
    nutrition_filters: NutritionFilters = Field(default_factory=NutritionFilters)
    excluded_ids: list[int] = Field(default_factory=list)
    shopping_mode: bool = False


# ── Build Your Own schemas ──────────────────────────────────────────────────


class AssemblyRoleOut(BaseModel):
    """One role slot in a template, as returned by GET /api/recipes/templates."""

    display: str
    required: bool
    keywords: list[str]
    hint: str = ""


class AssemblyTemplateOut(BaseModel):
    """One assembly template, as returned by GET /api/recipes/templates."""

    id: str  # slug, e.g. "burrito_taco"
    title: str
    icon: str
    descriptor: str
    role_sequence: list[AssemblyRoleOut]


class RoleCandidateItem(BaseModel):
    """One candidate ingredient for a wizard picker step."""

    name: str
    in_pantry: bool
    tags: list[str] = Field(default_factory=list)


class RoleCandidatesResponse(BaseModel):
    """Response from GET /api/recipes/template-candidates."""

    compatible: list[RoleCandidateItem] = Field(default_factory=list)
    other: list[RoleCandidateItem] = Field(default_factory=list)
    available_tags: list[str] = Field(default_factory=list)


class BuildRequest(BaseModel):
    """Request body for POST /api/recipes/build."""

    template_id: str
    role_overrides: dict[str, str] = Field(default_factory=dict)
