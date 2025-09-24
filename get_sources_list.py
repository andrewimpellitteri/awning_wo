#!/usr/bin/env python3
"""
Export all sources to CSV with isSailLoft classification column
"""

import os
import csv
from datetime import datetime
from sqlalchemy import create_engine, text

# Database connection setup
DATABASE_URL = "postgresql://postgres:Wegetthatshitclean12%21@database-1.ca3sci02uq0g.us-east-1.rds.amazonaws.com:5432/clean_repair"


def get_all_sources_data():
    """Get all source data from the database"""
    try:
        engine = create_engine(DATABASE_URL)

        # Query to get all source data
        query = text("""
            SELECT ssource, sourceaddress, sourcecity, sourcestate, 
                   sourcezip, sourcephone, sourcefax, sourceemail
            FROM tblsource 
            WHERE ssource IS NOT NULL 
            ORDER BY ssource
        """)

        with engine.connect() as connection:
            result = connection.execute(query)
            sources = []

            for row in result.fetchall():
                source_data = {
                    "ssource": row[0],
                    "isSailLoft": "",
                }
                sources.append(source_data)

        return sources

    except Exception as e:
        print(f"Error connecting to database: {e}")
        return []


def export_to_csv(sources, filename=None):
    """Export sources data to CSV"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sources_export_{timestamp}.csv"

    try:
        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "ssource",
                "isSailLoft",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for source in sources:
                writer.writerow(source)

        print(f"Successfully exported {len(sources)} sources to {filename}")
        return filename

    except Exception as e:
        print(f"Error writing CSV file: {e}")
        return None


def main():
    """Main function"""
    print("Fetching all sources from database...")

    sources = get_all_sources_data()

    if not sources:
        print("No sources found or database connection failed.")
        return

    # Export to CSV
    filename = export_to_csv(sources)


if __name__ == "__main__":
    main()
