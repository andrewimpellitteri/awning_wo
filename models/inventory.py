from extensions import db
from datetime import datetime


class Inventory(db.Model):
    __tablename__ = "tblcustawngs"

    # Map Python attributes to actual lowercase database columns
    Description = db.Column("description", db.Text)
    Material = db.Column("material", db.Text)
    Condition = db.Column("condition", db.Text)
    Color = db.Column("color", db.Text)
    SizeWgt = db.Column("sizewgt", db.Text)
    Price = db.Column("price", db.Numeric(10, 2), nullable=True)
    CustID = db.Column("custid", db.Text)
    Qty = db.Column("qty", db.Integer, nullable=True)
    InventoryKey = db.Column("inventorykey", db.Text, primary_key=True)
    created_at = db.Column("created_at", db.DateTime, default=datetime.utcnow, nullable=True)

    def to_dict(self):
        """Convert model instance to dictionary, replacing None with empty strings for text fields"""
        return {
            "InventoryKey": self.InventoryKey,
            "Description": self.Description or "",
            "Material": self.Material or "",
            "Condition": self.Condition or "",
            "Color": self.Color or "",
            "SizeWgt": self.SizeWgt or "",
            "Price": float(self.Price) if self.Price is not None else None,
            "CustID": self.CustID or "",
            "Qty": self.Qty or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<CustAwning {self.Description} (CustID={self.CustID})>"
