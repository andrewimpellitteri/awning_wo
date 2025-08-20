
from extensions import db
from datetime import datetime

class Tblrepairworkorderdetail(db.Model):
    __tablename__ = "tblRepairWorkOrderDetail"


    RepairOrderNo = db.Column(db.Text)

    CustID = db.Column(db.Text)

    ROName = db.Column(db.Text)

    SOURCE = db.Column(db.Text)

    WO DATE = db.Column(db.Text)

    DATE TO SUB = db.Column(db.Text)

    DateRequired = db.Column(db.Text)

    RushOrder = db.Column(db.Text)

    FirmRush = db.Column(db.Text)

    QUOTE = db.Column(db.Text)

    QUOTE  BY = db.Column(db.Text)

    APPROVED = db.Column(db.Text)

    RACK# = db.Column(db.Text)

    STORAGE = db.Column(db.Text)

    ITEM TYPE = db.Column(db.Text)

    TYPE OF REPAIR = db.Column(db.Text)

    SPECIALINSTRUCTIONS = db.Column(db.Text)

    CLEAN = db.Column(db.Text)

    SEECLEAN = db.Column(db.Text)

    CLEANFIRST = db.Column(db.Text)

    REPAIRSDONEBY = db.Column(db.Text)

    DateCompleted = db.Column(db.Text)

    MaterialList = db.Column(db.Text)

    CUSTOMERPRICE = db.Column(db.Text)

    RETURNSTATUS = db.Column(db.Text)

    RETURNDATE = db.Column(db.Text)

    LOCATION = db.Column(db.Text)

    DATEOUT = db.Column(db.Text)

    DateIn = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblrepairworkorderdetail {{self.id}}>"
