"""add_checkin_tables

Revision ID: 385d84275569
Revises: f2238738a091
Create Date: 2025-11-09 16:44:38.911967

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '385d84275569'
down_revision: Union[str, None] = 'f2238738a091'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tblcheckins table
    op.create_table(
        'tblcheckins',
        sa.Column('checkinid', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('custid', sa.String(), nullable=False),
        sa.Column('datein', sa.Date(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('workorderno', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['custid'], ['tblcustomers.custid'], ),
        sa.ForeignKeyConstraint(['workorderno'], ['tblcustworkorderdetail.workorderno'], ),
        sa.PrimaryKeyConstraint('checkinid')
    )

    # Create tblcheckinitems table
    op.create_table(
        'tblcheckinitems',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('checkinid', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('material', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('qty', sa.Integer(), nullable=True),
        sa.Column('sizewgt', sa.String(), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('condition', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['checkinid'], ['tblcheckins.checkinid'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on checkinid for faster lookups
    op.create_index(op.f('ix_tblcheckinitems_checkinid'), 'tblcheckinitems', ['checkinid'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_tblcheckinitems_checkinid'), table_name='tblcheckinitems')
    op.drop_table('tblcheckinitems')
    op.drop_table('tblcheckins')
