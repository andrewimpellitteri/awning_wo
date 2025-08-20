from app import db
from datetime import datetime

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    description = db.Column(db.String(500))
    material = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50))
    size_weight = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    qty = db.Column(db.Integer, default=1)
    inventory_key = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventoryItem {self.description}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'description': self.description,
            'material': self.material,
            'condition': self.condition,
            'color': self.color,
            'size_weight': self.size_weight,
            'price': float(self.price) if self.price else None,
            'qty': self.qty
        }
