#!/bin/bash
source /var/app/venv/*/bin/activate
cd /var/app/current
python -c "
from app import app
from extensions import db
with app.app_context():
    db.create_all()
    print('Database tables created successfully!')
"