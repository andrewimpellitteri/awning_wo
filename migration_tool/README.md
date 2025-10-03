# Database Migration Tool

Migrates the Awning WO database from Microsoft Access (.accdb) to PostgreSQL with proper data types.

## Features

- ✅ Converts Access DB → SQLite → PostgreSQL
- ✅ Applies proper data type conversions (dates, booleans, numerics)
- ✅ Handles messy legacy data (multiple date formats, boolean variations)
- ✅ Backs up and restores user accounts
- ✅ Data quality auditing
- ✅ Ready for AWS RDS deployment

## Quick Start

### Complete Migration (Recommended)

```bash
# Set your PostgreSQL connection
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Run complete migration
./migration_tool/complete_migration.sh
```

This script will:
1. Backup existing users
2. Convert Access DB to SQLite
3. Run data quality audit
4. Create PostgreSQL schema
5. Transfer data with type conversions
6. Restore users
7. (Optional) Run validation tests

### Manual Step-by-Step Migration

```bash
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Step 1: Backup users
python migration_tool/backup_users.py

# Step 2: Convert Access DB to SQLite
python migration_tool/run_migration.py step1

# Step 3: Audit data quality (optional but recommended)
python migration_tool/audit_data_quality.py > audit_report.txt

# Step 4: Create PostgreSQL schema
python migration_tool/run_migration.py step2

# Step 5: Transfer data with type conversions
python migration_tool/run_migration.py step3

# Step 6: Restore users
python migration_tool/restore_users.py migration_tool/users_backup_YYYYMMDD_HHMMSS.json

# Step 7: Run tests (optional)
python migration_tool/run_migration.py step4
```

## Data Type Conversions

### WorkOrder Table
| Field | Old Type | New Type | Notes |
|-------|----------|----------|-------|
| DateCompleted | String | DateTime | Completion timestamp |
| DateRequired | String | Date | Rush order due date |
| DateIn | String | Date | Intake date |
| Clean | String | **Date** | Date when cleaning completed |
| Treat | String | **Date** | Date when treatment completed |
| RushOrder | String | Boolean | Converts "1", "Y", "YES" → True |
| FirmRush | String | Boolean | Converts "1", "Y", "YES" → True |
| Quote | String | Boolean | Quote flag |
| SeeRepair | String | Boolean | Repair reference flag |
| CleanFirstWO | String | String | Work order reference (unchanged) |

### RepairWorkOrder Table
| Field | Old Type | New Type | Notes |
|-------|----------|----------|-------|
| WO_DATE | String | Date | Work order date |
| DATE_TO_SUB | String | Date | Submission date |
| DateCompleted | String | DateTime | Completion timestamp |
| CLEAN | String | Boolean | Uses "YES"/"NO" values |
| CLEANFIRST | String | Boolean | Uses "YES"/"NO" values |
| SEECLEAN | String | String | Work order reference (unchanged) |

### Item Tables (WorkOrderItem, RepairWorkOrderItem, Inventory)
| Field | Old Type | New Type | Notes |
|-------|----------|----------|-------|
| Qty | String | Integer | Strips commas, handles "5.0" → 5 |
| Price | String | Decimal(10,2) | Strips $ and commas |

## Boolean Value Handling

The migration handles messy boolean values:
- **Truthy**: `"1"`, `"YES"`, `"Y"`, `"yes"`, `"y"`, `"TRUE"`, `"True"`, `"true"`, `"T"`
- **Falsy**: `"0"`, `"NO"`, `"N"`, `"no"`, `"n"`, `"FALSE"`, `"False"`, `"false"`, `"F"`
- **Unknown**: Converted to `NULL`

## Date Format Handling

Supports multiple legacy date formats:
- `YYYY-MM-DD` (standard)
- `MM/DD/YY HH:MM:SS` (Access format)
- `MM/DD/YYYY`
- `M/D/YY` (single-digit months/days)
- ISO format (`YYYY-MM-DDTHH:MM:SS`)
- Invalid dates like `"0000-00-00"` → `NULL`

## Files

- `complete_migration.sh` - Master migration script
- `backup_users.py` - Backup user table before migration
- `restore_users.py` - Restore user table after migration
- `audit_data_quality.py` - Audit data before migration
- `run_migration.py` - Main migration logic
- `migration_config.py` - Configuration (paths, DB URIs)
- `DATA_TYPE_MIGRATION_PLAN.md` - Detailed migration plan

## Configuration

Edit `migration_config.py` to change:
- Access DB path (default: `data/csv_export/Clean_Repair.accdb`)
- SQLite intermediate path (default: `migration_tool/intermediate.sqlite`)
- PostgreSQL connection (from `DATABASE_URL` env var or config)

## AWS RDS Deployment

To deploy to AWS RDS:

```bash
# Set RDS connection
export DATABASE_URL="postgresql://user:pass@your-rds-instance.region.rds.amazonaws.com:5432/dbname"

# Run migration
./migration_tool/complete_migration.sh

# Or use the EB environment variable
eb printenv  # Check current DATABASE_URL
```

## Troubleshooting

### "mdb-tools not found"
Install mdb-tools:
```bash
brew install mdb-tools  # macOS
sudo apt-get install mdb-tools  # Ubuntu
```

### "Could not convert date value"
Check the audit report for problematic values:
```bash
python migration_tool/audit_data_quality.py > audit_report.txt
cat audit_report.txt
```

### "Users table not found"
This is normal for fresh migrations. The script will create it during restoration.

### Type conversion warnings
Review warnings in the migration output. Most are handled gracefully (converted to NULL).

## Data Quality Reports

The audit script generates reports showing:
- All unique boolean values in the database
- Sample date formats for each date field
- Invalid dates (0000-00-00, 99/99/99, etc.)
- Currency-formatted numeric values
- Non-numeric values in numeric fields

Save audit reports before migration:
```bash
python migration_tool/audit_data_quality.py > audit_report_$(date +%Y%m%d).txt
```

## Validation

After migration, verify:
1. Row counts match between Access and PostgreSQL
2. Sample records look correct
3. Dates are properly formatted
4. Booleans show as true/false
5. Numeric fields are proper numbers
6. Users can log in

## Backup Strategy

The migration tool automatically creates:
- User table JSON backup (`users_backup_YYYYMMDD_HHMMSS.json`)
- Data quality audit report (`audit_report_YYYYMMDD_HHMMSS.txt`)
- Intermediate SQLite database (`intermediate.sqlite`)

Always keep these files until you've verified the migration.

## See Also

- [DATA_TYPE_MIGRATION_PLAN.md](DATA_TYPE_MIGRATION_PLAN.md) - Comprehensive migration strategy
- [CLAUDE.md](../CLAUDE.md) - Project documentation