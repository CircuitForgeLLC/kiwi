"""Pydantic schemas for visual label capture (kiwi#79)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LabelCaptureResponse(BaseModel):
    """Extraction result returned after the user photographs a nutrition label."""
    barcode: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    serving_size_g: Optional[float] = None
    calories: Optional[float] = None
    fat_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    sugar_g: Optional[float] = None
    fiber_g: Optional[float] = None
    protein_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    ingredient_names: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    needs_review: bool = True   # True when confidence < REVIEW_THRESHOLD


class LabelConfirmRequest(BaseModel):
    """User-confirmed extraction to save to the local product cache."""
    barcode: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    serving_size_g: Optional[float] = None
    calories: Optional[float] = None
    fat_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    sugar_g: Optional[float] = None
    fiber_g: Optional[float] = None
    protein_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    ingredient_names: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    # When True the confirmed product is also added to inventory
    location: str = "pantry"
    quantity: float = 1.0
    auto_add: bool = True


class LabelConfirmResponse(BaseModel):
    """Result of confirming a captured product."""
    ok: bool
    barcode: str
    product_id: Optional[int] = None
    inventory_item_id: Optional[int] = None
    message: str
