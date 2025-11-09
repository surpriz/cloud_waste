"""Admin API endpoints for user management."""

import uuid
from typing import Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api.deps import get_current_superuser
from app.core.database import get_db
from app.crud import user as user_crud
from app.models.user import User
from app.models.ml_training_data import MLTrainingData
from app.models.user_action_pattern import UserActionPattern
from app.models.cost_trend_data import CostTrendData
from app.schemas.user import User as UserSchema, UserAdminUpdate
from app.schemas.ses_metrics import SESMetrics
from app.services.ses_metrics_service import SESMetricsService
from app.ml.data_pipeline import export_all_ml_datasets

router = APIRouter()


class AdminStats(BaseModel):
    """Admin statistics schema."""

    total_users: int
    active_users: int
    inactive_users: int
    superusers: int


@router.get(
    "/stats",
    response_model=AdminStats,
    summary="Get admin statistics",
)
async def get_admin_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
) -> AdminStats:
    """
    Get admin statistics (superuser only).

    Returns:
        Admin statistics including user counts
    """
    total_users = await user_crud.count_users(db)
    active_users = await user_crud.count_active_users(db)
    superusers = await user_crud.count_superusers(db)

    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        inactive_users=total_users - active_users,
        superusers=superusers,
    )


@router.get(
    "/users",
    response_model=list[UserSchema],
    summary="Get all users",
)
async def get_all_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of users to return"),
) -> list[UserSchema]:
    """
    Get all users (superuser only).

    Args:
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return

    Returns:
        List of all users
    """
    users = await user_crud.get_all_users(db, skip=skip, limit=limit)
    return [UserSchema.model_validate(user) for user in users]


@router.get(
    "/users/{user_id}",
    response_model=UserSchema,
    summary="Get user by ID",
)
async def get_user_by_id(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
) -> UserSchema:
    """
    Get user by ID (superuser only).

    Args:
        user_id: User UUID

    Returns:
        User object

    Raises:
        HTTPException: If user not found
    """
    user = await user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserSchema.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserSchema,
    summary="Update user (admin)",
)
async def update_user_admin(
    user_id: uuid.UUID,
    user_update: UserAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> UserSchema:
    """
    Update user (superuser only).

    Admins can modify:
    - is_active (block/unblock user)
    - is_superuser (promote/demote admin)

    Args:
        user_id: User UUID
        user_update: User update data

    Returns:
        Updated user object

    Raises:
        HTTPException: If user not found or attempting to modify self
    """
    # Get target user
    target_user = await user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent admin from modifying themselves
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account via admin API. Use profile settings instead.",
        )

    # Update user
    updated_user = await user_crud.update_user(db, target_user, user_update)
    return UserSchema.model_validate(updated_user)


@router.post(
    "/users/{user_id}/toggle-active",
    response_model=UserSchema,
    summary="Toggle user active status",
)
async def toggle_user_active(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> UserSchema:
    """
    Toggle user active status (block/unblock) (superuser only).

    Args:
        user_id: User UUID

    Returns:
        Updated user object

    Raises:
        HTTPException: If user not found or attempting to modify self
    """
    # Get target user
    target_user = await user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent admin from blocking themselves
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block/unblock your own account",
        )

    # Toggle active status
    new_status = not target_user.is_active
    update_data = UserAdminUpdate(is_active=new_status)
    updated_user = await user_crud.update_user(db, target_user, update_data)

    return UserSchema.model_validate(updated_user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
)
async def delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> None:
    """
    Delete user permanently (superuser only).

    This will CASCADE delete all associated data:
    - Cloud accounts
    - Scans
    - Orphan resources
    - Chat conversations

    Args:
        user_id: User UUID

    Raises:
        HTTPException: If user not found or attempting to delete self
    """
    # Get target user
    target_user = await user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent admin from deleting themselves
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account. Contact another admin.",
        )

    # Delete user (CASCADE will handle related data)
    await user_crud.delete_user(db, target_user)

    return None


