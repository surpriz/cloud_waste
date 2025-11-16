"""add_inventory_scan_type

Add 'inventory' as a valid value for scans.scan_type column.
This allows differentiating between orphan scans (manual/scheduled) and
inventory scans (cost intelligence) to prevent interference between the two systems.

scan_type column already exists as VARCHAR(20), so no schema changes needed.
Valid values after this migration: 'manual', 'scheduled', 'inventory'

Revision ID: e69a1f8c1fa1
Revises: c3d4e5f6a7b8
Create Date: 2025-11-16 09:16:07.619988

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e69a1f8c1fa1'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add 'inventory' as a valid scan_type value.

    No database schema changes required - scan_type is VARCHAR(20).
    This migration documents the addition of 'inventory' as a valid value.
    """
    # No schema changes needed - scan_type column can already hold 'inventory'
    pass


def downgrade() -> None:
    """
    Remove 'inventory' scan_type value (conceptual downgrade only).

    Note: This won't delete existing inventory scans, but documents that
    'inventory' is no longer a supported scan_type value.
    """
    # No schema changes to revert
    pass
