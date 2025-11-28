"""Subscription API endpoints."""

import logging
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.subscription import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    CreatePortalSessionRequest,
    CreatePortalSessionResponse,
    SubscriptionPlanResponse,
    UserSubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def get_subscription_plans(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SubscriptionPlanResponse]:
    """Get all available subscription plans.

    Returns:
        List of subscription plans
    """
    service = SubscriptionService(db)
    plans = await service.get_all_active_plans()
    return [SubscriptionPlanResponse.model_validate(plan) for plan in plans]


@router.get("/current", response_model=UserSubscriptionResponse)
async def get_current_subscription(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSubscriptionResponse:
    """Get current user's subscription.

    If the user doesn't have a subscription, a free subscription is created automatically.
    This ensures all users always have access to the platform's basic features.

    Returns:
        User's active subscription (existing or newly created free subscription)

    Raises:
        HTTPException: If free plan not found in database (configuration error)
    """
    service = SubscriptionService(db)

    try:
        # Get or create subscription (auto-creates free subscription if needed)
        subscription = await service.get_or_create_user_subscription(current_user.id)
        return UserSubscriptionResponse.model_validate(subscription)
    except ValueError as e:
        # This should only happen if free plan is not configured in database
        logger.error(f"Failed to get/create subscription for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription system not properly configured. Please contact support.",
        )


@router.post(
    "/create-checkout-session",
    response_model=CreateCheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateCheckoutSessionResponse:
    """Create Stripe Checkout Session for subscription purchase.

    Args:
        request: Checkout session request (plan, success_url, cancel_url)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Checkout session details (session_id, url)

    Raises:
        HTTPException: If plan is invalid or Stripe error
    """
    service = SubscriptionService(db)

    try:
        session = await service.create_checkout_session(
            user=current_user,
            plan_name=request.plan_name,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )

        return CreateCheckoutSessionResponse(
            session_id=session["id"],
            url=session["url"],
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session. Please try again later.",
        )


@router.post(
    "/create-portal-session",
    response_model=CreatePortalSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreatePortalSessionResponse:
    """Create Stripe Customer Portal Session.

    Args:
        request: Portal session request (return_url)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Portal session details (url)

    Raises:
        HTTPException: If user has no Stripe customer or Stripe error
    """
    service = SubscriptionService(db)

    try:
        session = await service.create_portal_session(
            user=current_user,
            return_url=request.return_url,
        )

        return CreatePortalSessionResponse(url=session["url"])

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session. Please try again later.",
        )


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
) -> dict:
    """Handle Stripe webhooks.

    Args:
        request: FastAPI request object
        db: Database session
        stripe_signature: Stripe signature header

    Returns:
        Success response

    Raises:
        HTTPException: If signature verification fails
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    service = SubscriptionService(db)

    # Handle webhook events
    try:
        if event["type"] == "checkout.session.completed":
            await service.handle_checkout_completed(event["data"]["object"])
            logger.info(f"Processed checkout.session.completed webhook")

        elif event["type"] == "customer.subscription.updated":
            await service.handle_subscription_updated(event["data"]["object"])
            logger.info(f"Processed customer.subscription.updated webhook")

        elif event["type"] == "customer.subscription.deleted":
            await service.handle_subscription_deleted(event["data"]["object"])
            logger.info(f"Processed customer.subscription.deleted webhook")

        elif event["type"] == "invoice.payment_succeeded":
            # Stripe automatically renews subscription on successful payment
            logger.info(f"Processed invoice.payment_succeeded webhook")

        elif event["type"] == "invoice.payment_failed":
            logger.warning(f"Payment failed for subscription: {event['data']['object']}")

        else:
            logger.info(f"Unhandled webhook event type: {event['type']}")

    except Exception as e:
        logger.error(f"Error processing webhook {event['type']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )

    return {"status": "success"}
