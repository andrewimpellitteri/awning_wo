from extensions import db


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

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "Description": self.Description,
            "Material": self.Material,
            "Condition": self.Condition,
            "Color": self.Color,
            "SizeWgt": self.SizeWgt,
            "Price": self.Price,
            "CustID": self.CustID,
            "Qty": self.Qty,
            "InventoryKey": self.InventoryKey,
        }

    def __repr__(self):
        return f"<CustAwning {self.Description} (CustID={self.CustID})>"
