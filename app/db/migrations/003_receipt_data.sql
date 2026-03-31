-- Migration 003: OCR receipt data table (ported from Alembic 54cddaf4f4e2)

CREATE TABLE IF NOT EXISTS receipt_data (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id          INTEGER NOT NULL UNIQUE
                            REFERENCES receipts (id) ON DELETE CASCADE,
    merchant_name       TEXT,
    merchant_address    TEXT,
    merchant_phone      TEXT,
    merchant_email      TEXT,
    merchant_website    TEXT,
    merchant_tax_id     TEXT,
    transaction_date    TEXT,
    transaction_time    TEXT,
    receipt_number      TEXT,
    register_number     TEXT,
    cashier_name        TEXT,
    transaction_id      TEXT,
    items               TEXT NOT NULL DEFAULT '[]',
    subtotal            REAL,
    tax                 REAL,
    discount            REAL,
    tip                 REAL,
    total               REAL,
    payment_method      TEXT,
    amount_paid         REAL,
    change_given        REAL,
    raw_text            TEXT,
    confidence_scores   TEXT NOT NULL DEFAULT '{}',
    warnings            TEXT NOT NULL DEFAULT '[]',
    processing_time     REAL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_receipt_data_receipt_id ON receipt_data (receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_data_merchant   ON receipt_data (merchant_name);
CREATE INDEX IF NOT EXISTS idx_receipt_data_date       ON receipt_data (transaction_date);
