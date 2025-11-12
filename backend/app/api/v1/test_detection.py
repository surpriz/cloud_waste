"""Test detection API endpoints for debugging and development.

⚠️ SECURITY WARNING: These endpoints are only available in development mode (DEBUG=True).
They allow overriding detection rules for testing purposes.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.core.config import settings
from app.core.security import credential_encryption
from app.models.cloud_account import CloudAccount
from app.models.user import User
from app.providers.aws import AWSProvider
from app.providers.azure import AzureProvider
from app.services.pricing_service import PricingService
from sqlalchemy import select
import json
import sentry_sdk

router = APIRouter()


class DetectionOverrides(BaseModel):
    """Override rules for specific resource types."""

    min_age_days: int | None = Field(None, description="Override min_age_days")
    confidence_threshold_days: int | None = Field(
        None, description="Override confidence_threshold_days"
    )
    enabled: bool = Field(True, description="Enable detection for this resource type")


class TestDetectionRequest(BaseModel):
    """Request body for test detection."""

    account_id: uuid.UUID = Field(..., description="Cloud account ID to scan")
    region: str = Field(..., description="AWS region to scan (e.g., us-east-1)")
    resource_types: list[str] = Field(
        ..., description="Resource types to detect (e.g., ['elastic_ip', 'ebs_volume'])"
    )
    overrides: dict[str, DetectionOverrides] = Field(
        default_factory=dict,
        description="Detection rule overrides per resource type",
    )


class TestDetectionResponse(BaseModel):
    """Response from test detection."""

    status: str = Field(..., description="Operation status (success, error)")
    account_id: str = Field(..., description="Scanned account ID")
    region: str = Field(..., description="Scanned region")
    resource_types_scanned: list[str] = Field(..., description="Resource types scanned")
    resources_found: int = Field(..., description="Number of resources found")
    overrides_applied: dict = Field(..., description="Overrides that were applied")
    results: list[dict] = Field(..., description="Detected resources")


@router.post(
    "/test/detect-resources",
    response_model=TestDetectionResponse,
    summary="Test resource detection with custom rules (DEV ONLY)",
)
async def test_resource_detection(
    request: TestDetectionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> TestDetectionResponse:
    """
    Test resource detection with custom detection rules (DEV ONLY).

    ⚠️ SECURITY: This endpoint is only available when DEBUG=True.
    It allows superusers to test detection with overridden rules (e.g., min_age_days=0).

    Use case:
    - Testing detection immediately after creating test resources
    - Debugging detection logic without waiting for age thresholds
    - Validating detection rules in development

    Example request:
    ```json
    {
      "account_id": "uuid",
      "region": "us-east-1",
      "resource_types": ["elastic_ip"],
      "overrides": {
        "elastic_ip": {
          "min_age_days": 0,
          "confidence_threshold_days": 0
        }
      }
    }
    ```

    Args:
        request: Test detection request with account, region, and overrides

    Returns:
        TestDetectionResponse with detected resources

    Raises:
        HTTPException: If DEBUG=False, account not found, or scan fails
    """
    # ⚠️ SECURITY CHECK: Only allow in development mode
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test detection endpoint is only available in DEBUG mode (development)",
        )

    # Get cloud account
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == request.account_id,
            CloudAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud account not found or not authorized",
        )

    # Decrypt credentials
    try:
        credentials_json = credential_encryption.decrypt(account.credentials_encrypted)
        credentials = json.loads(credentials_json)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt credentials: {str(e)}",
        )

    # Initialize provider
    if account.provider == "aws":
        # Create pricing service
        pricing_service = PricingService(db)

        provider = AWSProvider(
            access_key=credentials["access_key_id"],
            secret_key=credentials["secret_access_key"],
            regions=[request.region],
            pricing_service=pricing_service,
        )

        # Validate credentials
        try:
            await provider.validate_credentials()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid AWS credentials: {str(e)}",
            )

    elif account.provider == "azure":
        provider = AzureProvider(
            tenant_id=credentials["tenant_id"],
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            subscription_id=credentials["subscription_id"],
            regions=[request.region],
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {account.provider} not supported for test detection",
        )

    # Prepare detection rules with overrides
    from app.models.detection_rule import DEFAULT_DETECTION_RULES

    detection_rules = {}

    for resource_type in request.resource_types:
        # Start with default rules
        default_rules = DEFAULT_DETECTION_RULES.get(resource_type, {}).copy()

        # Apply overrides if provided
        if resource_type in request.overrides:
            overrides = request.overrides[resource_type]
            if overrides.min_age_days is not None:
                default_rules["min_age_days"] = overrides.min_age_days
            if overrides.confidence_threshold_days is not None:
                default_rules["confidence_threshold_days"] = (
                    overrides.confidence_threshold_days
                )
            default_rules["enabled"] = overrides.enabled

        detection_rules[resource_type] = default_rules

    # Run detection based on resource types
    all_results = []

    try:
        for resource_type in request.resource_types:
            rules = detection_rules.get(resource_type)

            if resource_type == "elastic_ip":
                orphans = await provider.scan_unassigned_ips(request.region, rules)
                all_results.extend(orphans)
            elif resource_type == "ebs_volume":
                orphans = await provider.scan_unattached_volumes(request.region, rules)
                all_results.extend(orphans)
            # Add more resource types as needed

        # Convert results to dict for response
        results_dict = [
            {
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "resource_name": r.resource_name,
                "region": r.region,
                "estimated_monthly_cost": r.estimated_monthly_cost,
                "metadata": r.resource_metadata,
            }
            for r in all_results
        ]

        return TestDetectionResponse(
            status="success",
            account_id=str(request.account_id),
            region=request.region,
            resource_types_scanned=request.resource_types,
            resources_found=len(all_results),
            overrides_applied={
                rt: request.overrides[rt].model_dump()
                for rt in request.overrides
            },
            results=results_dict,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test detection failed: {str(e)}",
        )


@router.get("/sentry-test")
async def test_sentry(
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> dict:
    """
    Test Sentry error tracking by triggering different types of errors.

    ⚠️ Only available in DEBUG mode with superuser authentication.

    This endpoint tests:
    - Exception capture
    - Breadcrumbs
    - User context
    - Tags and extras
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are only available in DEBUG mode",
        )

    # Add breadcrumb
    sentry_sdk.add_breadcrumb(
        category="test",
        message="Sentry test endpoint called",
        level="info",
    )

    # Set user context
    sentry_sdk.set_user({
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.full_name,
    })

    # Set tags and extras
    sentry_sdk.set_tag("test_type", "manual_sentry_test")
    sentry_sdk.set_tag("environment", settings.APP_ENV)
    sentry_sdk.set_context("test_info", {
        "endpoint": "/api/v1/test/sentry-test",
        "purpose": "Manual Sentry integration test",
    })

    # Capture a test exception (this will be sent to Sentry)
    try:
        # Intentionally raise an exception to test Sentry
        raise ValueError("🧪 Test Sentry Exception - This is a controlled test error to verify Sentry integration")
    except ValueError as e:
        # Capture the exception and send to Sentry
        sentry_sdk.capture_exception(e)

        # Return success (we caught the exception, but it was sent to Sentry)
        return {
            "status": "success",
            "message": "Test exception sent to Sentry successfully",
            "sentry_dsn_configured": bool(settings.SENTRY_DSN),
            "sentry_environment": settings.SENTRY_ENVIRONMENT,
            "user_context": {
                "id": str(current_user.id),
                "email": current_user.email,
            },
            "instructions": "Check your Sentry dashboard at https://sentry.io for the captured exception",
        }


@router.get("/sentry-test-division-by-zero")
async def test_sentry_division_by_zero(
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> dict:
    """
    Test Sentry by triggering a ZeroDivisionError (uncaught exception).

    ⚠️ This will return HTTP 500 - use for testing error handling.
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are only available in DEBUG mode",
        )

    # This will be caught by FastAPI's exception handler and sent to Sentry
    result = 1 / 0  # Intentional ZeroDivisionError
    return {"result": result}
