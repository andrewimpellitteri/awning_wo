"""add_checkin_extra_fields

Revision ID: add_checkin_fields
Revises: 385d84275569
Create Date: 2025-11-09 17:29:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_checkin_fields'
down_revision: Union[str, None] = '385d84275569'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fields to tblcheckins to match work order form
    op.add_column('tblcheckins', sa.Column('specialinstructions', sa.Text(), nullable=True))
    op.add_column('tblcheckins', sa.Column('storagetime', sa.String(), nullable=True))
    op.add_column('tblcheckins', sa.Column('rack_number', sa.String(), nullable=True))
    op.add_column('tblcheckins', sa.Column('returnto', sa.String(), nullable=True))
    op.add_column('tblcheckins', sa.Column('daterequired', sa.Date(), nullable=True))
    op.add_column('tblcheckins', sa.Column('repairsneeded', sa.Boolean(), nullable=True))
    op.add_column('tblcheckins', sa.Column('rushorder', sa.Boolean(), nullable=True))


def downgrade() -> None:
    # Remove added columns
    op.drop_column('tblcheckins', 'rushorder')
    op.drop_column('tblcheckins', 'repairsneeded')
    op.drop_column('tblcheckins', 'daterequired')
    op.drop_column('tblcheckins', 'returnto')
    op.drop_column('tblcheckins', 'rack_number')
    op.drop_column('tblcheckins', 'storagetime')
    op.drop_column('tblcheckins', 'specialinstructions')
