-- 040_corrections.sql — corrections table for SFT training data
-- Schema from circuitforge_core.api.corrections.CORRECTIONS_MIGRATION_SQL
CREATE TABLE IF NOT EXISTS corrections (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          TEXT    NOT NULL DEFAULT '',
    product          TEXT    NOT NULL,
    correction_type  TEXT    NOT NULL,
    input_text       TEXT    NOT NULL,
    original_output  TEXT    NOT NULL,
    corrected_output TEXT    NOT NULL DEFAULT '',
    rating           TEXT    NOT NULL DEFAULT 'down',
    context          TEXT    NOT NULL DEFAULT '{}',
    opted_in         INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_corrections_product
    ON corrections (product);

CREATE INDEX IF NOT EXISTS idx_corrections_opted_in
    ON corrections (opted_in);
