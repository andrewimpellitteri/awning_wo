from extensions import db
from sqlalchemy.sql import func


class CheckIn(db.Model):
    __tablename__ = "tblcheckins"

    # Primary key
    CheckInID = db.Column("checkinid", db.Integer, primary_key=True, autoincrement=True)

    # Foreign key to customer
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    # Date when items checked in
    DateIn = db.Column("datein", db.Date, nullable=False)

    # Status: 'pending' or 'processed'
    Status = db.Column("status", db.String, nullable=False, default="pending")

    # Reference to created work order (nullable until conversion)
    WorkOrderNo = db.Column(
        "workorderno",
        db.String,
        db.ForeignKey("tblcustworkorderdetail.workorderno"),
        nullable=True
    )

    # Additional fields to match work order
    SpecialInstructions = db.Column("specialinstructions", db.Text, nullable=True)
    StorageTime = db.Column("storagetime", db.String, nullable=True)
    RackNo = db.Column("rack_number", db.String, nullable=True)
    ReturnTo = db.Column("returnto", db.String, nullable=True)
    DateRequired = db.Column("daterequired", db.Date, nullable=True)
    RepairsNeeded = db.Column("repairsneeded", db.Boolean, default=False)
    RushOrder = db.Column("rushorder", db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    customer = db.relationship("Customer", backref="checkins")
    items = db.relationship(
        "CheckInItem", back_populates="checkin", cascade="all, delete-orphan"
    )
    files = db.relationship(
        "CheckInFile", back_populates="checkin", cascade="all, delete-orphan", lazy="joined"
    )
    work_order = db.relationship("WorkOrder", foreign_keys=[WorkOrderNo])

    def to_dict(self, include_items=True):
        """Convert model instance to dictionary"""
        data = {
            "CheckInID": self.CheckInID,
            "CustID": self.CustID,
            "DateIn": self.DateIn.strftime("%m/%d/%Y") if self.DateIn else None,
            "Status": self.Status,
            "WorkOrderNo": self.WorkOrderNo,
            "created_at": self.created_at.strftime("%m/%d/%Y %H:%M:%S")
            if self.created_at
            else None,
            "updated_at": self.updated_at.strftime("%m/%d/%Y %H:%M:%S")
            if self.updated_at
            else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self):
        return f"<CheckIn {self.CheckInID}: Customer {self.CustID}>"

    def __str__(self):
        return f"Check-in {self.CheckInID} - {self.customer.Name if self.customer else 'Unknown'}"


class CheckInItem(db.Model):
    __tablename__ = "tblcheckinitems"

    # Auto-increment primary key
    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)

    # Foreign key to check-in
    CheckInID = db.Column(
        "checkinid",
        db.Integer,
        db.ForeignKey("tblcheckins.checkinid"),
        nullable=False,
        index=True,
    )

    # Item details (same fields as WorkOrderItem for consistency)
    Description = db.Column("description", db.String, nullable=False)
    Material = db.Column("material", db.String, nullable=True, default="Unknown")
    Color = db.Column("color", db.String)
    Qty = db.Column("qty", db.Integer, nullable=True)

    # Size/measurements (Width x Drop)
    SizeWgt = db.Column("sizewgt", db.String)

    # Price quote for repairs/cleaning
    Price = db.Column("price", db.Numeric(10, 2), nullable=True)

    # Condition notes
    Condition = db.Column("condition", db.String)

    # InventoryKey to track if item came from customer's existing inventory
    # NULL = manually added (NEW item), has value = selected from customer history
    InventoryKey = db.Column("inventorykey", db.Integer, nullable=True)

    # Relationships
    checkin = db.relationship("CheckIn", back_populates="items")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "id": self.id,
            "CheckInID": self.CheckInID,
            "Description": self.Description,
            "Material": self.Material,
            "Color": self.Color,
            "Qty": self.Qty,
            "SizeWgt": self.SizeWgt,
            "Price": float(self.Price) if self.Price else None,
            "Condition": self.Condition,
            "InventoryKey": self.InventoryKey,
            "is_new": self.InventoryKey is None,  # Helper flag for templates
        }

    def __repr__(self):
        return f"<CheckInItem {self.id}: {self.Description}>"

    def __str__(self):
        return f"{self.Description} ({self.Material}) - Qty: {self.Qty}"
