
from extensions import db
from datetime import datetime

class Tblcondition(db.Model):
    __tablename__ = "tblCondition"


    Condition = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblcondition {{self.id}}>"
