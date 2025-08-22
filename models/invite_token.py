from extensions import db
import secrets
from datetime import datetime


class InviteToken(db.Model):
    __tablename__ = "invite_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False)

    @staticmethod
    def generate_token(role="user"):
        """
        Create an invite token but do not mark it used.
        Returns the token object (not committed yet).
        """
        token_str = secrets.token_urlsafe(16)
        invite = InviteToken(token=token_str, role=role)
        db.session.add(invite)
        db.session.flush()  # assign ID without committing
        return invite
