-- 022_meal_plans.sql
CREATE TABLE meal_plans (
  id          INTEGER PRIMARY KEY,
  week_start  TEXT    NOT NULL,
  meal_types  TEXT    NOT NULL DEFAULT '["dinner"]',
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
