-- Migration 020: recipe browser navigation telemetry.
-- Used to determine whether category nesting depth needs increasing.
-- Review: if any category has page > 5 and result_count > 100 consistently,
-- consider adding a third nesting level for that category.

CREATE TABLE browser_telemetry (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    domain       TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    page         INTEGER NOT NULL,
    result_count INTEGER NOT NULL,
    recorded_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
