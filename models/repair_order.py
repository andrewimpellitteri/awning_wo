from datetime import datetime
from extensions import db


class RepairWorkOrder(db.Model):
    __tablename__ = "tblRepairWorkOrderDetail"

    RepairOrderNo = db.Column(db.String, primary_key=True, nullable=False)
    CustID = db.Column(db.String, db.ForeignKey("tblCustomers.CustID"), nullable=False)

    ROName = db.Column(db.String)
    SOURCE = db.Column(db.String)
    WO_DATE = db.Column("WO DATE", db.String)
    DATE_TO_SUB = db.Column("DATE TO SUB", db.String)
    DateRequired = db.Column(db.String)
    RushOrder = db.Column(db.String)
    FirmRush = db.Column(db.String)
    QUOTE = db.Column(db.String)
    QUOTE_BY = db.Column("QUOTE  BY", db.String)
    APPROVED = db.Column(db.String)
    RackNo = db.Column("RACK#", db.String)
    STORAGE = db.Column(db.String)
    ITEM_TYPE = db.Column("ITEM TYPE", db.String)
    TYPE_OF_REPAIR = db.Column("TYPE OF REPAIR", db.String)
    SPECIALINSTRUCTIONS = db.Column(db.Text)
    CLEAN = db.Column(db.String)
    SEECLEAN = db.Column(db.String)
    CLEANFIRST = db.Column(db.String)
    REPAIRSDONEBY = db.Column(db.String)
    DateCompleted = db.Column(db.String)
    MaterialList = db.Column(db.Text)
    CUSTOMERPRICE = db.Column(db.String)
    RETURNSTATUS = db.Column(db.String)
    RETURNDATE = db.Column(db.String)
    LOCATION = db.Column(db.String)
    DATEOUT = db.Column(db.String)
    DateIn = db.Column(db.String)

    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())
    updated_at = db.Column(
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

    def __repr__(self):
        return f"<RepairWorkOrder {self.RepairOrderNo}: {self.ROName}>"

    def __str__(self):
        return f"Repair Order {self.RepairOrderNo} - {self.ROName or 'Unnamed'}"


class RepairWorkOrderItem(db.Model):
    __tablename__ = "tblRepOrdDetCustAwngs"

    # Composite primary key to handle multiple items per repair order
    RepairOrderNo = db.Column(
        db.String,
        db.ForeignKey("tblRepairWorkOrderDetail.RepairOrderNo"),
        nullable=False,
        primary_key=True,
    )
    CustID = db.Column(db.String, db.ForeignKey("tblCustomers.CustID"), nullable=False)

    # Add Description and Material to primary key to allow multiple items per repair order
    Description = db.Column(db.String, primary_key=True)
    Material = db.Column(db.String, primary_key=True)

    # Rest of the columns
    Qty = db.Column(db.String)
    Condition = db.Column(db.String)
    Color = db.Column(db.String)
    SizeWgt = db.Column(db.String)
    Price = db.Column(db.String)

    # relationships
    repair_work_order = db.relationship("RepairWorkOrder", back_populates="items")

    def __repr__(self):
        return f"<RepairWorkOrderItem {self.RepairOrderNo}: {self.Description}>"

    def __str__(self):
        return f"{self.Description} ({self.Material}) - Qty: {self.Qty}"
