-- Migration 007: Recipe corpus index (food.com dataset).

CREATE TABLE recipes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id      TEXT,
    title            TEXT    NOT NULL,
    ingredients      TEXT    NOT NULL DEFAULT '[]',  -- JSON array of raw ingredient strings
    ingredient_names TEXT    NOT NULL DEFAULT '[]',  -- JSON array of normalized names
    directions       TEXT    NOT NULL DEFAULT '[]',  -- JSON array of step strings
    category         TEXT,
    keywords         TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    calories         REAL,
    fat_g            REAL,
    protein_g        REAL,
    sodium_mg        REAL,
    -- Element coverage scores computed at import time
    element_coverage TEXT    NOT NULL DEFAULT '{}',  -- JSON {element: 0.0-1.0}
    source           TEXT    NOT NULL DEFAULT 'foodcom',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_recipes_title        ON recipes (title);
CREATE INDEX idx_recipes_category     ON recipes (category);
CREATE UNIQUE INDEX idx_recipes_external_id  ON recipes (external_id);
