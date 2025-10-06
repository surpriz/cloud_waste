"""add_attached_volume_detection_rules

Revision ID: 8bfa51fe1573
Revises: 4841b81d124e
Create Date: 2025-10-06 14:40:46.615833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bfa51fe1573'
down_revision: Union[str, None] = '4841b81d124e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Update existing EBS volume detection rules to include:
    - detect_attached_unused: true
    - min_idle_days_attached: 30
    """
    # Update all existing ebs_volume detection rules
    op.execute("""
        UPDATE detection_rules
        SET rules = jsonb_set(
            jsonb_set(
                rules,
                '{detect_attached_unused}',
                'true'::jsonb,
                true
            ),
            '{min_idle_days_attached}',
            '30'::jsonb,
            true
        ),
        updated_at = NOW()
        WHERE resource_type = 'ebs_volume'
        AND (
            rules->>'detect_attached_unused' IS NULL
            OR rules->>'min_idle_days_attached' IS NULL
        );
    """)


def downgrade() -> None:
    """
    Remove attached volume detection from EBS volume rules.
    """
    op.execute("""
        UPDATE detection_rules
        SET rules = rules - 'detect_attached_unused' - 'min_idle_days_attached',
        updated_at = NOW()
        WHERE resource_type = 'ebs_volume';
    """)
