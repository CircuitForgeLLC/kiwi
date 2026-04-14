-- 028_community_pseudonyms.sql
-- Per-user pseudonym store: maps the user's chosen community display name
-- to their Directus user ID. This table lives in per-user kiwi.db only.
-- It is NEVER replicated to the community PostgreSQL — pseudonym isolation is by design.
--
-- A user may have one active pseudonym. Old pseudonyms are retained for reference
-- (posts published under them keep their pseudonym attribution) but only one is
-- flagged as current (is_current = 1).

CREATE TABLE IF NOT EXISTS community_pseudonyms (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudonym       TEXT NOT NULL,
    directus_user_id TEXT NOT NULL,
    is_current      INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Only one pseudonym can be current at a time per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_community_pseudonyms_current
    ON community_pseudonyms (directus_user_id)
    WHERE is_current = 1;
