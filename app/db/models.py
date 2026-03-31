"""
REMOVED — schema is now managed by plain SQL migrations in app/db/migrations/.
This file is kept for historical reference only. Nothing imports it.
"""
# fmt: off  # noqa — dead file, not linted

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    CheckConstraint,
    Index,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.db.base import Base


# Association table for many-to-many relationship between products and tags
product_tags = Table(
    "product_tags",
    Base.metadata,
    Column(
        "product_id",
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
)


class Receipt(Base):
    """
    Receipt model - stores receipt metadata and processing status.

    Corresponds to the 'receipts' table in the database schema.
    """

    __tablename__ = "receipts"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # File Information
    filename = Column(String(255), nullable=False)
    original_path = Column(Text, nullable=False)
    processed_path = Column(Text, nullable=True)

    # Processing Status
    status = Column(
        String(50),
        nullable=False,
        default="uploaded",
        server_default="uploaded",
    )
    error = Column(Text, nullable=True)

    # Metadata (JSONB for flexibility)
    # Using 'receipt_metadata' to avoid conflict with SQLAlchemy's metadata attribute
    receipt_metadata = Column("metadata", JSONB, nullable=False, default={}, server_default="{}")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    quality_assessment = relationship(
        "QualityAssessment",
        back_populates="receipt",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan",
    )
    receipt_data = relationship(
        "ReceiptData",
        back_populates="receipt",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan",
    )

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'processed', 'error')",
            name="receipts_status_check",
        ),
        # Indexes will be created after table definition
    )

    def __repr__(self) -> str:
        return f"<Receipt(id={self.id}, filename={self.filename}, status={self.status})>"


# Create indexes for Receipt table
Index("idx_receipts_status", Receipt.status)
Index("idx_receipts_created_at", Receipt.created_at.desc())
Index("idx_receipts_metadata", Receipt.receipt_metadata, postgresql_using="gin")


class QualityAssessment(Base):
    """
    Quality Assessment model - stores quality evaluation results.

    One-to-one relationship with Receipt.
    Corresponds to the 'quality_assessments' table in the database schema.
    """

    __tablename__ = "quality_assessments"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Foreign Key (1:1 with receipts)
    receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Quality Scores
    overall_score = Column(Numeric(5, 2), nullable=False)
    is_acceptable = Column(Boolean, nullable=False, default=False, server_default="false")

    # Detailed Metrics (JSONB)
    metrics = Column(JSONB, nullable=False, default={}, server_default="{}")

    # Improvement Suggestions
    improvement_suggestions = Column(JSONB, nullable=False, default=[], server_default="[]")

    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    # Relationships
    receipt = relationship("Receipt", back_populates="quality_assessment")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100",
            name="quality_assessments_score_range",
        ),
        Index("idx_quality_assessments_receipt_id", "receipt_id"),
        Index("idx_quality_assessments_score", "overall_score"),
        Index("idx_quality_assessments_acceptable", "is_acceptable"),
        Index("idx_quality_assessments_metrics", "metrics", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<QualityAssessment(id={self.id}, receipt_id={self.receipt_id}, "
            f"score={self.overall_score}, acceptable={self.is_acceptable})>"
        )


class Product(Base):
    """
    Product model - stores product catalog information.

    Products can come from:
    - Barcode scans (OpenFoodFacts API)
    - Manual user entries
    - Future: OCR extraction from receipts

    One product can have many inventory items.
    """

    __tablename__ = "products"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Identifiers
    barcode = Column(String(50), unique=True, nullable=True)  # UPC/EAN code

    # Product Information
    name = Column(String(500), nullable=False)
    brand = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)

    # Additional Details
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)

    # Nutritional Data (JSONB for flexibility)
    nutrition_data = Column(JSONB, nullable=False, default={}, server_default="{}")

    # Source Tracking
    source = Column(
        String(50),
        nullable=False,
        default="manual",
        server_default="manual",
    )  # 'openfoodfacts', 'manual', 'receipt_ocr'
    source_data = Column(JSONB, nullable=False, default={}, server_default="{}")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    inventory_items = relationship(
        "InventoryItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    tags = relationship(
        "Tag",
        secondary=product_tags,
        back_populates="products",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "source IN ('openfoodfacts', 'manual', 'receipt_ocr')",
            name="products_source_check",
        ),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name}, barcode={self.barcode})>"


class Tag(Base):
    """
    Tag model - stores tags/labels for organizing products.

    Tags can be used to categorize products by:
    - Food type (dairy, meat, vegetables, fruit, etc.)
    - Dietary restrictions (vegan, gluten-free, kosher, halal, etc.)
    - Allergens (contains nuts, contains dairy, etc.)
    - Custom user categories

    Many-to-many relationship with products.
    """

    __tablename__ = "tags"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Tag Information
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)  # URL-safe version
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code for UI (#FF5733)

    # Category (optional grouping)
    category = Column(String(50), nullable=True)  # 'food_type', 'dietary', 'allergen', 'custom'

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    products = relationship(
        "Product",
        secondary=product_tags,
        back_populates="tags",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "category IN ('food_type', 'dietary', 'allergen', 'custom', NULL)",
            name="tags_category_check",
        ),
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name={self.name}, category={self.category})>"


