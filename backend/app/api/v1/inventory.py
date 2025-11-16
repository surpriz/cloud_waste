"""Inventory API endpoints (Cost Intelligence)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.crud import all_cloud_resource as crud_inventory
from app.crud import cloud_account as crud_cloud_account
from app.schemas.all_cloud_resource import (
    AllCloudResource,
    CostBreakdown,
    HighCostResource,
    InventoryStats,
    OptimizationRecommendation,
)
from app.models.all_cloud_resource import OptimizationPriority

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/stats", response_model=InventoryStats)
@limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
async def get_inventory_stats(
    request: Request,
    cloud_account_id: uuid.UUID = Query(..., description="Cloud account ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get inventory statistics for a cloud account.

    Returns comprehensive statistics including:
    - Total resources and costs
    - Breakdown by type, region, provider
    - Optimization opportunities
    - High-cost resources count
    """
    # Verify account belongs to user
    account = await crud_cloud_account.get_cloud_account_by_id(db, cloud_account_id, current_user.id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    stats = await crud_inventory.get_inventory_stats(db, cloud_account_id)

    # Add by_provider (derived from account)
    stats["by_provider"] = {account.provider: stats["total_resources"]}

    return stats


@router.get("/cost-breakdown", response_model=CostBreakdown)
@limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
async def get_cost_breakdown(
    request: Request,
    cloud_account_id: uuid.UUID = Query(..., description="Cloud account ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get detailed cost breakdown by type, region, and provider.

    Useful for identifying where cloud spend is concentrated.
    """
    # Verify account belongs to user
    account = await crud_cloud_account.get_cloud_account_by_id(db, cloud_account_id, current_user.id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    breakdown = await crud_inventory.get_cost_breakdown(db, cloud_account_id)

    # Add provider breakdown
    stats = await crud_inventory.get_inventory_stats(db, cloud_account_id)
    breakdown["by_provider"] = [
        {
            "provider": account.provider,
            "count": stats["total_resources"],
            "total_monthly_cost": stats["total_monthly_cost"],
        }
    ]

    return breakdown


@router.get("/high-cost-resources", response_model=list[HighCostResource])
@limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
async def get_high_cost_resources(
    request: Request,
    cloud_account_id: uuid.UUID = Query(..., description="Cloud account ID"),
    min_cost: float = Query(100.0, description="Minimum monthly cost threshold"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AllCloudResource]:
    """
    Get high-cost resources above specified threshold.

    By default, returns resources costing >$100/month.
    Useful for identifying expensive resources that may need review.
    """
    # Verify account belongs to user
    account = await crud_cloud_account.get_cloud_account_by_id(db, cloud_account_id, current_user.id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    resources = await crud_inventory.get_high_cost_resources(
        db, cloud_account_id, min_cost, limit
    )
    return resources


@router.get("/optimizable-resources", response_model=list[AllCloudResource])
@limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
async def get_optimizable_resources(
    request: Request,
    cloud_account_id: uuid.UUID = Query(..., description="Cloud account ID"),
    priority: OptimizationPriority | None = Query(
        None, description="Filter by optimization priority"
    ),
    min_savings: float | None = Query(
        None, description="Minimum monthly savings threshold"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AllCloudResource]:
    """
    Get resources with optimization opportunities.

    Returns resources that can be optimized to reduce costs,
    sorted by potential monthly savings (highest first).
    """
    # Verify account belongs to user
    account = await crud_cloud_account.get_cloud_account_by_id(db, cloud_account_id, current_user.id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    resources = await crud_inventory.get_optimizable_resources(
        db, cloud_account_id, priority, min_savings, limit
    )
    return resources


@router.get("/resources", response_model=list[AllCloudResource])
@limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
async def get_all_resources(
    request: Request,
    cloud_account_id: uuid.UUID = Query(..., description="Cloud account ID"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    is_optimizable: bool | None = Query(
        None, description="Filter by optimization status"
    ),
    min_cost: float | None = Query(None, description="Minimum monthly cost filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AllCloudResource]:
    """
    Get all cloud resources for an account (with filters).

    Returns paginated list of all resources from the latest scan.
    Supports filtering by type, optimization status, and cost.
    """
    # Verify account belongs to user
    account = await crud_cloud_account.get_cloud_account_by_id(db, cloud_account_id, current_user.id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cloud account not found")

    resources = await crud_inventory.get_resources_by_account(
        db, cloud_account_id, resource_type, is_optimizable, min_cost, skip, limit
    )
    return resources


@router.get("/resources/{resource_id}", response_model=AllCloudResource)
@limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
async def get_resource_details(
    request: Request,
    resource_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AllCloudResource:
    """
    Get detailed information for a specific resource.

    Includes full metadata, utilization metrics, and optimization recommendations.
    """
    resource = await crud_inventory.get_resource_by_id(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Verify resource belongs to user's account
    account = await crud_cloud_account.get_cloud_account_by_id(
        db, resource.cloud_account_id, current_user.id
    )
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Resource not found")

    return resource
