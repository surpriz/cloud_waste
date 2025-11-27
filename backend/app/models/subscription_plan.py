"""Subscription Plan database model."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SubscriptionPlan(Base):
    """Subscription plan model (Free, Pro, Enterprise)."""

    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )  # 'free', 'pro', 'enterprise'
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )  # 'Free', 'Pro', 'Enterprise'
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
    )
    stripe_price_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )  # Stripe Price ID (null for free plan)

    # Limits
    max_scans_per_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )  # null = unlimited
    max_cloud_accounts: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )  # null = unlimited
    has_ai_chat: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    has_impact_tracking: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    has_email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    has_api_access: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    has_priority_support: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user_subscriptions: Mapped[list["UserSubscription"]] = relationship(  # type: ignore
        "UserSubscription",
        back_populates="plan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<SubscriptionPlan {self.display_name} ({self.price_monthly}{self.currency}/mo)>"
