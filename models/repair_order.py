from datetime import datetime, date
from extensions import db
from sqlalchemy.sql import func


class RepairWorkOrder(db.Model):
    __tablename__ = "tblrepairworkorderdetail"

    # Map Python attributes to actual lowercase database columns
    RepairOrderNo = db.Column(
        "repairorderno", db.String, primary_key=True, nullable=False
    )
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    ROName = db.Column("roname", db.String)
    SOURCE = db.Column("source", db.String)

    # Date fields with proper types
    WO_DATE = db.Column("WO DATE", db.Date, nullable=True)  # Uppercase with space
    DATE_TO_SUB = db.Column(
        "DATE TO SUB", db.Date, nullable=True
    )  # Uppercase with spaces
    DateRequired = db.Column("daterequired", db.Date, nullable=True)
    DateCompleted = db.Column("datecompleted", db.DateTime, nullable=True)
    RETURNDATE = db.Column("returndate", db.Date, nullable=True)
    DATEOUT = db.Column("dateout", db.Date, nullable=True)
    DateIn = db.Column("datein", db.Date, nullable=True)

    # Boolean fields with proper types
    RushOrder = db.Column("rushorder", db.Boolean, default=False)
    FirmRush = db.Column("firmrush", db.Boolean, default=False)
    QUOTE = db.Column(
        "quote", db.Boolean, default=False
    )  # need to change to str?? might be same a wo dropdown or could be a bool?
    APPROVED = db.Column("approved", db.Boolean, default=False)
    CLEAN = db.Column("clean", db.Boolean, default=False)  # Uses "YES"/"NO" values
    CLEANFIRST = db.Column(
        "cleanfirst", db.Boolean, default=False
    )  # deprecated only for historical

    # String fields (keep as string)
    QUOTE_BY = db.Column(
        "QUOTE  BY", db.String
    )  # Note: TWO spaces between QUOTE and BY
    RackNo = db.Column("RACK#", db.String)  # Uppercase
    STORAGE = db.Column("storage", db.String)
    ITEM_TYPE = db.Column("ITEM TYPE", db.String)  # Uppercase with space
    TYPE_OF_REPAIR = db.Column("TYPE OF REPAIR", db.String)  # Uppercase with spaces
    SPECIALINSTRUCTIONS = db.Column("specialinstructions", db.Text)
    SEECLEAN = db.Column("seeclean", db.String)  # Work order reference
    REPAIRSDONEBY = db.Column("repairsdoneby", db.String)
    MaterialList = db.Column("materiallist", db.Text)
    CUSTOMERPRICE = db.Column("customerprice", db.String)
    RETURNSTATUS = db.Column("returnstatus", db.String)
    LOCATION = db.Column("location", db.String)
    final_location = db.Column("finallocation", db.String, nullable=True)

    # Denormalized source name from customer (for performance)
    source_name = db.Column("source_name", db.Text, nullable=True)

    # Timestamp fields with proper types
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    customer = db.relationship("Customer", back_populates="repair_work_orders")
    items = db.relationship(
        "RepairWorkOrderItem",
        back_populates="repair_work_order",
        cascade="all, delete-orphan",
    )
    files = db.relationship(
        "RepairOrderFile",
        back_populates="repair_order",
        cascade="all, delete-orphan",
    )

    def sync_source_name(self):
        """
        Update source_name from customer's source.
        Call this after creating or updating a repair order's customer.

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

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "RepairOrderNo": self.RepairOrderNo,
            "CustID": self.CustID,
            "ROName": self.ROName,
            "SOURCE": self.SOURCE,
            # Serialize dates properly
            "WO_DATE": self.WO_DATE.strftime("%m/%d/%Y") if self.WO_DATE else None,
            "DATE_TO_SUB": self.DATE_TO_SUB.strftime("%m/%d/%Y")
            if self.DATE_TO_SUB
            else None,
            "DateRequired": self.DateRequired.strftime("%m/%d/%Y")
            if self.DateRequired
            else None,
            "DateCompleted": self.DateCompleted.strftime("%m/%d/%Y %H:%M:%S")
            if self.DateCompleted
            else None,
            "RETURNDATE": self.RETURNDATE.strftime("%m/%d/%Y")
            if self.RETURNDATE
            else None,
            "DATEOUT": self.DATEOUT.strftime("%m/%d/%Y") if self.DATEOUT else None,
            "DateIn": self.DateIn.strftime("%m/%d/%Y") if self.DateIn else None,
            # Booleans serialize as is
            "RushOrder": self.RushOrder,
            "FirmRush": self.FirmRush,
            "QUOTE": self.QUOTE,
            "APPROVED": self.APPROVED,
            "CLEAN": self.CLEAN,
            "CLEANFIRST": self.CLEANFIRST,
            # Strings
            "QUOTE_BY": self.QUOTE_BY,
            "RackNo": self.RackNo,
            "STORAGE": self.STORAGE,
            "ITEM_TYPE": self.ITEM_TYPE,
            "TYPE_OF_REPAIR": self.TYPE_OF_REPAIR,
            "SPECIALINSTRUCTIONS": self.SPECIALINSTRUCTIONS,
            "SEECLEAN": self.SEECLEAN,
            "REPAIRSDONEBY": self.REPAIRSDONEBY,
            "MaterialList": self.MaterialList,
            "CUSTOMERPRICE": self.CUSTOMERPRICE,
            "RETURNSTATUS": self.RETURNSTATUS,
            "LOCATION": self.LOCATION,
            "final_location": self.final_location,
            # Timestamps
            "created_at": self.created_at.strftime("%m/%d/%Y %H:%M:%S")
            if self.created_at
            else None,
            "updated_at": self.updated_at.strftime("%m/%d/%Y %H:%M:%S")
            if self.updated_at
            else None,
        }

    def __repr__(self):
        return f"<RepairWorkOrder {self.RepairOrderNo}: {self.ROName}>"

    def __str__(self):
        return f"Repair Order {self.RepairOrderNo} - {self.ROName or 'Unnamed'}"


class RepairWorkOrderItem(db.Model):
    __tablename__ = "tblreporddetcustawngs"

    # Auto-increment primary key
    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)

    # Foreign key to repair order
    RepairOrderNo = db.Column(
        "repairorderno",
        db.String,
        db.ForeignKey("tblrepairworkorderdetail.repairorderno"),
        nullable=False,
        index=True,  # Add index for faster lookups
    )

    # Fields that were previously part of composite primary key
    Description = db.Column("description", db.String, nullable=False, default="")
    Material = db.Column("material", db.String, nullable=False, default="")

    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    # Rest of the columns
    Qty = db.Column("qty", db.Integer, nullable=True)
    Condition = db.Column("condition", db.String)
    Color = db.Column("color", db.String)
    SizeWgt = db.Column("sizewgt", db.String)
    Price = db.Column("price", db.Numeric(10, 2), nullable=True)

    # relationships
    repair_work_order = db.relationship("RepairWorkOrder", back_populates="items")
    customer = db.relationship("Customer")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "id": self.id,
            "RepairOrderNo": self.RepairOrderNo,
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
        return f"<RepairWorkOrderItem {self.RepairOrderNo}: {self.Description}>"

    def __str__(self):
        return f"{self.Description} ({self.Material}) - Qty: {self.Qty}"
