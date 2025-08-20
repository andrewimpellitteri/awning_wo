
from extensions import db
from datetime import datetime

class Tblincompletetoexcel(db.Model):
    __tablename__ = "tblIncompletetoExcel"


    Clean = db.Column(db.Text)

    DateIn = db.Column(db.Text)

    Name = db.Column(db.Text)

    WorkOrderNo = db.Column(db.Text)

    Source = db.Column(db.Text)

    SourceOld = db.Column(db.Text)

    Storage = db.Column(db.Text)

    StorageTime = db.Column(db.Text)

    Rack# = db.Column(db.Text)

    SpecialInstructions = db.Column(db.Text)

    RepairsNeeded = db.Column(db.Text)

    SeeRepair = db.Column(db.Text)

    ReturnStatus = db.Column(db.Text)

    Treat = db.Column(db.Text)

    RushOrder = db.Column(db.Text)

    DateRequired = db.Column(db.Text)

    ShipTo = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblincompletetoexcel {{self.id}}>"
