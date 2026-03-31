"""
Receipt processing service — orchestrates the OCR pipeline.

Pipeline stages:
  1. Preprocess  — enhance image, convert to PNG
  2. Quality     — score image; abort to 'low_quality' if below threshold
  3. OCR         — VisionLanguageOCR extracts structured data
  4. Persist     — flatten result into receipt_data table
  5. Stage       — set status to 'staged'; items await human approval

Items are NOT added to inventory automatically. Use the
POST /receipts/{id}/ocr/approve endpoint to commit approved items.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.db.store import Store

logger = logging.getLogger(__name__)


def _flatten_ocr_result(result: dict[str, Any]) -> dict[str, Any]:
    """Map nested VisionLanguageOCR output to the flat receipt_data schema."""
    merchant = result.get("merchant") or {}
    transaction = result.get("transaction") or {}
    totals = result.get("totals") or {}
    return {
        "merchant_name":    merchant.get("name"),
        "merchant_address": merchant.get("address"),
        "merchant_phone":   merchant.get("phone"),
        "transaction_date": transaction.get("date"),
        "transaction_time": transaction.get("time"),
        "receipt_number":   transaction.get("receipt_number"),
        "register_number":  transaction.get("register"),
        "cashier_name":     transaction.get("cashier"),
        "items":            result.get("items") or [],
        "subtotal":         totals.get("subtotal"),
        "tax":              totals.get("tax"),
        "discount":         totals.get("discount"),
        "total":            totals.get("total"),
        "payment_method":   totals.get("payment_method"),
        "amount_paid":      totals.get("amount_paid"),
        "change_given":     totals.get("change"),
        "raw_text":         result.get("raw_text"),
        "confidence_scores": result.get("confidence") or {},
        "warnings":         result.get("warnings") or [],
    }


class ReceiptService:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def process(self, receipt_id: int, image_path: Path) -> None:
        """Run the full OCR pipeline for a receipt image.

        Stages run synchronously inside asyncio.to_thread so SQLite and the
        VLM (which uses torch) both stay off the async event loop.
        """
        import asyncio
        await asyncio.to_thread(self._run_pipeline, receipt_id, image_path)

    def _run_pipeline(self, receipt_id: int, image_path: Path) -> None:
        from app.core.config import settings
        from app.services.image_preprocessing.enhancement import ImageEnhancer
        from app.services.image_preprocessing.format_conversion import FormatConverter
        from app.services.quality.assessment import QualityAssessor

        # ── Stage 1: Preprocess ───────────────────────────────────────────────
        enhancer = ImageEnhancer()
        converter = FormatConverter()
        enhanced = enhancer.enhance(image_path)
        processed_path = converter.to_png(enhanced)

        # ── Stage 2: Quality assessment ───────────────────────────────────────
        assessor = QualityAssessor()
        assessment = assessor.assess(processed_path)
        self.store.upsert_quality_assessment(
            receipt_id,
            overall_score=assessment["overall_score"],
            is_acceptable=assessment["is_acceptable"],
            metrics=assessment.get("metrics", {}),
            suggestions=assessment.get("suggestions", []),
        )

        if not assessment["is_acceptable"]:
            self.store.update_receipt_status(receipt_id, "low_quality")
            logger.warning(
                "Receipt %s: quality too low for OCR (score=%.1f) — %s",
                receipt_id, assessment["overall_score"],
                "; ".join(assessment.get("suggestions", [])),
            )
            return

        if not settings.ENABLE_OCR:
            self.store.update_receipt_status(receipt_id, "processed")
            logger.info("Receipt %s: quality OK but ENABLE_OCR=false — skipping OCR", receipt_id)
            return

        # ── Stage 3: OCR extraction ───────────────────────────────────────────
        from app.services.ocr.vl_model import VisionLanguageOCR
        ocr = VisionLanguageOCR()
        result = ocr.extract_receipt_data(str(processed_path))

        if result.get("error"):
            self.store.update_receipt_status(receipt_id, "error", result["error"])
            logger.error("Receipt %s: OCR failed — %s", receipt_id, result["error"])
            return

        # ── Stage 4: Persist extracted data ───────────────────────────────────
        flat = _flatten_ocr_result(result)
        self.store.upsert_receipt_data(receipt_id, flat)

        item_count = len(flat.get("items") or [])

        # ── Stage 5: Stage for human approval ────────────────────────────────
        self.store.update_receipt_status(receipt_id, "staged")
        logger.info(
            "Receipt %s: OCR complete — %d item(s) staged for review "
            "(confidence=%.2f)",
            receipt_id, item_count,
            (result.get("confidence") or {}).get("overall", 0.0),
        )
