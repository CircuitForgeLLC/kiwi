"""Receipt upload, OCR, and quality endpoints."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.cloud_session import CloudUser, get_session
from app.core.config import settings
from app.db.session import get_store
from app.db.store import Store
from app.models.schemas.receipt import ReceiptResponse
from app.models.schemas.quality import QualityAssessment
from app.tiers import can_use

router = APIRouter()


async def _save_upload(file: UploadFile, dest_dir: Path) -> Path:
    dest = dest_dir / f"{uuid.uuid4()}_{file.filename}"
    async with aiofiles.open(dest, "wb") as f:
        await f.write(await file.read())
    return dest


@router.post("/", response_model=ReceiptResponse, status_code=201)
async def upload_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    settings.ensure_dirs()
    saved = await _save_upload(file, settings.UPLOAD_DIR)
    receipt = await asyncio.to_thread(
        store.create_receipt, file.filename, str(saved)
    )
    # Only queue OCR if the feature is enabled server-side AND the user's tier allows it.
    # Check tier here, not inside the background task — once dispatched it can't be cancelled.
    ocr_allowed = settings.ENABLE_OCR and can_use("receipt_ocr", session.tier, session.has_byok)
    if ocr_allowed:
        background_tasks.add_task(_process_receipt_ocr, receipt["id"], saved, store)
    return ReceiptResponse.model_validate(receipt)


@router.post("/batch", response_model=List[ReceiptResponse], status_code=201)
async def upload_receipts_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    settings.ensure_dirs()
    ocr_allowed = settings.ENABLE_OCR and can_use("receipt_ocr", session.tier, session.has_byok)
    results = []
    for file in files:
        saved = await _save_upload(file, settings.UPLOAD_DIR)
        receipt = await asyncio.to_thread(
            store.create_receipt, file.filename, str(saved)
        )
        if ocr_allowed:
            background_tasks.add_task(_process_receipt_ocr, receipt["id"], saved, store)
        results.append(ReceiptResponse.model_validate(receipt))
    return results


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(receipt_id: int, store: Store = Depends(get_store)):
    receipt = await asyncio.to_thread(store.get_receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return ReceiptResponse.model_validate(receipt)


@router.get("/", response_model=List[ReceiptResponse])
async def list_receipts(
    limit: int = 50, offset: int = 0, store: Store = Depends(get_store)
):
    receipts = await asyncio.to_thread(store.list_receipts, limit, offset)
    return [ReceiptResponse.model_validate(r) for r in receipts]


@router.get("/{receipt_id}/quality", response_model=QualityAssessment)
async def get_receipt_quality(receipt_id: int, store: Store = Depends(get_store)):
    qa = await asyncio.to_thread(
        store._fetch_one,
        "SELECT * FROM quality_assessments WHERE receipt_id = ?",
        (receipt_id,),
    )
    if not qa:
        raise HTTPException(status_code=404, detail="Quality assessment not found")
    return QualityAssessment.model_validate(qa)


async def _process_receipt_ocr(receipt_id: int, image_path: Path, store: Store) -> None:
    """Background task: run OCR pipeline on an uploaded receipt."""
    try:
        await asyncio.to_thread(store.update_receipt_status, receipt_id, "processing")
        from app.services.receipt_service import ReceiptService
        service = ReceiptService(store)
        await service.process(receipt_id, image_path)
    except Exception as exc:
        await asyncio.to_thread(
            store.update_receipt_status, receipt_id, "error", str(exc)
        )
