from extensions import db
from sqlalchemy.sql import func


class CheckInFile(db.Model):
    __tablename__ = "tblcheckinfiles"

    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    CheckInID = db.Column(
        "checkinid",
        db.Integer,
        db.ForeignKey("tblcheckins.checkinid"),
        nullable=False,
    )
    file_name = db.Column("file_name", db.String(255), nullable=False)
    file_path = db.Column("file_path", db.String(500), nullable=False)
    file_size = db.Column("file_size", db.Integer, nullable=True)
    file_type = db.Column("file_type", db.String(100), nullable=True)
    uploaded_at = db.Column("uploaded_at", db.DateTime, server_default=func.now())

    # Relationship to CheckIn
    checkin = db.relationship("CheckIn", back_populates="files")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "id": self.id,
            "CheckInID": self.CheckInID,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "uploaded_at": self.uploaded_at.strftime("%m/%d/%Y %H:%M:%S")
            if self.uploaded_at
            else None,
        }

    def __repr__(self):
        return f"<CheckInFile {self.id}: {self.file_name}>"

    def __str__(self):
        return f"{self.file_name} (Check-in #{self.CheckInID})"
