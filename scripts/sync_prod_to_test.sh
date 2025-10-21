#!/bin/bash
# sync_prod_to_test.sh
# Syncs production database to test database
# WARNING: This will DESTROY all data in the test database!
#
# Usage:
#   1. Set environment variables:
#      export PROD_DB="postgresql://postgres:password@host:5432/clean_repair"
#      export DATABASE_URL="postgresql://postgres:password@host:5432/clean_repair_test"
#   2. Run: ./scripts/sync_prod_to_test.sh

set -e  # Exit on error

echo "===== Production to Test Database Sync ====="
echo ""

# Check for required environment variables
if [ -z "$PROD_DB" ]; then
    echo "❌ Error: PROD_DB environment variable not set"
    echo "   Example: export PROD_DB=\"postgresql://user:pass@host:5432/clean_repair\""
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable not set"
    echo "   Example: export DATABASE_URL=\"postgresql://user:pass@host:5432/clean_repair_test\""
    exit 1
fi

echo "Production DB: $PROD_DB"
echo "Test DB:       $DATABASE_URL"
echo ""
echo "⚠️  WARNING: This will completely replace the test database with production data"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Sync cancelled."
    exit 0
fi

# Temporary dump file
DUMP_FILE="/tmp/prod_db_dump_$(date +%Y%m%d_%H%M%S).sql"

echo ""
echo "Step 1: Dumping production database..."
pg_dump "$PROD_DB" -F p -f "$DUMP_FILE"

echo "✓ Production database dumped to $DUMP_FILE"
FILE_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "  Dump file size: $FILE_SIZE"
echo ""

echo "Step 2: Dropping and recreating test database..."
# Extract database name from DATABASE_URL for the drop/create commands
# DATABASE_URL format: postgresql://user:pass@host:port/dbname
TEST_DB_NAME=$(echo "$DATABASE_URL" | sed 's/.*\///')
# Connection string without database name (connect to 'postgres' database)
POSTGRES_URL=$(echo "$DATABASE_URL" | sed 's/\/[^\/]*$/\/postgres/')

psql "$POSTGRES_URL" -c "DROP DATABASE IF EXISTS $TEST_DB_NAME;" 2>/dev/null || true
psql "$POSTGRES_URL" -c "CREATE DATABASE $TEST_DB_NAME;"

echo "✓ Test database recreated"
echo ""

echo "Step 3: Restoring production data to test database..."
psql "$DATABASE_URL" -f "$DUMP_FILE" -q

echo "✓ Data restored to test database"
echo ""

echo "Step 4: Cleaning up dump file..."
rm "$DUMP_FILE"
echo "✓ Dump file removed"
echo ""

echo "===== Sync Complete ====="
echo "Production data has been synced to test database"
echo ""
echo "Next steps:"
echo "  1. Verify test database: ./alembic_db.sh test current"
echo "  2. Run migrations if needed: ./alembic_db.sh test upgrade head"
echo "  3. Run tests: pytest"
