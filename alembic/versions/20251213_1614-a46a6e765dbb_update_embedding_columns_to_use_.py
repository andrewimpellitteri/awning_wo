"""Update embedding columns to use pgvector Vector type

Revision ID: a46a6e765dbb
Revises: c8d9e0f1a2b3
Create Date: 2025-12-13 16:14:47.242524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = 'a46a6e765dbb'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure the pgvector extension is enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    # Alter the embedding columns to use the VECTOR type
    op.alter_column('customer_embeddings', 'embedding',
               existing_type=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
               type_=pgvector.sqlalchemy.Vector(1536),
               existing_nullable=False)
    op.alter_column('item_embeddings', 'embedding',
               existing_type=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
               type_=pgvector.sqlalchemy.Vector(1536),
               existing_nullable=False)
    op.alter_column('work_order_embeddings', 'embedding',
               existing_type=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
               type_=pgvector.sqlalchemy.Vector(1536),
               existing_nullable=False)


def downgrade() -> None:
    # Revert the embedding columns back to ARRAY of float
    op.alter_column('work_order_embeddings', 'embedding',
               existing_type=pgvector.sqlalchemy.Vector(1536),
               type_=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
               existing_nullable=False)
    op.alter_column('item_embeddings', 'embedding',
               existing_type=pgvector.sqlalchemy.Vector(1536),
               type_=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
               existing_nullable=False)
    op.alter_column('customer_embeddings', 'embedding',
               existing_type=pgvector.sqlalchemy.Vector(1536),
               type_=postgresql.ARRAY(.DOUBLE_PRECISION(precision=53)),
               existing_nullable=False)