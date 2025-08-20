from app import db
from datetime import datetime

class ProgressTracking(db.Model):
    __tablename__ = 'progress_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'))
    
    # Progress details
    pgrs_work_order_no = db.Column(db.String(50))
    pgrs_name = db.Column(db.String(200))
    pgrs_date_in = db.Column(db.Date)
    pgrs_date_updated = db.Column(db.Date)
    pgrs_source = db.Column(db.String(200))
    
    # Work order progress
    wo_quote = db.Column(db.Numeric(10, 2))
    on_deck_clean = db.Column(db.Boolean, default=False)
    tub = db.Column(db.Boolean, default=False)
    clean = db.Column(db.Boolean, default=False)
    treat = db.Column(db.Boolean, default=False)
    wrap_clean = db.Column(db.Boolean, default=False)
    notes_clean = db.Column(db.Text)
    
    # Repair order progress
    pgrs_repair_order_no = db.Column(db.String(50))
    repair_quote = db.Column(db.Numeric(10, 2))
    on_deck_repair = db.Column(db.Boolean, default=False)
    in_process = db.Column(db.Boolean, default=False)
    wrap_repair = db.Column(db.Boolean, default=False)
    repair_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProgressTracking {self.pgrs_work_order_no}>'
