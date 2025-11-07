"""
ML Data Collection Service.

Collects anonymized data from scans for ML training when user has given consent.
All data is anonymized to protect user privacy and comply with GDPR.
"""

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloud_account import CloudAccount
from app.models.cloudwatch_metrics_history import CloudWatchMetricsHistory
from app.models.cost_trend_data import CostTrendData
from app.models.ml_training_data import MLTrainingData
from app.models.orphan_resource import OrphanResource
from app.models.resource_lifecycle_event import ResourceLifecycleEvent
from app.models.scan import Scan
from app.models.user import User
from app.services.ml_anonymization import (
    anonymize_account_id,
    anonymize_metrics,
    anonymize_region,
    anonymize_resource_config,
    anonymize_resource_id,
    calculate_resource_age_days,
)


async def collect_ml_training_data(
    scan: Scan,
    orphan_resources: List[OrphanResource],
    user: User,
    db: AsyncSession,
) -> int:
    """
    Collect anonymized ML training data from scan results.

    Args:
        scan: Completed scan object
        orphan_resources: List of detected orphan resources
        user: User who owns the scan
        db: Database session

    Returns:
        Number of ML training records created
    """
    # Data collection is automatic (mentioned in CGV/Terms of Service)
    # No frontend opt-in required - user agreed via CGV
    records_created = 0

    for resource in orphan_resources:
        try:
            # Extract metadata
            metadata = resource.resource_metadata or {}

            # Calculate resource age
            created_date = metadata.get("created_date")
            resource_age = calculate_resource_age_days(created_date)

            # Get detection scenario and confidence
            detection_scenario = metadata.get("detection_scenario", "unknown")
            confidence_level = metadata.get("confidence", "medium")

            # Anonymize metrics
            raw_metrics = metadata.get("cloudwatch_metrics", {})
            anonymized_metrics = anonymize_metrics(raw_metrics)

            # Anonymize resource config
            anonymized_config = anonymize_resource_config(metadata)

            # Get cloud account
            result = await db.execute(
                select(CloudAccount).where(CloudAccount.id == resource.cloud_account_id)
            )
            account = result.scalar_one_or_none()
            if not account:
                continue

            # Create ML training record
            ml_record = MLTrainingData(
                resource_type=resource.resource_type,
                provider=account.provider,
                region_anonymized=anonymize_region(resource.region),
                resource_age_days=resource_age,
                detection_scenario=detection_scenario,
                metrics_summary=anonymized_metrics,
                cost_monthly=resource.estimated_monthly_cost,
                confidence_level=confidence_level,
                user_action=None,  # Will be set later when user takes action
                resource_config=anonymized_config,
                detected_at=resource.created_at,
            )

            db.add(ml_record)
            records_created += 1

            # Also create lifecycle event
            await collect_resource_lifecycle_event(
                resource=resource,
                account=account,
                event_type="detected",
                db=db,
            )

            # Collect CloudWatch metrics history if available
            if raw_metrics:
                await collect_cloudwatch_metrics_history(
                    resource=resource,
                    account=account,
                    metrics=raw_metrics,
                    db=db,
                )

        except Exception as e:
            # Log error but continue processing other resources
            print(f"Error collecting ML data for resource {resource.id}: {e}")
            continue

    if records_created > 0:
        await db.commit()

    return records_created


async def collect_resource_lifecycle_event(
    resource: OrphanResource,
    account: CloudAccount,
    event_type: str,
    db: AsyncSession,
    event_metadata: Dict[str, Any] | None = None,
) -> None:
    """
    Record a lifecycle event for a resource.

    Args:
        resource: The orphan resource
        account: Cloud account the resource belongs to
        event_type: Type of event (detected, status_changed, deleted, etc.)
        db: Database session
        event_metadata: Optional additional metadata about the event
    """
    try:
        # Get resource metadata
        metadata = resource.resource_metadata or {}

        # Calculate resource age
        created_date = metadata.get("created_date")
        resource_age = calculate_resource_age_days(created_date)

        # Anonymize metrics snapshot
        raw_metrics = metadata.get("cloudwatch_metrics", {})
        anonymized_metrics = anonymize_metrics(raw_metrics)

        # Create lifecycle event
        lifecycle_event = ResourceLifecycleEvent(
            resource_hash=anonymize_resource_id(resource.resource_id),
            resource_type=resource.resource_type,
            provider=account.provider,
            region_anonymized=anonymize_region(resource.region),
            event_type=event_type,
            age_at_event_days=resource_age,
            cost_at_event=resource.estimated_monthly_cost,
            metrics_snapshot=anonymized_metrics,
            event_metadata=event_metadata or {},
            event_timestamp=datetime.now(),
        )

        db.add(lifecycle_event)
        await db.commit()

    except Exception as e:
        print(f"Error collecting lifecycle event for resource {resource.id}: {e}")
        # Don't raise - this is non-critical


