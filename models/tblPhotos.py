
from extensions import db
from datetime import datetime

class Tblphotos(db.Model):
    __tablename__ = "tblPhotos"


    CustID = db.Column(db.Text)

    PhotoDate = db.Column(db.Text)

    Link = db.Column(db.Text)

    Notes = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblphotos {{self.id}}>"
