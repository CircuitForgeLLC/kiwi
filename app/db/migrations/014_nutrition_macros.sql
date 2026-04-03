-- Migration 014: Add macro nutrition columns to recipes and ingredient_profiles.
--
-- recipes: sugar, carbs, fiber, servings, and an estimated flag.
-- ingredient_profiles: carbs, fiber, calories, sugar per 100g (for estimation fallback).

ALTER TABLE recipes ADD COLUMN sugar_g            REAL;
ALTER TABLE recipes ADD COLUMN carbs_g            REAL;
ALTER TABLE recipes ADD COLUMN fiber_g            REAL;
ALTER TABLE recipes ADD COLUMN servings           REAL;
ALTER TABLE recipes ADD COLUMN nutrition_estimated INTEGER NOT NULL DEFAULT 0;

ALTER TABLE ingredient_profiles ADD COLUMN carbs_g_per_100g   REAL DEFAULT 0.0;
ALTER TABLE ingredient_profiles ADD COLUMN fiber_g_per_100g   REAL DEFAULT 0.0;
ALTER TABLE ingredient_profiles ADD COLUMN calories_per_100g  REAL DEFAULT 0.0;
ALTER TABLE ingredient_profiles ADD COLUMN sugar_g_per_100g   REAL DEFAULT 0.0;

CREATE INDEX idx_recipes_sugar_g ON recipes (sugar_g);
CREATE INDEX idx_recipes_carbs_g ON recipes (carbs_g);
