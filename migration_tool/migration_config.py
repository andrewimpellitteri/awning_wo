# migration_tool/migration_config.py

# --- Configuration for the database migration tool ---

# Path to the source Microsoft Access database file
ACCESS_DB_PATH = "data/csv_export/Clean_Repair.accdb"

# Path to the intermediate SQLite database file (will be created by the script)
SQLITE_DB_PATH = "migration_tool/intermediate.sqlite"

# --- PostgreSQL Connection Details ---
# It's recommended to use environment variables for sensitive data like passwords.
# The script will fall back to these values if environment variables are not set.

import os

POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "password")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = "migrated_db"

# SQLAlchemy connection URI for PostgreSQL
POSTGRES_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
