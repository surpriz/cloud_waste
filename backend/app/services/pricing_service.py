"""Pricing service for dynamic cloud provider pricing."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.pricing_cache import CloudProvider, PricingCache

logger = structlog.get_logger()


# Fallback hardcoded prices (used if API fails AND cache is empty)
FALLBACK_PRICING = {
    "aws": {
        # EBS volumes
        "ebs_gp3": 0.08,  # $0.08/GB/month
        "ebs_gp2": 0.10,
        "ebs_io1": 0.125,
        "ebs_io2": 0.125,
        "ebs_st1": 0.045,
        "ebs_sc1": 0.015,
        # Elastic IPs
        "elastic_ip": 3.60,  # $3.60/month
        # Load Balancers
        "alb": 16.20,  # Application Load Balancer
        "nlb": 16.20,  # Network Load Balancer
        "clb": 18.00,  # Classic Load Balancer
        # Add more as needed
    },
    "azure": {
        # Managed Disks
        "Standard_LRS": 0.048,  # Standard HDD
        "StandardSSD_LRS": 0.096,  # Standard SSD
        "Premium_LRS": 0.15,  # Premium SSD
        # Public IPs
        "public_ip_basic": 3.00,
        "public_ip_standard": 3.00,
    },
    "gcp": {
        # Persistent Disks
        "pd-standard": 0.04,  # Standard persistent disk
        "pd-balanced": 0.10,  # Balanced persistent disk
        "pd-ssd": 0.17,  # SSD persistent disk
    },
}


class AWSPricingClient:
    """
    Client for AWS Price List API.

    AWS Pricing API documentation:
    https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html

    IMPORTANT: AWS Pricing API is only available in:
    - us-east-1 (North Virginia)
    - ap-south-1 (Mumbai)

    All API calls must be made to us-east-1 regardless of the resource region.
    """

    def __init__(self):
        """Initialize AWS Pricing API client (us-east-1 only)."""
        self.client = boto3.client("pricing", region_name="us-east-1")

    def _region_code_to_location(self, region_code: str) -> str:
        """
        Convert AWS region code to location name used by Pricing API.

        Example: 'us-east-1' → 'US East (N. Virginia)'
        """
        region_map = {
            "us-east-1": "US East (N. Virginia)",
            "us-east-2": "US East (Ohio)",
            "us-west-1": "US West (N. California)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "Europe (Ireland)",
            "eu-west-2": "Europe (London)",
            "eu-west-3": "Europe (Paris)",
            "eu-central-1": "Europe (Frankfurt)",
            "ap-southeast-1": "Asia Pacific (Singapore)",
            "ap-southeast-2": "Asia Pacific (Sydney)",
            "ap-northeast-1": "Asia Pacific (Tokyo)",
            "ap-northeast-2": "Asia Pacific (Seoul)",
            # Add more regions as needed
        }
        return region_map.get(region_code, region_code)

    async def get_ebs_price(self, volume_type: str, region: str) -> float | None:
        """
        Get EBS volume price per GB/month from AWS Pricing API.

        Args:
            volume_type: EBS volume type ('gp2', 'gp3', 'io1', 'io2', 'st1', 'sc1')
            region: AWS region code (e.g., 'us-east-1')

        Returns:
            Price per GB/month in USD, or None if not found
        """
        try:
            # AWS Pricing API uses synchronous boto3, run in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_products(
                    ServiceCode="AmazonEC2",
                    Filters=[
                        {"Type": "TERM_MATCH", "Field": "volumeApiName", "Value": volume_type},
                        {
                            "Type": "TERM_MATCH",
                            "Field": "location",
                            "Value": self._region_code_to_location(region),
                        },
                        {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
                    ],
                    MaxResults=1,
                ),
            )

            if not response.get("PriceList"):
                logger.warning(
                    "aws.pricing.not_found",
                    volume_type=volume_type,
                    region=region,
                )
                return None

            # Parse nested AWS pricing JSON structure
            price_item = json.loads(response["PriceList"][0])
            terms = price_item.get("terms", {}).get("OnDemand", {})

            for term_sku, term_attrs in terms.items():
                price_dimensions = term_attrs.get("priceDimensions", {})
                for dim_key, dim_attrs in price_dimensions.items():
                    price_per_unit = dim_attrs.get("pricePerUnit", {}).get("USD")
                    if price_per_unit:
                        return float(price_per_unit)

            return None

        except (BotoCoreError, ClientError) as e:
            logger.error(
                "aws.pricing.api_error",
                error=str(e),
                volume_type=volume_type,
                region=region,
            )
            return None
        except Exception as e:
            logger.error(
                "aws.pricing.unexpected_error",
                error=str(e),
                volume_type=volume_type,
                region=region,
            )
            return None

    async def get_elastic_ip_price(self, region: str) -> float | None:
        """
        Get Elastic IP price per month from AWS Pricing API.

        Args:
            region: AWS region code

        Returns:
            Price per month in USD, or None if not found
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_products(
                    ServiceCode="AmazonEC2",
                    Filters=[
                        {
                            "Type": "TERM_MATCH",
                            "Field": "location",
                            "Value": self._region_code_to_location(region),
                        },
                        {
                            "Type": "TERM_MATCH",
                            "Field": "productFamily",
                            "Value": "IP Address",
                        },
                        {"Type": "TERM_MATCH", "Field": "usagetype", "Value": "ElasticIP:IdleAddress"},
                    ],
                    MaxResults=1,
                ),
            )

            if not response.get("PriceList"):
                return None

            # Parse pricing (hourly rate * 730 hours/month)
            price_item = json.loads(response["PriceList"][0])
            terms = price_item.get("terms", {}).get("OnDemand", {})

            for term_sku, term_attrs in terms.items():
                price_dimensions = term_attrs.get("priceDimensions", {})
                for dim_key, dim_attrs in price_dimensions.items():
                    price_per_hour = dim_attrs.get("pricePerUnit", {}).get("USD")
                    if price_per_hour:
                        # Convert hourly to monthly (730 hours/month)
                        return float(price_per_hour) * 730

            return None

        except Exception as e:
            logger.error(
                "aws.pricing.elastic_ip_error",
                error=str(e),
                region=region,
            )
            return None


