"""add_vm_phase_a_detection_rules_azure

Revision ID: 5a7f3b9c2e4d
Revises: 4766abf4c8b9
Create Date: 2025-10-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a7f3b9c2e4d'
down_revision: Union[str, None] = '4766abf4c8b9'
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
