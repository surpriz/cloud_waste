"""Scan API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.crud import cloud_account as cloud_account_crud
from app.crud import scan as scan_crud
from app.models.user import User
from app.schemas.scan import Scan, ScanCreate, ScanSummary, ScanWithResources
from app.workers.tasks import scan_cloud_account

router = APIRouter()


@router.post("/", response_model=Scan, status_code=status.HTTP_201_CREATED)
async def create_scan(
    scan_in: ScanCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Scan:
    """
    Create a new scan job for a cloud account.

    Validates that the account belongs to the current user and queues
    a background task to perform the scan.
    """
    # Verify account belongs to user
    account = await cloud_account_crud.get_cloud_account_by_id(
        db, scan_in.cloud_account_id
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud account not found",
        )

    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to scan this account",
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloud account is inactive",
        )

    # Create scan record
    scan = await scan_crud.create_scan(db, scan_in)

    # Queue background task
    scan_cloud_account.delay(str(scan.id), str(account.id))

    return scan


@router.get("/", response_model=list[Scan])
async def list_scans(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> list[Scan]:
    """
    List all scans for the current user's cloud accounts.
    """
    scans = await scan_crud.get_scans_by_user(db, current_user.id, skip, limit)
    return scans


@router.get("/summary", response_model=ScanSummary)
async def get_scan_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    cloud_account_id: uuid.UUID | None = Query(None),
) -> ScanSummary:
    """
    Get scan summary statistics.

    Optionally filter by cloud account ID.
    """
    # If cloud_account_id provided, verify it belongs to user
    if cloud_account_id:
        account = await cloud_account_crud.get_cloud_account_by_id(db, cloud_account_id)
        if not account or account.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud account not found",
            )

    stats = await scan_crud.get_scan_statistics(db, cloud_account_id)
    return ScanSummary(**stats)


@router.get("/{scan_id}", response_model=ScanWithResources)
async def get_scan(
    scan_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ScanWithResources:
    """
    Get a specific scan by ID with its orphan resources.
    """
    scan = await scan_crud.get_scan_by_id(db, scan_id, load_resources=True)

    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    # Verify scan belongs to user's account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db, scan.cloud_account_id
    )

    if not account or account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this scan",
        )

    return scan


@router.get("/account/{cloud_account_id}", response_model=list[Scan])
async def list_scans_by_account(
    cloud_account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> list[Scan]:
    """
    List all scans for a specific cloud account.
    """
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
            detail="Not authorized to view this account's scans",
        )

    scans = await scan_crud.get_scans_by_account(db, cloud_account_id, skip, limit)
    return scans
