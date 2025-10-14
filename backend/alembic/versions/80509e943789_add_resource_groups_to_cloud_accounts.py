"""Add resource_groups to cloud_accounts

Revision ID: 80509e943789
Revises: 5a7f3b9c2e4d
Create Date: 2025-10-14 12:45:34.542749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80509e943789'
down_revision: Union[str, None] = '5a7f3b9c2e4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add resource_groups JSON column to cloud_accounts table
    op.add_column('cloud_accounts', sa.Column('resource_groups', sa.dialects.postgresql.JSON(), nullable=True))


def downgrade() -> None:
    # Remove resource_groups column
    op.drop_column('cloud_accounts', 'resource_groups')
