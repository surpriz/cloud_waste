"""GCP provider implementation for CloudWaste."""

from app.providers.base import CloudProviderBase, OrphanResourceData


class GCPProvider(CloudProviderBase):
    """Google Cloud Platform provider implementation."""

    def __init__(
        self,
        project_id: str,
        service_account_json: str,
        regions: list[str] | None = None,
    ) -> None:
        """
        Initialize GCP provider.

        Args:
            project_id: GCP Project ID
            service_account_json: Service Account JSON key (as string)
            regions: List of GCP regions to scan (None = all regions)
        """
        # Store credentials (will be used later for GCP client initialization)
        self.project_id = project_id
        self.service_account_json = service_account_json
        self.regions = regions or []

    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate GCP credentials.

        For MVP, this is a placeholder.
        Full validation will be implemented in Phase 2.

        Returns:
            Dict with project_id
        """
        return {"project_id": self.project_id}

    async def get_available_regions(self) -> list[str]:
        """
        Get list of available GCP regions.

        Returns:
            List of default GCP regions
        """
        return [
            "us-central1",
            "us-east1",
            "us-west1",
            "europe-west1",
            "europe-west2",
            "asia-southeast1",
            "asia-northeast1",
        ]

    async def scan_all_resources(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan all GCP resources for waste detection.

        This is a skeleton implementation for MVP.
        Actual GCP scanning will be implemented in Phase 2.

        Args:
            detection_rules: Optional detection configuration

        Returns:
            Empty list (to be populated later with actual detections)
        """
        # TODO: Implement GCP resource scanning
        # Will require:
        # - google.cloud.compute_v1 for Compute Engine
        # - google.cloud.storage for Cloud Storage
        # - google.cloud.sql_v1 for Cloud SQL
        # - google.cloud.monitoring_v3 for metrics

        return []

    # Required abstract methods from CloudProviderBase
    # All return empty lists for MVP (Phase 1)
    # Full implementation will be added in Phase 2

    async def scan_unattached_volumes(self, region: str) -> list[OrphanResourceData]:
        """Scan for unattached persistent disks (Phase 2)."""
        return []

    async def scan_unassigned_ips(self, region: str) -> list[OrphanResourceData]:
        """Scan for unassigned static IP addresses (Phase 2)."""
        return []

    async def scan_orphaned_snapshots(
        self, region: str, detection_rules: dict | None = None, orphaned_volume_ids: list[str] | None = None
    ) -> list[OrphanResourceData]:
        """Scan for orphaned disk snapshots (Phase 2)."""
        return []

    async def scan_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for stopped Compute Engine instances (Phase 2)."""
        return []

    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle running Compute Engine instances (Phase 2)."""
        return []

    async def scan_unused_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused load balancers (Phase 2)."""
        return []

    async def scan_stopped_databases(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for stopped Cloud SQL instances (Phase 2)."""
        return []

    async def scan_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused Cloud NAT gateways (Phase 2)."""
        return []

    async def scan_unused_fsx_file_systems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_neptune_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_msk_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle GKE clusters (Phase 2)."""
        return []

    async def scan_idle_sagemaker_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_redshift_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_elasticache_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_vpn_connections(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_transit_gateway_attachments(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_opensearch_domains(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_global_accelerators(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_kinesis_streams(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_unused_vpc_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_documentdb_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []

    async def scan_idle_s3_buckets(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Cloud Storage buckets (Phase 2)."""
        return []

    async def scan_idle_lambda_functions(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Cloud Functions (Phase 2)."""
        return []

    async def scan_idle_dynamodb_tables(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP."""
        return []
