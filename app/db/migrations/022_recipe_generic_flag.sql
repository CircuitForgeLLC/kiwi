-- Migration 022: Add is_generic flag to recipes
-- Generic recipes are catch-all/dump recipes with loose ingredient lists
-- that should not appear in Level 1 (deterministic "use what I have") results.
-- Admins can mark recipes via the recipe editor or a bulk backfill script.
ALTER TABLE recipes ADD COLUMN is_generic INTEGER NOT NULL DEFAULT 0;
