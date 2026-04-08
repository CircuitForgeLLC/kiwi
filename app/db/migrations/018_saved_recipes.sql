-- Migration 018: saved recipes bookmarks.

CREATE TABLE saved_recipes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    saved_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    notes       TEXT,
    rating      INTEGER CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    style_tags  TEXT    NOT NULL DEFAULT '[]',
    UNIQUE (recipe_id)
);

CREATE INDEX idx_saved_recipes_saved_at ON saved_recipes (saved_at DESC);
CREATE INDEX idx_saved_recipes_rating   ON saved_recipes (rating);
