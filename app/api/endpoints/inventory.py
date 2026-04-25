"""Inventory API endpoints — products, items, barcode scanning, tags, stats."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.cloud_session import CloudUser, _auth_label, get_session

log = logging.getLogger(__name__)
from app.db.session import get_store
from app.services.expiration_predictor import ExpirationPredictor

_predictor = ExpirationPredictor()
from app.db.store import Store
from app.models.schemas.inventory import (
    BarcodeScanResponse,
    BulkAddByNameRequest,
    BulkAddByNameResponse,
    BulkAddItemResult,
    DiscardRequest,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryStats,
    PartialConsumeRequest,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    TagCreate,
    TagResponse,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich_item(item: dict, user_constraints: list[str] | None = None) -> dict:
    """Attach computed fields: opened_expiry_date, secondary_state/uses/warning/discard_signs."""
    from datetime import date, timedelta
    opened = item.get("opened_date")
    if opened:
        days = _predictor.days_after_opening(item.get("category"))
        if days is not None:
            try:
                opened_expiry = date.fromisoformat(opened) + timedelta(days=days)
                item = {**item, "opened_expiry_date": str(opened_expiry)}
            except ValueError:
                pass
    if "opened_expiry_date" not in item:
        item = {**item, "opened_expiry_date": None}

    # Secondary use window — check sell-by date (not opened expiry).
    # Apply dietary constraint filter (e.g. wine suppressed for halal/alcohol-free).
    sec = _predictor.secondary_state(item.get("category"), item.get("expiration_date"))
    sec = _predictor.filter_secondary_by_constraints(sec, user_constraints or [])
    item = {
        **item,
        "secondary_state": sec["label"] if sec else None,
        "secondary_uses": sec["uses"] if sec else None,
        "secondary_warning": sec["warning"] if sec else None,
        "secondary_discard_signs": sec["discard_signs"] if sec else None,
    }
    return item


# ── Products ──────────────────────────────────────────────────────────────────

@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductCreate, store: Store = Depends(get_store)):
    product, _ = await asyncio.to_thread(
        store.get_or_create_product,
        body.name,
        body.barcode,
        brand=body.brand,
        category=body.category,
        description=body.description,
        image_url=body.image_url,
        nutrition_data=body.nutrition_data,
        source=body.source,
        source_data=body.source_data,
    )
    return ProductResponse.model_validate(product)


@router.get("/products", response_model=List[ProductResponse])
async def list_products(store: Store = Depends(get_store)):
    products = await asyncio.to_thread(store.list_products)
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, store: Store = Depends(get_store)):
    product = await asyncio.to_thread(store.get_product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.get("/products/barcode/{barcode}", response_model=ProductResponse)
async def get_product_by_barcode(barcode: str, store: Store = Depends(get_store)):
    from app.db import store as store_module  # avoid circular
    product = await asyncio.to_thread(
        store._fetch_one, "SELECT * FROM products WHERE barcode = ?", (barcode,)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int, body: ProductUpdate, store: Store = Depends(get_store)
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        product = await asyncio.to_thread(store.get_product, product_id)
    else:
        import json
        sets = ", ".join(f"{k} = ?" for k in updates)
        values = []
        for k, v in updates.items():
            values.append(json.dumps(v) if isinstance(v, dict) else v)
        values.append(product_id)
        await asyncio.to_thread(
            store.conn.execute,
            f"UPDATE products SET {sets}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        store.conn.commit()
        product = await asyncio.to_thread(store.get_product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, store: Store = Depends(get_store)):
    existing = await asyncio.to_thread(store.get_product, product_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
    await asyncio.to_thread(
        store.conn.execute, "DELETE FROM products WHERE id = ?", (product_id,)
    )
    store.conn.commit()


# ── Inventory items ───────────────────────────────────────────────────────────

@router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    body: InventoryItemCreate,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    log.info("add_item auth=%s tier=%s product_id=%s", _auth_label(session.user_id), session.tier, body.product_id)
    item = await asyncio.to_thread(
        store.add_inventory_item,
        body.product_id,
        body.location,
        quantity=body.quantity,
        unit=body.unit,
        sublocation=body.sublocation,
        purchase_date=str(body.purchase_date) if body.purchase_date else None,
        expiration_date=str(body.expiration_date) if body.expiration_date else None,
        notes=body.notes,
        source=body.source,
    )
    # RETURNING * omits joined columns (product_name, barcode, category).
    # Re-fetch with the products JOIN so the response is fully populated (#99).
    full_item = await asyncio.to_thread(store.get_inventory_item, item["id"])
    return InventoryItemResponse.model_validate(full_item)


@router.post("/items/bulk-add-by-name", response_model=BulkAddByNameResponse)
async def bulk_add_items_by_name(body: BulkAddByNameRequest, store: Store = Depends(get_store)):
    """Create pantry items from a list of ingredient names (no barcode required).

    Uses get_or_create_product so re-adding an existing product is idempotent.
    """
    results: list[BulkAddItemResult] = []
    for entry in body.items:
        try:
            product, _ = await asyncio.to_thread(
                store.get_or_create_product, entry.name, None, source="manual"
            )
            item = await asyncio.to_thread(
                store.add_inventory_item,
                product["id"],
                entry.location,
                quantity=entry.quantity,
                unit=entry.unit,
                source="manual",
            )
            results.append(BulkAddItemResult(name=entry.name, ok=True, item_id=item["id"]))
        except Exception as exc:
            results.append(BulkAddItemResult(name=entry.name, ok=False, error=str(exc)))

    added = sum(1 for r in results if r.ok)
    return BulkAddByNameResponse(added=added, failed=len(results) - added, results=results)


@router.get("/items", response_model=List[InventoryItemResponse])
async def list_inventory_items(
    location: Optional[str] = None,
    item_status: str = "available",
    store: Store = Depends(get_store),
):
    items = await asyncio.to_thread(store.list_inventory, location, item_status)
    return [InventoryItemResponse.model_validate(_enrich_item(i)) for i in items]


@router.get("/items/expiring", response_model=List[InventoryItemResponse])
async def get_expiring_items(days: int = 7, store: Store = Depends(get_store)):
    items = await asyncio.to_thread(store.expiring_soon, days)
    return [InventoryItemResponse.model_validate(_enrich_item(i)) for i in items]


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(item_id: int, store: Store = Depends(get_store)):
    item = await asyncio.to_thread(store.get_inventory_item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return InventoryItemResponse.model_validate(_enrich_item(item))


@router.patch("/items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int, body: InventoryItemUpdate, store: Store = Depends(get_store)
):
    updates = body.model_dump(exclude_none=True)
    if "purchase_date" in updates and updates["purchase_date"]:
        updates["purchase_date"] = str(updates["purchase_date"])
    if "expiration_date" in updates and updates["expiration_date"]:
        updates["expiration_date"] = str(updates["expiration_date"])
    if "opened_date" in updates and updates["opened_date"]:
        updates["opened_date"] = str(updates["opened_date"])
    item = await asyncio.to_thread(store.update_inventory_item, item_id, **updates)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return InventoryItemResponse.model_validate(_enrich_item(item))


@router.post("/items/{item_id}/open", response_model=InventoryItemResponse)
async def mark_item_opened(item_id: int, store: Store = Depends(get_store)):
    """Record that this item was opened today, triggering secondary shelf-life tracking."""
    from datetime import date
    item = await asyncio.to_thread(
        store.update_inventory_item,
        item_id,
        opened_date=str(date.today()),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return InventoryItemResponse.model_validate(_enrich_item(item))


@router.post("/items/{item_id}/consume", response_model=InventoryItemResponse)
async def consume_item(
    item_id: int,
    body: Optional[PartialConsumeRequest] = None,
    store: Store = Depends(get_store),
):
    """Consume an inventory item fully or partially.

    When body.quantity is provided, decrements by that amount and only marks
    status=consumed when quantity reaches zero. Omit body to consume all.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    if body is not None:
        item = await asyncio.to_thread(
            store.partial_consume_item, item_id, body.quantity, now
        )
    else:
        item = await asyncio.to_thread(
            store.update_inventory_item,
            item_id,
            status="consumed",
            consumed_at=now,
        )
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return InventoryItemResponse.model_validate(_enrich_item(item))


