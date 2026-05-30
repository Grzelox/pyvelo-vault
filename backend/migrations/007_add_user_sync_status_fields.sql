-- Add aggregate sync status fields to users table

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_sync_source TEXT,
    ADD COLUMN IF NOT EXISTS last_sync_status TEXT,
    ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_last_sync_at ON users(last_sync_at);
