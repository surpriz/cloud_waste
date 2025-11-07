"""
GDPR Compliance Service.

Implements GDPR requirements including:
- Right to be forgotten (delete all user's ML data)
- Right to access (export user's data)
- Data minimization
- Consent management
"""

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloudwatch_metrics_history import CloudWatchMetricsHistory
from app.models.cost_trend_data import CostTrendData
from app.models.ml_training_data import MLTrainingData
from app.models.resource_lifecycle_event import ResourceLifecycleEvent
from app.models.user_action_pattern import UserActionPattern
from app.models.user_preferences import UserPreferences
from app.services.ml_anonymization import anonymize_account_id, anonymize_user_id


async def delete_user_ml_data(user_id: UUID, db: AsyncSession) -> Dict[str, int]:
    """
    Delete all ML data associated with a user (Right to be Forgotten).

    This function removes all anonymized ML data that can be linked back
    to the user through their hashed user_id or account_id.

    Args:
        user_id: User UUID to delete data for
        db: Database session

    Returns:
        Dictionary with count of deleted records per table

    Example:
        >>> deleted_counts = await delete_user_ml_data(user_id, db)
        >>> print(f"Deleted {deleted_counts['user_action_patterns']} action patterns")
    """
    deleted_counts = {}

    # Get user hash for matching ML data
    user_hash = anonymize_user_id(str(user_id))

    try:
        # 1. Delete UserActionPattern records
        result = await db.execute(
            delete(UserActionPattern).where(UserActionPattern.user_hash == user_hash)
        )
        deleted_counts["user_action_patterns"] = result.rowcount

        # 2. Delete CostTrendData records
        # Need to get all cloud accounts for this user first
        from app.models.cloud_account import CloudAccount

        result = await db.execute(select(CloudAccount).where(CloudAccount.user_id == user_id))
        user_accounts = result.scalars().all()

        cost_trends_deleted = 0
        for account in user_accounts:
            account_hash = anonymize_account_id(str(account.id))
            result = await db.execute(
                delete(CostTrendData).where(CostTrendData.account_hash == account_hash)
            )
            cost_trends_deleted += result.rowcount
        deleted_counts["cost_trend_data"] = cost_trends_deleted

        # 3. Delete MLTrainingData records
        # These are harder to link back since they're fully anonymized
        # We can only delete those created within user's scan timeframes
        # For now, we'll log that this requires manual review
        deleted_counts["ml_training_data"] = 0  # Requires manual review

        # 4. Delete ResourceLifecycleEvent records
        # Similar to MLTrainingData - requires resource hash mapping
        deleted_counts["resource_lifecycle_events"] = 0  # Requires manual review

        # 5. Delete CloudWatchMetricsHistory records
        # These are fully anonymized - no user link
        deleted_counts["cloudwatch_metrics_history"] = 0  # No user link

        # 6. Remove ML consent from user preferences
        result = await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        preferences = result.scalar_one_or_none()
        if preferences:
            preferences.ml_data_collection_consent = False
            preferences.ml_consent_date = None
            preferences.anonymized_industry = None
            preferences.anonymized_company_size = None

        await db.commit()

        print(f"✅ GDPR data deletion completed for user {user_id}: {deleted_counts}")

        return deleted_counts

    except Exception as e:
        await db.rollback()
        print(f"❌ GDPR data deletion failed for user {user_id}: {e}")
        raise


