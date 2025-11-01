"""Admin API endpoints for pricing management."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser
from app.core.database import get_db
from app.models.pricing_cache import CloudProvider, PricingCache
from app.models.user import User
from app.schemas.admin_pricing import (
    PricingCacheItem,
    PricingRefreshResponse,
    PricingStats,
)
from app.workers.celery_app import celery_app

router = APIRouter()


@router.get(
    "/pricing/stats",
    response_model=PricingStats,
    summary="Get pricing system statistics",
)
async def get_pricing_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
) -> PricingStats:
    """
    Get pricing system statistics (superuser only).

    Returns comprehensive stats about the pricing cache system:
    - Total cached prices
    - Expired vs valid entries
    - Source breakdown (API vs fallback)
    - Cache hit rate
    - API success rate

    Returns:
        PricingStats object with all statistics
    """
    # Count total prices in cache
    total_result = await db.execute(select(func.count(PricingCache.id)))
    total_cached_prices = total_result.scalar() or 0

    # Count expired prices
    expired_result = await db.execute(
        select(func.count(PricingCache.id)).where(
            PricingCache.expires_at < datetime.utcnow()
        )
    )
    expired_prices = expired_result.scalar() or 0

    # Count API-sourced prices
    api_result = await db.execute(
        select(func.count(PricingCache.id)).where(PricingCache.source == "api")
    )
    api_sourced_prices = api_result.scalar() or 0

    # Count fallback-sourced prices
    fallback_result = await db.execute(
        select(func.count(PricingCache.id)).where(PricingCache.source == "fallback")
    )
    fallback_sourced_prices = fallback_result.scalar() or 0

    # Get last refresh timestamp
    last_refresh_result = await db.execute(
        select(func.max(PricingCache.last_updated))
    )
    last_refresh_at = last_refresh_result.scalar()

    # Calculate cache hit rate (valid entries / total)
    valid_prices = total_cached_prices - expired_prices
    cache_hit_rate = (
        (valid_prices / total_cached_prices * 100) if total_cached_prices > 0 else 0.0
    )

    # Calculate API success rate (API sourced / total)
    api_success_rate = (
        (api_sourced_prices / total_cached_prices * 100)
        if total_cached_prices > 0
        else 0.0
    )

    return PricingStats(
        total_cached_prices=total_cached_prices,
        expired_prices=expired_prices,
        api_sourced_prices=api_sourced_prices,
        fallback_sourced_prices=fallback_sourced_prices,
        last_refresh_at=last_refresh_at,
        cache_hit_rate=round(cache_hit_rate, 2),
        api_success_rate=round(api_success_rate, 2),
    )


@router.get(
    "/pricing/cache",
    response_model=list[PricingCacheItem],
    summary="Get pricing cache entries",
)
async def get_pricing_cache(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
    provider: str | None = Query(None, description="Filter by provider (aws, azure, gcp)"),
    region: str | None = Query(None, description="Filter by region"),
    service: str | None = Query(None, description="Filter by service"),
    skip: int = Query(0, ge=0, description="Number of entries to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of entries to return"),
) -> list[PricingCacheItem]:
    """
    Get pricing cache entries with optional filters (superuser only).

    Supports filtering by:
    - Provider (aws, azure, gcp)
    - Region (us-east-1, eu-west-1, etc.)
    - Service (ebs_gp3, elastic_ip, etc.)

    Results are ordered by last_updated descending.

    Args:
        provider: Optional provider filter
        region: Optional region filter
        service: Optional service filter
        skip: Pagination offset
        limit: Maximum results per page

    Returns:
        List of PricingCacheItem objects
    """
    # Build query with filters
    query = select(PricingCache)

    if provider:
        query = query.where(PricingCache.provider == provider)
    if region:
        query = query.where(PricingCache.region == region)
    if service:
        query = query.where(PricingCache.service == service)

    # Order by last updated (most recent first)
    query = query.order_by(PricingCache.last_updated.desc())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    result = await db.execute(query)
    cache_entries = result.scalars().all()

    # Convert to response schema
    return [
        PricingCacheItem(
            provider=entry.provider,
            service=entry.service,
            region=entry.region,
            price_per_unit=entry.price_per_unit,
            unit=entry.unit,
            currency=entry.currency,
            source=entry.source,
            last_updated=entry.last_updated,
            expires_at=entry.expires_at,
            is_expired=entry.is_expired(),
        )
        for entry in cache_entries
    ]


@router.post(
    "/pricing/refresh",
    response_model=PricingRefreshResponse,
    summary="Trigger manual pricing refresh",
)
async def trigger_pricing_refresh(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
) -> PricingRefreshResponse:
    """
    Manually trigger pricing cache refresh (superuser only).

    This endpoint launches the Celery task `update_pricing_cache` immediately,
    which will fetch fresh prices from cloud provider APIs.

    The task runs asynchronously - use the returned task_id to track progress.

    Returns:
        PricingRefreshResponse with task_id for tracking

    Raises:
        HTTPException: If Celery task cannot be launched
    """
    try:
        # Launch Celery task asynchronously
        task = celery_app.send_task("app.workers.tasks.update_pricing_cache")

        return PricingRefreshResponse(
            status="success",
            task_id=str(task.id),
            message="Pricing refresh task launched successfully. Check task status using task_id.",
            updated_count=None,  # Will be available in task result
            failed_count=None,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to launch pricing refresh task: {str(e)}",
        )


@router.get(
    "/pricing/refresh/{task_id}",
    response_model=PricingRefreshResponse,
    summary="Get pricing refresh task status",
)
async def get_refresh_task_status(
    task_id: str,
    _: Annotated[User, Depends(get_current_superuser)],
) -> PricingRefreshResponse:
    """
    Get status of a pricing refresh task (superuser only).

    Use the task_id returned from POST /pricing/refresh to check progress.

    Args:
        task_id: Celery task ID

    Returns:
        PricingRefreshResponse with task status and results

    Raises:
        HTTPException: If task not found
    """
    try:
        # Get task result from Celery
        task_result = celery_app.AsyncResult(task_id)

        if task_result.state == "PENDING":
            return PricingRefreshResponse(
                status="pending",
                task_id=task_id,
                message="Task is queued and waiting to execute",
                updated_count=None,
                failed_count=None,
            )
        elif task_result.state == "SUCCESS":
            result = task_result.result
            return PricingRefreshResponse(
                status="success",
                task_id=task_id,
                message="Pricing refresh completed successfully",
                updated_count=result.get("updated_count", 0),
                failed_count=result.get("failed_count", 0),
            )
        elif task_result.state == "FAILURE":
            return PricingRefreshResponse(
                status="error",
                task_id=task_id,
                message=f"Task failed: {str(task_result.info)}",
                updated_count=None,
                failed_count=None,
            )
        else:
            return PricingRefreshResponse(
                status="running",
                task_id=task_id,
                message=f"Task is currently running (state: {task_result.state})",
                updated_count=None,
                failed_count=None,
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found or error retrieving status: {str(e)}",
        )
