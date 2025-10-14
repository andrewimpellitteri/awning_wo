# Alembic Database Migration Guide

## Overview
This project uses Alembic for database schema migrations. Alembic provides version control for your database schema, making it safe and easy to evolve your database structure over time.

## Quick Start

### Basic Commands

```bash
# Check current migration status
./alembic_db.sh prod current      # Production database
./alembic_db.sh test current      # Test database

# View migration history
./alembic_db.sh prod history

# Create a new migration (after modifying models)
./alembic_db.sh test revision --autogenerate -m "add_new_column"

# Apply migrations
./alembic_db.sh test upgrade head    # Test first!
./alembic_db.sh prod upgrade head    # Then production

# Rollback one migration
./alembic_db.sh prod downgrade -1

# Show SQL without executing
./alembic_db.sh prod upgrade head --sql
```

## Workflow: Adding a New Field

Let's say you want to add a new field to the WorkOrder model. Here's the complete workflow:

### 1. Update Your Model

Edit `models/work_order.py`:

```python
class WorkOrder(db.Model):
    __tablename__ = "tblcustworkorderdetail"

    # ... existing fields ...

    # New field
    cleaning_notes = db.Column("cleaning_notes", db.Text, nullable=True)
```

### 2. Create a Migration

```bash
# Generate migration automatically by comparing models to database
./alembic_db.sh test revision --autogenerate -m "add_cleaning_notes_to_work_orders"
```

This creates a new file in `alembic/versions/` like:
`20251013_1930-abc123def456_add_cleaning_notes_to_work_orders.py`

### 3. Review the Migration

**IMPORTANT:** Always review auto-generated migrations!

```bash
# Open the generated migration file
code alembic/versions/20251013_1930-abc123def456_add_cleaning_notes_to_work_orders.py
```

Check that:
- The `upgrade()` function adds the column correctly
- The `downgrade()` function removes it correctly
- No unexpected changes were detected

Example migration:

```python
def upgrade() -> None:
    op.add_column('tblcustworkorderdetail',
                  sa.Column('cleaning_notes', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('tblcustworkorderdetail', 'cleaning_notes')
```

### 4. Test on Test Database First

```bash
# Apply migration to test database
./alembic_db.sh test upgrade head

# Verify the change worked
psql "postgresql://postgres:PASSWORD@HOST:5432/clean_repair_test" -c "\d tblcustworkorderdetail"
```

Test your application with the test database to make sure everything works.

### 5. Apply to Production

```bash
# Apply to production database
./alembic_db.sh prod upgrade head
```

### 6. Deploy Code

```bash
# Commit your changes (model + migration file)
git add models/work_order.py alembic/versions/20251013_1930-*.py
git commit -m "Add cleaning_notes field to WorkOrder"
git push

# Deploy to Elastic Beanstalk
eb deploy
```

## Database Switching

The `alembic_db.sh` helper script manages database switching:

```bash
./alembic_db.sh prod <command>    # Uses clean_repair
./alembic_db.sh test <command>    # Uses clean_repair_test
```

You can also use raw alembic commands with environment variables:

```bash
POSTGRES_DB=clean_repair_test alembic current
```

## Common Scenarios

### Scenario 1: Add a Column

**Model change:**
```python
new_field = db.Column("new_field", db.String(100), nullable=True)
```

**Migration (auto-generated):**
```python
def upgrade():
    op.add_column('table_name', sa.Column('new_field', sa.String(100), nullable=True))

def downgrade():
    op.drop_column('table_name', 'new_field')
```

### Scenario 2: Rename a Column (Issue #82 - Storage + Rack)

For issue #82, you need to combine `storage` and `rack_number` into one field.

**Step 1: Add migration with data transformation:**

