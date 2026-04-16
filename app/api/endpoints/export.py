"""Export endpoints — CSV and JSON export of user data."""
from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime, timezone

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


@router.get("/json")
async def export_full_json(store: Store = Depends(get_store)):
    """Export full pantry inventory + saved recipes as a single JSON file.

    Intended for data portability — users can import this into another
    Kiwi instance or keep it as an offline backup.
    """
    inventory, saved = await asyncio.gather(
        asyncio.to_thread(store.list_inventory),
        asyncio.to_thread(store.get_saved_recipes, 1000, 0),
    )

    export_doc = {
        "kiwi_export": {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "inventory": [dict(row) for row in inventory],
            "saved_recipes": [dict(row) for row in saved],
        }
    }

    body = json.dumps(export_doc, default=str, indent=2)
    filename = f"kiwi-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    return StreamingResponse(
        iter([body]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
