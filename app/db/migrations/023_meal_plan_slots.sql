-- 023_meal_plan_slots.sql
CREATE TABLE meal_plan_slots (
  id           INTEGER PRIMARY KEY,
  plan_id      INTEGER NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
  day_of_week  INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
  meal_type    TEXT    NOT NULL,
  recipe_id    INTEGER REFERENCES recipes(id),
  servings     REAL    NOT NULL DEFAULT 2.0,
  custom_label TEXT,
  UNIQUE(plan_id, day_of_week, meal_type)
);
