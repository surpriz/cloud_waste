"""Pricing cache database model for storing cloud provider pricing data."""

import uuid
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import Float, Index, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class CloudProvider(str, Enum):
    """Cloud provider enumeration."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class PricingCache(Base):
    """
    Pricing cache model for storing cloud provider pricing data.

    This table caches pricing information retrieved from cloud provider APIs
    (AWS Price List API, Azure Retail Prices API, GCP Cloud Billing API).

    Purpose:
    - Reduce API calls to cloud providers (rate limits, performance)
    - Provide fallback when cloud APIs are unavailable
    - Track pricing history and detect significant price changes
    - Support multi-region pricing (prices vary by region)

    Cache Strategy:
    - TTL: 24 hours (expires_at)
    - Refresh: Daily via Celery Beat task at 2 AM
    - Fallback: Hardcoded prices if API fails or cache expired

    Example entries:
    - AWS EBS gp3 in us-east-1: $0.08/GB/month
    - Azure Standard_LRS disk in eastus: $0.048/GB/month
    - GCP pd-standard in us-central1: $0.04/GB/month
    """

    __tablename__ = "pricing_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Cloud provider (aws, azure, gcp)
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Cloud provider: aws, azure, gcp",
    )

    # Service/SKU identifier (e.g., 'ebs_gp3', 'Standard_LRS', 'pd-standard')
    service: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Service or SKU identifier (e.g., ebs_gp3, Standard_LRS)",
    )

    # Region (e.g., 'us-east-1', 'eastus', 'us-central1')
    region: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Cloud region (e.g., us-east-1, eastus, us-central1)",
    )

    # Price per unit (e.g., $/GB/month, $/hour)
    price_per_unit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Price per unit (e.g., $/GB/month, $/hour)",
    )

    # Unit of measurement (e.g., 'GB', 'hour', 'request')
    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="GB",
        comment="Unit of measurement (e.g., GB, hour, request)",
    )

    # Currency (always USD for now)
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
        comment="Currency code (USD)",
    )

    # Metadata: Source of pricing data
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Source of pricing (api, fallback, manual)",
    )

    # Pricing API response metadata (optional, for debugging)
    api_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Original API response metadata (for debugging)",
    )

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when price was last updated",
    )

    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(hours=24),
        comment="Expiration timestamp (24h TTL)",
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    # Composite index for fast lookups
    __table_args__ = (
        Index(
            "ix_pricing_cache_lookup",
            "provider",
            "service",
            "region",
            unique=True,
        ),
        Index(
            "ix_pricing_cache_expires_at",
            "expires_at",
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PricingCache {self.provider}:{self.service}:{self.region} "
            f"${self.price_per_unit}/{self.unit}>"
        )

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.utcnow() > self.expires_at

    def refresh_expiration(self) -> None:
        """Refresh expiration to 24 hours from now."""
        self.expires_at = datetime.utcnow() + timedelta(hours=24)
        self.last_updated = datetime.utcnow()
