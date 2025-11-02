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
from app.models.user import User
from app.providers.aws import AWSProvider
from app.providers.azure import AzureProvider
from app.providers.gcp import GCPProvider
from app.providers.microsoft365 import Microsoft365Provider
from app.services.email_service import send_scan_summary_email
from app.services.pricing_service import PricingService
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
                # Create pricing service for dynamic pricing
                pricing_service = PricingService(db)

                provider = AWSProvider(
                    access_key=credentials["access_key_id"],
                    secret_key=credentials["secret_access_key"],
                    regions=account.regions if account.regions else None,
                    pricing_service=pricing_service,
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
                    # Scan global resources (S3, etc.) only in the first region (i == 0)
                    orphans = await provider.scan_all_resources(
                        region, user_detection_rules, scan_global_resources=(i == 0)
                    )
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

                # Send email notification if user has enabled notifications
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user and user.email_scan_notifications:
                    send_scan_summary_email(
                        email=user.email,
                        full_name=user.full_name or "Utilisateur",
                        account_name=account.account_name,
                        scan_type=scan.scan_type,
                        status="completed",
                        started_at=scan.started_at.strftime("%d/%m/%Y %H:%M") if scan.started_at else "N/A",
                        completed_at=scan.completed_at.strftime("%d/%m/%Y %H:%M") if scan.completed_at else "N/A",
                        total_resources_scanned=total_resources,
                        orphan_resources_found=len(all_orphans),
                        estimated_monthly_waste=total_waste,
                        regions_scanned=regions_to_scan,
                    )

                return {
                    "scan_id": str(scan.id),
                    "status": "completed",
                    "total_resources_scanned": total_resources,
                    "orphan_resources_found": len(all_orphans),
                    "estimated_monthly_waste": total_waste,
                    "regions_scanned": regions_to_scan,
                }

            elif account.provider == "azure":
                provider = AzureProvider(
                    tenant_id=credentials["tenant_id"],
                    client_id=credentials["client_id"],
                    client_secret=credentials["client_secret"],
                    subscription_id=credentials["subscription_id"],
                    regions=account.regions if account.regions else None,
                    resource_groups=account.resource_groups if account.resource_groups else None,
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
                    # Scan global resources (Storage Accounts, etc.) only in the first region (i == 0)
                    orphans = await provider.scan_all_resources(
                        region, user_detection_rules, scan_global_resources=(i == 0)
                    )
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

                # Send email notification if user has enabled notifications
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user and user.email_scan_notifications:
                    send_scan_summary_email(
                        email=user.email,
                        full_name=user.full_name or "Utilisateur",
                        account_name=account.account_name,
                        scan_type=scan.scan_type,
                        status="completed",
                        started_at=scan.started_at.strftime("%d/%m/%Y %H:%M") if scan.started_at else "N/A",
                        completed_at=scan.completed_at.strftime("%d/%m/%Y %H:%M") if scan.completed_at else "N/A",
                        total_resources_scanned=total_resources,
                        orphan_resources_found=len(all_orphans),
                        estimated_monthly_waste=total_waste,
                        regions_scanned=regions_to_scan,
                    )

                return {
                    "scan_id": str(scan.id),
                    "status": "completed",
                    "total_resources_scanned": total_resources,
                    "orphan_resources_found": len(all_orphans),
                    "estimated_monthly_waste": total_waste,
                    "regions_scanned": regions_to_scan,
                }

            elif account.provider == "gcp":
                provider = GCPProvider(
                    project_id=credentials["project_id"],
                    service_account_json=credentials["service_account_json"],
                    regions=account.regions if account.regions else None,
                )

                # Get regions to scan
                regions_to_scan = (
                    account.regions
                    if account.regions
                    else ["us-central1", "us-east1", "europe-west1"]  # Default GCP regions
                )

                # For MVP, GCP scanning returns empty list
                # Full implementation will be added in Phase 2
                all_orphans = []
                total_resources = 0

                # Update scan with results
                scan.status = ScanStatus.COMPLETED.value
                scan.total_resources_scanned = 0
                scan.orphan_resources_found = 0
                scan.estimated_monthly_waste = 0.0
                scan.completed_at = datetime.now()

                # Update account last_scan_at
                account.last_scan_at = datetime.now()

                await db.commit()

                # Send email notification if user has enabled notifications
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user and user.email_scan_notifications:
                    send_scan_summary_email(
                        email=user.email,
                        full_name=user.full_name or "Utilisateur",
                        account_name=account.account_name,
                        scan_type=scan.scan_type,
                        status="completed",
                        started_at=scan.started_at.strftime("%d/%m/%Y %H:%M") if scan.started_at else "N/A",
                        completed_at=scan.completed_at.strftime("%d/%m/%Y %H:%M") if scan.completed_at else "N/A",
                        total_resources_scanned=0,
                        orphan_resources_found=0,
                        estimated_monthly_waste=0.0,
                        regions_scanned=regions_to_scan,
                    )

                return {
                    "scan_id": str(scan.id),
                    "status": "completed",
                    "total_resources_scanned": 0,
                    "orphan_resources_found": 0,
                    "estimated_monthly_waste": 0.0,
                    "regions_scanned": regions_to_scan,
                }

            elif account.provider == "microsoft365":
                provider = Microsoft365Provider(
                    tenant_id=credentials["tenant_id"],
                    client_id=credentials["client_id"],
                    client_secret=credentials["client_secret"],
                )

                # Validate credentials
                await provider.validate_credentials()

                # Microsoft 365 is global (no regions)
                # Scan all resources globally (scan_global_resources=True)
                all_orphans = await provider.scan_all_resources(
                    region="global",
                    detection_rules=user_detection_rules,
                    scan_global_resources=True,
                )
                total_resources = len(all_orphans)

                # Save orphan resources to database
                for orphan in all_orphans:
                    orphan_resource = OrphanResource(
                        scan_id=scan.id,
                        cloud_account_id=account.id,
                        resource_type=orphan.resource_type,
                        resource_id=orphan.resource_id,
                        resource_name=orphan.resource_name,
                        region=orphan.region,  # "global" for M365
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

                # Send email notification if user has enabled notifications
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user and user.email_scan_notifications:
                    send_scan_summary_email(
                        email=user.email,
                        full_name=user.full_name or "Utilisateur",
                        account_name=account.account_name,
                        scan_type=scan.scan_type,
                        status="completed",
                        started_at=scan.started_at.strftime("%d/%m/%Y %H:%M") if scan.started_at else "N/A",
                        completed_at=scan.completed_at.strftime("%d/%m/%Y %H:%M") if scan.completed_at else "N/A",
                        total_resources_scanned=total_resources,
                        orphan_resources_found=len(all_orphans),
                        estimated_monthly_waste=total_waste,
                        regions_scanned=["global"],
                    )

                return {
                    "scan_id": str(scan.id),
                    "status": "completed",
                    "total_resources_scanned": total_resources,
                    "orphan_resources_found": len(all_orphans),
                    "estimated_monthly_waste": total_waste,
                    "regions_scanned": ["global"],
                }

            else:
                scan.status = ScanStatus.FAILED.value
                scan.error_message = f"Unsupported provider: {account.provider}"
                scan.completed_at = datetime.now()
                await db.commit()

                # Send error email notification if user has enabled notifications
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user and user.email_scan_notifications:
                    send_scan_summary_email(
                        email=user.email,
                        full_name=user.full_name or "Utilisateur",
                        account_name=account.account_name,
                        scan_type=scan.scan_type,
                        status="failed",
                        started_at=scan.started_at.strftime("%d/%m/%Y %H:%M") if scan.started_at else "N/A",
                        completed_at=scan.completed_at.strftime("%d/%m/%Y %H:%M") if scan.completed_at else "N/A",
                        error_message=scan.error_message,
                    )

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

                    # Send error email notification if user has enabled notifications
                    result = await db.execute(
                        select(CloudAccount).where(CloudAccount.id == cloud_account_id)
                    )
                    account = result.scalar_one_or_none()
                    if account:
                        result = await db.execute(select(User).where(User.id == account.user_id))
                        user = result.scalar_one_or_none()
                        if user and user.email_scan_notifications:
                            send_scan_summary_email(
                                email=user.email,
                                full_name=user.full_name or "Utilisateur",
                                account_name=account.account_name,
                                scan_type=scan.scan_type,
                                status="failed",
                                started_at=scan.started_at.strftime("%d/%m/%Y %H:%M") if scan.started_at else "N/A",
                                completed_at=scan.completed_at.strftime("%d/%m/%Y %H:%M") if scan.completed_at else "N/A",
                                error_message=scan.error_message,
                            )
            except Exception:
                pass  # If we can't update the scan, just return the error

            return {
                "error": str(e),
                "scan_id": scan_id,
                "status": "failed",
            }


@celery_app.task(name="app.workers.tasks.scan_cloud_account_scheduled")
def scan_cloud_account_scheduled(cloud_account_id: str) -> dict[str, Any]:
    """
    Scheduled task to scan a specific cloud account.

    This task is triggered by Celery Beat based on account-specific schedule settings.

    Args:
        cloud_account_id: UUID of the cloud account to scan

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

    return loop.run_until_complete(_scan_cloud_account_scheduled_async(cloud_account_id))


async def _scan_cloud_account_scheduled_async(cloud_account_id: str) -> dict[str, Any]:
    """
    Async implementation of scheduled scan for a specific account.

    Args:
        cloud_account_id: UUID of the cloud account to scan

    Returns:
        Dict with task results
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get cloud account
            result = await db.execute(
                select(CloudAccount).where(CloudAccount.id == cloud_account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                return {
                    "status": "error",
                    "error": f"Cloud account {cloud_account_id} not found",
                }

            # Check if account is active and has scheduled scans enabled
            if not account.is_active or not account.scheduled_scan_enabled:
                return {
                    "status": "skipped",
                    "message": f"Account {account.account_name} is inactive or scheduled scans disabled",
                }

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

            return {
                "status": "success",
                "account_name": account.account_name,
                "scan_id": str(scan.id),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


@celery_app.task(name="app.workers.tasks.check_and_trigger_scheduled_scans")
def check_and_trigger_scheduled_scans() -> dict[str, Any]:
    """
    Check all accounts and trigger scans for those that need it based on their schedule.

    This task runs every hour and checks if any account's scheduled scan should be triggered.

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

    return loop.run_until_complete(_check_and_trigger_scheduled_scans_async())


async def _check_and_trigger_scheduled_scans_async() -> dict[str, Any]:
    """
    Async implementation to check and trigger scheduled scans.

    Returns:
        Dict with task results
    """
    from datetime import datetime

    async with AsyncSessionLocal() as db:
        try:
            current_hour = datetime.utcnow().hour
            current_day_of_week = datetime.utcnow().weekday()  # 0 = Monday
            current_day_of_month = datetime.utcnow().day

            # Get all active accounts with scheduled scans enabled
            result = await db.execute(
                select(CloudAccount).where(
                    CloudAccount.is_active == True,  # noqa: E712
                    CloudAccount.scheduled_scan_enabled == True,  # noqa: E712
                )
            )
            accounts = result.scalars().all()

            scans_triggered = []

            for account in accounts:
                should_scan = False

                # Check if this account should be scanned now
                if account.scheduled_scan_hour != current_hour:
                    continue  # Not the right hour

                if account.scheduled_scan_frequency == "daily":
                    should_scan = True
                elif account.scheduled_scan_frequency == "weekly":
                    if account.scheduled_scan_day_of_week == current_day_of_week:
                        should_scan = True
                elif account.scheduled_scan_frequency == "monthly":
                    if account.scheduled_scan_day_of_month == current_day_of_month:
                        should_scan = True

                if should_scan:
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
                    scans_triggered.append(str(scan.id))

            return {
                "status": "success",
                "accounts_checked": len(accounts),
                "scans_triggered": len(scans_triggered),
                "scan_ids": scans_triggered,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


@celery_app.task(name="app.workers.tasks.cleanup_unverified_accounts")
def cleanup_unverified_accounts() -> dict[str, Any]:
    """
    Cleanup unverified user accounts older than configured threshold.

    This task runs daily via Celery Beat and deletes user accounts
    that have not verified their email within the configured timeframe.

    Returns:
        Dict with cleanup results
    """
    import structlog

    from app.crud import user as user_crud

    logger = structlog.get_logger()

    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _cleanup_accounts() -> dict[str, Any]:
        """Inner async function to perform cleanup."""
        async with AsyncSessionLocal() as db:
            try:
                # Get unverified users older than threshold
                users_to_delete = await user_crud.get_unverified_users_older_than(
                    db,
                    days=settings.UNVERIFIED_ACCOUNT_CLEANUP_DAYS,
                )

                deleted_count = 0
                deleted_emails = []

                # Delete each unverified user
                for user in users_to_delete:
                    try:
                        logger.info(
                            "cleanup.deleting_unverified_user",
                            user_id=str(user.id),
                            email=user.email,
                            created_at=user.created_at.isoformat(),
                        )

                        await user_crud.delete_user(db, user)
                        deleted_count += 1
                        deleted_emails.append(user.email)

                    except Exception as e:
                        logger.error(
                            "cleanup.delete_user_failed",
                            user_id=str(user.id),
                            email=user.email,
                            error=str(e),
                        )

                logger.info(
                    "cleanup.completed",
                    deleted_count=deleted_count,
                    total_checked=len(users_to_delete),
                )

                return {
                    "status": "success",
                    "deleted_count": deleted_count,
                    "total_checked": len(users_to_delete),
                    "deleted_emails": deleted_emails,
                }

            except Exception as e:
                logger.error(
                    "cleanup.error",
                    error=str(e),
                )
                return {
                    "status": "error",
                    "error": str(e),
                }

    # Run async cleanup
    return loop.run_until_complete(_cleanup_accounts())


@celery_app.task(name="app.workers.tasks.update_pricing_cache")
def update_pricing_cache() -> dict[str, Any]:
    """
    Update pricing cache from cloud provider APIs.

    This task runs daily at 2 AM to refresh pricing data from:
    - AWS Price List API (for EBS volumes, Elastic IPs, etc.)
    - Azure Retail Prices API (future)
    - GCP Cloud Billing API (future)

    Returns:
        Dict with update results
    """
    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_update_pricing_cache_async())


async def _update_pricing_cache_async() -> dict[str, Any]:
    """
    Async implementation of pricing cache update.

    Fetches prices from cloud provider APIs and stores them in the database.
    """
    import structlog

    logger = structlog.get_logger()

    async with AsyncSessionLocal() as db:
        try:
            pricing_service = PricingService(db)

            # AWS regions to fetch pricing for
            aws_regions = [
                "us-east-1",
                "us-east-2",
                "us-west-1",
                "us-west-2",
                "eu-west-1",
                "eu-west-2",
                "eu-west-3",
                "eu-central-1",
                "ap-southeast-1",
                "ap-southeast-2",
                "ap-northeast-1",
                "ap-northeast-2",
            ]

            # EBS volume types to update
            ebs_volume_types = ["ebs_gp3", "ebs_gp2", "ebs_io1", "ebs_io2", "ebs_st1", "ebs_sc1"]

            # Other AWS services
            other_services = ["elastic_ip"]

            updated_count = 0
            failed_count = 0

            # Update EBS pricing for each region
            for region in aws_regions:
                for volume_type in ebs_volume_types:
                    try:
                        # Force refresh to fetch from API
                        price = await pricing_service.get_aws_price(
                            volume_type, region, force_refresh=True
                        )
                        updated_count += 1
                        logger.info(
                            "pricing.updated",
                            provider="aws",
                            service=volume_type,
                            region=region,
                            price=price,
                        )
                    except Exception as e:
                        failed_count += 1
                        logger.error(
                            "pricing.update_failed",
                            provider="aws",
                            service=volume_type,
                            region=region,
                            error=str(e),
                        )

            # Update other service pricing (region-independent or us-east-1)
            for service in other_services:
                try:
                    price = await pricing_service.get_aws_price(
                        service, "us-east-1", force_refresh=True
                    )
                    updated_count += 1
                    logger.info(
                        "pricing.updated",
                        provider="aws",
                        service=service,
                        region="us-east-1",
                        price=price,
                    )
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        "pricing.update_failed",
                        provider="aws",
                        service=service,
                        region="us-east-1",
                        error=str(e),
                    )

            logger.info(
                "pricing.cache_update_complete",
                updated_count=updated_count,
                failed_count=failed_count,
            )

            return {
                "status": "success",
                "updated_count": updated_count,
                "failed_count": failed_count,
            }

        except Exception as e:
            logger.error(
                "pricing.cache_update_error",
                error=str(e),
            )
            return {
                "status": "error",
                "error": str(e),
            }
