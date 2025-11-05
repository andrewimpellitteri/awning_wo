#!/usr/bin/env python3
"""
Generate an invite token for user registration.

Usage:
    python generate_invite_token.py [role]

Where role is one of: user, manager, admin (default: user)
"""

import sys
from app import create_app
from extensions import db
from models.invite_token import InviteToken

def generate_token(role="user"):
    """Generate an invite token and save to database."""
    valid_roles = {"user", "manager", "admin"}

    if role not in valid_roles:
        print(f"Error: Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        try:
            invite = InviteToken.generate_token(role=role)
            db.session.commit()

            print(f"\n✓ Invite token generated successfully!")
            print(f"\nToken:   {invite.token}")
            print(f"Role:    {invite.role}")
            print(f"Created: {invite.created_at}")
            print(f"\nShare this token with the user to register at /register")

        except Exception as e:
            db.session.rollback()
            print(f"Error generating token: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) > 1 else "user"
    generate_token(role)
