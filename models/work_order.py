from datetime import datetime
from extensions import db
from models.source import Source


class WorkOrder(db.Model):
    __tablename__ = "tblCustWorkOrderDetail"

    WorkOrderNo = db.Column(db.String, primary_key=True, nullable=False)
    CustID = db.Column(db.String, db.ForeignKey("tblCustomers.CustID"), nullable=False)

    WOName = db.Column(db.String)
    Storage = db.Column(db.String)
    StorageTime = db.Column(db.String)
    RackNo = db.Column("Rack#", db.String)
    SpecialInstructions = db.Column(db.Text)
    RepairsNeeded = db.Column(db.Text)
    SeeRepair = db.Column(db.String)
    ReturnStatus = db.Column(db.String)
    DateCompleted = db.Column(db.String)
    Quote = db.Column(db.String)
    Clean = db.Column(db.String)
    Treat = db.Column(db.String)
    RushOrder = db.Column(db.String)
    DateRequired = db.Column(db.String)
    DateIn = db.Column(db.String)
    ShipTo = db.Column(db.String, db.ForeignKey("tblSource.SSource"))
    FirmRush = db.Column(db.String)
    CleanFirstWO = db.Column(db.String)
    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())
    updated_at = db.Column(
        db.String,
        default=lambda: datetime.utcnow().isoformat(),
        onupdate=lambda: datetime.utcnow().isoformat(),
    )

    # relationships
    customer = db.relationship("Customer", back_populates="work_orders")
    items = db.relationship(
        "WorkOrderItem", back_populates="work_order", cascade="all, delete-orphan"
    )

    ship_to_source = db.relationship(
        "Source",
        primaryjoin="WorkOrder.ShipTo==Source.SSource",
        lazy="joined",
        uselist=False,
    )


class WorkOrderItem(db.Model):
    __tablename__ = "tblOrdDetCustAwngs"

    # FIXED: Create a composite primary key to handle multiple items per work order
    WorkOrderNo = db.Column(
        db.String,
        db.ForeignKey("tblCustWorkOrderDetail.WorkOrderNo"),
        nullable=False,
        primary_key=True,
    )
    CustID = db.Column(db.String, db.ForeignKey("tblCustomers.CustID"), nullable=False)

    # Add Description and Material to primary key to allow multiple items per work order
    Description = db.Column(db.String, primary_key=True)
    Material = db.Column(db.String, primary_key=True)

    # Rest of the columns
    Qty = db.Column(db.String)
    Condition = db.Column(db.String)
    Color = db.Column(db.String)
    SizeWgt = db.Column(db.String)
    Price = db.Column(db.String)

    # relationships
    work_order = db.relationship("WorkOrder", back_populates="items")

    def __repr__(self):
        return f"<WorkOrderItem {self.WorkOrderNo}: {self.Description}>"

    def __str__(self):
        return f"{self.Description} ({self.Material}) - Qty: {self.Qty}"
