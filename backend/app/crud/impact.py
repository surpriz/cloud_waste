"""CRUD operations for Impact dashboard and environmental calculations."""

import uuid
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloud_account import CloudAccount
from app.models.orphan_resource import OrphanResource, ResourceStatus
from app.models.scan import Scan
from app.schemas.impact import (
    Achievement,
    ImpactSummary,
    ImpactTimeline,
    QuickStats,
    TimelineDataPoint,
    UserAchievements,
)


# Carbon intensity data (kg CO2 per kWh) by region
AWS_CARBON_INTENSITY = {
    # US Regions
    "us-east-1": 0.415,  # Virginia
    "us-east-2": 0.741,  # Ohio
    "us-west-1": 0.285,  # N. California
    "us-west-2": 0.285,  # Oregon
    # EU Regions
    "eu-west-1": 0.295,  # Ireland
    "eu-west-2": 0.283,  # London
    "eu-west-3": 0.056,  # Paris
    "eu-central-1": 0.338,  # Frankfurt
    "eu-north-1": 0.008,  # Stockholm - very low!
    # Asia Pacific
    "ap-southeast-1": 0.431,  # Singapore
    "ap-southeast-2": 0.79,  # Sydney
    "ap-northeast-1": 0.506,  # Tokyo
    "ap-northeast-2": 0.436,  # Seoul
    "ap-south-1": 0.708,  # Mumbai
    # Other
    "ca-central-1": 0.12,  # Canada (Montreal)
    "sa-east-1": 0.074,  # Sao Paulo
}

AZURE_CARBON_INTENSITY = {
    # US Regions
    "eastus": 0.415,
    "eastus2": 0.415,
    "westus": 0.285,
    "westus2": 0.285,
    "centralus": 0.531,
    "westcentralus": 0.741,
    # EU Regions
    "westeurope": 0.39,
    "northeurope": 0.21,  # Iceland - very low!
    "uksouth": 0.283,
    "ukwest": 0.283,
    "francecentral": 0.056,
    "germanywestcentral": 0.338,
    # Asia Pacific
    "southeastasia": 0.431,
    "eastasia": 0.81,
    "australiaeast": 0.79,
    "japaneast": 0.506,
    "koreacentral": 0.436,
    "centralindia": 0.708,
}

# Default fallback for unknown regions
DEFAULT_CARBON_INTENSITY = 0.4

# Estimated power consumption (kWh per hour) per resource type
RESOURCE_POWER_CONSUMPTION = {
    # AWS Compute
    "ec2_instance": 0.5,
    "ec2_instance_stopped": 0.0,  # Stopped instances don't consume power
    "ec2_instance_idle": 0.5,
    # AWS Storage
    "ebs_volume": 0.01,
    "ebs_volume_unattached": 0.01,
    "ebs_snapshot": 0.005,
    "s3_bucket": 0.02,
    # AWS Network
    "elastic_ip": 0.001,
    "nat_gateway": 0.2,
    "load_balancer": 0.3,
    "load_balancer_alb": 0.3,
    "load_balancer_nlb": 0.3,
    "load_balancer_clb": 0.25,
    "load_balancer_gwlb": 0.3,
    "vpn_connection": 0.1,
    "transit_gateway_attachment": 0.15,
    "vpc_endpoint": 0.05,
    "globalaccelerator": 0.2,
    # AWS Database
    "rds_instance": 0.8,
    "rds_instance_stopped": 0.0,
    "redshift_cluster": 1.0,
    "elasticache": 0.4,
    "neptune_cluster": 0.9,
    "documentdb_cluster": 0.8,
    "dynamodb_table": 0.3,
    # AWS Analytics & Streaming
    "kinesis_stream": 0.15,
    "kafka_cluster": 0.7,
    "opensearch_domain": 0.6,
    # AWS ML & Containers
    "sagemaker_endpoint": 0.6,
    "eks_cluster": 0.5,
    # AWS Storage Advanced
    "fsx_filesystem": 0.4,
    "fsx_lustre": 0.4,
    "fsx_windows": 0.4,
    "fsx_ontap": 0.5,
    "fsx_openzfs": 0.4,
    # AWS Serverless
    "lambda_function": 0.001,  # Very low, pay-per-use
    # Azure
    "virtual_machine": 0.6,
    "managed_disk": 0.01,
    "managed_disk_unattached": 0.01,
    "public_ip": 0.001,
    "public_ip_unassociated": 0.001,
    # Default for unknown types
    "default": 0.1,
}


