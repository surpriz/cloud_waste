"""CRUD operations for all cloud resources (inventory mode)."""

import uuid
from typing import Any

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_cloud_resource import AllCloudResource, OptimizationPriority
from app.schemas.all_cloud_resource import AllCloudResourceCreate


async def create_resource(
    db: AsyncSession, resource_in: AllCloudResourceCreate
) -> AllCloudResource:
    """
    Create a new cloud resource (inventory mode).

    Args:
        db: Database session
        resource_in: Resource creation data

    Returns:
        Created resource object
    """
    resource = AllCloudResource(**resource_in.model_dump())
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


async def bulk_create_resources(
    db: AsyncSession, resources_in: list[AllCloudResourceCreate]
) -> list[AllCloudResource]:
    """
    Bulk create cloud resources (optimized for large scans).

    Args:
        db: Database session
        resources_in: List of resources to create

    Returns:
        List of created resource objects
    """
    resources = [AllCloudResource(**r.model_dump()) for r in resources_in]
    db.add_all(resources)
    await db.commit()
    for resource in resources:
        await db.refresh(resource)
    return resources


async def get_resource_by_id(
    db: AsyncSession, resource_id: uuid.UUID
) -> AllCloudResource | None:
    """
    Get cloud resource by ID.

    Args:
        db: Database session
        resource_id: Resource UUID

    Returns:
        AllCloudResource object or None if not found
    """
    result = await db.execute(
        select(AllCloudResource).where(AllCloudResource.id == resource_id)
    )
    return result.scalar_one_or_none()


