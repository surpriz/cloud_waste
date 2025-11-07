"""Cost Trend Data database model."""

import uuid
from datetime import datetime

from sqlalchemy import Float, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class CostTrendData(Base):
    """
    Anonymized cost trends for forecasting models.

    Aggregates monthly cost data by account (anonymized) to train
    forecasting models for budget prediction and anomaly detection.
    """

    __tablename__ = "cost_trend_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Account identification (anonymized)
    account_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )  # SHA256 hash of cloud_account_id

    # Time period
    month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,
    )  # YYYY-MM format

    # Provider
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Cost metrics
    total_spend: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )  # Total cloud spend for the month

    waste_detected: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )  # Total waste detected (monthly equivalent)

    waste_eliminated: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )  # Waste actually eliminated by user actions

    waste_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )  # waste_detected / total_spend * 100

    # Breakdown by resource type
    top_waste_categories: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )  # {"ebs_volume": 450, "ec2_instance": 320, ...}

    # Resource counts
    total_resources_scanned: Mapped[int] = mapped_column(
        Float,  # Using Float for consistency, but represents count
        nullable=False,
    )

    orphan_resources_found: Mapped[int] = mapped_column(
        Float,  # Using Float for consistency
        nullable=False,
    )

    # Regional breakdown (anonymized)
    regional_breakdown: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )  # {"us-*": 2400, "eu-*": 1800, ...}

    # Metadata
    scan_count: Mapped[int] = mapped_column(
        Float,  # Using Float for consistency
        nullable=False,
        default=1.0,
    )  # Number of scans during the month

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<CostTrendData {self.provider}:{self.month}>"
