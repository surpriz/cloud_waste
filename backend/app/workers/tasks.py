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
from app.services.ml_data_collector import (
    aggregate_monthly_cost_trends,
    collect_ml_training_data,
)
from app.services.pricing_service import PricingService
from app.services.inventory_scanner import AWSInventoryScanner, AzureInventoryScanner
from app.workers.celery_app import celery_app
from app.models.all_cloud_resource import AllCloudResource
from app.schemas.all_cloud_resource import AllCloudResourceCreate

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

            # Track start time for elapsed calculation
            scan_start_time = datetime.now()

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

                # Update: Validating credentials
                task.update_state(
                    state="PROGRESS",
                    meta={
                        "current": 0,
                        "total": len(regions_to_scan) + 2,
                        "percent": 0,
                        "current_step": "Validating credentials...",
                        "region": "",
                        "resources_found": 0,
                        "elapsed_seconds": 0,
                    },
                )

                for i, region in enumerate(regions_to_scan):
                    elapsed = (datetime.now() - scan_start_time).total_seconds()

                    # Update task progress
                    task.update_state(
                        state="PROGRESS",
                        meta={
                            "current": i + 1,
                            "total": len(regions_to_scan) + 2,
                            "percent": int((i + 1) / (len(regions_to_scan) + 2) * 100),
                            "current_step": f"Scanning region {region}...",
                            "region": region,
                            "resources_found": len(all_orphans),
                            "elapsed_seconds": int(elapsed),
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

                # Update: Saving results
                elapsed = (datetime.now() - scan_start_time).total_seconds()
                task.update_state(
                    state="PROGRESS",
                    meta={
                        "current": len(regions_to_scan) + 1,
                        "total": len(regions_to_scan) + 2,
                        "percent": 95,
                        "current_step": "Saving results...",
                        "region": "",
                        "resources_found": len(all_orphans),
                        "elapsed_seconds": int(elapsed),
                    },
                )

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

                # Collect ML training data if user has consented
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user:
                    try:
                        # Get orphan_resources list from database
                        orphan_resources_list = await db.execute(
                            select(OrphanResource).where(OrphanResource.scan_id == scan.id)
                        )
                        orphan_resources_from_db = list(orphan_resources_list.scalars().all())

                        # Collect ML data
                        ml_records = await collect_ml_training_data(
                            scan=scan,
                            orphan_resources=orphan_resources_from_db,
                            user=user,
                            db=db,
                        )

                        # Aggregate cost trends
                        current_month = datetime.now().strftime("%Y-%m")
                        await aggregate_monthly_cost_trends(
                            cloud_account=account,
                            month=current_month,
                            scan=scan,
                            orphan_resources=orphan_resources_from_db,
                            db=db,
                        )

                        if ml_records > 0:
                            print(f"✅ Collected {ml_records} ML training records for scan {scan.id}")
                    except Exception as e:
                        # Log but don't fail the scan
                        print(f"⚠️ ML data collection failed for scan {scan.id}: {e}")

                # ===================================================================
                # INVENTORY SCAN: Scan ALL AWS resources for cost intelligence
                # This runs in addition to orphan scanning to provide complete
                # resource visibility and optimization recommendations
                # ===================================================================
                import structlog
                logger = structlog.get_logger()

                try:
                    logger.info(
                        "inventory.scan_start",
                        account=account.account_name,
                        regions=regions_to_scan,
                    )

                    # Create inventory scanner
                    inventory_scanner = AWSInventoryScanner(provider)
                    all_inventory_resources = []

                    # Scan all regions for complete inventory
                    for i, region in enumerate(regions_to_scan):
                        logger.info(
                            "inventory.scan_region_start",
                            region=region,
                            progress=f"{i+1}/{len(regions_to_scan)}",
                        )

                        # Scan EC2 instances (all)
                        ec2_resources = await inventory_scanner.scan_ec2_instances(region)
                        all_inventory_resources.extend(ec2_resources)
                        logger.info(
                            "inventory.ec2_scanned",
                            region=region,
                            ec2_count=len(ec2_resources),
                        )

                        # Scan RDS instances (all)
                        rds_resources = await inventory_scanner.scan_rds_instances(region)
                        all_inventory_resources.extend(rds_resources)
                        logger.info(
                            "inventory.rds_scanned",
                            region=region,
                            rds_count=len(rds_resources),
                        )

                    # Scan S3 buckets (global, only once)
                    if regions_to_scan:
                        s3_resources = await inventory_scanner.scan_s3_buckets()
                        all_inventory_resources.extend(s3_resources)
                        logger.info(
                            "inventory.s3_scanned",
                            s3_count=len(s3_resources),
                        )

                    # Save all inventory resources to database
                    for resource in all_inventory_resources:
                        all_cloud_resource = AllCloudResource(
                            scan_id=scan.id,  # Same scan_id as orphan resources
                            cloud_account_id=account.id,
                            resource_type=resource.resource_type,
                            resource_id=resource.resource_id,
                            resource_name=resource.resource_name,
                            region=resource.region,
                            estimated_monthly_cost=resource.estimated_monthly_cost,
                            currency=resource.currency,
                            utilization_status=resource.utilization_status,
                            cpu_utilization_percent=resource.cpu_utilization_percent,
                            memory_utilization_percent=resource.memory_utilization_percent,
                            storage_utilization_percent=resource.storage_utilization_percent,
                            network_utilization_mbps=resource.network_utilization_mbps,
                            is_optimizable=resource.is_optimizable,
                            optimization_priority=resource.optimization_priority,
                            optimization_score=resource.optimization_score,
                            potential_monthly_savings=resource.potential_monthly_savings,
                            optimization_recommendations=resource.optimization_recommendations,
                            resource_metadata=resource.resource_metadata,
                            tags=resource.tags,
                            resource_status=resource.resource_status,
                            created_at_cloud=resource.created_at_cloud,
                        )
                        db.add(all_cloud_resource)

                    await db.commit()

                    logger.info(
                        "inventory.scan_complete",
                        total_resources=len(all_inventory_resources),
                        optimizable=sum(1 for r in all_inventory_resources if r.is_optimizable),
                        total_cost=sum(r.estimated_monthly_cost for r in all_inventory_resources),
                        potential_savings=sum(r.potential_monthly_savings or 0 for r in all_inventory_resources),
                    )

                    print(f"✅ Inventory scan complete: {len(all_inventory_resources)} resources scanned")

                except Exception as e:
                    # Log but don't fail the main scan
                    logger.error("inventory.scan_failed", error=str(e))
                    print(f"⚠️ Inventory scan failed for scan {scan.id}: {e}")

                # Send email notification if user has enabled notifications
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

                # Collect ML training data if user has consented (Azure)
                result = await db.execute(select(User).where(User.id == account.user_id))
                user = result.scalar_one_or_none()
                if user:
                    try:
                        # Get orphan_resources list from database
                        orphan_resources_list = await db.execute(
                            select(OrphanResource).where(OrphanResource.scan_id == scan.id)
                        )
                        orphan_resources_from_db = list(orphan_resources_list.scalars().all())

                        # Collect ML data
                        ml_records = await collect_ml_training_data(
                            scan=scan,
                            orphan_resources=orphan_resources_from_db,
                            user=user,
                            db=db,
                        )

                        # Aggregate cost trends
                        current_month = datetime.now().strftime("%Y-%m")
                        await aggregate_monthly_cost_trends(
                            cloud_account=account,
                            month=current_month,
                            scan=scan,
                            orphan_resources=orphan_resources_from_db,
                            db=db,
                        )

                        if ml_records > 0:
                            print(f"✅ Collected {ml_records} ML training records for scan {scan.id}")
                    except Exception as e:
                        # Log but don't fail the scan
                        print(f"⚠️ ML data collection failed for scan {scan.id}: {e}")

                # ===================================================================
                # INVENTORY SCAN: Scan ALL Azure resources for cost intelligence
                # This runs in addition to orphan scanning to provide complete
                # resource visibility and optimization recommendations
                # ===================================================================
                import structlog
                logger = structlog.get_logger()

                try:
                    logger.info(
                        "inventory.scan_start",
                        account=account.account_name,
                        regions=regions_to_scan,
                    )

                    # Create inventory scanner
                    inventory_scanner = AzureInventoryScanner(provider)
                    all_inventory_resources = []

                    # Scan all regions for complete inventory
                    for i, region in enumerate(regions_to_scan):
                        logger.info(
                            "inventory.scan_region_start",
                            region=region,
                            progress=f"{i+1}/{len(regions_to_scan)}",
                        )

                        # Scan Virtual Machines (all)
                        vm_resources = await inventory_scanner.scan_virtual_machines(region)
                        all_inventory_resources.extend(vm_resources)
                        logger.info(
                            "inventory.vm_scanned",
                            region=region,
                            vm_count=len(vm_resources),
                        )

                        # Scan Managed Disks (all)
                        disk_resources = await inventory_scanner.scan_managed_disks(region)
                        all_inventory_resources.extend(disk_resources)
                        logger.info(
                            "inventory.disk_scanned",
                            region=region,
                            disk_count=len(disk_resources),
                        )

                        # Scan Public IPs (all)
                        ip_resources = await inventory_scanner.scan_public_ips(region)
                        all_inventory_resources.extend(ip_resources)
                        logger.info(
                            "inventory.ip_scanned",
                            region=region,
                            ip_count=len(ip_resources),
                        )

                        # Scan Load Balancers (all)
                        lb_resources = await inventory_scanner.scan_load_balancers(region)
                        all_inventory_resources.extend(lb_resources)
                        logger.info(
                            "inventory.lb_scanned",
                            region=region,
                            lb_count=len(lb_resources),
                        )

                        # Scan Application Gateways (all)
                        ag_resources = await inventory_scanner.scan_app_gateways(region)
                        all_inventory_resources.extend(ag_resources)
                        logger.info(
                            "inventory.ag_scanned",
                            region=region,
                            ag_count=len(ag_resources),
                        )

                        # Scan Storage Accounts (all)
                        sa_resources = await inventory_scanner.scan_storage_accounts(region)
                        all_inventory_resources.extend(sa_resources)
                        logger.info(
                            "inventory.sa_scanned",
                            region=region,
                            sa_count=len(sa_resources),
                        )

                        # Scan ExpressRoute Circuits (all)
                        er_resources = await inventory_scanner.scan_expressroute_circuits(region)
                        all_inventory_resources.extend(er_resources)
                        logger.info(
                            "inventory.er_scanned",
                            region=region,
                            er_count=len(er_resources),
                        )

                        # Scan Disk Snapshots (all)
                        snapshot_resources = await inventory_scanner.scan_disk_snapshots(region)
                        all_inventory_resources.extend(snapshot_resources)
                        logger.info(
                            "inventory.snapshot_scanned",
                            region=region,
                            snapshot_count=len(snapshot_resources),
                        )

                        # Scan NAT Gateways (all)
                        nat_resources = await inventory_scanner.scan_nat_gateways(region)
                        all_inventory_resources.extend(nat_resources)
                        logger.info(
                            "inventory.nat_scanned",
                            region=region,
                            nat_count=len(nat_resources),
                        )

                        # Scan Azure SQL Databases (all)
                        sqldb_resources = await inventory_scanner.scan_azure_sql_databases(region)
                        all_inventory_resources.extend(sqldb_resources)
                        logger.info(
                            "inventory.sqldb_scanned",
                            region=region,
                            sqldb_count=len(sqldb_resources),
                        )

                        # Scan AKS Clusters (all)
                        aks_resources = await inventory_scanner.scan_aks_clusters(region)
                        all_inventory_resources.extend(aks_resources)
                        logger.info(
                            "inventory.aks_scanned",
                            region=region,
                            aks_count=len(aks_resources),
                        )

                        # Scan Function Apps (all)
                        function_resources = await inventory_scanner.scan_function_apps(region)
                        all_inventory_resources.extend(function_resources)
                        logger.info(
                            "inventory.functions_scanned",
                            region=region,
                            function_count=len(function_resources),
                        )

                        # Scan Cosmos DB accounts (all)
                        cosmos_resources = await inventory_scanner.scan_cosmos_dbs(region)
                        all_inventory_resources.extend(cosmos_resources)
                        logger.info(
                            "inventory.cosmos_scanned",
                            region=region,
                            cosmos_count=len(cosmos_resources),
                        )

                        # Scan Container Apps (all)
                        container_app_resources = await inventory_scanner.scan_container_apps(region)
                        all_inventory_resources.extend(container_app_resources)
                        logger.info(
                            "inventory.container_apps_scanned",
                            region=region,
                            container_app_count=len(container_app_resources),
                        )

                        # Scan Virtual Desktop host pools (all)
                        vd_resources = await inventory_scanner.scan_virtual_desktops(region)
                        all_inventory_resources.extend(vd_resources)
                        logger.info(
                            "inventory.virtual_desktops_scanned",
                            region=region,
                            vd_count=len(vd_resources),
                        )

                        # Scan HDInsight clusters (all)
                        hdinsight_resources = await inventory_scanner.scan_hdinsight_clusters(region)
                        all_inventory_resources.extend(hdinsight_resources)
                        logger.info(
                            "inventory.hdinsight_scanned",
                            region=region,
                            hdinsight_count=len(hdinsight_resources),
                        )

                        # Scan ML Compute Instances (all)
                        ml_resources = await inventory_scanner.scan_ml_compute_instances(region)
                        all_inventory_resources.extend(ml_resources)
                        logger.info(
                            "inventory.ml_compute_scanned",
                            region=region,
                            ml_count=len(ml_resources),
                        )

                        # Scan App Services (all, excluding Function Apps)
                        app_service_resources = await inventory_scanner.scan_app_services(region)
                        all_inventory_resources.extend(app_service_resources)
                        logger.info(
                            "inventory.app_services_scanned",
                            region=region,
                            app_service_count=len(app_service_resources),
                        )

                        # Scan Redis Caches (all)
                        redis_resources = await inventory_scanner.scan_redis_caches(region)
                        all_inventory_resources.extend(redis_resources)
                        logger.info(
                            "inventory.redis_scanned",
                            region=region,
                            redis_count=len(redis_resources),
                        )

                        # Scan Event Hubs (all)
                        event_hub_resources = await inventory_scanner.scan_event_hubs(region)
                        all_inventory_resources.extend(event_hub_resources)
                        logger.info(
                            "inventory.event_hubs_scanned",
                            region=region,
                            event_hub_count=len(event_hub_resources),
                        )

                        # Scan NetApp Files (all)
                        netapp_resources = await inventory_scanner.scan_netapp_files(region)
                        all_inventory_resources.extend(netapp_resources)
                        logger.info(
                            "inventory.netapp_scanned",
                            region=region,
                            netapp_count=len(netapp_resources),
                        )

                        # Scan Cognitive Search (all)
                        cognitive_search_resources = await inventory_scanner.scan_cognitive_search(region)
                        all_inventory_resources.extend(cognitive_search_resources)
                        logger.info(
                            "inventory.cognitive_search_scanned",
                            region=region,
                            cognitive_search_count=len(cognitive_search_resources),
                        )

                        # Scan API Management (all)
                        apim_resources = await inventory_scanner.scan_api_management(region)
                        all_inventory_resources.extend(apim_resources)
                        logger.info(
                            "inventory.api_management_scanned",
                            region=region,
                            apim_count=len(apim_resources),
                        )

                        # Scan CDN (all)
                        cdn_resources = await inventory_scanner.scan_cdn(region)
                        all_inventory_resources.extend(cdn_resources)
                        logger.info(
                            "inventory.cdn_scanned",
                            region=region,
                            cdn_count=len(cdn_resources),
                        )

                        # Scan Container Instances (all)
                        aci_resources = await inventory_scanner.scan_container_instances(region)
                        all_inventory_resources.extend(aci_resources)
                        logger.info(
                            "inventory.container_instances_scanned",
                            region=region,
                            aci_count=len(aci_resources),
                        )

                        # Scan Logic Apps (all)
                        logic_app_resources = await inventory_scanner.scan_logic_apps(region)
                        all_inventory_resources.extend(logic_app_resources)
                        logger.info(
                            "inventory.logic_apps_scanned",
                            region=region,
                            logic_app_count=len(logic_app_resources),
                        )

                        # Scan Log Analytics Workspaces (all)
                        log_analytics_resources = await inventory_scanner.scan_log_analytics(region)
                        all_inventory_resources.extend(log_analytics_resources)
                        logger.info(
                            "inventory.log_analytics_scanned",
                            region=region,
                            log_analytics_count=len(log_analytics_resources),
                        )

                        # Scan Backup Vaults (all)
                        backup_vault_resources = await inventory_scanner.scan_backup_vaults(region)
                        all_inventory_resources.extend(backup_vault_resources)
                        logger.info(
                            "inventory.backup_vaults_scanned",
                            region=region,
                            backup_vault_count=len(backup_vault_resources),
                        )

                        # Scan Data Factory Pipelines (all)
                        data_factory_resources = await inventory_scanner.scan_data_factory_pipelines(region)
                        all_inventory_resources.extend(data_factory_resources)
                        logger.info(
                            "inventory.data_factory_scanned",
                            region=region,
                            data_factory_count=len(data_factory_resources),
                        )

                        # Scan Synapse Serverless SQL (all)
                        synapse_resources = await inventory_scanner.scan_synapse_serverless_sql(region)
                        all_inventory_resources.extend(synapse_resources)
                        logger.info(
                            "inventory.synapse_serverless_scanned",
                            region=region,
                            synapse_count=len(synapse_resources),
                        )

                        # Scan Storage SFTP (all)
                        sftp_resources = await inventory_scanner.scan_storage_sftp(region)
                        all_inventory_resources.extend(sftp_resources)
                        logger.info(
                            "inventory.storage_sftp_scanned",
                            region=region,
                            sftp_count=len(sftp_resources),
                        )

                        # Scan AD Domain Services (all)
                        ad_domain_resources = await inventory_scanner.scan_ad_domain_services(region)
                        all_inventory_resources.extend(ad_domain_resources)
                        logger.info(
                            "inventory.ad_domain_services_scanned",
                            region=region,
                            ad_domain_count=len(ad_domain_resources),
                        )

                        # Scan Service Bus Premium (all)
                        service_bus_resources = await inventory_scanner.scan_service_bus_premium(region)
                        all_inventory_resources.extend(service_bus_resources)
                        logger.info(
                            "inventory.service_bus_premium_scanned",
                            region=region,
                            service_bus_count=len(service_bus_resources),
                        )

                        # Scan IoT Hub (all)
                        iot_hub_resources = await inventory_scanner.scan_iot_hub(region)
                        all_inventory_resources.extend(iot_hub_resources)
                        logger.info(
                            "inventory.iot_hub_scanned",
                            region=region,
                            iot_hub_count=len(iot_hub_resources),
                        )

                        # Scan Stream Analytics (all)
                        stream_analytics_resources = await inventory_scanner.scan_stream_analytics(region)
                        all_inventory_resources.extend(stream_analytics_resources)
                        logger.info(
                            "inventory.stream_analytics_scanned",
                            region=region,
                            stream_analytics_count=len(stream_analytics_resources),
                        )

                        # Scan Document Intelligence (all)
                        document_intelligence_resources = await inventory_scanner.scan_ai_document_intelligence(region)
                        all_inventory_resources.extend(document_intelligence_resources)
                        logger.info(
                            "inventory.document_intelligence_scanned",
                            region=region,
                            document_intelligence_count=len(document_intelligence_resources),
                        )

                        # Scan Computer Vision (all)
                        computer_vision_resources = await inventory_scanner.scan_computer_vision(region)
                        all_inventory_resources.extend(computer_vision_resources)
                        logger.info(
                            "inventory.computer_vision_scanned",
                            region=region,
                            computer_vision_count=len(computer_vision_resources),
                        )

                        # Scan Face API (all)
                        face_api_resources = await inventory_scanner.scan_face_api(region)
                        all_inventory_resources.extend(face_api_resources)
                        logger.info(
                            "inventory.face_api_scanned",
                            region=region,
                            face_api_count=len(face_api_resources),
                        )

                        # Scan Text Analytics (all)
                        text_analytics_resources = await inventory_scanner.scan_text_analytics(region)
                        all_inventory_resources.extend(text_analytics_resources)
                        logger.info(
                            "inventory.text_analytics_scanned",
                            region=region,
                            text_analytics_count=len(text_analytics_resources),
                        )

                        # Scan Speech Services (all)
                        speech_services_resources = await inventory_scanner.scan_speech_services(region)
                        all_inventory_resources.extend(speech_services_resources)
                        logger.info(
                            "inventory.speech_services_scanned",
                            region=region,
                            speech_services_count=len(speech_services_resources),
                        )

                        # Scan Bot Service (all)
                        bot_service_resources = await inventory_scanner.scan_bot_service(region)
                        all_inventory_resources.extend(bot_service_resources)
                        logger.info(
                            "inventory.bot_service_scanned",
                            region=region,
                            bot_service_count=len(bot_service_resources),
                        )

                        # Scan Application Insights (all)
                        application_insights_resources = await inventory_scanner.scan_application_insights(region)
                        all_inventory_resources.extend(application_insights_resources)
                        logger.info(
                            "inventory.application_insights_scanned",
                            region=region,
                            application_insights_count=len(application_insights_resources),
                        )

                        # Scan Managed DevOps Pools (all)
                        managed_devops_pools_resources = await inventory_scanner.scan_managed_devops_pools(region)
                        all_inventory_resources.extend(managed_devops_pools_resources)
                        logger.info(
                            "inventory.managed_devops_pools_scanned",
                            region=region,
                            managed_devops_pools_count=len(managed_devops_pools_resources),
                        )

                        # Scan Private Endpoints (all)
                        private_endpoint_resources = await inventory_scanner.scan_private_endpoints(region)
                        all_inventory_resources.extend(private_endpoint_resources)
                        logger.info(
                            "inventory.private_endpoints_scanned",
                            region=region,
                            private_endpoint_count=len(private_endpoint_resources),
                        )

                        # Scan ML Endpoints (all)
                        ml_endpoint_resources = await inventory_scanner.scan_ml_endpoints(region)
                        all_inventory_resources.extend(ml_endpoint_resources)
                        logger.info(
                            "inventory.ml_endpoints_scanned",
                            region=region,
                            ml_endpoint_count=len(ml_endpoint_resources),
                        )

                        # Scan Synapse SQL Pools (all)
                        synapse_sql_pool_resources = await inventory_scanner.scan_synapse_sql_pools(region)
                        all_inventory_resources.extend(synapse_sql_pool_resources)
                        logger.info(
                            "inventory.synapse_sql_pools_scanned",
                            region=region,
                            synapse_sql_pool_count=len(synapse_sql_pool_resources),
                        )

                        # Scan VPN Gateways (all)
                        vpn_gateway_resources = await inventory_scanner.scan_vpn_gateways(region)
                        all_inventory_resources.extend(vpn_gateway_resources)
                        logger.info(
                            "inventory.vpn_gateways_scanned",
                            region=region,
                            vpn_gateway_count=len(vpn_gateway_resources),
                        )

                        # Scan VNet Peerings (all)
                        vnet_peering_resources = await inventory_scanner.scan_vnet_peerings(region)
                        all_inventory_resources.extend(vnet_peering_resources)
                        logger.info(
                            "inventory.vnet_peerings_scanned",
                            region=region,
                            vnet_peering_count=len(vnet_peering_resources),
                        )

                        # Scan Front Doors (global - only once, not per region)
                        if region == regions[0]:  # Only scan once (Front Door is global)
                            front_door_resources = await inventory_scanner.scan_front_doors(region)
                            all_inventory_resources.extend(front_door_resources)
                            logger.info(
                                "inventory.front_doors_scanned",
                                front_door_count=len(front_door_resources),
                            )

                        # Scan Container Registries (all)
                        container_registry_resources = await inventory_scanner.scan_container_registries(region)
                        all_inventory_resources.extend(container_registry_resources)
                        logger.info(
                            "inventory.container_registries_scanned",
                            region=region,
                            container_registry_count=len(container_registry_resources),
                        )

                        # Scan Service Bus Topics (all)
                        service_bus_topic_resources = await inventory_scanner.scan_service_bus_topics(region)
                        all_inventory_resources.extend(service_bus_topic_resources)
                        logger.info(
                            "inventory.service_bus_topics_scanned",
                            region=region,
                            service_bus_topic_count=len(service_bus_topic_resources),
                        )

                        # Scan Service Bus Queues (all)
                        service_bus_queue_resources = await inventory_scanner.scan_service_bus_queues(region)
                        all_inventory_resources.extend(service_bus_queue_resources)
                        logger.info(
                            "inventory.service_bus_queues_scanned",
                            region=region,
                            service_bus_queue_count=len(service_bus_queue_resources),
                        )

                        # Scan Event Grid Subscriptions (all)
                        event_grid_sub_resources = await inventory_scanner.scan_event_grid_subscriptions(region)
                        all_inventory_resources.extend(event_grid_sub_resources)
                        logger.info(
                            "inventory.event_grid_subscriptions_scanned",
                            region=region,
                            event_grid_subscription_count=len(event_grid_sub_resources),
                        )

                        # Scan Key Vault Secrets (all)
                        key_vault_secret_resources = await inventory_scanner.scan_key_vault_secrets(region)
                        all_inventory_resources.extend(key_vault_secret_resources)
                        logger.info(
                            "inventory.key_vault_secrets_scanned",
                            region=region,
                            key_vault_secret_count=len(key_vault_secret_resources),
                        )

                        # Scan App Configuration stores (all)
                        app_config_resources = await inventory_scanner.scan_app_configurations(region)
                        all_inventory_resources.extend(app_config_resources)
                        logger.info(
                            "inventory.app_configurations_scanned",
                            region=region,
                            app_configuration_count=len(app_config_resources),
                        )

                        # Scan API Management services (all)
                        api_mgmt_resources = await inventory_scanner.scan_api_managements(region)
                        all_inventory_resources.extend(api_mgmt_resources)
                        logger.info(
                            "inventory.api_managements_scanned",
                            region=region,
                            api_management_count=len(api_mgmt_resources),
                        )

                        # Scan Logic Apps (all)
                        logic_app_resources = await inventory_scanner.scan_logic_apps(region)
                        all_inventory_resources.extend(logic_app_resources)
                        logger.info(
                            "inventory.logic_apps_scanned",
                            region=region,
                            logic_app_count=len(logic_app_resources),
                        )

                        # Scan Data Factories (all)
                        data_factory_resources = await inventory_scanner.scan_data_factories(region)
                        all_inventory_resources.extend(data_factory_resources)
                        logger.info(
                            "inventory.data_factories_scanned",
                            region=region,
                            data_factory_count=len(data_factory_resources),
                        )

                        # Scan Static Web Apps (all)
                        static_web_app_resources = await inventory_scanner.scan_static_web_apps(region)
                        all_inventory_resources.extend(static_web_app_resources)
                        logger.info(
                            "inventory.static_web_apps_scanned",
                            region=region,
                            static_web_app_count=len(static_web_app_resources),
                        )

                        # Scan Dedicated HSMs (all)
                        dedicated_hsm_resources = await inventory_scanner.scan_dedicated_hsms(region)
                        all_inventory_resources.extend(dedicated_hsm_resources)
                        logger.info(
                            "inventory.dedicated_hsms_scanned",
                            region=region,
                            dedicated_hsm_count=len(dedicated_hsm_resources),
                        )

                        # Scan IoT Hub Message Routing (all)
                        iot_hub_routing_resources = await inventory_scanner.scan_iot_hub_message_routing(region)
                        all_inventory_resources.extend(iot_hub_routing_resources)
                        logger.info(
                            "inventory.iot_hub_routing_scanned",
                            region=region,
                            iot_hub_routing_count=len(iot_hub_routing_resources),
                        )

                        # Scan ML Online Endpoints (all)
                        ml_online_endpoint_resources = await inventory_scanner.scan_ml_online_endpoints(region)
                        all_inventory_resources.extend(ml_online_endpoint_resources)
                        logger.info(
                            "inventory.ml_online_endpoints_scanned",
                            region=region,
                            ml_online_endpoint_count=len(ml_online_endpoint_resources),
                        )

                        # Scan ML Batch Endpoints (all)
                        ml_batch_endpoint_resources = await inventory_scanner.scan_ml_batch_endpoints(region)
                        all_inventory_resources.extend(ml_batch_endpoint_resources)
                        logger.info(
                            "inventory.ml_batch_endpoints_scanned",
                            region=region,
                            ml_batch_endpoint_count=len(ml_batch_endpoint_resources),
                        )

                        # Scan Automation Accounts (all)
                        automation_account_resources = await inventory_scanner.scan_automation_accounts(region)
                        all_inventory_resources.extend(automation_account_resources)
                        logger.info(
                            "inventory.automation_accounts_scanned",
                            region=region,
                            automation_account_count=len(automation_account_resources),
                        )

                        # Scan Azure Advisor Recommendations (all)
                        advisor_recommendation_resources = await inventory_scanner.scan_advisor_recommendations(region)
                        all_inventory_resources.extend(advisor_recommendation_resources)
                        logger.info(
                            "inventory.advisor_recommendations_scanned",
                            region=region,
                            advisor_recommendation_count=len(advisor_recommendation_resources),
                        )

                        # Scan ARM Template Deployments (all)
                        arm_deployment_resources = await inventory_scanner.scan_arm_deployments(region)
                        all_inventory_resources.extend(arm_deployment_resources)
                        logger.info(
                            "inventory.arm_deployments_scanned",
                            region=region,
                            arm_deployment_count=len(arm_deployment_resources),
                        )

                        # Scan Container Instances (all)
                        container_instance_resources = await inventory_scanner.scan_container_instances(region)
                        all_inventory_resources.extend(container_instance_resources)
                        logger.info(
                            "inventory.container_instances_scanned",
                            region=region,
                            container_instance_count=len(container_instance_resources),
                        )

                    # Save all inventory resources to database
                    for resource in all_inventory_resources:
                        all_cloud_resource = AllCloudResource(
                            scan_id=scan.id,  # Same scan_id as orphan resources
                            cloud_account_id=account.id,
                            resource_type=resource.resource_type,
                            resource_id=resource.resource_id,
                            resource_name=resource.resource_name,
                            region=resource.region,
                            estimated_monthly_cost=resource.estimated_monthly_cost,
                            currency=resource.currency,
                            utilization_status=resource.utilization_status,
                            cpu_utilization_percent=resource.cpu_utilization_percent,
                            memory_utilization_percent=resource.memory_utilization_percent,
                            storage_utilization_percent=resource.storage_utilization_percent,
                            network_utilization_mbps=resource.network_utilization_mbps,
                            is_optimizable=resource.is_optimizable,
                            optimization_priority=resource.optimization_priority,
                            optimization_score=resource.optimization_score,
                            potential_monthly_savings=resource.potential_monthly_savings,
                            optimization_recommendations=resource.optimization_recommendations,
                            resource_metadata=resource.resource_metadata,
                            tags=resource.tags,
                            resource_status=resource.resource_status,
                            created_at_cloud=resource.created_at_cloud,
                        )
                        db.add(all_cloud_resource)

                    await db.commit()

                    logger.info(
                        "inventory.scan_complete",
                        total_resources=len(all_inventory_resources),
                        optimizable=sum(1 for r in all_inventory_resources if r.is_optimizable),
                        total_cost=sum(r.estimated_monthly_cost for r in all_inventory_resources),
                        potential_savings=sum(r.potential_monthly_savings or 0 for r in all_inventory_resources),
                    )

                    print(f"✅ Inventory scan complete: {len(all_inventory_resources)} resources scanned")

                except Exception as e:
                    # Log but don't fail the main scan
                    logger.error("inventory.scan_failed", error=str(e))
                    print(f"⚠️ Inventory scan failed for scan {scan.id}: {e}")

                # Send email notification if user has enabled notifications
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
            # Capture exception in Sentry with context
            try:
                import sentry_sdk
                sentry_sdk.set_context("scan_details", {
                    "scan_id": scan_id,
                    "cloud_account_id": cloud_account_id,
                    "provider": account.provider if 'account' in locals() else "unknown",
                    "account_name": account.account_name if 'account' in locals() else "unknown",
                })
                sentry_sdk.capture_exception(e)
            except Exception:
                pass  # Don't fail if Sentry capture fails

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