-- Migration 029: Add inferred_tags column and update FTS index to include it.
--
-- inferred_tags holds a JSON array of normalized tag strings derived by
-- scripts/pipeline/infer_recipe_tags.py (e.g. ["cuisine:Italian",
-- "dietary:Low-Carb", "flavor:Umami", "can_be:Gluten-Free"]).
--
-- The FTS5 browser table is rebuilt to index inferred_tags alongside
-- category and keywords so browse domain queries match against all signals.

-- 1. Add inferred_tags column (empty array default; populated by pipeline run)
ALTER TABLE recipes ADD COLUMN inferred_tags TEXT NOT NULL DEFAULT '[]';

-- 2. Drop old FTS table and triggers that only covered category + keywords
DROP TRIGGER IF EXISTS recipes_ai;
DROP TRIGGER IF EXISTS recipes_ad;
DROP TRIGGER IF EXISTS recipes_au;
DROP TABLE IF EXISTS recipe_browser_fts;

-- 3. Recreate FTS5 table: now indexes category, keywords, AND inferred_tags
CREATE VIRTUAL TABLE recipe_browser_fts USING fts5(
    category,
    keywords,
    inferred_tags,
    content=recipes,
    content_rowid=id
);

-- 4. Triggers to keep FTS in sync with recipes table changes
CREATE TRIGGER recipes_ai AFTER INSERT ON recipes BEGIN
    INSERT INTO recipe_browser_fts(rowid, category, keywords, inferred_tags)
    VALUES (new.id, new.category, new.keywords, new.inferred_tags);
END;

CREATE TRIGGER recipes_ad AFTER DELETE ON recipes BEGIN
    INSERT INTO recipe_browser_fts(recipe_browser_fts, rowid, category, keywords, inferred_tags)
    VALUES ('delete', old.id, old.category, old.keywords, old.inferred_tags);
END;

CREATE TRIGGER recipes_au AFTER UPDATE ON recipes BEGIN
    INSERT INTO recipe_browser_fts(recipe_browser_fts, rowid, category, keywords, inferred_tags)
    VALUES ('delete', old.id, old.category, old.keywords, old.inferred_tags);
    INSERT INTO recipe_browser_fts(rowid, category, keywords, inferred_tags)
    VALUES (new.id, new.category, new.keywords, new.inferred_tags);
END;

-- 5. Populate FTS from current table state
-- (inferred_tags is '[]' for all rows at this point; run infer_recipe_tags.py
--  to populate, then the FTS will be rebuilt as part of that script.)
INSERT INTO recipe_browser_fts(recipe_browser_fts) VALUES('rebuild');
