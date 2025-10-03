#!/bin/bash
# complete_migration.sh
# Complete migration from Access DB to PostgreSQL with proper data types
#
# Usage:
#   export DATABASE_URL="postgresql://user:pass@host:port/dbname"
#   ./migration_tool/complete_migration.sh

set -e  # Exit on error

echo "================================================================================"
echo "AWNING WO - COMPLETE DATABASE MIGRATION"
echo "================================================================================"
echo ""

# Check required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable not set"
    echo "Usage: export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    exit 1
fi

# Check if Access DB exists
ACCESS_DB="data/csv_export/Clean_Repair.accdb"
if [ ! -f "$ACCESS_DB" ]; then
    echo "ERROR: Access database not found at $ACCESS_DB"
    exit 1
fi

echo "Target database: $(echo $DATABASE_URL | sed 's/\/\/.*@/\/\/*****@/')"
echo "Source Access DB: $ACCESS_DB"
echo ""

# Step 1: Backup existing users
echo "Step 1: Backing up existing users..."
python migration_tool/backup_users.py
BACKUP_FILE=$(ls -t migration_tool/users_backup_*.json | head -1)
echo "Users backed up to: $BACKUP_FILE"
echo ""

# Step 2: Convert Access DB to SQLite
echo "Step 2: Converting Access DB to SQLite..."
python migration_tool/run_migration.py step1
echo ""

# Step 3: Run data quality audit
echo "Step 3: Running data quality audit..."
python migration_tool/audit_data_quality.py > migration_tool/audit_report_$(date +%Y%m%d_%H%M%S).txt
AUDIT_REPORT=$(ls -t migration_tool/audit_report_*.txt | head -1)
echo "Audit report saved to: $AUDIT_REPORT"
echo ""
echo "Review audit report? (y/n)"
read -r REVIEW
if [ "$REVIEW" = "y" ]; then
    cat "$AUDIT_REPORT"
    echo ""
    echo "Press Enter to continue..."
    read
fi

# Step 4: Create PostgreSQL schema
echo "Step 4: Creating PostgreSQL schema..."
python migration_tool/run_migration.py step2
echo ""

# Step 5: Transfer data with type conversions
echo "Step 5: Transferring data with type conversions..."
python migration_tool/run_migration.py step3
echo ""

# Step 6: Restore users
echo "Step 6: Restoring users..."
python migration_tool/restore_users.py "$BACKUP_FILE"
echo ""

# Step 7: Run validation tests (optional)
echo "Step 7: Run validation tests? (y/n)"
read -r RUN_TESTS
if [ "$RUN_TESTS" = "y" ]; then
    python migration_tool/run_migration.py step4
fi

echo ""
echo "================================================================================"
echo "MIGRATION COMPLETE!"
echo "================================================================================"
echo ""
echo "Summary:"
echo "  - Access DB: $ACCESS_DB"
echo "  - Target DB: $(echo $DATABASE_URL | sed 's/\/\/.*@/\/\/*****@/')"
echo "  - Users backup: $BACKUP_FILE"
echo "  - Audit report: $AUDIT_REPORT"
echo ""
echo "Next steps:"
echo "  1. Verify data in PostgreSQL"
echo "  2. Test the application"
echo "  3. Deploy to AWS RDS"
echo ""
