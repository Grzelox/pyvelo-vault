-- Add calories column to activities table.
-- This stores energy burned in kilocalories when provided by the activity source.
ALTER TABLE activities ADD COLUMN calories DOUBLE PRECISION;
