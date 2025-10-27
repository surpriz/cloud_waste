"""add_email_verification_fields

Revision ID: cb0146578cde
Revises: f9e2c8d4a1b3
Create Date: 2025-10-27 18:58:57.386928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb0146578cde'
down_revision: Union[str, None] = 'f9e2c8d4a1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email_verified column (default False for existing users)
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Add email_verification_token column (nullable)
    op.add_column('users', sa.Column('email_verification_token', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_email_verification_token'), 'users', ['email_verification_token'], unique=False)

    # Add verification_token_expires_at column (nullable)
    op.add_column('users', sa.Column('verification_token_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Drop columns in reverse order
    op.drop_column('users', 'verification_token_expires_at')
    op.drop_index(op.f('ix_users_email_verification_token'), table_name='users')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
