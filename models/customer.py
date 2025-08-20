from app import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)  # CustID
    name = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(100))
    address = db.Column(db.String(255))
    address2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    home_phone = db.Column(db.String(20))
    work_phone = db.Column(db.String(20))
    cell_phone = db.Column(db.String(20))
    email_address = db.Column(db.String(150))
    
    # Mailing address
    mail_address = db.Column(db.String(255))
    mail_city = db.Column(db.String(100))
    mail_state = db.Column(db.String(50))
    mail_zip = db.Column(db.String(20))
    
    # Source information
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'))
    source = db.relationship('Source', backref='customers')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    work_orders = db.relationship('WorkOrder', backref='customer', lazy='dynamic')
    repair_orders = db.relationship('RepairOrder', backref='customer', lazy='dynamic')
    inventory_items = db.relationship('InventoryItem', backref='customer', lazy='dynamic')
    photos = db.relationship('Photo', backref='customer', lazy='dynamic')
    
    def __repr__(self):
        return f'<Customer {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contact': self.contact,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'email_address': self.email_address,
            'phone': self.home_phone or self.work_phone or self.cell_phone
        }
