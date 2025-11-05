"""fix_user_id_autoincrement_and_constraints

Revision ID: f2238738a091
Revises: 3457f357de30
Create Date: 2025-11-05 17:19:17.474836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2238738a091'
down_revision: Union[str, None] = '3457f357de30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix User table:
    # 1. Create a sequence for the id column
    # 2. Change id from BIGINT to INTEGER with auto-increment
    # 3. Set NOT NULL constraints on id, username, email

    # Create sequence for user.id
    op.execute("CREATE SEQUENCE IF NOT EXISTS user_id_seq")

    # Set the sequence to start from the next available ID
    op.execute("""
        SELECT setval('user_id_seq',
            COALESCE((SELECT MAX(id) FROM "user"), 0) + 1,
            false)
    """)

    # Alter the id column to use the sequence and be NOT NULL
    op.execute('ALTER TABLE "user" ALTER COLUMN id SET NOT NULL')
    op.execute('ALTER TABLE "user" ALTER COLUMN id SET DEFAULT nextval(\'user_id_seq\')')
    op.execute('ALTER SEQUENCE user_id_seq OWNED BY "user".id')

    # Fix other columns to match model constraints
    op.execute('ALTER TABLE "user" ALTER COLUMN username SET NOT NULL')
    op.execute('ALTER TABLE "user" ALTER COLUMN email SET NOT NULL')


def downgrade() -> None:
    # Revert changes
    op.execute('ALTER TABLE "user" ALTER COLUMN id DROP DEFAULT')
    op.execute('DROP SEQUENCE IF EXISTS user_id_seq')
    op.execute('ALTER TABLE "user" ALTER COLUMN id DROP NOT NULL')
    op.execute('ALTER TABLE "user" ALTER COLUMN username DROP NOT NULL')
    op.execute('ALTER TABLE "user" ALTER COLUMN email DROP NOT NULL')
