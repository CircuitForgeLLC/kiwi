-- Migration 016: Add FTS5 sync triggers for the recipes_fts content table.
--
-- Migration 015 created recipes_fts and did a one-time rebuild, but omitted
-- triggers. Without them, INSERT/UPDATE/DELETE on recipes does not update the
-- FTS index, so new rows are invisible to MATCH queries.
--
-- CREATE TRIGGER IF NOT EXISTS is idempotent — safe to re-run.

CREATE TRIGGER IF NOT EXISTS recipes_fts_ai
  AFTER INSERT ON recipes BEGIN
    INSERT INTO recipes_fts(rowid, ingredient_names)
    VALUES (new.id, new.ingredient_names);
END;

CREATE TRIGGER IF NOT EXISTS recipes_fts_ad
  AFTER DELETE ON recipes BEGIN
    INSERT INTO recipes_fts(recipes_fts, rowid, ingredient_names)
    VALUES ('delete', old.id, old.ingredient_names);
END;

CREATE TRIGGER IF NOT EXISTS recipes_fts_au
  AFTER UPDATE ON recipes BEGIN
    INSERT INTO recipes_fts(recipes_fts, rowid, ingredient_names)
    VALUES ('delete', old.id, old.ingredient_names);
    INSERT INTO recipes_fts(rowid, ingredient_names)
    VALUES (new.id, new.ingredient_names);
END;
