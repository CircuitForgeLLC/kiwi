-- 042_activitypub.sql
-- ActivityPub federation tables: follower registry, delivery log, dedup, Mastodon tokens.

-- Follower registry: AP actors that Follow this Kiwi instance
CREATE TABLE IF NOT EXISTS ap_followers (
    id          INTEGER PRIMARY KEY,
    actor_id    TEXT NOT NULL UNIQUE,       -- AP actor URL
    inbox_url   TEXT NOT NULL,
    shared_inbox TEXT,
    followed_at TEXT NOT NULL DEFAULT (datetime('now')),
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_ap_followers_active
    ON ap_followers (active) WHERE active = 1;

-- Outgoing delivery log: one row per (post_slug, target_inbox) attempt
CREATE TABLE IF NOT EXISTS ap_deliveries (
    id          INTEGER PRIMARY KEY,
    post_slug   TEXT NOT NULL,
    target_inbox TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending', -- pending | delivered | failed
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ap_deliveries_status
    ON ap_deliveries (status) WHERE status != 'delivered';

-- Incoming activity dedup: prevents replay attacks and double-processing
CREATE TABLE IF NOT EXISTS ap_received (
    activity_id TEXT PRIMARY KEY,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Mastodon OAuth tokens: per-user, encrypted at rest
-- Stored in the user's local kiwi.db (CLOUD_MODE: per-user DB tree)
CREATE TABLE IF NOT EXISTS mastodon_tokens (
    id              INTEGER PRIMARY KEY,
    directus_user_id TEXT NOT NULL UNIQUE,
    instance_url    TEXT NOT NULL,
    access_token    TEXT NOT NULL,   -- Fernet-encrypted when AP_TOKEN_ENCRYPTION_KEY set
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
