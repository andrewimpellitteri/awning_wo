
from extensions import db
from datetime import datetime

class Tblcustomers(db.Model):
    __tablename__ = "tblCustomers"


    CustID = db.Column(db.Text)

    Name = db.Column(db.Text)

    Contact = db.Column(db.Text)

    Address = db.Column(db.Text)

    Address2 = db.Column(db.Text)

    City = db.Column(db.Text)

    State = db.Column(db.Text)

    ZipCode = db.Column(db.Text)

    HomePhone = db.Column(db.Text)

    WorkPhone = db.Column(db.Text)

    CellPhone = db.Column(db.Text)

    EmailAddress = db.Column(db.Text)

    MailAddress = db.Column(db.Text)

    MailCity = db.Column(db.Text)

    MailState = db.Column(db.Text)

    MailZip = db.Column(db.Text)

    SourceOld = db.Column(db.Text)

    Source = db.Column(db.Text)

    SourceAddress = db.Column(db.Text)

    SourceState = db.Column(db.Text)

    SourceCity = db.Column(db.Text)

    SourceZip = db.Column(db.Text)


    def __repr__(self):
        return f"<Tblcustomers {{self.id}}>"
