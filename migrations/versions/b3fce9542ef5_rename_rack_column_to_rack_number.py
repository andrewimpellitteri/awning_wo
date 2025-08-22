"""Rename Rack# column to rack_number

Revision ID: rename_rack_column
Revises: [previous_revision_id]
Create Date: 2024-XX-XX XX:XX:XX.XXXXXX

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "rename_rack_column"
down_revision = "[previous_revision_id]"  # Replace with your actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Rename Rack# column to rack_number for better PostgreSQL compatibility"""
    # Rename the problematic column
    op.execute(
        'ALTER TABLE tblcustworkorderdetail RENAME COLUMN "Rack#" TO rack_number'
    )


def downgrade():
    """Revert rack_number column back to Rack#"""
    # Revert the column name change
    op.execute(
        'ALTER TABLE tblcustworkorderdetail RENAME COLUMN rack_number TO "Rack#"'
    )
