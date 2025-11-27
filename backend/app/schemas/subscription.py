"""Subscription request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SubscriptionPlanResponse(BaseModel):
    """Subscription plan response schema."""

    id: UUID
    name: str = Field(..., description="Plan internal name (free, pro, enterprise)")
    display_name: str = Field(..., description="Plan display name")
    description: Optional[str] = Field(None, description="Plan description")
    price_monthly: Decimal = Field(..., description="Monthly price")
    currency: str = Field(..., description="Currency code (EUR, USD)")
    stripe_price_id: Optional[str] = Field(None, description="Stripe Price ID")

    # Limits
    max_scans_per_month: Optional[int] = Field(
        None, description="Maximum scans per month (null = unlimited)"
    )
    max_cloud_accounts: Optional[int] = Field(
        None, description="Maximum cloud accounts (null = unlimited)"
    )

    # Features
    has_ai_chat: bool = Field(..., description="AI chat assistant access")
    has_impact_tracking: bool = Field(..., description="Environmental impact tracking")
    has_email_notifications: bool = Field(..., description="Email notifications")
    has_api_access: bool = Field(..., description="API access")
    has_priority_support: bool = Field(..., description="Priority support")

    is_active: bool = Field(..., description="Plan is active and available")

    class Config:
        """Pydantic config."""

        from_attributes = True


class UserSubscriptionResponse(BaseModel):
    """User subscription response schema."""

    id: UUID
    user_id: UUID
    plan: SubscriptionPlanResponse
    status: str = Field(
        ...,
        description="Subscription status (active, canceled, past_due, incomplete, trialing)",
    )
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    current_period_start: Optional[datetime] = Field(
        None, description="Current billing period start"
    )
    current_period_end: Optional[datetime] = Field(
        None, description="Current billing period end"
    )
    cancel_at_period_end: bool = Field(
        ..., description="Subscription will cancel at period end"
    )

    # Usage tracking
    scans_used_this_month: int = Field(..., description="Scans used this month")
    last_scan_reset_at: Optional[datetime] = Field(
        None, description="Last scan counter reset"
    )

    created_at: datetime
    canceled_at: Optional[datetime] = Field(None, description="Cancellation timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class CreateCheckoutSessionRequest(BaseModel):
    """Request to create Stripe Checkout Session."""

    plan_name: str = Field(
        ...,
        description="Plan to subscribe to (pro, enterprise)",
        pattern="^(pro|enterprise)$",
    )
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if user cancels")


class CreateCheckoutSessionResponse(BaseModel):
    """Response with Stripe Checkout Session details."""

    session_id: str = Field(..., description="Stripe Checkout Session ID")
    url: str = Field(..., description="Stripe Checkout URL")


class CreatePortalSessionRequest(BaseModel):
    """Request to create Stripe Customer Portal Session."""

    return_url: str = Field(..., description="URL to return to after portal session")


class CreatePortalSessionResponse(BaseModel):
    """Response with Stripe Customer Portal Session details."""

    url: str = Field(..., description="Stripe Customer Portal URL")


class SubscriptionLimitCheckResponse(BaseModel):
    """Response for subscription limit checks."""

    allowed: bool = Field(..., description="Action is allowed")
    error_message: Optional[str] = Field(None, description="Error message if not allowed")
    current_usage: Optional[int] = Field(None, description="Current usage count")
    limit: Optional[int] = Field(None, description="Usage limit (null = unlimited)")
