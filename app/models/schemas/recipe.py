"""Pydantic schemas for the recipe engine API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LeftoversResponse(BaseModel):
    """Cooked-leftover shelf-life estimate returned by POST /recipes/{id}/leftovers."""
    fridge_days: int
    freeze_days: int | None = None   # None = not recommended
    freeze_by_day: int | None = None  # day number from cook date to freeze by
    storage_advice: str


class StepAnalysis(BaseModel):
    """Active/passive classification for one direction step."""
    is_passive: bool
    detected_minutes: int | None = None
    prep_min: int | None = None   # estimated physical prep time (action detection)


class TimeEffortProfile(BaseModel):
    """Parsed time and effort profile for a recipe.

    Mirrors app.services.recipe.time_effort.TimeEffortProfile (dataclass).
    Serialised into RecipeSuggestion so the frontend can render the effort
    summary without a second round-trip.
    """
    active_min: int = 0
    passive_min: int = 0
    total_min: int = 0
    effort_label: str = "moderate"   # "quick" | "moderate" | "involved"
    equipment: list[str] = Field(default_factory=list)
    step_analyses: list[StepAnalysis] = Field(default_factory=list)


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
    complexity: str | None = None  # 'easy' | 'moderate' | 'involved'
    estimated_time_min: int | None = None  # derived from step count + method signals
    time_effort: TimeEffortProfile | None = None  # full time/effort profile from parse_time_effort
    rerank_score: float | None = None  # cross-encoder relevance score (paid+ only, None for free tier)


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
    orch_fallback: bool = False  # True when orch budget exhausted; fell back to local LLM


class RecipeJobQueued(BaseModel):
    job_id: str
    status: str = "queued"


class RecipeJobStatus(BaseModel):
    job_id: str
    status: str
    result: RecipeResult | None = None
    error: str | None = None


class NutritionFilters(BaseModel):
    """Optional per-serving upper bounds for macro filtering. None = no filter."""
    max_calories: float | None = None
    max_sugar_g: float | None = None
    max_carbs_g: float | None = None
    max_sodium_mg: float | None = None


class RecipeRequest(BaseModel):
    pantry_items: list[str]
    # Maps product name → secondary state label for items past nominal expiry
    # but still within their secondary use window (e.g. {"Bread": "stale"}).
    # Used by the recipe engine to boost recipes suited to those specific states.
    secondary_pantry_items: dict[str, str] = Field(default_factory=dict)
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
    exclude_ingredients: list[str] = Field(default_factory=list)
    shopping_mode: bool = False
    pantry_match_only: bool = False  # when True, only return recipes with zero missing ingredients
    complexity_filter: str | None = None  # 'easy' | 'moderate' | 'involved' — None = any
    max_time_min: int | None = None  # filter by estimated cooking time ceiling
    max_total_min: int | None = None  # filter by parsed total time (active + passive)
    max_active_min: int | None = None  # filter by hands-on active time only
    unit_system: str = "metric"  # "metric" | "imperial"


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


class StreamTokenRequest(BaseModel):
    """Request body for POST /recipes/stream-token.

    Pantry items and dietary constraints are fetched from the DB at request
    time — the client does not supply them here.
    """
    level: int = Field(4, ge=3, le=4, description="Recipe level: 3=styled, 4=wildcard")
    wildcard_confirmed: bool = Field(False, description="Required true for level 4")


class StreamTokenResponse(BaseModel):
    """Response from POST /recipes/stream-token.

    The frontend opens EventSource at stream_url?token=<token> to receive
    SSE chunks directly from the coordinator.
    """
    stream_url: str
    token: str
    expires_in_s: int
