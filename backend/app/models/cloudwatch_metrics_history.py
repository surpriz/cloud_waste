"""CloudWatch Metrics History database model."""

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class CloudWatchMetricsHistory(Base):
    """
    Extended CloudWatch metrics history for time-series analysis.

    Stores historical metrics data (7-90 days) to train prediction models
    for anomaly detection, waste forecasting, and rightsizing recommendations.
    """

    __tablename__ = "cloudwatch_metrics_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Resource identification (anonymized)
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

    # Metric information
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # CPUUtilization, NetworkIn, VolumeReadOps, etc.

    # Time-series data
    metric_values: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )  # {"timeseries": [...], "avg": X, "p50": Y, "p95": Z, "p99": W, "trend": "..."}

    aggregation_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # hourly, daily, weekly

    # Time range covered
    start_date: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    # Collection metadata
    collected_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<CloudWatchMetricsHistory {self.resource_type}:{self.metric_name}>"
