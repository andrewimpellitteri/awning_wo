#!/usr/bin/env python3
"""
Restore user table from backup file after migration.

Usage:
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"
    python migration_tool/restore_users.py migration_tool/users_backup_20241002_143022.json
"""
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
import pandas as pd
import click


@click.command()
@click.argument('backup_file', type=click.Path(exists=True))
def restore_users(backup_file):
    """Restore users from backup JSON file"""
    print("="*80)
    print("RESTORING USER TABLE")
    print("="*80)

    # Get database URL from environment
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Usage: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        sys.exit(1)

    print(f"Target database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'unknown'}")
    print(f"Backup file: {backup_file}")

    # Load backup file
    with open(backup_file, 'r') as f:
        backup_data = json.load(f)

    print(f"\nBackup created: {backup_data['backup_date']}")
    print(f"Source database: {backup_data['source_database']}")
    print(f"Number of users: {len(backup_data['users'])}")

    if len(backup_data['users']) == 0:
        print("\n⚠️  No users in backup file. Skipping restoration.")
        return

    # Convert to DataFrame
    users_df = pd.DataFrame(backup_data['users'])

    print("\nUsers to restore:")
    for _, user in users_df.iterrows():
        print(f"  - {user['username']} ({user['role']})")

    # Confirm
    if not click.confirm('\nProceed with restoration?'):
        print("Cancelled.")
        return

    # Restore to database
    engine = create_engine(DATABASE_URL)

    # Check which table name to use (user or users)
    check_query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name IN ('user', 'users')
    """)

    with engine.connect() as conn:
        result = conn.execute(check_query)
        tables = result.fetchall()

    # Use existing table name or default to 'user' (matching the schema)
    if len(tables) == 0:
        table_name = 'user'  # Default to singular (matches current schema)
        print(f"\n⚠️  user table does not exist. It will be created as '{table_name}'")
    else:
        table_name = tables[0][0]
        print(f"Restoring to existing table: {table_name}")

    # Insert users
    users_df.to_sql(table_name, engine, if_exists='replace', index=False)

    print(f"\n✅ Successfully restored {len(users_df)} users")
    print("="*80)


if __name__ == "__main__":
    restore_users()
