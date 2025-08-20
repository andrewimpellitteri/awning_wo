
from extensions import db
from datetime import datetime

class Tblreporddetcustawngs(db.Model):
    __tablename__ = "tblRepOrdDetCustAwngs"


    RepairOrderNo = db.Column(db.Text)

    CustID = db.Column(db.Text)

    Qty = db.Column(db.Text)

    Description = db.Column(db.Text)

    Material = db.Column(db.Text)

    Condition = db.Column(db.Text)

    Color = db.Column(db.Text)

    SizeWgt = db.Column(db.Text)

    Price = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblreporddetcustawngs {{self.id}}>"
