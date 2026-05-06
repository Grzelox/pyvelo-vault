-- Add start_date column to activities table
-- This stores the UTC timestamp when the activity started
ALTER TABLE activities ADD COLUMN start_date TIMESTAMP WITH TIME ZONE;

