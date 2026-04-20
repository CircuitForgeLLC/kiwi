-- Migration 034: async recipe generation job queue
CREATE TABLE IF NOT EXISTS recipe_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT    NOT NULL UNIQUE,
    user_id     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'queued',
    request     TEXT    NOT NULL,
    result      TEXT,
    error       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_recipe_jobs_job_id  ON recipe_jobs (job_id);
CREATE INDEX IF NOT EXISTS idx_recipe_jobs_user_id ON recipe_jobs (user_id, created_at DESC);
