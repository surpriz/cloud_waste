"""
ML Data Pipeline & ETL Service.

Export and prepare ML training datasets from collected anonymized data.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.cloudwatch_metrics_history import CloudWatchMetricsHistory
from app.models.cost_trend_data import CostTrendData
from app.models.ml_training_data import MLTrainingData
from app.models.resource_lifecycle_event import ResourceLifecycleEvent
from app.models.user_action_pattern import UserActionPattern

# Create async engine for database operations
engine = create_async_engine(str(settings.DATABASE_URL), echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False  # type: ignore
)


async def export_ml_training_dataset(
    start_date: datetime,
    end_date: datetime,
    output_format: str = "json",
    output_dir: str = "/tmp/cloudwaste_ml_exports",
) -> str:
    """
    Export ML training dataset for waste prediction models.

    Args:
        start_date: Start date for data export
        end_date: End date for data export
        output_format: Format for export (json, csv, parquet)
        output_dir: Directory to save export files

    Returns:
        Path to exported file
    """
    async with AsyncSessionLocal() as db:
        # Query ml_training_data
        result = await db.execute(
            select(MLTrainingData)
            .where(MLTrainingData.detected_at >= start_date)
            .where(MLTrainingData.detected_at <= end_date)
            .order_by(MLTrainingData.detected_at.desc())
        )
        ml_records = result.scalars().all()

        # Convert to dictionaries
        dataset = []
        for record in ml_records:
            dataset.append(
                {
                    "resource_type": record.resource_type,
                    "provider": record.provider,
                    "region_anonymized": record.region_anonymized,
                    "resource_age_days": record.resource_age_days,
                    "detection_scenario": record.detection_scenario,
                    "metrics_summary": record.metrics_summary,
                    "cost_monthly": record.cost_monthly,
                    "confidence_level": record.confidence_level,
                    "user_action": record.user_action,
                    "resource_config": record.resource_config,
                    "detected_at": record.detected_at.isoformat(),
                }
            )

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ml_training_data_{timestamp}.{output_format}"
        filepath = output_path / filename

        # Export based on format
        if output_format == "json":
            with open(filepath, "w") as f:
                json.dump(dataset, f, indent=2)
        elif output_format == "csv":
            # Flatten nested JSON fields for CSV
            import csv

            if dataset:
                with open(filepath, "w", newline="") as f:
                    # Get all fields (excluding complex nested structures)
                    fieldnames = [
                        "resource_type",
                        "provider",
                        "region_anonymized",
                        "resource_age_days",
                        "detection_scenario",
                        "cost_monthly",
                        "confidence_level",
                        "user_action",
                        "detected_at",
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(dataset)
        else:
            # JSON is default fallback
            with open(filepath, "w") as f:
                json.dump(dataset, f, indent=2)

        print(f"✅ Exported {len(dataset)} ML training records to {filepath}")
        return str(filepath)


async def export_user_action_patterns(
    start_date: datetime,
    end_date: datetime,
    output_format: str = "json",
    output_dir: str = "/tmp/cloudwaste_ml_exports",
) -> str:
    """
    Export user action patterns for recommendation models.

    Args:
        start_date: Start date for data export
        end_date: End date for data export
        output_format: Format for export (json, csv)
        output_dir: Directory to save export files

    Returns:
        Path to exported file
    """
    async with AsyncSessionLocal() as db:
        # Query user_action_patterns
        result = await db.execute(
            select(UserActionPattern)
            .where(UserActionPattern.action_at >= start_date)
            .where(UserActionPattern.action_at <= end_date)
            .order_by(UserActionPattern.action_at.desc())
        )
        action_records = result.scalars().all()

        # Convert to dictionaries
        dataset = []
        for record in action_records:
            dataset.append(
                {
                    "user_hash": record.user_hash,
                    "resource_type": record.resource_type,
                    "provider": record.provider,
                    "detection_scenario": record.detection_scenario,
                    "confidence_level": record.confidence_level,
                    "action_taken": record.action_taken,
                    "time_to_action_hours": record.time_to_action_hours,
                    "cost_monthly": record.cost_monthly,
                    "cost_saved_monthly": record.cost_saved_monthly,
                    "industry_anonymized": record.industry_anonymized,
                    "company_size_bucket": record.company_size_bucket,
                    "detected_at": record.detected_at.isoformat(),
                    "action_at": record.action_at.isoformat(),
                }
            )

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_action_patterns_{timestamp}.{output_format}"
        filepath = output_path / filename

        # Export
        if output_format == "json":
            with open(filepath, "w") as f:
                json.dump(dataset, f, indent=2)
        elif output_format == "csv":
            import csv

            if dataset:
                with open(filepath, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=dataset[0].keys())
                    writer.writeheader()
                    writer.writerows(dataset)

        print(f"✅ Exported {len(dataset)} user action patterns to {filepath}")
        return str(filepath)


async def export_cost_trends(
    months: int = 12,
    output_format: str = "json",
    output_dir: str = "/tmp/cloudwaste_ml_exports",
) -> str:
    """
    Export cost trend data for forecasting models.

    Args:
        months: Number of months to export (default: 12)
        output_format: Format for export (json, csv)
        output_dir: Directory to save export files

    Returns:
        Path to exported file
    """
    async with AsyncSessionLocal() as db:
        # Calculate start month
        end_month = datetime.now().strftime("%Y-%m")
        start_date = datetime.now() - timedelta(days=months * 30)
        start_month = start_date.strftime("%Y-%m")

        # Query cost_trend_data
        result = await db.execute(
            select(CostTrendData).where(CostTrendData.month >= start_month).order_by(CostTrendData.month)
        )
        cost_records = result.scalars().all()

        # Convert to dictionaries
        dataset = []
        for record in cost_records:
            dataset.append(
                {
                    "account_hash": record.account_hash,
                    "month": record.month,
                    "provider": record.provider,
                    "total_spend": record.total_spend,
                    "waste_detected": record.waste_detected,
                    "waste_eliminated": record.waste_eliminated,
                    "waste_percentage": record.waste_percentage,
                    "top_waste_categories": record.top_waste_categories,
                    "total_resources_scanned": record.total_resources_scanned,
                    "orphan_resources_found": record.orphan_resources_found,
                    "regional_breakdown": record.regional_breakdown,
                    "scan_count": record.scan_count,
                }
            )

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cost_trends_{timestamp}.{output_format}"
        filepath = output_path / filename

        # Export
        if output_format == "json":
            with open(filepath, "w") as f:
                json.dump(dataset, f, indent=2)
        elif output_format == "csv":
            import csv

            if dataset:
                with open(filepath, "w", newline="") as f:
                    # Flatten for CSV (exclude complex JSON fields)
                    fieldnames = [
                        "account_hash",
                        "month",
                        "provider",
                        "total_spend",
                        "waste_detected",
                        "waste_eliminated",
                        "waste_percentage",
                        "total_resources_scanned",
                        "orphan_resources_found",
                        "scan_count",
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(dataset)

        print(f"✅ Exported {len(dataset)} cost trend records to {filepath}")
        return str(filepath)


async def validate_data_quality(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate data quality of exported ML dataset.

    Args:
        dataset: List of data records

    Returns:
        Dictionary with quality metrics
    """
    if not dataset:
        return {
            "total_records": 0,
            "null_percentage": {},
            "duplicate_percentage": 0,
            "class_distribution": {},
            "quality_score": 0.0,
        }

    total_records = len(dataset)

    # Calculate null percentages per field
    null_counts = {}
    for record in dataset:
        for key, value in record.items():
            if key not in null_counts:
                null_counts[key] = 0
            if value is None:
                null_counts[key] += 1

    null_percentage = {key: (count / total_records * 100) for key, count in null_counts.items()}

    # Calculate duplicate percentage (simplified - just count exact duplicates)
    unique_records = len(set(json.dumps(r, sort_keys=True) for r in dataset))
    duplicate_percentage = ((total_records - unique_records) / total_records * 100) if total_records > 0 else 0

    # Class distribution (if user_action field exists)
    class_distribution = {}
    if "user_action" in dataset[0]:
        for record in dataset:
            action = record.get("user_action", "unknown")
            if action not in class_distribution:
                class_distribution[action] = 0
            class_distribution[action] += 1

    # Calculate quality score (0-100)
    # Factors: low null rate, low duplicates, balanced classes
    null_rate = sum(null_percentage.values()) / len(null_percentage) if null_percentage else 0
    quality_score = max(0, 100 - null_rate - duplicate_percentage)

    return {
        "total_records": total_records,
        "unique_records": unique_records,
        "null_percentage": null_percentage,
        "duplicate_percentage": round(duplicate_percentage, 2),
        "class_distribution": class_distribution,
        "quality_score": round(quality_score, 2),
    }


async def export_all_ml_datasets(
    output_format: str = "json",
    output_dir: str = "/tmp/cloudwaste_ml_exports",
) -> Dict[str, str]:
    """
    Export all ML datasets (training data, user actions, cost trends).

    Args:
        output_format: Format for export (json, csv)
        output_dir: Directory to save export files

    Returns:
        Dictionary with paths to all exported files
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # Last 90 days

    results = {}

    # Export ML training data
    results["ml_training_data"] = await export_ml_training_dataset(
        start_date=start_date,
        end_date=end_date,
        output_format=output_format,
        output_dir=output_dir,
    )

    # Export user action patterns
    results["user_action_patterns"] = await export_user_action_patterns(
        start_date=start_date,
        end_date=end_date,
        output_format=output_format,
        output_dir=output_dir,
    )

    # Export cost trends (last 12 months)
    results["cost_trends"] = await export_cost_trends(
        months=12, output_format=output_format, output_dir=output_dir
    )

    print(f"✅ All ML datasets exported to {output_dir}")
    return results