class InventoryItem(Base):
    """
    Inventory Item model - tracks individual items in user's inventory.

    Links to a Product and adds user-specific information like
    quantity, location, expiration date, etc.
    """

    __tablename__ = "inventory_items"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Foreign Keys
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Quantity
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit = Column(String(50), nullable=False, default="count", server_default="count")

    # Location
    location = Column(String(100), nullable=False)
    sublocation = Column(String(255), nullable=True)

    # Dates
    purchase_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)

    # Status
    status = Column(
        String(50),
        nullable=False,
        default="available",
        server_default="available",
    )
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Source Tracking
    source = Column(
        String(50),
        nullable=False,
        default="manual",
        server_default="manual",
    )  # 'barcode_scan', 'manual', 'receipt'

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    product = relationship("Product", back_populates="inventory_items")
    receipt = relationship("Receipt")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'consumed', 'expired', 'discarded')",
            name="inventory_items_status_check",
        ),
        CheckConstraint(
            "source IN ('barcode_scan', 'manual', 'receipt')",
            name="inventory_items_source_check",
        ),
        CheckConstraint(
            "quantity > 0",
            name="inventory_items_quantity_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryItem(id={self.id}, product_id={self.product_id}, "
            f"quantity={self.quantity}, location={self.location}, status={self.status})>"
        )


# Create indexes for Product table
Index("idx_products_barcode", Product.barcode)
Index("idx_products_name", Product.name)
Index("idx_products_category", Product.category)
Index("idx_products_source", Product.source)
Index("idx_products_nutrition_data", Product.nutrition_data, postgresql_using="gin")

# Create indexes for Tag table
Index("idx_tags_name", Tag.name)
Index("idx_tags_slug", Tag.slug)
Index("idx_tags_category", Tag.category)

# Create indexes for InventoryItem table
Index("idx_inventory_items_product", InventoryItem.product_id)
Index("idx_inventory_items_receipt", InventoryItem.receipt_id)
Index("idx_inventory_items_status", InventoryItem.status)
Index("idx_inventory_items_location", InventoryItem.location)
Index("idx_inventory_items_expiration", InventoryItem.expiration_date)
Index("idx_inventory_items_created", InventoryItem.created_at.desc())
# Composite index for common query: active items by location
Index(
    "idx_inventory_items_active_by_location",
    InventoryItem.status,
    InventoryItem.location,
    postgresql_where=(InventoryItem.status == "available"),
)


class ReceiptData(Base):
    """
    Receipt Data model - stores OCR-extracted structured data from receipts.

    One-to-one relationship with Receipt.
    Stores merchant info, transaction details, line items, and totals.
    """

    __tablename__ = "receipt_data"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Foreign Key (1:1 with receipts)
    receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Merchant Information
    merchant_name = Column(String(500), nullable=True)
    merchant_address = Column(Text, nullable=True)
    merchant_phone = Column(String(50), nullable=True)
    merchant_email = Column(String(255), nullable=True)
    merchant_website = Column(String(255), nullable=True)
    merchant_tax_id = Column(String(100), nullable=True)

    # Transaction Information
    transaction_date = Column(Date, nullable=True)
    transaction_time = Column(String(20), nullable=True)  # Store as string for flexibility
    receipt_number = Column(String(100), nullable=True)
    register_number = Column(String(50), nullable=True)
    cashier_name = Column(String(255), nullable=True)
    transaction_id = Column(String(100), nullable=True)

    # Line Items (JSONB array)
    items = Column(JSONB, nullable=False, default=[], server_default="[]")

    # Financial Totals
    subtotal = Column(Numeric(12, 2), nullable=True)
    tax = Column(Numeric(12, 2), nullable=True)
    discount = Column(Numeric(12, 2), nullable=True)
    tip = Column(Numeric(12, 2), nullable=True)
    total = Column(Numeric(12, 2), nullable=True)
    payment_method = Column(String(100), nullable=True)
    amount_paid = Column(Numeric(12, 2), nullable=True)
    change_given = Column(Numeric(12, 2), nullable=True)

    # OCR Metadata
    raw_text = Column(Text, nullable=True)  # Full OCR text output
    confidence_scores = Column(JSONB, nullable=False, default={}, server_default="{}")
    warnings = Column(JSONB, nullable=False, default=[], server_default="[]")
    processing_time = Column(Numeric(8, 3), nullable=True)  # seconds

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    receipt = relationship("Receipt", back_populates="receipt_data")

    def __repr__(self) -> str:
        return (
            f"<ReceiptData(id={self.id}, receipt_id={self.receipt_id}, "
            f"merchant={self.merchant_name}, total={self.total})>"
        )


# Create indexes for ReceiptData table
Index("idx_receipt_data_receipt_id", ReceiptData.receipt_id)
Index("idx_receipt_data_merchant", ReceiptData.merchant_name)
Index("idx_receipt_data_date", ReceiptData.transaction_date)
Index("idx_receipt_data_items", ReceiptData.items, postgresql_using="gin")
Index("idx_receipt_data_confidence", ReceiptData.confidence_scores, postgresql_using="gin")
