
from extensions import db
from datetime import datetime

class User(db.Model):
    __tablename__ = "user"


    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.Text, nullable=False)

    email = db.Column(db.Text, nullable=False)

    password_hash = db.Column(db.Text, nullable=False)


    def __repr__(self):
        return f"<User {{self.id}}>"
