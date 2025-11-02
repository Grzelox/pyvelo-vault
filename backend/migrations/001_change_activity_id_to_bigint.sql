-- Migration: Change activities.id from INTEGER to BIGINT
-- This is required to support Strava activity IDs which are 64-bit integers
-- and exceed PostgreSQL's INTEGER type limit (2,147,483,647)

-- Change the id column type to BIGINT
ALTER TABLE activities ALTER COLUMN id TYPE BIGINT;

-- Note: This migration is safe to run even if there's existing data
-- PostgreSQL will automatically convert existing INTEGER values to BIGINT

