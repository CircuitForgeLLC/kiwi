-- Migration 010: User substitution approval log (opt-in dataset moat).

CREATE TABLE substitution_feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name       TEXT    NOT NULL,
    substitute_name     TEXT    NOT NULL,
    constraint_label    TEXT,
    compensation_used   TEXT    NOT NULL DEFAULT '[]',  -- JSON array of compensation ingredient names
    approved            INTEGER NOT NULL DEFAULT 0,
    opted_in            INTEGER NOT NULL DEFAULT 0,     -- user consented to anonymized sharing
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_substitution_feedback_original ON substitution_feedback (original_name);
CREATE INDEX idx_substitution_feedback_opted_in ON substitution_feedback (opted_in);
