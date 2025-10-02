"""CRUD operations for orphan resources."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orphan_resource import OrphanResource, ResourceStatus
from app.schemas.orphan_resource import OrphanResourceCreate, OrphanResourceUpdate


async def create_orphan_resource(
    db: AsyncSession, resource_in: OrphanResourceCreate
) -> OrphanResource:
    """
    Create a new orphan resource.

    Args:
        db: Database session
        resource_in: Orphan resource creation data

    Returns:
        Created orphan resource object
    """
    resource = OrphanResource(**resource_in.model_dump())
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


async def get_orphan_resource_by_id(
    db: AsyncSession, resource_id: uuid.UUID
) -> OrphanResource | None:
    """
    Get orphan resource by ID.

    Args:
        db: Database session
        resource_id: Resource UUID

    Returns:
        OrphanResource object or None if not found
    """
    result = await db.execute(
        select(OrphanResource).where(OrphanResource.id == resource_id)
    )
    return result.scalar_one_or_none()


async def get_orphan_resources_by_scan(
    db: AsyncSession,
    scan_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[OrphanResource]:
    """
    Get orphan resources for a specific scan.

    Args:
        db: Database session
        scan_id: Scan UUID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of orphan resource objects
    """
    result = await db.execute(
        select(OrphanResource)
        .where(OrphanResource.scan_id == scan_id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_orphan_resources_by_account(
    db: AsyncSession,
    cloud_account_id: uuid.UUID,
    status: ResourceStatus | None = None,
    resource_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[OrphanResource]:
    """
    Get orphan resources for a specific cloud account.

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID
        status: Optional status filter
        resource_type: Optional resource type filter
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of orphan resource objects
    """
    query = select(OrphanResource).where(
        OrphanResource.cloud_account_id == cloud_account_id
    )

    if status:
        query = query.where(OrphanResource.status == status.value)

    if resource_type:
        query = query.where(OrphanResource.resource_type == resource_type)

    result = await db.execute(query.offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_orphan_resource(
    db: AsyncSession,
    resource_id: uuid.UUID,
    resource_update: OrphanResourceUpdate,
) -> OrphanResource | None:
    """
    Update an orphan resource.

    Args:
        db: Database session
        resource_id: Resource UUID
        resource_update: Resource update data

    Returns:
        Updated orphan resource object or None if not found
    """
    result = await db.execute(
        select(OrphanResource).where(OrphanResource.id == resource_id)
    )
    resource = result.scalar_one_or_none()

    if not resource:
        return None

    update_data = resource_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and isinstance(value, ResourceStatus):
            setattr(resource, field, value.value)
        else:
            setattr(resource, field, value)

    await db.commit()
    await db.refresh(resource)
    return resource


async def delete_orphan_resource(
    db: AsyncSession, resource_id: uuid.UUID
) -> OrphanResource | None:
    """
    Delete an orphan resource.

    Args:
        db: Database session
        resource_id: Resource UUID

    Returns:
        Deleted orphan resource object or None if not found
    """
    result = await db.execute(
        select(OrphanResource).where(OrphanResource.id == resource_id)
    )
    resource = result.scalar_one_or_none()

    if resource:
        await db.delete(resource)
        await db.commit()

    return resource


async def get_orphan_resource_statistics(
    db: AsyncSession,
    cloud_account_id: uuid.UUID | None = None,
    status: ResourceStatus | None = None,
) -> dict[str, Any]:
    """
    Get orphan resource statistics.

    Args:
        db: Database session
        cloud_account_id: Optional cloud account UUID to filter by
        status: Optional status filter

    Returns:
        Dictionary with orphan resource statistics
    """
    query = select(OrphanResource)

    if cloud_account_id:
        query = query.where(OrphanResource.cloud_account_id == cloud_account_id)

    if status:
        query = query.where(OrphanResource.status == status.value)

    result = await db.execute(query)
    resources = result.scalars().all()

    # Total resources
    total_resources = len(resources)

    # By type
    by_type: dict[str, int] = {}
    for resource in resources:
        by_type[resource.resource_type] = by_type.get(resource.resource_type, 0) + 1

    # By region
    by_region: dict[str, int] = {}
    for resource in resources:
        by_region[resource.region] = by_region.get(resource.region, 0) + 1

    # By status
    by_status: dict[str, int] = {}
    for resource in resources:
        by_status[resource.status] = by_status.get(resource.status, 0) + 1

    # Total costs
    total_monthly_cost = sum(resource.estimated_monthly_cost for resource in resources)
    total_annual_cost = total_monthly_cost * 12

    return {
        "total_resources": total_resources,
        "by_type": by_type,
        "by_region": by_region,
        "by_status": by_status,
        "total_monthly_cost": round(total_monthly_cost, 2),
        "total_annual_cost": round(total_annual_cost, 2),
    }


async def get_top_cost_resources(
    db: AsyncSession,
    cloud_account_id: uuid.UUID | None = None,
    limit: int = 10,
) -> list[OrphanResource]:
    """
    Get top orphan resources by estimated monthly cost.

    Args:
        db: Database session
        cloud_account_id: Optional cloud account UUID to filter by
        limit: Maximum number of resources to return

    Returns:
        List of orphan resources sorted by cost (descending)
    """
    query = select(OrphanResource).order_by(
        OrphanResource.estimated_monthly_cost.desc()
    )

    if cloud_account_id:
        query = query.where(OrphanResource.cloud_account_id == cloud_account_id)

    result = await db.execute(query.limit(limit))
    return list(result.scalars().all())
