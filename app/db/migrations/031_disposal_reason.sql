-- Migration 031: add disposal_reason for waste logging (#60)
-- status='discarded' already exists in the CHECK constraint from migration 002.
-- This column stores free-text reason (optional) and calm-framing presets.
ALTER TABLE inventory_items ADD COLUMN disposal_reason TEXT;
