"""Merge heads: add_celery_task_id and b2c3d4e5f6a7

Revision ID: c3d4e5f6a7b8
Revises: add_celery_task_id, b2c3d4e5f6a7
Create Date: 2025-01-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = ('add_celery_task_id', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge two migration branches - no schema changes needed."""
    pass


def downgrade() -> None:
    """Merge downgrade - no schema changes needed."""
    pass
