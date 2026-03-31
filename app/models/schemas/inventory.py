"""Pydantic schemas for inventory management (integer IDs, SQLite-compatible)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Tags ──────────────────────────────────────────────────────────────────────

class TagCreate(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=7)
    category: Optional[str] = None


class TagResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    color: Optional[str]
    category: Optional[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Products ──────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str = Field(..., max_length=500)
    barcode: Optional[str] = Field(None, max_length=50)
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    nutrition_data: Dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    source_data: Dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    nutrition_data: Optional[Dict[str, Any]] = None


class ProductResponse(BaseModel):
    id: int
    barcode: Optional[str]
    name: str
    brand: Optional[str]
    category: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    nutrition_data: Dict[str, Any]
    source: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Inventory Items ───────────────────────────────────────────────────────────

class InventoryItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(default=1.0, gt=0)
    unit: str = "count"
    location: str
    sublocation: Optional[str] = None
    purchase_date: Optional[date] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None
    source: str = "manual"


class InventoryItemUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = None
    location: Optional[str] = None
    sublocation: Optional[str] = None
    expiration_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class InventoryItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    quantity: float
    unit: str
    location: str
    sublocation: Optional[str]
    purchase_date: Optional[str]
    expiration_date: Optional[str]
    status: str
    notes: Optional[str]
    source: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Barcode scan ──────────────────────────────────────────────────────────────

class BarcodeScanResult(BaseModel):
    barcode: str
    barcode_type: str
    product: Optional[ProductResponse]
    inventory_item: Optional[InventoryItemResponse]
    added_to_inventory: bool
    message: str


class BarcodeScanResponse(BaseModel):
    success: bool
    barcodes_found: int
    results: List[BarcodeScanResult]
    message: str


# ── Stats ─────────────────────────────────────────────────────────────────────

class InventoryStats(BaseModel):
    total_items: int
    available_items: int
    expiring_soon: int
    expired_items: int
    locations: Dict[str, int]
