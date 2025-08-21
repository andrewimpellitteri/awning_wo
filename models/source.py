from extensions import db


class Source(db.Model):
    __tablename__ = "tblSource"

    # Using SSource as primary key since it appears to be the identifier
    SSource = db.Column(db.Text, primary_key=True, nullable=False)
    SourceAddress = db.Column(db.Text)
    SourceState = db.Column(db.Text)
    SourceCity = db.Column(db.Text)
    SourceZip = db.Column(db.Text)
    SourcePhone = db.Column(db.Text)
    SourceFax = db.Column(db.Text)
    SourceEmail = db.Column(db.Text)

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "SSource": self.SSource,
            "SourceAddress": self.SourceAddress,
            "SourceState": self.SourceState,
            "SourceCity": self.SourceCity,
            "SourceZip": self.SourceZip,
            "SourcePhone": self.SourcePhone,
            "SourceFax": self.SourceFax,
            "SourceEmail": self.SourceEmail,
        }

    def clean_email(self):
        """Clean email by removing #mailto: suffix"""
        if self.SourceEmail and "#mailto:" in self.SourceEmail:
            return self.SourceEmail.split("#mailto:")[0]
        return self.SourceEmail

    def clean_phone(self):
        """Format phone number for display"""
        if self.SourcePhone and len(self.SourcePhone) == 10:
            return f"({self.SourcePhone[:3]}) {self.SourcePhone[3:6]}-{self.SourcePhone[6:]}"
        return self.SourcePhone

    def __repr__(self):
        return f"<Source {self.SSource}>"