async def collect_cloudwatch_metrics_history(
    resource: OrphanResource,
    account: CloudAccount,
    metrics: Dict[str, Any],
    db: AsyncSession,
) -> None:
    """
    Store extended CloudWatch metrics history for time-series analysis.

    Args:
        resource: The orphan resource
        account: Cloud account
        metrics: Raw CloudWatch metrics dictionary
        db: Database session
    """
    try:
        # Get time range from metadata
        metadata = resource.resource_metadata or {}
        period_days = metadata.get("metrics_period_days", 30)

        end_date = datetime.now()
        start_date = datetime.fromtimestamp(end_date.timestamp() - (period_days * 86400))

        # Process each metric
        for metric_name, metric_data in metrics.items():
            if not isinstance(metric_data, dict):
                continue

            # Anonymize metric values
            anonymized_values = {
                "timeseries": metric_data.get("timeseries", []),
                "avg": metric_data.get("avg"),
                "p50": metric_data.get("p50"),
                "p95": metric_data.get("p95"),
                "p99": metric_data.get("p99"),
                "min": metric_data.get("min"),
                "max": metric_data.get("max"),
                "trend": metric_data.get("trend", "unknown"),
            }

            # Remove None values
            anonymized_values = {k: v for k, v in anonymized_values.items() if v is not None}

            # Create metrics history record
            metrics_history = CloudWatchMetricsHistory(
                resource_type=resource.resource_type,
                provider=account.provider,
                region_anonymized=anonymize_region(resource.region),
                metric_name=metric_name,
                metric_values=anonymized_values,
                aggregation_period="daily",
                start_date=start_date,
                end_date=end_date,
                collected_at=datetime.now(),
            )

            db.add(metrics_history)

        await db.commit()

    except Exception as e:
        print(f"Error collecting metrics history for resource {resource.id}: {e}")
        # Don't raise - this is non-critical


