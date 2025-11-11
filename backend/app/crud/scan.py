"""CRUD operations for scans."""

import uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.scan import Scan, ScanStatus
from app.schemas.scan import ScanCreate, ScanUpdate


async def create_scan(db: AsyncSession, scan_in: ScanCreate) -> Scan:
    """
    Create a new scan job.

    Args:
        db: Database session
        scan_in: Scan creation data

    Returns:
        Created scan object
    """
    scan = Scan(
        cloud_account_id=scan_in.cloud_account_id,
        scan_type=scan_in.scan_type.value,
        status=ScanStatus.PENDING.value,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan


async def get_scan_by_id(
    db: AsyncSession, scan_id: uuid.UUID, load_resources: bool = False
) -> Scan | None:
    """
    Get scan by ID.

    Args:
        db: Database session
        scan_id: Scan UUID
        load_resources: Whether to eagerly load orphan resources

    Returns:
        Scan object or None if not found
    """
    query = select(Scan).where(Scan.id == scan_id)

    if load_resources:
        query = query.options(selectinload(Scan.orphan_resources))

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_scans_by_account(
    db: AsyncSession,
    cloud_account_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[Scan]:
    """
    Get scans for a specific cloud account.

    Args:
        db: Database session
        cloud_account_id: Cloud account UUID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of scan objects
    """
    result = await db.execute(
        select(Scan)
        .where(Scan.cloud_account_id == cloud_account_id)
        .order_by(desc(Scan.created_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_scans_by_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[Scan]:
    """
    Get all scans for a user's cloud accounts.

    Args:
        db: Database session
        user_id: User UUID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of scan objects
    """
    from app.models.cloud_account import CloudAccount

    result = await db.execute(
        select(Scan)
        .join(CloudAccount)
        .where(CloudAccount.user_id == user_id)
        .order_by(desc(Scan.created_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_scan(
    db: AsyncSession, scan_id: uuid.UUID, scan_update: ScanUpdate
) -> Scan | None:
    """
    Update a scan.

    Args:
        db: Database session
        scan_id: Scan UUID
        scan_update: Scan update data

    Returns:
        Updated scan object or None if not found
    """
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()

    if not scan:
        return None

    update_data = scan_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scan, field, value)

    await db.commit()
    await db.refresh(scan)
    return scan


async def get_scan_statistics(
    db: AsyncSession,
    cloud_account_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, int | float]:
    """
    Get scan statistics.

    Args:
        db: Database session
        cloud_account_id: Optional cloud account UUID to filter by
        user_id: Optional user UUID to filter by (SECURITY: prevents data leaks)

    Returns:
        Dictionary with scan statistics
    """
    from app.models.cloud_account import CloudAccount

    query = select(Scan)

    # SECURITY: Filter by user_id to prevent cross-user data leakage
    if user_id:
        query = query.join(CloudAccount, Scan.cloud_account_id == CloudAccount.id).where(
            CloudAccount.user_id == user_id
        )

    if cloud_account_id:
        query = query.where(Scan.cloud_account_id == cloud_account_id)

    result = await db.execute(query)
    scans = result.scalars().all()

    completed_scans = [s for s in scans if s.status == ScanStatus.COMPLETED.value]
    failed_scans = [s for s in scans if s.status == ScanStatus.FAILED.value]

    total_orphan_resources = sum(s.orphan_resources_found for s in completed_scans)
    total_monthly_waste = sum(s.estimated_monthly_waste for s in completed_scans)

    last_scan = None
    if completed_scans:
        last_scan = max(
            (s.completed_at for s in completed_scans if s.completed_at), default=None
        )

    return {
        "total_scans": len(scans),
        "completed_scans": len(completed_scans),
        "failed_scans": len(failed_scans),
        "total_orphan_resources": total_orphan_resources,
        "total_monthly_waste": round(total_monthly_waste, 2),
        "last_scan_at": last_scan,
    }


async def delete_scan(db: AsyncSession, scan_id: uuid.UUID) -> bool:
    """
    Delete a scan and all its associated orphan resources.

    Args:
        db: Database session
        scan_id: Scan UUID

    Returns:
        True if deleted, False if not found
    """
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()

    if not scan:
        return False

    await db.delete(scan)
    await db.commit()
    return True


async def delete_all_scans_by_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Delete all scans for a user's cloud accounts.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        Number of scans deleted
    """
    from app.models.cloud_account import CloudAccount

    # Get all scans for the user's accounts
    result = await db.execute(
        select(Scan)
        .join(CloudAccount)
        .where(CloudAccount.user_id == user_id)
    )
    scans = result.scalars().all()

    # Delete all scans
    for scan in scans:
        await db.delete(scan)

    await db.commit()
    return len(scans)
