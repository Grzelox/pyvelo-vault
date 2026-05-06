-- Add Garmin Connect integration fields to users table

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS garmin_access_token TEXT,
    ADD COLUMN IF NOT EXISTS garmin_refresh_token TEXT,
    ADD COLUMN IF NOT EXISTS garmin_token_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS garmin_user_id TEXT,
    ADD COLUMN IF NOT EXISTS last_garmin_sync TIMESTAMPTZ;

