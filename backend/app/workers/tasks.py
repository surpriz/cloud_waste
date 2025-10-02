"""Celery background tasks for cloud resource scanning."""

import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import credential_encryption
from app.crud import cloud_account as cloud_account_crud
from app.models.cloud_account import CloudAccount
from app.models.orphan_resource import OrphanResource
from app.models.scan import Scan, ScanStatus
from app.providers.aws import AWSProvider
from app.workers.celery_app import celery_app

# Create async engine for database operations
engine = create_async_engine(str(settings.DATABASE_URL), echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False  # type: ignore
)


async def get_db_session() -> AsyncSession:
    """Get database session for async operations."""
    async with AsyncSessionLocal() as session:
        return session


@celery_app.task(name="app.workers.tasks.scan_cloud_account", bind=True)
def scan_cloud_account(self: Any, scan_id: str, cloud_account_id: str) -> dict[str, Any]:
    """
    Scan a cloud account for orphaned resources.

    Args:
        scan_id: UUID of the scan job
        cloud_account_id: UUID of the cloud account to scan

    Returns:
        Dict with scan results
    """
    # Get or create event loop for Celery solo pool
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_scan_cloud_account_async(self, scan_id, cloud_account_id))


async def _scan_cloud_account_async(
    task: Any, scan_id: str, cloud_account_id: str
) -> dict[str, Any]:
    """
    Async implementation of cloud account scanning.

    Args:
        task: Celery task instance
        scan_id: UUID of the scan job
        cloud_account_id: UUID of the cloud account to scan

    Returns:
        Dict with scan results
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get scan record
            result = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = result.scalar_one_or_none()

            if not scan:
                return {"error": f"Scan {scan_id} not found"}

            # Update scan status to in_progress
            scan.status = ScanStatus.IN_PROGRESS.value
            scan.started_at = datetime.now()
            await db.commit()

            # Get cloud account
            result = await db.execute(
                select(CloudAccount).where(CloudAccount.id == cloud_account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                scan.status = ScanStatus.FAILED.value
                scan.error_message = f"Cloud account {cloud_account_id} not found"
                scan.completed_at = datetime.now()
                await db.commit()
                return {"error": scan.error_message}

            # Decrypt credentials
            credentials_json = credential_encryption.decrypt(
                account.credentials_encrypted
            )
            credentials = json.loads(credentials_json)

            # Get user's detection rules
            from app.crud import detection_rule as detection_rule_crud
            user_detection_rules = {}
            user_rules = await detection_rule_crud.get_user_rules(db, account.user_id)
            for rule in user_rules:
                user_detection_rules[rule.resource_type] = rule.rules

            # Initialize provider based on account type
            if account.provider == "aws":
                provider = AWSProvider(
                    access_key=credentials["access_key_id"],
                    secret_key=credentials["secret_access_key"],
                    regions=account.regions if account.regions else None,
                )

                # Validate credentials
                await provider.validate_credentials()

                # Get regions to scan
                regions_to_scan = (
                    account.regions
                    if account.regions
                    else await provider.get_available_regions()
                )

                # Limit to first 3 regions for faster scanning in MVP
                regions_to_scan = regions_to_scan[:3]

                # Scan all regions
                all_orphans = []
                total_resources = 0

                for i, region in enumerate(regions_to_scan):
                    # Update task progress
                    task.update_state(
                        state="PROGRESS",
                        meta={
                            "current": i + 1,
                            "total": len(regions_to_scan),
                            "region": region,
                        },
                    )

                    # Scan all resource types in this region
                    # Pass user's detection rules
                    orphans = await provider.scan_all_resources(region, user_detection_rules)
                    all_orphans.extend(orphans)
                    total_resources += len(orphans)

                # Save orphan resources to database
                for orphan in all_orphans:
                    orphan_resource = OrphanResource(
                        scan_id=scan.id,
                        cloud_account_id=account.id,
                        resource_type=orphan.resource_type,
                        resource_id=orphan.resource_id,
                        resource_name=orphan.resource_name,
                        region=orphan.region,
                        estimated_monthly_cost=orphan.estimated_monthly_cost,
                        resource_metadata=orphan.resource_metadata,
                    )
                    db.add(orphan_resource)

                # Calculate total waste
                total_waste = sum(o.estimated_monthly_cost for o in all_orphans)

                # Update scan with results
                scan.status = ScanStatus.COMPLETED.value
                scan.total_resources_scanned = total_resources
                scan.orphan_resources_found = len(all_orphans)
                scan.estimated_monthly_waste = total_waste
                scan.completed_at = datetime.now()

                # Update account last_scan_at
                account.last_scan_at = datetime.now()

                await db.commit()

                return {
                    "scan_id": str(scan.id),
                    "status": "completed",
                    "total_resources_scanned": total_resources,
                    "orphan_resources_found": len(all_orphans),
                    "estimated_monthly_waste": total_waste,
                    "regions_scanned": regions_to_scan,
                }

            else:
                scan.status = ScanStatus.FAILED.value
                scan.error_message = f"Unsupported provider: {account.provider}"
                scan.completed_at = datetime.now()
                await db.commit()
                return {"error": scan.error_message}

        except Exception as e:
            # Try to update scan with error if scan was retrieved
            try:
                result = await db.execute(select(Scan).where(Scan.id == scan_id))
                scan = result.scalar_one_or_none()
                if scan:
                    scan.status = ScanStatus.FAILED.value
                    scan.error_message = str(e)[:500]  # Limit error message length
                    scan.completed_at = datetime.now()
                    await db.commit()
            except Exception:
                pass  # If we can't update the scan, just return the error

            return {
                "error": str(e),
                "scan_id": scan_id,
                "status": "failed",
            }


@celery_app.task(name="app.workers.tasks.scheduled_scan_all_accounts")
def scheduled_scan_all_accounts() -> dict[str, Any]:
    """
    Scheduled task to scan all active cloud accounts.

    Runs daily via Celery Beat scheduler.

    Returns:
        Dict with task results
    """
    # Get or create event loop for Celery solo pool
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_scheduled_scan_all_accounts_async())


async def _scheduled_scan_all_accounts_async() -> dict[str, Any]:
    """
    Async implementation of scheduled scan for all accounts.

    Returns:
        Dict with task results
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get all active cloud accounts
            result = await db.execute(
                select(CloudAccount).where(CloudAccount.is_active == True)  # noqa: E712
            )
            accounts = result.scalars().all()

            scans_created = []

            for account in accounts:
                # Create scan record
                scan = Scan(
                    cloud_account_id=account.id,
                    scan_type="scheduled",
                    status=ScanStatus.PENDING.value,
                )
                db.add(scan)
                await db.commit()
                await db.refresh(scan)

                # Queue scan task
                scan_cloud_account.delay(str(scan.id), str(account.id))
                scans_created.append(str(scan.id))

            return {
                "status": "success",
                "accounts_scanned": len(accounts),
                "scans_created": scans_created,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
