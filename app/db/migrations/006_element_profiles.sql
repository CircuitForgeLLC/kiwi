-- Migration 006: Ingredient element profiles + FlavorGraph molecule index.

CREATE TABLE ingredient_profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    name_variants       TEXT NOT NULL DEFAULT '[]',   -- JSON array of aliases/alternate spellings
    elements            TEXT NOT NULL DEFAULT '[]',   -- JSON array: ["Richness","Depth"]
    -- Functional submetadata (from USDA FDC)
    fat_pct             REAL    DEFAULT 0.0,
    fat_saturated_pct   REAL    DEFAULT 0.0,
    moisture_pct        REAL    DEFAULT 0.0,
    protein_pct         REAL    DEFAULT 0.0,
    starch_pct          REAL    DEFAULT 0.0,
    binding_score       INTEGER DEFAULT 0 CHECK (binding_score BETWEEN 0 AND 3),
    glutamate_mg        REAL    DEFAULT 0.0,
    ph_estimate         REAL,
    sodium_mg_per_100g  REAL    DEFAULT 0.0,
    smoke_point_c       REAL,
    is_fermented        INTEGER NOT NULL DEFAULT 0,
    is_emulsifier       INTEGER NOT NULL DEFAULT 0,
    -- Aroma submetadata
    flavor_molecule_ids TEXT NOT NULL DEFAULT '[]',   -- JSON array of FlavorGraph compound IDs
    heat_stable         INTEGER NOT NULL DEFAULT 1,
    add_timing          TEXT    NOT NULL DEFAULT 'any'
                            CHECK (add_timing IN ('early','finish','any')),
    -- Brightness submetadata
    acid_type           TEXT CHECK (acid_type IN ('citric','acetic','lactic',NULL)),
    -- Texture submetadata
    texture_profile     TEXT    NOT NULL DEFAULT 'neutral',
    water_activity      REAL,
    -- Source
    usda_fdc_id         TEXT,
    source              TEXT    NOT NULL DEFAULT 'usda',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX idx_ingredient_profiles_name ON ingredient_profiles (name);
CREATE INDEX idx_ingredient_profiles_elements ON ingredient_profiles (elements);

CREATE TABLE flavor_molecules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_id     TEXT    NOT NULL UNIQUE,   -- FlavorGraph node ID
    compound_name   TEXT    NOT NULL,
    ingredient_names TEXT   NOT NULL DEFAULT '[]',  -- JSON array of ingredient names
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_flavor_molecules_compound_id ON flavor_molecules (compound_id);
