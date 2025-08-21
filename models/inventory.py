from extensions import db


class Inventory(db.Model):
    __tablename__ = "tblCustAwngs"

    Description = db.Column(db.Text)
    Material = db.Column(db.Text)
    Condition = db.Column(db.Text)
    Color = db.Column(db.Text)
    SizeWgt = db.Column(db.Text)
    Price = db.Column(db.Text)
    CustID = db.Column(db.Text)
    Qty = db.Column(db.Text)
    InventoryKey = db.Column(db.Text, primary_key=True)

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