def _get_carbon_intensity(provider: str, region: str) -> float:
    """
    Get carbon intensity (kg CO2/kWh) for a specific cloud provider region.

    Args:
        provider: Cloud provider ('aws', 'azure', 'gcp')
        region: Region identifier

    Returns:
        Carbon intensity in kg CO2 per kWh
    """
    if provider == "aws":
        return AWS_CARBON_INTENSITY.get(region, DEFAULT_CARBON_INTENSITY)
    elif provider == "azure":
        return AZURE_CARBON_INTENSITY.get(region.lower(), DEFAULT_CARBON_INTENSITY)
    else:
        return DEFAULT_CARBON_INTENSITY


def _get_power_consumption(resource_type: str) -> float:
    """
    Get estimated power consumption (kWh/hour) for a resource type.

    Args:
        resource_type: Type of cloud resource

    Returns:
        Power consumption in kWh per hour
    """
    return RESOURCE_POWER_CONSUMPTION.get(resource_type, RESOURCE_POWER_CONSUMPTION["default"])


def _calculate_co2_for_resource(
    resource: OrphanResource,
    provider: str,
    months_saved: float = 1.0,
) -> float:
    """
    Calculate CO2 emissions saved (kg) by deleting a resource.

    Args:
        resource: OrphanResource object
        provider: Cloud provider ('aws', 'azure')
        months_saved: Number of months to calculate for (default: 1 month)

    Returns:
        CO2 emissions saved in kilograms
    """
    # Get carbon intensity for this region
    carbon_intensity = _get_carbon_intensity(provider, resource.region)

    # Get power consumption for this resource type
    power_consumption_kwh = _get_power_consumption(resource.resource_type)

    # Calculate total hours
    hours = months_saved * 30 * 24  # months * days * hours

    # CO2 = hours * kWh/hour * kg CO2/kWh
    co2_kg = hours * power_consumption_kwh * carbon_intensity

    return round(co2_kg, 2)


def _calculate_trees_equivalent(co2_kg: float) -> float:
    """
    Calculate equivalent number of trees planted for 1 year.

    Average tree absorbs ~21.77 kg CO2 per year.

    Args:
        co2_kg: CO2 in kilograms

    Returns:
        Equivalent number of trees
    """
    return round(co2_kg / 21.77, 2)


def _calculate_car_km_equivalent(co2_kg: float) -> float:
    """
    Calculate equivalent car kilometers not driven.

    Average car emits ~0.12 kg CO2 per km.

    Args:
        co2_kg: CO2 in kilograms

    Returns:
        Equivalent kilometers not driven
    """
    return round(co2_kg / 0.12, 2)


def _calculate_home_days_equivalent(co2_kg: float) -> float:
    """
    Calculate equivalent home electricity days.

    Average home emits ~30 kg CO2 per day.

    Args:
        co2_kg: CO2 in kilograms

    Returns:
        Equivalent days of home electricity
    """
    return round(co2_kg / 30.0, 2)


