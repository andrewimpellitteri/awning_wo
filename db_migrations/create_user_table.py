from app import create_app
from extensions import db
from models.user import User
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        print("Creating 'user' table...")
        User.__table__.create(bind=db.engine)
        print("'user' table created successfully!")
    else:
        print("'user' table already exists.")
