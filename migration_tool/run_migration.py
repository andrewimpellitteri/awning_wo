# migration_tool/run_migration.py

import click
import subprocess
import sqlite3
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
from datetime import datetime

# Add project root to Python path to allow importing from other directories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from extensions import db
from app import create_app

# Configuration (can be overridden via CLI arguments)
ACCESS_DB_PATH = "data/csv_export/Clean_Repair.accdb"
SQLITE_DB_PATH = "migration_tool/intermediate.sqlite"
POSTGRES_URI = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/clean_repair"
)


# =============================================================================
# DATA TYPE CONVERSION FUNCTIONS
# =============================================================================


def convert_date_field(value):
    """Convert various date string formats to proper date object - handles messy data"""
    if pd.isna(value) or value in ["", None, "0000-00-00", "00/00/00", "00/00/0000"]:
        return None

    # Convert to string for processing
    str_value = str(value).strip()

    # Check for invalid dates with day/month = 00
    # These are common in Access databases to represent "no date"
    if "/00/" in str_value or str_value.startswith("00/") or "/00 " in str_value:
        return None

    try:
        # Try pandas to_datetime first (handles most formats)
        parsed = pd.to_datetime(str_value, errors="coerce")
        if pd.notna(parsed):
            # Validate the parsed date is reasonable (not year 1900, not future)
            date_obj = parsed.date()
            if date_obj.year < 1970 or date_obj.year > 2050:
                return None
            return date_obj
    except:
        pass

    # Try common formats explicitly
    formats = [
        "%Y-%m-%d",  # 2024-01-15
        "%m/%d/%y %H:%M:%S",  # 01/15/24 14:30:00
        "%m/%d/%Y %H:%M:%S",  # 01/15/2024 14:30:00
        "%m/%d/%Y",  # 01/15/2024
        "%m/%d/%y",  # 01/15/24
        "%Y-%m-%dT%H:%M:%S",  # ISO format
    ]

    for fmt in formats:
        try:
            parsed_date = datetime.strptime(str_value, fmt).date()
            # Validate year range
            if parsed_date.year < 1970 or parsed_date.year > 2050:
                return None
            return parsed_date
        except (ValueError, AttributeError):
            continue

    # Only log if it's not one of the common invalid patterns
    if not any(invalid in str_value for invalid in ["01/00/00", "00/00/", "/00/"]):
        click.echo(f"    ⚠️  Could not convert date value: {repr(value)}")
    return None


def convert_boolean_field(value):
    """Convert string boolean to actual boolean - handles messy legacy data"""
    if pd.isna(value) or value in ["", None]:
        return None

    # Convert to uppercase string for comparison
    str_value = str(value).strip().upper()

    # Truthy values
    if str_value in ("1", "YES", "Y", "TRUE", "T"):
        return True

    # Falsy values (explicit false)
    if str_value in ("0", "NO", "N", "FALSE", "F"):
        return False

    # Default to None for unexpected values
    return None


def convert_numeric_field(value, field_type="integer"):
    """Convert string numeric to integer or decimal"""
    if pd.isna(value) or value in ["", None]:
        return None

    try:
        # Remove currency symbols and commas
        cleaned = str(value).replace("$", "").replace(",", "").strip()

        if field_type == "integer":
            # Convert to int
            return int(float(cleaned))  # float first to handle "5.0" -> 5
        else:
            # Convert to decimal (for Price fields)
            return round(float(cleaned), 2)
    except (ValueError, AttributeError):
        click.echo(f"    ⚠️  Could not convert numeric value: {repr(value)}")
        return None


