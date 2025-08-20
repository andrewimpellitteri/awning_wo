
from extensions import db
from datetime import datetime

class Switchboard items(db.Model):
    __tablename__ = "Switchboard Items"


    SwitchboardID = db.Column(db.Text)

    ItemNumber = db.Column(db.Text)

    ItemText = db.Column(db.Text)

    Command = db.Column(db.Text)

    Argument = db.Column(db.Text)


    def __repr__(self):
        return f"<Switchboard items {{self.id}}>"
