import subprocess
import sqlite3
import csv
import io

access_file = "data/csv_export/Clean_Repair.accdb"
sqlite_file = "Clean_Repair.sqlite"

# Connect to SQLite
conn = sqlite3.connect(sqlite_file)
cur = conn.cursor()

# Get tables from mdbtools
tables = (
    subprocess.check_output(["mdb-tables", "-1", access_file]).decode().splitlines()
)

for table in tables:
    # Export table to CSV
    csv_data = subprocess.check_output(["mdb-export", access_file, table]).decode()
    csv_file = io.StringIO(csv_data)
    reader = csv.reader(csv_file)

    # Read header
    headers = next(reader)
    col_defs = ", ".join(f'"{h}" TEXT' for h in headers)
    cur.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_defs})')

    # Insert rows
    for row in reader:
        placeholders = ", ".join("?" for _ in row)
        cur.execute(f'INSERT INTO "{table}" VALUES ({placeholders})', row)

conn.commit()
conn.close()
print("Conversion complete!")
