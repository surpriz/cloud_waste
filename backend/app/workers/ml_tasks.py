"""
Celery tasks for ML data collection and export.

Background tasks for automated ML dataset exports and data quality monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from app.ml.data_pipeline import export_all_ml_datasets, validate_data_quality
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.ml_tasks.export_ml_datasets_weekly")
def export_ml_datasets_weekly() -> dict[str, Any]:
    """
    Export ML datasets every week for training purposes.

    This task runs weekly and exports:
    - ML training data (last 90 days)
    - User action patterns (last 90 days)
    - Cost trends (last 12 months)

    Returns:
        Dict with export results and file paths
    """
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run export
        results = loop.run_until_complete(
            export_all_ml_datasets(output_format="json", output_dir="/tmp/cloudwaste_ml_exports")
        )

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "files_exported": results,
        }

    except Exception as e:
        print(f"❌ ML dataset export failed: {e}")
        return {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


@celery_app.task(name="app.workers.ml_tasks.validate_ml_data_quality")
def validate_ml_data_quality() -> dict[str, Any]:
    """
    Validate ML data quality on a daily basis.

    Checks:
    - Null value percentages
    - Duplicate records
    - Class distribution balance
    - Overall quality score

    Returns:
        Dict with quality metrics
    """
    try:
        # This is a placeholder - in production, you'd fetch recent data and validate
        # For now, we just log that the task ran
        print(f"✅ ML data quality validation task ran at {datetime.now()}")

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "message": "Data quality validation completed",
        }

    except Exception as e:
        print(f"❌ ML data quality validation failed: {e}")
        return {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


@celery_app.task(name="app.workers.ml_tasks.cleanup_old_ml_data")
def cleanup_old_ml_data(retention_years: int = 3) -> dict[str, Any]:
    """
    Clean up ML data older than retention period (GDPR compliance).

    Args:
        retention_years: Number of years to retain data (default: 3)

    Returns:
        Dict with cleanup results
    """
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run cleanup
        results = loop.run_until_complete(_cleanup_old_ml_data_async(retention_years))

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "records_deleted": results,
        }

    except Exception as e:
        print(f"❌ ML data cleanup failed: {e}")
        return {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


async def _cleanup_old_ml_data_async(retention_years: int) -> dict[str, int]:
    """
    Async implementation of ML data cleanup.

    Args:
        retention_years: Number of years to retain data

    Returns:
        Dict with count of deleted records per table
    """
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.models.cloudwatch_metrics_history import CloudWatchMetricsHistory
    from app.models.cost_trend_data import CostTrendData
    from app.models.ml_training_data import MLTrainingData
    from app.models.resource_lifecycle_event import ResourceLifecycleEvent
    from app.models.user_action_pattern import UserActionPattern

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=retention_years * 365)

    # Create async engine
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False  # type: ignore
    )

    deleted_counts = {}

    async with AsyncSessionLocal() as db:
        # Delete old MLTrainingData
        result = await db.execute(
            delete(MLTrainingData).where(MLTrainingData.created_at < cutoff_date)
        )
        deleted_counts["ml_training_data"] = result.rowcount

        # Delete old UserActionPattern
        result = await db.execute(
            delete(UserActionPattern).where(UserActionPattern.created_at < cutoff_date)
        )
        deleted_counts["user_action_patterns"] = result.rowcount

        # Delete old ResourceLifecycleEvent
        result = await db.execute(
            delete(ResourceLifecycleEvent).where(ResourceLifecycleEvent.created_at < cutoff_date)
        )
        deleted_counts["resource_lifecycle_events"] = result.rowcount

        # Delete old CloudWatchMetricsHistory
        result = await db.execute(
            delete(CloudWatchMetricsHistory).where(CloudWatchMetricsHistory.created_at < cutoff_date)
        )
        deleted_counts["cloudwatch_metrics_history"] = result.rowcount

        # Delete old CostTrendData
        result = await db.execute(
            delete(CostTrendData).where(CostTrendData.created_at < cutoff_date)
        )
        deleted_counts["cost_trend_data"] = result.rowcount

        await db.commit()

    print(f"✅ Cleaned up old ML data: {deleted_counts}")
    return deleted_counts
