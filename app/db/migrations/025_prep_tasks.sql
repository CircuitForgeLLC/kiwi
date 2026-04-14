-- 025_prep_tasks.sql
CREATE TABLE prep_tasks (
  id               INTEGER PRIMARY KEY,
  session_id       INTEGER NOT NULL REFERENCES prep_sessions(id) ON DELETE CASCADE,
  recipe_id        INTEGER REFERENCES recipes(id),
  slot_id          INTEGER REFERENCES meal_plan_slots(id),
  task_label       TEXT    NOT NULL,
  duration_minutes INTEGER,
  sequence_order   INTEGER NOT NULL,
  equipment        TEXT,
  is_parallel      INTEGER NOT NULL DEFAULT 0,
  notes            TEXT,
  user_edited      INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
