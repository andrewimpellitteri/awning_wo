from datetime import datetime
from extensions import db
from sqlalchemy.ext.hybrid import hybrid_property
from flask import current_app  # Import current_app to access Flask config


class WorkOrder(db.Model):
    __tablename__ = "tblcustworkorderdetail"

    # Map Python attributes to actual lowercase database columns
    WorkOrderNo = db.Column("workorderno", db.String, primary_key=True, nullable=False)
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    WOName = db.Column("woname", db.String)
    Storage = db.Column("storage", db.String)
    StorageTime = db.Column("storagetime", db.String)
    # FIXED: Quote the column name to match the actual database column
    RackNo = db.Column("rack_number", db.String)
    SpecialInstructions = db.Column("specialinstructions", db.Text)
    RepairsNeeded = db.Column("repairsneeded", db.Text)
    SeeRepair = db.Column("seerepair", db.String)
    ReturnStatus = db.Column("returnstatus", db.String)
    DateCompleted = db.Column("datecompleted", db.String)
    Quote = db.Column("quote", db.String)
    Clean = db.Column("clean", db.String)
    Treat = db.Column("treat", db.String)
    RushOrder = db.Column("rushorder", db.String)
    DateRequired = db.Column("daterequired", db.String)
    DateIn = db.Column("datein", db.String)
    ShipTo = db.Column("shipto", db.String, db.ForeignKey("tblsource.ssource"))
    FirmRush = db.Column("firmrush", db.String)
    CleanFirstWO = db.Column("cleanfirstwo", db.String)
    created_at = db.Column(
        "created_at", db.String, default=lambda: datetime.utcnow().isoformat()
    )
    updated_at = db.Column(
        "updated_at",
        db.String,
        default=lambda: datetime.utcnow().isoformat(),
        onupdate=lambda: datetime.utcnow().isoformat(),
    )

    # relationships
    customer = db.relationship("Customer", back_populates="work_orders")
    items = db.relationship(
        "WorkOrderItem", back_populates="work_order", cascade="all, delete-orphan"
    )

    files = db.relationship(
        "WorkOrderFile",
        back_populates="work_order",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    QueuePosition = db.Column("queueposition", db.Integer, nullable=True)

    ship_to_source = db.relationship(
        "Source",
        primaryjoin="WorkOrder.ShipTo==Source.SSource",
        lazy="joined",
        uselist=False,
    )

    @property
    def is_sail_order(self):
        """Return True if ShipTo is in the sail order sources list.

        Note: This is a Python property, not a hybrid property,
        so it only works when the object is loaded in Python,
        not in database queries.
        """
        try:
            sail_sources = current_app.config.get("SAIL_ORDER_SOURCES", [])
            return self.ShipTo is not None and self.ShipTo in sail_sources
        except RuntimeError:
            # Handle case where we're outside application context
            return False

    @classmethod
    def get_sail_order_sources(cls):
        """Helper method to get sail order sources safely"""
        try:
            return current_app.config.get("SAIL_ORDER_SOURCES", [])
        except RuntimeError:
            return []

    def to_dict(self, include_items=True):
        data = {
            "WorkOrderNo": self.WorkOrderNo,
            "CustID": self.CustID,
            "WOName": self.WOName,
            "Storage": self.Storage,
            "StorageTime": self.StorageTime,
            "RackNo": self.RackNo,
            "SpecialInstructions": self.SpecialInstructions,
            "RepairsNeeded": self.RepairsNeeded,
            "SeeRepair": self.SeeRepair,
            "ReturnStatus": self.ReturnStatus,
            "DateCompleted": self.DateCompleted,
            "Quote": self.Quote,
            "Clean": self.Clean,
            "Treat": self.Treat,
            "RushOrder": self.RushOrder,
            "DateRequired": self.DateRequired,
            "DateIn": self.DateIn,
            "ShipTo": self.ShipTo,
            "FirmRush": self.FirmRush,
            "CleanFirstWO": self.CleanFirstWO,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self):
        return f"<WorkOrder {self.WorkOrderNo}: {self.WOName}>"

    def __str__(self):
        return f"Work Order {self.WorkOrderNo} - {self.WOName or 'Unnamed'}"


class WorkOrderItem(db.Model):
    __tablename__ = "tblorddetcustawngs"

    # Map to lowercase database column names
    WorkOrderNo = db.Column(
        "workorderno",
        db.String,
        db.ForeignKey("tblcustworkorderdetail.workorderno"),
        nullable=False,
        primary_key=True,
    )
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    # Add Description and Material to primary key
    Description = db.Column("description", db.String, primary_key=True)
    Material = db.Column("material", db.String, primary_key=True)

    # Rest of the columns
    Qty = db.Column("qty", db.String)
    Condition = db.Column("condition", db.String)
    Color = db.Column("color", db.String)
    SizeWgt = db.Column("sizewgt", db.String)
    Price = db.Column("price", db.String)

    # relationships
    work_order = db.relationship("WorkOrder", back_populates="items")
    customer = db.relationship("Customer")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "WorkOrderNo": self.WorkOrderNo,
            "CustID": self.CustID,
            "Description": self.Description,
            "Material": self.Material,
            "Qty": self.Qty,
            "Condition": self.Condition,
            "Color": self.Color,
            "SizeWgt": self.SizeWgt,
            "Price": self.Price,
        }

    def __repr__(self):
        return f"<WorkOrderItem {self.WorkOrderNo}: {self.Description}>"

    def __str__(self):
        return f"{self.Description} ({self.Material}) - Qty: {self.Qty}"
