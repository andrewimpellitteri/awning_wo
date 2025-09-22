from datetime import datetime
from extensions import db


class WorkOrderFile(db.Model):
    __tablename__ = "tblworkorderfiles"

    # Primary key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Foreign key to WorkOrder
    WorkOrderNo = db.Column(
        "workorderno",
        db.String,
        db.ForeignKey("tblcustworkorderdetail.workorderno"),
        nullable=False,
    )

    # File info
    filename = db.Column("filename", db.String, nullable=False)
    file_path = db.Column("file_path", db.String, nullable=False)  # optional full path
    uploaded_at = db.Column("uploaded_at", db.DateTime, default=datetime.utcnow)

    # Relationship back to WorkOrder
    work_order = db.relationship("WorkOrder", back_populates="files")

    def to_dict(self):
        return {
            "id": self.id,
            "WorkOrderNo": self.WorkOrderNo,
            "filename": self.filename,
            "file_path": self.file_path,
            "uploaded_at": self.uploaded_at.isoformat(),
        }
