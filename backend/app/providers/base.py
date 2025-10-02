"""Base abstract class for cloud provider implementations."""

from abc import ABC, abstractmethod
from typing import Any


class OrphanResourceData:
    """Data class for orphan resource information."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        resource_name: str | None,
        region: str,
        estimated_monthly_cost: float,
        resource_metadata: dict[str, Any],
    ) -> None:
        """
        Initialize orphan resource data.

        Args:
            resource_type: Type of resource (e.g., 'ebs_volume', 'elastic_ip')
            resource_id: Unique identifier of the resource
            resource_name: Human-readable name (if available)
            region: Cloud region where resource exists
            estimated_monthly_cost: Estimated monthly cost in USD
            resource_metadata: Additional metadata about the resource
        """
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.region = region
        self.estimated_monthly_cost = estimated_monthly_cost
        self.resource_metadata = resource_metadata


class CloudProviderBase(ABC):
    """
    Abstract base class for cloud provider implementations.

    All cloud providers (AWS, Azure, GCP) must implement this interface
    to ensure consistent scanning behavior across different providers.
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        regions: list[str] | None = None,
    ) -> None:
        """
        Initialize cloud provider client.

        Args:
            access_key: Provider access key or ID
            secret_key: Provider secret key or token
            regions: List of regions to scan (None = all regions)
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.regions = regions or []

    @abstractmethod
    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate cloud provider credentials.

        Returns:
            Dict with account information (account_id, arn, etc.)

        Raises:
            Exception: If credentials are invalid
        """
        pass

    @abstractmethod
    async def get_available_regions(self) -> list[str]:
        """
        Get list of available regions for the provider.

        Returns:
            List of region identifiers
        """
        pass

    @abstractmethod
    async def scan_unattached_volumes(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for unattached storage volumes.

        Args:
            region: Region to scan

        Returns:
            List of orphan volume resources
        """
        pass

    @abstractmethod
    async def scan_unassigned_ips(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for unassigned public IP addresses.

        Args:
            region: Region to scan

        Returns:
            List of orphan IP address resources
        """
        pass

    @abstractmethod
    async def scan_orphaned_snapshots(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for orphaned snapshots (parent resource deleted).

        Args:
            region: Region to scan

        Returns:
            List of orphan snapshot resources
        """
        pass

    @abstractmethod
    async def scan_stopped_instances(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for compute instances stopped for extended period.

        Args:
            region: Region to scan

        Returns:
            List of stopped instance resources
        """
        pass

    @abstractmethod
    async def scan_unused_load_balancers(
        self, region: str
    ) -> list[OrphanResourceData]:
        """
        Scan for load balancers with no healthy backends.

        Args:
            region: Region to scan

        Returns:
            List of unused load balancer resources
        """
        pass

    @abstractmethod
    async def scan_stopped_databases(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for database instances stopped for extended period.

        Args:
            region: Region to scan

        Returns:
            List of stopped database resources
        """
        pass

    @abstractmethod
    async def scan_unused_nat_gateways(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for NAT gateways with no traffic.

        Args:
            region: Region to scan

        Returns:
            List of unused NAT gateway resources
        """
        pass

    async def scan_all_resources(
        self, region: str, detection_rules: dict[str, dict] | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan all resource types in a specific region.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules per resource type

        Returns:
            Combined list of all orphan resources found
        """
        results: list[OrphanResourceData] = []
        rules = detection_rules or {}

        # Execute all scan methods with user's rules
        results.extend(
            await self.scan_unattached_volumes(region, rules.get("ebs_volume"))
        )
        results.extend(await self.scan_unassigned_ips(region))
        results.extend(await self.scan_orphaned_snapshots(region))
        results.extend(await self.scan_stopped_instances(region))
        results.extend(await self.scan_unused_load_balancers(region))
        results.extend(await self.scan_stopped_databases(region))
        results.extend(await self.scan_unused_nat_gateways(region))

        return results
