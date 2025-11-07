"""
User Action Tracking Service.

Tracks user decisions (delete, ignore, keep) on orphan resources
for ML training when user has given consent.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloud_account import CloudAccount
from app.models.orphan_resource import OrphanResource
from app.models.user import User
from app.models.user_action_pattern import UserActionPattern
from app.services.ml_anonymization import anonymize_user_id
from app.services.ml_data_collector import (
    update_cost_trend_with_eliminated_waste,
    update_ml_training_data_with_user_action,
)


async def track_user_action(
    resource: OrphanResource,
    action: str,  # deleted, ignored, kept
    user: User,
    cloud_account: CloudAccount,
    db: AsyncSession,
) -> None:
    """
    Record user action on an orphan resource for ML training.

    Args:
        resource: The orphan resource
        action: Action taken (deleted, ignored, kept)
        user: User who took the action
        cloud_account: Cloud account the resource belongs to
        db: Database session
    """
    # Data collection is automatic (mentioned in CGV/Terms of Service)
    # No frontend opt-in required - user agreed via CGV
    try:
        # Extract metadata
        metadata = resource.resource_metadata or {}
        detection_scenario = metadata.get("detection_scenario", "unknown")
        confidence_level = metadata.get("confidence", "medium")

        # Calculate time to action
        time_to_action_hours = calculate_time_to_action(resource.created_at, datetime.now())

        # Calculate cost saved (only if deleted)
        cost_saved = resource.estimated_monthly_cost if action == "deleted" else 0.0

        # Create user action pattern record
        user_action = UserActionPattern(
            user_hash=anonymize_user_id(str(user.id)),
            resource_type=resource.resource_type,
            provider=cloud_account.provider,
            detection_scenario=detection_scenario,
            confidence_level=confidence_level,
            action_taken=action,
            time_to_action_hours=time_to_action_hours,
            cost_monthly=resource.estimated_monthly_cost,
            cost_saved_monthly=cost_saved,
            industry_anonymized=user.preferences.anonymized_industry,
            company_size_bucket=user.preferences.anonymized_company_size,
            detected_at=resource.created_at,
            action_at=datetime.now(),
        )

        db.add(user_action)
        await db.commit()

        # Update ML training data with this action
        await update_ml_training_data_with_user_action(
            resource_id=resource.id,
            action=action,
            db=db,
        )

        # If deleted, update cost trend data
        if action == "deleted":
            current_month = datetime.now().strftime("%Y-%m")
            await update_cost_trend_with_eliminated_waste(
                cloud_account_id=cloud_account.id,
                month=current_month,
                cost_eliminated=resource.estimated_monthly_cost,
                db=db,
            )

        print(f"✅ Tracked user action: {action} on {resource.resource_type} (resource {resource.id})")

    except Exception as e:
        print(f"⚠️ Failed to track user action for resource {resource.id}: {e}")
        # Don't raise - this is non-critical


def calculate_time_to_action(detected_at: datetime, action_at: datetime) -> int:
    """
    Calculate time between detection and action in hours.

    Args:
        detected_at: When resource was detected as waste
        action_at: When user took action on it

    Returns:
        Time difference in hours
    """
    time_delta = action_at - detected_at
    hours = int(time_delta.total_seconds() / 3600)
    return max(0, hours)  # Ensure non-negative
