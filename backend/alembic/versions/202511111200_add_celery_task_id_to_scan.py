"""Add celery_task_id to Scan model for progress tracking

Revision ID: add_celery_task_id
Revises: f9e2c8d4a1b3
Create Date: 2025-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_celery_task_id'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add celery_task_id column to scans table."""
    op.add_column('scans', sa.Column('celery_task_id', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_scans_celery_task_id'), 'scans', ['celery_task_id'], unique=False)


def downgrade() -> None:
    """Remove celery_task_id column from scans table."""
    op.drop_index(op.f('ix_scans_celery_task_id'), table_name='scans')
    op.drop_column('scans', 'celery_task_id')
