from app import db
from datetime import datetime

class RepairOrder(db.Model):
    __tablename__ = 'repair_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    repair_order_no = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    ro_name = db.Column(db.String(200))
    
    # Source and dates
    source = db.Column(db.String(200))
    wo_date = db.Column(db.Date)
    date_to_sub = db.Column(db.Date)
    date_required = db.Column(db.Date)
    date_in = db.Column(db.Date)
    date_completed = db.Column(db.Date)
    date_out = db.Column(db.Date)
    return_date = db.Column(db.Date)
    
    # Order details
    rush_order = db.Column(db.Boolean, default=False)
    firm_rush = db.Column(db.Boolean, default=False)
    quote = db.Column(db.Numeric(10, 2))
    quote_by = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=False)
    
    # Storage and location
    rack_number = db.Column(db.String(20))
    storage = db.Column(db.String(100))
    location = db.Column(db.String(100))
    
    # Repair details
    item_type = db.Column(db.String(100))
    type_of_repair = db.Column(db.String(200))
    special_instructions = db.Column(db.Text)
    repairs_done_by = db.Column(db.String(100))
    material_list = db.Column(db.Text)
    customer_price = db.Column(db.Numeric(10, 2))
    
    # Services
    clean = db.Column(db.Boolean, default=False)
    see_clean = db.Column(db.Boolean, default=False)
    clean_first = db.Column(db.Boolean, default=False)
    
    # Status
    return_status = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('RepairOrderItem', backref='repair_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<RepairOrder {self.repair_order_no}>'

class RepairOrderItem(db.Model):
    __tablename__ = 'repair_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    repair_order_id = db.Column(db.Integer, db.ForeignKey('repair_orders.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    qty = db.Column(db.Integer, default=1)
    description = db.Column(db.String(500))
    material = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50))
    size_weight = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    
    def __repr__(self):
        return f'<RepairOrderItem {self.description}>'
