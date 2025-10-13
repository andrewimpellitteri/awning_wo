"""initial_baseline

Revision ID: 64fe9db37cf1
Revises:
Create Date: 2025-10-13 19:00:00.000000

This is a baseline migration that represents the current production schema
after migration from Access DB. No changes need to be applied - the database
already has this schema. This migration exists for tracking purposes only.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64fe9db37cf1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration - no changes needed.
    The database schema already matches the models as of this revision.
    """
    pass


def downgrade() -> None:
    """
    Cannot downgrade from baseline.
    """
    pass