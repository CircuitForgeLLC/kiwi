-- Migration 039: Drop FK constraint on saved_recipes.recipe_id.
--
-- In cloud mode the recipe corpus is ATTACHed as a separate database.
-- SQLite FK constraints only resolve against the `main` schema, so
-- `REFERENCES recipes(id)` was always failing for cloud saves (the
-- main.recipes table is empty; all data lives in corpus.recipes).
-- The corpus is read-only and never modified by the app, so cascade-on-delete
-- is meaningless anyway. Remove the constraint without changing any data.

PRAGMA foreign_keys = OFF;

CREATE TABLE saved_recipes_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id   INTEGER NOT NULL,
    saved_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    notes       TEXT,
    rating      INTEGER CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    style_tags  TEXT    NOT NULL DEFAULT '[]',
    UNIQUE (recipe_id)
);

INSERT INTO saved_recipes_new SELECT * FROM saved_recipes;

DROP TABLE saved_recipes;

ALTER TABLE saved_recipes_new RENAME TO saved_recipes;

CREATE INDEX IF NOT EXISTS idx_saved_recipes_saved_at ON saved_recipes (saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_recipes_rating   ON saved_recipes (rating);

PRAGMA foreign_keys = ON;
