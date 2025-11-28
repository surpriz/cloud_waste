#!/usr/bin/env python3
"""
Database migration script: Create free subscriptions for existing users.

This script finds all users without an active subscription and creates
a free subscription for them. This is needed after implementing the
Stripe subscription system to ensure all existing users have subscriptions.

Usage:
    python scripts/migrate_user_subscriptions.py [--dry-run]

Options:
    --dry-run    Show what would be done without making changes
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.models.user_subscription import UserSubscription


async def migrate_user_subscriptions(dry_run: bool = False):
    """Create free subscriptions for all users without subscriptions."""

    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )

    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            print("=" * 60)
            print("🔄 User Subscription Migration Script")
            print("=" * 60)

            # Get free plan
            result = await session.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.name == "free",
                    SubscriptionPlan.is_active == True,
                )
            )
            free_plan = result.scalar_one_or_none()

            if not free_plan:
                print("❌ ERROR: Free subscription plan not found in database!")
                print("   Please ensure the free plan exists before running this script.")
                return 1

            print(f"✅ Found free plan: {free_plan.display_name}")
            print(f"   - ID: {free_plan.id}")
            print(f"   - Max scans/month: {free_plan.max_scans_per_month}")
            print(f"   - Max cloud accounts: {free_plan.max_cloud_accounts}")
            print()

            # Get all users
            result = await session.execute(select(User))
            all_users = result.scalars().all()
            print(f"📊 Total users in database: {len(all_users)}")
            print()

            # Find users without active subscriptions
            users_without_subscription = []

            for user in all_users:
                result = await session.execute(
                    select(UserSubscription).where(
                        UserSubscription.user_id == user.id,
                        UserSubscription.status == "active",
                    )
                )
                subscription = result.scalar_one_or_none()

                if not subscription:
                    users_without_subscription.append(user)

            if not users_without_subscription:
                print("✅ All users already have active subscriptions!")
                print("   No migration needed.")
                return 0

            print(f"⚠️  Found {len(users_without_subscription)} users without subscriptions:")
            print()

            # Create subscriptions
            created_count = 0
            for user in users_without_subscription:
                print(f"  - {user.email} (ID: {user.id})")

                if not dry_run:
                    # Create free subscription
                    subscription = UserSubscription(
                        user_id=user.id,
                        plan_id=free_plan.id,
                        status="active",
                        current_period_start=datetime.utcnow(),
                        current_period_end=None,  # Free plan never expires
                        scans_used_this_month=0,
                        last_scan_reset_at=datetime.utcnow(),
                    )
                    session.add(subscription)
                    created_count += 1

            print()

            if dry_run:
                print("🔍 DRY RUN MODE - No changes were made")
                print(f"   Would create {len(users_without_subscription)} free subscriptions")
            else:
                # Commit changes
                await session.commit()
                print("=" * 60)
                print(f"✅ Successfully created {created_count} free subscriptions!")
                print("=" * 60)

            return 0

        except Exception as e:
            print()
            print("=" * 60)
            print(f"❌ ERROR during migration: {e}")
            print("=" * 60)
            await session.rollback()
            return 1

        finally:
            await session.close()
            await engine.dispose()


if __name__ == "__main__":
    # Check for --dry-run flag
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print()
        print("🔍 Running in DRY RUN mode - no changes will be made")
        print()

    # Run migration
    exit_code = asyncio.run(migrate_user_subscriptions(dry_run=dry_run))
    sys.exit(exit_code)
