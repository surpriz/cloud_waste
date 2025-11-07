"""Resource Lifecycle Event database model."""

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceLifecycleEvent(Base):
    """
    Historical events for resource lifecycle tracking.

    Records lifecycle events of cloud resources for time-series analysis
    and ML training. Uses hashed resource IDs for anonymization.
    """

    __tablename__ = "resource_lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Resource identification (anonymized)
    resource_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )  # SHA256 hash of resource_id (for tracking same resource over time)

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    region_anonymized: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Event information
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )  # detected, status_changed, deleted, metrics_updated

    # Resource state at event
    age_at_event_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cost_at_event: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Metrics snapshot at event time
    metrics_snapshot: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )  # CloudWatch metrics at this point in time

    # Event metadata
    event_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )  # Additional context (status change, detection reason, etc.)

    # Timestamp
    event_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ResourceLifecycleEvent {self.event_type}:{self.resource_type}>"
