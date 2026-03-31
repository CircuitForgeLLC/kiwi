-- Migration 002: products + inventory items (ported from Alembic 8fc1bf4e7a91)

CREATE TABLE IF NOT EXISTS products (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode        TEXT UNIQUE,
    name           TEXT NOT NULL,
    brand          TEXT,
    category       TEXT,
    description    TEXT,
    image_url      TEXT,
    nutrition_data TEXT NOT NULL DEFAULT '{}',
    source         TEXT NOT NULL DEFAULT 'manual'
                       CHECK (source IN ('openfoodfacts', 'manual', 'receipt_ocr')),
    source_data    TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_barcode   ON products (barcode);
CREATE INDEX IF NOT EXISTS idx_products_name      ON products (name);
CREATE INDEX IF NOT EXISTS idx_products_category  ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_source    ON products (source);

CREATE TABLE IF NOT EXISTS inventory_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL
                        REFERENCES products (id) ON DELETE RESTRICT,
    receipt_id      INTEGER
                        REFERENCES receipts (id) ON DELETE SET NULL,
    quantity        REAL NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit            TEXT NOT NULL DEFAULT 'count',
    location        TEXT NOT NULL,
    sublocation     TEXT,
    purchase_date   TEXT,
    expiration_date TEXT,
    status          TEXT NOT NULL DEFAULT 'available'
                        CHECK (status IN ('available', 'consumed', 'expired', 'discarded')),
    consumed_at     TEXT,
    notes           TEXT,
    source          TEXT NOT NULL DEFAULT 'manual'
                        CHECK (source IN ('barcode_scan', 'manual', 'receipt')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_inventory_product    ON inventory_items (product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_receipt    ON inventory_items (receipt_id);
CREATE INDEX IF NOT EXISTS idx_inventory_status     ON inventory_items (status);
CREATE INDEX IF NOT EXISTS idx_inventory_location   ON inventory_items (location);
CREATE INDEX IF NOT EXISTS idx_inventory_expiration ON inventory_items (expiration_date);
CREATE INDEX IF NOT EXISTS idx_inventory_created    ON inventory_items (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_active_loc ON inventory_items (status, location)
    WHERE status = 'available';