def apply_type_conversions(df, table_name):
    """Apply data type conversions to dataframe based on table"""
    click.echo(f"    - Applying data type conversions...")

    # WorkOrder table conversions
    if table_name.lower() == "tblcustworkorderdetail":
        # Boolean fields FIRST (needed for auto-completion logic)
        for bool_field in ["rushorder", "firmrush", "quote", "seerepair"]:
            if bool_field in df.columns:
                df[bool_field] = df[bool_field].apply(convert_boolean_field)

        # Date fields - convert to pandas datetime64[ns] format
        # Keep as datetime during processing, convert to date objects at the end
        for date_field in ["datecompleted", "daterequired", "datein", "clean", "treat"]:
            if date_field in df.columns:
                # Apply custom conversion first (handles invalid dates)
                df[date_field] = df[date_field].apply(convert_date_field)
                # Convert to pandas datetime (NaT for None values, not NaTType objects)
                df[date_field] = pd.to_datetime(df[date_field], errors="coerce")

        # OPTIMAL AUTO-COMPLETION: Handle Access sentinel value "01/00/00 00:00:00"
        # Based on EDA: 732 records with this sentinel, all 1+ years old, 96.9% have no clean/treat dates
        if "datecompleted" in df.columns and "datein" in df.columns:
            click.echo(
                f"    - DEBUG: Starting auto-completion (datein type: {df['datein'].dtype}, datecompleted type: {df['datecompleted'].dtype})"
            )
            # Configuration: Only auto-complete orders older than 1 year
            AGE_THRESHOLD_DAYS = 365

            try:
                click.echo("    - DEBUG: Checking types before age calculation:")
                for col in [
                    "datein",
                    "datecompleted",
                    "daterequired",
                    "clean",
                    "treat",
                ]:
                    if col in df.columns:
                        types_summary = (
                            df[col]
                            .map(lambda x: type(x).__name__)
                            .value_counts()
                            .to_dict()
                        )
                        click.echo(f"      {col}: {types_summary}")

                # Calculate age of each work order
                today = pd.Timestamp.now()
                datein_ts = pd.to_datetime(df["datein"])
                age_days = (today - datein_ts).dt.days
                click.echo(
                    f"    - DEBUG: age_days calculated (dtype: {age_days.dtype}, NaNs: {age_days.isna().sum()})"
                )

                # Identify old incomplete orders (NULL datecompleted from sentinel conversion)
                # Filter out records where datein is NULL (age_days would be NaN)
                old_incomplete_mask = (
                    (df["datecompleted"].isna())
                    & (df["datein"].notna())
                    & (age_days > AGE_THRESHOLD_DAYS)
                )
                click.echo(f"    - DEBUG: old_incomplete_mask created")

                total_incomplete = old_incomplete_mask.sum()
            except Exception as e:
                click.echo(
                    f"    - DEBUG ERROR in age calculation: {type(e).__name__}: {e}"
                )
                import traceback

                click.echo(traceback.format_exc())
                raise
            if total_incomplete > 0:
                click.echo(
                    f"    - Found {total_incomplete} old work orders (>1 year) with NULL datecompleted (sentinel: 01/00/00)"
                )

                # Track completion method statistics
                completed_from_service = 0
                completed_from_required = 0
                completed_from_estimate = 0

                # PRIORITY 1: Use clean/treat service dates (most accurate)
                if "clean" in df.columns and "treat" in df.columns:
                    # Create mask for rows that have at least one service date
                    has_service = df["clean"].notna() | df["treat"].notna()
                    service_candidates = old_incomplete_mask & has_service

                    if service_candidates.sum() > 0:
                        # Only compute max for rows that have at least one service date
                        service_date = df.loc[
                            service_candidates, ["clean", "treat"]
                        ].max(axis=1, skipna=True)
                        completed_from_service = service_candidates.sum()

                        # Assign service dates
                        df.loc[service_candidates, "datecompleted"] = (
                            service_date.values
                        )
                        click.echo(
                            f"      ✓ {completed_from_service} completed using clean/treat dates"
                        )

                # PRIORITY 2: Use daterequired (customer's deadline - likely done by then)
                still_incomplete = old_incomplete_mask & df["datecompleted"].isna()
                if "daterequired" in df.columns:
                    required_mask = still_incomplete & df["daterequired"].notna()
                    completed_from_required = required_mask.sum()

                    if completed_from_required > 0:
                        df.loc[required_mask, "datecompleted"] = df["daterequired"]
                        click.echo(
                            f"      ✓ {completed_from_required} completed using daterequired deadline"
                        )

                # PRIORITY 3: Intelligent estimate based on rush vs normal turnaround
                still_incomplete = old_incomplete_mask & df["datecompleted"].isna()
                completed_from_estimate = still_incomplete.sum()

                if completed_from_estimate > 0:
                    # Realistic turnaround times based on business logic
                    # Rush orders: 3 days, Normal orders: 14 days (2 weeks)
                    if "rushorder" in df.columns:
                        # Get rushorder values for incomplete records (True, False, or None)
                        rush_values = df.loc[still_incomplete, "rushorder"].fillna(
                            False
                        )
                        is_rush = rush_values == True
                        rush_count = is_rush.sum()
                    else:
                        is_rush = pd.Series(
                            [False] * completed_from_estimate,
                            index=df[still_incomplete].index,
                        )
                        rush_count = 0

                    # Assign turnaround days: 3 for rush, 14 for normal
                    turnaround_days = np.where(is_rush, 3, 14)

                    # Get datein values for incomplete records as timestamps
                    datein_subset = pd.to_datetime(df.loc[still_incomplete, "datein"])

                    # Calculate estimated completion dates
                    estimated_completion = datein_subset + pd.to_timedelta(
                        turnaround_days, unit="D"
                    )

                    # Convert back to date objects (matching the column type)
                    df.loc[still_incomplete, "datecompleted"] = estimated_completion

                    normal_count = completed_from_estimate - rush_count

                    click.echo(
                        f"      ✓ {completed_from_estimate} completed using intelligent estimates:"
                    )
                    if rush_count > 0:
                        click.echo(
                            f"        - {rush_count} rush orders (3-day turnaround)"
                        )
                    if normal_count > 0:
                        click.echo(
                            f"        - {normal_count} normal orders (14-day turnaround)"
                        )

                # Summary statistics
                click.echo(f"    - 📊 Auto-completion summary:")
                click.echo(
                    f"      - From service dates: {completed_from_service} ({completed_from_service / total_incomplete * 100:.1f}%)"
                )
                click.echo(
                    f"      - From deadline dates: {completed_from_required} ({completed_from_required / total_incomplete * 100:.1f}%)"
                )
                click.echo(
                    f"      - From estimates: {completed_from_estimate} ({completed_from_estimate / total_incomplete * 100:.1f}%)"
                )

        # Convert datetime64[ns] columns back to date objects for database insertion
        for date_field in ["datecompleted", "daterequired", "datein", "clean", "treat"]:
            if date_field in df.columns:
                df[date_field] = df[date_field].dt.date

    # RepairWorkOrder table conversions
    elif table_name.lower() == "tblrepairworkorderdetail":
        # Date fields - convert to pandas datetime64[ns] format
        # Keep as datetime during processing, convert to date objects at the end
        date_fields_map = {
            "WO DATE": "WO DATE",
            "DATE TO SUB": "DATE TO SUB",
            "daterequired": "daterequired",
            "datecompleted": "datecompleted",
            "returndate": "returndate",
            "dateout": "dateout",
            "datein": "datein",
        }
        for field_name in date_fields_map.values():
            if field_name in df.columns:
                # Apply custom conversion first (handles invalid dates)
                df[field_name] = df[field_name].apply(convert_date_field)
                # Convert to pandas datetime (NaT for None values)
                df[field_name] = pd.to_datetime(df[field_name], errors="coerce")

        # OPTIMAL AUTO-COMPLETION: Handle Access sentinel value for repair orders
        if "datecompleted" in df.columns and "datein" in df.columns:
            # Configuration: Only auto-complete orders older than 1 year
            AGE_THRESHOLD_DAYS = 365

            # Calculate age of each repair order
            today = pd.Timestamp.now()
            datein_ts = pd.to_datetime(df["datein"])
            age_days = (today - datein_ts).dt.days

            # Identify old incomplete repair orders
            # Filter out records where datein is NULL (age_days would be NaN)
            old_incomplete_mask = (
                (df["datecompleted"].isna())
                & (df["datein"].notna())
                & (age_days > AGE_THRESHOLD_DAYS)
            )

            total_incomplete = old_incomplete_mask.sum()
            if total_incomplete > 0:
                click.echo(
                    f"    - Found {total_incomplete} old repair orders (>1 year) with NULL datecompleted"
                )

                # Track completion method statistics
                completed_from_return = 0
                completed_from_required = 0
                completed_from_estimate = 0

                # PRIORITY 1: Use returndate (most accurate for repairs)
                if "returndate" in df.columns:
                    return_mask = old_incomplete_mask & df["returndate"].notna()
                    completed_from_return = return_mask.sum()

                    if completed_from_return > 0:
                        df.loc[return_mask, "datecompleted"] = df["returndate"]
                        click.echo(
                            f"      ✓ {completed_from_return} completed using returndate"
                        )

                # PRIORITY 2: Use daterequired
                still_incomplete = old_incomplete_mask & df["datecompleted"].isna()
                if "daterequired" in df.columns:
                    required_mask = still_incomplete & df["daterequired"].notna()
                    completed_from_required = required_mask.sum()

                    if completed_from_required > 0:
                        df.loc[required_mask, "datecompleted"] = df["daterequired"]
                        click.echo(
                            f"      ✓ {completed_from_required} completed using daterequired deadline"
                        )

                # PRIORITY 3: Intelligent estimate (repairs take longer - use 21 days)
                still_incomplete = old_incomplete_mask & df["datecompleted"].isna()
                completed_from_estimate = still_incomplete.sum()

                if completed_from_estimate > 0:
                    # Repairs typically take 3 weeks (21 days)
                    # Get datein values for incomplete records as timestamps
                    datein_subset = pd.to_datetime(df.loc[still_incomplete, "datein"])

                    # Calculate estimated completion dates
                    estimated_completion = datein_subset + pd.Timedelta(days=21)

                    # Assign estimated completion (still as datetime64[ns])
                    df.loc[still_incomplete, "datecompleted"] = estimated_completion

                    click.echo(
                        f"      ✓ {completed_from_estimate} completed using intelligent estimate (21-day turnaround)"
                    )

                # Summary statistics
                click.echo(f"    - 📊 Auto-completion summary:")
                click.echo(
                    f"      - From return dates: {completed_from_return} ({completed_from_return / total_incomplete * 100:.1f}%)"
                )
                click.echo(
                    f"      - From deadline dates: {completed_from_required} ({completed_from_required / total_incomplete * 100:.1f}%)"
                )
                click.echo(
                    f"      - From estimates: {completed_from_estimate} ({completed_from_estimate / total_incomplete * 100:.1f}%)"
                )

        # Boolean fields
        for bool_field in [
            "rushorder",
            "firmrush",
            "quote",
            "approved",
            "clean",
            "cleanfirst",
        ]:
            if bool_field in df.columns:
                df[bool_field] = df[bool_field].apply(convert_boolean_field)

        # Convert datetime64[ns] columns back to date objects for database insertion
        for field_name in date_fields_map.values():
            if field_name in df.columns:
                df[field_name] = df[field_name].dt.date

    # WorkOrderItem and RepairWorkOrderItem conversions
    elif table_name.lower() in ["tblorddetcustawngs", "tblreporddetcustawngs"]:
        if "qty" in df.columns:
            df["qty"] = df["qty"].apply(lambda x: convert_numeric_field(x, "integer"))
        if "price" in df.columns:
            df["price"] = df["price"].apply(
                lambda x: convert_numeric_field(x, "decimal")
            )

    # Inventory table conversions
    elif table_name.lower() == "tblcustawngs":
        if "qty" in df.columns:
            df["qty"] = df["qty"].apply(lambda x: convert_numeric_field(x, "integer"))
        if "price" in df.columns:
            df["price"] = df["price"].apply(
                lambda x: convert_numeric_field(x, "decimal")
            )

    # Remove temporary columns that shouldn't be inserted into database
    if "_original_datecompleted" in df.columns:
        df = df.drop(columns=["_original_datecompleted"])

    return df


