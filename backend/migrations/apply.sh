#!/bin/bash
# Script to apply database migrations

# Default database connection parameters (can be overridden by environment variables)
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-pyvelovaultdb}
DB_USER=${DB_USER:-user}

echo "Applying database migrations..."
echo "Database: $DB_NAME@$DB_HOST:$DB_PORT"

# Check if running inside Docker
if [ -f /.dockerenv ]; then
    # Inside Docker container, use db as host
    DB_HOST=db
    MIGRATION_DIR=/code/migrations
    export PGPASSWORD=password
else
    # Outside Docker
    MIGRATION_DIR=$(dirname "$0")
fi

# Apply each migration in order
for migration in $MIGRATION_DIR/*.sql; do
    if [ -f "$migration" ]; then
        echo "Applying migration: $(basename $migration)"
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$migration"
        if [ $? -eq 0 ]; then
            echo "✓ $(basename $migration) applied successfully"
        else
            echo "✗ Failed to apply $(basename $migration)"
            exit 1
        fi
    fi
done

echo "All migrations completed!"
