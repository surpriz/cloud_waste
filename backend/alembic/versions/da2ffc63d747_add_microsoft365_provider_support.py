"""add_microsoft365_provider_support

Revision ID: da2ffc63d747
Revises: 4e275083c57b
Create Date: 2025-11-02 10:38:20.129371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da2ffc63d747'
down_revision: Union[str, None] = '4e275083c57b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add support for Microsoft 365 provider.

    Note: The cloud_accounts table already supports any provider string via VARCHAR(50).
    No schema changes are required. This is a placeholder migration for tracking
    MS365 provider support in the migration history.

    Default detection rules for MS365 resource types (sharepoint_sites, onedrive_drives)
    are applied per-user when they create an MS365 account.
    """
    # No database changes needed - MS365 uses existing schema
    pass


def downgrade() -> None:
    """
    Remove Microsoft 365 provider support.

    No database changes to revert - MS365 uses existing schema.
    """
    # No database changes to revert
    pass
