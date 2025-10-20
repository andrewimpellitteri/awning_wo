"""Add created_at timestamp to inventory table

Revision ID: 5b0dfd867084
Revises: 47b99b554807
Create Date: 2025-10-20 12:41:27.139322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5b0dfd867084'
down_revision: Union[str, None] = '47b99b554807'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at column to inventory table (tblcustawngs)
    op.add_column('tblcustawngs', sa.Column('created_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove created_at column from inventory table
    op.drop_column('tblcustawngs', 'created_at')
