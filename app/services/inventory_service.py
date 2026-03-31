"""
Inventory management service.

This service orchestrates:
- Barcode scanning
- Product lookups (OpenFoodFacts)
- Inventory CRUD operations
- Tag management
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import UUID
import uuid
import logging

from app.db.models import Product, InventoryItem, Tag, product_tags
from app.models.schemas.inventory import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    TagCreate,
    TagResponse,
    InventoryStats,
)
from app.services.barcode_scanner import BarcodeScanner
from app.services.openfoodfacts import OpenFoodFactsService
from app.services.expiration_predictor import ExpirationPredictor

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for managing inventory and products."""

    def __init__(self):
        self.barcode_scanner = BarcodeScanner()
        self.openfoodfacts = OpenFoodFactsService()
        self.expiration_predictor = ExpirationPredictor()

    # ========== Barcode Scanning ==========

    async def scan_barcode_image(
        self,
        image_path: Path,
        db: AsyncSession,
        auto_add: bool = True,
        location: str = "pantry",
        quantity: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Scan an image for barcodes and optionally add to inventory.

        Args:
            image_path: Path to image file
            db: Database session
            auto_add: Whether to auto-add to inventory
            location: Default storage location
            quantity: Default quantity

        Returns:
            Dictionary with scan results
        """
        # Scan for barcodes
        barcodes = self.barcode_scanner.scan_image(image_path)

        if not barcodes:
            return {
                "success": False,
                "barcodes_found": 0,
                "results": [],
                "message": "No barcodes detected in image",
            }

        results = []
        for barcode_data in barcodes:
            result = await self._process_barcode(
                barcode_data, db, auto_add, location, quantity
            )
            results.append(result)

        return {
            "success": True,
            "barcodes_found": len(barcodes),
            "results": results,
            "message": f"Found {len(barcodes)} barcode(s)",
        }

    async def _process_barcode(
        self,
        barcode_data: Dict[str, Any],
        db: AsyncSession,
        auto_add: bool,
        location: str,
        quantity: float,
    ) -> Dict[str, Any]:
        """Process a single barcode detection."""
        barcode = barcode_data["data"]
        barcode_type = barcode_data["type"]

        # Check if product already exists
        product = await self.get_product_by_barcode(db, barcode)

        # If not found, lookup in OpenFoodFacts
        if not product:
            off_data = await self.openfoodfacts.lookup_product(barcode)

            if off_data:
                # Create product from OpenFoodFacts data
                product_create = ProductCreate(
                    barcode=barcode,
                    name=off_data["name"],
                    brand=off_data.get("brand"),
                    category=off_data.get("category"),
                    description=off_data.get("description"),
                    image_url=off_data.get("image_url"),
                    nutrition_data=off_data.get("nutrition_data", {}),
                    source="openfoodfacts",
                    source_data=off_data.get("raw_data", {}),
                )
                product = await self.create_product(db, product_create)
                source = "openfoodfacts"
            else:
                # Product not found in OpenFoodFacts
                # Create a placeholder product
                product_create = ProductCreate(
                    barcode=barcode,
                    name=f"Unknown Product ({barcode})",
                    source="manual",
                )
                product = await self.create_product(db, product_create)
                source = "manual"
        else:
            source = product.source

        # Auto-add to inventory if requested
        inventory_item = None
        predicted_expiration = None
        if auto_add:
            # Predict expiration date based on product category and location
            category = self.expiration_predictor.get_category_from_product(
                product.name,
                product.category,
                [tag.name for tag in product.tags] if product.tags else None
            )
            if category:
                predicted_expiration = self.expiration_predictor.predict_expiration(
                    category,
                    location,
                    date.today()
                )

            item_create = InventoryItemCreate(
                product_id=product.id,
                quantity=quantity,
                location=location,
                purchase_date=date.today(),
                expiration_date=predicted_expiration,
                source="barcode_scan",
            )
            inventory_item = await self.create_inventory_item(db, item_create)

        return {
            "barcode": barcode,
            "barcode_type": barcode_type,
            "quality": barcode_data["quality"],
            "product": ProductResponse.from_orm(product),
            "inventory_item": (
                InventoryItemResponse.from_orm(inventory_item) if inventory_item else None
            ),
            "source": source,
            "predicted_expiration": predicted_expiration.isoformat() if predicted_expiration else None,
            "predicted_category": category if auto_add else None,
        }

    # ========== Product Management ==========

    async def create_product(
        self,
        db: AsyncSession,
        product: ProductCreate,
    ) -> Product:
        """Create a new product."""
        # Create product
        db_product = Product(
            id=uuid.uuid4(),
            barcode=product.barcode,
            name=product.name,
            brand=product.brand,
            category=product.category,
            description=product.description,
            image_url=product.image_url,
            nutrition_data=product.nutrition_data,
            source=product.source,
            source_data=product.source_data,
        )

        db.add(db_product)
        await db.flush()

        # Add tags if specified
        if product.tag_ids:
            for tag_id in product.tag_ids:
                tag = await db.get(Tag, tag_id)
                if tag:
                    db_product.tags.append(tag)

        await db.commit()
        await db.refresh(db_product, ["tags"])

        return db_product

    async def get_product(self, db: AsyncSession, product_id: UUID) -> Optional[Product]:
        """Get a product by ID."""
        result = await db.execute(
            select(Product).where(Product.id == product_id).options(selectinload(Product.tags))
        )
        return result.scalar_one_or_none()

    async def get_product_by_barcode(
        self, db: AsyncSession, barcode: str
    ) -> Optional[Product]:
        """Get a product by barcode."""
        result = await db.execute(
            select(Product).where(Product.barcode == barcode).options(selectinload(Product.tags))
        )
        return result.scalar_one_or_none()

    async def list_products(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
    ) -> List[Product]:
        """List products with optional filtering."""
        query = select(Product).options(selectinload(Product.tags))

        if category:
            query = query.where(Product.category == category)

        query = query.offset(skip).limit(limit).order_by(Product.name)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_product(
        self,
        db: AsyncSession,
        product_id: UUID,
        product_update: ProductUpdate,
    ) -> Optional[Product]:
        """Update a product."""
        product = await self.get_product(db, product_id)
        if not product:
            return None

        # Update fields
        for field, value in product_update.dict(exclude_unset=True).items():
            if field == "tag_ids":
                # Update tags
                product.tags = []
                for tag_id in value:
                    tag = await db.get(Tag, tag_id)
                    if tag:
                        product.tags.append(tag)
            else:
                setattr(product, field, value)

        product.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(product, ["tags"])

        return product

    async def delete_product(self, db: AsyncSession, product_id: UUID) -> bool:
        """Delete a product (will fail if inventory items exist)."""
        product = await self.get_product(db, product_id)
        if not product:
            return False

        await db.delete(product)
        await db.commit()
        return True

    # ========== Inventory Item Management ==========

    async def create_inventory_item(
        self,
        db: AsyncSession,
        item: InventoryItemCreate,
    ) -> InventoryItem:
        """Create a new inventory item."""
        db_item = InventoryItem(
            id=uuid.uuid4(),
            product_id=item.product_id,
            quantity=item.quantity,
            unit=item.unit,
            location=item.location,
            sublocation=item.sublocation,
            purchase_date=item.purchase_date,
            expiration_date=item.expiration_date,
            notes=item.notes,
            source=item.source,
            status="available",
        )

        db.add(db_item)
        await db.commit()
        await db.refresh(db_item, ["product"])

        return db_item

    async def get_inventory_item(
        self, db: AsyncSession, item_id: UUID
    ) -> Optional[InventoryItem]:
        """Get an inventory item by ID."""
        result = await db.execute(
            select(InventoryItem)
            .where(InventoryItem.id == item_id)
            .options(selectinload(InventoryItem.product).selectinload(Product.tags))
        )
        return result.scalar_one_or_none()

    async def list_inventory_items(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        location: Optional[str] = None,
        status: str = "available",
    ) -> List[InventoryItem]:
        """List inventory items with filtering."""
        query = select(InventoryItem).options(
            selectinload(InventoryItem.product).selectinload(Product.tags)
        )

        query = query.where(InventoryItem.status == status)

        if location:
            query = query.where(InventoryItem.location == location)

        query = (
            query.offset(skip)
            .limit(limit)
            .order_by(InventoryItem.expiration_date.asc().nullsfirst())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_inventory_item(
        self,
        db: AsyncSession,
        item_id: UUID,
        item_update: InventoryItemUpdate,
    ) -> Optional[InventoryItem]:
        """Update an inventory item."""
        item = await self.get_inventory_item(db, item_id)
        if not item:
            return None

        for field, value in item_update.dict(exclude_unset=True).items():
            setattr(item, field, value)

        item.updated_at = datetime.utcnow()

        if item_update.status == "consumed" and not item.consumed_at:
            item.consumed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(item, ["product"])

        return item

    async def delete_inventory_item(self, db: AsyncSession, item_id: UUID) -> bool:
        """Delete an inventory item."""
        item = await self.get_inventory_item(db, item_id)
        if not item:
            return False

        await db.delete(item)
        await db.commit()
        return True

    async def mark_as_consumed(
        self, db: AsyncSession, item_id: UUID
    ) -> Optional[InventoryItem]:
        """Mark an inventory item as consumed."""
        return await self.update_inventory_item(
            db, item_id, InventoryItemUpdate(status="consumed")
        )

    # ========== Tag Management ==========

    async def create_tag(self, db: AsyncSession, tag: TagCreate) -> Tag:
        """Create a new tag."""
        db_tag = Tag(
            id=uuid.uuid4(),
            name=tag.name,
            slug=tag.slug,
            description=tag.description,
            color=tag.color,
            category=tag.category,
        )

        db.add(db_tag)
        await db.commit()
        await db.refresh(db_tag)

        return db_tag

    async def get_tag(self, db: AsyncSession, tag_id: UUID) -> Optional[Tag]:
        """Get a tag by ID."""
        return await db.get(Tag, tag_id)

    async def list_tags(
        self, db: AsyncSession, category: Optional[str] = None
    ) -> List[Tag]:
        """List all tags, optionally filtered by category."""
        query = select(Tag).order_by(Tag.name)

        if category:
            query = query.where(Tag.category == category)

        result = await db.execute(query)
        return list(result.scalars().all())

    # ========== Statistics and Analytics ==========

    async def get_inventory_stats(self, db: AsyncSession) -> InventoryStats:
        """Get inventory statistics."""
        # Total items (available only)
        total_result = await db.execute(
            select(func.count(InventoryItem.id)).where(InventoryItem.status == "available")
        )
        total_items = total_result.scalar() or 0

        # Total unique products
        products_result = await db.execute(
            select(func.count(func.distinct(InventoryItem.product_id))).where(
                InventoryItem.status == "available"
            )
        )
        total_products = products_result.scalar() or 0

        # Items by location
        location_result = await db.execute(
            select(
                InventoryItem.location,
                func.count(InventoryItem.id).label("count"),
            )
            .where(InventoryItem.status == "available")
            .group_by(InventoryItem.location)
        )
        items_by_location = {row[0]: row[1] for row in location_result}

        # Items by status
        status_result = await db.execute(
            select(InventoryItem.status, func.count(InventoryItem.id).label("count")).group_by(
                InventoryItem.status
            )
        )
        items_by_status = {row[0]: row[1] for row in status_result}

        # Expiring soon (next 7 days)
        today = date.today()
        week_from_now = today + timedelta(days=7)

        expiring_result = await db.execute(
            select(func.count(InventoryItem.id)).where(
                and_(
                    InventoryItem.status == "available",
                    InventoryItem.expiration_date.isnot(None),
                    InventoryItem.expiration_date <= week_from_now,
                    InventoryItem.expiration_date >= today,
                )
            )
        )
        expiring_soon = expiring_result.scalar() or 0

        # Expired
        expired_result = await db.execute(
            select(func.count(InventoryItem.id)).where(
                and_(
                    InventoryItem.status == "available",
                    InventoryItem.expiration_date.isnot(None),
                    InventoryItem.expiration_date < today,
                )
            )
        )
        expired = expired_result.scalar() or 0

        return InventoryStats(
            total_items=total_items,
            total_products=total_products,
            items_by_location=items_by_location,
            items_by_status=items_by_status,
            expiring_soon=expiring_soon,
            expired=expired,
        )

    async def get_expiring_items(
        self, db: AsyncSession, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get items expiring within N days."""
        today = date.today()
        cutoff_date = today + timedelta(days=days)

        result = await db.execute(
            select(InventoryItem)
            .where(
                and_(
                    InventoryItem.status == "available",
                    InventoryItem.expiration_date.isnot(None),
                    InventoryItem.expiration_date <= cutoff_date,
                    InventoryItem.expiration_date >= today,
                )
            )
            .options(selectinload(InventoryItem.product).selectinload(Product.tags))
            .order_by(InventoryItem.expiration_date.asc())
        )

        items = result.scalars().all()

        return [
            {
                "inventory_item": item,
                "days_until_expiry": (item.expiration_date - today).days,
            }
            for item in items
        ]
