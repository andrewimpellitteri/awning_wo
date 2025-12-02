"""add_work_order_drafts_table

Revision ID: b7c3d4e5f6a7
Revises: a41aef6abd42
Create Date: 2025-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7c3d4e5f6a7'
down_revision: Union[str, None] = 'a41aef6abd42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create work_order_drafts table for auto-save functionality

    Note: Foreign key constraint to user.id is omitted because the user table
    lacks a primary key constraint. We rely on application-level integrity instead.
    """

    op.create_table(
        'work_order_drafts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),  # Match user.id type (bigint)
        sa.Column('draft_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('form_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('form_type', sa.String(length=50), nullable=False, server_default='work_order'),
        sa.PrimaryKeyConstraint('id'),
        # Foreign key omitted - user table has no primary key constraint
        # Application enforces referential integrity via @login_required decorator
    )

    # Create indexes for performance
    op.create_index('ix_work_order_drafts_user_id', 'work_order_drafts', ['user_id'])
    op.create_index('ix_work_order_drafts_form_type', 'work_order_drafts', ['form_type'])
    op.create_index('ix_work_order_drafts_user_updated', 'work_order_drafts', ['user_id', 'updated_at'], postgresql_ops={'updated_at': 'DESC'})


def downgrade() -> None:
    """Drop work_order_drafts table"""

    # Drop indexes first
    op.drop_index('ix_work_order_drafts_user_updated', table_name='work_order_drafts')
    op.drop_index('ix_work_order_drafts_form_type', table_name='work_order_drafts')
    op.drop_index('ix_work_order_drafts_user_id', table_name='work_order_drafts')

    # Drop table
    op.drop_table('work_order_drafts')
