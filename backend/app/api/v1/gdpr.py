"""GDPR compliance API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.gdpr_compliance import (
    check_user_consent_status,
    delete_user_ml_data,
    export_user_ml_data,
    list_user_ml_data_summary,
)

router = APIRouter()


@router.get("/consent-status")
async def get_consent_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's ML data collection consent status.

    Returns information about:
    - Whether user has given consent
    - When consent was given
    - Data retention period
    - Industry and company size (if provided)
    """
    consent_info = await check_user_consent_status(current_user.id, db)
    return consent_info


@router.get("/my-data-summary")
async def get_my_data_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary count of all ML data we have about current user.

    Returns counts for:
    - Action patterns (decisions on resources)
    - Cost trends (monthly aggregates)
    - ML training data (fully anonymized)
    """
    summary = await list_user_ml_data_summary(current_user.id, db)
    return summary


@router.get("/export-my-data")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all ML data associated with current user (Right to Access).

    Returns JSON with:
    - User action patterns
    - Cost trends
    - ML consent information
    """
    try:
        user_data = await export_user_ml_data(current_user.id, db)
        return JSONResponse(content=user_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export user data: {str(e)}",
        )


@router.delete("/delete-my-ml-data", status_code=status.HTTP_200_OK)
async def delete_my_ml_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete all ML data associated with current user (Right to be Forgotten).

    This will:
    1. Delete all user action patterns
    2. Delete all cost trends linked to user's accounts
    3. Remove ML consent from preferences
    4. Preserve fully anonymized data that cannot be linked back

    NOTE: This does NOT delete the user account itself, only ML data.
    To delete your entire account, use the account deletion endpoint.
    """
    try:
        deleted_counts = await delete_user_ml_data(current_user.id, db)

        return {
            "message": "Your ML data has been successfully deleted",
            "deleted_records": deleted_counts,
            "note": "Fully anonymized data that cannot be linked back to you has been preserved for ML training",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user ML data: {str(e)}",
        )
