-- 017_household_invites.sql
CREATE TABLE IF NOT EXISTS household_invites (
    token        TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT NOT NULL,
    used_at      TEXT,
    used_by      TEXT
);
