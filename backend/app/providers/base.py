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

    def _deduplicate_resources(
        self, resources: list[OrphanResourceData]
    ) -> list[OrphanResourceData]:
        """
        Deduplicate resources detected by multiple scenarios.

        When a single physical resource (e.g., EBS volume) is detected by multiple
        waste scenarios (e.g., unattached + over-provisioned IOPS + low utilization),
        this method combines them into a single entry to avoid:
        - Counting the same resource multiple times
        - Summing costs incorrectly (3x the actual cost)
        - Misleading users about total waste

        Strategy:
        - Group by (resource_id, region)
        - Keep the highest cost (= real cost of the resource)
        - Combine all detection scenarios in metadata
        - Keep the highest confidence level

        Args:
            resources: List of detected orphan resources (may contain duplicates)

        Returns:
            Deduplicated list with one entry per unique resource
        """
        import structlog

        logger = structlog.get_logger()

        # Group resources by (resource_id, region)
        grouped: dict[tuple[str, str], list[OrphanResourceData]] = {}
        for resource in resources:
            key = (resource.resource_id, resource.region)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(resource)

        # Deduplicate each group
        deduplicated: list[OrphanResourceData] = []
        total_duplicates = 0

        for key, duplicates in grouped.items():
            if len(duplicates) == 1:
                # No duplication, keep as is
                deduplicated.append(duplicates[0])
            else:
                # Duplication detected: combine information
                total_duplicates += len(duplicates) - 1

                # Keep the detection with the highest cost (= real cost of resource)
                primary = max(duplicates, key=lambda r: r.estimated_monthly_cost)

                # Collect all detection scenarios
                all_scenarios = []
                all_reasons = []
                all_detections = []

                for dup in duplicates:
                    scenario = dup.resource_metadata.get("orphan_type", "unknown")
                    reason = dup.resource_metadata.get("orphan_reason", "")
                    confidence = dup.resource_metadata.get("confidence", "low")

                    all_scenarios.append(scenario)
                    if reason:
                        all_reasons.append(reason)

                    all_detections.append(
                        {
                            "scenario": scenario,
                            "reason": reason,
                            "cost": dup.estimated_monthly_cost,
                            "confidence": confidence,
                        }
                    )

                # Find highest confidence level (critical > high > medium > low)
                confidence_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                best_confidence = max(
                    [d.resource_metadata.get("confidence", "low") for d in duplicates],
                    key=lambda c: confidence_order.get(c, 0),
                )

                # Enrich primary metadata with combined information
                primary.resource_metadata["detection_scenarios"] = all_scenarios
                primary.resource_metadata["combined_reasons"] = all_reasons
                primary.resource_metadata["confidence"] = best_confidence
                primary.resource_metadata["duplicate_count"] = len(duplicates)
                primary.resource_metadata["all_detections"] = all_detections
                primary.resource_metadata["is_deduplicated"] = True

                # Log deduplication for monitoring
                logger.info(
                    "resource.deduplicated",
                    resource_id=key[0],
                    region=key[1],
                    duplicate_count=len(duplicates),
                    scenarios=all_scenarios,
                    final_cost=primary.estimated_monthly_cost,
                )

                deduplicated.append(primary)

        # Log overall deduplication stats
        if total_duplicates > 0:
            logger.info(
                "scan.deduplication_complete",
                total_resources_before=len(resources),
                total_resources_after=len(deduplicated),
                duplicates_removed=total_duplicates,
                deduplication_ratio=f"{total_duplicates / len(resources) * 100:.1f}%",
            )

        return deduplicated

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
        Scan for orphaned snapshots (SCENARIO 1: parent resource deleted or idle).

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules
            orphaned_volume_ids: List of volume IDs detected as orphaned/idle

        Returns:
            List of orphan snapshot resources
        """
        pass

    @abstractmethod
    async def scan_redundant_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for redundant snapshots (SCENARIO 2: exceeding retention limit)."""
        pass

    @abstractmethod
    async def scan_unused_ami_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for snapshots of unused AMIs (SCENARIO 10)."""
        pass

    @abstractmethod
    async def scan_old_unused_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for very old snapshots without compliance tags (SCENARIO 3)."""
        pass

    @abstractmethod
    async def scan_snapshots_from_deleted_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for snapshots from deleted instances (SCENARIO 4)."""
        pass

    @abstractmethod
    async def scan_incomplete_failed_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for incomplete/failed snapshots (SCENARIO 5: error or pending state)."""
        pass

    @abstractmethod
    async def scan_untagged_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for untagged snapshots (SCENARIO 6: no tags present)."""
        pass

    @abstractmethod
    async def scan_excessive_retention_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for snapshots with excessive retention in non-prod (SCENARIO 8)."""
        pass

    @abstractmethod
    async def scan_duplicate_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for duplicate snapshots (SCENARIO 9: same volume within time window)."""
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
    async def scan_oversized_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for over-provisioned instances (CPU <30%).

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of oversized instance resources
        """
        pass

    @abstractmethod
    async def scan_old_generation_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for obsolete generation instances (t2, m4, c4, r4).

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of old generation instance resources
        """
        pass

    @abstractmethod
    async def scan_burstable_credit_waste(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for burstable instances (T2/T3/T4) with unused CPU credits.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of burstable instances with credit waste
        """
        pass

    @abstractmethod
    async def scan_dev_test_24_7_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for non-production instances running 24/7.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of dev/test instances running 24/7
        """
        pass

    @abstractmethod
    async def scan_untagged_ec2_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for instances without any tags.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of untagged instance resources
        """
        pass

    @abstractmethod
    async def scan_right_sizing_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for advanced right-sizing opportunities.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of right-sizing opportunity resources
        """
        pass

    @abstractmethod
    async def scan_spot_eligible_workloads(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for stable workloads eligible for Spot instances.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of Spot-eligible instance resources
        """
        pass

    @abstractmethod
    async def scan_scheduled_unused_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for instances only used during business hours.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of scheduled unused instance resources
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
    async def scan_load_balancer_cross_zone_disabled(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for load balancers with cross-zone load balancing disabled.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of load balancers with cross-zone disabled causing data transfer costs
        """
        pass

    @abstractmethod
    async def scan_load_balancer_idle_patterns(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for load balancers with idle connection patterns during business hours.

        Args:
            region: Region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of load balancers with predictable idle patterns
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
    async def scan_nat_gateway_vpc_endpoint_candidates(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for NAT gateways that could benefit from VPC Endpoints (Scenario 8).

        Args:
            region: Region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of NAT gateways with VPC Endpoint opportunities
        """
        pass

    @abstractmethod
    async def scan_nat_gateway_dev_test_unused_hours(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for dev/test NAT gateways with business-hours-only traffic (Scenario 9).

        Args:
            region: Region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of dev/test NAT gateways with scheduling opportunities
        """
        pass

    @abstractmethod
    async def scan_nat_gateway_obsolete_migration(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for obsolete NAT gateways after migration (Scenario 10).

        Args:
            region: Region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of NAT gateways likely obsolete after migration
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

        # EBS Snapshot scanning - 10 waste scenarios (100% coverage)
        # SCENARIO 1: Orphaned snapshots (volume deleted or idle)
        results.extend(
            await self.scan_orphaned_snapshots(region, rules.get("ebs_snapshot"), orphaned_volume_ids)
        )
        # SCENARIO 2: Redundant snapshots (exceeding retention limit)
        results.extend(await self.scan_redundant_snapshots(region, rules.get("ebs_snapshot")))

        # SCENARIO 3: Old unused snapshots (>365 days without compliance tags)
        results.extend(await self.scan_old_unused_snapshots(region, rules.get("ebs_snapshot")))

        # SCENARIO 4: Snapshots from deleted instances
        results.extend(await self.scan_snapshots_from_deleted_instances(region, rules.get("ebs_snapshot")))

        # SCENARIO 5: Incomplete/failed snapshots
        results.extend(await self.scan_incomplete_failed_snapshots(region, rules.get("ebs_snapshot")))

        # SCENARIO 6: Untagged snapshots
        results.extend(await self.scan_untagged_snapshots(region, rules.get("ebs_snapshot")))

        # SCENARIO 7: Never restored snapshots (CloudTrail - Phase 2, deferred)
        # TODO: Implement CloudTrail-based detection

        # SCENARIO 8: Excessive retention in non-prod
        results.extend(await self.scan_excessive_retention_snapshots(region, rules.get("ebs_snapshot")))

        # SCENARIO 9: Duplicate snapshots
        results.extend(await self.scan_duplicate_snapshots(region, rules.get("ebs_snapshot")))

        # SCENARIO 10: Snapshots of unused AMIs
        results.extend(await self.scan_unused_ami_snapshots(region, rules.get("ebs_snapshot")))

        # EC2 Instance scanning - 10 waste scenarios (100% coverage)
        # SCENARIO 1: Stopped instances >30 days
        results.extend(await self.scan_stopped_instances(region, rules.get("ec2_instance")))

        # SCENARIO 2: Over-provisioned instances (CPU <30%)
        results.extend(await self.scan_oversized_instances(region, rules.get("ec2_instance")))

        # SCENARIO 3: Old generation instances (t2→t3, m4→m5)
        results.extend(await self.scan_old_generation_instances(region, rules.get("ec2_instance")))

        # SCENARIO 4: Burstable credit waste (T2/T3/T4 unused credits)
        results.extend(await self.scan_burstable_credit_waste(region, rules.get("ec2_instance")))

        # SCENARIO 5: Dev/Test instances running 24/7
        results.extend(await self.scan_dev_test_24_7_instances(region, rules.get("ec2_instance")))

        # SCENARIO 6: Untagged instances
        results.extend(await self.scan_untagged_ec2_instances(region, rules.get("ec2_instance")))

        # SCENARIO 7: Idle running instances (CPU <5%)
        results.extend(await self.scan_idle_running_instances(region, rules.get("ec2_instance")))

        # SCENARIO 8: Advanced right-sizing opportunities
        results.extend(await self.scan_right_sizing_opportunities(region, rules.get("ec2_instance")))

        # SCENARIO 9: Spot-eligible workloads
        results.extend(await self.scan_spot_eligible_workloads(region, rules.get("ec2_instance")))

        # SCENARIO 10: Scheduled unused instances (business hours only)
        results.extend(await self.scan_scheduled_unused_instances(region, rules.get("ec2_instance")))

        # Load Balancer scanning - 10 waste scenarios (100% coverage)
        # Scenarios 1-7 + 10: Basic detection (no listeners, no targets, unhealthy, CLB migration)
        results.extend(
            await self.scan_unused_load_balancers(region, rules.get("load_balancer"))
        )

        # Scenario 8: Cross-zone load balancing disabled
        results.extend(
            await self.scan_load_balancer_cross_zone_disabled(region, rules.get("load_balancer"))
        )

        # Scenario 9: Idle connection patterns (business hours only)
        results.extend(
            await self.scan_load_balancer_idle_patterns(region, rules.get("load_balancer"))
        )

        results.extend(
            await self.scan_stopped_databases(region, rules.get("rds_instance"))
        )

        # NAT Gateway scanning - 10 waste scenarios (100% coverage)
        # Scenario 1-7: Basic detection (no routes, zero traffic, etc.)
        results.extend(
            await self.scan_unused_nat_gateways(region, rules.get("nat_gateway"))
        )

        # Scenario 8: VPC Endpoint candidates
        results.extend(
            await self.scan_nat_gateway_vpc_endpoint_candidates(region, rules.get("nat_gateway"))
        )

        # Scenario 9: Dev/Test business hours only
        results.extend(
            await self.scan_nat_gateway_dev_test_unused_hours(region, rules.get("nat_gateway"))
        )

        # Scenario 10: Obsolete after migration
        results.extend(
            await self.scan_nat_gateway_obsolete_migration(region, rules.get("nat_gateway"))
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

        # Deduplicate resources to avoid counting the same resource multiple times
        # (e.g., a volume detected as unattached + over-provisioned + low IOPS usage)
        results = self._deduplicate_resources(results)

        return results
