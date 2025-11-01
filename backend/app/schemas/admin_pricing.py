"""Admin pricing schemas for API responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class PricingCacheItem(BaseModel):
    """Individual pricing cache entry."""

    provider: str = Field(..., description="Cloud provider (aws, azure, gcp)")
    service: str = Field(..., description="Service identifier (e.g., ebs_gp3)")
    region: str = Field(..., description="Cloud region")
    price_per_unit: float = Field(..., description="Price per unit")
    unit: str = Field(..., description="Unit of measurement (e.g., GB, hour)")
    currency: str = Field(..., description="Currency code (USD)")
    source: str = Field(..., description="Source of pricing (api, fallback)")
    last_updated: datetime = Field(..., description="Last update timestamp")
    expires_at: datetime = Field(..., description="Cache expiration timestamp")
    is_expired: bool = Field(..., description="Whether cache entry is expired")


class PricingStats(BaseModel):
    """Pricing system statistics."""

    total_cached_prices: int = Field(..., description="Total number of prices in cache")
    expired_prices: int = Field(..., description="Number of expired cache entries")
    api_sourced_prices: int = Field(..., description="Prices from cloud provider APIs")
    fallback_sourced_prices: int = Field(..., description="Prices from fallback/hardcoded")
    last_refresh_at: datetime | None = Field(None, description="Last pricing refresh timestamp")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage (0-100)")
    api_success_rate: float = Field(..., description="API call success rate (0-100)")


class PricingRefreshResponse(BaseModel):
    """Response from pricing refresh operation."""

    status: str = Field(..., description="Operation status (success, error)")
    task_id: str | None = Field(None, description="Celery task ID for tracking")
    message: str = Field(..., description="Human-readable message")
    updated_count: int | None = Field(None, description="Number of prices updated")
    failed_count: int | None = Field(None, description="Number of failed updates")
