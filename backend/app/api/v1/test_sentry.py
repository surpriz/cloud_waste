"""Test Sentry error tracking endpoints for debugging and development.

⚠️ SECURITY WARNING: These endpoints are only available in development mode (DEBUG=True).
They allow triggering test errors to verify Sentry integration.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.models.user import User

router = APIRouter()


class SentryTestResponse(BaseModel):
    """Response from Sentry test endpoints."""

    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Response message")
    sentry_enabled: bool = Field(..., description="Whether Sentry is configured")
    sentry_environment: str | None = Field(None, description="Sentry environment")


@router.post(
    "/test/sentry/error",
    response_model=SentryTestResponse,
    summary="Trigger test error for Sentry (DEV ONLY)",
)
async def test_sentry_error(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SentryTestResponse:
    """
    Trigger a test error to verify Sentry error tracking (DEV ONLY).

    ⚠️ SECURITY: This endpoint is only available when DEBUG=True.
    It allows authenticated users to trigger a test exception.

    Use case:
    - Verify Sentry integration is working
    - Test error capture and reporting
    - Validate Sentry dashboard configuration

    Returns:
        Never returns - always raises ZeroDivisionError

    Raises:
        HTTPException: If DEBUG=False (production mode)
        ZeroDivisionError: Intentional test error for Sentry
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are only available in DEBUG mode",
        )

    # Check if Sentry is configured
    sentry_enabled = bool(settings.SENTRY_DSN)

    # Capture context before raising error
    if sentry_enabled:
        import sentry_sdk

        sentry_sdk.set_user({"email": current_user.email, "id": str(current_user.id)})
        sentry_sdk.set_context(
            "test_context",
            {
                "endpoint": "/api/v1/test/sentry/error",
                "purpose": "Sentry integration test",
                "user_triggered": True,
            },
        )

    # Trigger test error
    # This will be captured by Sentry and appear in the dashboard
    raise ZeroDivisionError("🚨 TEST ERROR: Sentry integration test triggered by user")


@router.get(
    "/test/sentry/status",
    response_model=SentryTestResponse,
    summary="Check Sentry configuration status (DEV ONLY)",
)
async def check_sentry_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SentryTestResponse:
    """
    Check if Sentry is properly configured (DEV ONLY).

    ⚠️ SECURITY: This endpoint is only available when DEBUG=True.

    Returns:
        SentryTestResponse with Sentry configuration status

    Raises:
        HTTPException: If DEBUG=False (production mode)
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are only available in DEBUG mode",
        )

    sentry_enabled = bool(settings.SENTRY_DSN)

    if sentry_enabled:
        return SentryTestResponse(
            status="success",
            message=f"Sentry is configured and enabled (environment: {settings.SENTRY_ENVIRONMENT})",
            sentry_enabled=True,
            sentry_environment=settings.SENTRY_ENVIRONMENT,
        )
    else:
        return SentryTestResponse(
            status="warning",
            message="Sentry is not configured (SENTRY_DSN not set)",
            sentry_enabled=False,
            sentry_environment=None,
        )


@router.post(
    "/test/sentry/message",
    response_model=SentryTestResponse,
    summary="Send test message to Sentry (DEV ONLY)",
)
async def test_sentry_message(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SentryTestResponse:
    """
    Send a test message to Sentry without raising an error (DEV ONLY).

    ⚠️ SECURITY: This endpoint is only available when DEBUG=True.

    This sends an informational message to Sentry to verify
    that message capture is working (not just error capture).

    Returns:
        SentryTestResponse with operation status

    Raises:
        HTTPException: If DEBUG=False or Sentry not configured
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are only available in DEBUG mode",
        )

    if not settings.SENTRY_DSN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sentry is not configured (SENTRY_DSN not set)",
        )

    import sentry_sdk

    # Set user context
    sentry_sdk.set_user({"email": current_user.email, "id": str(current_user.id)})

    # Send test message
    sentry_sdk.capture_message(
        "✅ Sentry test message from CloudWaste",
        level="info",
        extras={
            "endpoint": "/api/v1/test/sentry/message",
            "purpose": "Testing Sentry message capture",
            "triggered_by": current_user.email,
        },
    )

    return SentryTestResponse(
        status="success",
        message=f"Test message sent to Sentry (environment: {settings.SENTRY_ENVIRONMENT})",
        sentry_enabled=True,
        sentry_environment=settings.SENTRY_ENVIRONMENT,
    )
