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
    # Add VM Phase A detection rules for Azure Virtual Machine waste scenarios

    # Rule 1: VMs Deallocated (Stopped) for Extended Period
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('virtual_machine_deallocated', '{"enabled": true, "min_stopped_days": 30, "description": "Azure VMs that have been deallocated (stopped) for extended periods (>30 days). While deallocated VMs do not incur compute charges, their attached disks continue to generate costs."}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)

    # Rule 2: VMs Stopped but NOT Deallocated (CRITICAL)
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('virtual_machine_stopped_not_deallocated', '{"enabled": true, "min_stopped_days": 7, "description": "CRITICAL: Azure VMs in stopped state but NOT deallocated continue to incur FULL compute charges even while not running. This is a high-priority cost optimization opportunity."}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)

    # Rule 3: VMs Created but Never Started
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('virtual_machine_never_started', '{"enabled": true, "min_age_days": 7, "description": "Azure VMs that have been provisioned but never started. These may be provisioning errors, forgotten test resources, or orphaned instances from failed deployments."}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)

    # Rule 4: VMs Oversized with Premium Disks
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('virtual_machine_oversized_premium', '{"enabled": true, "min_vcpus": 8, "disk_tier": "Premium_LRS", "description": "Azure VMs with excessive CPU cores (>8 vCPUs) and Premium_LRS managed disks. Potential cost optimization by downsizing VM or switching to Standard_LRS disks."}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)

    # Rule 5: VMs Missing Required Governance Tags (Orphaned)
    op.execute("""
        INSERT INTO detection_rules (resource_type, rules, created_at, updated_at)
        VALUES ('virtual_machine_untagged_orphan', '{"enabled": true, "required_tags": ["owner", "team"], "min_age_days": 30, "description": "Azure VMs missing required governance tags (owner, team) and older than 30 days. These may be orphaned resources with unclear ownership and cost accountability."}', NOW(), NOW())
        ON CONFLICT (resource_type) DO UPDATE
        SET rules = EXCLUDED.rules, updated_at = NOW();
    """)


def downgrade() -> None:
    # Remove VM Phase A detection rules
    op.execute("""
        DELETE FROM detection_rules WHERE resource_type IN (
            'virtual_machine_deallocated',
            'virtual_machine_stopped_not_deallocated',
            'virtual_machine_never_started',
            'virtual_machine_oversized_premium',
            'virtual_machine_untagged_orphan'
        );
    """)
