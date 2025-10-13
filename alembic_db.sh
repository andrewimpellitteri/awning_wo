#!/bin/bash
# Helper script to run Alembic commands on different databases
#
# Usage:
#   ./alembic_db.sh prod current              # Check production DB status
#   ./alembic_db.sh test current              # Check test DB status
#   ./alembic_db.sh prod upgrade head         # Apply migrations to production
#   ./alembic_db.sh test upgrade head         # Apply migrations to test
#   ./alembic_db.sh prod revision --autogenerate -m "add_field"  # Create new migration
#

DB_ENV=$1
shift  # Remove first argument, pass rest to alembic

case $DB_ENV in
  prod|production)
    export POSTGRES_DB=clean_repair
    echo "🔵 Using PRODUCTION database: clean_repair"
    ;;
  test|testing)
    export POSTGRES_DB=clean_repair_test
    echo "🟢 Using TEST database: clean_repair_test"
    ;;
  *)
    echo "❌ Error: First argument must be 'prod' or 'test'"
    echo "Usage: $0 <prod|test> <alembic command>"
    echo ""
    echo "Examples:"
    echo "  $0 prod current"
    echo "  $0 test upgrade head"
    echo "  $0 prod revision --autogenerate -m 'add new field'"
    exit 1
    ;;
esac

# Run alembic with remaining arguments
alembic "$@"
