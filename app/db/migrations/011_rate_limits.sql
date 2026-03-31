-- Migration 011: Daily rate limits (leftover mode: 5/day free tier).

CREATE TABLE rate_limits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    feature      TEXT    NOT NULL,
    window_date  TEXT    NOT NULL,  -- YYYY-MM-DD
    count        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (feature, window_date)
);

CREATE INDEX idx_rate_limits_feature_date ON rate_limits (feature, window_date);
