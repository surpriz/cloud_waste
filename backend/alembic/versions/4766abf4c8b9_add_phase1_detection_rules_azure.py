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
    # Add Phase 1 detection rules for Azure waste scenarios

    # Rule 1: Managed Disks on Stopped VMs
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('managed_disk_on_stopped_vm', '{"enabled": true, "min_stopped_days": 30, "description": "Managed disks attached to VMs that have been deallocated (stopped) for extended periods"}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)

    # Rule 2: Orphaned Disk Snapshots
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('disk_snapshot_orphaned', '{"enabled": true, "min_age_days": 90, "description": "Disk snapshots whose source disks have been deleted"}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)

    # Rule 3: Public IPs on Stopped Resources
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('public_ip_on_stopped_resource', '{"enabled": true, "min_stopped_days": 30, "description": "Public IP addresses associated to stopped VMs or inactive load balancers"}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)


def downgrade() -> None:
    # Remove Phase 1 detection rules
    op.execute("""
        DELETE FROM detection_rules WHERE resource_type IN (
            'managed_disk_on_stopped_vm',
            'disk_snapshot_orphaned',
            'public_ip_on_stopped_resource'
        );
    """)
