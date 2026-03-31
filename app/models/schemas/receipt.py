"""Receipt schemas (integer IDs, SQLite-compatible)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReceiptResponse(BaseModel):
    id: int
    filename: str
    status: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ApproveOCRRequest(BaseModel):
    """Approve staged OCR items for inventory population.

    item_indices: which items (by 0-based index) to approve.
                  Omit or pass null to approve all items.
    location:     pantry location for created inventory items.
    """
    item_indices: Optional[List[int]] = Field(
        default=None,
        description="0-based indices of items to approve. Null = approve all.",
    )
    location: str = Field(default="pantry")


class ApprovedInventoryItem(BaseModel):
    inventory_id: int
    product_name: str
    quantity: float
    location: str
    expiration_date: Optional[str] = None


class ApproveOCRResponse(BaseModel):
    receipt_id: int
    approved: int
    skipped: int
    inventory_items: List[ApprovedInventoryItem]