@router.post("/items/{item_id}/discard", response_model=InventoryItemResponse)
async def discard_item(
    item_id: int,
    body: DiscardRequest = DiscardRequest(),
    store: Store = Depends(get_store),
):
    """Mark an item as discarded (not used, spoiled, etc).

    Optional reason field accepts free text or a preset label
    ('not used', 'spoiled', 'excess', 'other').
    """
    from datetime import datetime, timezone
    item = await asyncio.to_thread(
        store.update_inventory_item,
        item_id,
        status="discarded",
        consumed_at=datetime.now(timezone.utc).isoformat(),
        disposal_reason=body.reason,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return InventoryItemResponse.model_validate(_enrich_item(item))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(item_id: int, store: Store = Depends(get_store)):
    existing = await asyncio.to_thread(store.get_inventory_item, item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    await asyncio.to_thread(
        store.conn.execute, "DELETE FROM inventory_items WHERE id = ?", (item_id,)
    )
    store.conn.commit()


# ── Barcode scanning ──────────────────────────────────────────────────────────

class BarcodeScanTextRequest(BaseModel):
    barcode: str
    location: str = "pantry"
    quantity: float = 1.0
    auto_add_to_inventory: bool = True


@router.post("/scan/text", response_model=BarcodeScanResponse)
async def scan_barcode_text(
    body: BarcodeScanTextRequest,
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Scan a barcode from a text string (e.g. from a hardware scanner or manual entry)."""
    log.info("scan auth=%s tier=%s barcode=%r", _auth_label(session.user_id), session.tier, body.barcode)
    from app.services.openfoodfacts import OpenFoodFactsService
    from app.services.expiration_predictor import ExpirationPredictor

    off = OpenFoodFactsService()
    predictor = ExpirationPredictor()
    product_info = await off.lookup_product(body.barcode)
    inventory_item = None

    if product_info and body.auto_add_to_inventory:
        product, _ = await asyncio.to_thread(
            store.get_or_create_product,
            product_info.get("name", body.barcode),
            body.barcode,
            brand=product_info.get("brand"),
            category=product_info.get("category"),
            nutrition_data=product_info.get("nutrition_data", {}),
            source="openfoodfacts",
            source_data=product_info,
        )
        exp = predictor.predict_expiration(
            product_info.get("category", ""),
            body.location,
            product_name=product_info.get("name", body.barcode),
            tier=session.tier,
            has_byok=session.has_byok,
        )
        # Use OFFs pack size when detected; caller-supplied quantity is a fallback
        resolved_qty = product_info.get("pack_quantity") or body.quantity
        resolved_unit = product_info.get("pack_unit") or "count"
        inventory_item = await asyncio.to_thread(
            store.add_inventory_item,
            product["id"], body.location,
            quantity=resolved_qty,
            unit=resolved_unit,
            expiration_date=str(exp) if exp else None,
            source="barcode_scan",
        )
        result_product = ProductResponse.model_validate(product)
    else:
        result_product = None

    product_found = product_info is not None
    return BarcodeScanResponse(
        success=True,
        barcodes_found=1,
        results=[{
            "barcode": body.barcode,
            "barcode_type": "text",
            "product": result_product,
            "inventory_item": InventoryItemResponse.model_validate(inventory_item) if inventory_item else None,
            "added_to_inventory": inventory_item is not None,
            "needs_manual_entry": not product_found,
            "message": "Added to inventory" if inventory_item else "Not found in any product database — add manually",
        }],
        message="Barcode processed",
    )


@router.post("/scan", response_model=BarcodeScanResponse)
async def scan_barcode_image(
    file: UploadFile = File(...),
    auto_add_to_inventory: bool = Form(True),
    location: str = Form("pantry"),
    quantity: float = Form(1.0),
    store: Store = Depends(get_store),
    session: CloudUser = Depends(get_session),
):
    """Scan a barcode from an uploaded image. Requires Phase 2 scanner integration."""
    log.info("scan_image auth=%s tier=%s", _auth_label(session.user_id), session.tier)
    temp_dir = Path("/tmp/kiwi_barcode_scans")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"{uuid.uuid4()}_{file.filename}"
    try:
        async with aiofiles.open(temp_file, "wb") as f:
            await f.write(await file.read())
        from app.services.barcode_scanner import BarcodeScanner
        from app.services.openfoodfacts import OpenFoodFactsService
        from app.services.expiration_predictor import ExpirationPredictor

        barcodes = await asyncio.to_thread(BarcodeScanner().scan_image, temp_file)
        if not barcodes:
            return BarcodeScanResponse(
                success=False, barcodes_found=0, results=[],
                message="No barcodes detected in image"
            )

        off = OpenFoodFactsService()
        predictor = ExpirationPredictor()
        results = []
        for bc in barcodes:
            code = bc["data"]
            product_info = await off.lookup_product(code)
            inventory_item = None
            if product_info and auto_add_to_inventory:
                product, _ = await asyncio.to_thread(
                    store.get_or_create_product,
                    product_info.get("name", code),
                    code,
                    brand=product_info.get("brand"),
                    category=product_info.get("category"),
                    nutrition_data=product_info.get("nutrition_data", {}),
                    source="openfoodfacts",
                    source_data=product_info,
                )
                exp = predictor.predict_expiration(
                    product_info.get("category", ""),
                    location,
                    product_name=product_info.get("name", code),
                    tier=session.tier,
            has_byok=session.has_byok,
                )
                resolved_qty = product_info.get("pack_quantity") or quantity
                resolved_unit = product_info.get("pack_unit") or "count"
                inventory_item = await asyncio.to_thread(
                    store.add_inventory_item,
                    product["id"], location,
                    quantity=resolved_qty,
                    unit=resolved_unit,
                    expiration_date=str(exp) if exp else None,
                    source="barcode_scan",
                )
            results.append({
                "barcode": code,
                "barcode_type": bc.get("type", "unknown"),
                "product": ProductResponse.model_validate(product) if product_info else None,
                "inventory_item": InventoryItemResponse.model_validate(inventory_item) if inventory_item else None,
                "added_to_inventory": inventory_item is not None,
                "message": "Added to inventory" if inventory_item else "Barcode scanned",
            })
        return BarcodeScanResponse(
            success=True, barcodes_found=len(barcodes), results=results,
            message=f"Processed {len(barcodes)} barcode(s)"
        )
    finally:
        if temp_file.exists():
            temp_file.unlink()


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(body: TagCreate, store: Store = Depends(get_store)):
    cur = await asyncio.to_thread(
        store.conn.execute,
        "INSERT INTO tags (name, slug, description, color, category) VALUES (?,?,?,?,?) RETURNING *",
        (body.name, body.slug, body.description, body.color, body.category),
    )
    store.conn.commit()
    import sqlite3; store.conn.row_factory = sqlite3.Row
    return TagResponse.model_validate(store._row_to_dict(cur.fetchone()))


@router.get("/tags", response_model=List[TagResponse])
async def list_tags(
    category: Optional[str] = None, store: Store = Depends(get_store)
):
    if category:
        tags = await asyncio.to_thread(
            store._fetch_all, "SELECT * FROM tags WHERE category = ? ORDER BY name", (category,)
        )
    else:
        tags = await asyncio.to_thread(
            store._fetch_all, "SELECT * FROM tags ORDER BY name"
        )
    return [TagResponse.model_validate(t) for t in tags]


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.post("/recalculate-expiry")
async def recalculate_expiry(
    session: CloudUser = Depends(get_session),
    store: Store = Depends(get_store),
) -> dict:
    """Re-run the expiration predictor over all available inventory items.

    Uses each item's stored purchase_date and current location. Safe to call
    multiple times — idempotent per session.
    """
    def _run(s: Store) -> tuple[int, int]:
        return s.recalculate_expiry(tier=session.tier, has_byok=session.has_byok)

    updated, skipped = await asyncio.to_thread(_run, store)
    return {"updated": updated, "skipped": skipped}


@router.get("/stats", response_model=InventoryStats)
async def get_inventory_stats(store: Store = Depends(get_store)):
    def _stats():
        rows = store._fetch_all(
            """SELECT status, location, COUNT(*) as cnt
               FROM inventory_items GROUP BY status, location"""
        )
        total = sum(r["cnt"] for r in rows)
        available = sum(r["cnt"] for r in rows if r["status"] == "available")
        expired = sum(r["cnt"] for r in rows if r["status"] == "expired")
        expiring = len(store.expiring_soon(7))
        locations = {}
        for r in rows:
            if r["status"] == "available":
                locations[r["location"]] = locations.get(r["location"], 0) + r["cnt"]
        return {
            "total_items": total,
            "available_items": available,
            "expiring_soon": expiring,
            "expired_items": expired,
            "locations": locations,
        }
    return InventoryStats.model_validate(await asyncio.to_thread(_stats))
