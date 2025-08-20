
from extensions import db
from datetime import datetime

class Tblcustworkorderdetail(db.Model):
    __tablename__ = "tblCustWorkOrderDetail"


    WorkOrderNo = db.Column(db.Text)

    CustID = db.Column(db.Text)

    WOName = db.Column(db.Text)

    Storage = db.Column(db.Text)

    StorageTime = db.Column(db.Text)

    Rack# = db.Column(db.Text)

    SpecialInstructions = db.Column(db.Text)

    RepairsNeeded = db.Column(db.Text)

    SeeRepair = db.Column(db.Text)

    ReturnStatus = db.Column(db.Text)

    DateCompleted = db.Column(db.Text)

    Quote = db.Column(db.Text)

    Clean = db.Column(db.Text)

    Treat = db.Column(db.Text)

    RushOrder = db.Column(db.Text)

    DateRequired = db.Column(db.Text)

    DateIn = db.Column(db.Text)

    ShipTo = db.Column(db.Text)

    FirmRush = db.Column(db.Text)

    CleanFirstWO = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblcustworkorderdetail {{self.id}}>"
