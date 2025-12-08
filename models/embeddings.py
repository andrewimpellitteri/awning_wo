"""
Embedding models for RAG chatbot functionality.

These models store vector embeddings for semantic search over:
- Customers
- Work Orders
- Items (from work orders)
"""
from extensions import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY


class CustomerEmbedding(db.Model):
    """Stores embeddings for customer records."""
    __tablename__ = "customer_embeddings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Text, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)  # The text that was embedded
    embedding = db.Column(ARRAY(db.Float), nullable=False)  # Vector embedding

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Convert to dictionary (excludes embedding for efficiency)."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<CustomerEmbedding {self.id}: {self.customer_id}>"


class WorkOrderEmbedding(db.Model):
    """Stores embeddings for work order records."""
    __tablename__ = "work_order_embeddings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    work_order_no = db.Column(db.String, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)  # The text that was embedded
    embedding = db.Column(ARRAY(db.Float), nullable=False)  # Vector embedding

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Convert to dictionary (excludes embedding for efficiency)."""
        return {
            "id": self.id,
            "work_order_no": self.work_order_no,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<WorkOrderEmbedding {self.id}: {self.work_order_no}>"


class ItemEmbedding(db.Model):
    """Stores embeddings for work order items."""
    __tablename__ = "item_embeddings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_id = db.Column(db.Integer, nullable=False, index=True)  # References WorkOrderItem.id
    content = db.Column(db.Text, nullable=False)  # The text that was embedded
    embedding = db.Column(ARRAY(db.Float), nullable=False)  # Vector embedding

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Convert to dictionary (excludes embedding for efficiency)."""
        return {
            "id": self.id,
            "item_id": self.item_id,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ItemEmbedding {self.id}: item {self.item_id}>"
