-- Migration 036: captured_products local cache
-- Products captured via visual label scanning (kiwi#79).
-- Keyed by barcode; checked before FDC/OFF on future scans so each product
-- is only captured once per device.

CREATE TABLE IF NOT EXISTS captured_products (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode           TEXT UNIQUE NOT NULL,
    product_name      TEXT,
    brand             TEXT,
    serving_size_g    REAL,
    calories          REAL,
    fat_g             REAL,
    saturated_fat_g   REAL,
    carbs_g           REAL,
    sugar_g           REAL,
    fiber_g           REAL,
    protein_g         REAL,
    sodium_mg         REAL,
    ingredient_names  TEXT NOT NULL DEFAULT '[]',   -- JSON array
    allergens         TEXT NOT NULL DEFAULT '[]',   -- JSON array
    confidence        REAL,
    source            TEXT NOT NULL DEFAULT 'visual_capture',
    captured_at       TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_by_user INTEGER NOT NULL DEFAULT 0
);