async def aggregate_monthly_cost_trends(
    cloud_account: CloudAccount,
    month: str,  # Format: YYYY-MM
    scan: Scan,
    orphan_resources: List[OrphanResource],
    db: AsyncSession,
) -> None:
    """
    Aggregate cost trends for a cloud account for a specific month.

    Args:
        cloud_account: The cloud account
        month: Month in YYYY-MM format
        scan: The scan that was just completed
        orphan_resources: List of orphan resources found in scan
        db: Database session
    """
    try:
        # Calculate waste by resource type
        waste_by_type: Dict[str, float] = {}
        regional_breakdown: Dict[str, float] = {}

        for resource in orphan_resources:
            # Aggregate by type
            if resource.resource_type not in waste_by_type:
                waste_by_type[resource.resource_type] = 0
            waste_by_type[resource.resource_type] += resource.estimated_monthly_cost

            # Aggregate by region (anonymized)
            region = anonymize_region(resource.region)
            if region not in regional_breakdown:
                regional_breakdown[region] = 0
            regional_breakdown[region] += resource.estimated_monthly_cost

        # Check if record already exists for this month
        account_hash = anonymize_account_id(str(cloud_account.id))

        result = await db.execute(
            select(CostTrendData).where(
                CostTrendData.account_hash == account_hash,
                CostTrendData.month == month,
                CostTrendData.provider == cloud_account.provider,
            )
        )
        existing_record = result.scalar_one_or_none()

        if existing_record:
            # Update existing record
            existing_record.waste_detected = scan.estimated_monthly_waste
            existing_record.waste_percentage = (
                (scan.estimated_monthly_waste / existing_record.total_spend * 100)
                if existing_record.total_spend > 0
                else 0
            )
            existing_record.top_waste_categories = waste_by_type
            existing_record.total_resources_scanned = float(scan.total_resources_scanned)
            existing_record.orphan_resources_found = float(scan.orphan_resources_found)
            existing_record.regional_breakdown = regional_breakdown
            existing_record.scan_count = float(existing_record.scan_count) + 1.0
        else:
            # Create new record
            # Note: total_spend would need to come from AWS Cost Explorer or similar
            # For now, we estimate it based on waste percentage
            estimated_total_spend = scan.estimated_monthly_waste * 10  # Assume waste is ~10% of total

            cost_trend = CostTrendData(
                account_hash=account_hash,
                month=month,
                provider=cloud_account.provider,
                total_spend=estimated_total_spend,
                waste_detected=scan.estimated_monthly_waste,
                waste_eliminated=0.0,  # Will be updated when users delete resources
                waste_percentage=(
                    (scan.estimated_monthly_waste / estimated_total_spend * 100)
                    if estimated_total_spend > 0
                    else 0
                ),
                top_waste_categories=waste_by_type,
                total_resources_scanned=float(scan.total_resources_scanned),
                orphan_resources_found=float(scan.orphan_resources_found),
                regional_breakdown=regional_breakdown,
                scan_count=1.0,
            )
            db.add(cost_trend)

        await db.commit()

    except Exception as e:
        print(f"Error aggregating cost trends for account {cloud_account.id}: {e}")
        # Don't raise - this is non-critical


async def update_ml_training_data_with_user_action(
    resource_id: UUID,
    action: str,
    db: AsyncSession,
) -> None:
    """
    Update ML training data when user takes action on a resource.

    Args:
        resource_id: The resource UUID
        action: The action taken (deleted, ignored, kept)
        db: Database session
    """
    try:
        # Get the resource
        result = await db.execute(
            select(OrphanResource).where(OrphanResource.id == resource_id)
        )
        resource = result.scalar_one_or_none()
        if not resource:
            return

        # Find corresponding ML training record
        # Match by resource_type, detection_scenario, cost, and detected_at (within 1 hour)
        metadata = resource.resource_metadata or {}
        detection_scenario = metadata.get("detection_scenario", "unknown")

        result = await db.execute(
            select(MLTrainingData).where(
                MLTrainingData.resource_type == resource.resource_type,
                MLTrainingData.detection_scenario == detection_scenario,
                MLTrainingData.cost_monthly == resource.estimated_monthly_cost,
                MLTrainingData.detected_at >= datetime.fromtimestamp(
                    resource.created_at.timestamp() - 3600
                ),
                MLTrainingData.detected_at <= datetime.fromtimestamp(
                    resource.created_at.timestamp() + 3600
                ),
                MLTrainingData.user_action.is_(None),  # Only update records without action
            ).limit(1)
        )
        ml_record = result.scalar_one_or_none()

        if ml_record:
            ml_record.user_action = action
            await db.commit()

    except Exception as e:
        print(f"Error updating ML training data for resource {resource_id}: {e}")
        # Don't raise - this is non-critical


async def update_cost_trend_with_eliminated_waste(
    cloud_account_id: UUID,
    month: str,
    cost_eliminated: float,
    db: AsyncSession,
) -> None:
    """
    Update cost trend data when user eliminates waste.

    Args:
        cloud_account_id: Cloud account UUID
        month: Month in YYYY-MM format
        cost_eliminated: Amount of monthly cost eliminated
        db: Database session
    """
    try:
        account_hash = anonymize_account_id(str(cloud_account_id))

        result = await db.execute(
            select(CostTrendData).where(
                CostTrendData.account_hash == account_hash,
                CostTrendData.month == month,
            )
        )
        cost_trend = result.scalar_one_or_none()

        if cost_trend:
            cost_trend.waste_eliminated += cost_eliminated
            await db.commit()

    except Exception as e:
        print(f"Error updating cost trend for account {cloud_account_id}: {e}")
        # Don't raise - this is non-critical
