-- Migration 037: add 'visual_capture' to products.source CHECK constraint
-- SQLite cannot ALTER a CHECK constraint, so we rebuild the table.

PRAGMA foreign_keys = OFF;

BEGIN;

CREATE TABLE products_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode         TEXT UNIQUE,
    name            TEXT NOT NULL,
    brand           TEXT,
    category        TEXT,
    description     TEXT,
    image_url       TEXT,
    nutrition_data  TEXT NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL DEFAULT 'openfoodfacts'
                         CHECK (source IN ('openfoodfacts', 'manual', 'receipt_ocr', 'visual_capture')),
    source_data     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO products_new
    SELECT id, barcode, name, brand, category, description, image_url,
           nutrition_data, source, source_data, created_at, updated_at
    FROM products;

DROP TABLE products;
ALTER TABLE products_new RENAME TO products;

COMMIT;

PRAGMA foreign_keys = ON;
