-- Migration 019: recipe collections (Paid tier organisation).

CREATE TABLE recipe_collections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recipe_collection_members (
    collection_id   INTEGER NOT NULL REFERENCES recipe_collections(id) ON DELETE CASCADE,
    saved_recipe_id INTEGER NOT NULL REFERENCES saved_recipes(id) ON DELETE CASCADE,
    added_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, saved_recipe_id)
);
