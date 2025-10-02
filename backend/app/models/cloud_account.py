"""CloudAccount database model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class CloudAccount(Base):
    """Cloud account connection model."""

    __tablename__ = "cloud_accounts"

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
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'aws', 'azure', 'gcp'
    account_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    account_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # AWS Account ID, Azure Subscription ID, etc.

    # Encrypted credentials stored as binary
    credentials_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    # Metadata
    regions: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )  # List of regions to scan, e.g., ['eu-west-1', 'us-east-1']

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    last_scan_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
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
    user: Mapped["User"] = relationship("User", back_populates="cloud_accounts")  # type: ignore
    scans: Mapped[list["Scan"]] = relationship(  # type: ignore
        "Scan",
        back_populates="cloud_account",
        cascade="all, delete-orphan",
    )
    orphan_resources: Mapped[list["OrphanResource"]] = relationship(  # type: ignore
        "OrphanResource",
        back_populates="cloud_account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<CloudAccount {self.provider}:{self.account_name}>"
