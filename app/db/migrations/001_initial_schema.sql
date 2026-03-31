-- Migration 001: receipts + quality assessments (ported from Alembic f31d9044277e)

CREATE TABLE IF NOT EXISTS receipts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    original_path TEXT NOT NULL,
    processed_path TEXT,
    status      TEXT NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN ('uploaded', 'processing', 'processed', 'error')),
    error       TEXT,
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_receipts_status     ON receipts (status);
CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts (created_at DESC);

CREATE TABLE IF NOT EXISTS quality_assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id      INTEGER NOT NULL UNIQUE
                        REFERENCES receipts (id) ON DELETE CASCADE,
    overall_score   REAL NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    is_acceptable   INTEGER NOT NULL DEFAULT 0,
    metrics         TEXT NOT NULL DEFAULT '{}',
    improvement_suggestions TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_quality_receipt_id  ON quality_assessments (receipt_id);
CREATE INDEX IF NOT EXISTS idx_quality_score       ON quality_assessments (overall_score);
CREATE INDEX IF NOT EXISTS idx_quality_acceptable  ON quality_assessments (is_acceptable);
