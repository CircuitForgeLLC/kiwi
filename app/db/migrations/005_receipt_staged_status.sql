-- Migration 005: Add 'staged' and 'low_quality' to receipts status constraint.
--
-- SQLite does not support ALTER TABLE to modify CHECK constraints.
-- Pattern: create new table → copy data → drop old → rename.

PRAGMA foreign_keys = OFF;

CREATE TABLE receipts_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    original_path   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'uploaded'
                        CHECK (status IN (
                            'uploaded',
                            'processing',
                            'processed',
                            'staged',
                            'low_quality',
                            'error'
                        )),
    error           TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO receipts_new SELECT * FROM receipts;

DROP TABLE receipts;

ALTER TABLE receipts_new RENAME TO receipts;

CREATE INDEX IF NOT EXISTS idx_receipts_status     ON receipts (status);
CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts (created_at DESC);

PRAGMA foreign_keys = ON;
