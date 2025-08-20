from app import db
from datetime import datetime

class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_no = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    wo_name = db.Column(db.String(200))
    
    # Storage and handling
    storage = db.Column(db.String(100))
    storage_time = db.Column(db.String(50))
    rack_number = db.Column(db.String(20))
    
    # Instructions and requirements
    special_instructions = db.Column(db.Text)
    repairs_needed = db.Column(db.Text)
    see_repair = db.Column(db.Boolean, default=False)
    
    # Status and timing
    return_status = db.Column(db.String(50))
    date_completed = db.Column(db.Date)
    date_in = db.Column(db.Date)
    date_required = db.Column(db.Date)
    
    # Services
    quote = db.Column(db.Numeric(10, 2))
    clean = db.Column(db.Boolean, default=False)
    treat = db.Column(db.Boolean, default=False)
    rush_order = db.Column(db.Boolean, default=False)
    firm_rush = db.Column(db.Boolean, default=False)
    clean_first_wo = db.Column(db.Boolean, default=False)
    
    # Shipping
    ship_to = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('WorkOrderItem', backref='work_order', lazy='dynamic', cascade='all, delete-orphan')
    progress_records = db.relationship('ProgressTracking', backref='work_order', lazy='dynamic')
    
    def __repr__(self):
        return f'<WorkOrder {self.work_order_no}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'work_order_no': self.work_order_no,
            'customer_id': self.customer_id,
            'wo_name': self.wo_name,
            'date_in': self.date_in.isoformat() if self.date_in else None,
            'date_required': self.date_required.isoformat() if self.date_required else None,
            'rush_order': self.rush_order,
            'quote': float(self.quote) if self.quote else None,
            'return_status': self.return_status
        }

class WorkOrderItem(db.Model):
    __tablename__ = 'work_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    qty = db.Column(db.Integer, default=1)
    description = db.Column(db.String(500))
    material = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50))
    size_weight = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    
    def __repr__(self):
        return f'<WorkOrderItem {self.description}>'
