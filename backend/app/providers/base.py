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

    def _calculate_confidence_level(
        self,
        age_days: int,
        detection_rules: dict | None = None,
    ) -> str:
        """
        Calculate confidence level based on resource age and configurable thresholds.

        Args:
            age_days: Age of the resource in days
            detection_rules: Optional detection configuration with custom thresholds:
                {
                    "confidence_critical_days": int (default 90),
                    "confidence_high_days": int (default 30),
                    "confidence_medium_days": int (default 7)
                }

        Returns:
            Confidence level: "critical", "high", "medium", or "low"
        """
        # Get thresholds from detection rules or use defaults
        critical_days = 90
        high_days = 30
        medium_days = 7

        if detection_rules:
            critical_days = detection_rules.get("confidence_critical_days", 90)
            high_days = detection_rules.get("confidence_high_days", 30)
            medium_days = detection_rules.get("confidence_medium_days", 7)

        # Calculate confidence level based on age
        if age_days >= critical_days:
            return "critical"
        elif age_days >= high_days:
            return "high"
        elif age_days >= medium_days:
            return "medium"
        else:
            return "low"

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
    async def scan_unattached_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for unattached storage volumes.

        Args:
            region: Region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan volume resources
        """
        pass

    @abstractmethod
    async def scan_volumes_on_stopped_instances(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for volumes on stopped instances."""
        pass

    @abstractmethod
    async def scan_gp2_migration_opportunities(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for gp2 volumes that should migrate to gp3."""
        pass

    @abstractmethod
    async def scan_unnecessary_io2_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for io2 volumes without compliance requirements."""
        pass

    @abstractmethod
    async def scan_overprovisioned_iops_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for volumes with over-provisioned IOPS."""
        pass

    @abstractmethod
    async def scan_overprovisioned_throughput_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for volumes with over-provisioned throughput."""
        pass

    @abstractmethod
    async def scan_low_iops_usage_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for volumes with low IOPS utilization (CloudWatch)."""
        pass

    @abstractmethod
    async def scan_low_throughput_usage_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for volumes with low throughput utilization (CloudWatch)."""
        pass

    @abstractmethod
    async def scan_volume_type_downgrade_opportunities(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for volume type downgrade opportunities (CloudWatch)."""
        pass

    @abstractmethod
    async def scan_unassigned_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for unassigned Elastic IPs and EIPs on stopped instances (SCENARIOS 1-2).

        Args:
            region: Region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan IP address resources
        """
        pass

    @abstractmethod
    async def scan_additional_eips_per_instance(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for instances with multiple EIPs (SCENARIO 3)."""
        pass

    @abstractmethod
    async def scan_eips_on_detached_enis(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs on detached ENIs (SCENARIO 4)."""
        pass

    @abstractmethod
    async def scan_never_used_eips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs never associated with any resource (SCENARIO 5)."""
        pass

    @abstractmethod
    async def scan_eips_on_unused_nat_gateways(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs on unused NAT Gateways (SCENARIO 6)."""
        pass

    @abstractmethod
    async def scan_idle_eips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs on idle instances with minimal traffic (SCENARIO 7)."""
        pass

    @abstractmethod
    async def scan_low_traffic_eips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs with low network traffic (SCENARIO 8)."""
        pass

    @abstractmethod
    async def scan_unused_nat_gateway_eips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs on NAT Gateways with zero connections (SCENARIO 9)."""
        pass

    @abstractmethod
    async def scan_eips_on_failed_instances(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """Scan for EIPs on instances failing status checks (SCENARIO 10)."""
        pass

    @abstractmethod
    async def scan_orphaned_snapshots(
        self, region: str, detection_rules: dict | None = None, orphaned_volume_ids: list[str] | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for orphaned snapshots (parent resource deleted or idle).

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules
            orphaned_volume_ids: List of volume IDs detected as orphaned/idle

        Returns:
            List of orphan snapshot resources
        """
        pass

    @abstractmethod
    async def scan_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for compute instances stopped for extended period.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of stopped instance resources
        """
        pass

    @abstractmethod
    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for running instances with very low utilization (idle).

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of idle running instance resources
        """
        pass

    @abstractmethod
    async def scan_unused_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for load balancers with no healthy backends.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of unused load balancer resources
        """
        pass

    @abstractmethod
    async def scan_stopped_databases(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for database instances stopped for extended period or idle.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of stopped/idle database resources
        """
        pass

    @abstractmethod
    async def scan_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for NAT gateways with no traffic.

        Args:
            region: Region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of unused NAT gateway resources
        """
        pass

    @abstractmethod
    async def scan_unused_fsx_file_systems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused FSx file systems."""
        pass

    @abstractmethod
    async def scan_idle_neptune_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Neptune clusters."""
        pass

    @abstractmethod
    async def scan_idle_msk_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle MSK clusters."""
        pass

    @abstractmethod
    async def scan_idle_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle EKS clusters."""
        pass

    @abstractmethod
    async def scan_idle_sagemaker_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle SageMaker endpoints."""
        pass

    @abstractmethod
    async def scan_idle_redshift_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Redshift clusters."""
        pass

    @abstractmethod
    async def scan_idle_elasticache_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle ElastiCache clusters."""
        pass

    @abstractmethod
    async def scan_idle_vpn_connections(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle VPN connections."""
        pass

    @abstractmethod
    async def scan_idle_transit_gateway_attachments(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Transit Gateway attachments."""
        pass

    @abstractmethod
    async def scan_idle_opensearch_domains(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle OpenSearch domains."""
        pass

    @abstractmethod
    async def scan_idle_global_accelerators(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Global Accelerators."""
        pass

    @abstractmethod
    async def scan_idle_kinesis_streams(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Kinesis streams."""
        pass

    @abstractmethod
    async def scan_unused_vpc_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused VPC endpoints."""
        pass

    @abstractmethod
    async def scan_idle_documentdb_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle DocumentDB clusters."""
        pass

    @abstractmethod
    async def scan_idle_s3_buckets(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle S3 buckets (called once per account, not per region).

        Note: S3 buckets are global resources, so this method should be called
        only once per account scan, not for each region.

        Args:
            detection_rules: Optional detection configuration

        Returns:
            List of idle S3 bucket resources
        """
        pass

    @abstractmethod
    async def scan_idle_lambda_functions(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Lambda functions in a specific region.

        Detects 4 scenarios (by priority):
        1. Unused provisioned concurrency (VERY EXPENSIVE - highest priority)
        2. Never invoked (function created but never executed)
        3. Zero invocations (not invoked in last X days)
        4. 100% failures (all invocations fail = dead function)

        Args:
            region: Region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of idle Lambda function resources
        """
        pass

    @abstractmethod
    async def scan_idle_dynamodb_tables(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle/orphaned DynamoDB tables in a specific region.

        Detects 5 scenarios (by priority):
        1. Over-provisioned capacity (< 10% utilization - VERY EXPENSIVE)
        2. Unused Global Secondary Indexes (GSI never queried - doubles cost)
        3. Never used tables in Provisioned mode (0 usage since creation)
        4. Never used tables in On-Demand mode (0 usage in 60 days)
        5. Empty tables (0 items for 90+ days)

        Args:
            region: Region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned DynamoDB table resources
        """
        pass

    async def scan_all_resources(
        self, region: str, detection_rules: dict[str, dict] | None = None, scan_global_resources: bool = False
    ) -> list[OrphanResourceData]:
        """
        Scan all resource types in a specific region.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules per resource type
            scan_global_resources: If True, also scan global resources (e.g., S3 buckets).
                                   Should only be True for the first region in a multi-region scan.

        Returns:
            Combined list of all orphan resources found
        """
        results: list[OrphanResourceData] = []
        rules = detection_rules or {}

        # Execute all scan methods with user's rules
        # Original 7 resource types

        # EBS Volume scanning - 10 waste scenarios (100% coverage)
        # SCENARIO 1 & 7: Unattached and idle volumes
        volume_orphans = await self.scan_unattached_volumes(region, rules.get("ebs_volume"))
        results.extend(volume_orphans)

        # SCENARIO 2: Volumes on stopped instances
        results.extend(await self.scan_volumes_on_stopped_instances(region, rules.get("ebs_volume")))

        # SCENARIO 3: gp2 → gp3 migration opportunities
        results.extend(await self.scan_gp2_migration_opportunities(region, rules.get("ebs_volume")))

        # SCENARIO 4: Unnecessary io2 volumes
        results.extend(await self.scan_unnecessary_io2_volumes(region, rules.get("ebs_volume")))

        # SCENARIO 5: Over-provisioned IOPS
        results.extend(await self.scan_overprovisioned_iops_volumes(region, rules.get("ebs_volume")))

        # SCENARIO 6: Over-provisioned throughput
        results.extend(await self.scan_overprovisioned_throughput_volumes(region, rules.get("ebs_volume")))

        # SCENARIO 8: Low IOPS usage (CloudWatch)
        results.extend(await self.scan_low_iops_usage_volumes(region, rules.get("ebs_volume")))

        # SCENARIO 9: Low throughput usage (CloudWatch)
        results.extend(await self.scan_low_throughput_usage_volumes(region, rules.get("ebs_volume")))

        # SCENARIO 10: Volume type downgrade opportunities (CloudWatch)
        results.extend(await self.scan_volume_type_downgrade_opportunities(region, rules.get("ebs_volume")))

        # Extract orphaned volume IDs to pass to snapshot scanner
        orphaned_volume_ids = [
            vol.resource_id for vol in volume_orphans
            if vol.resource_metadata.get("orphan_type") in ["unattached", "attached_never_used", "attached_idle"]
        ]

        # Elastic IP scanning - 10 waste scenarios (100% coverage)
        # SCENARIO 1-2: Unassociated and stopped instance EIPs
        results.extend(await self.scan_unassigned_ips(region, rules.get("elastic_ip")))

        # SCENARIO 3: Multiple EIPs per instance
        results.extend(await self.scan_additional_eips_per_instance(region, rules.get("elastic_ip")))

        # SCENARIO 4: EIPs on detached ENIs
        results.extend(await self.scan_eips_on_detached_enis(region, rules.get("elastic_ip")))

        # SCENARIO 5: Never-used EIPs
        results.extend(await self.scan_never_used_eips(region, rules.get("elastic_ip")))

        # SCENARIO 6: EIPs on unused NAT Gateways (basic traffic check)
        results.extend(await self.scan_eips_on_unused_nat_gateways(region, rules.get("elastic_ip")))

        # SCENARIO 7: Idle EIPs (CloudWatch - minimal network traffic)
        results.extend(await self.scan_idle_eips(region, rules.get("elastic_ip")))

        # SCENARIO 8: Low-traffic EIPs (CloudWatch - < 1 GB/month)
        results.extend(await self.scan_low_traffic_eips(region, rules.get("elastic_ip")))

        # SCENARIO 9: EIPs on NAT Gateways with zero connections (CloudWatch)
        results.extend(await self.scan_unused_nat_gateway_eips(region, rules.get("elastic_ip")))

        # SCENARIO 10: EIPs on failed instances (CloudWatch - status check failures)
        results.extend(await self.scan_eips_on_failed_instances(region, rules.get("elastic_ip")))

        # Scan snapshots with orphaned volume IDs
        results.extend(
            await self.scan_orphaned_snapshots(region, rules.get("ebs_snapshot"), orphaned_volume_ids)
        )
        results.extend(
            await self.scan_stopped_instances(region, rules.get("ec2_instance"))
        )
        results.extend(
            await self.scan_idle_running_instances(region, rules.get("ec2_instance"))
        )
        results.extend(
            await self.scan_unused_load_balancers(region, rules.get("load_balancer"))
        )
        results.extend(
            await self.scan_stopped_databases(region, rules.get("rds_instance"))
        )
        results.extend(
            await self.scan_unused_nat_gateways(region, rules.get("nat_gateway"))
        )

        # TOP 15 high-cost idle resources
        results.extend(
            await self.scan_unused_fsx_file_systems(region, rules.get("fsx_file_system"))
        )
        results.extend(
            await self.scan_idle_neptune_clusters(region, rules.get("neptune_cluster"))
        )
        results.extend(await self.scan_idle_msk_clusters(region, rules.get("msk_cluster")))
        results.extend(await self.scan_idle_eks_clusters(region, rules.get("eks_cluster")))
        results.extend(
            await self.scan_idle_sagemaker_endpoints(
                region, rules.get("sagemaker_endpoint")
            )
        )
        results.extend(
            await self.scan_idle_redshift_clusters(region, rules.get("redshift_cluster"))
        )
        results.extend(
            await self.scan_idle_elasticache_clusters(
                region, rules.get("elasticache_cluster")
            )
        )
        results.extend(
            await self.scan_idle_vpn_connections(region, rules.get("vpn_connection"))
        )
        results.extend(
            await self.scan_idle_transit_gateway_attachments(
                region, rules.get("transit_gateway_attachment")
            )
        )
        results.extend(
            await self.scan_idle_opensearch_domains(region, rules.get("opensearch_domain"))
        )
        results.extend(
            await self.scan_idle_global_accelerators(
                region, rules.get("global_accelerator")
            )
        )
        results.extend(
            await self.scan_idle_kinesis_streams(region, rules.get("kinesis_stream"))
        )
        results.extend(
            await self.scan_unused_vpc_endpoints(region, rules.get("vpc_endpoint"))
        )
        results.extend(
            await self.scan_idle_documentdb_clusters(
                region, rules.get("documentdb_cluster")
            )
        )
        results.extend(
            await self.scan_idle_lambda_functions(region, rules.get("lambda_function"))
        )
        results.extend(
            await self.scan_idle_dynamodb_tables(region, rules.get("dynamodb_table"))
        )

        # Global resources (scanned only once, not per region)
        if scan_global_resources:
            results.extend(await self.scan_idle_s3_buckets(rules.get("s3_bucket")))

        return results