@click.group()
def cli():
    """Database Migration Tool"""
    pass


def step_1_accdb_to_sqlite():
    """Converts the Access database to an intermediate SQLite database."""
    click.echo("--- Step 1: Converting Access DB to SQLite ---")

    if os.path.exists(SQLITE_DB_PATH):
        os.remove(SQLITE_DB_PATH)
        click.echo(f"Removed existing SQLite file: {SQLITE_DB_PATH}")

    try:
        # Use mdb-tools to get table names
        tables = (
            subprocess.check_output(["mdb-tables", "-1", ACCESS_DB_PATH])
            .decode()
            .splitlines()
        )

        conn = sqlite3.connect(SQLITE_DB_PATH)

        for table in tables:
            click.echo(f"  - Processing table: {table}")
            # Export table to CSV format in memory
            csv_data = subprocess.check_output(
                ["mdb-export", ACCESS_DB_PATH, table]
            ).decode()

            # Use pandas to read CSV and write to SQLite
            df = pd.read_csv(pd.io.common.StringIO(csv_data))
            df.to_sql(table, conn, if_exists="replace", index=False)

        conn.close()
        click.echo("✅ Access to SQLite conversion successful.")
    except Exception as e:
        click.echo(f"❌ Error in Step 1: {e}")
        sys.exit(1)


