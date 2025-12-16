from extensions import db
from sqlalchemy.sql import func
from flask import current_app  # Import current_app to access Flask config


class WorkOrder(db.Model):
    __tablename__ = "tblcustworkorderdetail"

    # Map Python attributes to actual lowercase database columns
    WorkOrderNo = db.Column("workorderno", db.String, primary_key=True, nullable=False)
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    WOName = db.Column("woname", db.String)

    # === STORAGE/LOCATION FIELDS (See issue #82) ===
    # DEPRECATED: Do not use - column exists but is empty/unused
    Storage = db.Column("storage", db.String)

    # Storage TIME type: "Seasonal" or "Temporary" (how long stored)
    StorageTime = db.Column("storagetime", db.String)

    # Physical LOCATION where item is stored (e.g., "5 B", "bin 4 top", "cleaning room")
    # This is the PRIMARY location field - use this, not Storage!
    RackNo = db.Column("rack_number", db.String)
    # === END STORAGE/LOCATION FIELDS ===

    SpecialInstructions = db.Column("specialinstructions", db.Text)
    RepairsNeeded = db.Column("repairsneeded", db.Boolean)  # should be bool
    ReturnStatus = db.Column("returnstatus", db.String)
    ReturnTo = db.Column("returnto", db.String, nullable=True)
    # Date/DateTime fields with proper types
    DateCompleted = db.Column("datecompleted", db.DateTime, nullable=True)
    DateRequired = db.Column("daterequired", db.Date, nullable=True)
    DateIn = db.Column("datein", db.Date, nullable=True)
    Clean = db.Column("clean", db.Date, nullable=True)  # Date when cleaning completed
    Treat = db.Column("treat", db.Date, nullable=True)  # Date when treatment completed
    # Boolean fields with proper types
    Quote = db.Column("quote", db.String)  # needs to be sting
    RushOrder = db.Column("rushorder", db.Boolean, default=False)
    FirmRush = db.Column("firmrush", db.Boolean, default=False)
    isCushion = db.Column("iscushion", db.Boolean, default=False)
    SeeRepair = db.Column("seerepair", db.String)  # needs to be string
    # String fields (keep as string)
    ShipTo = db.Column("shipto", db.String, db.ForeignKey("tblsource.ssource"))
    CleanFirstWO = db.Column(
        "cleanfirstwo", db.String
    )  # deprecated only for historical
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    final_location = db.Column("finallocation", db.String, nullable=True)

    # Denormalized source name from customer (for performance)
    source_name = db.Column("source_name", db.Text, nullable=True)

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

    ProcessingStatus = db.Column("processingstatus", db.Boolean, default=False)

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

    def sync_source_name(self):
        """
        Update source_name from customer's source.
        Call this after creating or updating a work order's customer.

        The database trigger will handle this automatically, but this
        method provides explicit control when needed.
        """
        if self.customer and self.customer.source_info:
            self.source_name = self.customer.source_info.SSource
        else:
            self.source_name = None

    @property
    def customer_source_name(self):
        """
        Get customer's source name with fallback to relationship.
        Prefer using the denormalized source_name for performance.
        """
        # Use denormalized value if available
        if self.source_name:
            return self.source_name
        # Fallback to relationship (for backward compatibility)
        if self.customer and self.customer.source_info:
            return self.customer.source_info.SSource
        return None

    def to_dict(self, include_items=True):
        from datetime import date, datetime

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
            "ReturnTo": self.ReturnTo,
            # Serialize dates properly
            "DateCompleted": self.DateCompleted.strftime("%m/%d/%Y")
            if self.DateCompleted
            else None,
            "DateRequired": self.DateRequired.strftime("%m/%d/%Y")
            if self.DateRequired
            else None,
            "DateIn": self.DateIn.strftime("%m/%d/%Y") if self.DateIn else None,
            "Clean": self.Clean.strftime("%m/%d/%Y") if self.Clean else None,
            "Treat": self.Treat.strftime("%m/%d/%Y") if self.Treat else None,
            # Booleans serialize as is
            "Quote": self.Quote,
            "RushOrder": self.RushOrder,
            "FirmRush": self.FirmRush,
            "ShipTo": self.ShipTo,
            "CleanFirstWO": self.CleanFirstWO,
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
        return f"<WorkOrder {self.WorkOrderNo}: {self.WOName}>"

    def __str__(self):
        return f"Work Order {self.WorkOrderNo} - {self.WOName or 'Unnamed'}"


class WorkOrderItem(db.Model):
    __tablename__ = "tblorddetcustawngs"

    # Auto-increment primary key
    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)

    # Map to lowercase database column names
    WorkOrderNo = db.Column(
        "workorderno",
        db.String,
        db.ForeignKey("tblcustworkorderdetail.workorderno"),
        nullable=False,
        index=True,  # Add index for faster lookups
    )
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    # Fields that were previously part of composite primary key
    Description = db.Column("description", db.String, nullable=False)
    Material = db.Column("material", db.String, nullable=True, default="Unknown")

    # Rest of the columns
    Qty = db.Column("qty", db.Integer, nullable=True)
    Condition = db.Column("condition", db.String)
    Color = db.Column("color", db.String)
    SizeWgt = db.Column("sizewgt", db.String)
    Price = db.Column("price", db.Numeric(10, 2), nullable=True)
    InventoryKey = db.Column("inventory_key", db.String, nullable=True)

    # relationships
    work_order = db.relationship("WorkOrder", back_populates="items")
    customer = db.relationship("Customer")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "id": self.id,
            "WorkOrderNo": self.WorkOrderNo,
            "CustID": self.CustID,
            "Description": self.Description,
            "Material": self.Material,
            "Qty": self.Qty,
            "Condition": self.Condition,
            "Color": self.Color,
            "SizeWgt": self.SizeWgt,
            "Price": self.Price,
            "InventoryKey": self.InventoryKey,
        }

    def __repr__(self):
        return f"<WorkOrderItem {self.WorkOrderNo}: {self.Description}>"

    def __str__(self):
        return f"{self.Description} ({self.Material}) - Qty: {self.Qty}"
