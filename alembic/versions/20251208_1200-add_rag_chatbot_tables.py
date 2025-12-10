"""add_rag_chatbot_tables

Revision ID: c8d9e0f1a2b3
Revises: b7c3d4e5f6a7
Create Date: 2025-12-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b7c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pgvector extension and RAG chatbot tables"""

    # Enable pgvector extension (requires superuser or rds_superuser on AWS RDS)
    # If this fails, run: CREATE EXTENSION IF NOT EXISTS vector;
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create chat_sessions table for conversation history
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('work_order_no', sa.String(), nullable=True),  # Optional context
        sa.Column('customer_id', sa.String(), nullable=True),  # Optional context
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])
    op.create_index('ix_chat_sessions_updated_at', 'chat_sessions', ['updated_at'])

    # Create chat_messages table for individual messages
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),  # 'user' or 'assistant'
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),  # Retrieved sources, etc.
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])

    # Create customer_embeddings table
    op.create_table(
        'customer_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),  # The text that was embedded
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),  # Vector as array
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_customer_embeddings_customer_id', 'customer_embeddings', ['customer_id'])

    # Create work_order_embeddings table
    op.create_table(
        'work_order_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('work_order_no', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),  # The text that was embedded
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),  # Vector as array
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_work_order_embeddings_work_order_no', 'work_order_embeddings', ['work_order_no'])

    # Create item_embeddings table
    op.create_table(
        'item_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),  # References work_order_item.id
        sa.Column('content', sa.Text(), nullable=False),  # The text that was embedded
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),  # Vector as array
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_item_embeddings_item_id', 'item_embeddings', ['item_id'])


def downgrade() -> None:
    """Drop RAG chatbot tables"""

    # Drop indexes and tables
    op.drop_index('ix_item_embeddings_item_id', table_name='item_embeddings')
    op.drop_table('item_embeddings')

    op.drop_index('ix_work_order_embeddings_work_order_no', table_name='work_order_embeddings')
    op.drop_table('work_order_embeddings')

    op.drop_index('ix_customer_embeddings_customer_id', table_name='customer_embeddings')
    op.drop_table('customer_embeddings')

    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index('ix_chat_sessions_updated_at', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_user_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')

    # Note: We don't drop the vector extension as it may be used by other tables
