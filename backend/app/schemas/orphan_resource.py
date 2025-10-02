"""Orphan resource Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.orphan_resource import ResourceStatus


class OrphanResourceBase(BaseModel):
    """Base orphan resource schema."""

    resource_type: str = Field(description="Type of resource (e.g., ebs_volume)")
    resource_id: str = Field(description="Unique resource identifier")
    resource_name: str | None = Field(default=None, description="Human-readable name")
    region: str = Field(description="Cloud region")
    estimated_monthly_cost: float = Field(description="Monthly cost in USD")
    resource_metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata"
    )


class OrphanResourceCreate(OrphanResourceBase):
    """Schema for creating an orphan resource."""

    scan_id: uuid.UUID
    cloud_account_id: uuid.UUID


class OrphanResourceUpdate(BaseModel):
    """Schema for updating an orphan resource."""

    status: ResourceStatus | None = None
    resource_name: str | None = None


class OrphanResource(OrphanResourceBase):
    """Schema for orphan resource response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    cloud_account_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime


class OrphanResourceStats(BaseModel):
    """Schema for orphan resource statistics."""

    total_resources: int
    by_type: dict[str, int]
    by_region: dict[str, int]
    by_status: dict[str, int]
    total_monthly_cost: float
    total_annual_cost: float


class ResourceCostBreakdown(BaseModel):
    """Schema for resource cost breakdown."""

    resource_type: str
    count: int
    total_monthly_cost: float
    percentage: float
