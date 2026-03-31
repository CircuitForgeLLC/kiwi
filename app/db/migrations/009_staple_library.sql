-- Migration 009: Staple library (bulk-preparable base components).

CREATE TABLE staples (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT    NOT NULL UNIQUE,
    name              TEXT    NOT NULL,
    description       TEXT,
    base_ingredients  TEXT    NOT NULL DEFAULT '[]',  -- JSON array of ingredient strings
    base_method       TEXT,
    base_time_minutes INTEGER,
    yield_formats     TEXT    NOT NULL DEFAULT '{}',  -- JSON {format_name: {elements, shelf_days, methods, texture}}
    dietary_labels    TEXT    NOT NULL DEFAULT '[]',  -- JSON ['vegan','high-protein']
    compatible_styles TEXT    NOT NULL DEFAULT '[]',  -- JSON [style_id]
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE user_staples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    staple_slug   TEXT    NOT NULL REFERENCES staples(slug) ON DELETE CASCADE,
    active_format TEXT    NOT NULL,
    quantity_g    REAL,
    prepared_at   TEXT,
    notes         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_user_staples_slug ON user_staples (staple_slug);