async def get_impact_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> ImpactSummary:
    """
    Get comprehensive impact summary for a user.

    Calculates financial savings, environmental impact, and engagement metrics
    across all user's cloud accounts and orphan resources.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        ImpactSummary object with all metrics
    """
    # Get all cloud accounts for this user
    accounts_result = await db.execute(
        select(CloudAccount).where(CloudAccount.user_id == user_id)
    )
    accounts = list(accounts_result.scalars().all())
    account_ids = [account.id for account in accounts]

    if not account_ids:
        # Return empty summary
        return _create_empty_impact_summary()

    # Get all orphan resources across all accounts
    resources_result = await db.execute(
        select(OrphanResource).where(OrphanResource.cloud_account_id.in_(account_ids))
    )
    all_resources = list(resources_result.scalars().all())

    # Group resources by status
    active_resources = [r for r in all_resources if r.status == ResourceStatus.ACTIVE.value]
    deleted_resources = [r for r in all_resources if r.status == ResourceStatus.DELETED.value]
    ignored_resources = [r for r in all_resources if r.status == ResourceStatus.IGNORED.value]
    marked_resources = [
        r for r in all_resources if r.status == ResourceStatus.MARKED_FOR_DELETION.value
    ]

    # Financial calculations
    total_monthly_savings = sum(r.estimated_monthly_cost for r in deleted_resources)
    total_annual_savings = total_monthly_savings * 12
    potential_monthly_savings = sum(r.estimated_monthly_cost for r in active_resources)

    # Calculate "already wasted" - money wasted before detection
    already_wasted_total = 0.0
    for resource in all_resources:
        if resource.resource_metadata and "age_days" in resource.resource_metadata:
            age_days = resource.resource_metadata["age_days"]
            daily_cost = resource.estimated_monthly_cost / 30
            already_wasted_total += age_days * daily_cost

    # Environmental impact - only for deleted resources
    total_co2_saved_kg = 0.0
    co2_by_provider: dict[str, float] = {}

    for resource in deleted_resources:
        # Find the provider for this resource
        provider = "aws"  # Default
        for account in accounts:
            if account.id == resource.cloud_account_id:
                provider = account.provider
                break

        co2 = _calculate_co2_for_resource(resource, provider, months_saved=1.0)
        total_co2_saved_kg += co2

        # Accumulate by provider
        co2_by_provider[provider] = co2_by_provider.get(provider, 0.0) + co2

    # Environmental equivalents
    trees_equivalent = _calculate_trees_equivalent(total_co2_saved_kg)
    car_km_equivalent = _calculate_car_km_equivalent(total_co2_saved_kg)
    home_days_equivalent = _calculate_home_days_equivalent(total_co2_saved_kg)

    # Savings breakdown by provider
    savings_by_provider: dict[str, float] = {}
    for resource in deleted_resources:
        provider = "aws"
        for account in accounts:
            if account.id == resource.cloud_account_id:
                provider = account.provider
                break
        savings_by_provider[provider] = (
            savings_by_provider.get(provider, 0.0) + resource.estimated_monthly_cost
        )

    # Savings breakdown by resource type
    savings_by_resource_type: dict[str, float] = {}
    resources_by_resource_type: dict[str, int] = {}

    for resource in deleted_resources:
        rt = resource.resource_type
        savings_by_resource_type[rt] = (
            savings_by_resource_type.get(rt, 0.0) + resource.estimated_monthly_cost
        )
        resources_by_resource_type[rt] = resources_by_resource_type.get(rt, 0) + 1

    # User engagement metrics
    total_detected = len(all_resources)
    total_deleted = len(deleted_resources)
    cleanup_rate = total_deleted / total_detected if total_detected > 0 else 0.0

    # Get first scan date
    first_scan_result = await db.execute(
        select(Scan)
        .where(Scan.cloud_account_id.in_(account_ids))
        .order_by(Scan.created_at.asc())
        .limit(1)
    )
    first_scan = first_scan_result.scalar_one_or_none()
    first_scan_date = first_scan.created_at if first_scan else None

    days_since_first_scan = 0
    if first_scan_date:
        days_since_first_scan = (datetime.utcnow() - first_scan_date).days

    # Get last cleanup date
    last_cleanup_date = None
    if deleted_resources:
        last_cleanup_date = max(r.updated_at for r in deleted_resources)

    # Calculate cleanup streak
    cleanup_streak_days = await _calculate_cleanup_streak(db, account_ids)

    return ImpactSummary(
        # Financial
        total_resources_detected=total_detected,
        total_resources_deleted=total_deleted,
        total_resources_active=len(active_resources),
        total_resources_ignored=len(ignored_resources),
        total_monthly_savings=round(total_monthly_savings, 2),
        total_annual_savings=round(total_annual_savings, 2),
        potential_monthly_savings=round(potential_monthly_savings, 2),
        already_wasted_total=round(already_wasted_total, 2),
        # Environmental
        total_co2_saved_kg=round(total_co2_saved_kg, 2),
        trees_equivalent=trees_equivalent,
        car_km_equivalent=car_km_equivalent,
        home_days_equivalent=home_days_equivalent,
        # Breakdown
        savings_by_provider=savings_by_provider,
        co2_by_provider=co2_by_provider,
        savings_by_resource_type=savings_by_resource_type,
        resources_by_resource_type=resources_by_resource_type,
        # Engagement
        cleanup_rate=round(cleanup_rate, 4),
        first_scan_date=first_scan_date,
        days_since_first_scan=days_since_first_scan,
        last_cleanup_date=last_cleanup_date,
        cleanup_streak_days=cleanup_streak_days,
    )


