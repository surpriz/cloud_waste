"""All cloud resources database model (inventory mode)."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Float, ForeignKey, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceUtilization(str, Enum):
    """Resource utilization status."""

    IDLE = "idle"  # Resource exists but not used (0% utilization)
    LOW = "low"  # Low utilization (<30%)
    MEDIUM = "medium"  # Medium utilization (30-70%)
    HIGH = "high"  # High utilization (>70%)
    UNKNOWN = "unknown"  # Utilization data not available


class OptimizationPriority(str, Enum):
    """Optimization priority level."""

    CRITICAL = "critical"  # Immediate action needed (high cost + low value)
    HIGH = "high"  # Should optimize soon
    MEDIUM = "medium"  # Nice to optimize
    LOW = "low"  # Already optimized or low impact
    NONE = "none"  # No optimization needed


class AllCloudResource(Base):
    """
    All cloud resources model (inventory mode).

    This table stores ALL cloud resources (not just orphans) to provide
    a complete cost intelligence view. Used for:
    - Cost breakdown by service/region
    - High-cost resource alerts
    - Optimization recommendations
    - Budget tracking
    """

    __tablename__ = "all_cloud_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Resource identification
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    resource_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    region: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Cost information
    estimated_monthly_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        index=True,  # Index for sorting by cost
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    # Utilization metrics
    utilization_status: Mapped[str] = mapped_column(
        String(20),
        default=ResourceUtilization.UNKNOWN.value,
        nullable=False,
        index=True,
    )
    cpu_utilization_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    memory_utilization_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    storage_utilization_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    network_utilization_mbps: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Optimization recommendations
    is_optimizable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    optimization_priority: Mapped[str] = mapped_column(
        String(20),
        default=OptimizationPriority.NONE.value,
        nullable=False,
        index=True,
    )
    optimization_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Score 0-100: 0=perfectly optimized, 100=highly wasteful",
    )
    potential_monthly_savings: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    optimization_recommendations: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of optimization suggestions with cost impact",
    )

    # Resource metadata
    resource_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Raw metadata from cloud provider (tags, config, etc.)",
    )
    tags: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Resource tags for categorization and cost allocation",
    )

    # Status tracking
    resource_status: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Cloud provider status (running, stopped, available, etc.)",
    )
    is_orphan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="True if this resource is also in orphan_resources table",
    )

    # Timestamps
    created_at_cloud: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When resource was created in cloud provider",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last time resource was actively used",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    cloud_account: Mapped["CloudAccount"] = relationship(  # type: ignore
        "CloudAccount",
        back_populates="all_resources",
    )
    scan: Mapped["Scan"] = relationship(  # type: ignore
        "Scan",
        back_populates="all_resources",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<AllCloudResource {self.resource_type}:{self.resource_id} ${self.estimated_monthly_cost}/mo>"