class MLDataStats(BaseModel):
    """ML data collection statistics schema."""

    total_ml_records: int
    total_user_actions: int
    total_cost_trends: int
    records_last_7_days: int
    records_last_30_days: int
    last_collection_date: datetime | None


@router.get(
    "/ml-stats",
    response_model=MLDataStats,
    summary="Get ML data collection statistics",
)
async def get_ml_data_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
) -> MLDataStats:
    """
    Get ML data collection statistics (superuser only).

    Returns:
        ML data statistics including record counts
    """
    # Count total records
    total_ml_records_result = await db.execute(select(func.count()).select_from(MLTrainingData))
    total_ml_records = total_ml_records_result.scalar_one()

    total_user_actions_result = await db.execute(
        select(func.count()).select_from(UserActionPattern)
    )
    total_user_actions = total_user_actions_result.scalar_one()

    total_cost_trends_result = await db.execute(select(func.count()).select_from(CostTrendData))
    total_cost_trends = total_cost_trends_result.scalar_one()

    # Count records in last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    records_last_7_days_result = await db.execute(
        select(func.count())
        .select_from(MLTrainingData)
        .where(MLTrainingData.created_at >= seven_days_ago)
    )
    records_last_7_days = records_last_7_days_result.scalar_one()

    # Count records in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    records_last_30_days_result = await db.execute(
        select(func.count())
        .select_from(MLTrainingData)
        .where(MLTrainingData.created_at >= thirty_days_ago)
    )
    records_last_30_days = records_last_30_days_result.scalar_one()

    # Get last collection date
    last_record_result = await db.execute(
        select(MLTrainingData.created_at).order_by(MLTrainingData.created_at.desc()).limit(1)
    )
    last_collection_date = last_record_result.scalar_one_or_none()

    return MLDataStats(
        total_ml_records=total_ml_records,
        total_user_actions=total_user_actions,
        total_cost_trends=total_cost_trends,
        records_last_7_days=records_last_7_days,
        records_last_30_days=records_last_30_days,
        last_collection_date=last_collection_date,
    )


class MLExportResponse(BaseModel):
    """ML data export response schema."""

    success: bool
    message: str
    files: dict[str, str]
    total_records_exported: int


@router.post(
    "/ml-export",
    response_model=MLExportResponse,
    summary="Export ML datasets",
)
async def export_ml_datasets(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_superuser)],
    days: int = Query(90, ge=7, le=365, description="Number of days to export"),
    output_format: str = Query("json", regex="^(json|csv)$", description="Export format (json or csv)"),
) -> MLExportResponse:
    """
    Export ML datasets for training (superuser only).

    Args:
        days: Number of days to export (7-365, default: 90)
        output_format: Export format (json or csv, default: json)

    Returns:
        Export result with file paths and record counts
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Export datasets
        files = await export_all_ml_datasets(
            output_format=output_format, output_dir="./ml_datasets"
        )

        # Count total records exported
        total_records = 0
        for file_path in files.values():
            if file_path and "ml_training_data" in file_path:
                # Count records from ml_training_data table
                result = await db.execute(
                    select(func.count())
                    .select_from(MLTrainingData)
                    .where(MLTrainingData.created_at >= start_date)
                )
                total_records = result.scalar_one()

        return MLExportResponse(
            success=True,
            message=f"Successfully exported ML datasets for last {days} days",
            files=files,
            total_records_exported=total_records,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export ML datasets: {str(e)}",
        )


@router.get(
    "/ses-metrics",
    response_model=SESMetrics,
    summary="Get AWS SES metrics",
)
async def get_ses_metrics(
    _: Annotated[User, Depends(get_current_superuser)],
) -> SESMetrics:
    """
    Get AWS SES email metrics (superuser only).

    Returns comprehensive SES metrics including:
    - Send statistics (24h, 7d, 30d)
    - Deliverability rates
    - Bounce and complaint rates
    - Send quotas and usage
    - Account reputation status
    - Alerts for critical thresholds

    Returns:
        SES metrics object

    Raises:
        HTTPException: If unable to fetch SES metrics
    """
    try:
        service = SESMetricsService()
        metrics = await service.get_ses_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch SES metrics: {str(e)}",
        )
