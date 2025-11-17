"""add_customer_search_indexes

Revision ID: 89f615af9aa1
Revises: 9678d67d158f
Create Date: 2025-11-16 16:02:04.594386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89f615af9aa1'
down_revision: Union[str, None] = '9678d67d158f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add B-tree indexes on tblcustomers to optimize customer search queries.

    For ~10,000 customers, these indexes will significantly speed up:
    - ILIKE/LIKE searches on name, contact, and custid
    - ORDER BY name operations

    Using LOWER() function indexes for case-insensitive searches.
    """
    # Index for name searches (most common search field)
    # Using functional index on LOWER(name) for case-insensitive searches
    op.create_index(
        'idx_customers_name_lower',
        'tblcustomers',
        [sa.text('LOWER(name)')],
        postgresql_using='btree'
    )

    # Index for contact searches
    op.create_index(
        'idx_customers_contact_lower',
        'tblcustomers',
        [sa.text('LOWER(contact)')],
        postgresql_using='btree'
    )

    # Index for CustID searches (already primary key, but adding for completeness)
    # This helps with LOWER(custid) searches
    op.create_index(
        'idx_customers_custid_lower',
        'tblcustomers',
        [sa.text('LOWER(custid)')],
        postgresql_using='btree'
    )

    # Regular index on name for ORDER BY operations (without LOWER)
    # This is in addition to the LOWER index and helps with non-filtered sorts
    op.create_index(
        'idx_customers_name',
        'tblcustomers',
        ['name'],
        postgresql_using='btree'
    )


def downgrade() -> None:
    """
    Remove customer search indexes.
    """
    op.drop_index('idx_customers_name', table_name='tblcustomers')
    op.drop_index('idx_customers_custid_lower', table_name='tblcustomers')
    op.drop_index('idx_customers_contact_lower', table_name='tblcustomers')
    op.drop_index('idx_customers_name_lower', table_name='tblcustomers')
