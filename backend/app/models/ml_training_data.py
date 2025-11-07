"""ML Training Data database model."""

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MLTrainingData(Base):
    """
    Anonymized resource patterns for ML training.

    This table stores anonymized data about detected orphan resources
    to train prediction models for V2. All personally identifiable
    information (account IDs, resource IDs, names) is removed.
    """

    __tablename__ = "ml_training_data"

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
    )  # ebs_volume, ec2_instance, rds_instance, etc.

    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )  # aws, azure, gcp

    region_anonymized: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # us-*, eu-*, ap-*, other

    # Resource characteristics
    resource_age_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )  # Age of resource when detected as waste

    detection_scenario: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # idle_volume, stopped_instance, unused_eip, etc.

    # Metrics (anonymized aggregates)
    metrics_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )  # CloudWatch metrics aggregates (avg, p50, p95, p99, trend)

    # Cost information
    cost_monthly: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
    )  # Estimated monthly waste cost

    confidence_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )  # critical, high, medium, low

    # User action (nullable until user takes action)
    user_action: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )  # deleted, ignored, kept, null

    # Resource metadata (anonymized)
    resource_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )  # Size, type, etc. (no identifiable info)

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MLTrainingData {self.resource_type}:{self.detection_scenario}>"