```python
def upgrade():
    # Add temporary column
    op.add_column('tblcustworkorderdetail',
                  sa.Column('storage_combined', sa.String(), nullable=True))

    # Migrate data: Combine storage + rack_number
    op.execute("""
        UPDATE tblcustworkorderdetail
        SET storage_combined = CONCAT(
            COALESCE(storage, ''),
            CASE
                WHEN rack_number IS NOT NULL AND rack_number != ''
                THEN ' - Rack: ' || rack_number
                ELSE ''
            END
        )
        WHERE storage IS NOT NULL OR rack_number IS NOT NULL
    """)

    # Drop old columns (optional - keep for historical data)
    # op.drop_column('tblcustworkorderdetail', 'rack_number')

def downgrade():
    # Reverse the migration
    op.drop_column('tblcustworkorderdetail', 'storage_combined')
```

### Scenario 3: Change Column Type

**Model change:**
```python
# Change from String to Text
field = db.Column("field", db.Text)  # was db.String(100)
```

**Migration:**
```python
def upgrade():
    op.alter_column('table_name', 'field',
                    existing_type=sa.String(100),
                    type_=sa.Text())

def downgrade():
    op.alter_column('table_name', 'field',
                    existing_type=sa.Text(),
                    type_=sa.String(100))
```

### Scenario 4: Add an Index

```python
def upgrade():
    op.create_index('idx_workorder_cleaning_notes',
                    'tblcustworkorderdetail',
                    ['cleaning_notes'])

def downgrade():
    op.drop_index('idx_workorder_cleaning_notes',
                  'tblcustworkorderdetail')
```

### Scenario 5: Add Optimistic Locking (Issue #92)

```python
def upgrade():
    # Add version column for optimistic locking
    op.add_column('tblcustworkorderdetail',
                  sa.Column('version', sa.Integer(), nullable=False, server_default='1'))

    # Create index for faster version checks
    op.create_index('idx_workorder_version', 'tblcustworkorderdetail', ['version'])

def downgrade():
    op.drop_index('idx_workorder_version', 'tblcustworkorderdetail')
    op.drop_column('tblcustworkorderdetail', 'version')
```

## Safety Best Practices

### 1. Always Test First
```bash
# Test database first
./alembic_db.sh test upgrade head

# Run application tests
pytest

# If all good, apply to production
./alembic_db.sh prod upgrade head
```

### 2. Backup Before Production Migrations

```bash
# Backup production database before major migrations
pg_dump "postgresql://user:pass@host:5432/clean_repair" > backup_$(date +%Y%m%d_%H%M%S).sql

# Or via RDS snapshot (recommended)
aws rds create-db-snapshot \
    --db-instance-identifier database-1 \
    --db-snapshot-identifier pre-migration-$(date +%Y%m%d)
```

### 3. Review Auto-Generated Migrations

Alembic's autogenerate is smart but not perfect. Always review:
- Check for unexpected table/column drops
- Verify data type changes are correct
- Add data migrations if needed (see Scenario 2)

### 4. Test Rollbacks

```bash
# Apply migration
./alembic_db.sh test upgrade head

# Test rollback
./alembic_db.sh test downgrade -1

# Re-apply
./alembic_db.sh test upgrade head
```

### 5. Keep Migrations Small

Create focused migrations:
- ✅ Good: "add_cleaning_notes_field"
- ✅ Good: "add_index_to_customer_name"
- ❌ Bad: "update_all_tables_for_issue_67_82_92"

## Migration File Structure

```python
"""descriptive_message

Revision ID: abc123def456          # Unique ID for this migration
Revises: previous_revision_id      # Previous migration (creates chain)
Create Date: 2025-10-13 19:30:00

"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123def456'
down_revision = 'previous_id'      # Forms migration chain

def upgrade() -> None:
    """Apply the migration"""
    op.add_column(...)

def downgrade() -> None:
    """Reverse the migration"""
    op.drop_column(...)
```

## Troubleshooting

### Problem: "Can't locate revision identified by 'head'"
**Solution:** Database not stamped. Stamp it:
```bash
./alembic_db.sh prod stamp head
```