class PricingService:
    """
    Centralized pricing service for all cloud providers.

    Pricing strategy (3-tier fallback):
    1. Redis cache (24h TTL) - Fastest, lowest latency
    2. PostgreSQL pricing_cache table - Backup if Redis fails
    3. Hardcoded fallback prices - Last resort if APIs unavailable

    Usage:
        service = PricingService(db_session)
        price = await service.get_aws_price("ebs_gp3", "us-east-1")
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize pricing service.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db
        self.aws_client = AWSPricingClient()

    async def get_aws_price(
        self,
        service: str,
        region: str,
        force_refresh: bool = False,
    ) -> float:
        """
        Get AWS service price with multi-tier caching.

        Args:
            service: Service identifier (e.g., 'ebs_gp3', 'elastic_ip')
            region: AWS region code (e.g., 'us-east-1')
            force_refresh: Skip cache and fetch from API

        Returns:
            Price per unit (e.g., $/GB/month)
        """
        cache_key = f"pricing:aws:{service}:{region}"

        # 1. Try Redis cache (TODO: implement Redis integration)
        # For now, skip Redis and go directly to PostgreSQL

        if not force_refresh:
            # 2. Try PostgreSQL cache
            cached_price = await self._get_cached_price_from_db(
                CloudProvider.AWS.value, service, region
            )
            if cached_price is not None:
                logger.debug(
                    "pricing.cache_hit",
                    provider="aws",
                    service=service,
                    region=region,
                    price=cached_price,
                )
                return cached_price

        # 3. Fetch from AWS Pricing API
        api_price = await self._fetch_aws_price_from_api(service, region)

        if api_price is not None:
            # Cache the price in PostgreSQL
            await self._save_price_to_db(
                CloudProvider.AWS.value,
                service,
                region,
                api_price,
                source="api",
            )
            logger.info(
                "pricing.api_success",
                provider="aws",
                service=service,
                region=region,
                price=api_price,
            )
            return api_price

        # 4. Fallback to hardcoded prices
        fallback_price = FALLBACK_PRICING["aws"].get(service)
        if fallback_price is None:
            # Unknown service, use conservative estimate
            fallback_price = 0.10
            logger.warning(
                "pricing.fallback_unknown_service",
                provider="aws",
                service=service,
                region=region,
                fallback_price=fallback_price,
            )
        else:
            logger.warning(
                "pricing.fallback_used",
                provider="aws",
                service=service,
                region=region,
                fallback_price=fallback_price,
            )

        # Cache the fallback price so it appears in the dashboard
        await self._save_price_to_db(
            CloudProvider.AWS.value,
            service,
            region,
            fallback_price,
            source="fallback",
        )

        return fallback_price

    async def _fetch_aws_price_from_api(self, service: str, region: str) -> float | None:
        """
        Fetch price from AWS Pricing API based on service type.

        Args:
            service: Service identifier
            region: AWS region code

        Returns:
            Price or None if not found
        """
        if service.startswith("ebs_"):
            # EBS volume pricing
            volume_type = service.replace("ebs_", "")
            return await self.aws_client.get_ebs_price(volume_type, region)
        elif service == "elastic_ip":
            # Elastic IP pricing
            return await self.aws_client.get_elastic_ip_price(region)
        else:
            logger.warning(
                "pricing.unsupported_service",
                service=service,
                region=region,
            )
            return None

    async def _get_cached_price_from_db(
        self, provider: str, service: str, region: str
    ) -> float | None:
        """
        Get cached price from PostgreSQL pricing_cache table.

        Args:
            provider: Cloud provider ('aws', 'azure', 'gcp')
            service: Service identifier
            region: Region code

        Returns:
            Cached price or None if not found or expired
        """
        try:
            result = await self.db.execute(
                select(PricingCache).where(
                    PricingCache.provider == provider,
                    PricingCache.service == service,
                    PricingCache.region == region,
                    PricingCache.expires_at > datetime.utcnow(),
                )
            )
            cache_entry = result.scalar_one_or_none()

            if cache_entry:
                return cache_entry.price_per_unit

            return None

        except Exception as e:
            logger.error(
                "pricing.cache_read_error",
                error=str(e),
                provider=provider,
                service=service,
                region=region,
            )
            return None

    async def _save_price_to_db(
        self,
        provider: str,
        service: str,
        region: str,
        price: float,
        source: str = "api",
        api_metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Save or update price in PostgreSQL pricing_cache table.

        Args:
            provider: Cloud provider
            service: Service identifier
            region: Region code
            price: Price per unit
            source: Source of pricing ('api', 'fallback', 'manual')
            api_metadata: Optional API response metadata
        """
        try:
            # Check if entry exists
            result = await self.db.execute(
                select(PricingCache).where(
                    PricingCache.provider == provider,
                    PricingCache.service == service,
                    PricingCache.region == region,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing entry
                existing.price_per_unit = price
                existing.source = source
                existing.api_metadata = api_metadata
                existing.refresh_expiration()
                logger.debug(
                    "pricing.cache_updated",
                    provider=provider,
                    service=service,
                    region=region,
                    price=price,
                )
            else:
                # Create new entry
                new_entry = PricingCache(
                    provider=provider,
                    service=service,
                    region=region,
                    price_per_unit=price,
                    unit="GB",  # Default unit
                    source=source,
                    api_metadata=api_metadata,
                    expires_at=datetime.utcnow() + timedelta(hours=24),
                )
                self.db.add(new_entry)
                logger.debug(
                    "pricing.cache_created",
                    provider=provider,
                    service=service,
                    region=region,
                    price=price,
                )

            await self.db.commit()

        except Exception as e:
            logger.error(
                "pricing.cache_write_error",
                error=str(e),
                provider=provider,
                service=service,
                region=region,
            )
            await self.db.rollback()


# Singleton instance (optional, for convenience)
_pricing_service_instance: PricingService | None = None


def get_pricing_service(db: AsyncSession) -> PricingService:
    """Get or create PricingService instance."""
    return PricingService(db)
