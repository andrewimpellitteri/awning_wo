"""add_returnto_field_to_work_and_repair_orders

Revision ID: 09dc975e09be
Revises: 5b0dfd867084
Create Date: 2025-10-20 21:43:42.116123

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09dc975e09be'
down_revision: Union[str, None] = '5b0dfd867084'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add returnto column to work orders table
    op.add_column('tblcustworkorderdetail',
                  sa.Column('returnto', sa.String(), nullable=True))

    # Add returnto column to repair orders table
    op.add_column('tblrepairworkorderdetail',
                  sa.Column('returnto', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove returnto column from repair orders table
    op.drop_column('tblrepairworkorderdetail', 'returnto')

    # Remove returnto column from work orders table
    op.drop_column('tblcustworkorderdetail', 'returnto')
