
from extensions import db
from datetime import datetime

class TblitemscompletebydatetoexcelExporterrors(db.Model):
    __tablename__ = "tblItemsCompleteByDatetoExcel_ExportErrors"


    Error = db.Column(db.Text)

    Field = db.Column(db.Text)

    Row = db.Column(db.Text)


    def __repr__(self):
        return f"<TblitemscompletebydatetoexcelExporterrors {{self.id}}>"
