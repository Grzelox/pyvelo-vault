-- Add strava_athlete_id column to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS strava_athlete_id INTEGER;

-- Add comment to document the column
COMMENT ON COLUMN users.strava_athlete_id IS 'Strava athlete ID for the connected account';

