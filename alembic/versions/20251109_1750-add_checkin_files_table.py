"""add_checkin_files_table

Revision ID: add_checkin_files
Revises: add_checkin_fields
Create Date: 2025-11-09 17:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_checkin_files'
down_revision: Union[str, None] = 'add_checkin_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tblcheckinfiles table
    op.create_table(
        'tblcheckinfiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('checkinid', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_type', sa.String(length=100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['checkinid'], ['tblcheckins.checkinid'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index for faster lookups
    op.create_index('idx_tblcheckinfiles_checkinid', 'tblcheckinfiles', ['checkinid'], unique=False)


def downgrade() -> None:
    # Drop table
    op.drop_index('idx_tblcheckinfiles_checkinid', table_name='tblcheckinfiles')
    op.drop_table('tblcheckinfiles')
