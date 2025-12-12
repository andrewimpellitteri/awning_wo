"""add_document_embeddings_table

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2025-12-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_embeddings table for OCR'd work order files"""

    # Create document_embeddings table
    op.create_table(
        'document_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),  # References tblworkorderfiles.id
        sa.Column('work_order_no', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('s3_path', sa.String(), nullable=False),
        sa.Column('ocr_text', sa.Text(), nullable=True),  # Full extracted text
        sa.Column('content', sa.Text(), nullable=False),  # Text used for embedding
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('ocr_method', sa.String(50), nullable=True),  # 'textract_image', 'textract_pdf', etc.
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for efficient lookups
    op.create_index('ix_document_embeddings_file_id', 'document_embeddings', ['file_id'])
    op.create_index('ix_document_embeddings_work_order_no', 'document_embeddings', ['work_order_no'])


def downgrade() -> None:
    """Drop document_embeddings table"""

    op.drop_index('ix_document_embeddings_work_order_no', table_name='document_embeddings')
    op.drop_index('ix_document_embeddings_file_id', table_name='document_embeddings')
    op.drop_table('document_embeddings')
