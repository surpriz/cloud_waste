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
    # Add default detection rule for Azure Public IP (Unassociated)
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('public_ip_unassociated', '{"enabled": true, "min_age_days": 7}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)


def downgrade() -> None:
    # Remove Azure Public IP detection rule
    op.execute("""
        DELETE FROM detection_rules WHERE resource_type = 'public_ip_unassociated';
    """)
