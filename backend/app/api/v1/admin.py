"""Admin API endpoints for user management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_superuser
from app.core.database import get_db
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import User as UserSchema, UserAdminUpdate

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
