
from extensions import db
from datetime import datetime

class Paste errors(db.Model):
    __tablename__ = "Paste Errors"


    Field0 = db.Column(db.Text)


    def __repr__(self):
        return f"<Paste errors {{self.id}}>"
