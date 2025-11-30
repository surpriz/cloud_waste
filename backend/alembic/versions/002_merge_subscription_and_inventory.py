"""merge subscription and inventory heads

Merges two parallel migration branches:
- 001_add_subscriptions (Stripe subscription tables)
- e69a1f8c1fa1 (inventory scan type)

Both branches were created independently, creating multiple heads.
This merge migration resolves the conflict.

Revision ID: 002_merge_heads
Revises: 001_add_subscriptions, e69a1f8c1fa1
Create Date: 2025-11-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_merge_heads'
down_revision: Union[str, None] = ('001_add_subscriptions', 'e69a1f8c1fa1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge two migration branches - no schema changes needed."""
    pass


def downgrade() -> None:
    """Merge downgrade - no schema changes needed."""
    pass
