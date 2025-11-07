"""User Action Pattern database model."""

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class UserActionPattern(Base):
    """
    Anonymized user decision patterns for ML training.

    Records how users interact with detected waste (delete, ignore, keep)
    to learn preferences and improve recommendation accuracy.
    All user identifiers are hashed for privacy.
    """

    __tablename__ = "user_action_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # User identification (anonymized)
    user_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )  # SHA256 hash of user_id (for pattern tracking without exposing identity)

    # Resource and detection context
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    detection_scenario: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    confidence_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # User action
    action_taken: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )  # deleted, ignored, kept

    # Timing metrics
    time_to_action_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # Time between detection and action

    # Cost impact
    cost_monthly: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    cost_saved_monthly: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )  # Actual savings if deleted

    # User context (opt-in only)
    industry_anonymized: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )  # tech, finance, healthcare, retail, etc. (user can opt-in to share)

    company_size_bucket: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )  # small (<50), medium (50-500), large (500-5000), enterprise (5000+)

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    action_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserActionPattern {self.resource_type}:{self.action_taken}>"
