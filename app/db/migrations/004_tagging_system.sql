-- Migration 004: tags + product_tags join table (ported from Alembic 14f688cde2ca)

CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    color       TEXT,
    category    TEXT CHECK (category IN ('food_type', 'dietary', 'allergen', 'custom') OR category IS NULL),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tags_name     ON tags (name);
CREATE INDEX IF NOT EXISTS idx_tags_slug     ON tags (slug);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags (category);

CREATE TABLE IF NOT EXISTS product_tags (
    product_id  INTEGER NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (product_id, tag_id)
);
