"""change_quote_field_to_string

Revision ID: 6ee664c8b95f
Revises: 64fe9db37cf1
Create Date: 2025-10-17 10:15:51.582151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ee664c8b95f'
down_revision: Union[str, None] = '64fe9db37cf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Change QUOTE field from Boolean to String (VARCHAR).
    Converts existing boolean values:
    - True → 'YES'
    - False → NULL
    - NULL → NULL

    New valid values: 'YES', 'DONE', 'APPROVED', or NULL
    """
    # For PostgreSQL, we need to:
    # 1. Add a temporary column
    # 2. Copy data with conversion
    # 3. Drop old column
    # 4. Rename new column

    # Add temporary column
    op.add_column('tblrepairworkorderdetail',
                  sa.Column('quote_temp', sa.String(), nullable=True))

    # Convert boolean values to strings
    # True → 'YES', False → NULL, NULL → NULL
    op.execute("""
        UPDATE tblrepairworkorderdetail
        SET quote_temp = CASE
            WHEN quote = true THEN 'YES'
            ELSE NULL
        END
    """)

    # Drop old boolean column
    op.drop_column('tblrepairworkorderdetail', 'quote')

    # Rename temp column to quote
    op.alter_column('tblrepairworkorderdetail', 'quote_temp',
                    new_column_name='quote')


def downgrade() -> None:
    """
    Revert QUOTE field from String back to Boolean.
    Converts string values:
    - 'YES', 'DONE', 'APPROVED' → True
    - NULL → NULL
    - Other values → False
    """
    # Add temporary boolean column
    op.add_column('tblrepairworkorderdetail',
                  sa.Column('quote_temp', sa.Boolean(), nullable=True))

    # Convert string values back to boolean
    op.execute("""
        UPDATE tblrepairworkorderdetail
        SET quote_temp = CASE
            WHEN quote IN ('YES', 'DONE', 'APPROVED') THEN true
            WHEN quote IS NULL THEN NULL
            ELSE false
        END
    """)

    # Drop string column
    op.drop_column('tblrepairworkorderdetail', 'quote')

    # Rename temp column to quote
    op.alter_column('tblrepairworkorderdetail', 'quote_temp',
                    new_column_name='quote')
