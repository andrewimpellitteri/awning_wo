
from extensions import db
from datetime import datetime

class Name autocorrect log(db.Model):
    __tablename__ = "Name AutoCorrect Log"


    Object Type = db.Column(db.Text)

    Object Name = db.Column(db.Text)

    Control Name = db.Column(db.Text)

    Property Name = db.Column(db.Text)

    Old Value = db.Column(db.Text)

    New Value = db.Column(db.Text)

    Time = db.Column(db.Text)


    def __repr__(self):
        return f"<Name autocorrect log {{self.id}}>"
