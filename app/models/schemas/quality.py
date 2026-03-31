"""Quality assessment schemas (integer IDs, SQLite-compatible)."""
from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel


class QualityAssessment(BaseModel):
    id: int
    receipt_id: int
    overall_score: float
    is_acceptable: bool
    metrics: Dict[str, Any] = {}
    improvement_suggestions: List[str] = []
    created_at: str

    model_config = {"from_attributes": True}
