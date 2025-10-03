#!/usr/bin/env python3
"""
Backup user table from existing database before migration.
This preserves user accounts, passwords, and roles.

Usage:
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"
    python migration_tool/backup_users.py
"""
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
import pandas as pd

def backup_users():
    """Backup all users from the database"""
    print("="*80)
    print("BACKING UP USER TABLE")
    print("="*80)

    # Get database URL from environment
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Usage: export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        sys.exit(1)

    print(f"Source database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'unknown'}")

    engine = create_engine(DATABASE_URL)

    # Check if user or users table exists (handle both singular and plural)
    check_query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name IN ('user', 'users')
    """)

    with engine.connect() as conn:
        result = conn.execute(check_query)
        tables = result.fetchall()

    if len(tables) == 0:
        print("WARNING: user/users table does not exist in database")
        print("Creating empty backup file...")
        backup_data = {
            'users': [],
            'backup_date': datetime.utcnow().isoformat(),
            'source_database': DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'unknown'
        }
    else:
        # Use whichever table exists
        table_name = tables[0][0]
        print(f"Found table: {table_name}")

        # Backup users table
        users_query = text(f'SELECT * FROM "{table_name}"')
        users_df = pd.read_sql(users_query, engine)

        print(f"\nFound {len(users_df)} users to backup:")
        for _, user in users_df.iterrows():
            print(f"  - {user['username']} ({user['role']})")

        # Convert to dictionary
        backup_data = {
            'users': users_df.to_dict('records'),
            'backup_date': datetime.utcnow().isoformat(),
            'source_database': DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'unknown'
        }

    # Save to JSON file
    backup_filename = f"migration_tool/users_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_filename, 'w') as f:
        json.dump(backup_data, f, indent=2, default=str)

    print(f"\n✅ Users backed up to: {backup_filename}")
    print("="*80)

    return backup_filename

if __name__ == "__main__":
    backup_users()
