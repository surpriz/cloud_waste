"""Subscription access control dependencies."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


async def check_scan_limit(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to check if user can perform a scan.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User if allowed

    Raises:
        HTTPException: If scan limit exceeded
    """
    service = SubscriptionService(db)
    can_scan, error_message = await service.check_scan_limit(current_user.id)

    if not can_scan:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message or "Scan limit exceeded",
        )

    return current_user


async def check_cloud_account_limit(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to check if user can add more cloud accounts.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User if allowed

    Raises:
        HTTPException: If cloud account limit exceeded
    """
    service = SubscriptionService(db)
    can_add, error_message = await service.check_cloud_account_limit(current_user.id)

    if not can_add:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message or "Cloud account limit exceeded",
        )

    return current_user


async def require_ai_chat_access(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to check if user has AI chat access.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User if allowed

    Raises:
        HTTPException: If feature not available in subscription
    """
    service = SubscriptionService(db)
    has_access, error_message = await service.check_feature_access(
        current_user.id, "ai_chat"
    )

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message or "AI Chat requires Pro or Enterprise subscription",
        )

    return current_user


async def require_impact_tracking_access(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to check if user has impact tracking access.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User if allowed

    Raises:
        HTTPException: If feature not available in subscription
    """
    service = SubscriptionService(db)
    has_access, error_message = await service.check_feature_access(
        current_user.id, "impact_tracking"
    )

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message
            or "Impact Tracking requires Pro or Enterprise subscription",
        )

    return current_user


async def require_api_access(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to check if user has API access.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User if allowed

    Raises:
        HTTPException: If feature not available in subscription
    """
    service = SubscriptionService(db)
    has_access, error_message = await service.check_feature_access(
        current_user.id, "api_access"
    )

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message or "API Access requires Enterprise subscription",
        )

    return current_user
