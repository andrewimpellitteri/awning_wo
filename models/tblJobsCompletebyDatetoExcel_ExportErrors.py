
from extensions import db
from datetime import datetime

class TbljobscompletebydatetoexcelExporterrors(db.Model):
    __tablename__ = "tblJobsCompletebyDatetoExcel_ExportErrors"


    Error = db.Column(db.Text)

    Field = db.Column(db.Text)

    Row = db.Column(db.Text)


    def __repr__(self):
        return f"<TbljobscompletebydatetoexcelExporterrors {{self.id}}>"
