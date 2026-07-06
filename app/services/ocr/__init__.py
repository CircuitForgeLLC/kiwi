"""OCR services for receipt text extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vl_model import VisionLanguageOCR

__all__ = ["VisionLanguageOCR"]
