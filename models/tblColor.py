
from extensions import db
from datetime import datetime

class Tblcolor(db.Model):
    __tablename__ = "tblColor"


    Color = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblcolor {{self.id}}>"
