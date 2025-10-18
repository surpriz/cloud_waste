"""add_phase1_detection_rules_azure

Revision ID: 4766abf4c8b9
Revises: 0b5aea06d0d5
Create Date: 2025-10-11 21:19:24.663892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4766abf4c8b9'
down_revision: Union[str, None] = '0b5aea06d0d5'
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
