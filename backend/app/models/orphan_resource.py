"""Orphan resource database model."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ResourceStatus(str, Enum):
    """Orphan resource status enumeration."""

    ACTIVE = "active"  # Resource is orphaned and active
    IGNORED = "ignored"  # User marked as ignore
    MARKED_FOR_DELETION = "marked_for_deletion"  # User wants to delete
    DELETED = "deleted"  # Resource has been deleted


class OrphanResource(Base):
    """Orphan resource model."""

    __tablename__ = "orphan_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    estimated_monthly_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    resource_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=ResourceStatus.ACTIVE.value,
        nullable=False,
        index=True,
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
    scan: Mapped["Scan"] = relationship(  # type: ignore
        "Scan",
        back_populates="orphan_resources",
    )
    cloud_account: Mapped["CloudAccount"] = relationship(  # type: ignore
        "CloudAccount",
        back_populates="orphan_resources",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<OrphanResource {self.resource_type}:{self.resource_id}>"