### Problem: "Target database is not up to date"
**Solution:** Check status and upgrade:
```bash
./alembic_db.sh prod current
./alembic_db.sh prod upgrade head
```

### Problem: Migration detects changes you didn't make
**Solution:** Your model doesn't match the database. Options:
1. If database is correct: Update your model to match
2. If model is correct: Create migration to update database
3. If both are correct: Check for server_default, type differences

### Problem: "Can't drop column because it's referenced"
**Solution:** Drop foreign key constraints first:
```python
def upgrade():
    op.drop_constraint('fk_name', 'table_name', type_='foreignkey')
    op.drop_column('table_name', 'column_name')
```

## Advanced: Manual Migrations

Sometimes you need to write migrations by hand:

```bash
# Create empty migration
./alembic_db.sh prod revision -m "custom_data_migration"
```

Example - Migrate data between tables:

```python
def upgrade():
    # Use Alembic's connection
    connection = op.get_bind()

    # Execute raw SQL for complex data migrations
    connection.execute("""
        INSERT INTO new_table (field1, field2)
        SELECT old_field1, old_field2 FROM old_table
        WHERE condition = true
    """)

    # Or use SQLAlchemy Core for type safety
    from sqlalchemy import table, column, select
    old_table = table('old_table',
                      column('old_field1'),
                      column('old_field2'))
    new_table = table('new_table',
                      column('field1'),
                      column('field2'))

    # Select and insert
    connection.execute(
        new_table.insert().from_select(
            ['field1', 'field2'],
            select(old_table.c.old_field1, old_table.c.old_field2)
        )
    )
```

## Elastic Beanstalk Deployment

### Option 1: Automatic Migrations (Recommended for Small Teams)

Add to `.ebextensions/02_migrations.config`:

```yaml
container_commands:
  01_migrate:
    command: "source /var/app/venv/*/bin/activate && alembic upgrade head"
    leader_only: true
```

### Option 2: Manual Migrations (Recommended for Production)

```bash
# 1. SSH into EB instance
eb ssh

# 2. Activate virtual environment
source /var/app/venv/*/bin/activate
cd /var/app/current

# 3. Run migration
alembic upgrade head

# 4. Verify
alembic current
```

## Migration History

View all migrations:

```bash
./alembic_db.sh prod history --verbose
```

View current version:

```bash
./alembic_db.sh prod current
```

## Relationship with Old Migration Tool

Your `migration_tool/` directory is kept for historical reference:
- ✅ Use for: Re-migrating from Access DB if needed
- ❌ Don't use for: Schema changes going forward

**Going forward:**
- **Old way:** Modify `run_migration.py` → Drop all tables → Re-import
- **New way:** Modify model → Create Alembic migration → Apply safely

## Summary Cheat Sheet

```bash
# Day-to-day workflow
./alembic_db.sh test revision --autogenerate -m "description"  # Create
./alembic_db.sh test upgrade head                               # Test
./alembic_db.sh prod upgrade head                               # Deploy

# Checking status
./alembic_db.sh prod current    # What version am I on?
./alembic_db.sh prod history    # Show all migrations

# Undoing mistakes
./alembic_db.sh test downgrade -1        # Undo last migration
./alembic_db.sh test downgrade <revision_id>  # Go to specific version

# Previewing changes
./alembic_db.sh prod upgrade head --sql  # Show SQL without running
```

## Next Steps

1. Read through this guide
2. Practice creating a test migration
3. Review your GitHub issues (#67, #82, #92, #98) and plan migrations
4. Test migrations on `clean_repair_test` first
5. Apply to `clean_repair` production

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLAlchemy Column Types](https://docs.sqlalchemy.org/en/14/core/type_basics.html)

## Questions?

If you're unsure about a migration:
1. Test on `clean_repair_test` first
2. Review the auto-generated SQL
3. Create a database backup
4. Ask for review if making destructive changes