async def export_user_ml_data(user_id: UUID, db: AsyncSession) -> Dict[str, Any]:
    """
    Export all ML data associated with a user (Right to Access).

    Returns anonymized data that was collected from this user's scans.

    Args:
        user_id: User UUID to export data for
        db: Database session

    Returns:
        Dictionary with all user's ML data

    Example:
        >>> user_data = await export_user_ml_data(user_id, db)
        >>> print(f"User has {len(user_data['action_patterns'])} action patterns")
    """
    user_hash = anonymize_user_id(str(user_id))

    user_data: Dict[str, Any] = {
        "user_id": str(user_id),
        "export_date": datetime.now().isoformat(),
        "action_patterns": [],
        "cost_trends": [],
        "ml_consent": {},
    }

    try:
        # 1. Export UserActionPattern records
        result = await db.execute(
            select(UserActionPattern).where(UserActionPattern.user_hash == user_hash)
        )
        action_patterns = result.scalars().all()

        for pattern in action_patterns:
            user_data["action_patterns"].append(
                {
                    "resource_type": pattern.resource_type,
                    "provider": pattern.provider,
                    "detection_scenario": pattern.detection_scenario,
                    "action_taken": pattern.action_taken,
                    "time_to_action_hours": pattern.time_to_action_hours,
                    "cost_saved_monthly": pattern.cost_saved_monthly,
                    "detected_at": pattern.detected_at.isoformat(),
                    "action_at": pattern.action_at.isoformat(),
                }
            )

        # 2. Export CostTrendData records
        from app.models.cloud_account import CloudAccount

        result = await db.execute(select(CloudAccount).where(CloudAccount.user_id == user_id))
        user_accounts = result.scalars().all()

        for account in user_accounts:
            account_hash = anonymize_account_id(str(account.id))
            result = await db.execute(
                select(CostTrendData).where(CostTrendData.account_hash == account_hash)
            )
            cost_trends = result.scalars().all()

            for trend in cost_trends:
                user_data["cost_trends"].append(
                    {
                        "month": trend.month,
                        "provider": trend.provider,
                        "total_spend": trend.total_spend,
                        "waste_detected": trend.waste_detected,
                        "waste_eliminated": trend.waste_eliminated,
                        "waste_percentage": trend.waste_percentage,
                    }
                )

        # 3. Export ML consent information
        result = await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        preferences = result.scalar_one_or_none()

        if preferences:
            user_data["ml_consent"] = {
                "consent_given": preferences.ml_data_collection_consent,
                "consent_date": (
                    preferences.ml_consent_date.isoformat()
                    if preferences.ml_consent_date
                    else None
                ),
                "industry": preferences.anonymized_industry,
                "company_size": preferences.anonymized_company_size,
                "data_retention_years": preferences.data_retention_years,
            }

        print(f"✅ GDPR data export completed for user {user_id}")

        return user_data

    except Exception as e:
        print(f"❌ GDPR data export failed for user {user_id}: {e}")
        raise


async def anonymize_user_data_on_account_deletion(user_id: UUID, db: AsyncSession) -> None:
    """
    Anonymize or delete user data when user deletes their account.

    This ensures compliance with GDPR while preserving valuable ML data
    by fully anonymizing it (removing any possible link back to the user).

    Args:
        user_id: User UUID being deleted
        db: Database session
    """
    try:
        # Delete all personally identifiable ML data
        deleted_counts = await delete_user_ml_data(user_id, db)

        print(f"✅ User data anonymized on account deletion: {deleted_counts}")

    except Exception as e:
        print(f"❌ Failed to anonymize user data on account deletion: {e}")
        raise


async def check_user_consent_status(user_id: UUID, db: AsyncSession) -> Dict[str, Any]:
    """
    Check user's ML data collection consent status.

    Args:
        user_id: User UUID to check
        db: Database session

    Returns:
        Dictionary with consent information
    """
    result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    preferences = result.scalar_one_or_none()

    if not preferences:
        return {
            "has_consent": False,
            "consent_date": None,
            "data_retention_years": "3",
            "message": "User has not set ML data collection preferences",
        }

    return {
        "has_consent": preferences.ml_data_collection_consent,
        "consent_date": (
            preferences.ml_consent_date.isoformat() if preferences.ml_consent_date else None
        ),
        "data_retention_years": preferences.data_retention_years,
        "industry": preferences.anonymized_industry,
        "company_size": preferences.anonymized_company_size,
    }


async def list_user_ml_data_summary(user_id: UUID, db: AsyncSession) -> Dict[str, int]:
    """
    Get a summary count of all ML data associated with a user.

    Useful for transparency - showing users what data we have about them.

    Args:
        user_id: User UUID
        db: Database session

    Returns:
        Dictionary with count of records per data type
    """
    user_hash = anonymize_user_id(str(user_id))

    summary = {}

    try:
        # Count UserActionPattern records
        result = await db.execute(
            select(UserActionPattern).where(UserActionPattern.user_hash == user_hash)
        )
        summary["action_patterns"] = len(result.scalars().all())

        # Count CostTrendData records
        from app.models.cloud_account import CloudAccount

        result = await db.execute(select(CloudAccount).where(CloudAccount.user_id == user_id))
        user_accounts = result.scalars().all()

        cost_trends_count = 0
        for account in user_accounts:
            account_hash = anonymize_account_id(str(account.id))
            result = await db.execute(
                select(CostTrendData).where(CostTrendData.account_hash == account_hash)
            )
            cost_trends_count += len(result.scalars().all())
        summary["cost_trends"] = cost_trends_count

        summary["ml_training_data"] = 0  # Cannot be directly linked to user
        summary["lifecycle_events"] = 0  # Cannot be directly linked to user
        summary["metrics_history"] = 0  # Cannot be directly linked to user

        return summary

    except Exception as e:
        print(f"❌ Failed to get ML data summary for user {user_id}: {e}")
        raise
