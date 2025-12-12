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


class DocumentEmbedding(db.Model):
    """Stores embeddings for OCR'd document text from work order files."""
    __tablename__ = "document_embeddings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_id = db.Column(db.Integer, nullable=False, index=True)  # References WorkOrderFile.id
    work_order_no = db.Column(db.String, nullable=False, index=True)  # For easier querying
    filename = db.Column(db.String, nullable=False)  # Original filename
    s3_path = db.Column(db.String, nullable=False)  # S3 path for reference
    ocr_text = db.Column(db.Text, nullable=True)  # Full OCR extracted text
    content = db.Column(db.Text, nullable=False)  # Text that was embedded (may be truncated)
    embedding = db.Column(ARRAY(db.Float), nullable=False)  # Vector embedding
    ocr_confidence = db.Column(db.Float, nullable=True)  # Average OCR confidence score
    ocr_method = db.Column(db.String(50), nullable=True)  # 'textract', 'pdf_text', etc.

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Convert to dictionary (excludes embedding for efficiency)."""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "work_order_no": self.work_order_no,
            "filename": self.filename,
            "s3_path": self.s3_path,
            "ocr_text": self.ocr_text,
            "content": self.content,
            "ocr_confidence": self.ocr_confidence,
            "ocr_method": self.ocr_method,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<DocumentEmbedding {self.id}: {self.filename} (WO: {self.work_order_no})>"
