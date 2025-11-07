"""User Preferences database model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserPreferences(Base):
    """
    User preferences for privacy, ML data collection, and personalization.

    Stores user consent for ML data collection and optional demographic
    information for improving recommendations.
    """

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ML Data Collection Consent
    ml_data_collection_consent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )  # Default: False (opt-in required)

    ml_consent_date: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )  # When user gave consent

    # Optional demographic data (for better ML recommendations)
    # Users can choose to share this for improved predictions
    anonymized_industry: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # tech, finance, healthcare, retail, manufacturing, etc.

    anonymized_company_size: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )  # small, medium, large, enterprise

    # Notification preferences
    email_scan_summaries: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    email_cost_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    email_marketing: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Data retention preferences
    data_retention_years: Mapped[int] = mapped_column(
        String(2),  # Using String to store as text "1", "2", "3"
        default="3",
        nullable=False,
    )  # How long to keep ML data (1, 2, or 3 years)

    # Timestamps
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
    user: Mapped["User"] = relationship(  # type: ignore
        "User",
        back_populates="preferences",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserPreferences user_id={self.user_id}>"
