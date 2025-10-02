"""Scan database model."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ScanStatus(str, Enum):
    """Scan status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanType(str, Enum):
    """Scan type enumeration."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"


class Scan(Base):
    """Scan job model."""

    __tablename__ = "scans"

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
    status: Mapped[str] = mapped_column(
        String(20),
        default=ScanStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    scan_type: Mapped[str] = mapped_column(
        String(20),
        default=ScanType.MANUAL.value,
        nullable=False,
    )
    total_resources_scanned: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    orphan_resources_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    estimated_monthly_waste: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    cloud_account: Mapped["CloudAccount"] = relationship(  # type: ignore
        "CloudAccount",
        back_populates="scans",
    )
    orphan_resources: Mapped[list["OrphanResource"]] = relationship(  # type: ignore
        "OrphanResource",
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Scan {self.id} - {self.status}>"
