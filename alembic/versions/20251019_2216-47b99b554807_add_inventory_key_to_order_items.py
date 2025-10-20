"""add_inventory_key_to_order_items

Revision ID: 47b99b554807
Revises: 6ee664c8b95f
Create Date: 2025-10-19 22:16:17.259294

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47b99b554807'
down_revision: Union[str, None] = '6ee664c8b95f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add inventory_key column to work order items and repair order items tables.
    This allows tracking which inventory catalog item each order item came from,
    enabling dynamic filtering between existing items and available inventory.

    The column is nullable because:
    - Existing items don't have this tracking yet
    - Manually added items (not from inventory) won't have an InventoryKey
    """
    # Add inventory_key to work order items table
    op.add_column('tblorddetcustawngs',
                  sa.Column('inventory_key', sa.String(), nullable=True))

    # Add inventory_key to repair order items table
    op.add_column('tblreporddetcustawngs',
                  sa.Column('inventory_key', sa.String(), nullable=True))


def downgrade() -> None:
    """
    Remove inventory_key columns from order items tables.
    """
    # Remove from work order items table
    op.drop_column('tblorddetcustawngs', 'inventory_key')

    # Remove from repair order items table
    op.drop_column('tblreporddetcustawngs', 'inventory_key')
