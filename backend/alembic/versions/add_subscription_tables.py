"""add_subscription_tables

Revision ID: 001_add_subscriptions
Revises: cb0146578cde
Create Date: 2025-11-26 21:00:00.000000

"""
from typing import Sequence, Union
from decimal import Decimal
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_add_subscriptions'
down_revision: Union[str, None] = 'cb0146578cde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create subscription_plans table
    op.create_table(
        'subscription_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR'),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=True),
        sa.Column('max_scans_per_month', sa.Integer(), nullable=True),
        sa.Column('max_cloud_accounts', sa.Integer(), nullable=True),
        sa.Column('has_ai_chat', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('has_impact_tracking', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('has_email_notifications', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('has_api_access', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('has_priority_support', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(op.f('ix_subscription_plans_id'), 'subscription_plans', ['id'], unique=False)

    # Create user_subscriptions table
    op.create_table(
        'user_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True, unique=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('scans_used_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_scan_reset_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ondelete='RESTRICT'),
    )
    op.create_index(op.f('ix_user_subscriptions_id'), 'user_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_user_subscriptions_user_id'), 'user_subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_subscriptions_plan_id'), 'user_subscriptions', ['plan_id'], unique=False)
    op.create_index(op.f('ix_user_subscriptions_stripe_subscription_id'), 'user_subscriptions', ['stripe_subscription_id'], unique=False)
    op.create_index(op.f('ix_user_subscriptions_stripe_customer_id'), 'user_subscriptions', ['stripe_customer_id'], unique=False)

    # Add stripe_customer_id column to users table
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_stripe_customer_id'), 'users', ['stripe_customer_id'], unique=False)

    # Insert default subscription plans
    plans_table = sa.table(
        'subscription_plans',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.Text),
        sa.column('price_monthly', sa.Numeric),
        sa.column('currency', sa.String),
        sa.column('stripe_price_id', sa.String),
        sa.column('max_scans_per_month', sa.Integer),
        sa.column('max_cloud_accounts', sa.Integer),
        sa.column('has_ai_chat', sa.Boolean),
        sa.column('has_impact_tracking', sa.Boolean),
        sa.column('has_email_notifications', sa.Boolean),
        sa.column('has_api_access', sa.Boolean),
        sa.column('has_priority_support', sa.Boolean),
        sa.column('is_active', sa.Boolean),
    )

    op.bulk_insert(
        plans_table,
        [
            {
                'id': uuid.uuid4(),
                'name': 'free',
                'display_name': 'Free',
                'description': 'Get started with basic cloud waste detection',
                'price_monthly': Decimal('0.00'),
                'currency': 'EUR',
                'stripe_price_id': None,
                'max_scans_per_month': 5,
                'max_cloud_accounts': 1,
                'has_ai_chat': False,
                'has_impact_tracking': False,
                'has_email_notifications': False,
                'has_api_access': False,
                'has_priority_support': False,
                'is_active': True,
            },
            {
                'id': uuid.uuid4(),
                'name': 'pro',
                'display_name': 'Pro',
                'description': 'Advanced features for growing teams',
                'price_monthly': Decimal('29.00'),
                'currency': 'EUR',
                'stripe_price_id': None,  # To be updated with actual Stripe Price ID
                'max_scans_per_month': 50,
                'max_cloud_accounts': 5,
                'has_ai_chat': True,
                'has_impact_tracking': True,
                'has_email_notifications': True,
                'has_api_access': False,
                'has_priority_support': False,
                'is_active': True,
            },
            {
                'id': uuid.uuid4(),
                'name': 'enterprise',
                'display_name': 'Enterprise',
                'description': 'Unlimited resources and priority support',
                'price_monthly': Decimal('99.00'),
                'currency': 'EUR',
                'stripe_price_id': None,  # To be updated with actual Stripe Price ID
                'max_scans_per_month': None,  # Unlimited
                'max_cloud_accounts': None,  # Unlimited
                'has_ai_chat': True,
                'has_impact_tracking': True,
                'has_email_notifications': True,
                'has_api_access': True,
                'has_priority_support': True,
                'is_active': True,
            },
        ]
    )


def downgrade() -> None:
    # Drop stripe_customer_id from users table
    op.drop_index(op.f('ix_users_stripe_customer_id'), table_name='users')
    op.drop_column('users', 'stripe_customer_id')

    # Drop user_subscriptions table
    op.drop_index(op.f('ix_user_subscriptions_stripe_customer_id'), table_name='user_subscriptions')
    op.drop_index(op.f('ix_user_subscriptions_stripe_subscription_id'), table_name='user_subscriptions')
    op.drop_index(op.f('ix_user_subscriptions_plan_id'), table_name='user_subscriptions')
    op.drop_index(op.f('ix_user_subscriptions_user_id'), table_name='user_subscriptions')
    op.drop_index(op.f('ix_user_subscriptions_id'), table_name='user_subscriptions')
    op.drop_table('user_subscriptions')

    # Drop subscription_plans table
    op.drop_index(op.f('ix_subscription_plans_id'), table_name='subscription_plans')
    op.drop_table('subscription_plans')
