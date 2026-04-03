-- Migration 015: FTS5 inverted index for recipe ingredient lookup.
--
-- Content table backed by `recipes` — stores only the inverted index, no text duplication.
-- MATCH queries replace O(N) LIKE scans with O(log N) token lookups.
--
-- One-time rebuild cost on 3.2M rows: ~15-30 seconds at startup.
-- Subsequent startups skip this migration entirely.

CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
    ingredient_names,
    content=recipes,
    content_rowid=id,
    tokenize="unicode61"
);

INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild');
