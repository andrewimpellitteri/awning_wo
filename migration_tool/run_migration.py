# migration_tool/run_migration.py

import click
import subprocess
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add project root to Python path to allow importing from other directories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from migration_tool.migration_config import ACCESS_DB_PATH, SQLITE_DB_PATH, POSTGRES_URI
from extensions import db
from app import create_app


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

        click.echo("  - Pre-cleaning sources...")

        customers_df = pd.read_sql_table("tblCustomers", sqlite_conn)
        customer_sources = customers_df["Source"].dropna().unique()

        sources_df = pd.read_sql_table("tblSource", sqlite_conn)
        existing_sources = sources_df["SSource"].dropna().unique()

        # FIXED: Add common shipto values that are missing
        common_shipto_values = ["Customer", "Source", "Ship To", "Pick Up"]
        all_needed_sources = list(customer_sources) + common_shipto_values

        new_sources = [
            s for s in all_needed_sources if s not in existing_sources and pd.notna(s)
        ]
        if new_sources:
            click.echo(f"    - Found {len(new_sources)} new sources to add.")
            new_sources_df = pd.DataFrame(new_sources, columns=["SSource"])
            sources_df = pd.concat([sources_df, new_sources_df], ignore_index=True)

            sources_df.to_sql(
                "tblSource", sqlite_conn, if_exists="replace", index=False
            )
            click.echo("    - Updated tblSource in intermediate SQLite DB.")

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
                        df.dropna(subset=["custid"], inplace=True)
                        # Clean shipto values - replace invalid ones with 'Customer'
                        if "shipto" in df.columns:
                            # Get valid sources
                            valid_sources = set(sources_df["SSource"].dropna().unique())
                            # Replace invalid shipto values
                            df.loc[~df["shipto"].isin(valid_sources), "shipto"] = (
                                "Customer"
                            )

                    # FIXED: Enhanced cleaning for WorkOrderItems
                    if table_name.lower() == "tblorddetcustawngs":
                        # Material is required (primary key), so drop rows with null material
                        initial_count = len(df)
                        df.dropna(subset=["material"], inplace=True)
                        dropped_count = initial_count - len(df)
                        if dropped_count > 0:
                            click.echo(
                                f"    - Dropped {dropped_count} rows with null material"
                            )

                        # Also ensure description is not null (also primary key)
                        df.dropna(subset=["description"], inplace=True)

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

        sqlite_conn.close()
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


if __name__ == "__main__":
    cli()
