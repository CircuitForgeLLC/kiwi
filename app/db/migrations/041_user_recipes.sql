-- Migration 041: user_recipes table for user-scanned and manually-entered recipes.
--
-- Separate from the food.com corpus (recipes table) -- user recipes are personal,
-- not curated, and need different fields (servings as string, cook_time as string).

CREATE TABLE IF NOT EXISTS user_recipes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    subtitle    TEXT,
    servings    TEXT,           -- kept as string: "2", "4-6", "serves 8"
    cook_time   TEXT,           -- kept as string: "25 min", "1 hour"
    source_note TEXT,           -- e.g. "Purple Carrot", "Betty Crocker"
    ingredients TEXT NOT NULL DEFAULT '[]', -- JSON: [{name, qty, unit, raw}]
    steps       TEXT NOT NULL DEFAULT '[]', -- JSON: ["step 1", "step 2", ...]
    notes       TEXT,
    tags        TEXT DEFAULT '[]',          -- JSON: ["vegan", "quick"]
    source      TEXT NOT NULL DEFAULT 'manual', -- 'scan' | 'manual'
    pantry_match_pct INTEGER,   -- 0-100, computed at scan time; null for manual
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_user_recipes_created ON user_recipes (created_at DESC);
