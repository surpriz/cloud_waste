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

    This migration adds default detection rules for Microsoft 365 resource types
    (SharePoint sites and OneDrive drives).

    Note: The cloud_accounts table already supports any provider string via VARCHAR(50).
    No schema changes are required. This migration is for documentation and default rules.
    """
    # Add default detection rules for Microsoft 365 SharePoint sites
    op.execute("""
        INSERT INTO detection_rules (id, user_id, resource_type, rules, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            NULL,
            'sharepoint_sites',
            '{
                "large_files_unused": {"enabled": true, "min_file_size_mb": 100, "min_age_days": 180},
                "duplicate_files": {"enabled": true},
                "sites_abandoned": {"enabled": true, "min_inactive_days": 90},
                "excessive_versions": {"enabled": true, "max_versions_threshold": 50},
                "recycle_bin_old": {"enabled": true, "max_retention_days": 30}
            }'::jsonb,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM detection_rules WHERE resource_type = 'sharepoint_sites' AND user_id IS NULL
        );
    """)

    # Add default detection rules for Microsoft 365 OneDrive drives
    op.execute("""
        INSERT INTO detection_rules (id, user_id, resource_type, rules, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            NULL,
            'onedrive_drives',
            '{
                "large_files_unused": {"enabled": true, "min_file_size_mb": 100, "min_age_days": 180},
                "disabled_users": {"enabled": true, "retention_days": 93},
                "temp_files_accumulated": {"enabled": true, "min_age_days": 7, "file_patterns": [".tmp", "~$", ".bak", ".swp"]},
                "excessive_sharing": {"enabled": true, "min_age_days": 90},
                "duplicate_attachments": {"enabled": true}
            }'::jsonb,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM detection_rules WHERE resource_type = 'onedrive_drives' AND user_id IS NULL
        );
    """)


def downgrade() -> None:
    """
    Remove Microsoft 365 provider support.

    This removes the default detection rules for Microsoft 365 resource types.
    """
    # Remove default detection rules for Microsoft 365
    op.execute("""
        DELETE FROM detection_rules
        WHERE resource_type IN ('sharepoint_sites', 'onedrive_drives')
        AND user_id IS NULL;
    """)
