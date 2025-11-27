"""User Subscription database model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserSubscription(Base):
    """User subscription model - tracks active subscriptions."""

    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Stripe data
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )  # null for free plan
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )  # Stripe customer ID

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )  # active, canceled, past_due, incomplete, trialing

    # Billing period
    current_period_start: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Usage tracking (reset monthly)
    scans_used_this_month: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    last_scan_reset_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # type: ignore
        "User",
        back_populates="subscription",
    )
    plan: Mapped["SubscriptionPlan"] = relationship(  # type: ignore
        "SubscriptionPlan",
        back_populates="user_subscriptions",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserSubscription user_id={self.user_id} plan_id={self.plan_id} status={self.status}>"
