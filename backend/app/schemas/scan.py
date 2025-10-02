"""Scan Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.scan import ScanStatus, ScanType


class ScanBase(BaseModel):
    """Base scan schema."""

    scan_type: ScanType = Field(default=ScanType.MANUAL)


class ScanCreate(ScanBase):
    """Schema for creating a scan."""

    cloud_account_id: uuid.UUID = Field(description="Cloud account to scan")


class ScanUpdate(BaseModel):
    """Schema for updating a scan."""

    status: ScanStatus | None = None
    total_resources_scanned: int | None = None
    orphan_resources_found: int | None = None
    estimated_monthly_waste: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Scan(ScanBase):
    """Schema for scan response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cloud_account_id: uuid.UUID
    status: str
    total_resources_scanned: int
    orphan_resources_found: int
    estimated_monthly_waste: float
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ScanWithResources(Scan):
    """Schema for scan with orphan resources."""

    orphan_resources: list["OrphanResource"] = []  # type: ignore  # noqa: F821


# Import at bottom to avoid circular imports
from app.schemas.orphan_resource import OrphanResource  # noqa: E402, F401


class ScanSummary(BaseModel):
    """Schema for scan summary statistics."""

    total_scans: int
    completed_scans: int
    failed_scans: int
    total_orphan_resources: int
    total_monthly_waste: float
    last_scan_at: datetime | None
