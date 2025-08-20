
from extensions import db
from datetime import datetime

class Tblwosummary(db.Model):
    __tablename__ = "tblWOSummary"


    OrderDetailID = db.Column(db.Text)

    CustID = db.Column(db.Text)

    WorkOrderNo = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblwosummary {{self.id}}>"
