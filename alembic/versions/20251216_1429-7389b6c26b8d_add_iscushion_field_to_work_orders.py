"""add_iscushion_field_to_work_orders

Revision ID: 7389b6c26b8d
Revises: 524d6b061f83
Create Date: 2025-12-16 14:29:22.074618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7389b6c26b8d'
down_revision: Union[str, None] = '524d6b061f83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add isCushion column to work orders table
    op.add_column('tblcustworkorderdetail', sa.Column('iscushion', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    # Remove isCushion column from work orders table
    op.drop_column('tblcustworkorderdetail', 'iscushion')
