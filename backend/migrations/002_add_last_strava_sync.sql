-- Migration: Add last_strava_sync column to users table
-- This column tracks when each user was last synced with Strava
-- to enable delta sync (only fetching new activities)

ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_strava_sync TIMESTAMP WITH TIME ZONE;

-- Create an index on the column for faster queries
CREATE INDEX IF NOT EXISTS idx_users_last_strava_sync ON users(last_strava_sync);

COMMENT ON COLUMN users.last_strava_sync IS 'Timestamp of the last successful Strava activity sync';