async def _calculate_cleanup_streak(
    db: AsyncSession,
    account_ids: list[uuid.UUID],
) -> int:
    """
    Calculate consecutive days with at least one resource deletion.

    Args:
        db: Database session
        account_ids: List of cloud account IDs

    Returns:
        Number of consecutive days with cleanup activity
    """
    # Get all deleted resources ordered by updated_at desc
    result = await db.execute(
        select(OrphanResource)
        .where(
            and_(
                OrphanResource.cloud_account_id.in_(account_ids),
                OrphanResource.status == ResourceStatus.DELETED.value,
            )
        )
        .order_by(OrphanResource.updated_at.desc())
    )
    deleted_resources = list(result.scalars().all())

    if not deleted_resources:
        return 0

    # Get unique dates (day granularity)
    cleanup_dates = set()
    for resource in deleted_resources:
        cleanup_dates.add(resource.updated_at.date())

    # Sort dates descending
    sorted_dates = sorted(cleanup_dates, reverse=True)

    # Calculate streak
    streak = 0
    expected_date = datetime.utcnow().date()

    for cleanup_date in sorted_dates:
        if cleanup_date == expected_date:
            streak += 1
            expected_date -= timedelta(days=1)
        elif cleanup_date < expected_date:
            # Check if there's a gap
            break

    return streak


def _create_empty_impact_summary() -> ImpactSummary:
    """Create empty impact summary for users with no accounts."""
    return ImpactSummary(
        total_resources_detected=0,
        total_resources_deleted=0,
        total_resources_active=0,
        total_resources_ignored=0,
        total_monthly_savings=0.0,
        total_annual_savings=0.0,
        potential_monthly_savings=0.0,
        already_wasted_total=0.0,
        total_co2_saved_kg=0.0,
        trees_equivalent=0.0,
        car_km_equivalent=0.0,
        home_days_equivalent=0.0,
        savings_by_provider={},
        co2_by_provider={},
        savings_by_resource_type={},
        resources_by_resource_type={},
        cleanup_rate=0.0,
        first_scan_date=None,
        days_since_first_scan=0,
        last_cleanup_date=None,
        cleanup_streak_days=0,
    )


