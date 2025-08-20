
from extensions import db
from datetime import datetime

class Tblitemscompletebydatetoexcel(db.Model):
    __tablename__ = "tblItemsCompleteByDatetoExcel"


    Clean = db.Column(db.Text)

    DateIn = db.Column(db.Text)

    WorkOrderNo = db.Column(db.Text)

    Name = db.Column(db.Text)

    Source = db.Column(db.Text)

    Qty = db.Column(db.Text)

    Description = db.Column(db.Text)

    Material = db.Column(db.Text)

    Condition = db.Column(db.Text)

    Color = db.Column(db.Text)

    SizeWgt = db.Column(db.Text)

    Price = db.Column(db.Text)

    DateCompleted = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblitemscompletebydatetoexcel {{self.id}}>"
