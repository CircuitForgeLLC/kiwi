"""Pydantic schemas for the shopping list endpoints."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ShoppingItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    source: str = "manual"
    recipe_id: Optional[int] = None
    sort_order: int = 0


class ShoppingItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    checked: Optional[bool] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class GroceryLinkOut(BaseModel):
    ingredient: str
    retailer: str
    url: str


class ShoppingItemResponse(BaseModel):
    id: int
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    category: Optional[str]
    checked: bool
    notes: Optional[str]
    source: str
    recipe_id: Optional[int]
    sort_order: int
    created_at: str
    updated_at: str
    grocery_links: list[GroceryLinkOut] = []


class BulkAddFromRecipeRequest(BaseModel):
    recipe_id: int
    include_covered: bool = False  # if True, add pantry-covered items too


class ConfirmPurchaseRequest(BaseModel):
    """Move a checked item into pantry inventory."""
    location: str = "pantry"
    quantity: Optional[float] = None   # override the list quantity
    unit: Optional[str] = None