async def get_impact_timeline(
    db: AsyncSession,
    user_id: uuid.UUID,
    period: Literal["day", "week", "month", "year", "all"] = "month",
) -> ImpactTimeline:
    """
    Get timeline data for impact charts.

    Groups resources by time periods and calculates cumulative savings.

    Args:
        db: Database session
        user_id: User UUID
        period: Time period granularity

    Returns:
        ImpactTimeline with data points grouped by period
    """
    # Get all cloud accounts
    accounts_result = await db.execute(
        select(CloudAccount).where(CloudAccount.user_id == user_id)
    )
    accounts = list(accounts_result.scalars().all())
    account_ids = [account.id for account in accounts]

    if not account_ids:
        return ImpactTimeline(period=period, data_points=[], summary={})

    # Get all resources
    resources_result = await db.execute(
        select(OrphanResource).where(OrphanResource.cloud_account_id.in_(account_ids))
    )
    all_resources = list(resources_result.scalars().all())

    # Group by time period
    data_by_period: dict[datetime, dict] = {}

    for resource in all_resources:
        # Use created_at for detection, updated_at for deletion
        detection_date = _truncate_to_period(resource.created_at, period)

        if detection_date not in data_by_period:
            data_by_period[detection_date] = {
                "resources_detected": 0,
                "resources_deleted": 0,
                "monthly_savings": 0.0,
                "co2_saved_kg": 0.0,
            }

        data_by_period[detection_date]["resources_detected"] += 1

        # If deleted, add to deletion stats
        if resource.status == ResourceStatus.DELETED.value:
            deletion_date = _truncate_to_period(resource.updated_at, period)

            if deletion_date not in data_by_period:
                data_by_period[deletion_date] = {
                    "resources_detected": 0,
                    "resources_deleted": 0,
                    "monthly_savings": 0.0,
                    "co2_saved_kg": 0.0,
                }

            data_by_period[deletion_date]["resources_deleted"] += 1
            data_by_period[deletion_date]["monthly_savings"] += resource.estimated_monthly_cost

            # Calculate CO2
            provider = "aws"
            for account in accounts:
                if account.id == resource.cloud_account_id:
                    provider = account.provider
                    break

            co2 = _calculate_co2_for_resource(resource, provider, months_saved=1.0)
            data_by_period[deletion_date]["co2_saved_kg"] += co2

    # Sort periods
    sorted_periods = sorted(data_by_period.keys())

    # Create data points with cumulative values
    data_points = []
    cumulative_savings = 0.0
    cumulative_co2 = 0.0

    for period_date in sorted_periods:
        data = data_by_period[period_date]
        cumulative_savings += data["monthly_savings"]
        cumulative_co2 += data["co2_saved_kg"]

        data_points.append(
            TimelineDataPoint(
                date=period_date,
                resources_detected=data["resources_detected"],
                resources_deleted=data["resources_deleted"],
                monthly_savings=round(data["monthly_savings"], 2),
                co2_saved_kg=round(data["co2_saved_kg"], 2),
                cumulative_savings=round(cumulative_savings, 2),
                cumulative_co2=round(cumulative_co2, 2),
            )
        )

    # Calculate summary
    total_savings = cumulative_savings
    avg_daily_savings = 0.0
    if data_points:
        days = (sorted_periods[-1] - sorted_periods[0]).days + 1
        avg_daily_savings = total_savings / days if days > 0 else 0.0

    summary = {
        "total_savings": round(total_savings, 2),
        "avg_daily_savings": round(avg_daily_savings, 2),
        "total_co2": round(cumulative_co2, 2),
        "total_detections": sum(dp.resources_detected for dp in data_points),
        "total_deletions": sum(dp.resources_deleted for dp in data_points),
    }

    return ImpactTimeline(
        period=period,
        data_points=data_points,
        summary=summary,
    )


