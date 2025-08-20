
from extensions import db
from datetime import datetime

class Tblmaterial(db.Model):
    __tablename__ = "tblMaterial"


    Material = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblmaterial {{self.id}}>"
