"""add_azure_public_ip_detection_rule

Revision ID: 0b5aea06d0d5
Revises: 8bfa51fe1573
Create Date: 2025-10-11 20:39:08.617125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b5aea06d0d5'
down_revision: Union[str, None] = '8bfa51fe1573'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: This migration was designed to add global detection rules, but detection_rules
    # table is user-specific (has user_id foreign key). This migration is kept for history
    # but does nothing, as default detection rules are now managed by the application code.
    pass


def downgrade() -> None:
    # See upgrade() - this migration is a no-op
    pass
