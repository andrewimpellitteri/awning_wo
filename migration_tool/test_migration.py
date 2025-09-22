# migration_tool/test_migration.py

import pytest
import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from migration_tool.migration_config import SQLITE_DB_PATH, POSTGRES_URI

@pytest.fixture(scope="module")
def sqlite_engine():
    """Fixture for the source SQLite database engine."""
    return create_engine(f"sqlite:///{SQLITE_DB_PATH}")

@pytest.fixture(scope="module")
def postgres_engine():
    """Fixture for the destination PostgreSQL database engine."""
    return create_engine(POSTGRES_URI)

def get_table_names(engine):
    """Helper function to get table names from a database."""
    if engine.name == 'sqlite':
        query = "SELECT name FROM sqlite_master WHERE type='table';"
    else: # postgres
        query = "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"
    
    with engine.connect() as connection:
        return pd.read_sql(query, connection).iloc[:, 0].tolist()

def test_table_presence(sqlite_engine, postgres_engine):
    """Tests that all tables from SQLite are present in PostgreSQL."""
    sqlite_tables = get_table_names(sqlite_engine)
    postgres_tables = get_table_names(postgres_engine)
    
    # The model names might be different from the table names in the accdb file.
    # This test will likely need adjustment once we see the actual table names.
    # For now, we'll just check that there are tables in both.
    assert len(sqlite_tables) > 0
    assert len(postgres_tables) > 0
    print(f"Found {len(sqlite_tables)} tables in SQLite and {len(postgres_tables)} in PostgreSQL.")


def test_row_counts(sqlite_engine, postgres_engine):
    """Tests that the row counts match for each table."""
    sqlite_tables = get_table_names(sqlite_engine)
    postgres_tables = get_table_names(postgres_engine)
    
    # This is a placeholder. The table names will need to be mapped correctly.
    # For now, we'll just test a few known tables.
    tables_to_test = ['tblCustomers', 'tblCustWorkOrderDetail']
    
    for table_name in tables_to_test:
        if table_name in sqlite_tables and table_name.lower() in postgres_tables:
            sqlite_count = pd.read_sql(f"SELECT COUNT(*) FROM {table_name}", sqlite_engine).iloc[0, 0]
            postgres_count = pd.read_sql(f'SELECT COUNT(*) FROM "{table_name.lower()}"', postgres_engine).iloc[0, 0]
            assert sqlite_count == postgres_count, f"Row count mismatch for table {table_name}"
            print(f"Row count for {table_name} matches: {sqlite_count}")

def test_sample_data_integrity(sqlite_engine, postgres_engine):
    """Tests that some sample data is consistent between the two databases."""
    # This is a placeholder. We'll need to know the actual data to write a meaningful test.
    # For example, we could check a specific customer's name or a work order's details.
    
    # Example for tblCustomers:
    sqlite_tables = get_table_names(sqlite_engine)
    postgres_tables = get_table_names(postgres_engine)
    if 'tblCustomers' in sqlite_tables and 'tblcustomers' in postgres_tables:
        sqlite_customer = pd.read_sql("SELECT * FROM tblCustomers WHERE CustID = '1'", sqlite_engine)
        postgres_customer = pd.read_sql("SELECT * FROM tblcustomers WHERE custid = '1'", postgres_engine)
        
        if not sqlite_customer.empty and not postgres_customer.empty:
            assert sqlite_customer['Name'].iloc[0] == postgres_customer['name'].iloc[0]
            print("Sample customer data integrity check passed.")
