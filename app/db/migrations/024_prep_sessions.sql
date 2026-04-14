-- 024_prep_sessions.sql
CREATE TABLE prep_sessions (
  id             INTEGER PRIMARY KEY,
  plan_id        INTEGER NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
  scheduled_date TEXT    NOT NULL,
  status         TEXT    NOT NULL DEFAULT 'draft'
                         CHECK(status IN ('draft','reviewed','done')),
  created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
