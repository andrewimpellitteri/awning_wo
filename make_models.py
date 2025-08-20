import sqlite3
from jinja2 import Template
import os

DB_PATH = "Clean_Repair.sqlite"  # Change this to your DB file
OUTPUT_DIR = "./models"  # Where the models will be saved

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Connect to SQLite database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]

model_template = Template("""
from extensions import db
from datetime import datetime

class {{ class_name }}(db.Model):
    __tablename__ = "{{ table_name }}"

{% for col in columns %}
    {{ col.name }} = db.Column({{ col.type }}{% if col.pk %}, primary_key=True{% endif %}{% if col.notnull and not col.pk %}, nullable=False{% endif %})
{% endfor %}

    def __repr__(self):
        return f"<{{ class_name }} {{ '{{' }}self.id{{ '}}' }}>"

""")

for table in tables:
    cursor.execute(f'PRAGMA table_info("{table}")')

    cols = cursor.fetchall()

    columns = []
    for c in cols:
        cid, name, ctype, notnull, dflt_value, pk = c
        # Map SQLite types to SQLAlchemy types (basic)
        type_map = {
            "INTEGER": "db.Integer",
            "TEXT": "db.Text",
            "REAL": "db.Float",
            "NUMERIC": "db.Numeric",
            "BLOB": "db.LargeBinary",
        }
        sa_type = type_map.get(ctype.upper(), "db.Text")
        columns.append(
            {"name": name, "type": sa_type, "notnull": bool(notnull), "pk": bool(pk)}
        )

    class_name = "".join(word.capitalize() for word in table.split("_"))
    model_code = model_template.render(
        class_name=class_name, table_name=table, columns=columns
    )

    # Save to file
    with open(os.path.join(OUTPUT_DIR, f"{table}.py"), "w") as f:
        f.write(model_code)

    print(f"Generated model for table: {table}")

conn.close()
