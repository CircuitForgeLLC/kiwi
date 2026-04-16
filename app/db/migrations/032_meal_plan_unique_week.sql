-- 032_meal_plan_unique_week.sql
-- Prevent duplicate plans for the same week.
-- Existing duplicates must be resolved before applying (keep MIN(id) per week_start).
CREATE UNIQUE INDEX IF NOT EXISTS idx_meal_plans_week_start ON meal_plans (week_start);
