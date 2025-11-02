# Database Migrations

This directory contains SQL migration scripts for the pyvelo-vault database.

## Current Migrations

### 001_change_activity_id_to_bigint.sql

**Issue**: Strava activity IDs are 64-bit integers that exceed PostgreSQL's INTEGER type limit (max: 2,147,483,647).

**Solution**: Changes the `activities.id` column from INTEGER to BIGINT to support Strava's large activity IDs.

## How to Apply Migrations

### Option 1: Using the apply script (Recommended)

From inside the API container:
```bash
docker exec -it pyvelo_api bash -c "cd /code && ./migrations/apply.sh"
```

### Option 2: Using psql directly

```bash
# From host machine
docker exec -it pyvelo_db psql -U user -d pyvelovaultdb -c "ALTER TABLE activities ALTER COLUMN id TYPE BIGINT;"

# Or connect to the database interactively
docker exec -it pyvelo_db psql -U user -d pyvelovaultdb
```

Then run:
```sql
ALTER TABLE activities ALTER COLUMN id TYPE BIGINT;
```

### Option 3: Recreate the database (Development only)

If you don't have any important data:

```bash
# Stop containers
docker compose down

# Remove the volume
docker volume rm pyvelo-vault-data

# Start fresh (tables will be created with new schema)
docker compose up -d
```

## Verify Migration

After applying the migration, verify it worked:

```bash
docker exec -it pyvelo_db psql -U user -d pyvelovaultdb -c "\d activities"
```

You should see `id | bigint` instead of `id | integer`.

## Future Migrations

This project currently doesn't use Alembic or similar migration tools. For production use, consider setting up a proper migration framework.