def step_2_setup_postgres_schema():
    """Sets up the database schema in PostgreSQL."""
    click.echo("\n--- Step 2: Setting up PostgreSQL Schema ---")
    try:
        app = create_app()
        with app.app_context():
            # Use a separate engine for the migration target
            engine = create_engine(POSTGRES_URI)
            db.metadata.drop_all(engine)  # Drop existing tables
            db.metadata.create_all(engine)  # Create new tables based on models
        click.echo("✅ PostgreSQL schema created successfully.")
    except Exception as e:
        click.echo(f"❌ Error in Step 2: {e}")
        sys.exit(1)


def step_3_transfer_data_to_postgres():
    """Transfers data from the SQLite database to PostgreSQL in the correct order."""
    click.echo("\n--- Step 3: Transferring Data to PostgreSQL ---")

    migration_order = [
        "tblsource",
        "tblcustomers",
        "tblcustawngs",
        "tblcustworkorderdetail",
        "tblorddetcustawngs",
        "tblrepairworkorderdetail",
        "tblreporddetcustawngs",
    ]

    column_mappings = {
        "tblcustworkorderdetail": {"rack#": "rack_number"},
        "tblrepairworkorderdetail": {
            # FIXED: Map to exact column names from your model
            "wo date": "WO DATE",  # Uppercase with space (matches your model)
            "date to sub": "DATE TO SUB",  # Uppercase with spaces (matches your model)
            "quote  by": "QUOTE  BY",  # TWO spaces between QUOTE and BY (matches your model)
            "rack#": "RACK#",  # Uppercase with # (matches your model)
            "item type": "ITEM TYPE",  # Uppercase with space (matches your model)
            "type of repair": "TYPE OF REPAIR",  # Uppercase with spaces (matches your model)
        },
    }

    try:
        sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB_PATH}")
        postgres_engine = create_engine(POSTGRES_URI)

        sqlite_conn = sqlite_engine.connect()

        all_sqlite_tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table';", sqlite_conn
        )["name"].tolist()
        sqlite_table_map = {t.lower(): t for t in all_sqlite_tables}

        for table_name in migration_order:
            source_table_name = sqlite_table_map.get(table_name.lower())

            if source_table_name:
                click.echo(
                    f"  - Transferring table: {source_table_name} -> {table_name}"
                )
                try:
                    df = pd.read_sql_table(source_table_name, sqlite_conn)

                    df.columns = [col.lower() for col in df.columns]

                    if table_name.lower() in column_mappings:
                        df.rename(
                            columns=column_mappings[table_name.lower()], inplace=True
                        )

                    # --- Data Cleaning and Type Conversion ---
                    if "custid" in df.columns:
                        df["custid"] = pd.to_numeric(df["custid"], errors="coerce")
                        df.dropna(subset=["custid"], inplace=True)
                        df["custid"] = df["custid"].astype(int)

                    # FIXED: Enhanced cleaning for WorkOrderDetail
                    if table_name.lower() == "tblcustworkorderdetail":
                        # custid filtering already done above (line 567)
                        # datein filtering happens after type conversion (below)
                        # Clean shipto values - replace invalid ones with 'Customer'
                        if "shipto" in df.columns:
                            # Get valid sources from PostgreSQL (already migrated)
                            valid_sources_df = pd.read_sql(
                                "SELECT DISTINCT ssource FROM tblsource",
                                postgres_engine,
                            )
                            valid_sources = set(
                                valid_sources_df["ssource"].dropna().unique()
                            )

                            # Add any missing sources referenced in shipto
                            missing_sources = df[
                                ~df["shipto"].isin(valid_sources) & df["shipto"].notna()
                            ]["shipto"].unique()
                            if len(missing_sources) > 0:
                                click.echo(
                                    f"    - Found {len(missing_sources)} shipto values not in source table, adding skeleton records..."
                                )
                                # Create skeleton source records for missing shipto values
                                missing_sources_df = pd.DataFrame(
                                    {"ssource": missing_sources}
                                )
                                missing_sources_df.to_sql(
                                    "tblsource",
                                    postgres_engine,
                                    if_exists="append",
                                    index=False,
                                )
                                click.echo(
                                    f"    - Added {len(missing_sources)} skeleton source records for shipto references"
                                )

                    # FIXED: Enhanced cleaning for WorkOrderItems
                    if table_name.lower() == "tblorddetcustawngs":
                        # Description is required (NOT NULL constraint), drop rows with null
                        initial_count = len(df)
                        df.dropna(subset=["description"], inplace=True)
                        dropped_count = initial_count - len(df)
                        if dropped_count > 0:
                            click.echo(
                                f"    - Dropped {dropped_count} rows with null description"
                            )

                        # Material can be empty string (not null, just empty)
                        df["material"] = df["material"].fillna("")

                        # FIXED: Remove orphaned records - workorders that don't exist in parent table
                        if "workorderno" in df.columns:
                            # Get valid work order numbers from the database
                            valid_workorders = pd.read_sql(
                                "SELECT DISTINCT workorderno FROM tblcustworkorderdetail",
                                postgres_engine,
                            )["workorderno"].tolist()

                            # FIXED: Convert both to same data type for comparison
                            # Convert work order numbers to strings for comparison
                            df["workorderno"] = df["workorderno"].astype(str)
                            valid_workorders_str = [str(wo) for wo in valid_workorders]

                            # DEBUG: Show some sample work order numbers after conversion
                            sample_items_wos = df["workorderno"].head(10).tolist()
                            sample_valid_wos = valid_workorders_str[:10]
                            click.echo(
                                f"    - Sample item work orders (str): {sample_items_wos}"
                            )
                            click.echo(
                                f"    - Sample valid work orders (str): {sample_valid_wos}"
                            )

                            orphaned_count = len(
                                df[~df["workorderno"].isin(valid_workorders_str)]
                            )
                            if orphaned_count > 0:
                                click.echo(
                                    f"    - Found {orphaned_count} orphaned work order items (referencing non-existent work orders)"
                                )
                                df = df[df["workorderno"].isin(valid_workorders_str)]
                                click.echo(
                                    f"    - Filtered to {len(df)} valid work order items"
                                )

                        df.drop_duplicates(
                            subset=["workorderno", "description", "material"],
                            keep="first",
                            inplace=True,
                        )

                    # FIXED: Enhanced cleaning for RepairWorkOrder
                    if table_name.lower() == "tblrepairworkorderdetail":
                        # Check if the mapped columns exist after mapping
                        expected_mapped_cols = [
                            "WO DATE",
                            "DATE TO SUB",
                            "QUOTE  BY",
                            "RACK#",
                            "ITEM TYPE",
                            "TYPE OF REPAIR",
                        ]
                        missing_cols = [
                            col for col in expected_mapped_cols if col not in df.columns
                        ]
                        if missing_cols:
                            click.echo(
                                f"    - ⚠️  Missing columns after mapping: {missing_cols}"
                            )
                            click.echo(f"    - Available columns: {list(df.columns)}")
                            # Continue anyway, but log the issue

                        # FIXED: Remove repair orders with invalid customer IDs
                        if "custid" in df.columns:
                            # Get valid customer IDs from the database
                            valid_customers = pd.read_sql(
                                "SELECT DISTINCT custid FROM tblcustomers",
                                postgres_engine,
                            )["custid"].tolist()

                            # FIXED: Convert both to same data type for comparison
                            # Convert customer IDs to integers for comparison
                            df["custid"] = pd.to_numeric(df["custid"], errors="coerce")
                            valid_customers_int = [
                                int(cid) for cid in valid_customers if pd.notna(cid)
                            ]

                            # Remove rows where custid conversion failed (NaN)
                            df.dropna(subset=["custid"], inplace=True)
                            df["custid"] = df["custid"].astype(int)

                            invalid_customer_count = len(
                                df[~df["custid"].isin(valid_customers_int)]
                            )
                            if invalid_customer_count > 0:
                                click.echo(
                                    f"    - Found {invalid_customer_count} repair orders with invalid customer IDs"
                                )
                                # DEBUG: Show some sample customer IDs
                                sample_repair_custs = df["custid"].head(10).tolist()
                                sample_valid_custs = valid_customers_int[:10]
                                click.echo(
                                    f"    - Sample repair customer IDs: {sample_repair_custs}"
                                )
                                click.echo(
                                    f"    - Sample valid customer IDs: {sample_valid_custs}"
                                )

                                df = df[df["custid"].isin(valid_customers_int)]
                                click.echo(
                                    f"    - Filtered to {len(df)} repair orders with valid customers"
                                )

                    # FIXED: Enhanced cleaning for RepairWorkOrderItems
                    if table_name.lower() == "tblreporddetcustawngs":
                        # Material and description are required (primary keys)
                        initial_count = len(df)
                        df.dropna(subset=["material", "description"], inplace=True)
                        dropped_count = initial_count - len(df)
                        if dropped_count > 0:
                            click.echo(
                                f"    - Dropped {dropped_count} rows with null material/description"
                            )

                        # FIXED: Remove orphaned records - repair orders that don't exist in parent table
                        if "repairorderno" in df.columns:
                            # Get valid repair order numbers from the database
                            valid_repairorders = pd.read_sql(
                                "SELECT DISTINCT repairorderno FROM tblrepairworkorderdetail",
                                postgres_engine,
                            )["repairorderno"].tolist()

                            # FIXED: Convert both to same data type for comparison
                            df["repairorderno"] = df["repairorderno"].astype(str)
                            valid_repairorders_str = [
                                str(ro) for ro in valid_repairorders
                            ]

                            orphaned_count = len(
                                df[~df["repairorderno"].isin(valid_repairorders_str)]
                            )
                            if orphaned_count > 0:
                                click.echo(
                                    f"    - Found {orphaned_count} orphaned repair order items (referencing non-existent repair orders)"
                                )
                                df = df[
                                    df["repairorderno"].isin(valid_repairorders_str)
                                ]
                                click.echo(
                                    f"    - Filtered to {len(df)} valid repair order items"
                                )

                        df.drop_duplicates(
                            subset=["repairorderno", "description", "material"],
                            keep="first",
                            inplace=True,
                        )

                    # Apply data type conversions
                    df = apply_type_conversions(df, table_name)

                    # Filter out rows with NULL datein after type conversions
                    if table_name.lower() == "tblcustworkorderdetail":
                        if "datein" in df.columns:
                            before_count = len(df)
                            df = df[df["datein"].notna()]
                            after_count = len(df)
                            if before_count > after_count:
                                click.echo(
                                    f"    - Filtered out {before_count - after_count} rows with NULL datein (after type conversion)"
                                )

                    # FIXED: Use smaller chunks and handle errors gracefully
                    try:
                        df.to_sql(
                            table_name,
                            postgres_engine,
                            if_exists="append",
                            index=False,
                            chunksize=500,
                        )
                        click.echo(f"    - ✅ Successfully transferred {len(df)} rows")

                        # POST-MIGRATION: After sources are migrated, check for missing customer source references
                        if table_name.lower() == "tblsource":
                            click.echo(
                                "  - Checking for customer source references not in tblsource..."
                            )
                            customers_df = pd.read_sql_table(
                                "tblCustomers", sqlite_conn
                            )
                            customer_sources = customers_df["Source"].dropna().unique()

                            # Get sources already migrated
                            migrated_sources_df = pd.read_sql(
                                "SELECT DISTINCT ssource FROM tblsource",
                                postgres_engine,
                            )
                            migrated_sources = set(
                                migrated_sources_df["ssource"].dropna().unique()
                            )

                            # Find missing sources
                            missing_sources = [
                                s
                                for s in customer_sources
                                if s not in migrated_sources and pd.notna(s)
                            ]

                            # Also add common shipto values
                            common_shipto_values = [
                                "Customer",
                                "Source",
                                "Ship To",
                                "Pick Up",
                            ]
                            missing_sources.extend(
                                [
                                    s
                                    for s in common_shipto_values
                                    if s not in migrated_sources
                                ]
                            )

                            if missing_sources:
                                click.echo(
                                    f"    - Found {len(missing_sources)} source references not in Access tblsource"
                                )
                                click.echo(
                                    f"    - Adding skeleton records: {missing_sources[:10]}..."
                                )
                                missing_sources_df = pd.DataFrame(
                                    {"ssource": missing_sources}
                                )
                                missing_sources_df.to_sql(
                                    "tblsource",
                                    postgres_engine,
                                    if_exists="append",
                                    index=False,
                                )
                                click.echo(
                                    f"    - Added {len(missing_sources)} skeleton source records"
                                )
                    except Exception as chunk_error:
                        click.echo(
                            f"    - ⚠️  Partial transfer failed for {table_name}: {chunk_error}"
                        )
                        # Try transferring in smaller chunks or row by row for debugging
                        if len(df) > 1:
                            click.echo(
                                f"    - Attempting row-by-row transfer for debugging..."
                            )
                            success_count = 0
                            for idx, row in df.iterrows():
                                try:
                                    row_df = pd.DataFrame([row])
                                    row_df.to_sql(
                                        table_name,
                                        postgres_engine,
                                        if_exists="append",
                                        index=False,
                                    )
                                    success_count += 1
                                except Exception as row_error:
                                    click.echo(f"      - Failed row {idx}: {row_error}")
                                    if (
                                        success_count == 0 and idx < 5
                                    ):  # Show first few errors
                                        click.echo(f"      - Row data: {row.to_dict()}")
                            click.echo(
                                f"    - Successfully transferred {success_count}/{len(df)} rows"
                            )

                except Exception as table_error:
                    click.echo(
                        f"    - ⚠️  Could not transfer table {source_table_name}. Reason: {table_error}"
                    )
            else:
                click.echo(f"  - Skipping table (not found in source): {table_name}")

        # Close connections
        sqlite_conn.close()
        postgres_engine.dispose()
        click.echo("✅ Data transfer to PostgreSQL finished.")
    except Exception as e:
        click.echo(f"❌ Error in Step 3: {e}")
        sys.exit(1)


