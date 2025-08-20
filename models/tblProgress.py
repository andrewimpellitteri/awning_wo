
from extensions import db
from datetime import datetime

class Tblprogress(db.Model):
    __tablename__ = "tblProgress"


    CustID = db.Column(db.Text)

    PgrsWorkOrderNo = db.Column(db.Text)

    PgrsName = db.Column(db.Text)

    PgrsDateIn = db.Column(db.Text)

    PgrsDateUptd = db.Column(db.Text)

    PgrsSource = db.Column(db.Text)

    WO_Quote = db.Column(db.Text)

    OnDeckClean = db.Column(db.Text)

    Tub = db.Column(db.Text)

    Clean = db.Column(db.Text)

    Treat = db.Column(db.Text)

    WrapClean = db.Column(db.Text)

    NotesClean = db.Column(db.Text)

    PgrsRepairOrderNo = db.Column(db.Text)

    Repair_Quote = db.Column(db.Text)

    OnDeckRepair = db.Column(db.Text)

    InProcess = db.Column(db.Text)

    WrapRepair = db.Column(db.Text)

    Repair_Notes = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblprogress {{self.id}}>"
