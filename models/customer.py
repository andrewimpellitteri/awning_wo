from extensions import db


class Customer(db.Model):
    __tablename__ = "tblcustomers"

    # Update to use lowercase column names to match PostgreSQL
    CustID = db.Column("custid", db.Text, primary_key=True, nullable=False)
    Name = db.Column("name", db.Text)
    Contact = db.Column("contact", db.Text)
    Address = db.Column("address", db.Text)
    Address2 = db.Column("address2", db.Text)
    City = db.Column("city", db.Text)
    State = db.Column("state", db.Text)
    ZipCode = db.Column("zipcode", db.Text)
    HomePhone = db.Column("homephone", db.Text)
    WorkPhone = db.Column("workphone", db.Text)
    CellPhone = db.Column("cellphone", db.Text)
    EmailAddress = db.Column("emailaddress", db.Text)
    MailAddress = db.Column("mailaddress", db.Text)
    MailCity = db.Column("mailcity", db.Text)
    MailState = db.Column("mailstate", db.Text)
    MailZip = db.Column("mailzip", db.Text)
    SourceOld = db.Column("sourceold", db.Text)
    # FIXED: Updated foreign key reference to use lowercase column name
    Source = db.Column(
        "source", db.Text, db.ForeignKey("tblsource.ssource"), nullable=True
    )
    SourceAddress = db.Column("sourceaddress", db.Text)
    SourceState = db.Column("sourcestate", db.Text)
    SourceCity = db.Column("sourcecity", db.Text)
    SourceZip = db.Column("sourcezip", db.Text)

    # Relationship to Source
    source_info = db.relationship("Source", back_populates="customers")

    # Relationship to WorkOrders
    work_orders = db.relationship(
        "WorkOrder", back_populates="customer", lazy="dynamic"
    )

    # Relationship to RepairWorkOrders
    repair_work_orders = db.relationship("RepairWorkOrder", back_populates="customer")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "CustID": self.CustID,
            "Name": self.Name,
            "Contact": self.Contact,
            "Address": self.Address,
            "Address2": self.Address2,
            "City": self.City,
            "State": self.State,
            "ZipCode": self.ZipCode,
            "HomePhone": self.HomePhone,
            "WorkPhone": self.WorkPhone,
            "CellPhone": self.CellPhone,
            "EmailAddress": self.EmailAddress,
            "MailAddress": self.MailAddress,
            "MailCity": self.MailCity,
            "MailState": self.MailState,
            "MailZip": self.MailZip,
            "SourceOld": self.SourceOld,
            "Source": self.Source,
            "SourceAddress": self.SourceAddress,
            "SourceState": self.SourceState,
            "SourceCity": self.SourceCity,
            "SourceZip": self.SourceZip,
        }

    def clean_email(self):
        """Clean email by removing #mailto: suffix"""
        if self.EmailAddress and "#mailto:" in self.EmailAddress:
            return self.EmailAddress.split("#mailto:")[0]
        return self.EmailAddress

    def clean_phone(self, phone_field):
        """Format phone number for display"""
        phone = getattr(self, phone_field, None)
        if phone and len(phone) == 10:
            return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
        elif phone and len(phone) == 14 and phone.startswith("("):
            return phone  # Already formatted
        return phone

    def get_full_address(self):
        """Get formatted full address"""
        parts = []
        if self.Address:
            parts.append(self.Address)
        if self.Address2:
            parts.append(self.Address2)

        city_state_zip = []
        if self.City:
            city_state_zip.append(self.City)
        if self.State:
            city_state_zip.append(self.State)
        if self.ZipCode:
            city_state_zip.append(self.ZipCode)

        if city_state_zip:
            if len(city_state_zip) == 3:
                parts.append(
                    f"{city_state_zip[0]}, {city_state_zip[1]} {city_state_zip[2]}"
                )
            else:
                parts.append(" ".join(city_state_zip))

        return "\n".join(parts) if parts else None

    def get_mailing_address(self):
        """Get formatted mailing address if different from physical"""
        if not any([self.MailAddress, self.MailCity, self.MailState, self.MailZip]):
            return None

        parts = []
        if self.MailAddress:
            parts.append(self.MailAddress)

        city_state_zip = []
        if self.MailCity:
            city_state_zip.append(self.MailCity)
        if self.MailState:
            city_state_zip.append(self.MailState)
        if self.MailZip:
            city_state_zip.append(self.MailZip)

        if city_state_zip:
            if len(city_state_zip) == 3:
                parts.append(
                    f"{city_state_zip[0]}, {city_state_zip[1]} {city_state_zip[2]}"
                )
            else:
                parts.append(" ".join(city_state_zip))

        return "\n".join(parts) if parts else None

    def get_primary_phone(self):
        """Get the first available phone number"""
        for phone_field in ["CellPhone", "HomePhone", "WorkPhone"]:
            phone = getattr(self, phone_field)
            if phone:
                return self.clean_phone(phone_field)
        return None

    def __repr__(self):
        return f"<Customer {self.CustID}: {self.Name}>"