def step_4_test_migration():
    """Runs tests to validate the migrated data."""
    click.echo("\n--- Step 4: Validating Migrated Data ---")
    try:
        # Use pytest to run the migration tests
        result = subprocess.run(
            ["pytest", "migration_tool/test_migration.py"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            click.echo("✅ All migration tests passed.")
            click.echo(result.stdout)
        else:
            click.echo("❌ Migration tests failed.")
            click.echo(result.stdout)
            click.echo(result.stderr)
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error in Step 4: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--access-file", default=ACCESS_DB_PATH, help="Path to the Access DB file."
)
def run(access_file):
    """Run the full database migration process."""
    global ACCESS_DB_PATH
    ACCESS_DB_PATH = access_file

    click.echo("🚀 Starting database migration...")

    step_1_accdb_to_sqlite()
    step_2_setup_postgres_schema()
    step_3_transfer_data_to_postgres()
    step_4_test_migration()

    click.echo("\n🎉 Migration complete!")


@cli.command()
@click.option(
    "--access-file", default=ACCESS_DB_PATH, help="Path to the Access DB file."
)
def step1(access_file):
    """Step 1: Convert Access DB to SQLite"""
    global ACCESS_DB_PATH
    ACCESS_DB_PATH = access_file
    step_1_accdb_to_sqlite()


@cli.command()
def step2():
    """Step 2: Setup PostgreSQL schema"""
    step_2_setup_postgres_schema()


@cli.command()
def step3():
    """Step 3: Transfer data to PostgreSQL with type conversions"""
    step_3_transfer_data_to_postgres()


@cli.command()
def step4():
    """Step 4: Run validation tests"""
    step_4_test_migration()


if __name__ == "__main__":
    cli()
