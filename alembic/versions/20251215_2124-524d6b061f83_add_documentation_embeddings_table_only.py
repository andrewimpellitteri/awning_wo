"""Add documentation embeddings table only

Revision ID: 524d6b061f83
Revises: 2359481d0ef0
Create Date: 2025-12-15 21:24:26.747215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '524d6b061f83'
down_revision: Union[str, None] = 'a46a6e765dbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create documentation_embeddings table
    op.create_table(
        'documentation_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_documentation_embeddings_file_path', 'documentation_embeddings', ['file_path'], unique=True)
    op.create_index('ix_documentation_embeddings_category', 'documentation_embeddings', ['category'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_documentation_embeddings_category', table_name='documentation_embeddings')
    op.drop_index('ix_documentation_embeddings_file_path', table_name='documentation_embeddings')

    # Drop table
    op.drop_table('documentation_embeddings')
