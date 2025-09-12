from extensions import db


class Source(db.Model):
    __tablename__ = "tblsource"

    # Fixed: Use lowercase column names to match PostgreSQL
    # But keep the Python attribute names in mixed case for consistency
    SSource = db.Column("ssource", db.Text, primary_key=True, nullable=False)
    SourceAddress = db.Column("sourceaddress", db.Text)
    SourceState = db.Column("sourcestate", db.Text)
    SourceCity = db.Column("sourcecity", db.Text)
    SourceZip = db.Column("sourcezip", db.Text)
    SourcePhone = db.Column("sourcephone", db.Text)
    SourceFax = db.Column("sourcefax", db.Text)
    SourceEmail = db.Column("sourceemail", db.Text)

    customers = db.relationship("Customer", back_populates="source_info")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "Name": self.SSource,
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

    def get_full_address(self):
        """Get formatted full address"""
        parts = []
        if self.SourceAddress:
            parts.append(self.SourceAddress)

        city_state_zip = []
        if self.SourceCity:
            city_state_zip.append(self.SourceCity)
        if self.SourceState:
            city_state_zip.append(self.SourceState)
        if self.SourceZip:
            city_state_zip.append(self.SourceZip)

        if city_state_zip:
            if len(city_state_zip) == 3:
                parts.append(
                    f"{city_state_zip[0]}, {city_state_zip[1]} {city_state_zip[2]}"
                )
            else:
                parts.append(" ".join(city_state_zip))

        return "\n".join(parts) if parts else None

    def __repr__(self):
        return f"<Source {self.SSource}>"
