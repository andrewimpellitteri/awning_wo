from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from extensions import db
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    # is_active = db.Column(db.Boolean, default=True)
    # created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # last_login = db.Column(db.DateTime)

    # Add role/user type
    role = db.Column(db.String(20), default="user")
    # Examples: "admin", "manager", "staff", "user"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
