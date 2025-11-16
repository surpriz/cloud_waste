"""add all_cloud_resources table for cost intelligence

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all_cloud_resources table for cost intelligence."""

    op.create_table(
        'all_cloud_resources',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cloud_account_id', sa.UUID(), nullable=False),
        sa.Column('scan_id', sa.UUID(), nullable=False),
        # Resource identification
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=False),
        sa.Column('resource_name', sa.String(length=255), nullable=True),
        sa.Column('region', sa.String(length=50), nullable=False),
        # Cost information
        sa.Column('estimated_monthly_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        # Utilization metrics
        sa.Column('utilization_status', sa.String(length=20), nullable=False, server_default='unknown'),
        sa.Column('cpu_utilization_percent', sa.Float(), nullable=True),
        sa.Column('memory_utilization_percent', sa.Float(), nullable=True),
        sa.Column('storage_utilization_percent', sa.Float(), nullable=True),
        sa.Column('network_utilization_mbps', sa.Float(), nullable=True),
        # Optimization recommendations
        sa.Column('is_optimizable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('optimization_priority', sa.String(length=20), nullable=False, server_default='none'),
        sa.Column('optimization_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('potential_monthly_savings', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('optimization_recommendations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        # Resource metadata
        sa.Column('resource_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        # Status tracking
        sa.Column('resource_status', sa.String(length=50), nullable=True),
        sa.Column('is_orphan', sa.Boolean(), nullable=False, server_default='false'),
        # Timestamps
        sa.Column('created_at_cloud', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        # Foreign keys
        sa.ForeignKeyConstraint(['cloud_account_id'], ['cloud_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient querying
    op.create_index(op.f('ix_all_cloud_resources_id'), 'all_cloud_resources', ['id'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_cloud_account_id'), 'all_cloud_resources', ['cloud_account_id'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_scan_id'), 'all_cloud_resources', ['scan_id'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_resource_type'), 'all_cloud_resources', ['resource_type'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_resource_id'), 'all_cloud_resources', ['resource_id'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_region'), 'all_cloud_resources', ['region'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_estimated_monthly_cost'), 'all_cloud_resources', ['estimated_monthly_cost'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_utilization_status'), 'all_cloud_resources', ['utilization_status'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_is_optimizable'), 'all_cloud_resources', ['is_optimizable'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_optimization_priority'), 'all_cloud_resources', ['optimization_priority'], unique=False)
    op.create_index(op.f('ix_all_cloud_resources_is_orphan'), 'all_cloud_resources', ['is_orphan'], unique=False)


def downgrade() -> None:
    """Drop all_cloud_resources table."""

    op.drop_index(op.f('ix_all_cloud_resources_is_orphan'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_optimization_priority'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_is_optimizable'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_utilization_status'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_estimated_monthly_cost'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_region'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_resource_id'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_resource_type'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_scan_id'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_cloud_account_id'), table_name='all_cloud_resources')
    op.drop_index(op.f('ix_all_cloud_resources_id'), table_name='all_cloud_resources')
    op.drop_table('all_cloud_resources')
