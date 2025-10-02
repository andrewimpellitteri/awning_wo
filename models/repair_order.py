from datetime import datetime
from extensions import db


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
    WO_DATE = db.Column("WO DATE", db.String)  # Uppercase with space
    DATE_TO_SUB = db.Column("DATE TO SUB", db.String)  # Uppercase with spaces
    DateRequired = db.Column("daterequired", db.String)
    RushOrder = db.Column("rushorder", db.String)
    FirmRush = db.Column("firmrush", db.String)
    QUOTE = db.Column("quote", db.String)
    QUOTE_BY = db.Column(
        "QUOTE  BY", db.String
    )  # Note: TWO spaces between QUOTE and BY
    APPROVED = db.Column("approved", db.String)
    RackNo = db.Column("RACK#", db.String)  # Uppercase
    STORAGE = db.Column("storage", db.String)
    ITEM_TYPE = db.Column("ITEM TYPE", db.String)  # Uppercase with space
    TYPE_OF_REPAIR = db.Column("TYPE OF REPAIR", db.String)  # Uppercase with spaces
    SPECIALINSTRUCTIONS = db.Column("specialinstructions", db.Text)
    CLEAN = db.Column("clean", db.String)
    SEECLEAN = db.Column("seeclean", db.String)
    CLEANFIRST = db.Column("cleanfirst", db.String)
    REPAIRSDONEBY = db.Column("repairsdoneby", db.String)
    DateCompleted = db.Column("datecompleted", db.String)
    MaterialList = db.Column("materiallist", db.Text)
    CUSTOMERPRICE = db.Column("customerprice", db.String)
    RETURNSTATUS = db.Column("returnstatus", db.String)
    RETURNDATE = db.Column("returndate", db.String)
    LOCATION = db.Column("location", db.String)
    DATEOUT = db.Column("dateout", db.String)
    DateIn = db.Column("datein", db.String)

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
    customer = db.relationship("Customer", back_populates="repair_work_orders")
    items = db.relationship(
        "RepairWorkOrderItem",
        back_populates="repair_work_order",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            "RepairOrderNo": self.RepairOrderNo,
            "CustID": self.CustID,
            "ROName": self.ROName,
            "SOURCE": self.SOURCE,
            "WO_DATE": self.WO_DATE,
            "DATE_TO_SUB": self.DATE_TO_SUB,
            "DateRequired": self.DateRequired,
            "RushOrder": self.RushOrder,
            "FirmRush": self.FirmRush,
            "QUOTE": self.QUOTE,
            "QUOTE_BY": self.QUOTE_BY,
            "APPROVED": self.APPROVED,
            "RackNo": self.RackNo,
            "STORAGE": self.STORAGE,
            "ITEM_TYPE": self.ITEM_TYPE,
            "TYPE_OF_REPAIR": self.TYPE_OF_REPAIR,
            "SPECIALINSTRUCTIONS": self.SPECIALINSTRUCTIONS,
            "CLEAN": self.CLEAN,
            "SEECLEAN": self.SEECLEAN,
            "CLEANFIRST": self.CLEANFIRST,
            "REPAIRSDONEBY": self.REPAIRSDONEBY,
            "DateCompleted": self.DateCompleted,
            "MaterialList": self.MaterialList,
            "CUSTOMERPRICE": self.CUSTOMERPRICE,
            "RETURNSTATUS": self.RETURNSTATUS,
            "RETURNDATE": self.RETURNDATE,
            "LOCATION": self.LOCATION,
            "DATEOUT": self.DATEOUT,
            "DateIn": self.DateIn,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def __repr__(self):
        return f"<RepairWorkOrder {self.RepairOrderNo}: {self.ROName}>"

    def __str__(self):
        return f"Repair Order {self.RepairOrderNo} - {self.ROName or 'Unnamed'}"


class RepairWorkOrderItem(db.Model):
    __tablename__ = "tblreporddetcustawngs"

    # Add auto-incrementing ID as primary key for easier item management
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Map to lowercase database column names
    RepairOrderNo = db.Column(
        "repairorderno",
        db.String,
        db.ForeignKey(
            "tblrepairworkorderdetail.repairorderno"
        ),  # Updated foreign key reference
        nullable=False,
    )
    CustID = db.Column(
        "custid", db.String, db.ForeignKey("tblcustomers.custid"), nullable=False
    )

    # Keep Description and Material as regular columns
    Description = db.Column("description", db.String)
    Material = db.Column("material", db.String)

    # Rest of the columns
    Qty = db.Column("qty", db.String)
    Condition = db.Column("condition", db.String)
    Color = db.Column("color", db.String)
    SizeWgt = db.Column("sizewgt", db.String)
    Price = db.Column("price", db.String)

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
