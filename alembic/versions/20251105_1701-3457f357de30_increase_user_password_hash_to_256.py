"""increase_user_password_hash_to_256

Revision ID: 3457f357de30
Revises: 09dc975e09be
Create Date: 2025-11-05 17:01:31.096063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3457f357de30'
down_revision: Union[str, None] = '09dc975e09be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Increase password_hash field from 120 to 256 characters
    op.alter_column('user', 'password_hash',
                    existing_type=sa.String(length=120),
                    type_=sa.String(length=256),
                    nullable=False)


def downgrade() -> None:
    # Revert password_hash field from 256 to 120 characters
    op.alter_column('user', 'password_hash',
                    existing_type=sa.String(length=256),
                    type_=sa.String(length=120),
                    nullable=False)
