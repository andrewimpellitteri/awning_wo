
from extensions import db
from datetime import datetime

class Tblcustawngs(db.Model):
    __tablename__ = "tblCustAwngs"


    Description = db.Column(db.Text)

    Material = db.Column(db.Text)

    Condition = db.Column(db.Text)

    Color = db.Column(db.Text)

    SizeWgt = db.Column(db.Text)

    Price = db.Column(db.Text)

    CustID = db.Column(db.Text)

    Qty = db.Column(db.Text)

    InventoryKey = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblcustawngs {{self.id}}>"
