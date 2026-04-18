-- Migration 033: standalone shopping list
-- Items can be added manually, from recipe gap analysis, or from the recipe browser.
-- Affiliate links are computed at query time by the API layer (never stored).

CREATE TABLE IF NOT EXISTS shopping_list_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    quantity     REAL,
    unit         TEXT,
    category     TEXT,
    checked      INTEGER NOT NULL DEFAULT 0,   -- 0=want, 1=in-cart/checked off
    notes        TEXT,
    source       TEXT    NOT NULL DEFAULT 'manual',  -- manual | recipe | meal_plan
    recipe_id    INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_shopping_list_checked
    ON shopping_list_items (checked, sort_order);
