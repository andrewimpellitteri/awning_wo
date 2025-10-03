#!/usr/bin/env python3
"""
Data quality audit script - run BEFORE migration to understand data variations.

This script audits the intermediate SQLite database created from the Access DB
to identify all value variations in boolean, date, and numeric fields.

Usage:
    python migration_tool/audit_data_quality.py
"""
import pandas as pd
from sqlalchemy import create_engine, text
from migration_config import SQLITE_DB_PATH
import os

def audit_boolean_fields(engine):
    """Check what actual values exist in boolean fields"""
    print("\n" + "="*80)
    print("BOOLEAN FIELD AUDIT")
    print("="*80)

    boolean_fields = {
        'tblcustworkorderdetail': ['rushorder', 'firmrush', 'quote', 'seerepair'],
        'tblrepairworkorderdetail': ['rushorder', 'firmrush', 'quote', 'approved', 'clean', 'cleanfirst']
    }

    results = {}
    for table, fields in boolean_fields.items():
        # Check if table exists
        check_query = text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        table_exists = pd.read_sql(check_query, engine)

        if len(table_exists) == 0:
            print(f"\n⚠️  Table {table} not found, skipping...")
            continue

        results[table] = {}
        for field in fields:
            try:
                query = text(f"""
                    SELECT "{field}" as value, COUNT(*) as count
                    FROM "{table}"
                    GROUP BY "{field}"
                    ORDER BY count DESC
                """)
                df = pd.read_sql(query, engine)
                results[table][field] = df
                print(f"\n{table}.{field}:")
                print(df.to_string(index=False))
            except Exception as e:
                print(f"\n{table}.{field}: ERROR - {e}")

    return results

def audit_date_fields(engine):
    """Check date field formats and sample values"""
    print("\n" + "="*80)
    print("DATE FIELD AUDIT")
    print("="*80)

    date_fields = {
        'tblcustworkorderdetail': ['datecompleted', 'daterequired', 'datein', 'clean', 'treat'],
        'tblrepairworkorderdetail': ['WO DATE', 'DATE TO SUB', 'daterequired', 'datecompleted', 'returndate', 'dateout', 'datein']
    }

    results = {}
    for table, fields in date_fields.items():
        # Check if table exists
        check_query = text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        table_exists = pd.read_sql(check_query, engine)

        if len(table_exists) == 0:
            print(f"\n⚠️  Table {table} not found, skipping...")
            continue

        results[table] = {}
        for field in fields:
            try:
                # Sample distinct values
                query = text(f"""
                    SELECT DISTINCT "{field}" as value, COUNT(*) as count
                    FROM "{table}"
                    WHERE "{field}" IS NOT NULL AND "{field}" != ''
                    GROUP BY "{field}"
                    ORDER BY count DESC
                    LIMIT 30
                """)
                df = pd.read_sql(query, engine)
                results[table][field] = df
                print(f"\n{table}.{field} - Top 30 values ({len(df)} unique):")
                print(df.to_string(index=False))

                # Check for potentially invalid dates
                invalid_query = text(f"""
                    SELECT "{field}" as value, COUNT(*) as count
                    FROM "{table}"
                    WHERE "{field}" LIKE '%0000%'
                       OR "{field}" LIKE '%99/99%'
                       OR "{field}" LIKE '%00/00%'
                    GROUP BY "{field}"
                """)
                invalid_df = pd.read_sql(invalid_query, engine)
                if len(invalid_df) > 0:
                    print(f"  ⚠️  WARNING: Potentially invalid dates found:")
                    print(invalid_df.to_string(index=False))
            except Exception as e:
                print(f"\n{table}.{field}: ERROR - {e}")

    return results

def audit_numeric_fields(engine):
    """Check Price and Qty fields for formatting issues"""
    print("\n" + "="*80)
    print("NUMERIC FIELD AUDIT")
    print("="*80)

    numeric_fields = {
        'tblorddetcustawngs': ['qty', 'price'],
        'tblreporddetcustawngs': ['qty', 'price'],
        'tblcustawngs': ['qty', 'price']
    }

    results = {}
    for table, fields in numeric_fields.items():
        # Check if table exists
        check_query = text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        table_exists = pd.read_sql(check_query, engine)

        if len(table_exists) == 0:
            print(f"\n⚠️  Table {table} not found, skipping...")
            continue

        results[table] = {}
        for field in fields:
            try:
                # Sample distinct values
                query = text(f"""
                    SELECT DISTINCT "{field}" as value, COUNT(*) as count
                    FROM "{table}"
                    WHERE "{field}" IS NOT NULL AND "{field}" != ''
                    GROUP BY "{field}"
                    ORDER BY count DESC
                    LIMIT 20
                """)
                df = pd.read_sql(query, engine)
                results[table][field] = df
                print(f"\n{table}.{field} - Sample values:")
                print(df.to_string(index=False))

                # Check for values with currency symbols
                currency_query = text(f"""
                    SELECT "{field}" as value, COUNT(*) as count
                    FROM "{table}"
                    WHERE "{field}" LIKE '%$%' OR "{field}" LIKE '%,%'
                    GROUP BY "{field}"
                    LIMIT 10
                """)
                currency_df = pd.read_sql(currency_query, engine)
                if len(currency_df) > 0:
                    print(f"  Found values with currency formatting:")
                    print(currency_df.to_string(index=False))
            except Exception as e:
                print(f"\n{table}.{field}: ERROR - {e}")

    return results

def generate_audit_report(boolean_results, date_results, numeric_results):
    """Generate summary report of findings"""
    print("\n" + "="*80)
    print("AUDIT SUMMARY REPORT")
    print("="*80)

    # Boolean summary
    print("\nBoolean Field Value Variations:")
    all_bool_values = set()
    for table, fields in boolean_results.items():
        for field, df in fields.items():
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                all_bool_values.update(df['value'].dropna().astype(str).unique())
    print(f"  Unique boolean values found: {sorted(all_bool_values)}")

    # Date format summary
    print("\nDate Format Issues:")
    print("  Check output above for:")
    print("    - Multiple date formats")
    print("    - Invalid dates (0000-00-00, 99/99/99)")
    print("    - Empty strings vs NULL")

    # Numeric summary
    print("\nNumeric Field Issues:")
    print("  Check output above for:")
    print("    - Currency symbols ($)")
    print("    - Commas in numbers")
    print("    - Non-numeric values")

    print("\n" + "="*80)
    print("Next steps:")
    print("1. Review all output above")
    print("2. Verify convert_boolean_field() handles all found variations")
    print("3. Verify convert_date_field() handles all found formats")
    print("4. Run full migration with type conversions")
    print("="*80)

if __name__ == "__main__":
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_DB_PATH}")
        print("Run 'python migration_tool/run_migration.py run --step 1' first to create it")
        exit(1)

    engine = create_engine(f"sqlite:///{SQLITE_DB_PATH}")

    print("Starting data quality audit...")
    print(f"Database: {SQLITE_DB_PATH}")

    boolean_results = audit_boolean_fields(engine)
    date_results = audit_date_fields(engine)
    numeric_results = audit_numeric_fields(engine)

    generate_audit_report(boolean_results, date_results, numeric_results)

    print("\n✅ Audit complete! Review findings above before proceeding with migration.")