async def get_resources_by_scan(
    db: AsyncSession,
    scan_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[AllCloudResource]:
    """
    Get resources for a specific scan.

    Args:
        db: Database session
        scan_id: Scan UUID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of resource objects
    """
    result = await db.execute(
        select(AllCloudResource)
        .where(AllCloudResource.scan_id == scan_id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_resources_by_account(
    db: AsyncSession,
    cloud_account_id: uuid.UUID,
    resource_type: str | None = None,
    is_optimizable: bool | None = None,
    min_cost: float | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AllCloudResource]:
    """
    Get resources for a specific cloud account from the latest scan.

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID
        resource_type: Optional resource type filter
        is_optimizable: Optional filter for optimizable resources
        min_cost: Optional minimum monthly cost filter
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of resource objects from the latest scan
    """
    # Build query with filters
    query = select(AllCloudResource).where(
        AllCloudResource.cloud_account_id == cloud_account_id
    )

    if resource_type:
        query = query.where(AllCloudResource.resource_type == resource_type)

    if is_optimizable is not None:
        query = query.where(AllCloudResource.is_optimizable == is_optimizable)

    if min_cost is not None:
        query = query.where(AllCloudResource.estimated_monthly_cost >= min_cost)

    query = query.order_by(AllCloudResource.estimated_monthly_cost.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_high_cost_resources(
    db: AsyncSession,
    cloud_account_id: uuid.UUID,
    min_cost: float = 100.0,
    limit: int = 10,
) -> list[AllCloudResource]:
    """
    Get high-cost resources (above threshold).

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID
        min_cost: Minimum monthly cost threshold (default $100)
        limit: Maximum number of results

    Returns:
        List of high-cost resources sorted by cost descending
    """
    result = await db.execute(
        select(AllCloudResource)
        .where(
            and_(
                AllCloudResource.cloud_account_id == cloud_account_id,
                AllCloudResource.estimated_monthly_cost >= min_cost,
            )
        )
        .order_by(AllCloudResource.estimated_monthly_cost.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_optimizable_resources(
    db: AsyncSession,
    cloud_account_id: uuid.UUID,
    priority: OptimizationPriority | None = None,
    min_savings: float | None = None,
    limit: int = 100,
) -> list[AllCloudResource]:
    """
    Get optimizable resources with potential savings.

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID
        priority: Optional filter by optimization priority
        min_savings: Optional minimum monthly savings filter
        limit: Maximum number of results

    Returns:
        List of optimizable resources sorted by potential savings
    """
    query = select(AllCloudResource).where(
        and_(
            AllCloudResource.cloud_account_id == cloud_account_id,
            AllCloudResource.is_optimizable == True,
        )
    )

    if priority:
        query = query.where(AllCloudResource.optimization_priority == priority.value)

    if min_savings:
        query = query.where(
            AllCloudResource.potential_monthly_savings >= min_savings
        )

    query = query.order_by(AllCloudResource.potential_monthly_savings.desc()).limit(
        limit
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_inventory_stats(
    db: AsyncSession, cloud_account_id: uuid.UUID
) -> dict[str, Any]:
    """
    Get inventory statistics for a cloud account.

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID

    Returns:
        Dictionary with inventory statistics
    """
    # Total resources and costs
    total_result = await db.execute(
        select(
            func.count(AllCloudResource.id),
            func.sum(AllCloudResource.estimated_monthly_cost),
            func.sum(AllCloudResource.potential_monthly_savings),
        ).where(AllCloudResource.cloud_account_id == cloud_account_id)
    )
    total_count, total_cost, total_savings = total_result.one()

    # By resource type
    by_type_result = await db.execute(
        select(
            AllCloudResource.resource_type,
            func.count(AllCloudResource.id).label("count"),
        )
        .where(AllCloudResource.cloud_account_id == cloud_account_id)
        .group_by(AllCloudResource.resource_type)
    )
    by_type = {row[0]: row[1] for row in by_type_result.all()}

    # By region
    by_region_result = await db.execute(
        select(
            AllCloudResource.region, func.count(AllCloudResource.id).label("count")
        )
        .where(AllCloudResource.cloud_account_id == cloud_account_id)
        .group_by(AllCloudResource.region)
    )
    by_region = {row[0]: row[1] for row in by_region_result.all()}

    # By utilization
    by_utilization_result = await db.execute(
        select(
            AllCloudResource.utilization_status,
            func.count(AllCloudResource.id).label("count"),
        )
        .where(AllCloudResource.cloud_account_id == cloud_account_id)
        .group_by(AllCloudResource.utilization_status)
    )
    by_utilization = {row[0]: row[1] for row in by_utilization_result.all()}

    # Optimizable count
    optimizable_result = await db.execute(
        select(func.count(AllCloudResource.id)).where(
            and_(
                AllCloudResource.cloud_account_id == cloud_account_id,
                AllCloudResource.is_optimizable == True,
            )
        )
    )
    optimizable_count = optimizable_result.scalar_one()

    # High-cost resources count (>$100/month)
    high_cost_result = await db.execute(
        select(func.count(AllCloudResource.id)).where(
            and_(
                AllCloudResource.cloud_account_id == cloud_account_id,
                AllCloudResource.estimated_monthly_cost >= 100.0,
            )
        )
    )
    high_cost_count = high_cost_result.scalar_one()

    return {
        "total_resources": total_count or 0,
        "total_monthly_cost": float(total_cost or 0.0),
        "total_annual_cost": float((total_cost or 0.0) * 12),
        "by_type": by_type,
        "by_region": by_region,
        "by_utilization": by_utilization,
        "optimizable_resources": optimizable_count or 0,
        "potential_monthly_savings": float(total_savings or 0.0),
        "potential_annual_savings": float((total_savings or 0.0) * 12),
        "high_cost_resources": high_cost_count or 0,
    }


async def get_cost_breakdown(
    db: AsyncSession, cloud_account_id: uuid.UUID
) -> dict[str, list[dict[str, Any]]]:
    """
    Get detailed cost breakdown by type, region, and tags.

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID

    Returns:
        Dictionary with cost breakdown by various dimensions
    """
    # By type
    by_type_result = await db.execute(
        select(
            AllCloudResource.resource_type,
            func.count(AllCloudResource.id).label("count"),
            func.sum(AllCloudResource.estimated_monthly_cost).label("total_cost"),
        )
        .where(AllCloudResource.cloud_account_id == cloud_account_id)
        .group_by(AllCloudResource.resource_type)
        .order_by(func.sum(AllCloudResource.estimated_monthly_cost).desc())
    )
    by_type = [
        {
            "resource_type": row[0],
            "count": row[1],
            "total_monthly_cost": float(row[2] or 0.0),
        }
        for row in by_type_result.all()
    ]

    # By region
    by_region_result = await db.execute(
        select(
            AllCloudResource.region,
            func.count(AllCloudResource.id).label("count"),
            func.sum(AllCloudResource.estimated_monthly_cost).label("total_cost"),
        )
        .where(AllCloudResource.cloud_account_id == cloud_account_id)
        .group_by(AllCloudResource.region)
        .order_by(func.sum(AllCloudResource.estimated_monthly_cost).desc())
    )
    by_region = [
        {
            "region": row[0],
            "count": row[1],
            "total_monthly_cost": float(row[2] or 0.0),
        }
        for row in by_region_result.all()
    ]

    return {
        "by_type": by_type,
        "by_region": by_region,
    }


async def delete_resources_by_scan(db: AsyncSession, scan_id: uuid.UUID) -> int:
    """
    Delete all resources for a specific scan.

    Args:
        db: Database session
        scan_id: Scan UUID

    Returns:
        Number of deleted resources
    """
    result = await db.execute(
        select(AllCloudResource).where(AllCloudResource.scan_id == scan_id)
    )
    resources = result.scalars().all()
    count = len(resources)

    for resource in resources:
        await db.delete(resource)

    await db.commit()
    return count
