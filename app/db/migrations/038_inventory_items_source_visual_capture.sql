-- Migration 038: add 'visual_capture' to inventory_items.source CHECK constraint
-- SQLite cannot ALTER a CHECK constraint, so we rebuild the table.

PRAGMA foreign_keys = OFF;

BEGIN;

CREATE TABLE inventory_items_new (
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
                        CHECK (source IN ('barcode_scan', 'manual', 'receipt', 'visual_capture')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    opened_date     TEXT,
    disposal_reason TEXT
);

INSERT INTO inventory_items_new
    SELECT id, product_id, receipt_id, quantity, unit, location, sublocation,
           purchase_date, expiration_date, status, consumed_at, notes, source,
           created_at, updated_at, opened_date, disposal_reason
    FROM inventory_items;

DROP TABLE inventory_items;
ALTER TABLE inventory_items_new RENAME TO inventory_items;

COMMIT;

PRAGMA foreign_keys = ON;
