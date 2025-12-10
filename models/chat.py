"""
Chat models for RAG chatbot functionality.

These models store chat sessions and messages for the AI assistant.
"""
from extensions import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSON


class ChatSession(db.Model):
    """Represents a chat conversation session."""
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)

    # Optional context - link to work order or customer
    work_order_no = db.Column(db.String, nullable=True)
    customer_id = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    messages = db.relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    def to_dict(self, include_messages=False):
        """Convert to dictionary for JSON serialization."""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "work_order_no": self.work_order_no,
            "customer_id": self.customer_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }
        if include_messages:
            data["messages"] = [msg.to_dict() for msg in self.messages]
        return data

    def __repr__(self):
        return f"<ChatSession {self.id}: {self.title or 'Untitled'}>"


class ChatMessage(db.Model):
    """Represents a single message in a chat session."""
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    message_metadata = db.Column(JSON, nullable=True)  # Store retrieved sources, context, etc.

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session = db.relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.message_metadata,  # Keep 'metadata' key in JSON for API compatibility
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<ChatMessage {self.id}: {self.role}>"
