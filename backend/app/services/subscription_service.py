"""Subscription service for Stripe integration."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.models.user_subscription import UserSubscription

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionService:
    """Service for managing user subscriptions and Stripe integration."""

    def __init__(self, db: AsyncSession):
        """Initialize subscription service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_plan_by_name(self, plan_name: str) -> Optional[SubscriptionPlan]:
        """Get subscription plan by name.

        Args:
            plan_name: Plan name ('free', 'pro', 'enterprise')

        Returns:
            SubscriptionPlan if found, None otherwise
        """
        result = await self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.name == plan_name,
                SubscriptionPlan.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_active_plans(self) -> list[SubscriptionPlan]:
        """Get all active subscription plans.

        Returns:
            List of active subscription plans
        """
        result = await self.db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active == True)
            .order_by(SubscriptionPlan.price_monthly)
        )
        return list(result.scalars().all())

    async def get_user_subscription(self, user_id: UUID) -> Optional[UserSubscription]:
        """Get user's active subscription.

        Args:
            user_id: User ID

        Returns:
            UserSubscription if found, None otherwise
        """
        result = await self.db.execute(
            select(UserSubscription)
            .options(selectinload(UserSubscription.plan))
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_user_subscription(
        self, user_id: UUID
    ) -> UserSubscription:
        """Get user's active subscription or create free subscription if none exists.

        This method ensures all users always have a valid subscription.
        New users or users without a subscription get a free plan automatically.

        Args:
            user_id: User ID

        Returns:
            UserSubscription (existing or newly created free subscription)

        Raises:
            ValueError: If free plan not found in database
        """
        # Try to get existing subscription
        subscription = await self.get_user_subscription(user_id)

        # If no subscription exists, create a free one
        if not subscription:
            logger.info(f"No subscription found for user {user_id}, creating free subscription")
            subscription = await self.create_free_subscription(user_id)

        return subscription

    async def create_free_subscription(
        self, user_id: UUID
    ) -> UserSubscription:
        """Create free subscription for new user.

        Args:
            user_id: User ID

        Returns:
            Created UserSubscription
        """
        free_plan = await self.get_plan_by_name("free")
        if not free_plan:
            raise ValueError("Free plan not found in database")

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=free_plan.id,
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=None,  # Free plan never expires
            scans_used_this_month=0,
            last_scan_reset_at=datetime.utcnow(),
        )

        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        logger.info(f"Created free subscription for user {user_id}")
        return subscription

    async def create_checkout_session(
        self,
        user: User,
        plan_name: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """Create Stripe Checkout Session for subscription purchase.

        Args:
            user: User object
            plan_name: Plan name ('pro' or 'enterprise')
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if user cancels

        Returns:
            Dict with checkout session details (id, url)

        Raises:
            ValueError: If plan is invalid or free
        """
        plan = await self.get_plan_by_name(plan_name)
        if not plan:
            raise ValueError(f"Plan '{plan_name}' not found")

        if plan.name == "free":
            raise ValueError("Cannot create checkout session for free plan")

        if not plan.stripe_price_id:
            raise ValueError(f"Stripe Price ID not configured for plan '{plan_name}'")

        # Create or retrieve Stripe customer
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={"user_id": str(user.id)},
            )
            user.stripe_customer_id = customer.id
            await self.db.commit()
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
        else:
            customer_id = user.stripe_customer_id

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "plan_id": str(plan.id),
                "plan_name": plan.name,
            },
        )

        logger.info(
            f"Created checkout session {checkout_session.id} for user {user.id}, plan {plan_name}"
        )

        return {
            "id": checkout_session.id,
            "url": checkout_session.url,
        }

    async def create_portal_session(
        self, user: User, return_url: str
    ) -> dict:
        """Create Stripe Customer Portal Session.

        Args:
            user: User object
            return_url: URL to return to after portal session

        Returns:
            Dict with portal session details (url)

        Raises:
            ValueError: If user has no Stripe customer ID
        """
        if not user.stripe_customer_id:
            raise ValueError("User has no Stripe customer ID")

        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )

        logger.info(f"Created portal session for user {user.id}")

        return {"url": portal_session.url}

    async def handle_checkout_completed(
        self, checkout_session: dict
    ) -> None:
        """Handle successful checkout completion webhook.

        Args:
            checkout_session: Stripe checkout.session.completed event data
        """
        user_id = UUID(checkout_session["metadata"]["user_id"])
        plan_id = UUID(checkout_session["metadata"]["plan_id"])
        stripe_subscription_id = checkout_session["subscription"]
        stripe_customer_id = checkout_session["customer"]

        # Get Stripe subscription details
        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)

        # Cancel existing subscription if any
        existing_subscription = await self.get_user_subscription(user_id)
        if existing_subscription:
            existing_subscription.status = "canceled"
            existing_subscription.canceled_at = datetime.utcnow()

        # Create new subscription
        new_subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            status=stripe_subscription["status"],
            current_period_start=datetime.fromtimestamp(
                stripe_subscription["current_period_start"]
            ),
            current_period_end=datetime.fromtimestamp(
                stripe_subscription["current_period_end"]
            ),
            cancel_at_period_end=stripe_subscription["cancel_at_period_end"],
            scans_used_this_month=0,
            last_scan_reset_at=datetime.utcnow(),
        )

        self.db.add(new_subscription)
        await self.db.commit()

        logger.info(
            f"Created subscription {stripe_subscription_id} for user {user_id}"
        )

    async def handle_subscription_updated(
        self, stripe_subscription: dict
    ) -> None:
        """Handle subscription update webhook.

        Args:
            stripe_subscription: Stripe customer.subscription.updated event data
        """
        result = await self.db.execute(
            select(UserSubscription).where(
                UserSubscription.stripe_subscription_id
                == stripe_subscription["id"]
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(
                f"Subscription {stripe_subscription['id']} not found in database"
            )
            return

        # Update status
        subscription.status = stripe_subscription["status"]

        # Update period dates only if present (Stripe sometimes omits these during cancellations)
        if "current_period_start" in stripe_subscription:
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription["current_period_start"]
            )
        if "current_period_end" in stripe_subscription:
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription["current_period_end"]
            )

        # Update cancellation flag
        subscription.cancel_at_period_end = stripe_subscription.get(
            "cancel_at_period_end", False
        )

        await self.db.commit()

        logger.info(
            f"Updated subscription {stripe_subscription['id']} status to {stripe_subscription['status']}, cancel_at_period_end={subscription.cancel_at_period_end}"
        )

    async def handle_subscription_deleted(
        self, stripe_subscription: dict
    ) -> None:
        """Handle subscription deletion webhook.

        Args:
            stripe_subscription: Stripe customer.subscription.deleted event data
        """
        result = await self.db.execute(
            select(UserSubscription).where(
                UserSubscription.stripe_subscription_id
                == stripe_subscription["id"]
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(
                f"Subscription {stripe_subscription['id']} not found in database"
            )
            return

        subscription.status = "canceled"
        subscription.canceled_at = datetime.utcnow()

        # Downgrade to free plan
        free_plan = await self.get_plan_by_name("free")
        if free_plan:
            await self.create_free_subscription(subscription.user_id)

        await self.db.commit()

        logger.info(
            f"Canceled subscription {stripe_subscription['id']} and downgraded to free"
        )

    async def check_scan_limit(self, user_id: UUID) -> tuple[bool, Optional[str]]:
        """Check if user can perform a scan based on their subscription.

        Args:
            user_id: User ID

        Returns:
            Tuple of (can_scan: bool, error_message: Optional[str])
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False, "No active subscription found"

        plan = subscription.plan

        # Check if scan limit is unlimited
        if plan.max_scans_per_month is None:
            return True, None

        # Reset monthly counter if needed
        now = datetime.utcnow()
        if (
            subscription.last_scan_reset_at is None
            or (now - subscription.last_scan_reset_at).days >= 30
        ):
            subscription.scans_used_this_month = 0
            subscription.last_scan_reset_at = now
            await self.db.commit()

        # Check if limit exceeded
        if subscription.scans_used_this_month >= plan.max_scans_per_month:
            return (
                False,
                f"Monthly scan limit reached ({plan.max_scans_per_month} scans). "
                f"Upgrade to {plan.name == 'free' and 'Pro' or 'Enterprise'} for more scans.",
            )

        return True, None

    async def increment_scan_usage(self, user_id: UUID) -> None:
        """Increment scan usage counter for user.

        Args:
            user_id: User ID
        """
        subscription = await self.get_user_subscription(user_id)
        if subscription:
            subscription.scans_used_this_month += 1
            await self.db.commit()
            logger.debug(
                f"Incremented scan usage for user {user_id}: {subscription.scans_used_this_month}"
            )

    async def check_cloud_account_limit(self, user_id: UUID) -> tuple[bool, Optional[str]]:
        """Check if user can add more cloud accounts.

        Args:
            user_id: User ID

        Returns:
            Tuple of (can_add: bool, error_message: Optional[str])
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False, "No active subscription found"

        plan = subscription.plan

        # Check if cloud account limit is unlimited
        if plan.max_cloud_accounts is None:
            return True, None

        # Count existing cloud accounts
        from app.models.cloud_account import CloudAccount

        result = await self.db.execute(
            select(CloudAccount).where(CloudAccount.user_id == user_id)
        )
        account_count = len(list(result.scalars().all()))

        if account_count >= plan.max_cloud_accounts:
            return (
                False,
                f"Cloud account limit reached ({plan.max_cloud_accounts} accounts). "
                f"Upgrade to {plan.name == 'free' and 'Pro' or 'Enterprise'} for more accounts.",
            )

        return True, None

    async def check_feature_access(
        self, user_id: UUID, feature: str
    ) -> tuple[bool, Optional[str]]:
        """Check if user has access to a premium feature.

        Args:
            user_id: User ID
            feature: Feature name ('ai_chat', 'impact_tracking', 'email_notifications', 'api_access')

        Returns:
            Tuple of (has_access: bool, error_message: Optional[str])
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False, "No active subscription found"

        plan = subscription.plan

        feature_map = {
            "ai_chat": plan.has_ai_chat,
            "impact_tracking": plan.has_impact_tracking,
            "email_notifications": plan.has_email_notifications,
            "api_access": plan.has_api_access,
            "priority_support": plan.has_priority_support,
        }

        has_access = feature_map.get(feature, False)

        if not has_access:
            return (
                False,
                f"This feature requires a {plan.name == 'free' and 'Pro' or 'Enterprise'} subscription. "
                f"Upgrade to access {feature.replace('_', ' ')}.",
            )

        return True, None
