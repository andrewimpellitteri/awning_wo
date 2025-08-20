from app import db
from datetime import datetime

class Photo(db.Model):
    __tablename__ = 'photos'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))  # Local file path
    photo_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Photo {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'photo_date': self.photo_date.isoformat() if self.photo_date else None,
            'notes': self.notes,
            'file_size': self.file_size
        }