def _truncate_to_period(
    dt: datetime,
    period: Literal["day", "week", "month", "year", "all"],
) -> datetime:
    """
    Truncate datetime to start of period.

    Args:
        dt: Datetime to truncate
        period: Period type

    Returns:
        Truncated datetime
    """
    if period == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        # Start of week (Monday)
        return (dt - timedelta(days=dt.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == "month":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # all
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_user_achievements(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> UserAchievements:
    """
    Calculate user achievement progress.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        UserAchievements with all achievement statuses
    """
    # Get impact summary for calculations
    summary = await get_impact_summary(db, user_id)

    # Get all cloud accounts
    accounts_result = await db.execute(
        select(CloudAccount).where(CloudAccount.user_id == user_id)
    )
    account_ids = [account.id for account in accounts_result.scalars().all()]

    # Get all deleted resources to check for speed records
    deleted_resources = []
    if account_ids:
        result = await db.execute(
            select(OrphanResource).where(
                and_(
                    OrphanResource.cloud_account_id.in_(account_ids),
                    OrphanResource.status == ResourceStatus.DELETED.value,
                )
            )
        )
        deleted_resources = list(result.scalars().all())

    # Calculate fastest cleanup
    fastest_cleanup_hours = None
    if deleted_resources:
        for resource in deleted_resources:
            hours = (resource.updated_at - resource.created_at).total_seconds() / 3600
            if fastest_cleanup_hours is None or hours < fastest_cleanup_hours:
                fastest_cleanup_hours = hours

    # Count resources deleted in last 24 hours
    resources_deleted_24h = 0
    cutoff = datetime.utcnow() - timedelta(hours=24)
    for resource in deleted_resources:
        if resource.updated_at >= cutoff:
            resources_deleted_24h += 1

    # Define achievements
    achievements_config = [
        {
            "id": "first_cleanup",
            "name": "First Steps",
            "description": "Delete your first orphaned resource",
            "icon": "🌱",
            "threshold": 1.0,
            "current_value": float(summary.total_resources_deleted),
            "category": "engagement",
        },
        {
            "id": "eco_warrior",
            "name": "Eco Warrior",
            "description": "Save $100 in monthly costs",
            "icon": "💚",
            "threshold": 100.0,
            "current_value": summary.total_monthly_savings,
            "category": "financial",
        },
        {
            "id": "cloud_optimizer",
            "name": "Cloud Optimizer",
            "description": "Save $1,000 in monthly costs",
            "icon": "💰",
            "threshold": 1000.0,
            "current_value": summary.total_monthly_savings,
            "category": "financial",
        },
        {
            "id": "carbon_hero",
            "name": "Carbon Hero",
            "description": "Save 100kg of CO2 emissions",
            "icon": "🌍",
            "threshold": 100.0,
            "current_value": summary.total_co2_saved_kg,
            "category": "environmental",
        },
        {
            "id": "speed_demon",
            "name": "Speed Demon",
            "description": "Delete 10+ resources in 24 hours",
            "icon": "⚡",
            "threshold": 10.0,
            "current_value": float(resources_deleted_24h),
            "category": "engagement",
        },
        {
            "id": "perfectionist",
            "name": "Perfectionist",
            "description": "Achieve 90%+ cleanup rate",
            "icon": "✨",
            "threshold": 0.9,
            "current_value": summary.cleanup_rate,
            "category": "engagement",
        },
        {
            "id": "marathon",
            "name": "Marathon Runner",
            "description": "Maintain a 30-day cleanup streak",
            "icon": "🏃",
            "threshold": 30.0,
            "current_value": float(summary.cleanup_streak_days),
            "category": "engagement",
        },
        {
            "id": "tree_planter",
            "name": "Tree Planter",
            "description": "CO2 savings equivalent to 100 trees",
            "icon": "🌳",
            "threshold": 100.0,
            "current_value": summary.trees_equivalent,
            "category": "environmental",
        },
        {
            "id": "cost_crusher",
            "name": "Cost Crusher",
            "description": "Save $5,000 in monthly costs",
            "icon": "🔥",
            "threshold": 5000.0,
            "current_value": summary.total_monthly_savings,
            "category": "financial",
        },
        {
            "id": "early_adopter",
            "name": "Early Adopter",
            "description": "Delete a resource within 1 hour of detection",
            "icon": "🚀",
            "threshold": 1.0,
            "current_value": 0.0 if fastest_cleanup_hours is None else min(1.0, 1.0 / fastest_cleanup_hours if fastest_cleanup_hours > 0 else 1.0),
            "category": "engagement",
        },
    ]

    # Build achievement objects
    achievements = []
    for config in achievements_config:
        unlocked = config["current_value"] >= config["threshold"]
        progress = min(1.0, config["current_value"] / config["threshold"]) if config["threshold"] > 0 else 0.0

        # Find unlock date if unlocked
        unlocked_at = None
        if unlocked:
            unlocked_at = datetime.utcnow()  # Simplified - in production, track actual unlock dates

        achievements.append(
            Achievement(
                id=config["id"],
                name=config["name"],
                description=config["description"],
                icon=config["icon"],
                unlocked=unlocked,
                unlocked_at=unlocked_at,
                progress=round(progress, 4),
                threshold=config["threshold"],
                current_value=round(config["current_value"], 2),
                category=config["category"],
            )
        )

    total_unlocked = sum(1 for a in achievements if a.unlocked)
    total_available = len(achievements)
    completion_rate = total_unlocked / total_available if total_available > 0 else 0.0

    return UserAchievements(
        achievements=achievements,
        total_unlocked=total_unlocked,
        total_available=total_available,
        completion_rate=round(completion_rate, 4),
    )


async def get_quick_stats(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> QuickStats:
    """
    Get quick interesting statistics for user.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        QuickStats with interesting metrics
    """
    # Get all cloud accounts
    accounts_result = await db.execute(
        select(CloudAccount).where(CloudAccount.user_id == user_id)
    )
    account_ids = [account.id for account in accounts_result.scalars().all()]

    if not account_ids:
        return _create_empty_quick_stats()

    # Get all resources
    resources_result = await db.execute(
        select(OrphanResource).where(OrphanResource.cloud_account_id.in_(account_ids))
    )
    all_resources = list(resources_result.scalars().all())

    if not all_resources:
        return _create_empty_quick_stats()

    # Biggest cleanup
    biggest_cleanup = max(all_resources, key=lambda r: r.estimated_monthly_cost)
    biggest_cleanup_monthly_cost = biggest_cleanup.estimated_monthly_cost
    biggest_cleanup_resource_type = biggest_cleanup.resource_type

    # Most common resource type
    type_counts: dict[str, int] = {}
    for resource in all_resources:
        type_counts[resource.resource_type] = type_counts.get(resource.resource_type, 0) + 1

    most_common_resource_type = None
    most_common_resource_count = 0
    if type_counts:
        most_common_resource_type = max(type_counts, key=type_counts.get)  # type: ignore
        most_common_resource_count = type_counts[most_common_resource_type]

    # Fastest cleanup
    deleted_resources = [r for r in all_resources if r.status == ResourceStatus.DELETED.value]
    fastest_cleanup_hours = None
    if deleted_resources:
        for resource in deleted_resources:
            hours = (resource.updated_at - resource.created_at).total_seconds() / 3600
            if fastest_cleanup_hours is None or hours < fastest_cleanup_hours:
                fastest_cleanup_hours = hours

    # Top region
    region_counts: dict[str, int] = {}
    for resource in all_resources:
        region_counts[resource.region] = region_counts.get(resource.region, 0) + 1

    top_region = None
    top_region_count = 0
    if region_counts:
        top_region = max(region_counts, key=region_counts.get)  # type: ignore
        top_region_count = region_counts[top_region]

    # Average resource age
    total_age_days = 0.0
    age_count = 0
    for resource in all_resources:
        if resource.resource_metadata and "age_days" in resource.resource_metadata:
            total_age_days += resource.resource_metadata["age_days"]
            age_count += 1

    average_resource_age_days = total_age_days / age_count if age_count > 0 else 0.0

    return QuickStats(
        biggest_cleanup_monthly_cost=round(biggest_cleanup_monthly_cost, 2),
        biggest_cleanup_resource_type=biggest_cleanup_resource_type,
        most_common_resource_type=most_common_resource_type,
        most_common_resource_count=most_common_resource_count,
        fastest_cleanup_hours=round(fastest_cleanup_hours, 2) if fastest_cleanup_hours else None,
        top_region=top_region,
        top_region_count=top_region_count,
        average_resource_age_days=round(average_resource_age_days, 2),
    )


def _create_empty_quick_stats() -> QuickStats:
    """Create empty quick stats for users with no resources."""
    return QuickStats(
        biggest_cleanup_monthly_cost=0.0,
        biggest_cleanup_resource_type=None,
        most_common_resource_type=None,
        most_common_resource_count=0,
        fastest_cleanup_hours=None,
        top_region=None,
        top_region_count=0,
        average_resource_age_days=0.0,
    )
