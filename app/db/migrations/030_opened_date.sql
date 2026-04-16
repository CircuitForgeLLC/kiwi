-- Migration 030: open-package tracking
-- Adds opened_date to track when a multi-use item was first opened,
-- enabling secondary shelf-life windows (e.g. salsa: 1 year sealed → 2 weeks opened).

ALTER TABLE inventory_items ADD COLUMN opened_date TEXT;
