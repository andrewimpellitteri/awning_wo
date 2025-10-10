from datetime import datetime
from extensions import db


class RepairOrderFile(db.Model):
    __tablename__ = "tblrepairorderfiles"

    # Primary key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Foreign key to RepairWorkOrder
    RepairOrderNo = db.Column(
        "repairorderno",
        db.String,
        db.ForeignKey("tblrepairworkorder.repairorderno"),
        nullable=False,
    )

    # File info
    filename = db.Column("filename", db.String, nullable=False)
    file_path = db.Column("file_path", db.String, nullable=False)
    uploaded_at = db.Column("uploaded_at", db.DateTime, default=datetime.utcnow)
    thumbnail_path = db.Column(db.String(500), nullable=True)

    # Relationship back to RepairWorkOrder
    repair_order = db.relationship("RepairWorkOrder", back_populates="files")

    def to_dict(self):
        return {
            "id": self.id,
            "RepairOrderNo": self.RepairOrderNo,
            "filename": self.filename,
            "file_path": self.file_path,
            "uploaded_at": self.uploaded_at.isoformat(),
        }