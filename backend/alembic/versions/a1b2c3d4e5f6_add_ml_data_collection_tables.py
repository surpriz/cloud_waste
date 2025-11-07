"""add ml data collection tables

Revision ID: a1b2c3d4e5f6
Revises: da2ffc63d747
Create Date: 2025-11-07 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'da2ffc63d747'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all ML data collection tables."""

    # 1. Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('ml_data_collection_consent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ml_consent_date', sa.DateTime(), nullable=True),
        sa.Column('anonymized_industry', sa.String(length=50), nullable=True),
        sa.Column('anonymized_company_size', sa.String(length=20), nullable=True),
        sa.Column('email_scan_summaries', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_cost_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_marketing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('data_retention_years', sa.String(length=2), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_user_preferences_id'), 'user_preferences', ['id'], unique=False)
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=True)

    # 2. Create ml_training_data table
    op.create_table(
        'ml_training_data',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('region_anonymized', sa.String(length=20), nullable=False),
        sa.Column('resource_age_days', sa.Integer(), nullable=False),
        sa.Column('detection_scenario', sa.String(length=100), nullable=False),
        sa.Column('metrics_summary', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('cost_monthly', sa.Float(), nullable=False),
        sa.Column('confidence_level', sa.String(length=20), nullable=False),
        sa.Column('user_action', sa.String(length=30), nullable=True),
        sa.Column('resource_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ml_training_data_id'), 'ml_training_data', ['id'], unique=False)
    op.create_index(op.f('ix_ml_training_data_resource_type'), 'ml_training_data', ['resource_type'], unique=False)
    op.create_index(op.f('ix_ml_training_data_provider'), 'ml_training_data', ['provider'], unique=False)
    op.create_index(op.f('ix_ml_training_data_detection_scenario'), 'ml_training_data', ['detection_scenario'], unique=False)
    op.create_index(op.f('ix_ml_training_data_confidence_level'), 'ml_training_data', ['confidence_level'], unique=False)
    op.create_index(op.f('ix_ml_training_data_user_action'), 'ml_training_data', ['user_action'], unique=False)
    op.create_index(op.f('ix_ml_training_data_resource_age_days'), 'ml_training_data', ['resource_age_days'], unique=False)
    op.create_index(op.f('ix_ml_training_data_cost_monthly'), 'ml_training_data', ['cost_monthly'], unique=False)

    # 3. Create resource_lifecycle_events table
    op.create_table(
        'resource_lifecycle_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('resource_hash', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('region_anonymized', sa.String(length=20), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('age_at_event_days', sa.Integer(), nullable=False),
        sa.Column('cost_at_event', sa.Float(), nullable=False),
        sa.Column('metrics_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('event_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('event_timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_lifecycle_events_id'), 'resource_lifecycle_events', ['id'], unique=False)
    op.create_index(op.f('ix_resource_lifecycle_events_resource_hash'), 'resource_lifecycle_events', ['resource_hash'], unique=False)
    op.create_index(op.f('ix_resource_lifecycle_events_resource_type'), 'resource_lifecycle_events', ['resource_type'], unique=False)
    op.create_index(op.f('ix_resource_lifecycle_events_event_type'), 'resource_lifecycle_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_resource_lifecycle_events_event_timestamp'), 'resource_lifecycle_events', ['event_timestamp'], unique=False)

    # 4. Create cloudwatch_metrics_history table
    op.create_table(
        'cloudwatch_metrics_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('region_anonymized', sa.String(length=20), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_values', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('aggregation_period', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('collected_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cloudwatch_metrics_history_id'), 'cloudwatch_metrics_history', ['id'], unique=False)
    op.create_index(op.f('ix_cloudwatch_metrics_history_resource_type'), 'cloudwatch_metrics_history', ['resource_type'], unique=False)
    op.create_index(op.f('ix_cloudwatch_metrics_history_metric_name'), 'cloudwatch_metrics_history', ['metric_name'], unique=False)

    # 5. Create user_action_patterns table
    op.create_table(
        'user_action_patterns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_hash', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('detection_scenario', sa.String(length=100), nullable=False),
        sa.Column('confidence_level', sa.String(length=20), nullable=False),
        sa.Column('action_taken', sa.String(length=30), nullable=False),
        sa.Column('time_to_action_hours', sa.Integer(), nullable=False),
        sa.Column('cost_monthly', sa.Float(), nullable=False),
        sa.Column('cost_saved_monthly', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('industry_anonymized', sa.String(length=50), nullable=True),
        sa.Column('company_size_bucket', sa.String(length=20), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('action_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_action_patterns_id'), 'user_action_patterns', ['id'], unique=False)
    op.create_index(op.f('ix_user_action_patterns_user_hash'), 'user_action_patterns', ['user_hash'], unique=False)
    op.create_index(op.f('ix_user_action_patterns_resource_type'), 'user_action_patterns', ['resource_type'], unique=False)
    op.create_index(op.f('ix_user_action_patterns_detection_scenario'), 'user_action_patterns', ['detection_scenario'], unique=False)
    op.create_index(op.f('ix_user_action_patterns_action_taken'), 'user_action_patterns', ['action_taken'], unique=False)
    op.create_index(op.f('ix_user_action_patterns_industry_anonymized'), 'user_action_patterns', ['industry_anonymized'], unique=False)
    op.create_index(op.f('ix_user_action_patterns_company_size_bucket'), 'user_action_patterns', ['company_size_bucket'], unique=False)

    # 6. Create cost_trend_data table
    op.create_table(
        'cost_trend_data',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_hash', sa.String(length=64), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('total_spend', sa.Float(), nullable=False),
        sa.Column('waste_detected', sa.Float(), nullable=False),
        sa.Column('waste_eliminated', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('waste_percentage', sa.Float(), nullable=False),
        sa.Column('top_waste_categories', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('total_resources_scanned', sa.Float(), nullable=False),
        sa.Column('orphan_resources_found', sa.Float(), nullable=False),
        sa.Column('regional_breakdown', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('scan_count', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cost_trend_data_id'), 'cost_trend_data', ['id'], unique=False)
    op.create_index(op.f('ix_cost_trend_data_account_hash'), 'cost_trend_data', ['account_hash'], unique=False)
    op.create_index(op.f('ix_cost_trend_data_month'), 'cost_trend_data', ['month'], unique=False)
    op.create_index(op.f('ix_cost_trend_data_provider'), 'cost_trend_data', ['provider'], unique=False)


def downgrade() -> None:
    """Drop all ML data collection tables."""

    # Drop cost_trend_data table
    op.drop_index(op.f('ix_cost_trend_data_provider'), table_name='cost_trend_data')
    op.drop_index(op.f('ix_cost_trend_data_month'), table_name='cost_trend_data')
    op.drop_index(op.f('ix_cost_trend_data_account_hash'), table_name='cost_trend_data')
    op.drop_index(op.f('ix_cost_trend_data_id'), table_name='cost_trend_data')
    op.drop_table('cost_trend_data')

    # Drop user_action_patterns table
    op.drop_index(op.f('ix_user_action_patterns_company_size_bucket'), table_name='user_action_patterns')
    op.drop_index(op.f('ix_user_action_patterns_industry_anonymized'), table_name='user_action_patterns')
    op.drop_index(op.f('ix_user_action_patterns_action_taken'), table_name='user_action_patterns')
    op.drop_index(op.f('ix_user_action_patterns_detection_scenario'), table_name='user_action_patterns')
    op.drop_index(op.f('ix_user_action_patterns_resource_type'), table_name='user_action_patterns')
    op.drop_index(op.f('ix_user_action_patterns_user_hash'), table_name='user_action_patterns')
    op.drop_index(op.f('ix_user_action_patterns_id'), table_name='user_action_patterns')
    op.drop_table('user_action_patterns')

    # Drop cloudwatch_metrics_history table
    op.drop_index(op.f('ix_cloudwatch_metrics_history_metric_name'), table_name='cloudwatch_metrics_history')
    op.drop_index(op.f('ix_cloudwatch_metrics_history_resource_type'), table_name='cloudwatch_metrics_history')
    op.drop_index(op.f('ix_cloudwatch_metrics_history_id'), table_name='cloudwatch_metrics_history')
    op.drop_table('cloudwatch_metrics_history')

    # Drop resource_lifecycle_events table
    op.drop_index(op.f('ix_resource_lifecycle_events_event_timestamp'), table_name='resource_lifecycle_events')
    op.drop_index(op.f('ix_resource_lifecycle_events_event_type'), table_name='resource_lifecycle_events')
    op.drop_index(op.f('ix_resource_lifecycle_events_resource_type'), table_name='resource_lifecycle_events')
    op.drop_index(op.f('ix_resource_lifecycle_events_resource_hash'), table_name='resource_lifecycle_events')
    op.drop_index(op.f('ix_resource_lifecycle_events_id'), table_name='resource_lifecycle_events')
    op.drop_table('resource_lifecycle_events')

    # Drop ml_training_data table
    op.drop_index(op.f('ix_ml_training_data_cost_monthly'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_resource_age_days'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_user_action'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_confidence_level'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_detection_scenario'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_provider'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_resource_type'), table_name='ml_training_data')
    op.drop_index(op.f('ix_ml_training_data_id'), table_name='ml_training_data')
    op.drop_table('ml_training_data')

    # Drop user_preferences table
    op.drop_index(op.f('ix_user_preferences_user_id'), table_name='user_preferences')
    op.drop_index(op.f('ix_user_preferences_id'), table_name='user_preferences')
    op.drop_table('user_preferences')
