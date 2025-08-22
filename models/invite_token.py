# models/invite_token.py
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
    def generate(role="user"):
        token = secrets.token_urlsafe(16)  # short but secure
        invite = InviteToken(token=token, role=role)
        db.session.add(invite)
        db.session.commit()
        return invite
