
from extensions import db
from datetime import datetime

class Tbldescriptions(db.Model):
    __tablename__ = "tblDescriptions"


    Description = db.Column(db.Text)


    def __repr__(self):
        return f"<Tbldescriptions {{self.id}}>"
