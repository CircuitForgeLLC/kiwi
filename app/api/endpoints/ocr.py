"""OCR status, trigger, and approval endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.cloud_session import CloudUser, get_session
from app.core.config import settings
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.receipt import (
    ApproveOCRRequest,
    ApproveOCRResponse,
    ApprovedInventoryItem,
)
from app.services.expiration_predictor import ExpirationPredictor
from app.tiers import can_use
from app.utils.units import normalize_to_metric

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/{receipt_id}/ocr/status")
async def get_ocr_status(receipt_id: int, store: Store = Depends(get_store)):
    receipt = await asyncio.to_thread(store.get_receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    rd = await asyncio.to_thread(
        store._fetch_one,
        "SELECT id, processing_time FROM receipt_data WHERE receipt_id = ?",
        (receipt_id,),
    )
    return {
        "receipt_id": receipt_id,
        "status": receipt["status"],
        "ocr_complete": rd is not None,
        "ocr_enabled": settings.ENABLE_OCR,
    }


# ── Trigger ───────────────────────────────────────────────────────────────────

@router.post("/{receipt_id}/ocr/trigger")
async def trigger_ocr(
    receipt_id: int,
    background_tasks: BackgroundTasks,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Manually trigger OCR processing for an already-uploaded receipt."""
    if not can_use("receipt_ocr", session.tier, session.has_byok):
        raise HTTPException(
            status_code=403,
            detail="Receipt OCR requires Paid tier or a configured local LLM backend (BYOK).",
        )
    if not settings.ENABLE_OCR:
        raise HTTPException(status_code=503, detail="OCR not enabled on this server.")

    receipt = await asyncio.to_thread(store.get_receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt["status"] == "processing":
        raise HTTPException(status_code=409, detail="OCR already in progress for this receipt.")

    image_path = Path(receipt["original_path"])
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk.")

    async def _run() -> None:
        try:
            await asyncio.to_thread(store.update_receipt_status, receipt_id, "processing")
            from app.services.receipt_service import ReceiptService
            await ReceiptService(store).process(receipt_id, image_path)
        except Exception as exc:
            logger.exception("OCR pipeline failed for receipt %s", receipt_id)
            await asyncio.to_thread(store.update_receipt_status, receipt_id, "error", str(exc))

    background_tasks.add_task(_run)
    return {"receipt_id": receipt_id, "status": "queued"}


# ── Data ──────────────────────────────────────────────────────────────────────

@router.get("/{receipt_id}/ocr/data")
async def get_ocr_data(receipt_id: int, store: Store = Depends(get_store)):
    rd = await asyncio.to_thread(
        store._fetch_one,
        "SELECT * FROM receipt_data WHERE receipt_id = ?",
        (receipt_id,),
    )
    if not rd:
        raise HTTPException(status_code=404, detail="No OCR data for this receipt")
    return rd


# ── Approve ───────────────────────────────────────────────────────────────────

@router.post("/{receipt_id}/ocr/approve", response_model=ApproveOCRResponse)
async def approve_ocr_items(
    receipt_id: int,
    body: ApproveOCRRequest,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Commit reviewed OCR line items into inventory.

    Reads items from receipt_data, optionally filtered by item_indices,
    and creates inventory entries. Receipt status moves to 'processed'.
    """
    receipt = await asyncio.to_thread(store.get_receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt["status"] not in ("staged", "processed"):
        raise HTTPException(
            status_code=409,
            detail=f"Receipt is not staged for approval (status={receipt['status']}).",
        )

    rd = await asyncio.to_thread(
        store._fetch_one,
        "SELECT items, transaction_date FROM receipt_data WHERE receipt_id = ?",
        (receipt_id,),
    )
    if not rd:
        raise HTTPException(status_code=404, detail="No OCR data found for this receipt.")

    raw_items: list[dict[str, Any]] = json.loads(rd["items"] or "[]")
    if not raw_items:
        raise HTTPException(status_code=422, detail="No items found in OCR data.")

    # Filter to requested indices, or use all
    if body.item_indices is not None:
        invalid = [i for i in body.item_indices if i >= len(raw_items) or i < 0]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Item indices out of range: {invalid} (receipt has {len(raw_items)} items)",
            )
        selected = [(i, raw_items[i]) for i in body.item_indices]
        skipped = len(raw_items) - len(selected)
    else:
        selected = list(enumerate(raw_items))
        skipped = 0

    created = await asyncio.to_thread(
        _commit_items, store, receipt_id, selected, body.location, rd.get("transaction_date")
    )

    await asyncio.to_thread(store.update_receipt_status, receipt_id, "processed")

    return ApproveOCRResponse(
        receipt_id=receipt_id,
        approved=len(created),
        skipped=skipped,
        inventory_items=created,
    )


def _commit_items(
    store: Store,
    receipt_id: int,
    selected: list[tuple[int, dict[str, Any]]],
    location: str,
    transaction_date: str | None,
) -> list[ApprovedInventoryItem]:
    """Create product + inventory entries for approved OCR line items.

    Runs synchronously inside asyncio.to_thread.
    """
    predictor = ExpirationPredictor()

    purchase_date: date | None = None
    if transaction_date:
        try:
            purchase_date = date.fromisoformat(transaction_date)
        except ValueError:
            logger.warning("Could not parse transaction_date %r", transaction_date)

    created: list[ApprovedInventoryItem] = []

    for _idx, item in selected:
        name = (item.get("name") or "").strip()
        if not name:
            logger.debug("Skipping nameless item at index %d", _idx)
            continue

        category = (item.get("category") or "").strip()
        quantity = float(item.get("quantity") or 1.0)

        raw_unit = (item.get("unit") or "each").strip()
        metric_qty, base_unit = normalize_to_metric(quantity, raw_unit)

        product, _ = store.get_or_create_product(
            name,
            category=category or None,
            source="receipt_ocr",
        )

        exp = predictor.predict_expiration(
            category, location,
            purchase_date=purchase_date,
            product_name=name,
        )

        inv = store.add_inventory_item(
            product["id"],
            location,
            quantity=metric_qty,
            unit=base_unit,
            receipt_id=receipt_id,
            purchase_date=str(purchase_date) if purchase_date else None,
            expiration_date=str(exp) if exp else None,
            source="receipt_ocr",
        )

        created.append(ApprovedInventoryItem(
            inventory_id=inv["id"],
            product_name=name,
            quantity=quantity,
            location=location,
            expiration_date=str(exp) if exp else None,
        ))

    return created
