"""All cloud resources Pydantic schemas (inventory mode)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.all_cloud_resource import (
    OptimizationPriority,
    ResourceUtilization,
)


class AllCloudResourceBase(BaseModel):
    """Base cloud resource schema."""

    resource_type: str = Field(description="Type of resource (e.g., ebs_volume)")
    resource_id: str = Field(description="Unique resource identifier")
    resource_name: str | None = Field(default=None, description="Human-readable name")
    region: str = Field(description="Cloud region")
    estimated_monthly_cost: float = Field(description="Monthly cost in USD")
    currency: str = Field(default="USD", description="Currency code")
    resource_metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata from cloud provider"
    )
    tags: dict[str, str] | None = Field(
        default=None, description="Resource tags for categorization"
    )


class AllCloudResourceCreate(AllCloudResourceBase):
    """Schema for creating a cloud resource (inventory mode)."""

    scan_id: uuid.UUID
    cloud_account_id: uuid.UUID
    utilization_status: ResourceUtilization | None = ResourceUtilization.UNKNOWN
    cpu_utilization_percent: float | None = None
    memory_utilization_percent: float | None = None
    storage_utilization_percent: float | None = None
    network_utilization_mbps: float | None = None
    is_optimizable: bool = False
    optimization_priority: OptimizationPriority = OptimizationPriority.NONE
    optimization_score: int = 0
    potential_monthly_savings: float = 0.0
    optimization_recommendations: list[dict[str, Any]] | None = None
    resource_status: str | None = None
    is_orphan: bool = False
    created_at_cloud: datetime | None = None
    last_used_at: datetime | None = None


class AllCloudResource(AllCloudResourceBase):
    """Schema for cloud resource response (inventory mode)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    cloud_account_id: uuid.UUID
    utilization_status: str
    cpu_utilization_percent: float | None
    memory_utilization_percent: float | None
    storage_utilization_percent: float | None
    network_utilization_mbps: float | None
    is_optimizable: bool
    optimization_priority: str
    optimization_score: int
    potential_monthly_savings: float
    optimization_recommendations: list[dict[str, Any]] | None
    resource_status: str | None
    is_orphan: bool
    created_at_cloud: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InventoryStats(BaseModel):
    """Schema for inventory statistics (all resources)."""

    total_resources: int
    total_monthly_cost: float
    total_annual_cost: float
    by_type: dict[str, int]
    by_region: dict[str, int]
    by_provider: dict[str, int]
    by_utilization: dict[str, int]
    optimizable_resources: int
    potential_monthly_savings: float
    potential_annual_savings: float
    high_cost_resources: int  # Resources > $100/month


class CostBreakdown(BaseModel):
    """Schema for detailed cost breakdown."""

    by_type: list[dict[str, Any]]
    by_region: list[dict[str, Any]]
    by_provider: list[dict[str, Any]]
    by_tag: list[dict[str, Any]] | None = None


class HighCostResource(BaseModel):
    """Schema for high-cost resource alert."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_name: str | None
    region: str
    estimated_monthly_cost: float
    utilization_status: str
    is_optimizable: bool
    potential_monthly_savings: float
    optimization_recommendations: list[dict[str, Any]] | None
    tags: dict[str, str] | None


class OptimizationRecommendation(BaseModel):
    """Schema for optimization recommendation."""

    resource_id: uuid.UUID
    resource_type: str
    resource_name: str | None
    current_monthly_cost: float
    recommended_action: str
    potential_monthly_savings: float
    priority: OptimizationPriority
    details: str
    alternatives: list[dict[str, Any]] | None = None


class CostTrend(BaseModel):
    """Schema for cost trend data."""

    date: datetime
    total_cost: float
    by_provider: dict[str, float]
    by_type: dict[str, float]


class BudgetStatus(BaseModel):
    """Schema for budget tracking."""

    monthly_budget: float | None
    current_spend: float
    projected_monthly_spend: float
    remaining_budget: float | None
    budget_utilization_percent: float | None
    is_over_budget: bool
    days_remaining_in_month: int
