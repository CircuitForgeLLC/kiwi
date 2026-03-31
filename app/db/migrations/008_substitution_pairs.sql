-- Migration 008: Derived substitution pairs.
-- Source: diff of lishuyang/recipepairs (GPL-3.0 derivation — raw data not shipped).

CREATE TABLE substitution_pairs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name       TEXT    NOT NULL,
    substitute_name     TEXT    NOT NULL,
    constraint_label    TEXT    NOT NULL,  -- 'vegan'|'vegetarian'|'dairy_free'|'gluten_free'|'low_fat'|'low_sodium'
    fat_delta           REAL    DEFAULT 0.0,
    moisture_delta      REAL    DEFAULT 0.0,
    glutamate_delta     REAL    DEFAULT 0.0,
    protein_delta       REAL    DEFAULT 0.0,
    occurrence_count    INTEGER DEFAULT 1,
    compensation_hints  TEXT    NOT NULL DEFAULT '[]',  -- JSON [{ingredient, reason, element}]
    source              TEXT    NOT NULL DEFAULT 'derived',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_substitution_pairs_original   ON substitution_pairs (original_name);
CREATE INDEX idx_substitution_pairs_constraint ON substitution_pairs (constraint_label);
CREATE UNIQUE INDEX idx_substitution_pairs_pair
    ON substitution_pairs (original_name, substitute_name, constraint_label);
