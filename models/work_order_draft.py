from extensions import db
from sqlalchemy.sql import func
from datetime import datetime


class WorkOrderDraft(db.Model):
    """
    Stores draft work orders for users to prevent data loss.
    Auto-save functionality stores form data here every 30 seconds.
    """
    __tablename__ = "work_order_drafts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Link to user who created the draft
    # Note: No foreign key constraint because user table lacks primary key
    # Application enforces referential integrity via @login_required
    user_id = db.Column(
        db.BigInteger,  # Match user.id type
        nullable=False,
        index=True
    )

    # Draft metadata
    draft_name = db.Column(db.String(255), nullable=True)  # Optional user-provided name
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Form data stored as JSON
    # This will contain all form fields: CustID, WOName, DateIn, items, etc.
    form_data = db.Column(db.JSON, nullable=False)

    # Optional: Track what page/form type this draft is for
    form_type = db.Column(db.String(50), default="work_order", nullable=False)
    # Examples: "work_order", "repair_order", "quote"

    # Relationships
    # Use primaryjoin since there's no foreign key constraint
    user = db.relationship(
        "User",
        primaryjoin="WorkOrderDraft.user_id == User.id",
        foreign_keys="WorkOrderDraft.user_id",
        backref=db.backref("work_order_drafts", lazy=True)
    )

    def __repr__(self):
        return f"<WorkOrderDraft {self.id} by User {self.user_id}>"

    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "draft_name": self.draft_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "form_data": self.form_data,
            "form_type": self.form_type,
        }

    @staticmethod
    def cleanup_old_drafts(user_id, keep_most_recent=5):
        """
        Delete old drafts for a user, keeping only the most recent N drafts.
        Call this periodically to prevent draft table bloat.

        Args:
            user_id: User ID to clean up drafts for
            keep_most_recent: Number of drafts to keep (default 5)
        """
        drafts = WorkOrderDraft.query.filter_by(user_id=user_id).order_by(
            WorkOrderDraft.updated_at.desc()
        ).all()

        if len(drafts) > keep_most_recent:
            drafts_to_delete = drafts[keep_most_recent:]
            for draft in drafts_to_delete:
                db.session.delete(draft)
            db.session.commit()
            return len(drafts_to_delete)
        return 0
