"""Orphan resource API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.crud import cloud_account as cloud_account_crud
from app.crud import orphan_resource as orphan_resource_crud
from app.models.orphan_resource import ResourceStatus
from app.models.user import User
from app.schemas.orphan_resource import (
    OrphanResource,
    OrphanResourceStats,
    OrphanResourceUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[OrphanResource])
async def list_orphan_resources(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    cloud_account_id: uuid.UUID | None = Query(None),
    status_filter: ResourceStatus | None = Query(None, alias="status"),
    resource_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> list[OrphanResource]:
    """
    List orphan resources.

    Can filter by cloud account, status, and resource type.
    """
    if cloud_account_id:
        # Verify account belongs to user
        account = await cloud_account_crud.get_cloud_account_by_id(db, cloud_account_id)

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud account not found",
            )

        if account.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this account's resources",
            )

        resources = await orphan_resource_crud.get_orphan_resources_by_account(
            db, cloud_account_id, status_filter, resource_type, skip, limit
        )
    else:
        # Get resources for all user's accounts
        # This requires joining through cloud_accounts
        from app.models.cloud_account import CloudAccount
        from app.models.orphan_resource import OrphanResource as OrphanResourceModel
        from sqlalchemy import select

        query = (
            select(OrphanResourceModel)
            .join(CloudAccount)
            .where(CloudAccount.user_id == current_user.id)
        )

        if status_filter:
            query = query.where(OrphanResourceModel.status == status_filter.value)

        if resource_type:
            query = query.where(OrphanResourceModel.resource_type == resource_type)

        result = await db.execute(query.offset(skip).limit(limit))
        resources = list(result.scalars().all())

    return resources


@router.get("/stats", response_model=OrphanResourceStats)
async def get_orphan_resource_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    cloud_account_id: uuid.UUID | None = Query(None),
    status_filter: ResourceStatus | None = Query(None, alias="status"),
) -> OrphanResourceStats:
    """
    Get orphan resource statistics.

    Optionally filter by cloud account and status.
    """
    if cloud_account_id:
        # Verify account belongs to user
        account = await cloud_account_crud.get_cloud_account_by_id(db, cloud_account_id)

        if not account or account.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud account not found",
            )

    stats = await orphan_resource_crud.get_orphan_resource_statistics(
        db, cloud_account_id, status_filter
    )
    return OrphanResourceStats(**stats)


@router.get("/top-cost", response_model=list[OrphanResource])
async def get_top_cost_resources(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    cloud_account_id: uuid.UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> list[OrphanResource]:
    """
    Get top orphan resources by estimated monthly cost.
    """
    if cloud_account_id:
        # Verify account belongs to user
        account = await cloud_account_crud.get_cloud_account_by_id(db, cloud_account_id)

        if not account or account.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud account not found",
            )

    resources = await orphan_resource_crud.get_top_cost_resources(
        db, cloud_account_id, limit
    )
    return resources


@router.get("/{resource_id}", response_model=OrphanResource)
async def get_orphan_resource(
    resource_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> OrphanResource:
    """
    Get a specific orphan resource by ID.
    """
    resource = await orphan_resource_crud.get_orphan_resource_by_id(db, resource_id)

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orphan resource not found",
        )

    # Verify resource belongs to user's account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db, resource.cloud_account_id
    )

    if not account or account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this resource",
        )

    return resource


@router.patch("/{resource_id}", response_model=OrphanResource)
async def update_orphan_resource(
    resource_id: uuid.UUID,
    resource_update: OrphanResourceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> OrphanResource:
    """
    Update an orphan resource (e.g., mark as ignored or for deletion).
    """
    resource = await orphan_resource_crud.get_orphan_resource_by_id(db, resource_id)

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orphan resource not found",
        )

    # Verify resource belongs to user's account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db, resource.cloud_account_id
    )

    if not account or account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this resource",
        )

    updated_resource = await orphan_resource_crud.update_orphan_resource(
        db, resource_id, resource_update
    )

    if not updated_resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orphan resource not found",
        )

    return updated_resource


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orphan_resource(
    resource_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Delete an orphan resource record.

    Note: This only removes the record from our database, it does not
    delete the actual cloud resource.
    """
    resource = await orphan_resource_crud.get_orphan_resource_by_id(db, resource_id)

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orphan resource not found",
        )

    # Verify resource belongs to user's account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db, resource.cloud_account_id
    )

    if not account or account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this resource",
        )

    await orphan_resource_crud.delete_orphan_resource(db, resource_id)
