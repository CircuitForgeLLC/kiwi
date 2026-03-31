"""Export endpoints — CSV/Excel of receipt and inventory data."""
from __future__ import annotations

import asyncio
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.db.session import get_store
from app.db.store import Store

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/receipts/csv")
async def export_receipts_csv(store: Store = Depends(get_store)):
    receipts = await asyncio.to_thread(store.list_receipts, 1000, 0)
    output = io.StringIO()
    fields = ["id", "filename", "status", "created_at", "updated_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(receipts)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts.csv"},
    )


@router.get("/inventory/csv")
async def export_inventory_csv(store: Store = Depends(get_store)):
    items = await asyncio.to_thread(store.list_inventory)
    output = io.StringIO()
    fields = ["id", "product_name", "barcode", "category", "quantity", "unit",
              "location", "expiration_date", "status", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(items)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"},
    )
