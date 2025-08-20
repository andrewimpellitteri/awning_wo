
from extensions import db
from datetime import datetime

class Tblsource(db.Model):
    __tablename__ = "tblSource"


    SSource = db.Column(db.Text)

    SourceAddress = db.Column(db.Text)

    SourceState = db.Column(db.Text)

    SourceCity = db.Column(db.Text)

    SourceZip = db.Column(db.Text)

    SourcePhone = db.Column(db.Text)

    SourceFax = db.Column(db.Text)

    SourceEmail = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblsource {{self.id}}>"
