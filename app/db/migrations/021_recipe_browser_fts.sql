-- Migration 021: FTS5 inverted index for the recipe browser (category + keywords).
--
-- The browser domain queries were using LIKE '%keyword%' against category and
-- keywords columns — a leading wildcard prevents any B-tree index use, so every
-- query was a full sequential scan of 3.1M rows. This FTS5 index replaces those
-- scans with O(log N) token lookups.
--
-- Content-table backed: stores only the inverted index, no text duplication.
-- The keywords column is a JSON array; FTS5 tokenises it as plain text, stripping
-- the punctuation, which gives correct per-word matching.
--
-- One-time rebuild cost on 3.1M rows: ~20-40 seconds at first startup.
-- Subsequent startups skip this migration (IF NOT EXISTS guard).

CREATE VIRTUAL TABLE IF NOT EXISTS recipe_browser_fts USING fts5(
    category,
    keywords,
    content=recipes,
    content_rowid=id,
    tokenize="unicode61"
);

INSERT INTO recipe_browser_fts(recipe_browser_fts) VALUES('rebuild');

CREATE TRIGGER IF NOT EXISTS recipe_browser_fts_ai
  AFTER INSERT ON recipes BEGIN
    INSERT INTO recipe_browser_fts(rowid, category, keywords)
    VALUES (new.id, new.category, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS recipe_browser_fts_ad
  AFTER DELETE ON recipes BEGIN
    INSERT INTO recipe_browser_fts(recipe_browser_fts, rowid, category, keywords)
    VALUES ('delete', old.id, old.category, old.keywords);
END;

CREATE TRIGGER IF NOT EXISTS recipe_browser_fts_au
  AFTER UPDATE ON recipes BEGIN
    INSERT INTO recipe_browser_fts(recipe_browser_fts, rowid, category, keywords)
    VALUES ('delete', old.id, old.category, old.keywords);
    INSERT INTO recipe_browser_fts(rowid, category, keywords)
    VALUES (new.id, new.category, new.keywords);
END;
