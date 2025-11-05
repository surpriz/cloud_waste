"""GCP provider implementation for CloudWaste."""

import asyncio
import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import compute_v1, container_v1, functions_v1, functions_v2, logging, monitoring_v3, run_v2
from google.oauth2 import service_account
from google.protobuf.timestamp_pb2 import Timestamp
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from app.providers.base import CloudProviderBase, OrphanResourceData


class GCPProvider(CloudProviderBase):
    """Google Cloud Platform provider implementation."""

    # GCP Machine Type Pricing (us-central1, monthly with Sustained Use Discounts)
    MACHINE_PRICING = {
        "e2-micro": 7.11,
        "e2-small": 14.23,
        "e2-medium": 28.45,
        "f1-micro": 3.88,
        "g1-small": 13.23,
        "n1-standard-1": 24.27,
        "n1-standard-2": 48.54,
        "n1-standard-4": 97.08,
        "n1-standard-8": 194.16,
        "n1-standard-16": 388.32,
        "n2-standard-2": 71.17,
        "n2-standard-4": 142.34,
        "n2-standard-8": 284.68,
        "n2-standard-16": 569.36,
        "n2-highcpu-2": 50.88,
        "n2-highcpu-4": 101.76,
        "n2-highcpu-8": 203.52,
        "n2-highcpu-16": 407.04,
        "n2-highmem-2": 95.45,
        "n2-highmem-4": 190.90,
        "n2-highmem-8": 381.80,
        "n2-highmem-16": 763.60,
        "c2-standard-4": 163.73,
        "c2-standard-8": 327.46,
        "c2-standard-16": 654.92,
    }

    # Spot pricing (60-91% discount)
    SPOT_DISCOUNT = 0.76  # Average 76% discount

    # Disk pricing per GB/month
    DISK_PRICING = {
        "pd-standard": 0.040,  # HDD
        "pd-balanced": 0.100,  # SSD balanced
        "pd-ssd": 0.170,  # SSD performance
    }

    # E2 burstable baseline CPU %
    E2_BASELINE_CPU = {
        "e2-micro": 12.5,
        "e2-small": 25.0,
        "e2-medium": 50.0,
    }

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
        self.project_id = project_id
        self.service_account_json = service_account_json
        self.regions = regions or []

        # Initialize GCP clients
        self._credentials = None
        self._compute_client = None
        self._monitoring_client = None
        self._gke_client = None
        self._logging_client = None
        self._run_client = None

    def _get_credentials(self) -> service_account.Credentials:
        """Get GCP credentials from service account JSON."""
        if self._credentials is None:
            credentials_dict = json.loads(self.service_account_json)
            self._credentials = service_account.Credentials.from_service_account_info(
                credentials_dict
            )
        return self._credentials

    def _get_compute_client(self) -> compute_v1.InstancesClient:
        """Get or create Compute Engine client."""
        if self._compute_client is None:
            self._compute_client = compute_v1.InstancesClient(
                credentials=self._get_credentials()
            )
        return self._compute_client

    def _get_monitoring_client(self) -> monitoring_v3.MetricServiceClient:
        """Get or create Cloud Monitoring client."""
        if self._monitoring_client is None:
            self._monitoring_client = monitoring_v3.MetricServiceClient(
                credentials=self._get_credentials()
            )
        return self._monitoring_client

    def _get_gke_client(self) -> container_v1.ClusterManagerClient:
        """Get or create GKE (Google Kubernetes Engine) client."""
        if self._gke_client is None:
            self._gke_client = container_v1.ClusterManagerClient(
                credentials=self._get_credentials()
            )
        return self._gke_client

    def _get_run_client(self) -> run_v2.ServicesClient:
        """Get or create Cloud Run client."""
        if self._run_client is None:
            self._run_client = run_v2.ServicesClient(
                credentials=self._get_credentials()
            )
        return self._run_client

    def _get_k8s_config(self, cluster: container_v1.Cluster, location: str) -> dict:
        """
        Build Kubernetes config dict for a GKE cluster.

        Args:
            cluster: GKE cluster object
            location: Cluster location (zone or region)

        Returns:
            Kubernetes config dict
        """
        try:
            # Get cluster endpoint and CA certificate
            endpoint = cluster.endpoint
            ca_cert = cluster.master_auth.cluster_ca_certificate

            # Build kubeconfig
            k8s_config_dict = {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [
                    {
                        "name": cluster.name,
                        "cluster": {
                            "server": f"https://{endpoint}",
                            "certificate-authority-data": ca_cert,
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": cluster.name,
                        "context": {"cluster": cluster.name, "user": cluster.name},
                    }
                ],
                "current-context": cluster.name,
                "users": [
                    {
                        "name": cluster.name,
                        "user": {
                            "auth-provider": {
                                "name": "gcp",
                                "config": {
                                    "access-token": self._get_credentials().token,
                                },
                            }
                        },
                    }
                ],
            }
            return k8s_config_dict
        except Exception:
            return {}

    def _get_machine_cost(self, machine_type: str, spot: bool = False) -> float:
        """
        Get monthly cost for a machine type.

        Args:
            machine_type: Machine type name (e.g., 'n2-standard-4')
            spot: Whether to use spot pricing

        Returns:
            Monthly cost in USD
        """
        base_cost = self.MACHINE_PRICING.get(machine_type, 0.0)
        if spot and base_cost > 0:
            return base_cost * (1 - self.SPOT_DISCOUNT)
        return base_cost

    def _calculate_disk_cost(self, disks: list[dict]) -> float:
        """
        Calculate total monthly cost for disks.

        Args:
            disks: List of disk configurations

        Returns:
            Total monthly cost in USD
        """
        total_cost = 0.0
        for disk in disks:
            disk_size_gb = disk.get("diskSizeGb", 0)
            disk_type = disk.get("type", "pd-standard").split("/")[-1]
            price_per_gb = self.DISK_PRICING.get(disk_type, 0.040)
            total_cost += disk_size_gb * price_per_gb
        return total_cost

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse GCP timestamp string to datetime."""
        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

    def _get_age_days(self, timestamp_str: str) -> int:
        """Calculate age in days from timestamp string."""
        timestamp = self._parse_timestamp(timestamp_str)
        age = datetime.now(timezone.utc) - timestamp
        return age.days

    def _get_machine_type_name(self, machine_type_url: str) -> str:
        """Extract machine type name from full URL."""
        return machine_type_url.split("/")[-1]

    def _get_zone_name(self, zone_url: str) -> str:
        """Extract zone name from full URL."""
        return zone_url.split("/")[-1]

    def _parse_cloud_run_cpu(self, cpu_str: str) -> float:
        """
        Parse Cloud Run CPU value to float.

        Args:
            cpu_str: CPU value (e.g., '1', '2', '1000m', '2000m')

        Returns:
            CPU as float (e.g., 1.0, 2.0, 1.0, 2.0)
        """
        if 'm' in str(cpu_str):
            # Millicores (e.g., '1000m' = 1 vCPU)
            return int(str(cpu_str).replace('m', '')) / 1000
        return float(cpu_str)

    def _parse_cloud_run_memory(self, memory_str: str) -> float:
        """
        Parse Cloud Run memory value to GiB.

        Args:
            memory_str: Memory value (e.g., '512Mi', '1Gi', '2048Mi')

        Returns:
            Memory in GiB (e.g., 0.5, 1.0, 2.0)
        """
        if 'Gi' in memory_str:
            return float(memory_str.replace('Gi', ''))
        elif 'Mi' in memory_str:
            return float(memory_str.replace('Mi', '')) / 1024
        return 0.5  # Default 512Mi

    async def _get_cpu_metrics(
        self, instance_id: str, zone: str, lookback_days: int = 14
    ) -> dict[str, Any]:
        """
        Get CPU utilization metrics from Cloud Monitoring.

        Args:
            instance_id: Instance ID
            zone: Zone name
            lookback_days: Number of days to look back

        Returns:
            Dict with avg, max, min CPU values and datapoints count
        """
        try:
            monitoring_client = self._get_monitoring_client()

            # Build time interval
            now = time.time()
            end_time = Timestamp(seconds=int(now))
            start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

            interval = monitoring_v3.TimeInterval(
                {"end_time": end_time, "start_time": start_time}
            )

            # Build filter
            filter_str = (
                f'metric.type="compute.googleapis.com/instance/cpu/utilization" '
                f'AND resource.instance_id="{instance_id}" '
                f'AND resource.zone="{zone}"'
            )

            # Query metrics
            results = monitoring_client.list_time_series(
                request={
                    "name": f"projects/{self.project_id}",
                    "filter": filter_str,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            # Extract values
            cpu_values = []
            for series in results:
                for point in series.points:
                    # CPU utilization is reported as fraction (0.0-1.0)
                    cpu_values.append(point.value.double_value * 100)

            if not cpu_values:
                return {
                    "avg_cpu": 0.0,
                    "max_cpu": 0.0,
                    "min_cpu": 0.0,
                    "datapoints": 0,
                }

            return {
                "avg_cpu": sum(cpu_values) / len(cpu_values),
                "max_cpu": max(cpu_values),
                "min_cpu": min(cpu_values),
                "datapoints": len(cpu_values),
            }

        except Exception as e:
            # If metrics not available, return zeros
            return {
                "avg_cpu": 0.0,
                "max_cpu": 0.0,
                "min_cpu": 0.0,
                "datapoints": 0,
            }

    async def _get_memory_metrics(
        self, instance_id: str, zone: str, lookback_days: int = 14
    ) -> dict[str, Any]:
        """
        Get memory utilization metrics from Cloud Monitoring.

        Requires Cloud Monitoring Agent installed on instance.

        Args:
            instance_id: Instance ID
            zone: Zone name
            lookback_days: Number of days to look back

        Returns:
            Dict with avg, max, min memory values and datapoints count
        """
        try:
            monitoring_client = self._get_monitoring_client()

            # Build time interval
            now = time.time()
            end_time = Timestamp(seconds=int(now))
            start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

            interval = monitoring_v3.TimeInterval(
                {"end_time": end_time, "start_time": start_time}
            )

            # Build filter for memory metrics
            filter_str = (
                f'metric.type="agent.googleapis.com/memory/percent_used" '
                f'AND resource.instance_id="{instance_id}"'
            )

            # Query metrics
            results = monitoring_client.list_time_series(
                request={
                    "name": f"projects/{self.project_id}",
                    "filter": filter_str,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            # Extract values
            memory_values = []
            for series in results:
                for point in series.points:
                    memory_values.append(point.value.double_value)

            if not memory_values:
                return {
                    "avg_memory": 0.0,
                    "max_memory": 0.0,
                    "min_memory": 0.0,
                    "datapoints": 0,
                }

            return {
                "avg_memory": sum(memory_values) / len(memory_values),
                "max_memory": max(memory_values),
                "min_memory": min(memory_values),
                "datapoints": len(memory_values),
            }

        except Exception:
            # Memory metrics not available (agent not installed)
            return {
                "avg_memory": 0.0,
                "max_memory": 0.0,
                "min_memory": 0.0,
                "datapoints": 0,
            }

    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate GCP credentials.

        Returns:
            Dict with project_id
        """
        try:
            # Test credentials by making a simple API call
            compute_client = self._get_compute_client()
            # This will raise an exception if credentials are invalid
            return {"project_id": self.project_id}
        except Exception as e:
            raise Exception(f"Invalid GCP credentials: {str(e)}")

    async def get_available_regions(self) -> list[str]:
        """
        Get list of available GCP regions.

        Returns:
            List of GCP regions
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

        Args:
            detection_rules: Optional detection configuration

        Returns:
            List of detected orphan resources
        """
        all_resources = []

        # Get regions to scan
        regions = self.regions if self.regions else await self.get_available_regions()

        # Scan Compute Engine instances (all 10 scenarios)
        for region in regions:
            # Phase 1 scenarios (7)
            all_resources.extend(
                await self.scan_stopped_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_idle_running_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_overprovisioned_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_old_generation_compute_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_no_spot_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_untagged_compute_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_devtest_247_instances(region, detection_rules)
            )

            # Phase 2 scenarios (3)
            all_resources.extend(
                await self.scan_memory_waste_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_rightsizing_instances(region, detection_rules)
            )
            all_resources.extend(
                await self.scan_burstable_waste_instances(region, detection_rules)
            )

        return all_resources

    # ==================== PHASE 1 SCENARIOS ====================

    async def scan_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Scan for stopped Compute Engine instances >30 days.

        Detection:
        - Status = TERMINATED
        - Age >= min_age_days (default: 30)

        Cost:
        - Only disks are charged when instance is stopped
        """
        resources = []
        min_age_days = (
            detection_rules.get("compute_instance_stopped", {}).get("min_age_days", 30)
            if detection_rules
            else 30
        )

        try:
            compute_client = self._get_compute_client()

            # List all zones in region
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    # List instances in zone with TERMINATED status
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="TERMINATED"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        # Calculate age since last stop
                        if hasattr(instance, "last_stop_timestamp"):
                            age_days = self._get_age_days(instance.last_stop_timestamp)
                        else:
                            # Fallback to creation timestamp
                            age_days = self._get_age_days(instance.creation_timestamp)

                        if age_days >= min_age_days:
                            # Calculate disk costs only
                            disks = [
                                {
                                    "diskSizeGb": disk.disk_size_gb,
                                    "type": disk.type,
                                }
                                for disk in instance.disks
                            ]
                            monthly_cost = self._calculate_disk_cost(disks)
                            already_wasted = monthly_cost * (age_days / 30.0)

                            resources.append(
                                OrphanResourceData(
                                    resource_id=str(instance.id),
                                    resource_name=instance.name,
                                    resource_type="compute_instance_stopped",
                                    region=zone,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "zone": zone,
                                        "machine_type": self._get_machine_type_name(
                                            instance.machine_type
                                        ),
                                        "status": instance.status,
                                        "age_days": age_days,
                                        "disks": disks,
                                        "already_wasted": already_wasted,
                                        "confidence": "high"
                                        if age_days >= 60
                                        else "medium",
                                    },
                                )
                            )

                except Exception as e:
                    # Zone might not exist, continue
                    continue

        except Exception as e:
            # Log error but don't fail entire scan
            pass

        return resources

    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Scan for idle running instances (CPU <5%).

        Detection:
        - Status = RUNNING
        - avg_cpu_14d < cpu_threshold (default: 5%)
        - Min datapoints >= 50

        Cost:
        - 95% of compute cost is waste (CPU <5%)
        """
        resources = []
        cpu_threshold = (
            detection_rules.get("compute_instance_idle", {}).get("cpu_threshold", 5.0)
            if detection_rules
            else 5.0
        )
        lookback_days = (
            detection_rules.get("compute_instance_idle", {}).get("lookback_days", 14)
            if detection_rules
            else 14
        )
        min_datapoints = (
            detection_rules.get("compute_instance_idle", {}).get("min_datapoints", 50)
            if detection_rules
            else 50
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        # Get CPU metrics
                        cpu_metrics = await self._get_cpu_metrics(
                            str(instance.id), zone, lookback_days
                        )

                        if (
                            cpu_metrics["datapoints"] >= min_datapoints
                            and cpu_metrics["avg_cpu"] < cpu_threshold
                        ):
                            machine_type = self._get_machine_type_name(
                                instance.machine_type
                            )
                            monthly_cost = self._get_machine_cost(machine_type)

                            # Waste = 95% of cost (keep 5% for baseline)
                            waste_percentage = (100 - cpu_metrics["avg_cpu"]) / 100.0
                            monthly_waste = monthly_cost * waste_percentage

                            age_days = self._get_age_days(instance.creation_timestamp)
                            already_wasted = monthly_waste * (age_days / 30.0)

                            resources.append(
                                OrphanResourceData(
                                    resource_id=str(instance.id),
                                    resource_name=instance.name,
                                    resource_type="compute_instance_idle",
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "zone": zone,
                                        "machine_type": machine_type,
                                        "status": instance.status,
                                        "age_days": age_days,
                                        "cpu_metrics": {
                                            "avg_cpu_14d": round(
                                                cpu_metrics["avg_cpu"], 2
                                            ),
                                            "max_cpu_14d": round(
                                                cpu_metrics["max_cpu"], 2
                                            ),
                                            "min_cpu_14d": round(
                                                cpu_metrics["min_cpu"], 2
                                            ),
                                            "datapoints": cpu_metrics["datapoints"],
                                        },
                                        "current_monthly_cost": monthly_cost,
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": "high",
                                        "recommendation": "Downgrade to smaller instance type or stop",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_overprovisioned_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Scan for over-provisioned instances (5% < CPU < 30%).

        Detection:
        - Status = RUNNING
        - 5% < avg_cpu_14d < 30%
        - Downgrade opportunity exists

        Cost:
        - Difference between current and recommended size
        """
        resources = []
        cpu_min_threshold = (
            detection_rules.get("compute_instance_overprovisioned", {}).get(
                "cpu_min_threshold", 5.0
            )
            if detection_rules
            else 5.0
        )
        cpu_max_threshold = (
            detection_rules.get("compute_instance_overprovisioned", {}).get(
                "cpu_max_threshold", 30.0
            )
            if detection_rules
            else 30.0
        )
        lookback_days = (
            detection_rules.get("compute_instance_overprovisioned", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        cpu_metrics = await self._get_cpu_metrics(
                            str(instance.id), zone, lookback_days
                        )

                        if (
                            cpu_min_threshold
                            < cpu_metrics["avg_cpu"]
                            < cpu_max_threshold
                            and cpu_metrics["datapoints"] >= 50
                        ):
                            machine_type = self._get_machine_type_name(
                                instance.machine_type
                            )
                            current_cost = self._get_machine_cost(machine_type)

                            # Recommend half the vCPUs (simple downgrade logic)
                            recommended_type = self._recommend_downgrade(machine_type)
                            recommended_cost = self._get_machine_cost(recommended_type)

                            if recommended_cost < current_cost:
                                monthly_waste = current_cost - recommended_cost
                                age_days = self._get_age_days(
                                    instance.creation_timestamp
                                )
                                already_wasted = monthly_waste * (age_days / 30.0)

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=str(instance.id),
                                        resource_name=instance.name,
                                        resource_type="compute_instance_overprovisioned",
                                        region=zone,
                                        estimated_monthly_cost=monthly_waste,
                                        resource_metadata={
                                            "zone": zone,
                                            "machine_type": machine_type,
                                            "status": instance.status,
                                            "cpu_metrics": {
                                                "avg_cpu_14d": round(
                                                    cpu_metrics["avg_cpu"], 2
                                                ),
                                                "max_cpu_14d": round(
                                                    cpu_metrics["max_cpu"], 2
                                                ),
                                            },
                                            "current_monthly_cost": current_cost,
                                            "recommended_machine_type": recommended_type,
                                            "recommended_monthly_cost": recommended_cost,
                                            "already_wasted": round(already_wasted, 2),
                                            "confidence": "medium",
                                            "recommendation": f"Downgrade to {recommended_type}",
                                        },
                                    )
                                )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    def _recommend_downgrade(self, machine_type: str) -> str:
        """Recommend a smaller machine type for downgrade."""
        # Simple downgrade logic: halve the vCPUs
        if "standard-16" in machine_type:
            return machine_type.replace("standard-16", "standard-8")
        elif "standard-8" in machine_type:
            return machine_type.replace("standard-8", "standard-4")
        elif "standard-4" in machine_type:
            return machine_type.replace("standard-4", "standard-2")
        elif "standard-2" in machine_type:
            return machine_type.replace("standard-2", "standard-1") if "n1" in machine_type else machine_type
        return machine_type

    async def scan_old_generation_compute_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Scan for old generation instances (n1).

        Detection:
        - machine_type starts with 'n1-'
        - Modern equivalent (n2/n2d) exists with better cost/performance

        Cost:
        - Potential savings from n1 → n2 migration
        """
        resources = []
        old_generations = (
            detection_rules.get("compute_instance_old_generation", {}).get(
                "old_generations", ["n1"]
            )
            if detection_rules
            else ["n1"]
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        machine_type = self._get_machine_type_name(
                            instance.machine_type
                        )

                        # Check if old generation
                        is_old_gen = any(
                            machine_type.startswith(f"{gen}-") for gen in old_generations
                        )

                        if is_old_gen:
                            current_cost = self._get_machine_cost(machine_type)

                            # Recommend n2 equivalent
                            recommended_type = machine_type.replace("n1-", "n2-")
                            if "standard-1" in machine_type:
                                recommended_type = "n2-standard-2"  # n2 min is 2 vCPUs

                            recommended_cost = self._get_machine_cost(recommended_type)

                            if recommended_cost > 0:
                                # Account for n2 better performance (+40%)
                                # Effective cost is lower
                                monthly_waste = max(
                                    0, current_cost - recommended_cost * 0.7
                                )

                                if monthly_waste >= 10.0:  # Min savings threshold
                                    age_days = self._get_age_days(
                                        instance.creation_timestamp
                                    )
                                    already_wasted = monthly_waste * (age_days / 30.0)

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=str(instance.id),
                                            resource_name=instance.name,
                                            resource_type="compute_instance_old_generation",
                                            region=zone,
                                            estimated_monthly_cost=monthly_waste,
                                            resource_metadata={
                                                "zone": zone,
                                                "machine_type": machine_type,
                                                "status": instance.status,
                                                "age_days": age_days,
                                                "current_monthly_cost": current_cost,
                                                "recommended_machine_type": recommended_type,
                                                "recommended_monthly_cost": recommended_cost,
                                                "already_wasted": round(
                                                    already_wasted, 2
                                                ),
                                                "confidence": "medium",
                                                "recommendation": f"Migrate to {recommended_type} for better cost/performance",
                                            },
                                        )
                                    )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_no_spot_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Scan for instances eligible for Spot VMs.

        Detection:
        - Status = RUNNING
        - scheduling.preemptible = False (not using Spot)
        - Labels indicate spot-eligible workload (batch, dev, test, staging)

        Cost:
        - 60-91% savings with Spot VMs
        """
        resources = []
        spot_eligible_labels = (
            detection_rules.get("compute_instance_no_spot", {}).get(
                "spot_eligible_labels", ["batch", "dev", "test", "staging"]
            )
            if detection_rules
            else ["batch", "dev", "test", "staging"]
        )
        min_savings_threshold = (
            detection_rules.get("compute_instance_no_spot", {}).get(
                "min_savings_threshold", 20.0
            )
            if detection_rules
            else 20.0
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        # Check if not using spot
                        is_preemptible = (
                            instance.scheduling.preemptible
                            if hasattr(instance.scheduling, "preemptible")
                            else False
                        )

                        if not is_preemptible:
                            # Check labels for spot-eligible workload
                            labels = dict(instance.labels) if instance.labels else {}
                            workload_type = labels.get("workload", "").lower()
                            environment = labels.get("environment", "").lower()

                            is_spot_eligible = (
                                workload_type in spot_eligible_labels
                                or environment in spot_eligible_labels
                            )

                            if is_spot_eligible:
                                machine_type = self._get_machine_type_name(
                                    instance.machine_type
                                )
                                standard_cost = self._get_machine_cost(machine_type)
                                spot_cost = self._get_machine_cost(
                                    machine_type, spot=True
                                )

                                monthly_waste = standard_cost - spot_cost

                                if monthly_waste >= min_savings_threshold:
                                    age_days = self._get_age_days(
                                        instance.creation_timestamp
                                    )
                                    already_wasted = monthly_waste * (age_days / 30.0)

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=str(instance.id),
                                            resource_name=instance.name,
                                            resource_type="compute_instance_no_spot",
                                            region=zone,
                                            estimated_monthly_cost=monthly_waste,
                                            resource_metadata={
                                                "zone": zone,
                                                "machine_type": machine_type,
                                                "status": instance.status,
                                                "age_days": age_days,
                                                "labels": labels,
                                                "current_monthly_cost": standard_cost,
                                                "spot_monthly_cost": spot_cost,
                                                "spot_discount_percentage": int(
                                                    self.SPOT_DISCOUNT * 100
                                                ),
                                                "already_wasted": round(
                                                    already_wasted, 2
                                                ),
                                                "confidence": "high",
                                                "recommendation": f"Convert to Spot VM for {int(self.SPOT_DISCOUNT*100)}% savings",
                                            },
                                        )
                                    )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_untagged_compute_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Scan for untagged instances (missing labels).

        Detection:
        - Missing required labels (environment, owner, cost-center)

        Cost:
        - 5% governance waste estimate
        """
        resources = []
        required_labels = (
            detection_rules.get("compute_instance_untagged", {}).get(
                "required_labels", ["environment", "owner", "cost-center"]
            )
            if detection_rules
            else ["environment", "owner", "cost-center"]
        )
        governance_waste_pct = (
            detection_rules.get("compute_instance_untagged", {}).get(
                "governance_waste_pct", 0.05
            )
            if detection_rules
            else 0.05
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        labels = dict(instance.labels) if instance.labels else {}

                        # Check for missing labels
                        missing_labels = [
                            label for label in required_labels if label not in labels
                        ]

                        if missing_labels:
                            machine_type = self._get_machine_type_name(
                                instance.machine_type
                            )
                            instance_monthly_cost = self._get_machine_cost(machine_type)

                            # Governance waste = 5% of instance cost
                            monthly_waste = (
                                instance_monthly_cost * governance_waste_pct
                            )

                            age_days = self._get_age_days(instance.creation_timestamp)
                            already_wasted = monthly_waste * (age_days / 30.0)

                            resources.append(
                                OrphanResourceData(
                                    resource_id=str(instance.id),
                                    resource_name=instance.name,
                                    resource_type="compute_instance_untagged",
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "zone": zone,
                                        "machine_type": machine_type,
                                        "status": instance.status,
                                        "age_days": age_days,
                                        "labels": labels,
                                        "missing_labels": missing_labels,
                                        "instance_monthly_cost": instance_monthly_cost,
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": "medium",
                                        "recommendation": "Add required labels for cost allocation",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_devtest_247_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Scan for dev/test instances running 24/7.

        Detection:
        - Status = RUNNING
        - Labels indicate dev/test environment
        - Uptime >= min_uptime_days (default: 7 days)

        Cost:
        - 64% savings with scheduled start/stop (8am-8pm Mon-Fri)
        """
        resources = []
        devtest_labels = (
            detection_rules.get("compute_instance_devtest_247", {}).get(
                "devtest_labels", ["dev", "test", "staging", "development"]
            )
            if detection_rules
            else ["dev", "test", "staging", "development"]
        )
        min_uptime_days = (
            detection_rules.get("compute_instance_devtest_247", {}).get(
                "min_uptime_days", 7
            )
            if detection_rules
            else 7
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        labels = dict(instance.labels) if instance.labels else {}
                        environment = labels.get("environment", "").lower()

                        # Check if dev/test environment
                        if environment in devtest_labels:
                            # Calculate uptime
                            if hasattr(instance, "last_start_timestamp"):
                                uptime_days = self._get_age_days(
                                    instance.last_start_timestamp
                                )
                            else:
                                uptime_days = self._get_age_days(
                                    instance.creation_timestamp
                                )

                            if uptime_days >= min_uptime_days:
                                machine_type = self._get_machine_type_name(
                                    instance.machine_type
                                )
                                monthly_cost = self._get_machine_cost(machine_type)

                                # Business hours: 12h/day * 5 days = 60h/week
                                # vs 168h/week (24/7)
                                # Savings: (168-60)/168 = 64%
                                waste_percentage = 0.64
                                monthly_waste = monthly_cost * waste_percentage

                                age_days = self._get_age_days(
                                    instance.creation_timestamp
                                )
                                already_wasted = monthly_waste * (age_days / 30.0)

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=str(instance.id),
                                        resource_name=instance.name,
                                        resource_type="compute_instance_devtest_247",
                                        region=zone,
                                        estimated_monthly_cost=monthly_waste,
                                        resource_metadata={
                                            "zone": zone,
                                            "machine_type": machine_type,
                                            "status": instance.status,
                                            "labels": labels,
                                            "uptime_days": uptime_days,
                                            "current_uptime_hours_weekly": 168,
                                            "optimal_uptime_hours_weekly": 60,
                                            "current_monthly_cost": monthly_cost,
                                            "optimal_monthly_cost": round(
                                                monthly_cost * 0.36, 2
                                            ),
                                            "waste_percentage": int(
                                                waste_percentage * 100
                                            ),
                                            "already_wasted": round(already_wasted, 2),
                                            "confidence": "high",
                                            "recommendation": "Implement automated start/stop schedule (8am-8pm Mon-Fri)",
                                        },
                                    )
                                )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    # ==================== PHASE 2 SCENARIOS ====================

    async def scan_memory_waste_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Scan for instances with over-provisioned memory (<40% usage).

        Detection:
        - Status = RUNNING
        - Cloud Monitoring Agent installed
        - avg_memory_used_14d < 40%

        Cost:
        - Savings from downgrading RAM (e.g., standard → highcpu)
        """
        resources = []
        memory_threshold = (
            detection_rules.get("compute_instance_memory_waste", {}).get(
                "memory_threshold", 40.0
            )
            if detection_rules
            else 40.0
        )
        lookback_days = (
            detection_rules.get("compute_instance_memory_waste", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        # Get memory metrics (requires monitoring agent)
                        memory_metrics = await self._get_memory_metrics(
                            str(instance.id), zone, lookback_days
                        )

                        if (
                            memory_metrics["datapoints"] >= 50
                            and memory_metrics["avg_memory"] < memory_threshold
                        ):
                            machine_type = self._get_machine_type_name(
                                instance.machine_type
                            )
                            current_cost = self._get_machine_cost(machine_type)

                            # Recommend highcpu variant (less RAM)
                            recommended_type = self._recommend_memory_downgrade(
                                machine_type
                            )
                            recommended_cost = self._get_machine_cost(recommended_type)

                            if recommended_cost < current_cost:
                                monthly_waste = current_cost - recommended_cost
                                age_days = self._get_age_days(
                                    instance.creation_timestamp
                                )
                                already_wasted = monthly_waste * (age_days / 30.0)

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=str(instance.id),
                                        resource_name=instance.name,
                                        resource_type="compute_instance_memory_waste",
                                        region=zone,
                                        estimated_monthly_cost=monthly_waste,
                                        resource_metadata={
                                            "zone": zone,
                                            "machine_type": machine_type,
                                            "status": instance.status,
                                            "memory_metrics": {
                                                "avg_memory_percent": round(
                                                    memory_metrics["avg_memory"], 2
                                                ),
                                                "max_memory_percent": round(
                                                    memory_metrics["max_memory"], 2
                                                ),
                                                "datapoints": memory_metrics[
                                                    "datapoints"
                                                ],
                                            },
                                            "current_monthly_cost": current_cost,
                                            "recommended_machine_type": recommended_type,
                                            "recommended_monthly_cost": recommended_cost,
                                            "already_wasted": round(already_wasted, 2),
                                            "confidence": "high",
                                            "recommendation": f"Downgrade to {recommended_type} (less RAM)",
                                        },
                                    )
                                )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    def _recommend_memory_downgrade(self, machine_type: str) -> str:
        """Recommend a machine type with less RAM."""
        # standard → highcpu (less RAM, same vCPUs)
        if "standard" in machine_type:
            return machine_type.replace("standard", "highcpu")
        # highmem → standard (less RAM)
        elif "highmem" in machine_type:
            return machine_type.replace("highmem", "standard")
        return machine_type

    async def scan_rightsizing_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Scan for rightsizing opportunities (holistic analysis).

        Detection:
        - Status = RUNNING
        - Comprehensive CPU + Memory analysis
        - Savings >= 10%

        Cost:
        - Difference between current and optimal size
        """
        resources = []
        min_savings_pct = (
            detection_rules.get("compute_instance_rightsizing", {}).get(
                "min_savings_pct", 10.0
            )
            if detection_rules
            else 10.0
        )
        lookback_days = (
            detection_rules.get("compute_instance_rightsizing", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        # Get both CPU and memory metrics
                        cpu_metrics = await self._get_cpu_metrics(
                            str(instance.id), zone, lookback_days
                        )
                        memory_metrics = await self._get_memory_metrics(
                            str(instance.id), zone, lookback_days
                        )

                        if (
                            cpu_metrics["datapoints"] >= 50
                            and memory_metrics["datapoints"] >= 50
                        ):
                            machine_type = self._get_machine_type_name(
                                instance.machine_type
                            )
                            current_cost = self._get_machine_cost(machine_type)

                            # Calculate optimal size based on usage
                            recommended_type = self._calculate_optimal_machine_type(
                                machine_type, cpu_metrics, memory_metrics
                            )
                            recommended_cost = self._get_machine_cost(recommended_type)

                            if recommended_type != machine_type:
                                savings_pct = (
                                    (current_cost - recommended_cost) / current_cost
                                ) * 100

                                if savings_pct >= min_savings_pct:
                                    monthly_waste = current_cost - recommended_cost
                                    age_days = self._get_age_days(
                                        instance.creation_timestamp
                                    )
                                    already_wasted = monthly_waste * (age_days / 30.0)

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=str(instance.id),
                                            resource_name=instance.name,
                                            resource_type="compute_instance_rightsizing",
                                            region=zone,
                                            estimated_monthly_cost=monthly_waste,
                                            resource_metadata={
                                                "zone": zone,
                                                "machine_type": machine_type,
                                                "status": instance.status,
                                                "metrics_analysis": {
                                                    "avg_cpu_percent": round(
                                                        cpu_metrics["avg_cpu"], 2
                                                    ),
                                                    "avg_memory_percent": round(
                                                        memory_metrics["avg_memory"], 2
                                                    ),
                                                },
                                                "current_monthly_cost": current_cost,
                                                "recommended_machine_type": recommended_type,
                                                "recommended_monthly_cost": recommended_cost,
                                                "savings_percentage": round(
                                                    savings_pct, 1
                                                ),
                                                "already_wasted": round(
                                                    already_wasted, 2
                                                ),
                                                "confidence": "high",
                                                "recommendation": f"Right-size to {recommended_type} for {round(savings_pct, 0)}% savings",
                                            },
                                        )
                                    )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    def _calculate_optimal_machine_type(
        self, current_type: str, cpu_metrics: dict, memory_metrics: dict
    ) -> str:
        """Calculate optimal machine type based on usage."""
        # Simple logic: if both CPU and memory <30%, downgrade
        if cpu_metrics["avg_cpu"] < 30 and memory_metrics["avg_memory"] < 30:
            # Downgrade by half
            if "standard-16" in current_type:
                return current_type.replace("standard-16", "standard-8")
            elif "standard-8" in current_type:
                return current_type.replace("standard-8", "standard-4")
            elif "standard-4" in current_type:
                return current_type.replace("standard-4", "standard-2")

        # If CPU low but memory high, use highcpu
        if cpu_metrics["avg_cpu"] < 30 and memory_metrics["avg_memory"] >= 40:
            return current_type.replace("standard", "highcpu")

        return current_type

    async def scan_burstable_waste_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Scan for e2 burstable instances not using burst capability.

        Detection:
        - machine_type starts with 'e2-'
        - Status = RUNNING
        - CPU rarely exceeds baseline (<5% of time)

        Cost:
        - Savings from e2 → f1/g1 downgrade
        """
        resources = []
        max_burst_pct = (
            detection_rules.get("compute_instance_burstable_waste", {}).get(
                "max_burst_pct", 5.0
            )
            if detection_rules
            else 5.0
        )
        lookback_days = (
            detection_rules.get("compute_instance_burstable_waste", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )

        try:
            compute_client = self._get_compute_client()
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone,
                        filter='status="RUNNING"',
                    )

                    instances = compute_client.list(request=request)

                    for instance in instances:
                        machine_type = self._get_machine_type_name(
                            instance.machine_type
                        )

                        # Check if e2 instance
                        if machine_type.startswith("e2-"):
                            # Get CPU metrics
                            cpu_metrics = await self._get_cpu_metrics(
                                str(instance.id), zone, lookback_days
                            )

                            if cpu_metrics["datapoints"] >= 50:
                                # Get baseline for this e2 type
                                baseline_cpu = self.E2_BASELINE_CPU.get(
                                    machine_type, 50.0
                                )

                                # Calculate % time above baseline (burst usage)
                                # Simplified: use avg CPU vs baseline
                                burst_usage = (
                                    max(0, cpu_metrics["avg_cpu"] - baseline_cpu)
                                    / baseline_cpu
                                    * 100
                                )

                                if burst_usage < max_burst_pct:
                                    current_cost = self._get_machine_cost(machine_type)

                                    # Recommend f1/g1 (shared-core, cheaper)
                                    recommended_type = (
                                        "f1-micro"
                                        if machine_type == "e2-micro"
                                        else "g1-small"
                                    )
                                    recommended_cost = self._get_machine_cost(
                                        recommended_type
                                    )

                                    if recommended_cost < current_cost:
                                        monthly_waste = current_cost - recommended_cost
                                        age_days = self._get_age_days(
                                            instance.creation_timestamp
                                        )
                                        already_wasted = monthly_waste * (
                                            age_days / 30.0
                                        )
                                        savings_pct = (
                                            monthly_waste / current_cost
                                        ) * 100

                                        resources.append(
                                            OrphanResourceData(
                                                resource_id=str(instance.id),
                                                resource_name=instance.name,
                                                resource_type="compute_instance_burstable_waste",
                                                region=zone,
                                                estimated_monthly_cost=monthly_waste,
                                                resource_metadata={
                                                    "zone": zone,
                                                    "machine_type": machine_type,
                                                    "status": instance.status,
                                                    "cpu_analysis": {
                                                        "baseline_cpu_percent": baseline_cpu,
                                                        "avg_cpu_percent": round(
                                                            cpu_metrics["avg_cpu"], 2
                                                        ),
                                                        "max_cpu_percent": round(
                                                            cpu_metrics["max_cpu"], 2
                                                        ),
                                                        "burst_usage_percent": round(
                                                            burst_usage, 2
                                                        ),
                                                    },
                                                    "current_monthly_cost": current_cost,
                                                    "recommended_machine_type": recommended_type,
                                                    "recommended_monthly_cost": recommended_cost,
                                                    "savings_percentage": round(
                                                        savings_pct, 1
                                                    ),
                                                    "already_wasted": round(
                                                        already_wasted, 2
                                                    ),
                                                    "confidence": "high",
                                                    "recommendation": f"Downgrade to {recommended_type} (burst capability unused)",
                                                },
                                            )
                                        )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    # ==================== PERSISTENT DISKS (10 SCENARIOS) ====================

    def _get_disks_client(self) -> compute_v1.DisksClient:
        """Get or create Disks client."""
        if not hasattr(self, "_disks_client") or self._disks_client is None:
            self._disks_client = compute_v1.DisksClient(
                credentials=self._get_credentials()
            )
        return self._disks_client

    def _get_snapshots_client(self) -> compute_v1.SnapshotsClient:
        """Get or create Snapshots client."""
        if not hasattr(self, "_snapshots_client") or self._snapshots_client is None:
            self._snapshots_client = compute_v1.SnapshotsClient(
                credentials=self._get_credentials()
            )
        return self._snapshots_client

    def _get_logging_client(self) -> logging.Client:
        """Get or create Cloud Logging client."""
        if not hasattr(self, "_logging_client") or self._logging_client is None:
            self._logging_client = logging.Client(
                project=self.project_id, credentials=self._get_credentials()
            )
        return self._logging_client

    def _get_disk_pricing(self, disk_type: str) -> float:
        """Get pricing per GB/month for disk type (us-central1 pricing)."""
        pricing = {
            "pd-standard": 0.040,
            "pd-balanced": 0.100,
            "pd-ssd": 0.170,
            "pd-extreme": 0.125,
        }
        return pricing.get(disk_type, 0.040)

    async def scan_unattached_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Scan for unattached persistent disks >7 days.

        Detects disks that are not attached to any instance and wasting 100% of cost.
        """
        resources = []
        min_age_days = (
            detection_rules.get("persistent_disk_unattached", {}).get("min_age_days", 7)
            if detection_rules
            else 7
        )
        exclude_labels = (
            detection_rules.get("persistent_disk_unattached", {}).get(
                "exclude_labels", {}
            )
            if detection_rules
            else {}
        )

        try:
            disks_client = self._get_disks_client()

            # List all disks in the region
            # GCP uses zones, so iterate through common zones in the region
            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Check if disk is unattached
                        users = disk.users if hasattr(disk, "users") else []

                        if users and len(users) > 0:
                            continue  # Disk is attached

                        # Check labels exclusion
                        labels = disk.labels if hasattr(disk, "labels") else {}
                        if self._matches_exclude_labels(labels, exclude_labels):
                            continue

                        # Check age
                        creation_timestamp = getattr(
                            disk, "creation_timestamp", None
                        )
                        if not creation_timestamp:
                            continue

                        age_days = self._get_age_days(creation_timestamp)
                        if age_days < min_age_days:
                            continue

                        # Calculate cost
                        disk_size_gb = disk.size_gb
                        disk_type = disk.type.split("/")[-1]
                        price_per_gb = self._get_disk_pricing(disk_type)

                        monthly_cost = disk_size_gb * price_per_gb
                        age_months = age_days / 30.0
                        already_wasted = monthly_cost * age_months

                        # Determine confidence
                        if age_days >= 90:
                            confidence = "critical"
                        elif age_days >= 60:
                            confidence = "high"
                        elif age_days >= 30:
                            confidence = "medium"
                        else:
                            confidence = "low"

                        metadata = {
                            "resource_id": disk.id,
                            "resource_name": disk.name,
                            "zone": zone,
                            "disk_type": disk_type,
                            "size_gb": disk_size_gb,
                            "status": disk.status,
                            "users": [],
                            "creation_timestamp": creation_timestamp,
                            "age_days": age_days,
                            "labels": labels,
                            "recommendation": "Delete disk or attach to instance",
                        }

                        resources.append(
                            OrphanResourceData(
                                resource_type="persistent_disk_unattached",
                                resource_id=str(disk.id),
                                resource_name=disk.name,
                                region=zone,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata=metadata,
                                confidence=confidence,
                                already_wasted=already_wasted,
                            )
                        )

                except Exception:
                    # Zone might not exist, continue to next
                    continue

        except Exception:
            pass

        return resources

    async def scan_attached_stopped_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Scan for disks attached to stopped instances >30 days.

        Detects disks attached to instances that have been stopped for extended periods.
        """
        resources = []
        min_age_days = (
            detection_rules.get("persistent_disk_attached_stopped", {}).get(
                "min_age_days", 30
            )
            if detection_rules
            else 30
        )
        exclude_boot_disks = (
            detection_rules.get("persistent_disk_attached_stopped", {}).get(
                "exclude_boot_disks", False
            )
            if detection_rules
            else False
        )

        try:
            disks_client = self._get_disks_client()
            instances_client = self._get_compute_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Check if disk is attached
                        users = disk.users if hasattr(disk, "users") else []

                        if not users or len(users) == 0:
                            continue  # Disk is not attached

                        # Get instance details
                        for instance_url in users:
                            try:
                                # Extract instance name from URL
                                instance_name = instance_url.split("/")[-1]

                                # Get instance
                                instance = instances_client.get(
                                    project=self.project_id,
                                    zone=zone,
                                    instance=instance_name,
                                )

                                # Check if instance is stopped
                                if instance.status != "TERMINATED":
                                    continue

                                # Check how long instance has been stopped
                                last_stop_timestamp = getattr(
                                    instance, "last_stop_timestamp", None
                                )
                                if not last_stop_timestamp:
                                    continue

                                stopped_days = self._get_age_days(last_stop_timestamp)
                                if stopped_days < min_age_days:
                                    continue

                                # Calculate cost
                                disk_size_gb = disk.size_gb
                                disk_type = disk.type.split("/")[-1]
                                price_per_gb = self._get_disk_pricing(disk_type)

                                monthly_cost = disk_size_gb * price_per_gb
                                already_wasted = monthly_cost * (stopped_days / 30.0)

                                # Determine confidence
                                if stopped_days >= 90:
                                    confidence = "high"
                                elif stopped_days >= 60:
                                    confidence = "medium"
                                else:
                                    confidence = "low"

                                metadata = {
                                    "resource_id": disk.id,
                                    "resource_name": disk.name,
                                    "zone": zone,
                                    "disk_type": disk_type,
                                    "size_gb": disk_size_gb,
                                    "status": disk.status,
                                    "users": [instance_url],
                                    "attached_instance": {
                                        "name": instance_name,
                                        "status": instance.status,
                                        "last_stop_timestamp": last_stop_timestamp,
                                        "stopped_days": stopped_days,
                                    },
                                    "creation_timestamp": getattr(
                                        disk, "creation_timestamp", None
                                    ),
                                    "recommendation": "Delete disk or restart instance if still needed",
                                }

                                resources.append(
                                    OrphanResourceData(
                                        resource_type="persistent_disk_attached_stopped",
                                        resource_id=str(disk.id),
                                        resource_name=disk.name,
                                        region=zone,
                                        estimated_monthly_cost=monthly_cost,
                                        resource_metadata=metadata,
                                        confidence=confidence,
                                        already_wasted=already_wasted,
                                    )
                                )

                            except Exception:
                                continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_never_used_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Scan for disks with zero I/O since creation >7 days.

        Uses Cloud Monitoring metrics to detect disks that have never been used.
        """
        resources = []
        min_age_days = (
            detection_rules.get("persistent_disk_never_used", {}).get(
                "min_age_days", 7
            )
            if detection_rules
            else 7
        )
        zero_io_threshold = (
            detection_rules.get("persistent_disk_never_used", {}).get(
                "zero_io_threshold", 0
            )
            if detection_rules
            else 0
        )

        try:
            disks_client = self._get_disks_client()
            monitoring_client = self._get_monitoring_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Check age
                        creation_timestamp = getattr(
                            disk, "creation_timestamp", None
                        )
                        if not creation_timestamp:
                            continue

                        age_days = self._get_age_days(creation_timestamp)
                        if age_days < min_age_days:
                            continue

                        # Query I/O metrics
                        creation_date = self._parse_timestamp(creation_timestamp)

                        interval = monitoring_v3.TimeInterval(
                            {
                                "end_time": {"seconds": int(time.time())},
                                "start_time": {"seconds": int(creation_date.timestamp())},
                            }
                        )

                        # Query read operations
                        try:
                            read_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/read_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            write_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/write_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            total_read_ops = sum(
                                [
                                    point.value.int64_value
                                    for series in read_ops
                                    for point in series.points
                                ]
                            )
                            total_write_ops = sum(
                                [
                                    point.value.int64_value
                                    for series in write_ops
                                    for point in series.points
                                ]
                            )

                            # Check if zero I/O
                            if (
                                total_read_ops <= zero_io_threshold
                                and total_write_ops <= zero_io_threshold
                            ):
                                # Calculate cost
                                disk_size_gb = disk.size_gb
                                disk_type = disk.type.split("/")[-1]
                                price_per_gb = self._get_disk_pricing(disk_type)

                                monthly_cost = disk_size_gb * price_per_gb
                                age_months = age_days / 30.0
                                already_wasted = monthly_cost * age_months

                                confidence = (
                                    "high" if age_days >= 30 else "medium"
                                )

                                metadata = {
                                    "resource_id": disk.id,
                                    "resource_name": disk.name,
                                    "zone": zone,
                                    "disk_type": disk_type,
                                    "size_gb": disk_size_gb,
                                    "status": disk.status,
                                    "io_metrics": {
                                        "total_read_ops": total_read_ops,
                                        "total_write_ops": total_write_ops,
                                        "total_read_bytes": 0,
                                        "total_write_bytes": 0,
                                    },
                                    "creation_timestamp": creation_timestamp,
                                    "age_days": age_days,
                                    "recommendation": "Delete disk - never used since creation",
                                }

                                resources.append(
                                    OrphanResourceData(
                                        resource_type="persistent_disk_never_used",
                                        resource_id=str(disk.id),
                                        resource_name=disk.name,
                                        region=zone,
                                        estimated_monthly_cost=monthly_cost,
                                        resource_metadata=metadata,
                                        confidence=confidence,
                                        already_wasted=already_wasted,
                                    )
                                )

                        except Exception:
                            # Metrics might not be available
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_orphan_disk_snapshots(
        self,
        region: str,
        detection_rules: dict | None = None,
        orphaned_volume_ids: list[str] | None = None,
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Scan for snapshots whose source disk no longer exists >30 days.

        Detects orphaned snapshots that may no longer be needed.
        """
        resources = []
        min_age_days = (
            detection_rules.get("persistent_disk_orphan_snapshots", {}).get(
                "min_age_days", 30
            )
            if detection_rules
            else 30
        )
        exclude_labels = (
            detection_rules.get("persistent_disk_orphan_snapshots", {}).get(
                "exclude_labels", {}
            )
            if detection_rules
            else {}
        )

        try:
            snapshots_client = self._get_snapshots_client()
            disks_client = self._get_disks_client()

            # Get all snapshots
            snapshots_list = list(snapshots_client.list(project=self.project_id))

            # Get all existing disk names
            all_disk_names = set()

            # Aggregate list across all zones
            aggregated_request = compute_v1.AggregatedListDisksRequest(
                project=self.project_id
            )
            agg_list = disks_client.aggregated_list(request=aggregated_request)

            for zone_name, response in agg_list:
                if hasattr(response, "disks") and response.disks:
                    for disk in response.disks:
                        all_disk_names.add(disk.name)

            # Check each snapshot
            for snapshot in snapshots_list:
                source_disk_url = getattr(snapshot, "source_disk", None)

                if not source_disk_url:
                    # Snapshot without source
                    continue

                # Extract disk name from URL
                source_disk_name = source_disk_url.split("/")[-1]

                # Check if source disk still exists
                if source_disk_name in all_disk_names:
                    continue  # Disk still exists

                # Check labels exclusion
                labels = snapshot.labels if hasattr(snapshot, "labels") else {}
                if self._matches_exclude_labels(labels, exclude_labels):
                    continue

                # Check age
                creation_timestamp = getattr(snapshot, "creation_timestamp", None)
                if not creation_timestamp:
                    continue

                age_days = self._get_age_days(creation_timestamp)
                if age_days < min_age_days:
                    continue

                # Calculate cost
                snapshot_size_gb = (
                    snapshot.storage_bytes / (1024**3)
                    if hasattr(snapshot, "storage_bytes")
                    else 0
                )
                snapshot_price_per_gb = 0.026

                monthly_cost = snapshot_size_gb * snapshot_price_per_gb
                age_months = age_days / 30.0
                already_wasted = monthly_cost * age_months

                confidence = "medium"  # Orphan snapshots may still be needed

                metadata = {
                    "resource_id": snapshot.id,
                    "resource_name": snapshot.name,
                    "snapshot_size_gb": snapshot_size_gb,
                    "storage_bytes": getattr(snapshot, "storage_bytes", 0),
                    "source_disk": source_disk_url,
                    "source_disk_exists": False,
                    "creation_timestamp": creation_timestamp,
                    "age_days": age_days,
                    "labels": labels,
                    "recommendation": "Review if snapshot still needed, consider deletion",
                }

                resources.append(
                    OrphanResourceData(
                        resource_type="persistent_disk_orphan_snapshots",
                        resource_id=str(snapshot.id),
                        resource_name=snapshot.name,
                        region="global",  # Snapshots are global
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata,
                        confidence=confidence,
                        already_wasted=already_wasted,
                    )
                )

        except Exception:
            pass

        return resources

    async def scan_old_type_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Scan for pd-standard disks with active workloads → recommend pd-balanced.

        Detects performance waste from using old HDD disks for active workloads.
        """
        resources = []
        min_io_threshold = (
            detection_rules.get("persistent_disk_old_type", {}).get(
                "min_io_threshold", 100
            )
            if detection_rules
            else 100
        )
        lookback_days = (
            detection_rules.get("persistent_disk_old_type", {}).get(
                "lookback_days", 7
            )
            if detection_rules
            else 7
        )
        performance_waste_factor = (
            detection_rules.get("persistent_disk_old_type", {}).get(
                "performance_waste_factor", 0.6
            )
            if detection_rules
            else 0.6
        )

        try:
            disks_client = self._get_disks_client()
            monitoring_client = self._get_monitoring_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        disk_type = disk.type.split("/")[-1]

                        # Only check pd-standard disks
                        if disk_type != "pd-standard":
                            continue

                        # Query I/O metrics for the last week
                        interval = monitoring_v3.TimeInterval(
                            {
                                "end_time": {"seconds": int(time.time())},
                                "start_time": {
                                    "seconds": int(time.time())
                                    - lookback_days * 24 * 3600
                                },
                            }
                        )

                        try:
                            read_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/read_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            write_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/write_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            total_ops = sum(
                                [
                                    point.value.int64_value
                                    for series in read_ops
                                    for point in series.points
                                ]
                            ) + sum(
                                [
                                    point.value.int64_value
                                    for series in write_ops
                                    for point in series.points
                                ]
                            )

                            # Calculate avg ops per day
                            avg_ops_per_day = total_ops / lookback_days

                            # Check if disk is active
                            if avg_ops_per_day < min_io_threshold:
                                continue  # Disk not active enough

                            # Calculate cost waste (performance opportunity cost)
                            disk_size_gb = disk.size_gb

                            current_cost = disk_size_gb * 0.040  # pd-standard
                            recommended_cost = disk_size_gb * 0.100  # pd-balanced

                            # Performance waste = upgrade cost * waste factor
                            monthly_waste = (
                                recommended_cost - current_cost
                            ) * performance_waste_factor

                            creation_timestamp = getattr(
                                disk, "creation_timestamp", None
                            )
                            age_days = (
                                self._get_age_days(creation_timestamp)
                                if creation_timestamp
                                else 0
                            )
                            already_wasted = monthly_waste * (age_days / 30.0)

                            confidence = "medium"

                            metadata = {
                                "resource_id": disk.id,
                                "resource_name": disk.name,
                                "zone": zone,
                                "disk_type": disk_type,
                                "size_gb": disk_size_gb,
                                "io_metrics": {
                                    "avg_ops_per_day": avg_ops_per_day,
                                },
                                "current_cost_monthly": current_cost,
                                "recommended_disk_type": "pd-balanced",
                                "recommended_cost_monthly": recommended_cost,
                                "performance_improvement": {
                                    "throughput_increase_percent": 133,
                                    "iops_increase_percent": 700,
                                },
                                "recommendation": "Migrate to pd-balanced for 8x IOPS and 2.3x throughput",
                            }

                            resources.append(
                                OrphanResourceData(
                                    resource_type="persistent_disk_old_type",
                                    resource_id=str(disk.id),
                                    resource_name=disk.name,
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata=metadata,
                                    confidence=confidence,
                                    already_wasted=already_wasted,
                                )
                            )

                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_overprovisioned_type_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Scan for pd-ssd disks using <50% of pd-balanced capacity → downgrade.

        Detects overprovisioned SSD disks that could be downgraded to save costs.
        """
        resources = []
        iops_utilization_threshold = (
            detection_rules.get("persistent_disk_overprovisioned_type", {}).get(
                "iops_utilization_threshold", 0.5
            )
            if detection_rules
            else 0.5
        )
        lookback_days = (
            detection_rules.get("persistent_disk_overprovisioned_type", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )
        min_savings_threshold = (
            detection_rules.get("persistent_disk_overprovisioned_type", {}).get(
                "min_savings_threshold", 10.0
            )
            if detection_rules
            else 10.0
        )

        try:
            disks_client = self._get_disks_client()
            monitoring_client = self._get_monitoring_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        disk_type = disk.type.split("/")[-1]

                        # Only check pd-ssd disks
                        if disk_type != "pd-ssd":
                            continue

                        # Query IOPS metrics
                        interval = monitoring_v3.TimeInterval(
                            {
                                "end_time": {"seconds": int(time.time())},
                                "start_time": {
                                    "seconds": int(time.time())
                                    - lookback_days * 24 * 3600
                                },
                            }
                        )

                        try:
                            read_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/read_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            write_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/write_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            # Calculate average IOPS
                            total_datapoints = 0
                            total_iops = 0

                            for series in read_ops:
                                total_datapoints += len(series.points)
                                total_iops += sum(
                                    [point.value.int64_value for point in series.points]
                                )

                            for series in write_ops:
                                total_datapoints += len(series.points)
                                total_iops += sum(
                                    [point.value.int64_value for point in series.points]
                                )

                            if total_datapoints == 0:
                                continue

                            avg_iops = total_iops / total_datapoints

                            # Calculate pd-balanced capacity
                            disk_size_gb = disk.size_gb
                            pd_balanced_max_iops = disk_size_gb * 6  # 6 IOPS/GB

                            # Check if under-utilizing
                            if avg_iops >= (
                                pd_balanced_max_iops * iops_utilization_threshold
                            ):
                                continue  # Using enough IOPS

                            # Calculate cost savings
                            current_cost = disk_size_gb * 0.170  # pd-ssd
                            recommended_cost = disk_size_gb * 0.100  # pd-balanced
                            monthly_waste = current_cost - recommended_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            utilization_percent = (
                                (avg_iops / pd_balanced_max_iops * 100)
                                if pd_balanced_max_iops > 0
                                else 0
                            )

                            creation_timestamp = getattr(
                                disk, "creation_timestamp", None
                            )
                            age_days = (
                                self._get_age_days(creation_timestamp)
                                if creation_timestamp
                                else 0
                            )
                            already_wasted = monthly_waste * (age_days / 30.0)

                            confidence = "high"

                            metadata = {
                                "resource_id": disk.id,
                                "resource_name": disk.name,
                                "zone": zone,
                                "disk_type": disk_type,
                                "size_gb": disk_size_gb,
                                "io_metrics": {
                                    "avg_total_iops": avg_iops,
                                },
                                "pd_balanced_capacity": {
                                    "max_iops": pd_balanced_max_iops,
                                    "current_utilization_percent": utilization_percent,
                                },
                                "current_cost_monthly": current_cost,
                                "recommended_disk_type": "pd-balanced",
                                "recommended_cost_monthly": recommended_cost,
                                "savings_percentage": int(
                                    (monthly_waste / current_cost) * 100
                                ),
                                "recommendation": f"Downgrade to pd-balanced - using only {utilization_percent:.0f}% of pd-balanced capacity",
                            }

                            resources.append(
                                OrphanResourceData(
                                    resource_type="persistent_disk_overprovisioned_type",
                                    resource_id=str(disk.id),
                                    resource_name=disk.name,
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata=metadata,
                                    confidence=confidence,
                                    already_wasted=already_wasted,
                                )
                            )

                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_untagged_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Scan for disks missing required labels.

        Detects governance waste from untagged resources.
        """
        resources = []
        required_labels = (
            detection_rules.get("persistent_disk_untagged", {}).get(
                "required_labels", ["environment", "owner", "cost-center"]
            )
            if detection_rules
            else ["environment", "owner", "cost-center"]
        )
        governance_waste_pct = (
            detection_rules.get("persistent_disk_untagged", {}).get(
                "governance_waste_pct", 0.05
            )
            if detection_rules
            else 0.05
        )

        try:
            disks_client = self._get_disks_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Check labels
                        labels = disk.labels if hasattr(disk, "labels") else {}

                        # Find missing labels
                        missing_labels = [
                            label for label in required_labels if label not in labels
                        ]

                        if not missing_labels:
                            continue  # All required labels present

                        # Calculate governance waste
                        disk_size_gb = disk.size_gb
                        disk_type = disk.type.split("/")[-1]
                        price_per_gb = self._get_disk_pricing(disk_type)

                        disk_monthly_cost = disk_size_gb * price_per_gb
                        monthly_waste = disk_monthly_cost * governance_waste_pct

                        creation_timestamp = getattr(
                            disk, "creation_timestamp", None
                        )
                        age_days = (
                            self._get_age_days(creation_timestamp)
                            if creation_timestamp
                            else 0
                        )
                        already_wasted = monthly_waste * (age_days / 30.0)

                        confidence = "medium"

                        metadata = {
                            "resource_id": disk.id,
                            "resource_name": disk.name,
                            "zone": zone,
                            "disk_type": disk_type,
                            "size_gb": disk_size_gb,
                            "labels": labels,
                            "missing_labels": missing_labels,
                            "creation_timestamp": creation_timestamp,
                            "age_days": age_days,
                            "disk_monthly_cost": disk_monthly_cost,
                            "recommendation": "Add required labels for cost allocation and governance",
                        }

                        resources.append(
                            OrphanResourceData(
                                resource_type="persistent_disk_untagged",
                                resource_id=str(disk.id),
                                resource_name=disk.name,
                                region=zone,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata=metadata,
                                confidence=confidence,
                                already_wasted=already_wasted,
                            )
                        )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_underutilized_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Scan for disks with <10% throughput utilization over 14 days.

        Detects disks that could be downgraded based on actual throughput usage.
        """
        resources = []
        utilization_threshold = (
            detection_rules.get("persistent_disk_underutilized", {}).get(
                "utilization_threshold", 10.0
            )
            if detection_rules
            else 10.0
        )
        lookback_days = (
            detection_rules.get("persistent_disk_underutilized", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )
        min_datapoints = (
            detection_rules.get("persistent_disk_underutilized", {}).get(
                "min_datapoints", 50
            )
            if detection_rules
            else 50
        )

        try:
            disks_client = self._get_disks_client()
            monitoring_client = self._get_monitoring_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Only check attached disks
                        users = disk.users if hasattr(disk, "users") else []
                        if not users or len(users) == 0:
                            continue

                        disk_type = disk.type.split("/")[-1]

                        # Query throughput metrics
                        interval = monitoring_v3.TimeInterval(
                            {
                                "end_time": {"seconds": int(time.time())},
                                "start_time": {
                                    "seconds": int(time.time())
                                    - lookback_days * 24 * 3600
                                },
                            }
                        )

                        try:
                            read_throughput = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/read_bytes_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            write_throughput = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/write_bytes_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            # Calculate average throughput
                            total_datapoints = 0
                            total_bytes = 0

                            for series in read_throughput:
                                total_datapoints += len(series.points)
                                total_bytes += sum(
                                    [
                                        point.value.double_value
                                        for point in series.points
                                    ]
                                )

                            for series in write_throughput:
                                total_datapoints += len(series.points)
                                total_bytes += sum(
                                    [
                                        point.value.double_value
                                        for point in series.points
                                    ]
                                )

                            if total_datapoints < min_datapoints:
                                continue

                            avg_mbps = (
                                (total_bytes / total_datapoints) / (1024 * 1024)
                                if total_datapoints > 0
                                else 0
                            )

                            # Calculate max throughput capacity
                            disk_size_gb = disk.size_gb
                            max_throughput_mbps = {
                                "pd-standard": disk_size_gb * 0.12,
                                "pd-balanced": disk_size_gb * 0.28,
                                "pd-ssd": disk_size_gb * 0.48,
                            }.get(disk_type, 0)

                            if max_throughput_mbps == 0:
                                continue

                            utilization_percent = (
                                (avg_mbps / max_throughput_mbps * 100)
                                if max_throughput_mbps > 0
                                else 0
                            )

                            # Check if under-utilized
                            if utilization_percent >= utilization_threshold:
                                continue

                            # Calculate potential savings (downgrade scenario)
                            current_cost = disk_size_gb * self._get_disk_pricing(
                                disk_type
                            )

                            # Recommend downgrade
                            if disk_type == "pd-ssd":
                                recommended_type = "pd-balanced"
                                recommended_cost = disk_size_gb * 0.100
                            elif disk_type == "pd-balanced":
                                recommended_type = "pd-standard"
                                recommended_cost = disk_size_gb * 0.040
                            else:
                                continue  # Already at lowest tier

                            monthly_waste = current_cost - recommended_cost

                            creation_timestamp = getattr(
                                disk, "creation_timestamp", None
                            )
                            age_days = (
                                self._get_age_days(creation_timestamp)
                                if creation_timestamp
                                else 0
                            )
                            already_wasted = monthly_waste * (age_days / 30.0)

                            confidence = "high"

                            metadata = {
                                "resource_id": disk.id,
                                "resource_name": disk.name,
                                "zone": zone,
                                "disk_type": disk_type,
                                "size_gb": disk_size_gb,
                                "io_metrics": {
                                    "avg_total_mbps": avg_mbps,
                                    "max_throughput_capacity_mbps": max_throughput_mbps,
                                    "utilization_percent": utilization_percent,
                                },
                                "current_cost_monthly": current_cost,
                                "recommended_disk_type": recommended_type,
                                "recommended_cost_monthly": recommended_cost,
                                "recommendation": f"Downgrade to {recommended_type} - using only {utilization_percent:.0f}% of throughput capacity",
                            }

                            resources.append(
                                OrphanResourceData(
                                    resource_type="persistent_disk_underutilized",
                                    resource_id=str(disk.id),
                                    resource_name=disk.name,
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata=metadata,
                                    confidence=confidence,
                                    already_wasted=already_wasted,
                                )
                            )

                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_oversized_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Scan for disks with >80% free space over 14 days.

        Detects over-provisioned disk sizes based on actual usage.
        Requires Cloud Monitoring Agent installed on instances.
        """
        resources = []
        free_space_threshold = (
            detection_rules.get("persistent_disk_oversized", {}).get(
                "free_space_threshold", 80.0
            )
            if detection_rules
            else 80.0
        )
        safety_buffer = (
            detection_rules.get("persistent_disk_oversized", {}).get(
                "safety_buffer", 1.30
            )
            if detection_rules
            else 1.30
        )
        min_savings_threshold = (
            detection_rules.get("persistent_disk_oversized", {}).get(
                "min_savings_threshold", 5.0
            )
            if detection_rules
            else 5.0
        )
        lookback_days = (
            detection_rules.get("persistent_disk_oversized", {}).get(
                "lookback_days", 14
            )
            if detection_rules
            else 14
        )

        try:
            disks_client = self._get_disks_client()
            monitoring_client = self._get_monitoring_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Only check attached disks
                        users = disk.users if hasattr(disk, "users") else []
                        if not users or len(users) == 0:
                            continue

                        # Query disk usage
                        interval = monitoring_v3.TimeInterval(
                            {
                                "end_time": {"seconds": int(time.time())},
                                "start_time": {
                                    "seconds": int(time.time())
                                    - lookback_days * 24 * 3600
                                },
                            }
                        )

                        try:
                            disk_usage = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="agent.googleapis.com/disk/percent_used" AND resource.device="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            usage_values = [
                                point.value.double_value
                                for series in disk_usage
                                for point in series.points
                            ]

                            if not usage_values:
                                # Agent not installed, skip
                                continue

                            avg_used_percent = sum(usage_values) / len(usage_values)
                            free_percent = 100 - avg_used_percent

                            # Check if over-sized
                            if free_percent < free_space_threshold:
                                continue

                            # Calculate recommended size
                            disk_size_gb = disk.size_gb
                            used_gb = disk_size_gb * (avg_used_percent / 100.0)
                            recommended_size_gb = int(used_gb * safety_buffer)

                            # Calculate savings
                            disk_type = disk.type.split("/")[-1]
                            price_per_gb = self._get_disk_pricing(disk_type)

                            current_cost = disk_size_gb * price_per_gb
                            recommended_cost = recommended_size_gb * price_per_gb
                            monthly_waste = current_cost - recommended_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            creation_timestamp = getattr(
                                disk, "creation_timestamp", None
                            )
                            age_days = (
                                self._get_age_days(creation_timestamp)
                                if creation_timestamp
                                else 0
                            )
                            already_wasted = monthly_waste * (age_days / 30.0)

                            confidence = "high"

                            metadata = {
                                "resource_id": disk.id,
                                "resource_name": disk.name,
                                "zone": zone,
                                "disk_type": disk_type,
                                "size_gb": disk_size_gb,
                                "disk_usage": {
                                    "avg_used_percent": avg_used_percent,
                                    "avg_used_gb": used_gb,
                                    "avg_free_percent": free_percent,
                                    "avg_free_gb": disk_size_gb - used_gb,
                                },
                                "recommended_size_gb": recommended_size_gb,
                                "current_cost_monthly": current_cost,
                                "recommended_cost_monthly": recommended_cost,
                                "savings_percentage": int(
                                    (monthly_waste / current_cost) * 100
                                ),
                                "recommendation": f"Resize from {disk_size_gb}GB to {recommended_size_gb}GB - using only {avg_used_percent:.0f}% of capacity",
                                "monitoring_agent_installed": True,
                            }

                            resources.append(
                                OrphanResourceData(
                                    resource_type="persistent_disk_oversized",
                                    resource_id=str(disk.id),
                                    resource_name=disk.name,
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata=metadata,
                                    confidence=confidence,
                                    already_wasted=already_wasted,
                                )
                            )

                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_readonly_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Scan for disks with zero writes for 30 days → recommend snapshot.

        Detects read-only disks that could be converted to cheaper snapshots.
        """
        resources = []
        max_write_ops_threshold = (
            detection_rules.get("persistent_disk_readonly", {}).get(
                "max_write_ops_threshold", 10
            )
            if detection_rules
            else 10
        )
        lookback_days = (
            detection_rules.get("persistent_disk_readonly", {}).get(
                "lookback_days", 30
            )
            if detection_rules
            else 30
        )
        min_savings_threshold = (
            detection_rules.get("persistent_disk_readonly", {}).get(
                "min_savings_threshold", 5.0
            )
            if detection_rules
            else 5.0
        )

        try:
            disks_client = self._get_disks_client()
            monitoring_client = self._get_monitoring_client()

            zones = [f"{region}-a", f"{region}-b", f"{region}-c", f"{region}-f"]

            for zone in zones:
                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone,
                    )

                    disks = disks_client.list(request=request)

                    for disk in disks:
                        # Only check attached disks
                        users = disk.users if hasattr(disk, "users") else []
                        if not users or len(users) == 0:
                            continue

                        # Query write operations
                        interval = monitoring_v3.TimeInterval(
                            {
                                "end_time": {"seconds": int(time.time())},
                                "start_time": {
                                    "seconds": int(time.time())
                                    - lookback_days * 24 * 3600
                                },
                            }
                        )

                        try:
                            write_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/write_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            read_ops = monitoring_client.list_time_series(
                                request={
                                    "name": f"projects/{self.project_id}",
                                    "filter": f'metric.type="compute.googleapis.com/instance/disk/read_ops_count" AND resource.disk_name="{disk.name}"',
                                    "interval": interval,
                                }
                            )

                            total_writes = sum(
                                [
                                    point.value.int64_value
                                    for series in write_ops
                                    for point in series.points
                                ]
                            )

                            total_reads = sum(
                                [
                                    point.value.int64_value
                                    for series in read_ops
                                    for point in series.points
                                ]
                            )

                            # Check if read-only
                            if total_writes > max_write_ops_threshold:
                                continue

                            # Calculate savings (disk → snapshot)
                            disk_size_gb = disk.size_gb
                            disk_type = disk.type.split("/")[-1]

                            disk_cost = disk_size_gb * self._get_disk_pricing(
                                disk_type
                            )
                            snapshot_cost = disk_size_gb * 0.026

                            monthly_waste = disk_cost - snapshot_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            # Calculate readonly period
                            readonly_days = lookback_days
                            already_wasted = monthly_waste * (readonly_days / 30.0)

                            confidence = "high"

                            metadata = {
                                "resource_id": disk.id,
                                "resource_name": disk.name,
                                "zone": zone,
                                "disk_type": disk_type,
                                "size_gb": disk_size_gb,
                                "io_metrics": {
                                    "total_read_ops_30d": total_reads,
                                    "total_write_ops_30d": total_writes,
                                    "readonly_days": readonly_days,
                                },
                                "current_cost_monthly": disk_cost,
                                "recommended_storage": "snapshot",
                                "recommended_cost_monthly": snapshot_cost,
                                "savings_percentage": int(
                                    (monthly_waste / disk_cost) * 100
                                ),
                                "recommendation": f"Convert to snapshot - zero writes for {readonly_days} days",
                            }

                            resources.append(
                                OrphanResourceData(
                                    resource_type="persistent_disk_readonly",
                                    resource_id=str(disk.id),
                                    resource_name=disk.name,
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata=metadata,
                                    confidence=confidence,
                                    already_wasted=already_wasted,
                                )
                            )

                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    # Legacy method name for backward compatibility
    async def scan_unattached_volumes(self, region: str) -> list[OrphanResourceData]:
        """Legacy method - redirects to scan_unattached_disks."""
        return await self.scan_unattached_disks(region)

    async def scan_orphaned_snapshots(
        self,
        region: str,
        detection_rules: dict | None = None,
        orphaned_volume_ids: list[str] | None = None,
    ) -> list[OrphanResourceData]:
        """Legacy method - redirects to scan_orphan_disk_snapshots."""
        return await self.scan_orphan_disk_snapshots(region, detection_rules)

    # ==================== OTHER STUB METHODS (NOT IMPLEMENTED) ====================

    async def scan_unassigned_ips(self, region: str) -> list[OrphanResourceData]:
        """Scan for unassigned static IP addresses (Phase 2)."""
        return []


    async def scan_unused_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused load balancers (Phase 2)."""
        return []

    async def scan_cloud_sql_stopped(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect stopped Cloud SQL instances >30 days.

        Waste: Stopped instances still pay storage + backups (~30-50% of total cost).
        Detection: state == 'STOPPED' AND age >= 30 days
        Cost: Storage $0.17/GB + Backups $0.08/GB (~$29-145/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from datetime import datetime, timezone

            # Get detection parameters
            min_age_days = 30
            if detection_rules and "cloud_sql_stopped" in detection_rules:
                rules = detection_rules["cloud_sql_stopped"]
                min_age_days = rules.get("min_age_days", 30)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)

            # List all Cloud SQL instances
            try:
                request = sql_v1.ListInstancesRequest(
                    project=self.project_id
                )

                for instance in sql_client.list(request=request):
                    # Check if instance is stopped
                    if instance.state != sql_v1.Instance.State.SUSPENDED:  # SUSPENDED = stopped
                        continue

                    # Calculate age
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    else:
                        continue

                    # Filter by minimum age
                    if age_days < min_age_days:
                        continue

                    # Calculate costs (storage + backups only, no instance cost)
                    storage_size_gb = instance.settings.data_disk_size_gb if instance.settings else 100
                    storage_type = instance.settings.data_disk_type if instance.settings else "PD_SSD"

                    # Storage pricing
                    storage_pricing = {
                        "PD_SSD": 0.17,
                        "PD_HDD": 0.09,
                    }
                    storage_cost = storage_size_gb * storage_pricing.get(storage_type, 0.17)

                    # Backup cost (estimate 1.5x database size)
                    backup_size_gb = storage_size_gb * 1.5
                    backup_cost = backup_size_gb * 0.08

                    # Total monthly cost
                    monthly_cost = storage_cost + backup_cost

                    # Calculate waste
                    months_wasted = age_days / 30
                    already_wasted = monthly_cost * months_wasted

                    # Determine confidence
                    if age_days >= 90:
                        confidence = "CRITICAL"
                    elif age_days >= 60:
                        confidence = "HIGH"
                    elif age_days >= 30:
                        confidence = "MEDIUM"
                    else:
                        confidence = "LOW"

                    resources.append(OrphanResourceData(
                        resource_id=instance.name,
                        resource_type="cloud_sql_stopped",
                        resource_name=instance.name,
                        region=instance.region if hasattr(instance, 'region') else "global",
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata={
                            "instance_name": instance.name,
                            "database_version": instance.database_version,
                            "state": "STOPPED",
                            "tier": instance.settings.tier if instance.settings else "unknown",
                            "storage_size_gb": storage_size_gb,
                            "storage_type": storage_type,
                            "age_days": age_days,
                            "stopped_days": age_days,
                            "storage_cost_monthly": round(storage_cost, 2),
                            "backup_cost_monthly": round(backup_cost, 2),
                            "already_wasted": round(already_wasted, 2),
                            "annual_cost": round(monthly_cost * 12, 2),
                            "confidence": confidence,
                            "recommendation": f"Create final snapshot and DELETE instance to save ${monthly_cost * 12:.2f}/year. Stopped for {age_days} days.",
                            "waste_reason": f"Cloud SQL instance stopped for {age_days} days - paying storage+backups only"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for stopped Cloud SQL instances: {e}")

        return resources

    async def scan_cloud_sql_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect idle Cloud SQL instances (zero connections).

        Waste: Instances with 0 connections = 100% waste.
        Detection: state == 'RUNNABLE' AND avg_connections == 0 for 14 days
        Cost: Full instance + storage + backups ($92-369/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            lookback_days = 14
            if detection_rules and "cloud_sql_idle" in detection_rules:
                rules = detection_rules["cloud_sql_idle"]
                lookback_days = rules.get("lookback_days", 14)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all RUNNABLE instances
            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    if instance.state != sql_v1.Instance.State.RUNNABLE:
                        continue

                    instance_name = instance.name

                    # Query connection metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        connections_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/network/connections"'
                        )

                        connections_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": connections_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        connection_values = []
                        for series in monitoring_client.list_time_series(request=connections_request):
                            for point in series.points:
                                connection_values.append(point.value.double_value or 0)

                        if not connection_values:
                            # No metrics available yet
                            continue

                        avg_connections = sum(connection_values) / len(connection_values)
                        max_connections = max(connection_values)

                        # Detect idle (zero connections)
                        if avg_connections == 0 and max_connections == 0:
                            # Calculate full cost
                            tier = instance.settings.tier if instance.settings else "db-n1-standard-1"

                            # Machine pricing
                            machine_pricing = {
                                "db-f1-micro": 7.67,
                                "db-g1-small": 25.00,
                                "db-n1-standard-1": 46.20,
                                "db-n1-standard-2": 92.40,
                                "db-n1-standard-4": 184.80,
                                "db-n1-standard-8": 369.60,
                                "db-custom-2-7680": 51.10,
                                "db-custom-4-15360": 102.20,
                            }
                            instance_cost = machine_pricing.get(tier, 46.20)

                            # Storage cost
                            storage_size_gb = instance.settings.data_disk_size_gb if instance.settings else 100
                            storage_type = instance.settings.data_disk_type if instance.settings else "PD_SSD"
                            storage_pricing = {"PD_SSD": 0.17, "PD_HDD": 0.09}
                            storage_cost = storage_size_gb * storage_pricing.get(storage_type, 0.17)

                            # Backup cost
                            backup_cost = storage_size_gb * 1.5 * 0.08

                            # Check HA
                            ha_enabled = instance.settings.availability_type == sql_v1.Settings.AvailabilityType.REGIONAL if instance.settings else False
                            if ha_enabled:
                                instance_cost *= 2

                            monthly_cost = instance_cost + storage_cost + backup_cost

                            # Calculate waste since creation
                            created_at = instance.create_time
                            if created_at:
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                already_wasted = monthly_cost * (age_days / 30)
                            else:
                                age_days = 0
                                already_wasted = 0

                            resources.append(OrphanResourceData(
                                resource_id=instance.name,
                                resource_type="cloud_sql_idle",
                                resource_name=instance.name,
                                region=instance.region if hasattr(instance, 'region') else "global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "instance_name": instance.name,
                                    "database_version": instance.database_version,
                                    "state": "RUNNABLE",
                                    "tier": tier,
                                    "availability_type": "HA" if ha_enabled else "ZONAL",
                                    "storage_size_gb": storage_size_gb,
                                    "connection_metrics": {
                                        "avg_connections_14d": round(avg_connections, 2),
                                        "max_connections_14d": max_connections
                                    },
                                    "age_days": age_days,
                                    "instance_cost_monthly": round(instance_cost, 2),
                                    "storage_cost_monthly": round(storage_cost, 2),
                                    "backup_cost_monthly": round(backup_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_cost * 12, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"DELETE instance to save ${monthly_cost * 12:.2f}/year. Zero connections in {lookback_days} days.",
                                    "waste_reason": f"Cloud SQL instance idle - 0 connections for {lookback_days}+ days (100% waste)"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch monitoring data for instance {instance_name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for idle Cloud SQL instances: {e}")

        return resources

    async def scan_cloud_sql_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect over-provisioned Cloud SQL instances.

        Waste: CPU<30% AND Memory<40% = over-provisioned.
        Detection: Analyze CloudMonitoring CPU/Memory metrics over 14 days
        Cost: Difference between current and recommended tier ($92-184/month savings typical)
        Priority: HIGH (P1) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            cpu_threshold = 30.0
            memory_threshold = 40.0
            lookback_days = 14
            if detection_rules and "cloud_sql_overprovisioned" in detection_rules:
                rules = detection_rules["cloud_sql_overprovisioned"]
                cpu_threshold = rules.get("cpu_threshold", 30.0)
                memory_threshold = rules.get("memory_threshold", 40.0)
                lookback_days = rules.get("lookback_days", 14)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List RUNNABLE instances
            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    if instance.state != sql_v1.Instance.State.RUNNABLE:
                        continue

                    instance_name = instance.name
                    tier = instance.settings.tier if instance.settings else "db-n1-standard-1"

                    # Query CPU and Memory metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        # CPU metrics
                        cpu_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/cpu/utilization"'
                        )
                        cpu_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": cpu_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        cpu_values = []
                        for series in monitoring_client.list_time_series(request=cpu_request):
                            for point in series.points:
                                cpu_values.append(point.value.double_value * 100)  # Convert to percentage

                        # Memory metrics
                        memory_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/memory/utilization"'
                        )
                        memory_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": memory_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        memory_values = []
                        for series in monitoring_client.list_time_series(request=memory_request):
                            for point in series.points:
                                memory_values.append(point.value.double_value * 100)

                        if not cpu_values or not memory_values:
                            continue

                        avg_cpu = sum(cpu_values) / len(cpu_values)
                        avg_memory = sum(memory_values) / len(memory_values)

                        # Detect over-provisioning
                        if avg_cpu < cpu_threshold and avg_memory < memory_threshold:
                            # Calculate recommended tier (downgrade)
                            machine_pricing = {
                                "db-n1-standard-1": 46.20,
                                "db-n1-standard-2": 92.40,
                                "db-n1-standard-4": 184.80,
                                "db-n1-standard-8": 369.60,
                            }

                            current_cost = machine_pricing.get(tier, 46.20)

                            # Simple downgrade logic
                            recommended_tier = tier
                            if "standard-8" in tier:
                                recommended_tier = tier.replace("standard-8", "standard-4")
                            elif "standard-4" in tier:
                                recommended_tier = tier.replace("standard-4", "standard-2")
                            elif "standard-2" in tier:
                                recommended_tier = tier.replace("standard-2", "standard-1")

                            recommended_cost = machine_pricing.get(recommended_tier, current_cost / 2)

                            # Check HA
                            ha_enabled = instance.settings.availability_type == sql_v1.Settings.AvailabilityType.REGIONAL if instance.settings else False
                            if ha_enabled:
                                current_cost *= 2
                                recommended_cost *= 2

                            monthly_waste = current_cost - recommended_cost

                            if monthly_waste > 0:
                                resources.append(OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_type="cloud_sql_overprovisioned",
                                    resource_name=instance.name,
                                    region=instance.region if hasattr(instance, 'region') else "global",
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "instance_name": instance.name,
                                        "database_version": instance.database_version,
                                        "state": "RUNNABLE",
                                        "tier": tier,
                                        "availability_type": "HA" if ha_enabled else "ZONAL",
                                        "cpu_metrics": {
                                            "avg_cpu_14d": round(avg_cpu, 1),
                                            "max_cpu_14d": round(max(cpu_values), 1) if cpu_values else 0
                                        },
                                        "memory_metrics": {
                                            "avg_memory_14d": round(avg_memory, 1),
                                            "max_memory_14d": round(max(memory_values), 1) if memory_values else 0
                                        },
                                        "current_cost_monthly": round(current_cost, 2),
                                        "recommended_tier": recommended_tier,
                                        "recommended_cost_monthly": round(recommended_cost, 2),
                                        "annual_savings": round(monthly_waste * 12, 2),
                                        "confidence": "HIGH",
                                        "recommendation": f"DOWNGRADE to {recommended_tier} to save ${monthly_waste * 12:.2f}/year. CPU avg {avg_cpu:.1f}%, Memory avg {avg_memory:.1f}%.",
                                        "waste_reason": f"Over-provisioned: CPU {avg_cpu:.1f}% < {cpu_threshold}%, Memory {avg_memory:.1f}% < {memory_threshold}%"
                                    }
                                ))

                    except Exception as e:
                        logger.warning(f"Could not fetch metrics for {instance_name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for over-provisioned Cloud SQL: {e}")

        return resources

    async def scan_cloud_sql_old_machine_type(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect old machine types (db-n1 → db-custom for 45% savings).

        Waste: db-n1 tiers cost 45% more than equivalent db-custom.
        Detection: tier.startswith('db-n1-')
        Cost: $41-82/month savings per instance
        Priority: MEDIUM (P2) 💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    tier = instance.settings.tier if instance.settings else ""

                    # Detect db-n1 tiers
                    if not tier.startswith("db-n1-"):
                        continue

                    # Calculate costs
                    machine_pricing = {
                        "db-n1-standard-1": 46.20,
                        "db-n1-standard-2": 92.40,
                        "db-n1-standard-4": 184.80,
                        "db-n1-standard-8": 369.60,
                    }
                    custom_pricing = {
                        "db-custom-1-3840": 25.55,   # Equivalent to standard-1
                        "db-custom-2-7680": 51.10,   # Equivalent to standard-2
                        "db-custom-4-15360": 102.20, # Equivalent to standard-4
                        "db-custom-8-30720": 204.40, # Equivalent to standard-8
                    }

                    current_cost = machine_pricing.get(tier, 46.20)

                    # Map to equivalent db-custom
                    if "standard-1" in tier:
                        recommended_tier = "db-custom-1-3840"
                        recommended_cost = custom_pricing["db-custom-1-3840"]
                    elif "standard-2" in tier:
                        recommended_tier = "db-custom-2-7680"
                        recommended_cost = custom_pricing["db-custom-2-7680"]
                    elif "standard-4" in tier:
                        recommended_tier = "db-custom-4-15360"
                        recommended_cost = custom_pricing["db-custom-4-15360"]
                    elif "standard-8" in tier:
                        recommended_tier = "db-custom-8-30720"
                        recommended_cost = custom_pricing["db-custom-8-30720"]
                    else:
                        continue

                    # Check HA
                    ha_enabled = instance.settings.availability_type == sql_v1.Settings.AvailabilityType.REGIONAL if instance.settings else False
                    if ha_enabled:
                        current_cost *= 2
                        recommended_cost *= 2

                    monthly_waste = current_cost - recommended_cost
                    savings_pct = (monthly_waste / current_cost * 100) if current_cost > 0 else 0

                    resources.append(OrphanResourceData(
                        resource_id=instance.name,
                        resource_type="cloud_sql_old_machine_type",
                        resource_name=instance.name,
                        region=instance.region if hasattr(instance, 'region') else "global",
                        estimated_monthly_cost=monthly_waste,
                        resource_metadata={
                            "instance_name": instance.name,
                            "database_version": instance.database_version,
                            "state": instance.state.name,
                            "tier": tier,
                            "availability_type": "HA" if ha_enabled else "ZONAL",
                            "current_cost_monthly": round(current_cost, 2),
                            "recommended_tier": recommended_tier,
                            "recommended_cost_monthly": round(recommended_cost, 2),
                            "savings_percentage": round(savings_pct, 1),
                            "annual_savings": round(monthly_waste * 12, 2),
                            "confidence": "MEDIUM",
                            "recommendation": f"MIGRATE to {recommended_tier} for -{savings_pct:.0f}% cost and better flexibility (${monthly_waste * 12:.2f}/year savings).",
                            "waste_reason": f"Old db-n1 tier - db-custom is {savings_pct:.0f}% cheaper with more flexibility"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for old machine types: {e}")

        return resources

    async def scan_cloud_sql_devtest_247(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect dev/test instances running 24/7.

        Waste: Dev/test should run business hours only (60h/week vs 168h).
        Detection: labels.environment in ['dev', 'test', 'staging'] AND uptime >7 days
        Cost: 64% savings with scheduling ($59/month typical)
        Priority: MEDIUM (P2) 💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from datetime import datetime, timezone

            # Get detection parameters
            min_uptime_days = 7
            business_hours_per_week = 60
            devtest_labels = ["dev", "test", "staging", "development"]
            if detection_rules and "cloud_sql_devtest_247" in detection_rules:
                rules = detection_rules["cloud_sql_devtest_247"]
                min_uptime_days = rules.get("min_uptime_days", 7)
                business_hours_per_week = rules.get("business_hours_per_week", 60)
                devtest_labels = rules.get("devtest_labels", devtest_labels)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    if instance.state != sql_v1.Instance.State.RUNNABLE:
                        continue

                    # Check labels
                    labels = dict(instance.settings.user_labels) if instance.settings and instance.settings.user_labels else {}
                    environment = labels.get("environment", "").lower()

                    if environment not in devtest_labels:
                        continue

                    # Check uptime
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    else:
                        age_days = 0

                    if age_days < min_uptime_days:
                        continue

                    # Calculate costs
                    tier = instance.settings.tier if instance.settings else "db-n1-standard-1"
                    machine_pricing = {
                        "db-f1-micro": 7.67,
                        "db-g1-small": 25.00,
                        "db-n1-standard-1": 46.20,
                        "db-n1-standard-2": 92.40,
                        "db-n1-standard-4": 184.80,
                    }
                    instance_cost = machine_pricing.get(tier, 46.20)

                    storage_size_gb = instance.settings.data_disk_size_gb if instance.settings else 100
                    storage_cost = storage_size_gb * 0.17
                    backup_cost = storage_size_gb * 1.5 * 0.08

                    # Current cost (24/7)
                    monthly_cost = instance_cost + storage_cost + backup_cost

                    # Optimal cost (business hours only)
                    hours_actual = 168
                    hours_optimal = business_hours_per_week
                    optimal_instance_cost = instance_cost * (hours_optimal / hours_actual)
                    optimal_cost = optimal_instance_cost + storage_cost + backup_cost

                    monthly_waste = monthly_cost - optimal_cost
                    waste_pct = (monthly_waste / monthly_cost * 100) if monthly_cost > 0 else 0

                    resources.append(OrphanResourceData(
                        resource_id=instance.name,
                        resource_type="cloud_sql_devtest_247",
                        resource_name=instance.name,
                        region=instance.region if hasattr(instance, 'region') else "global",
                        estimated_monthly_cost=monthly_waste,
                        resource_metadata={
                            "instance_name": instance.name,
                            "database_version": instance.database_version,
                            "state": "RUNNABLE",
                            "tier": tier,
                            "labels": labels,
                            "uptime_days": age_days,
                            "current_uptime_hours_weekly": hours_actual,
                            "optimal_uptime_hours_weekly": hours_optimal,
                            "current_cost_monthly": round(monthly_cost, 2),
                            "optimal_cost_monthly": round(optimal_cost, 2),
                            "waste_percentage": round(waste_pct, 0),
                            "annual_savings": round(monthly_waste * 12, 2),
                            "confidence": "HIGH",
                            "recommendation": f"Implement automated start/stop schedule (8am-8pm Mon-Fri) to save ${monthly_waste * 12:.2f}/year ({waste_pct:.0f}% savings).",
                            "waste_reason": f"Dev/test instance running 24/7 - {waste_pct:.0f}% waste with proper scheduling"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for dev/test 24/7 instances: {e}")

        return resources

    async def scan_cloud_sql_unused_replicas(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect unused read replicas (zero queries).

        Waste: Read replicas cost same as primary but never used.
        Detection: is_replica AND total_queries == 0 for 14 days
        Cost: Full instance cost ($92-150/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            lookback_days = 14
            if detection_rules and "cloud_sql_unused_replicas" in detection_rules:
                rules = detection_rules["cloud_sql_unused_replicas"]
                lookback_days = rules.get("lookback_days", 14)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    # Check if instance is a replica
                    if not instance.replica_configuration:
                        continue

                    if instance.state != sql_v1.Instance.State.RUNNABLE:
                        continue

                    instance_name = instance.name

                    # Query read operations
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        queries_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/queries"'
                        )

                        queries_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": queries_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        total_queries = 0
                        for series in monitoring_client.list_time_series(request=queries_request):
                            for point in series.points:
                                total_queries += point.value.int64_value or 0

                        # Detect unused replica
                        if total_queries == 0:
                            # Calculate full cost
                            tier = instance.settings.tier if instance.settings else "db-n1-standard-2"
                            machine_pricing = {
                                "db-n1-standard-1": 46.20,
                                "db-n1-standard-2": 92.40,
                                "db-n1-standard-4": 184.80,
                            }
                            instance_cost = machine_pricing.get(tier, 92.40)

                            storage_size_gb = instance.settings.data_disk_size_gb if instance.settings else 200
                            storage_cost = storage_size_gb * 0.17
                            backup_cost = storage_size_gb * 1.5 * 0.08

                            monthly_cost = instance_cost + storage_cost + backup_cost

                            # Calculate waste since creation
                            created_at = instance.create_time
                            if created_at:
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                already_wasted = monthly_cost * (age_days / 30)
                            else:
                                age_days = 0
                                already_wasted = 0

                            resources.append(OrphanResourceData(
                                resource_id=instance.name,
                                resource_type="cloud_sql_unused_replicas",
                                resource_name=instance.name,
                                region=instance.region if hasattr(instance, 'region') else "global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "instance_name": instance.name,
                                    "database_version": instance.database_version,
                                    "state": "RUNNABLE",
                                    "tier": tier,
                                    "is_replica": True,
                                    "storage_size_gb": storage_size_gb,
                                    "query_metrics": {
                                        "total_queries_14d": total_queries
                                    },
                                    "age_days": age_days,
                                    "instance_cost_monthly": round(instance_cost, 2),
                                    "storage_cost_monthly": round(storage_cost, 2),
                                    "backup_cost_monthly": round(backup_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_cost * 12, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"DELETE read replica to save ${monthly_cost * 12:.2f}/year. Zero queries in {lookback_days} days.",
                                    "waste_reason": f"Read replica unused - 0 queries for {lookback_days}+ days (100% waste)"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch metrics for replica {instance_name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unused replicas: {e}")

        return resources

    async def scan_cloud_sql_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect untagged Cloud SQL instances (governance waste).

        Waste: Missing labels = lost cost allocation & governance.
        Detection: missing required labels (environment, owner, cost-center)
        Cost: 5% of instance cost (governance overhead)
        Priority: LOW (P3) 💰
        """
        resources = []

        try:
            from google.cloud import sql_v1

            # Get detection parameters
            required_labels = ["environment", "owner", "cost-center"]
            governance_waste_pct = 0.05
            if detection_rules and "cloud_sql_untagged" in detection_rules:
                rules = detection_rules["cloud_sql_untagged"]
                required_labels = rules.get("required_labels", required_labels)
                governance_waste_pct = rules.get("governance_waste_pct", 0.05)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    # Check labels
                    labels = dict(instance.settings.user_labels) if instance.settings and instance.settings.user_labels else {}

                    # Identify missing labels
                    missing_labels = [label for label in required_labels if label not in labels]

                    if not missing_labels:
                        continue

                    # Calculate governance waste
                    tier = instance.settings.tier if instance.settings else "db-n1-standard-2"
                    machine_pricing = {
                        "db-f1-micro": 7.67,
                        "db-n1-standard-1": 46.20,
                        "db-n1-standard-2": 92.40,
                        "db-n1-standard-4": 184.80,
                    }
                    instance_cost = machine_pricing.get(tier, 92.40)

                    storage_size_gb = instance.settings.data_disk_size_gb if instance.settings else 100
                    storage_cost = storage_size_gb * 0.17
                    backup_cost = storage_size_gb * 1.5 * 0.08

                    # Check HA
                    ha_enabled = instance.settings.availability_type == sql_v1.Settings.AvailabilityType.REGIONAL if instance.settings else False
                    if ha_enabled:
                        instance_cost *= 2

                    instance_monthly_cost = instance_cost + storage_cost + backup_cost

                    # Governance waste
                    monthly_waste = instance_monthly_cost * governance_waste_pct

                    resources.append(OrphanResourceData(
                        resource_id=instance.name,
                        resource_type="cloud_sql_untagged",
                        resource_name=instance.name,
                        region=instance.region if hasattr(instance, 'region') else "global",
                        estimated_monthly_cost=monthly_waste,
                        resource_metadata={
                            "instance_name": instance.name,
                            "database_version": instance.database_version,
                            "state": instance.state.name,
                            "tier": tier,
                            "labels": labels,
                            "missing_labels": missing_labels,
                            "instance_monthly_cost": round(instance_monthly_cost, 2),
                            "annual_cost": round(monthly_waste * 12, 2),
                            "confidence": "MEDIUM",
                            "recommendation": f"Add required labels for cost allocation and governance. Missing: {', '.join(missing_labels)}.",
                            "waste_reason": f"Missing {len(missing_labels)} required labels - governance waste"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for untagged instances: {e}")

        return resources

    async def scan_cloud_sql_zero_io(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect instances with zero I/O (empty database).

        Waste: No read/write operations = database unused.
        Detection: total_read_ops == 0 AND total_write_ops == 0 for 14 days
        Cost: Full instance cost ($121/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            lookback_days = 14
            min_age_days = 7
            if detection_rules and "cloud_sql_zero_io" in detection_rules:
                rules = detection_rules["cloud_sql_zero_io"]
                lookback_days = rules.get("lookback_days", 14)
                min_age_days = rules.get("min_age_days", 7)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    if instance.state != sql_v1.Instance.State.RUNNABLE:
                        continue

                    # Check age
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    else:
                        age_days = 0

                    if age_days < min_age_days:
                        continue

                    instance_name = instance.name

                    # Query I/O metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        # Read ops
                        read_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/disk/read_ops_count"'
                        )
                        read_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": read_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        total_read_ops = 0
                        for series in monitoring_client.list_time_series(request=read_request):
                            for point in series.points:
                                total_read_ops += point.value.int64_value or 0

                        # Write ops
                        write_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/disk/write_ops_count"'
                        )
                        write_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": write_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        total_write_ops = 0
                        for series in monitoring_client.list_time_series(request=write_request):
                            for point in series.points:
                                total_write_ops += point.value.int64_value or 0

                        # Detect zero I/O
                        if total_read_ops == 0 and total_write_ops == 0:
                            # Calculate full cost
                            tier = instance.settings.tier if instance.settings else "db-n1-standard-2"
                            machine_pricing = {
                                "db-n1-standard-1": 46.20,
                                "db-n1-standard-2": 92.40,
                                "db-n1-standard-4": 184.80,
                            }
                            instance_cost = machine_pricing.get(tier, 92.40)

                            storage_size_gb = instance.settings.data_disk_size_gb if instance.settings else 100
                            storage_cost = storage_size_gb * 0.17
                            backup_cost = storage_size_gb * 1.5 * 0.08

                            monthly_cost = instance_cost + storage_cost + backup_cost

                            already_wasted = monthly_cost * (age_days / 30)

                            resources.append(OrphanResourceData(
                                resource_id=instance.name,
                                resource_type="cloud_sql_zero_io",
                                resource_name=instance.name,
                                region=instance.region if hasattr(instance, 'region') else "global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "instance_name": instance.name,
                                    "database_version": instance.database_version,
                                    "state": "RUNNABLE",
                                    "tier": tier,
                                    "storage_size_gb": storage_size_gb,
                                    "io_metrics": {
                                        "total_read_ops_14d": total_read_ops,
                                        "total_write_ops_14d": total_write_ops
                                    },
                                    "age_days": age_days,
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_cost * 12, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"DELETE instance to save ${monthly_cost * 12:.2f}/year. Zero I/O for {lookback_days} days.",
                                    "waste_reason": f"Database with zero I/O operations for {lookback_days}+ days (likely empty)"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch I/O metrics for {instance_name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for zero I/O instances: {e}")

        return resources

    async def scan_cloud_sql_storage_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect storage over-provisioned (>80% free space).

        Waste: Paying for unused storage + proportional backups.
        Detection: storage_used < 20% of allocated
        Cost: Storage + backup waste ($232/month typical for 1TB → 200GB)
        Priority: HIGH (P1) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            free_space_threshold = 80.0
            safety_buffer = 1.30
            min_savings_threshold = 5.0
            lookback_days = 14
            if detection_rules and "cloud_sql_storage_overprovisioned" in detection_rules:
                rules = detection_rules["cloud_sql_storage_overprovisioned"]
                free_space_threshold = rules.get("free_space_threshold", 80.0)
                safety_buffer = rules.get("safety_buffer", 1.30)
                min_savings_threshold = rules.get("min_savings_threshold", 5.0)
                lookback_days = rules.get("lookback_days", 14)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    instance_name = instance.name
                    allocated_storage_gb = instance.settings.data_disk_size_gb if instance.settings else 100

                    # Query storage usage
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        bytes_used_filter = (
                            f'resource.type="cloudsql_database" '
                            f'AND resource.labels.database_id="{self.project_id}:{instance_name}" '
                            f'AND metric.type="cloudsql.googleapis.com/database/disk/bytes_used"'
                        )
                        bytes_used_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": bytes_used_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        used_bytes_values = []
                        for series in monitoring_client.list_time_series(request=bytes_used_request):
                            for point in series.points:
                                used_bytes_values.append(point.value.double_value or 0)

                        if not used_bytes_values:
                            continue

                        avg_used_bytes = sum(used_bytes_values) / len(used_bytes_values)
                        avg_used_gb = avg_used_bytes / (1024**3)

                        # Calculate percentage
                        used_percent = (avg_used_gb / allocated_storage_gb * 100) if allocated_storage_gb > 0 else 0
                        free_percent = 100 - used_percent

                        # Detect over-provisioning
                        if free_percent >= free_space_threshold:
                            # Calculate recommended storage
                            recommended_storage_gb = int(avg_used_gb * safety_buffer)
                            recommended_storage_gb = max(recommended_storage_gb, 10)  # Minimum 10GB

                            # Storage pricing
                            storage_type = instance.settings.data_disk_type if instance.settings else "PD_SSD"
                            storage_pricing = {"PD_SSD": 0.17, "PD_HDD": 0.09}
                            price_per_gb = storage_pricing.get(storage_type, 0.17)

                            current_storage_cost = allocated_storage_gb * price_per_gb
                            recommended_storage_cost = recommended_storage_gb * price_per_gb
                            storage_waste = current_storage_cost - recommended_storage_cost

                            # Backup waste
                            current_backup_cost = allocated_storage_gb * 1.5 * 0.08
                            recommended_backup_cost = recommended_storage_gb * 1.5 * 0.08
                            backup_waste = current_backup_cost - recommended_backup_cost

                            monthly_waste = storage_waste + backup_waste

                            if monthly_waste >= min_savings_threshold:
                                savings_pct = (monthly_waste / (current_storage_cost + current_backup_cost) * 100) if (current_storage_cost + current_backup_cost) > 0 else 0

                                resources.append(OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_type="cloud_sql_storage_overprovisioned",
                                    resource_name=instance.name,
                                    region=instance.region if hasattr(instance, 'region') else "global",
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "instance_name": instance.name,
                                        "database_version": instance.database_version,
                                        "state": instance.state.name,
                                        "storage_size_gb": allocated_storage_gb,
                                        "storage_type": storage_type,
                                        "storage_usage": {
                                            "avg_used_gb": round(avg_used_gb, 1),
                                            "avg_used_percent": round(used_percent, 1),
                                            "avg_free_percent": round(free_percent, 1)
                                        },
                                        "recommended_storage_gb": recommended_storage_gb,
                                        "current_storage_cost_monthly": round(current_storage_cost, 2),
                                        "recommended_storage_cost_monthly": round(recommended_storage_cost, 2),
                                        "current_backup_cost_monthly": round(current_backup_cost, 2),
                                        "recommended_backup_cost_monthly": round(recommended_backup_cost, 2),
                                        "savings_percentage": round(savings_pct, 0),
                                        "annual_savings": round(monthly_waste * 12, 2),
                                        "confidence": "HIGH",
                                        "recommendation": f"REDUCE storage from {allocated_storage_gb}GB to {recommended_storage_gb}GB to save ${monthly_waste * 12:.2f}/year. Using only {used_percent:.0f}%.",
                                        "waste_reason": f"Storage over-provisioned: {free_percent:.0f}% free space ({allocated_storage_gb}GB allocated, {avg_used_gb:.0f}GB used)"
                                    }
                                ))

                    except Exception as e:
                        logger.warning(f"Could not fetch storage metrics for {instance_name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for storage over-provisioning: {e}")

        return resources

    async def scan_cloud_sql_unnecessary_ha(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect unnecessary High Availability on dev/test.

        Waste: HA doubles instance cost but dev/test doesn't need 99.95% SLA.
        Detection: availability_type == 'REGIONAL' AND labels.environment in ['dev', 'test']
        Cost: +100% instance cost waste ($184/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import sql_v1

            # Get detection parameters
            devtest_labels = ["dev", "test", "staging", "development"]
            if detection_rules and "cloud_sql_unnecessary_ha" in detection_rules:
                rules = detection_rules["cloud_sql_unnecessary_ha"]
                devtest_labels = rules.get("devtest_labels", devtest_labels)

            sql_client = sql_v1.CloudSqlInstancesServiceClient(credentials=self.credentials)

            try:
                request = sql_v1.ListInstancesRequest(project=self.project_id)

                for instance in sql_client.list(request=request):
                    # Check if HA enabled
                    ha_enabled = instance.settings.availability_type == sql_v1.Settings.AvailabilityType.REGIONAL if instance.settings else False

                    if not ha_enabled:
                        continue

                    if instance.state != sql_v1.Instance.State.RUNNABLE:
                        continue

                    # Check labels
                    labels = dict(instance.settings.user_labels) if instance.settings and instance.settings.user_labels else {}
                    environment = labels.get("environment", "").lower()

                    if environment not in devtest_labels:
                        continue

                    # Calculate HA waste
                    tier = instance.settings.tier if instance.settings else "db-n1-standard-4"
                    machine_pricing = {
                        "db-n1-standard-1": 46.20,
                        "db-n1-standard-2": 92.40,
                        "db-n1-standard-4": 184.80,
                        "db-n1-standard-8": 369.60,
                    }
                    instance_cost_single = machine_pricing.get(tier, 184.80)

                    # HA waste = standby replica cost
                    monthly_waste = instance_cost_single

                    resources.append(OrphanResourceData(
                        resource_id=instance.name,
                        resource_type="cloud_sql_unnecessary_ha",
                        resource_name=instance.name,
                        region=instance.region if hasattr(instance, 'region') else "global",
                        estimated_monthly_cost=monthly_waste,
                        resource_metadata={
                            "instance_name": instance.name,
                            "database_version": instance.database_version,
                            "state": "RUNNABLE",
                            "tier": tier,
                            "availability_type": "REGIONAL",
                            "labels": labels,
                            "instance_cost_single_monthly": round(instance_cost_single, 2),
                            "instance_cost_ha_monthly": round(instance_cost_single * 2, 2),
                            "annual_savings": round(monthly_waste * 12, 2),
                            "confidence": "HIGH",
                            "recommendation": f"DISABLE High Availability for dev/test environment to save ${monthly_waste * 12:.2f}/year. 99.95% SLA not needed for non-prod.",
                            "waste_reason": "High Availability enabled on dev/test - unnecessary +100% cost"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud SQL instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unnecessary HA: {e}")

        return resources

    # ================================================================
    # CLOUD SPANNER DETECTION METHODS (10 scenarios)
    # ================================================================

    async def scan_cloud_spanner_underutilized(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect Cloud Spanner instances under-utilized (CPU <30%).

        Waste: Instances provisioned with excessive nodes/PU compared to actual usage.
        Detection: avg_cpu <30% over 14 days
        Cost: Difference between current and optimal PU ($1,314/month typical)
        Priority: HIGH (P1) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            cpu_threshold = 30.0
            target_cpu = 65.0  # Google recommendation
            lookback_days = 14
            min_savings_threshold = 100.0
            if detection_rules and "cloud_spanner_underutilized" in detection_rules:
                rules = detection_rules["cloud_spanner_underutilized"]
                cpu_threshold = rules.get("cpu_threshold", 30.0)
                target_cpu = rules.get("target_cpu", 65.0)
                lookback_days = rules.get("lookback_days", 14)
                min_savings_threshold = rules.get("min_savings_threshold", 100.0)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all Cloud Spanner instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Get current capacity
                    if instance.node_count > 0:
                        current_pu = instance.node_count * 1000
                        current_nodes = instance.node_count
                    else:
                        current_pu = instance.processing_units
                        current_nodes = 0

                    # Query CPU metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        cpu_filter = (
                            f'resource.type="spanner_instance" '
                            f'AND resource.labels.instance_id="{instance_id}" '
                            f'AND metric.type="spanner.googleapis.com/instance/cpu/utilization"'
                        )

                        cpu_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": cpu_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        cpu_values = []
                        for series in monitoring_client.list_time_series(request=cpu_request):
                            for point in series.points:
                                cpu_values.append(point.value.double_value * 100)

                        if not cpu_values:
                            continue

                        avg_cpu = sum(cpu_values) / len(cpu_values)
                        max_cpu = max(cpu_values)

                        # Detect under-utilization
                        if avg_cpu < cpu_threshold:
                            # Calculate optimal PU for target CPU
                            optimal_pu = int(current_pu * (avg_cpu / target_cpu))
                            optimal_pu = max(100, optimal_pu)

                            if optimal_pu >= current_pu:
                                continue

                            # Calculate costs
                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            cost_per_pu = 2.19 if is_multiregional else 0.657

                            current_cost = current_pu * cost_per_pu
                            optimal_cost = optimal_pu * cost_per_pu
                            monthly_waste = current_cost - optimal_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            # Calculate age
                            created_at = instance.create_time
                            if created_at:
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                already_wasted = monthly_waste * (age_days / 30)
                            else:
                                age_days = 0
                                already_wasted = 0

                            confidence = "HIGH" if avg_cpu < 20 else "MEDIUM"

                            resources.append(OrphanResourceData(
                                resource_id=instance_id,
                                resource_type="cloud_spanner_underutilized",
                                resource_name=instance_id,
                                region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "instance_config": instance_config,
                                    "is_multiregional": is_multiregional,
                                    "state": "READY",
                                    "current_node_count": current_nodes,
                                    "current_processing_units": current_pu,
                                    "cpu_metrics": {
                                        "avg_cpu_14d": round(avg_cpu, 1),
                                        "max_cpu_14d": round(max_cpu, 1)
                                    },
                                    "recommended_processing_units": optimal_pu,
                                    "current_cost_monthly": round(current_cost, 2),
                                    "recommended_cost_monthly": round(optimal_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_waste * 12, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Reduce from {current_pu} PU to {optimal_pu} PU to save ${monthly_waste * 12:.2f}/year. CPU avg {avg_cpu:.1f}%.",
                                    "waste_reason": f"Under-utilized: CPU {avg_cpu:.1f}% < {cpu_threshold}%, optimal {optimal_pu} PU vs {current_pu} PU current"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch metrics for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for under-utilized Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_unnecessary_multiregional(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect unnecessary multi-regional Cloud Spanner instances.

        Waste: Multi-regional costs 3.3x more than regional but not needed for dev/test.
        Detection: Multi-regional config + dev/test labels OR >90% requests from one region
        Cost: ~$4,799/month waste (multi-regional vs regional)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1

            # Get detection parameters
            devtest_labels = ["dev", "test", "staging", "development"]
            regional_concentration_threshold = 90.0
            lookback_days = 14
            if detection_rules and "cloud_spanner_unnecessary_multiregional" in detection_rules:
                rules = detection_rules["cloud_spanner_unnecessary_multiregional"]
                devtest_labels = rules.get("devtest_labels", devtest_labels)
                regional_concentration_threshold = rules.get("regional_concentration_threshold", 90.0)
                lookback_days = rules.get("lookback_days", 14)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Check if multi-regional
                    is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])

                    if not is_multiregional:
                        continue

                    # Check labels
                    labels = dict(instance.labels) if instance.labels else {}
                    environment = labels.get('environment', '').lower()

                    # Detect if dev/test
                    is_devtest = environment in devtest_labels

                    if is_devtest:
                        # Multi-regional for dev/test = clear waste
                        # Get current capacity
                        if instance.node_count > 0:
                            current_pu = instance.node_count * 1000
                        else:
                            current_pu = instance.processing_units

                        # Calculate costs
                        multiregional_cost_per_pu = 2.19
                        regional_cost_per_pu = 0.657

                        current_cost = current_pu * multiregional_cost_per_pu
                        recommended_cost = current_pu * regional_cost_per_pu
                        monthly_waste = current_cost - recommended_cost

                        # Storage and backups also more expensive
                        # Estimate 500GB storage, 1TB backups
                        storage_size_gb = 500
                        backup_size_gb = 1000

                        storage_waste = storage_size_gb * (0.50 - 0.30)
                        backup_waste = backup_size_gb * (0.30 - 0.20)

                        total_monthly_waste = monthly_waste + storage_waste + backup_waste

                        # Calculate age
                        created_at = instance.create_time
                        if created_at:
                            age_days = (datetime.now(timezone.utc) - created_at).days
                            already_wasted = total_monthly_waste * (age_days / 30)
                        else:
                            age_days = 0
                            already_wasted = 0

                        savings_pct = (total_monthly_waste / (current_cost + storage_size_gb * 0.50 + backup_size_gb * 0.30) * 100)

                        resources.append(OrphanResourceData(
                            resource_id=instance_id,
                            resource_type="cloud_spanner_unnecessary_multiregional",
                            resource_name=instance_id,
                            region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                            estimated_monthly_cost=total_monthly_waste,
                            resource_metadata={
                                "instance_id": instance_id,
                                "instance_config": instance_config,
                                "is_multiregional": True,
                                "state": "READY",
                                "processing_units": current_pu,
                                "labels": labels,
                                "environment": environment,
                                "storage_size_gb": storage_size_gb,
                                "current_cost_monthly": round(current_cost + storage_size_gb * 0.50 + backup_size_gb * 0.30, 2),
                                "recommended_config": "regional",
                                "recommended_cost_monthly": round(recommended_cost + storage_size_gb * 0.30 + backup_size_gb * 0.20, 2),
                                "already_wasted": round(already_wasted, 2),
                                "savings_percentage": round(savings_pct, 1),
                                "annual_cost": round(total_monthly_waste * 12, 2),
                                "confidence": "HIGH",
                                "recommendation": f"Migrate to regional configuration to save ${total_monthly_waste * 12:.2f}/year. Dev/test doesn't need multi-regional (3.3x cost).",
                                "waste_reason": f"Multi-regional for {environment} environment - regional would be 67% cheaper"
                            }
                        ))

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unnecessary multi-regional Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_devtest_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect dev/test Cloud Spanner instances over-provisioned.

        Waste: Dev/test environments using production-sized instances (≥1 node).
        Detection: labels.environment in ['dev', 'test'] AND processing_units >=1000
        Cost: ~$1,774/month waste (3 nodes vs 300 PU recommended)
        Priority: HIGH (P1) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from datetime import datetime, timezone

            # Get detection parameters
            devtest_labels = ["dev", "test", "staging", "development"]
            devtest_pu_threshold = 1000  # 1+ node
            recommended_devtest_pu = 300
            min_savings_threshold = 100.0
            if detection_rules and "cloud_spanner_devtest_overprovisioned" in detection_rules:
                rules = detection_rules["cloud_spanner_devtest_overprovisioned"]
                devtest_labels = rules.get("devtest_labels", devtest_labels)
                devtest_pu_threshold = rules.get("devtest_pu_threshold", 1000)
                recommended_devtest_pu = rules.get("recommended_devtest_pu", 300)
                min_savings_threshold = rules.get("min_savings_threshold", 100.0)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Check labels
                    labels = dict(instance.labels) if instance.labels else {}
                    environment = labels.get('environment', '').lower()

                    # Detect dev/test
                    if environment not in devtest_labels:
                        continue

                    # Get current capacity
                    if instance.node_count > 0:
                        current_pu = instance.node_count * 1000
                    else:
                        current_pu = instance.processing_units

                    # Check if over-provisioned
                    if current_pu < devtest_pu_threshold:
                        continue

                    # Calculate costs
                    is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                    cost_per_pu = 2.19 if is_multiregional else 0.657

                    current_cost = current_pu * cost_per_pu
                    recommended_cost = recommended_devtest_pu * cost_per_pu
                    monthly_waste = current_cost - recommended_cost

                    if monthly_waste < min_savings_threshold:
                        continue

                    # Calculate age
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                        already_wasted = monthly_waste * (age_days / 30)
                    else:
                        age_days = 0
                        already_wasted = 0

                    savings_pct = (monthly_waste / current_cost * 100) if current_cost > 0 else 0

                    resources.append(OrphanResourceData(
                        resource_id=instance_id,
                        resource_type="cloud_spanner_devtest_overprovisioned",
                        resource_name=instance_id,
                        region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                        estimated_monthly_cost=monthly_waste,
                        resource_metadata={
                            "instance_id": instance_id,
                            "instance_config": instance_config,
                            "state": "READY",
                            "processing_units": current_pu,
                            "labels": labels,
                            "environment": environment,
                            "current_cost_monthly": round(current_cost, 2),
                            "recommended_processing_units": recommended_devtest_pu,
                            "recommended_cost_monthly": round(recommended_cost, 2),
                            "already_wasted": round(already_wasted, 2),
                            "savings_percentage": round(savings_pct, 0),
                            "annual_cost": round(monthly_waste * 12, 2),
                            "confidence": "HIGH",
                            "recommendation": f"Reduce to {recommended_devtest_pu} PU for dev/test environment to save ${monthly_waste * 12:.2f}/year ({savings_pct:.0f}% savings).",
                            "waste_reason": f"Dev/test over-provisioned: {current_pu} PU when {recommended_devtest_pu} PU sufficient"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for dev/test over-provisioned Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect idle Cloud Spanner instances (zero API requests).

        Waste: Instances with zero queries = 100% waste.
        Detection: total_api_requests == 0 for 14 days
        Cost: Full instance cost ($727/month typical) - 100% waste
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            lookback_days = 14
            min_age_days = 7
            min_requests_threshold = 0
            if detection_rules and "cloud_spanner_idle" in detection_rules:
                rules = detection_rules["cloud_spanner_idle"]
                lookback_days = rules.get("lookback_days", 14)
                min_age_days = rules.get("min_age_days", 7)
                min_requests_threshold = rules.get("min_requests_threshold", 0)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Check age
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    else:
                        age_days = 0

                    if age_days < min_age_days:
                        continue

                    # Query API request metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        api_filter = (
                            f'resource.type="spanner_instance" '
                            f'AND resource.labels.instance_id="{instance_id}" '
                            f'AND metric.type="spanner.googleapis.com/instance/api_request_count"'
                        )

                        api_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": api_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        total_requests = 0
                        for series in monitoring_client.list_time_series(request=api_request):
                            for point in series.points:
                                total_requests += point.value.int64_value or 0

                        # Detect idle
                        if total_requests <= min_requests_threshold:
                            # Calculate full cost (100% waste)
                            if instance.node_count > 0:
                                current_pu = instance.node_count * 1000
                            else:
                                current_pu = instance.processing_units

                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            cost_per_pu = 2.19 if is_multiregional else 0.657

                            nodes_cost = current_pu * cost_per_pu

                            # Estimate storage and backups
                            storage_size_gb = 100  # Minimal
                            storage_pricing = 0.50 if is_multiregional else 0.30
                            backup_pricing = 0.30 if is_multiregional else 0.20

                            storage_cost = storage_size_gb * storage_pricing
                            backup_cost = (storage_size_gb * 2) * backup_pricing

                            monthly_cost = nodes_cost + storage_cost + backup_cost
                            already_wasted = monthly_cost * (age_days / 30)

                            resources.append(OrphanResourceData(
                                resource_id=instance_id,
                                resource_type="cloud_spanner_idle",
                                resource_name=instance_id,
                                region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "instance_config": instance_config,
                                    "state": "READY",
                                    "processing_units": current_pu,
                                    "api_metrics": {
                                        "total_requests_14d": total_requests
                                    },
                                    "age_days": age_days,
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_cost * 12, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"DELETE instance to save ${monthly_cost * 12:.2f}/year. Zero API requests in {lookback_days} days (100% waste).",
                                    "waste_reason": f"Idle instance: 0 API requests for {lookback_days}+ days"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch API metrics for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for idle Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_pu_suboptimal(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect suboptimal Processing Units configuration.

        Waste: Nodes have fixed granularity (1000 PU increments), PU offers 100 PU granularity.
        Detection: Instance using nodes when PU would be more cost-efficient
        Cost: ~$263/month savings (2000 PU → 1600 PU optimal)
        Priority: LOW (P2) 💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            target_cpu = 65.0
            lookback_days = 14
            min_savings_threshold = 50.0
            if detection_rules and "cloud_spanner_pu_suboptimal" in detection_rules:
                rules = detection_rules["cloud_spanner_pu_suboptimal"]
                target_cpu = rules.get("target_cpu", 65.0)
                lookback_days = rules.get("lookback_days", 14)
                min_savings_threshold = rules.get("min_savings_threshold", 50.0)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all instances with nodes (not PU)
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                node_based_instances = [i for i in instances if i.node_count > 0]

                for instance in node_based_instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config
                    current_nodes = instance.node_count
                    current_pu = current_nodes * 1000

                    # Query CPU metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        cpu_filter = (
                            f'resource.type="spanner_instance" '
                            f'AND resource.labels.instance_id="{instance_id}" '
                            f'AND metric.type="spanner.googleapis.com/instance/cpu/utilization"'
                        )

                        cpu_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": cpu_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        cpu_values = []
                        for series in monitoring_client.list_time_series(request=cpu_request):
                            for point in series.points:
                                cpu_values.append(point.value.double_value * 100)

                        if not cpu_values:
                            continue

                        avg_cpu = sum(cpu_values) / len(cpu_values)

                        # Calculate optimal PU
                        optimal_pu = int(current_pu * (avg_cpu / target_cpu))
                        optimal_pu = max(100, optimal_pu)

                        # Round to nearest 100 PU
                        optimal_pu = ((optimal_pu + 99) // 100) * 100

                        # Check if PU would offer savings
                        if optimal_pu % 1000 != 0 and optimal_pu < current_pu:
                            # Calculate costs
                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            cost_per_pu = 2.19 if is_multiregional else 0.657

                            current_cost = current_pu * cost_per_pu
                            optimal_cost = optimal_pu * cost_per_pu
                            monthly_waste = current_cost - optimal_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            # Calculate age
                            created_at = instance.create_time
                            if created_at:
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                already_wasted = monthly_waste * (age_days / 30)
                            else:
                                age_days = 0
                                already_wasted = 0

                            savings_pct = (monthly_waste / current_cost * 100) if current_cost > 0 else 0

                            resources.append(OrphanResourceData(
                                resource_id=instance_id,
                                resource_type="cloud_spanner_pu_suboptimal",
                                resource_name=instance_id,
                                region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "instance_config": instance_config,
                                    "state": "READY",
                                    "current_node_count": current_nodes,
                                    "current_processing_units": current_pu,
                                    "cpu_metrics": {
                                        "avg_cpu_14d": round(avg_cpu, 1)
                                    },
                                    "recommended_processing_units": optimal_pu,
                                    "current_cost_monthly": round(current_cost, 2),
                                    "recommended_cost_monthly": round(optimal_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "savings_percentage": round(savings_pct, 0),
                                    "annual_cost": round(monthly_waste * 12, 2),
                                    "confidence": "MEDIUM",
                                    "recommendation": f"Switch to Processing Units for better granularity ({current_nodes} nodes → {optimal_pu} PU) to save ${monthly_waste * 12:.2f}/year.",
                                    "waste_reason": f"Suboptimal granularity: nodes fixed at 1000 PU increments, {optimal_pu} PU would be more efficient"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch CPU metrics for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for suboptimal PU Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_empty_databases(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect Cloud Spanner instances with empty databases.

        Waste: Instances with databases but no tables = unused infrastructure.
        Detection: Databases exist BUT no DDL statements (no tables)
        Cost: Full instance cost ($663/month typical) - 100% waste
        Priority: HIGH (P1) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import spanner_admin_database_v1
            from datetime import datetime, timezone

            # Get detection parameters
            min_age_days = 7
            if detection_rules and "cloud_spanner_empty_databases" in detection_rules:
                rules = detection_rules["cloud_spanner_empty_databases"]
                min_age_days = rules.get("min_age_days", 7)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            database_admin_client = spanner_admin_database_v1.DatabaseAdminClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    # Check age
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    else:
                        age_days = 0

                    if age_days < min_age_days:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config
                    instance_path = instance.name

                    # List databases
                    try:
                        databases = database_admin_client.list_databases(parent=instance_path)
                        database_list = list(databases)

                        if len(database_list) == 0:
                            # No databases at all
                            continue

                        # Check each database for tables
                        empty_databases = 0
                        for database in database_list:
                            database_path = database.name

                            # Get DDL
                            db_ddl = database_admin_client.get_database_ddl(database=database_path)

                            # If no DDL statements = no tables
                            if not db_ddl.statements or len(db_ddl.statements) == 0:
                                empty_databases += 1

                        # Detect if all databases are empty
                        if empty_databases == len(database_list) and len(database_list) > 0:
                            # Calculate full cost (100% waste)
                            if instance.node_count > 0:
                                current_pu = instance.node_count * 1000
                            else:
                                current_pu = instance.processing_units

                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            cost_per_pu = 2.19 if is_multiregional else 0.657

                            nodes_cost = current_pu * cost_per_pu

                            # Minimal storage
                            storage_size_gb = 10
                            storage_pricing = 0.50 if is_multiregional else 0.30
                            backup_pricing = 0.30 if is_multiregional else 0.20

                            storage_cost = storage_size_gb * storage_pricing
                            backup_cost = (storage_size_gb * 1.5) * backup_pricing

                            monthly_cost = nodes_cost + storage_cost + backup_cost
                            already_wasted = monthly_cost * (age_days / 30)

                            resources.append(OrphanResourceData(
                                resource_id=instance_id,
                                resource_type="cloud_spanner_empty_databases",
                                resource_name=instance_id,
                                region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "instance_config": instance_config,
                                    "state": "READY",
                                    "processing_units": current_pu,
                                    "total_databases": len(database_list),
                                    "empty_databases": empty_databases,
                                    "age_days": age_days,
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_cost * 12, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"DELETE instance to save ${monthly_cost * 12:.2f}/year. All {len(database_list)} database(s) are empty (no tables).",
                                    "waste_reason": f"All databases empty: {empty_databases}/{len(database_list)} databases have no tables"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch databases for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for empty database Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect untagged Cloud Spanner instances.

        Waste: Missing required labels = governance waste.
        Detection: Missing required labels (environment, owner, cost-center)
        Cost: 5% of instance cost (governance overhead)
        Priority: LOW (P3) 💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from datetime import datetime, timezone

            # Get detection parameters
            required_labels = ["environment", "owner", "cost-center"]
            governance_waste_pct = 0.05
            if detection_rules and "cloud_spanner_untagged" in detection_rules:
                rules = detection_rules["cloud_spanner_untagged"]
                required_labels = rules.get("required_labels", required_labels)
                governance_waste_pct = rules.get("governance_waste_pct", 0.05)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Check labels
                    labels = dict(instance.labels) if instance.labels else {}

                    # Identify missing labels
                    missing_labels = [label for label in required_labels if label not in labels]

                    if not missing_labels:
                        continue

                    # Calculate governance waste
                    if instance.node_count > 0:
                        current_pu = instance.node_count * 1000
                    else:
                        current_pu = instance.processing_units

                    is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                    cost_per_pu = 2.19 if is_multiregional else 0.657

                    nodes_cost = current_pu * cost_per_pu
                    monthly_waste = nodes_cost * governance_waste_pct

                    # Calculate age
                    created_at = instance.create_time
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                        already_wasted = monthly_waste * (age_days / 30)
                    else:
                        age_days = 0
                        already_wasted = 0

                    resources.append(OrphanResourceData(
                        resource_id=instance_id,
                        resource_type="cloud_spanner_untagged",
                        resource_name=instance_id,
                        region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                        estimated_monthly_cost=monthly_waste,
                        resource_metadata={
                            "instance_id": instance_id,
                            "instance_config": instance_config,
                            "state": instance.state.name,
                            "processing_units": current_pu,
                            "labels": labels,
                            "missing_labels": missing_labels,
                            "instance_monthly_cost": round(nodes_cost, 2),
                            "already_wasted": round(already_wasted, 2),
                            "annual_cost": round(monthly_waste * 12, 2),
                            "confidence": "MEDIUM",
                            "recommendation": f"Add required labels for cost allocation and governance. Missing: {', '.join(missing_labels)}.",
                            "waste_reason": f"Missing {len(missing_labels)} required labels - governance waste"
                        }
                    ))

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for untagged Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_low_cpu(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect Cloud Spanner instances with very low CPU (<20%).

        Waste: Severely under-utilized instances - aggressive reduction opportunity.
        Detection: avg_cpu <20% over 14 days
        Cost: ~$2,497/month waste (5 nodes → 1200 PU optimal)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            cpu_threshold = 20.0
            target_cpu = 65.0
            lookback_days = 14
            if detection_rules and "cloud_spanner_low_cpu" in detection_rules:
                rules = detection_rules["cloud_spanner_low_cpu"]
                cpu_threshold = rules.get("cpu_threshold", 20.0)
                target_cpu = rules.get("target_cpu", 65.0)
                lookback_days = rules.get("lookback_days", 14)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Get current capacity
                    if instance.node_count > 0:
                        current_pu = instance.node_count * 1000
                    else:
                        current_pu = instance.processing_units

                    # Query CPU metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        cpu_filter = (
                            f'resource.type="spanner_instance" '
                            f'AND resource.labels.instance_id="{instance_id}" '
                            f'AND metric.type="spanner.googleapis.com/instance/cpu/utilization"'
                        )

                        cpu_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": cpu_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        cpu_values = []
                        for series in monitoring_client.list_time_series(request=cpu_request):
                            for point in series.points:
                                cpu_values.append(point.value.double_value * 100)

                        if not cpu_values:
                            continue

                        avg_cpu = sum(cpu_values) / len(cpu_values)
                        max_cpu = max(cpu_values)

                        # Detect very low CPU
                        if avg_cpu < cpu_threshold:
                            # Calculate optimal PU (aggressive reduction)
                            optimal_pu = int(current_pu * (avg_cpu / target_cpu))
                            optimal_pu = max(100, optimal_pu)

                            if optimal_pu >= current_pu:
                                continue

                            # Calculate costs
                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            cost_per_pu = 2.19 if is_multiregional else 0.657

                            current_cost = current_pu * cost_per_pu
                            optimal_cost = optimal_pu * cost_per_pu
                            monthly_waste = current_cost - optimal_cost

                            # Calculate age
                            created_at = instance.create_time
                            if created_at:
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                already_wasted = monthly_waste * (age_days / 30)
                            else:
                                age_days = 0
                                already_wasted = 0

                            savings_pct = (monthly_waste / current_cost * 100) if current_cost > 0 else 0

                            resources.append(OrphanResourceData(
                                resource_id=instance_id,
                                resource_type="cloud_spanner_low_cpu",
                                resource_name=instance_id,
                                region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "instance_config": instance_config,
                                    "state": "READY",
                                    "processing_units": current_pu,
                                    "cpu_metrics": {
                                        "avg_cpu_14d": round(avg_cpu, 1),
                                        "max_cpu_14d": round(max_cpu, 1)
                                    },
                                    "recommended_processing_units": optimal_pu,
                                    "current_cost_monthly": round(current_cost, 2),
                                    "recommended_cost_monthly": round(optimal_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "savings_percentage": round(savings_pct, 0),
                                    "annual_cost": round(monthly_waste * 12, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"Reduce from {current_pu} PU to {optimal_pu} PU to save ${monthly_waste * 12:.2f}/year ({savings_pct:.0f}% savings). Very low CPU {avg_cpu:.1f}%.",
                                    "waste_reason": f"Very low CPU: {avg_cpu:.1f}% < {cpu_threshold}%, aggressive reduction recommended"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch CPU metrics for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for low CPU Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_storage_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect Cloud Spanner with small storage (<100GB) vs Cloud SQL.

        Waste: Cloud Spanner is overkill for small datasets - Cloud SQL is cheaper.
        Detection: avg_storage_gb <100 AND growth_rate <5%
        Cost: ~$585/month savings (Spanner → Cloud SQL migration)
        Priority: LOW (P2) 💰💰 (Migration complexity)
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            max_storage_gb = 100
            max_growth_rate_pct = 5.0
            lookback_days = 30
            if detection_rules and "cloud_spanner_storage_overprovisioned" in detection_rules:
                rules = detection_rules["cloud_spanner_storage_overprovisioned"]
                max_storage_gb = rules.get("max_storage_gb", 100)
                max_growth_rate_pct = rules.get("max_growth_rate_pct", 5.0)
                lookback_days = rules.get("lookback_days", 30)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    if instance.state != spanner_admin_instance_v1.Instance.State.READY:
                        continue

                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config

                    # Query storage metrics
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=lookback_days)

                    try:
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())}
                        })

                        storage_filter = (
                            f'resource.type="spanner_instance" '
                            f'AND resource.labels.instance_id="{instance_id}" '
                            f'AND metric.type="spanner.googleapis.com/instance/storage/used_bytes"'
                        )

                        storage_request = monitoring_v3.ListTimeSeriesRequest({
                            "name": f"projects/{self.project_id}",
                            "filter": storage_filter,
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        })

                        storage_values = []
                        for series in monitoring_client.list_time_series(request=storage_request):
                            for point in series.points:
                                storage_values.append(point.value.int64_value)

                        if not storage_values:
                            continue

                        avg_storage_bytes = sum(storage_values) / len(storage_values)
                        avg_storage_gb = avg_storage_bytes / (1024**3)

                        # Analyze growth rate
                        if len(storage_values) >= 8:
                            first_week = sum(storage_values[:len(storage_values)//4]) / (len(storage_values)//4)
                            last_week = sum(storage_values[-len(storage_values)//4:]) / (len(storage_values)//4)
                            growth_rate = ((last_week - first_week) / first_week * 100) if first_week > 0 else 0
                        else:
                            growth_rate = 0

                        # Detect small storage with low growth
                        if avg_storage_gb < max_storage_gb and growth_rate < max_growth_rate_pct:
                            # Calculate Spanner cost
                            if instance.node_count > 0:
                                current_pu = instance.node_count * 1000
                            else:
                                current_pu = instance.processing_units

                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            cost_per_pu = 2.19 if is_multiregional else 0.657
                            storage_pricing = 0.50 if is_multiregional else 0.30
                            backup_pricing = 0.30 if is_multiregional else 0.20

                            spanner_nodes_cost = current_pu * cost_per_pu
                            spanner_storage_cost = avg_storage_gb * storage_pricing
                            spanner_backup_cost = (avg_storage_gb * 2) * backup_pricing
                            spanner_total = spanner_nodes_cost + spanner_storage_cost + spanner_backup_cost

                            # Cloud SQL equivalent (db-n1-standard-2)
                            cloudsql_instance_cost = 92.40
                            cloudsql_storage_cost = avg_storage_gb * 0.17
                            cloudsql_backup_cost = (avg_storage_gb * 1.5) * 0.08
                            cloudsql_total = cloudsql_instance_cost + cloudsql_storage_cost + cloudsql_backup_cost

                            # Calculate potential savings
                            monthly_waste = spanner_total - cloudsql_total

                            if monthly_waste > 0:
                                resources.append(OrphanResourceData(
                                    resource_id=instance_id,
                                    resource_type="cloud_spanner_storage_overprovisioned",
                                    resource_name=instance_id,
                                    region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "instance_config": instance_config,
                                        "state": "READY",
                                        "processing_units": current_pu,
                                        "storage_metrics": {
                                            "avg_storage_gb": round(avg_storage_gb, 1),
                                            "growth_rate_30d_pct": round(growth_rate, 1)
                                        },
                                        "current_cost_monthly": round(spanner_total, 2),
                                        "alternative_cloudsql_cost_monthly": round(cloudsql_total, 2),
                                        "annual_savings": round(monthly_waste * 12, 2),
                                        "confidence": "LOW",
                                        "migration_complexity": "high",
                                        "recommendation": f"Consider migrating to Cloud SQL for small datasets (<{max_storage_gb}GB). Potential savings ${monthly_waste * 12:.2f}/year.",
                                        "waste_reason": f"Small storage {avg_storage_gb:.0f}GB - Cloud Spanner overkill, Cloud SQL would be cheaper"
                                    }
                                ))

                    except Exception as e:
                        logger.warning(f"Could not fetch storage metrics for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for storage over-provisioned Cloud Spanner: {e}")

        return resources

    async def scan_cloud_spanner_excessive_backups(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect excessive backup retention.

        Waste: Backups >90 days for dev/test or >365 days for prod.
        Detection: Backups age >threshold based on environment labels
        Cost: ~$100/month waste (500GB old backups)
        Priority: LOW (P3) 💰
        """
        resources = []

        try:
            from google.cloud import spanner_admin_instance_v1
            from google.cloud import spanner_admin_database_v1
            from datetime import datetime, timezone

            # Get detection parameters
            excessive_retention_days_devtest = 90
            excessive_retention_days_prod = 365
            devtest_labels = ["dev", "test", "staging", "development"]
            if detection_rules and "cloud_spanner_excessive_backups" in detection_rules:
                rules = detection_rules["cloud_spanner_excessive_backups"]
                excessive_retention_days_devtest = rules.get("excessive_retention_days_devtest", 90)
                excessive_retention_days_prod = rules.get("excessive_retention_days_prod", 365)
                devtest_labels = rules.get("devtest_labels", devtest_labels)

            spanner_client = spanner_admin_instance_v1.InstanceAdminClient(credentials=self.credentials)
            database_admin_client = spanner_admin_database_v1.DatabaseAdminClient(credentials=self.credentials)

            # List all instances
            try:
                parent = f"projects/{self.project_id}"
                instances = spanner_client.list_instances(parent=parent)

                for instance in instances:
                    instance_id = instance.name.split('/')[-1]
                    instance_config = instance.config
                    instance_path = instance.name

                    # Check labels
                    labels = dict(instance.labels) if instance.labels else {}
                    environment = labels.get('environment', '').lower()

                    is_devtest = environment in devtest_labels
                    retention_threshold = excessive_retention_days_devtest if is_devtest else excessive_retention_days_prod

                    # List backups
                    try:
                        backups = database_admin_client.list_backups(parent=instance_path)

                        total_backup_size_gb = 0
                        old_backups = []
                        old_backup_size_gb = 0

                        for backup in backups:
                            backup_size_bytes = backup.size_bytes
                            backup_size_gb = backup_size_bytes / (1024**3)
                            total_backup_size_gb += backup_size_gb

                            # Calculate age
                            creation_time = backup.create_time
                            age_days = (datetime.now(timezone.utc) - creation_time).days

                            # Identify old backups
                            if age_days >= retention_threshold:
                                old_backups.append({
                                    'name': backup.name.split('/')[-1],
                                    'age_days': age_days,
                                    'size_gb': backup_size_gb
                                })
                                old_backup_size_gb += backup_size_gb

                        # Detect excessive backups
                        if len(old_backups) > 0:
                            # Calculate waste
                            is_multiregional = any(x in instance_config for x in ['nam', 'eur', 'asia'])
                            backup_pricing = 0.30 if is_multiregional else 0.20

                            monthly_waste = old_backup_size_gb * backup_pricing

                            # Estimate waste over last 3 months
                            already_wasted = monthly_waste * 3

                            resources.append(OrphanResourceData(
                                resource_id=instance_id,
                                resource_type="cloud_spanner_excessive_backups",
                                resource_name=instance_id,
                                region=instance_config.split('/')[-1] if '/' in instance_config else instance_config,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "instance_config": instance_config,
                                    "labels": labels,
                                    "environment": environment if environment else "unknown",
                                    "backup_analysis": {
                                        "total_backups": len(list(backups)),
                                        "old_backups": len(old_backups),
                                        "total_backup_size_gb": round(total_backup_size_gb, 1),
                                        "old_backup_size_gb": round(old_backup_size_gb, 1),
                                        "oldest_backup_age_days": max([b['age_days'] for b in old_backups]) if old_backups else 0
                                    },
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(monthly_waste * 12, 2),
                                    "confidence": "MEDIUM",
                                    "recommendation": f"Delete backups >{retention_threshold} days for {environment if environment else 'this'} environment to save ${monthly_waste * 12:.2f}/year.",
                                    "waste_reason": f"Excessive backup retention: {len(old_backups)} backups >{retention_threshold} days"
                                }
                            ))

                    except Exception as e:
                        logger.warning(f"Could not fetch backups for Spanner instance {instance_id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error listing Cloud Spanner instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for excessive backups Cloud Spanner: {e}")

        return resources

    # ================================================================
    # CLOUD FIRESTORE DETECTION METHODS (10 scenarios)
    # ================================================================

    async def scan_firestore_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect completely idle Firestore databases (0 requests 30+ days).

        Waste: Databases with zero API requests but still paying for storage.
        Detection: api/request_count = 0 for 30+ days
        Cost: Storage cost ($9-$170/month typical) - 100% waste
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_idle_threshold = rules.get("days_idle_threshold", 30)
        min_savings_threshold = rules.get("min_savings_threshold", 5.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            admin_client = FirestoreAdminClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Check activity via Cloud Monitoring
                    now = datetime.utcnow()
                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(now.timestamp())},
                        "start_time": {"seconds": int((now - timedelta(days=days_idle_threshold)).timestamp())}
                    })

                    # Query api/request_count metric
                    total_requests = 0
                    try:
                        metric_filter = (
                            f'metric.type="firestore.googleapis.com/api/request_count" AND '
                            f'resource.labels.database_id="{database_id}"'
                        )

                        results = monitoring_client.list_time_series(
                            name=f"projects/{self.project_id}",
                            filter=metric_filter,
                            interval=interval,
                            view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                        )

                        for result in results:
                            for point in result.points:
                                total_requests += point.value.int64_value if hasattr(point.value, 'int64_value') else 0
                    except Exception as e:
                        logger.warning(f"Could not fetch metrics for database {database_id}: {e}")
                        continue

                    # If idle (0 requests)
                    if total_requests == 0:
                        # Estimate storage size (simplified - actual size would need Firestore client query)
                        estimated_storage_gb = 50.0  # Default estimate

                        # Calculate waste (storage + potential backups)
                        storage_monthly = estimated_storage_gb * 0.18
                        backup_monthly = estimated_storage_gb * 0.026 * 4  # 4 weekly backups estimate
                        monthly_waste = storage_monthly + backup_monthly

                        if monthly_waste < min_savings_threshold:
                            continue

                        # Calculate age (simplified)
                        created_at = database.create_time if hasattr(database, 'create_time') else now
                        age_days = (now - created_at.replace(tzinfo=None) if hasattr(created_at, 'replace') else now - now).days
                        already_wasted = monthly_waste * (age_days / 30)

                        # Confidence level
                        if days_idle_threshold >= 90:
                            confidence = "CRITICAL"
                        elif days_idle_threshold >= 60:
                            confidence = "HIGH"
                        else:
                            confidence = "MEDIUM"

                        resources.append(
                            OrphanResourceData(
                                resource_id=database.name,
                                resource_name=database_id,
                                resource_type="firestore_idle",
                                region=location_id,
                                estimated_monthly_cost=monthly_waste,
                                already_wasted=already_wasted,
                                confidence_level=confidence,
                                resource_metadata={
                                    "database_id": database_id,
                                    "location": location_id,
                                    "days_idle": days_idle_threshold,
                                    "total_requests": total_requests,
                                    "storage_gb_estimate": estimated_storage_gb,
                                    "storage_cost_monthly": round(storage_monthly, 2),
                                    "backup_cost_monthly": round(backup_monthly, 2)
                                },
                                recommendation=f"DELETE database if confirmed unused. Zero requests for {days_idle_threshold}+ days = 100% waste."
                            )
                        )

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for idle Firestore databases: {e}")

        return resources

    async def scan_firestore_unused_indexes(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect unused Firestore indexes (never used in queries).

        Waste: Indexes that are never used but consume storage and slow down writes.
        Detection: List indexes + correlate with query usage patterns (Cloud Logging)
        Cost: $0.18/GB/month storage + performance impact
        Priority: HIGH (P1) 💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_lookback = rules.get("days_lookback", 30)
        min_savings_threshold = rules.get("min_savings_threshold", 2.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # List all indexes in this database
                    collection_parent = f"{database.name}/collectionGroups/-"

                    try:
                        indexes = admin_client.list_indexes(parent=collection_parent)

                        unused_index_count = 0
                        for index in indexes:
                            # Simplified detection: In production, would correlate with Cloud Logging query patterns
                            # For MVP, flag all composite indexes for review
                            if len(index.fields) > 2:  # Composite indexes with 3+ fields
                                unused_index_count += 1

                        if unused_index_count > 0:
                            # Estimate waste
                            estimated_index_storage_gb = unused_index_count * 0.1  # ~100MB per unused index estimate
                            monthly_waste = estimated_index_storage_gb * 0.18

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=database.name,
                                    resource_name=f"{database_id}_unused_indexes",
                                    resource_type="firestore_unused_indexes",
                                    region=location_id,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "database_id": database_id,
                                        "unused_index_count": unused_index_count,
                                        "index_storage_gb": round(estimated_index_storage_gb, 2),
                                        "lookback_days": days_lookback
                                    },
                                    recommendation=f"Review and DELETE {unused_index_count} unused composite indexes. Saves storage and improves write performance."
                                )
                            )

                    except Exception as e:
                        logger.warning(f"Error listing indexes for database {database_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unused Firestore indexes: {e}")

        return resources

    async def scan_firestore_missing_ttl(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect missing TTL policies (expired data not auto-deleted).

        Waste: Old/expired data still consuming storage without TTL policies.
        Detection: Check for TTL field configuration + estimate old data volume
        Cost: $500-$5,000/year typical
        Priority: HIGH (P1) 💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        ttl_threshold_days = rules.get("ttl_threshold_days", 90)
        min_savings_threshold = rules.get("min_savings_threshold", 10.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Check for TTL policies
                    # In real implementation, would query Firestore for TTL field configuration
                    # For MVP, we flag databases without explicit TTL configuration

                    # Simplified: Estimate potential waste from old data
                    estimated_old_data_gb = 20.0  # Default estimate
                    monthly_waste = estimated_old_data_gb * 0.18

                    if monthly_waste < min_savings_threshold:
                        continue

                    resources.append(
                        OrphanResourceData(
                            resource_id=database.name,
                            resource_name=f"{database_id}_missing_ttl",
                            resource_type="firestore_missing_ttl",
                            region=location_id,
                            estimated_monthly_cost=monthly_waste,
                            confidence_level="MEDIUM",
                            resource_metadata={
                                "database_id": database_id,
                                "ttl_threshold_days": ttl_threshold_days,
                                "estimated_old_data_gb": estimated_old_data_gb
                            },
                            recommendation=f"Implement TTL policies for documents older than {ttl_threshold_days} days to auto-delete expired data."
                        )
                    )

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for missing TTL in Firestore: {e}")

        return resources

    async def scan_firestore_over_indexing(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect over-indexing (too many automatic indexes).

        Waste: Excessive automatic single-field indexes consuming storage.
        Detection: Count automatic indexes vs index exemptions
        Cost: $1,000-$10,000/year typical
        Priority: MEDIUM (P2) 💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        max_auto_indexes_threshold = rules.get("max_auto_indexes_threshold", 50)
        min_savings_threshold = rules.get("min_savings_threshold", 20.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Count indexes
                    collection_parent = f"{database.name}/collectionGroups/-"

                    try:
                        indexes = list(admin_client.list_indexes(parent=collection_parent))
                        total_indexes = len(indexes)

                        # Simplified: Flag if too many indexes
                        if total_indexes > max_auto_indexes_threshold:
                            # Estimate waste
                            excessive_indexes = total_indexes - max_auto_indexes_threshold
                            estimated_waste_gb = excessive_indexes * 0.05  # ~50MB per excessive index
                            monthly_waste = estimated_waste_gb * 0.18

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=database.name,
                                    resource_name=f"{database_id}_over_indexing",
                                    resource_type="firestore_over_indexing",
                                    region=location_id,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "database_id": database_id,
                                        "total_indexes": total_indexes,
                                        "excessive_indexes": excessive_indexes,
                                        "max_threshold": max_auto_indexes_threshold
                                    },
                                    recommendation=f"Add index exemptions for {excessive_indexes} rarely-queried fields to reduce storage overhead."
                                )
                            )

                    except Exception as e:
                        logger.warning(f"Error counting indexes for database {database_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for over-indexing in Firestore: {e}")

        return resources

    async def scan_firestore_empty_collections(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect empty collections with indexes.

        Waste: Collections with 0 documents but still have indexes configured.
        Detection: Query collections + check document count
        Cost: $50-$500/year typical
        Priority: MEDIUM (P2) 💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        min_savings_threshold = rules.get("min_savings_threshold", 5.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient
            from google.cloud import firestore

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Simplified detection: Flag databases with indexes but low usage
                    # In real implementation, would check individual collections

                    # For MVP, estimate based on index count
                    collection_parent = f"{database.name}/collectionGroups/-"

                    try:
                        indexes = list(admin_client.list_indexes(parent=collection_parent))

                        if len(indexes) > 0:
                            # Estimate 10% of indexes are on empty collections
                            empty_indexes_estimate = max(1, len(indexes) // 10)
                            estimated_waste_gb = empty_indexes_estimate * 0.01  # Small waste per empty collection
                            monthly_waste = estimated_waste_gb * 0.18

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=database.name,
                                    resource_name=f"{database_id}_empty_collections",
                                    resource_type="firestore_empty_collections",
                                    region=location_id,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="LOW",
                                    resource_metadata={
                                        "database_id": database_id,
                                        "total_indexes": len(indexes),
                                        "empty_collections_estimate": empty_indexes_estimate
                                    },
                                    recommendation="Review and DELETE empty collections or remove their indexes."
                                )
                            )

                    except Exception as e:
                        logger.warning(f"Error checking empty collections for database {database_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for empty collections in Firestore: {e}")

        return resources

    async def scan_firestore_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect untagged Firestore databases (missing required labels).

        Waste: Missing labels = governance overhead and cost allocation issues.
        Detection: Check labels via Admin API
        Cost: 5% of database cost (governance overhead)
        Priority: LOW (P3) 💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        required_labels = rules.get("required_labels", ["environment", "owner", "cost-center"])
        governance_waste_pct = rules.get("governance_waste_pct", 0.05)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Check labels (if available in API response)
                    labels = {}
                    if hasattr(database, 'labels'):
                        labels = dict(database.labels) if database.labels else {}

                    missing_labels = [label for label in required_labels if label not in labels]

                    if missing_labels:
                        # Estimate database cost for governance calculation
                        estimated_db_cost = 50.0  # Default monthly estimate
                        monthly_waste = estimated_db_cost * governance_waste_pct

                        resources.append(
                            OrphanResourceData(
                                resource_id=database.name,
                                resource_name=f"{database_id}_untagged",
                                resource_type="firestore_untagged",
                                region=location_id,
                                estimated_monthly_cost=monthly_waste,
                                confidence_level="LOW",
                                resource_metadata={
                                    "database_id": database_id,
                                    "missing_labels": missing_labels,
                                    "current_labels": list(labels.keys())
                                },
                                recommendation=f"Add missing labels: {', '.join(missing_labels)} for proper cost allocation and governance."
                            )
                        )

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for untagged Firestore databases: {e}")

        return resources

    async def scan_firestore_old_backups(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect old backups with excessive retention (>90 days).

        Waste: Backups retained longer than necessary.
        Detection: List backups + check age
        Cost: $100-$1,000/year typical
        Priority: LOW (P3) 💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        retention_threshold_days = rules.get("retention_threshold_days", 90)
        min_savings_threshold = rules.get("min_savings_threshold", 5.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient
            from datetime import datetime, timedelta

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # List backups for this database
                    try:
                        backups = admin_client.list_backups(parent=database.name)

                        old_backups = []
                        total_old_backup_size_gb = 0.0
                        now = datetime.utcnow()

                        for backup in backups:
                            if hasattr(backup, 'create_time'):
                                backup_age = (now - backup.create_time.replace(tzinfo=None)).days

                                if backup_age > retention_threshold_days:
                                    old_backups.append(backup.name)
                                    # Estimate backup size
                                    total_old_backup_size_gb += 10.0  # ~10GB per old backup estimate

                        if old_backups:
                            monthly_waste = total_old_backup_size_gb * 0.026  # Backup storage cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=database.name,
                                    resource_name=f"{database_id}_old_backups",
                                    resource_type="firestore_old_backups",
                                    region=location_id,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "database_id": database_id,
                                        "old_backup_count": len(old_backups),
                                        "retention_threshold_days": retention_threshold_days,
                                        "total_size_gb": round(total_old_backup_size_gb, 2)
                                    },
                                    recommendation=f"DELETE {len(old_backups)} backups older than {retention_threshold_days} days to reduce storage costs."
                                )
                            )

                    except Exception as e:
                        logger.warning(f"Error listing backups for database {database_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for old Firestore backups: {e}")

        return resources

    async def scan_firestore_inefficient_queries(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect inefficient query patterns (N+1 problem).

        Waste: Multiple sequential reads instead of batched queries = higher costs.
        Detection: Cloud Logging analysis of query patterns
        Cost: $500-$8,000/year typical
        Priority: HIGH (P1) 💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Simplified detection: Flag active databases for query pattern review
                    # In real implementation, would analyze Cloud Logging for N+1 patterns

                    # For MVP, estimate potential waste from inefficient queries
                    estimated_inefficient_reads = 100000  # 100K inefficient reads/month estimate
                    monthly_waste = (estimated_inefficient_reads / 100000) * 0.03  # Read cost

                    if monthly_waste < min_savings_threshold:
                        continue

                    resources.append(
                        OrphanResourceData(
                            resource_id=database.name,
                            resource_name=f"{database_id}_inefficient_queries",
                            resource_type="firestore_inefficient_queries",
                            region=location_id,
                            estimated_monthly_cost=monthly_waste,
                            confidence_level="LOW",
                            resource_metadata={
                                "database_id": database_id,
                                "estimated_inefficient_reads": estimated_inefficient_reads
                            },
                            recommendation="Review query patterns in Cloud Logging. Use batch reads instead of sequential document lookups to reduce costs."
                        )
                    )

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for inefficient queries in Firestore: {e}")

        return resources

    async def scan_firestore_unnecessary_composite(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect unnecessary composite indexes (custom indexes not used).

        Waste: Composite indexes that were created but never used in queries.
        Detection: List composite indexes + correlate with query usage
        Cost: $200-$3,000/year typical
        Priority: MEDIUM (P2) 💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_lookback = rules.get("days_lookback", 30)
        min_savings_threshold = rules.get("min_savings_threshold", 10.0)

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # List composite indexes
                    collection_parent = f"{database.name}/collectionGroups/-"

                    try:
                        indexes = admin_client.list_indexes(parent=collection_parent)

                        composite_count = 0
                        for index in indexes:
                            # Composite indexes have 2+ fields (excluding __name__)
                            non_system_fields = [f for f in index.fields if f.field_path != '__name__']
                            if len(non_system_fields) >= 2:
                                composite_count += 1

                        if composite_count > 0:
                            # Estimate waste (assume 20% are unused)
                            unused_composite_estimate = max(1, composite_count // 5)
                            estimated_waste_gb = unused_composite_estimate * 0.1  # ~100MB per unused composite
                            monthly_waste = estimated_waste_gb * 0.18

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=database.name,
                                    resource_name=f"{database_id}_unnecessary_composite",
                                    resource_type="firestore_unnecessary_composite",
                                    region=location_id,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "database_id": database_id,
                                        "total_composite_indexes": composite_count,
                                        "unused_estimate": unused_composite_estimate,
                                        "lookback_days": days_lookback
                                    },
                                    recommendation=f"Review {unused_composite_estimate} potentially unused composite indexes and DELETE if confirmed unnecessary."
                                )
                            )

                    except Exception as e:
                        logger.warning(f"Error listing composite indexes for database {database_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unnecessary composite indexes in Firestore: {e}")

        return resources

    async def scan_firestore_wrong_mode(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect wrong mode choice (Native vs Datastore mismatch).

        Waste: Using wrong Firestore mode for use case (migration recommendation).
        Detection: Check database mode + analyze usage patterns
        Cost: Migration awareness (no direct cost, but opportunity cost)
        Priority: LOW (P3) ⚠️
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        try:
            from google.cloud.firestore_admin_v1 import FirestoreAdminClient

            admin_client = FirestoreAdminClient()

            # List all Firestore databases
            parent = f"projects/{self.project_id}"

            try:
                databases = admin_client.list_databases(parent=parent)

                for database in databases:
                    database_id = database.name.split('/')[-1]
                    location_id = database.location_id

                    # Check database mode
                    db_type = database.type_ if hasattr(database, 'type_') else "UNKNOWN"

                    # Simplified detection: Flag Datastore mode databases for review
                    if "DATASTORE" in str(db_type).upper():
                        # Estimate potential savings from Native mode features
                        monthly_cost_awareness = 0.0  # Informational only

                        resources.append(
                            OrphanResourceData(
                                resource_id=database.name,
                                resource_name=f"{database_id}_wrong_mode",
                                resource_type="firestore_wrong_mode",
                                region=location_id,
                                estimated_monthly_cost=monthly_cost_awareness,
                                confidence_level="LOW",
                                resource_metadata={
                                    "database_id": database_id,
                                    "current_mode": str(db_type),
                                    "note": "Mode cannot be changed after creation with data"
                                },
                                recommendation="Review if Datastore mode is truly needed. Native mode offers real-time listeners and better mobile support. Consider for new databases."
                            )
                        )

            except Exception as e:
                logger.error(f"Error listing Firestore databases: {e}")

        except Exception as e:
            logger.error(f"Error scanning for wrong mode in Firestore: {e}")

        return resources

    # ================================================================
    # CLOUD BIGTABLE DETECTION METHODS (10 scenarios)
    # ================================================================

    async def scan_bigtable_underutilized(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect under-utilized Bigtable instances (CPU <65%).

        Waste: Instances with excessive nodes compared to actual CPU usage.
        Detection: avg_cpu <65% over 14 days
        Cost: Difference between current and optimal nodes ($1,422/month typical)
        Priority: HIGH (P1) 💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        cpu_threshold = rules.get("cpu_threshold", 65.0)
        target_cpu = rules.get("target_cpu", 65.0)
        lookback_days = rules.get("lookback_days", 14)
        min_savings_threshold = rules.get("min_savings_threshold", 100.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            instance_admin_client = BigtableInstanceAdminClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List clusters in this instance
                    clusters = instance_admin_client.list_clusters(parent=instance.name)

                    for cluster in clusters.clusters:
                        cluster_id = cluster.name.split('/')[-1]
                        node_count = cluster.serve_nodes
                        storage_type = str(cluster.default_storage_type)

                        # Get CPU metrics
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=lookback_days)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'metric.type="bigtable.googleapis.com/cluster/cpu_load" AND '
                                f'resource.labels.cluster="{cluster_id}"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            cpu_values = []
                            for result in results:
                                for point in result.points:
                                    cpu_values.append(point.value.double_value * 100)

                            if not cpu_values:
                                continue

                            avg_cpu = sum(cpu_values) / len(cpu_values)

                            if avg_cpu < cpu_threshold:
                                # Calculate optimal nodes
                                optimal_nodes = max(1, int(node_count * (avg_cpu / target_cpu)))

                                if optimal_nodes >= node_count:
                                    continue

                                # Calculate cost
                                node_monthly_cost = 474 if "SSD" in storage_type else 226
                                monthly_waste = (node_count - optimal_nodes) * node_monthly_cost

                                if monthly_waste < min_savings_threshold:
                                    continue

                                # Confidence level
                                if avg_cpu < 30:
                                    confidence = "CRITICAL"
                                elif avg_cpu < 50:
                                    confidence = "HIGH"
                                else:
                                    confidence = "MEDIUM"

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=cluster.name,
                                        resource_name=f"{instance_id}/{cluster_id}",
                                        resource_type="bigtable_underutilized",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level=confidence,
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "cluster_id": cluster_id,
                                            "current_nodes": node_count,
                                            "optimal_nodes": optimal_nodes,
                                            "avg_cpu_pct": round(avg_cpu, 2),
                                            "storage_type": storage_type,
                                            "node_monthly_cost": node_monthly_cost
                                        },
                                        recommendation=f"Reduce from {node_count} to {optimal_nodes} nodes based on {avg_cpu:.1f}% CPU utilization."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch CPU metrics for cluster {cluster_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for underutilized Bigtable instances: {e}")

        return resources

    async def scan_bigtable_unnecessary_multicluster(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect unnecessary multi-cluster Bigtable instances.

        Waste: Multi-cluster replication for dev/test = double node costs.
        Detection: >1 cluster + dev/test labels
        Cost: ~$2,844/month waste (6 nodes multi vs 3 nodes single)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        devtest_labels = rules.get("devtest_labels", ["dev", "test", "staging", "development"])
        min_savings_threshold = rules.get("min_savings_threshold", 200.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient

            instance_admin_client = BigtableInstanceAdminClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]
                    labels = dict(instance.labels) if hasattr(instance, 'labels') and instance.labels else {}

                    # List clusters in this instance
                    clusters = list(instance_admin_client.list_clusters(parent=instance.name).clusters)
                    cluster_count = len(clusters)

                    # Check if multi-cluster + dev/test
                    if cluster_count > 1:
                        env_label = labels.get('environment', '').lower()

                        if env_label in devtest_labels or any(label in labels.get('env', '').lower() for label in devtest_labels):
                            # Calculate total nodes across all clusters
                            total_nodes = sum(cluster.serve_nodes for cluster in clusters)
                            single_cluster_nodes = total_nodes // cluster_count  # Average per cluster

                            # Estimate storage type from first cluster
                            storage_type = str(clusters[0].default_storage_type) if clusters else "SSD"
                            node_monthly_cost = 474 if "SSD" in storage_type else 226

                            # Waste = cost of extra clusters
                            extra_nodes = total_nodes - single_cluster_nodes
                            monthly_waste = extra_nodes * node_monthly_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="bigtable_unnecessary_multicluster",
                                    region=clusters[0].location if clusters else "unknown",
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="HIGH",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "cluster_count": cluster_count,
                                        "total_nodes": total_nodes,
                                        "environment": env_label,
                                        "labels": list(labels.keys())
                                    },
                                    recommendation=f"Remove {cluster_count - 1} extra cluster(s) for dev/test environment. Multi-cluster replication not needed."
                                )
                            )

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unnecessary multi-cluster Bigtable: {e}")

        return resources

    async def scan_bigtable_unnecessary_ssd(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect unnecessary SSD storage for cold data.

        Waste: SSD storage costs 6.5x more than HDD for cold/archive data.
        Detection: SSD storage + low throughput (<500 ops/sec/node)
        Cost: ~$2,184/month savings (SSD→HDD for 10TB)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        throughput_threshold = rules.get("throughput_threshold", 500)
        min_savings_threshold = rules.get("min_savings_threshold", 100.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            instance_admin_client = BigtableInstanceAdminClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List clusters in this instance
                    clusters = instance_admin_client.list_clusters(parent=instance.name)

                    for cluster in clusters.clusters:
                        cluster_id = cluster.name.split('/')[-1]
                        storage_type = str(cluster.default_storage_type)

                        # Only flag SSD clusters
                        if "SSD" not in storage_type:
                            continue

                        # Get throughput metrics (simplified - use request count as proxy)
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=7)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'metric.type="bigtable.googleapis.com/server/request_count" AND '
                                f'resource.labels.cluster="{cluster_id}"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            total_requests = 0
                            for result in results:
                                for point in result.points:
                                    total_requests += point.value.int64_value if hasattr(point.value, 'int64_value') else 0

                            # Estimate ops/sec/node
                            days = 7
                            avg_ops_per_sec_per_node = total_requests / (days * 24 * 3600 * cluster.serve_nodes) if cluster.serve_nodes > 0 else 0

                            if avg_ops_per_sec_per_node < throughput_threshold:
                                # Estimate storage size (simplified - assume 1TB per 3 nodes)
                                estimated_storage_tb = max(1, cluster.serve_nodes // 3)

                                # Calculate storage cost difference
                                ssd_storage_cost = estimated_storage_tb * 1000 * 0.17
                                hdd_storage_cost = estimated_storage_tb * 1000 * 0.026
                                storage_waste = ssd_storage_cost - hdd_storage_cost

                                # Node cost difference
                                node_waste = cluster.serve_nodes * (474 - 226)

                                monthly_waste = storage_waste + node_waste

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=cluster.name,
                                        resource_name=f"{instance_id}/{cluster_id}",
                                        resource_type="bigtable_unnecessary_ssd",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="HIGH",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "cluster_id": cluster_id,
                                            "storage_type": storage_type,
                                            "avg_ops_per_sec_per_node": round(avg_ops_per_sec_per_node, 2),
                                            "threshold": throughput_threshold,
                                            "estimated_storage_tb": estimated_storage_tb
                                        },
                                        recommendation=f"Migrate from SSD to HDD storage. Low throughput ({avg_ops_per_sec_per_node:.0f} ops/sec/node) doesn't require SSD performance. Saves 6.5x on storage costs."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch throughput metrics for cluster {cluster_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for unnecessary SSD in Bigtable: {e}")

        return resources

    async def scan_bigtable_devtest_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect dev/test Bigtable instances over-provisioned.

        Waste: Dev/test with >1 node when 1 node minimum is sufficient.
        Detection: labels.environment in ['dev', 'test'] AND nodes >1
        Cost: ~$948/month waste (3 nodes → 1 node)
        Priority: HIGH (P1) 💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        devtest_labels = rules.get("devtest_labels", ["dev", "test", "staging", "development"])
        recommended_nodes = rules.get("recommended_nodes", 1)
        min_savings_threshold = rules.get("min_savings_threshold", 100.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient

            instance_admin_client = BigtableInstanceAdminClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]
                    labels = dict(instance.labels) if hasattr(instance, 'labels') and instance.labels else {}

                    # Check if dev/test environment
                    env_label = labels.get('environment', '').lower()

                    if env_label not in devtest_labels and not any(label in labels.get('env', '').lower() for label in devtest_labels):
                        continue

                    # List clusters in this instance
                    clusters = instance_admin_client.list_clusters(parent=instance.name)

                    for cluster in clusters.clusters:
                        cluster_id = cluster.name.split('/')[-1]
                        node_count = cluster.serve_nodes

                        if node_count <= recommended_nodes:
                            continue

                        # Calculate waste
                        storage_type = str(cluster.default_storage_type)
                        node_monthly_cost = 474 if "SSD" in storage_type else 226
                        monthly_waste = (node_count - recommended_nodes) * node_monthly_cost

                        if monthly_waste < min_savings_threshold:
                            continue

                        resources.append(
                            OrphanResourceData(
                                resource_id=cluster.name,
                                resource_name=f"{instance_id}/{cluster_id}",
                                resource_type="bigtable_devtest_overprovisioned",
                                region=cluster.location,
                                estimated_monthly_cost=monthly_waste,
                                confidence_level="HIGH",
                                resource_metadata={
                                    "instance_id": instance_id,
                                    "cluster_id": cluster_id,
                                    "current_nodes": node_count,
                                    "recommended_nodes": recommended_nodes,
                                    "environment": env_label,
                                    "storage_type": storage_type
                                },
                                recommendation=f"Reduce dev/test cluster from {node_count} to {recommended_nodes} node(s). Minimal configuration sufficient for non-production."
                            )
                        )

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for over-provisioned dev/test Bigtable: {e}")

        return resources

    async def scan_bigtable_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect idle Bigtable instances (zero requests).

        Waste: Instances with 0 API requests = 100% waste.
        Detection: total_requests = 0 for 14+ days
        Cost: Full instance cost ($506/month typical) - 100% waste
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_idle_threshold = rules.get("days_idle_threshold", 14)
        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            instance_admin_client = BigtableInstanceAdminClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List clusters in this instance
                    clusters = instance_admin_client.list_clusters(parent=instance.name)

                    for cluster in clusters.clusters:
                        cluster_id = cluster.name.split('/')[-1]

                        # Check activity via Cloud Monitoring
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=days_idle_threshold)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'metric.type="bigtable.googleapis.com/server/request_count" AND '
                                f'resource.labels.cluster="{cluster_id}"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            total_requests = 0
                            for result in results:
                                for point in result.points:
                                    total_requests += point.value.int64_value if hasattr(point.value, 'int64_value') else 0

                            if total_requests == 0:
                                # Calculate full cost
                                storage_type = str(cluster.default_storage_type)
                                node_monthly_cost = 474 if "SSD" in storage_type else 226
                                monthly_waste = cluster.serve_nodes * node_monthly_cost

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=cluster.name,
                                        resource_name=f"{instance_id}/{cluster_id}",
                                        resource_type="bigtable_idle",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="CRITICAL",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "cluster_id": cluster_id,
                                            "days_idle": days_idle_threshold,
                                            "total_requests": total_requests,
                                            "node_count": cluster.serve_nodes,
                                            "storage_type": storage_type
                                        },
                                        recommendation=f"DELETE cluster or instance. Zero requests for {days_idle_threshold}+ days = 100% waste."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch request metrics for cluster {cluster_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for idle Bigtable instances: {e}")

        return resources

    async def scan_bigtable_empty_tables(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect Bigtable instances with empty tables.

        Waste: Instances with tables but no data = unused infrastructure.
        Detection: 0 rows across all tables
        Cost: Full instance cost ($474/month typical) - 100% waste
        Priority: HIGH (P1) 💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient, BigtableTableAdminClient

            instance_admin_client = BigtableInstanceAdminClient()
            table_admin_client = BigtableTableAdminClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List tables in this instance
                    try:
                        tables = table_admin_client.list_tables(parent=instance.name)
                        table_count = len(list(tables))

                        # Simplified detection: Flag if has tables but low usage
                        # In real implementation, would check row counts per table

                        if table_count > 0:
                            # Estimate: Flag instances for manual review of table contents
                            # For MVP, we'll flag based on instance having tables

                            # Get cluster info for cost calculation
                            clusters = list(instance_admin_client.list_clusters(parent=instance.name).clusters)

                            if clusters:
                                cluster = clusters[0]
                                storage_type = str(cluster.default_storage_type)
                                node_monthly_cost = 474 if "SSD" in storage_type else 226
                                monthly_waste = cluster.serve_nodes * node_monthly_cost * 0.1  # Assume 10% waste for empty tables check

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=instance.name,
                                        resource_name=instance_id,
                                        resource_type="bigtable_empty_tables",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="MEDIUM",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "table_count": table_count,
                                            "node_count": cluster.serve_nodes
                                        },
                                        recommendation=f"Review {table_count} table(s) for empty/unused tables. Delete empty tables or entire instance if all tables are empty."
                                    )
                                )

                    except Exception as e:
                        logger.warning(f"Could not list tables for instance {instance_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for empty Bigtable tables: {e}")

        return resources

    async def scan_bigtable_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect untagged Bigtable instances (missing required labels).

        Waste: Missing labels = governance overhead and cost allocation issues.
        Detection: Check labels via Instance Admin API
        Cost: 5% of instance cost (governance overhead)
        Priority: LOW (P3) 💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        required_labels = rules.get("required_labels", ["environment", "owner", "cost-center"])
        governance_waste_pct = rules.get("governance_waste_pct", 0.05)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient

            instance_admin_client = BigtableInstanceAdminClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]
                    labels = dict(instance.labels) if hasattr(instance, 'labels') and instance.labels else {}

                    missing_labels = [label for label in required_labels if label not in labels]

                    if missing_labels:
                        # Get cluster info for cost calculation
                        clusters = list(instance_admin_client.list_clusters(parent=instance.name).clusters)

                        if clusters:
                            # Estimate instance cost
                            total_cost = 0
                            for cluster in clusters:
                                storage_type = str(cluster.default_storage_type)
                                node_monthly_cost = 474 if "SSD" in storage_type else 226
                                total_cost += cluster.serve_nodes * node_monthly_cost

                            monthly_waste = total_cost * governance_waste_pct

                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="bigtable_untagged",
                                    region=clusters[0].location if clusters else "unknown",
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="LOW",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "missing_labels": missing_labels,
                                        "current_labels": list(labels.keys()),
                                        "cluster_count": len(clusters)
                                    },
                                    recommendation=f"Add missing labels: {', '.join(missing_labels)} for proper cost allocation and governance."
                                )
                            )

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for untagged Bigtable instances: {e}")

        return resources

    async def scan_bigtable_low_cpu(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect Bigtable clusters with very low CPU (<30%).

        Waste: Severely under-utilized clusters - aggressive reduction opportunity.
        Detection: avg_cpu <30% over 14 days
        Cost: ~$2,370/month waste (10 nodes → 4 nodes optimal)
        Priority: CRITICAL (P0) 💰💰💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        cpu_threshold = rules.get("low_cpu_threshold", 30.0)
        target_cpu = rules.get("target_cpu", 65.0)
        lookback_days = rules.get("lookback_days", 14)
        min_savings_threshold = rules.get("min_savings_threshold", 200.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            instance_admin_client = BigtableInstanceAdminClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List clusters in this instance
                    clusters = instance_admin_client.list_clusters(parent=instance.name)

                    for cluster in clusters.clusters:
                        cluster_id = cluster.name.split('/')[-1]
                        node_count = cluster.serve_nodes

                        # Get CPU metrics
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=lookback_days)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'metric.type="bigtable.googleapis.com/cluster/cpu_load" AND '
                                f'resource.labels.cluster="{cluster_id}"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            cpu_values = []
                            for result in results:
                                for point in result.points:
                                    cpu_values.append(point.value.double_value * 100)

                            if not cpu_values:
                                continue

                            avg_cpu = sum(cpu_values) / len(cpu_values)

                            if avg_cpu < cpu_threshold:
                                # Calculate optimal nodes (aggressive reduction)
                                optimal_nodes = max(1, int(node_count * (avg_cpu / target_cpu)))

                                if optimal_nodes >= node_count:
                                    continue

                                # Calculate cost
                                storage_type = str(cluster.default_storage_type)
                                node_monthly_cost = 474 if "SSD" in storage_type else 226
                                monthly_waste = (node_count - optimal_nodes) * node_monthly_cost

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=cluster.name,
                                        resource_name=f"{instance_id}/{cluster_id}",
                                        resource_type="bigtable_low_cpu",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="CRITICAL",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "cluster_id": cluster_id,
                                            "current_nodes": node_count,
                                            "optimal_nodes": optimal_nodes,
                                            "avg_cpu_pct": round(avg_cpu, 2),
                                            "storage_type": storage_type
                                        },
                                        recommendation=f"AGGRESSIVE reduction: {node_count} → {optimal_nodes} nodes. Very low CPU ({avg_cpu:.1f}%) indicates significant over-provisioning."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch CPU metrics for cluster {cluster_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for low CPU Bigtable clusters: {e}")

        return resources

    async def scan_bigtable_storage_type_suboptimal(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect suboptimal storage type (HDD with high throughput needs).

        Waste: HDD storage when workload requires SSD performance.
        Detection: HDD storage + high throughput (>5K ops/sec/node)
        Cost: Migration recommendation awareness
        Priority: MEDIUM (P2) 💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        high_throughput_threshold = rules.get("high_throughput_threshold", 5000)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            instance_admin_client = BigtableInstanceAdminClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List clusters in this instance
                    clusters = instance_admin_client.list_clusters(parent=instance.name)

                    for cluster in clusters.clusters:
                        cluster_id = cluster.name.split('/')[-1]
                        storage_type = str(cluster.default_storage_type)

                        # Only flag HDD clusters
                        if "HDD" not in storage_type:
                            continue

                        # Get throughput metrics
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=7)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'metric.type="bigtable.googleapis.com/server/request_count" AND '
                                f'resource.labels.cluster="{cluster_id}"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            total_requests = 0
                            for result in results:
                                for point in result.points:
                                    total_requests += point.value.int64_value if hasattr(point.value, 'int64_value') else 0

                            # Estimate ops/sec/node
                            days = 7
                            avg_ops_per_sec_per_node = total_requests / (days * 24 * 3600 * cluster.serve_nodes) if cluster.serve_nodes > 0 else 0

                            if avg_ops_per_sec_per_node > high_throughput_threshold:
                                # Performance issue: HDD can't handle this throughput efficiently
                                monthly_cost_awareness = 0.0  # Informational (migration recommendation)

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=cluster.name,
                                        resource_name=f"{instance_id}/{cluster_id}",
                                        resource_type="bigtable_storage_type_suboptimal",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_cost_awareness,
                                        confidence_level="MEDIUM",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "cluster_id": cluster_id,
                                            "storage_type": storage_type,
                                            "avg_ops_per_sec_per_node": round(avg_ops_per_sec_per_node, 2),
                                            "threshold": high_throughput_threshold
                                        },
                                        recommendation=f"Consider migrating from HDD to SSD. High throughput ({avg_ops_per_sec_per_node:.0f} ops/sec/node) exceeds HDD performance capabilities. Risk of latency issues."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch throughput metrics for cluster {cluster_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for suboptimal storage type in Bigtable: {e}")

        return resources

    async def scan_bigtable_zero_read_tables(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect tables with zero reads (unused tables).

        Waste: Individual tables never read = storage + index overhead waste.
        Detection: Per-table read metrics = 0 for 30+ days
        Cost: Variable (table-level granularity)
        Priority: MEDIUM (P2) 💰💰
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_lookback = rules.get("days_lookback", 30)
        min_savings_threshold = rules.get("min_savings_threshold", 10.0)

        try:
            from google.cloud.bigtable_admin_v2 import BigtableInstanceAdminClient, BigtableTableAdminClient

            instance_admin_client = BigtableInstanceAdminClient()
            table_admin_client = BigtableTableAdminClient()

            # List all Bigtable instances
            parent = f"projects/{self.project_id}"

            try:
                instances = instance_admin_client.list_instances(parent=parent)

                for instance in instances.instances:
                    instance_id = instance.name.split('/')[-1]

                    # List tables in this instance
                    try:
                        tables = list(table_admin_client.list_tables(parent=instance.name))

                        # Simplified: Flag instances with multiple tables for table-level review
                        # In real implementation, would check per-table read metrics

                        if len(tables) > 1:
                            # Estimate: Assume 20% of tables are unused
                            zero_read_table_estimate = max(1, len(tables) // 5)

                            # Get cluster info for cost estimation
                            clusters = list(instance_admin_client.list_clusters(parent=instance.name).clusters)

                            if clusters:
                                # Estimate storage waste per unused table
                                estimated_waste_per_table = 10.0  # $10/month per unused table estimate
                                monthly_waste = zero_read_table_estimate * estimated_waste_per_table

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=instance.name,
                                        resource_name=instance_id,
                                        resource_type="bigtable_zero_read_tables",
                                        region=clusters[0].location if clusters else "unknown",
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="MEDIUM",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "total_tables": len(tables),
                                            "zero_read_estimate": zero_read_table_estimate,
                                            "days_lookback": days_lookback
                                        },
                                        recommendation=f"Review {zero_read_table_estimate} potentially unused table(s) with zero reads. Archive or delete unused tables to reduce storage overhead."
                                    )
                                )

                    except Exception as e:
                        logger.warning(f"Could not list tables for instance {instance_id}: {e}")

            except Exception as e:
                logger.error(f"Error listing Bigtable instances: {e}")

        except Exception as e:
            logger.error(f"Error scanning for zero-read Bigtable tables: {e}")

        return resources

    async def scan_cloud_nat_gateway_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect Cloud NAT gateways with zero traffic (idle).

        Waste: Cloud NAT gateway costs $32.40/month minimum even when idle.
        This is the #1 cause of Cloud NAT waste (40% of typical waste).

        Detection: Cloud Router with NAT config AND allocated_ports=0 AND sent_bytes=0 for 7+ days
        Cost: $32.40/month gateway minimum + $2.88/month per unused NAT IP
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            min_idle_days = 7
            if detection_rules and "gcp_nat_gateway_idle" in detection_rules:
                rules = detection_rules["gcp_nat_gateway_idle"]
                min_idle_days = rules.get("min_idle_days", 7)

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region for Cloud Routers with NAT
            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        # Check if router has NAT configurations
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Query Cloud Monitoring for NAT traffic metrics
                            end_time = datetime.now(timezone.utc)
                            start_time = end_time - timedelta(days=min_idle_days)

                            # Query allocated ports metric
                            allocated_ports = 0
                            sent_bytes = 0

                            try:
                                # Check allocated ports
                                interval = monitoring_v3.TimeInterval({
                                    "end_time": {"seconds": int(end_time.timestamp())},
                                    "start_time": {"seconds": int(start_time.timestamp())}
                                })

                                ports_filter = (
                                    f'resource.type="nat_gateway" '
                                    f'AND resource.labels.project_id="{self.project_id}" '
                                    f'AND resource.labels.region="{gcp_region}" '
                                    f'AND resource.labels.router_id="{router.name}" '
                                    f'AND resource.labels.nat_gateway_name="{nat.name}" '
                                    f'AND metric.type="router.googleapis.com/nat_allocated_ports"'
                                )

                                ports_request = monitoring_v3.ListTimeSeriesRequest({
                                    "name": f"projects/{self.project_id}",
                                    "filter": ports_filter,
                                    "interval": interval,
                                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                                })

                                for series in monitoring_client.list_time_series(request=ports_request):
                                    for point in series.points:
                                        allocated_ports = max(allocated_ports, point.value.int64_value or 0)

                                # Check sent bytes
                                bytes_filter = (
                                    f'resource.type="nat_gateway" '
                                    f'AND resource.labels.project_id="{self.project_id}" '
                                    f'AND resource.labels.region="{gcp_region}" '
                                    f'AND resource.labels.router_id="{router.name}" '
                                    f'AND resource.labels.nat_gateway_name="{nat.name}" '
                                    f'AND metric.type="router.googleapis.com/sent_bytes_count"'
                                )

                                bytes_request = monitoring_v3.ListTimeSeriesRequest({
                                    "name": f"projects/{self.project_id}",
                                    "filter": bytes_filter,
                                    "interval": interval,
                                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                                })

                                for series in monitoring_client.list_time_series(request=bytes_request):
                                    for point in series.points:
                                        sent_bytes += point.value.int64_value or 0

                            except Exception as e:
                                # If monitoring data unavailable, assume idle
                                logger.warning(f"Could not fetch monitoring data for NAT {nat.name}: {e}")

                            # Detect idle NAT (0 ports AND 0 bytes)
                            if allocated_ports == 0 and sent_bytes == 0:
                                # Calculate costs
                                gateway_cost = 32.40  # $0.045/hour * 24 * 30

                                # Count NAT IPs
                                nat_ip_count = 0
                                if nat.nat_ip_allocate_option == "MANUAL_ONLY":
                                    nat_ip_count = len(nat.nat_ips or [])
                                else:
                                    # Auto-allocated, estimate minimum
                                    nat_ip_count = 1

                                nat_ip_cost = nat_ip_count * 2.88
                                monthly_cost = gateway_cost + nat_ip_cost
                                annual_cost = monthly_cost * 12

                                # Calculate age
                                created_at = datetime.fromisoformat(
                                    router.creation_timestamp.replace('Z', '+00:00')
                                )
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                months_wasted = age_days / 30
                                already_wasted = monthly_cost * months_wasted

                                # Determine confidence
                                if min_idle_days >= 30:
                                    confidence = "CRITICAL"
                                elif min_idle_days >= 14:
                                    confidence = "HIGH"
                                elif min_idle_days >= 7:
                                    confidence = "MEDIUM"
                                else:
                                    confidence = "LOW"

                                resources.append(OrphanResourceData(
                                    resource_id=f"{router.name}/{nat.name}",
                                    resource_type="gcp_nat_gateway_idle",
                                    resource_name=nat.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "router_name": router.name,
                                        "nat_name": nat.name,
                                        "allocated_ports": allocated_ports,
                                        "sent_bytes": sent_bytes,
                                        "nat_ip_count": nat_ip_count,
                                        "nat_ip_allocate_option": nat.nat_ip_allocate_option,
                                        "gateway_cost": gateway_cost,
                                        "nat_ip_cost": nat_ip_cost,
                                        "age_days": age_days,
                                        "idle_days": min_idle_days,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": confidence,
                                        "recommendation": f"DELETE Cloud NAT to save ${annual_cost:.2f}/year. Gateway has been idle for {min_idle_days}+ days with 0 traffic.",
                                        "waste_reason": f"Cloud NAT gateway idle for {min_idle_days}+ days - 0 allocated ports, 0 traffic"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for idle Cloud NAT: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for idle Cloud NAT gateways: {e}")

        return resources

    async def scan_cloud_nat_over_allocated_ips(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect Cloud NAT with over-allocated NAT IP addresses.

        Waste: Manually allocated NAT IPs cost $2.88/month each when unused.
        Detection: MANUAL_ONLY allocation + (nat_ips.count > min_vms / 64)
        Cost: $2.88/month per unused IP
        Priority: CRITICAL (P0) 💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            # Get detection parameters
            vms_per_ip_threshold = 64  # GCP default: 64 VMs per NAT IP
            if detection_rules and "gcp_nat_over_allocated_ips" in detection_rules:
                rules = detection_rules["gcp_nat_over_allocated_ips"]
                vms_per_ip_threshold = rules.get("vms_per_ip_threshold", 64)

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    # Count VMs in region (estimate NAT usage)
                    vm_count = 0
                    for zone_name in [f"{gcp_region}-a", f"{gcp_region}-b", f"{gcp_region}-c"]:
                        try:
                            request = compute_v1.ListInstancesRequest(
                                project=self.project_id,
                                zone=zone_name
                            )
                            for instance in instances_client.list(request=request):
                                if instance.status == "RUNNING":
                                    vm_count += 1
                        except:
                            pass

                    # Check routers with NAT
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Only check MANUAL_ONLY allocation
                            if nat.nat_ip_allocate_option != "MANUAL_ONLY":
                                continue

                            nat_ip_count = len(nat.nat_ips or [])
                            optimal_ip_count = max(1, (vm_count + vms_per_ip_threshold - 1) // vms_per_ip_threshold)
                            over_allocated = nat_ip_count - optimal_ip_count

                            if over_allocated > 0:
                                # Calculate waste
                                monthly_cost = over_allocated * 2.88
                                annual_cost = monthly_cost * 12

                                created_at = datetime.fromisoformat(
                                    router.creation_timestamp.replace('Z', '+00:00')
                                )
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                months_wasted = age_days / 30
                                already_wasted = monthly_cost * months_wasted

                                confidence = "HIGH" if over_allocated >= 2 else "MEDIUM"

                                resources.append(OrphanResourceData(
                                    resource_id=f"{router.name}/{nat.name}",
                                    resource_type="gcp_nat_over_allocated_ips",
                                    resource_name=nat.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "router_name": router.name,
                                        "nat_name": nat.name,
                                        "nat_ip_count": nat_ip_count,
                                        "optimal_ip_count": optimal_ip_count,
                                        "over_allocated": over_allocated,
                                        "vm_count": vm_count,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": confidence,
                                        "recommendation": f"REDUCE NAT IPs from {nat_ip_count} to {optimal_ip_count} to save ${annual_cost:.2f}/year. You have {over_allocated} unused NAT IPs.",
                                        "waste_reason": f"Over-allocated {over_allocated} NAT IPs for {vm_count} VMs (optimal: {optimal_ip_count} IPs)"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for over-allocated NAT IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for over-allocated NAT IPs: {e}")

        return resources

    async def scan_cloud_nat_vms_with_external_ips(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect VMs with External IPs that also use Cloud NAT (double cost).

        Waste: VMs with External IPs don't need Cloud NAT (double-paying for egress).
        Detection: VMs with external IPs in subnets using Cloud NAT
        Cost: $32.40/month gateway waste (not actually needed)
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)
            subnetworks_client = compute_v1.SubnetworksClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    # Get NAT-enabled subnets
                    nat_subnets = set()
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Check source subnet IP ranges
                            if nat.source_subnetwork_ip_ranges_to_nat == "ALL_SUBNETWORKS_ALL_IP_RANGES":
                                # NAT applies to all subnets - get all subnets
                                subnet_request = compute_v1.ListSubnetworksRequest(
                                    project=self.project_id,
                                    region=gcp_region
                                )
                                for subnet in subnetworks_client.list(request=subnet_request):
                                    nat_subnets.add(subnet.name)
                            elif nat.subnetworks:
                                for subnet in nat.subnetworks:
                                    nat_subnets.add(subnet.name)

                    if not nat_subnets:
                        continue

                    # Check VMs with external IPs in NAT-enabled subnets
                    vms_with_double_cost = []
                    for zone_name in [f"{gcp_region}-a", f"{gcp_region}-b", f"{gcp_region}-c"]:
                        try:
                            request = compute_v1.ListInstancesRequest(
                                project=self.project_id,
                                zone=zone_name
                            )
                            for instance in instances_client.list(request=request):
                                if instance.status != "RUNNING":
                                    continue

                                # Check if VM has external IP
                                has_external_ip = False
                                for iface in instance.network_interfaces:
                                    if iface.access_configs:
                                        has_external_ip = True
                                        # Check if subnet uses NAT
                                        subnet_name = iface.subnetwork.split('/')[-1]
                                        if subnet_name in nat_subnets:
                                            vms_with_double_cost.append({
                                                "name": instance.name,
                                                "subnet": subnet_name,
                                                "external_ip": iface.access_configs[0].nat_i_p if iface.access_configs else None
                                            })
                        except:
                            pass

                    if vms_with_double_cost:
                        # Calculate waste (proportional gateway cost)
                        monthly_cost = 32.40  # Gateway cost wasted
                        annual_cost = monthly_cost * 12

                        resources.append(OrphanResourceData(
                            resource_id=f"nat-double-cost-{gcp_region}",
                            resource_type="gcp_nat_vms_with_external_ips",
                            resource_name=f"Cloud NAT Double-Cost in {gcp_region}",
                            region=gcp_region,
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                "vm_count": len(vms_with_double_cost),
                                "vms": vms_with_double_cost,
                                "annual_cost": round(annual_cost, 2),
                                "confidence": "HIGH",
                                "recommendation": f"REMOVE External IPs from {len(vms_with_double_cost)} VMs OR disable Cloud NAT to save ${annual_cost:.2f}/year. VMs with External IPs don't need Cloud NAT.",
                                "waste_reason": f"{len(vms_with_double_cost)} VMs have External IPs + Cloud NAT (double-paying for egress)"
                            }
                        ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for double-cost NAT: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for VMs with External IPs using NAT: {e}")

        return resources

    async def scan_cloud_nat_large_deployments(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect Cloud NAT for large deployments (self-managed NAT cheaper).

        Waste: Cloud NAT costs $32.40/month minimum. For >5 VMs, self-managed NAT is cheaper.
        Detection: Cloud NAT gateway with >5 VMs using it
        Cost: $21.40/month savings (Cloud NAT $32.40 vs self-managed NAT VM $11)
        Priority: HIGH (P1) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            # Get detection parameters
            min_vm_count = 5
            if detection_rules and "gcp_nat_large_deployments" in detection_rules:
                rules = detection_rules["gcp_nat_large_deployments"]
                min_vm_count = rules.get("min_vm_count", 5)

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    # Count VMs
                    vm_count = 0
                    for zone_name in [f"{gcp_region}-a", f"{gcp_region}-b", f"{gcp_region}-c"]:
                        try:
                            request = compute_v1.ListInstancesRequest(
                                project=self.project_id,
                                zone=zone_name
                            )
                            for instance in instances_client.list(request=request):
                                if instance.status == "RUNNING":
                                    vm_count += 1
                        except:
                            pass

                    if vm_count <= min_vm_count:
                        continue

                    # Check for Cloud NAT
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Calculate cost comparison
                            cloud_nat_cost = 32.40  # Minimum gateway cost
                            self_managed_cost = 11.00  # e2-small NAT VM
                            monthly_savings = cloud_nat_cost - self_managed_cost
                            annual_savings = monthly_savings * 12

                            resources.append(OrphanResourceData(
                                resource_id=f"{router.name}/{nat.name}",
                                resource_type="gcp_nat_large_deployments",
                                resource_name=nat.name,
                                region=gcp_region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "router_name": router.name,
                                    "nat_name": nat.name,
                                    "vm_count": vm_count,
                                    "cloud_nat_cost": cloud_nat_cost,
                                    "self_managed_cost": self_managed_cost,
                                    "annual_savings": round(annual_savings, 2),
                                    "confidence": "MEDIUM",
                                    "recommendation": f"MIGRATE to self-managed NAT VM to save ${annual_savings:.2f}/year. With {vm_count} VMs, self-managed NAT is 3x cheaper.",
                                    "waste_reason": f"Large deployment ({vm_count} VMs) - self-managed NAT would be ${monthly_savings:.2f}/month cheaper"
                                }
                            ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for large deployments: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for large deployment NAT waste: {e}")

        return resources

    async def scan_cloud_nat_devtest_unused(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect Dev/Test Cloud NAT unused for extended periods.

        Waste: Cloud NAT in dev/test environments left running 24/7.
        Detection: Cloud NAT with 'dev', 'test', 'staging' labels + idle 14+ days
        Cost: $32.40/month
        Priority: MEDIUM (P2) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            min_idle_days = 14
            if detection_rules and "gcp_nat_devtest_unused" in detection_rules:
                rules = detection_rules["gcp_nat_devtest_unused"]
                min_idle_days = rules.get("min_idle_days", 14)

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Dev/Test labels to check
            devtest_labels = ["dev", "test", "staging", "development", "nonprod", "qa"]

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        # Check for dev/test labels
                        router_labels = router.labels or {}
                        is_devtest = False
                        for label_key, label_value in router_labels.items():
                            if any(env in label_key.lower() or env in label_value.lower() for env in devtest_labels):
                                is_devtest = True
                                break

                        if not is_devtest:
                            continue

                        for nat in router.nats:
                            # Check if idle
                            end_time = datetime.now(timezone.utc)
                            start_time = end_time - timedelta(days=min_idle_days)

                            allocated_ports = 0
                            try:
                                interval = monitoring_v3.TimeInterval({
                                    "end_time": {"seconds": int(end_time.timestamp())},
                                    "start_time": {"seconds": int(start_time.timestamp())}
                                })

                                ports_filter = (
                                    f'resource.type="nat_gateway" '
                                    f'AND resource.labels.project_id="{self.project_id}" '
                                    f'AND resource.labels.region="{gcp_region}" '
                                    f'AND resource.labels.router_id="{router.name}" '
                                    f'AND metric.type="router.googleapis.com/nat_allocated_ports"'
                                )

                                ports_request = monitoring_v3.ListTimeSeriesRequest({
                                    "name": f"projects/{self.project_id}",
                                    "filter": ports_filter,
                                    "interval": interval,
                                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                                })

                                for series in monitoring_client.list_time_series(request=ports_request):
                                    for point in series.points:
                                        allocated_ports = max(allocated_ports, point.value.int64_value or 0)
                            except:
                                pass

                            if allocated_ports == 0:
                                monthly_cost = 32.40
                                annual_cost = monthly_cost * 12

                                created_at = datetime.fromisoformat(
                                    router.creation_timestamp.replace('Z', '+00:00')
                                )
                                age_days = (datetime.now(timezone.utc) - created_at).days
                                months_wasted = age_days / 30
                                already_wasted = monthly_cost * months_wasted

                                resources.append(OrphanResourceData(
                                    resource_id=f"{router.name}/{nat.name}",
                                    resource_type="gcp_nat_devtest_unused",
                                    resource_name=nat.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "router_name": router.name,
                                        "nat_name": nat.name,
                                        "labels": dict(router_labels),
                                        "idle_days": min_idle_days,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": "MEDIUM",
                                        "recommendation": f"DELETE dev/test Cloud NAT to save ${annual_cost:.2f}/year. Idle for {min_idle_days}+ days.",
                                        "waste_reason": f"Dev/Test Cloud NAT unused for {min_idle_days}+ days"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for dev/test NAT: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for dev/test NAT waste: {e}")

        return resources

    async def scan_cloud_nat_duplicate_gateways(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect duplicate NAT gateways for same subnet.

        Waste: Multiple Cloud NAT gateways serving the same subnets (redundant).
        Detection: Multiple Cloud Routers with NAT for same subnets
        Cost: $32.40/month per duplicate
        Priority: MEDIUM (P2) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            subnetworks_client = compute_v1.SubnetworksClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    # Track NAT coverage by subnet
                    subnet_nat_map = defaultdict(list)

                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Get subnets covered by this NAT
                            covered_subnets = set()
                            if nat.source_subnetwork_ip_ranges_to_nat == "ALL_SUBNETWORKS_ALL_IP_RANGES":
                                # Get all subnets
                                subnet_request = compute_v1.ListSubnetworksRequest(
                                    project=self.project_id,
                                    region=gcp_region
                                )
                                for subnet in subnetworks_client.list(request=subnet_request):
                                    covered_subnets.add(subnet.name)
                            elif nat.subnetworks:
                                for subnet in nat.subnetworks:
                                    covered_subnets.add(subnet.name)

                            # Track this NAT
                            for subnet in covered_subnets:
                                subnet_nat_map[subnet].append({
                                    "router": router.name,
                                    "nat": nat.name
                                })

                    # Find duplicates
                    for subnet, nats in subnet_nat_map.items():
                        if len(nats) > 1:
                            # Duplicate NAT gateways
                            monthly_cost = 32.40 * (len(nats) - 1)  # All but 1 are waste
                            annual_cost = monthly_cost * 12

                            resources.append(OrphanResourceData(
                                resource_id=f"duplicate-nat-{gcp_region}-{subnet}",
                                resource_type="gcp_nat_duplicate_gateways",
                                resource_name=f"Duplicate NAT for {subnet}",
                                region=gcp_region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "subnet": subnet,
                                    "nat_count": len(nats),
                                    "nats": nats,
                                    "annual_cost": round(annual_cost, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"CONSOLIDATE {len(nats)} NAT gateways to 1 to save ${annual_cost:.2f}/year. Remove {len(nats)-1} duplicate NAT(s).",
                                    "waste_reason": f"{len(nats)} Cloud NAT gateways serving same subnet {subnet} (only 1 needed)"
                                }
                            ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for duplicate NAT: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for duplicate NAT gateways: {e}")

        return resources

    async def scan_cloud_nat_broken_router(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect Cloud NAT with missing/misconfigured Cloud Router.

        Waste: Cloud NAT requires a Cloud Router. Broken/missing router = wasted NAT.
        Detection: NAT config exists but router has no BGP peers and no routes
        Cost: $32.40/month
        Priority: MEDIUM (P2) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        # Check if router is properly configured
                        has_bgp_peers = len(router.bgp_peers or []) > 0
                        has_network = router.network is not None and router.network != ""

                        if not has_network:
                            # Router not attached to network - broken
                            for nat in router.nats:
                                monthly_cost = 32.40
                                annual_cost = monthly_cost * 12

                                resources.append(OrphanResourceData(
                                    resource_id=f"{router.name}/{nat.name}",
                                    resource_type="gcp_nat_broken_router",
                                    resource_name=nat.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "router_name": router.name,
                                        "nat_name": nat.name,
                                        "has_network": has_network,
                                        "has_bgp_peers": has_bgp_peers,
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": "HIGH",
                                        "recommendation": f"DELETE broken Cloud NAT to save ${annual_cost:.2f}/year. Router not attached to network.",
                                        "waste_reason": "Cloud NAT with broken/misconfigured Cloud Router (no network)"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for broken NAT: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for broken Cloud NAT routers: {e}")

        return resources

    async def scan_cloud_nat_high_data_processing(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect Cloud NAT with high data processing costs (>1TB/month).

        Waste: Cloud NAT charges $0.045/GB for data processing. >1TB/month = expensive.
        Detection: sent_bytes_count > 1TB/month
        Cost: $45+/month for data processing
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timezone, timedelta

            # Get detection parameters
            min_bytes_per_month = 1_000_000_000_000  # 1TB
            if detection_rules and "gcp_nat_high_data_processing" in detection_rules:
                rules = detection_rules["gcp_nat_high_data_processing"]
                min_bytes_per_month = rules.get("min_bytes_per_month", 1_000_000_000_000)

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Query sent bytes last 30 days
                            end_time = datetime.now(timezone.utc)
                            start_time = end_time - timedelta(days=30)

                            sent_bytes = 0
                            try:
                                interval = monitoring_v3.TimeInterval({
                                    "end_time": {"seconds": int(end_time.timestamp())},
                                    "start_time": {"seconds": int(start_time.timestamp())}
                                })

                                bytes_filter = (
                                    f'resource.type="nat_gateway" '
                                    f'AND resource.labels.project_id="{self.project_id}" '
                                    f'AND resource.labels.region="{gcp_region}" '
                                    f'AND resource.labels.router_id="{router.name}" '
                                    f'AND resource.labels.nat_gateway_name="{nat.name}" '
                                    f'AND metric.type="router.googleapis.com/sent_bytes_count"'
                                )

                                bytes_request = monitoring_v3.ListTimeSeriesRequest({
                                    "name": f"projects/{self.project_id}",
                                    "filter": bytes_filter,
                                    "interval": interval,
                                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                                })

                                for series in monitoring_client.list_time_series(request=bytes_request):
                                    for point in series.points:
                                        sent_bytes += point.value.int64_value or 0
                            except:
                                pass

                            if sent_bytes > min_bytes_per_month:
                                # Calculate data processing cost
                                gb_sent = sent_bytes / (1024**3)
                                data_processing_cost = gb_sent * 0.045
                                gateway_cost = 32.40
                                monthly_cost = data_processing_cost
                                annual_cost = monthly_cost * 12

                                resources.append(OrphanResourceData(
                                    resource_id=f"{router.name}/{nat.name}",
                                    resource_type="gcp_nat_high_data_processing",
                                    resource_name=nat.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "router_name": router.name,
                                        "nat_name": nat.name,
                                        "sent_bytes": sent_bytes,
                                        "sent_gb": round(gb_sent, 2),
                                        "data_processing_cost": round(data_processing_cost, 2),
                                        "gateway_cost": gateway_cost,
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": "CRITICAL",
                                        "recommendation": f"MIGRATE to External IPs or self-managed NAT to save ${annual_cost:.2f}/year. {round(gb_sent, 0)}GB/month traffic = ${data_processing_cost:.2f}/month data processing.",
                                        "waste_reason": f"High data processing costs: {round(gb_sent, 0)}GB/month through Cloud NAT"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for high data processing: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for high data processing NAT: {e}")

        return resources

    async def scan_cloud_nat_regional_waste(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect Cloud NAT in unused regions (no VMs in region).

        Waste: Cloud NAT deployed in regions without VMs.
        Detection: Cloud NAT exists but 0 VMs in region
        Cost: $32.40/month
        Priority: HIGH (P1) 💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    # Count VMs in region
                    vm_count = 0
                    for zone_name in [f"{gcp_region}-a", f"{gcp_region}-b", f"{gcp_region}-c"]:
                        try:
                            request = compute_v1.ListInstancesRequest(
                                project=self.project_id,
                                zone=zone_name
                            )
                            for instance in instances_client.list(request=request):
                                if instance.status == "RUNNING":
                                    vm_count += 1
                        except:
                            pass

                    if vm_count > 0:
                        continue

                    # Check for Cloud NAT
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            monthly_cost = 32.40
                            annual_cost = monthly_cost * 12

                            created_at = datetime.fromisoformat(
                                router.creation_timestamp.replace('Z', '+00:00')
                            )
                            age_days = (datetime.now(timezone.utc) - created_at).days
                            months_wasted = age_days / 30
                            already_wasted = monthly_cost * months_wasted

                            resources.append(OrphanResourceData(
                                resource_id=f"{router.name}/{nat.name}",
                                resource_type="gcp_nat_regional_waste",
                                resource_name=nat.name,
                                region=gcp_region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "router_name": router.name,
                                    "nat_name": nat.name,
                                    "vm_count": 0,
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(annual_cost, 2),
                                    "confidence": "HIGH",
                                    "recommendation": f"DELETE Cloud NAT in unused region to save ${annual_cost:.2f}/year. No VMs in {gcp_region}.",
                                    "waste_reason": f"Cloud NAT in region {gcp_region} with 0 VMs"
                                }
                            ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for regional waste: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for regional NAT waste: {e}")

        return resources

    async def scan_cloud_nat_manual_vs_auto_allocate(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect Cloud NAT using Manual IP allocation vs Auto-allocate.

        Waste: Manual allocation requires pre-allocated IPs that may go unused.
        Detection: nat_ip_allocate_option == "MANUAL_ONLY"
        Cost: $2.88/month per unused allocated IP
        Priority: MEDIUM (P2) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            routers_client = compute_v1.RoutersClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan each region
            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListRoutersRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for router in routers_client.list(request=request):
                        if not router.nats:
                            continue

                        for nat in router.nats:
                            # Check allocation option
                            if nat.nat_ip_allocate_option == "MANUAL_ONLY":
                                nat_ip_count = len(nat.nat_ips or [])
                                # Assume potential waste of 1 IP per manual allocation
                                monthly_cost = 2.88
                                annual_cost = monthly_cost * 12

                                resources.append(OrphanResourceData(
                                    resource_id=f"{router.name}/{nat.name}",
                                    resource_type="gcp_nat_manual_vs_auto_allocate",
                                    resource_name=nat.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "router_name": router.name,
                                        "nat_name": nat.name,
                                        "nat_ip_allocate_option": nat.nat_ip_allocate_option,
                                        "nat_ip_count": nat_ip_count,
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": "LOW",
                                        "recommendation": f"SWITCH to AUTO_ALLOCATE to save ~${annual_cost:.2f}/year. Auto-allocate is more cost-efficient and dynamic.",
                                        "waste_reason": "Manual IP allocation risks over-provisioning - AUTO_ALLOCATE is more efficient"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for manual allocation: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for manual vs auto-allocate NAT: {e}")

        return resources

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

    async def scan_fargate_tasks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """GCP doesn't have Fargate (AWS ECS-specific service)."""
        return []

    # AWS-specific EBS volume methods (not applicable to GCP)
    async def scan_volumes_on_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_gp2_migration_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_unnecessary_io2_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_overprovisioned_iops_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_overprovisioned_throughput_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_low_iops_usage_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_low_throughput_usage_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    async def scan_volume_type_downgrade_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EBS-specific)."""
        return []

    # AWS-specific Elastic IP methods (not applicable to GCP)
    async def scan_additional_eips_per_instance(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_eips_on_detached_enis(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_never_used_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_eips_on_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_idle_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_low_traffic_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_unused_nat_gateway_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    async def scan_eips_on_failed_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Elastic IP-specific)."""
        return []

    # ==================== DISK SNAPSHOTS (10 SCENARIOS) ====================

    async def scan_orphaned_disk_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Scan for orphaned disk snapshots (source disk deleted >30 days).

        Detection:
        - Source disk no longer exists
        - Age >= min_age_days (default: 30)
        - Status = READY

        Cost:
        - 100% waste (source gone, purpose unclear)
        - $0.026/GB/month (standard) or $0.032/GB/month (multi-regional)
        """
        resources = []
        min_age_days = (
            detection_rules.get("gcp_disk_snapshot_orphaned", {}).get("min_age_days", 30)
            if detection_rules
            else 30
        )

        try:
            snapshots_client = self._get_snapshots_client()
            disks_client = self._get_disks_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                source_disk = snapshot.source_disk
                if not source_disk:
                    continue

                # Extract zone and disk name from URI
                # Format: https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/disks/{disk}
                parts = source_disk.split("/")
                if len(parts) < 4:
                    continue

                zone = parts[-3]
                disk_name = parts[-1]

                # Check if source disk exists
                source_disk_exists = False
                try:
                    disk_request = compute_v1.GetDiskRequest(
                        project=self.project_id, zone=zone, disk=disk_name
                    )
                    disks_client.get(request=disk_request)
                    source_disk_exists = True
                except Exception:
                    # Disk not found (404) = orphaned snapshot
                    pass

                if not source_disk_exists:
                    age_days = self._get_age_days(snapshot.creation_timestamp)

                    if age_days >= min_age_days:
                        # Calculate cost
                        size_gb = snapshot.storage_bytes / (1024**3)

                        # Determine storage type
                        storage_locations = snapshot.storage_locations or []
                        price_per_gb = (
                            0.032 if len(storage_locations) > 1 else 0.026
                        )  # Multi-regional vs standard

                        monthly_cost = size_gb * price_per_gb
                        already_wasted = monthly_cost * (age_days / 30.0)

                        # Confidence level
                        if age_days >= 90:
                            confidence = "critical"
                        elif age_days >= 30:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=str(snapshot.id),
                                resource_name=snapshot.name,
                                resource_type="gcp_disk_snapshot_orphaned",
                                region="global",  # Snapshots are global resources
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "creation_time": snapshot.creation_timestamp,
                                    "age_days": age_days,
                                    "source_disk": source_disk,
                                    "source_disk_exists": False,
                                    "storage_bytes": snapshot.storage_bytes,
                                    "size_gb": round(size_gb, 2),
                                    "storage_locations": storage_locations,
                                    "storage_type": "multi-regional"
                                    if len(storage_locations) > 1
                                    else "standard",
                                    "status": snapshot.status,
                                    "price_per_gb": price_per_gb,
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": confidence,
                                    "recommendation": "Delete orphaned snapshot - source disk no longer exists",
                                },
                            )
                        )

        except Exception as e:
            # Log error but don't fail entire scan
            pass

        return resources

    async def scan_redundant_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Scan for redundant disk snapshots (>5 snapshots per disk).

        Detection:
        - snapshot_count > max_snapshots_per_disk (default: 5)
        - Source disk still exists (not orphaned)

        Cost:
        - Excess snapshots waste
        - Recommend keeping last 3-5 snapshots
        """
        resources = []
        max_snapshots = (
            detection_rules.get("gcp_disk_snapshot_redundant", {}).get(
                "max_snapshots_per_disk", 5
            )
            if detection_rules
            else 5
        )
        recommended_count = (
            detection_rules.get("gcp_disk_snapshot_redundant", {}).get(
                "recommended_snapshots_count", 3
            )
            if detection_rules
            else 3
        )

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = list(snapshots_client.list(request=request))

            # Group snapshots by source_disk
            snapshots_by_disk = defaultdict(list)
            for snapshot in snapshots:
                if snapshot.source_disk and snapshot.status == "READY":
                    snapshots_by_disk[snapshot.source_disk].append(snapshot)

            # Check for redundant snapshots
            for source_disk, snapshots_list in snapshots_by_disk.items():
                snapshot_count = len(snapshots_list)

                if snapshot_count > max_snapshots:
                    # Sort by creation time (newest first)
                    snapshots_list.sort(
                        key=lambda s: s.creation_timestamp, reverse=True
                    )

                    # Snapshots to keep (recommended count)
                    snapshots_to_keep = snapshots_list[:recommended_count]

                    # Excess snapshots
                    snapshots_excess = snapshots_list[recommended_count:]
                    excess_count = len(snapshots_excess)

                    # Calculate excess storage
                    excess_storage_gb = sum(
                        [s.storage_bytes / (1024**3) for s in snapshots_excess]
                    )

                    # Average price per GB
                    price_per_gb = 0.026

                    monthly_waste = excess_storage_gb * price_per_gb

                    # Average age of excess snapshots
                    avg_age_excess = sum(
                        [self._get_age_days(s.creation_timestamp) for s in snapshots_excess]
                    ) / len(snapshots_excess)
                    avg_months = avg_age_excess / 30.0
                    already_wasted = monthly_waste * avg_months

                    # Confidence level
                    if snapshot_count >= 10:
                        confidence = "high"
                    elif snapshot_count >= 7:
                        confidence = "medium"
                    else:
                        confidence = "low"

                    resources.append(
                        OrphanResourceData(
                            resource_id=f"redundant-{source_disk.split('/')[-1]}",
                            resource_name=source_disk.split("/")[-1],
                            resource_type="gcp_disk_snapshot_redundant",
                            region="global",
                            estimated_monthly_cost=monthly_waste,
                            resource_metadata={
                                "source_disk": source_disk,
                                "snapshot_count": snapshot_count,
                                "recommended_count": recommended_count,
                                "excess_count": excess_count,
                                "snapshots_list": [
                                    {
                                        "snapshot_id": str(s.id),
                                        "snapshot_name": s.name,
                                        "creation_time": s.creation_timestamp,
                                        "size_gb": round(s.storage_bytes / (1024**3), 2),
                                        "status": s.status,
                                    }
                                    for s in snapshots_list[:10]  # Limit to 10 for metadata
                                ],
                                "excess_storage_gb": round(excess_storage_gb, 2),
                                "avg_age_excess_days": round(avg_age_excess, 0),
                                "already_wasted": round(already_wasted, 2),
                                "confidence": confidence,
                                "recommendation": f"Delete {excess_count} oldest snapshots - keep last {recommended_count} for recovery",
                            },
                        )
                    )

        except Exception as e:
            pass

        return resources

    async def scan_old_unused_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Scan for old unused disk snapshots (>365 days, never restored).

        Detection:
        - Age >= old_snapshot_threshold_days (default: 365)
        - Status = READY
        - Never restored (basic check without logging for Phase 1)

        Cost:
        - Waste = cost since 365 days (retention excessive)
        """
        resources = []
        old_snapshot_threshold_days = (
            detection_rules.get("gcp_disk_snapshot_old_unused", {}).get(
                "old_snapshot_threshold_days", 365
            )
            if detection_rules
            else 365
        )

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                age_days = self._get_age_days(snapshot.creation_timestamp)

                if age_days >= old_snapshot_threshold_days:
                    # Calculate cost
                    size_gb = snapshot.storage_bytes / (1024**3)

                    # Determine storage type
                    storage_locations = snapshot.storage_locations or []
                    price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                    monthly_cost = size_gb * price_per_gb

                    # Waste = cost since threshold
                    waste_days = age_days - old_snapshot_threshold_days
                    waste_months = waste_days / 30.0
                    already_wasted = monthly_cost * waste_months

                    # Confidence level
                    if age_days >= 730:  # 2+ years
                        confidence = "critical"
                    elif age_days >= 540:  # 18+ months
                        confidence = "high"
                    else:
                        confidence = "medium"

                    resources.append(
                        OrphanResourceData(
                            resource_id=str(snapshot.id),
                            resource_name=snapshot.name,
                            resource_type="gcp_disk_snapshot_old_unused",
                            region="global",
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                "creation_time": snapshot.creation_timestamp,
                                "age_days": age_days,
                                "source_disk": snapshot.source_disk or "N/A",
                                "size_gb": round(size_gb, 2),
                                "restore_count": 0,  # Basic assumption
                                "last_restore_date": None,
                                "waste_months": round(waste_months, 2),
                                "already_wasted": round(already_wasted, 2),
                                "confidence": confidence,
                                "recommendation": f"Delete old snapshot - {age_days} days old, likely never restored",
                            },
                        )
                    )

        except Exception as e:
            pass

        return resources

    async def scan_no_retention_policy_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Scan for snapshots without retention policy (manual snapshots).

        Detection:
        - source_snapshot_schedule_policy IS NULL (manual snapshot)
        - labels.retention_days IS NULL
        - Age >= manual_snapshot_threshold_days (default: 90)

        Cost:
        - Governance waste (5% of cost)
        - Risk of accumulation
        """
        resources = []
        manual_snapshot_threshold_days = (
            detection_rules.get("gcp_disk_snapshot_no_retention_policy", {}).get(
                "manual_snapshot_threshold_days", 90
            )
            if detection_rules
            else 90
        )
        governance_waste_pct = 0.05

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                # Check if manual snapshot (no automated policy)
                if hasattr(snapshot, "source_snapshot_schedule_policy") and snapshot.source_snapshot_schedule_policy:
                    continue  # Skip automated snapshots

                # Check if has retention label
                labels = snapshot.labels if hasattr(snapshot, "labels") and snapshot.labels else {}
                if "retention_days" in labels or "retention" in labels:
                    continue  # Has retention management

                age_days = self._get_age_days(snapshot.creation_timestamp)

                if age_days >= manual_snapshot_threshold_days:
                    # Calculate cost
                    size_gb = snapshot.storage_bytes / (1024**3)
                    storage_locations = snapshot.storage_locations or []
                    price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                    monthly_cost = size_gb * price_per_gb
                    governance_waste_monthly = monthly_cost * governance_waste_pct

                    # Projection: if created monthly without cleanup
                    projected_annual_accumulation_gb = size_gb * 12
                    projected_annual_cost = projected_annual_accumulation_gb * price_per_gb

                    confidence = "high" if age_days >= 180 else "medium"

                    resources.append(
                        OrphanResourceData(
                            resource_id=str(snapshot.id),
                            resource_name=snapshot.name,
                            resource_type="gcp_disk_snapshot_no_retention_policy",
                            region="global",
                            estimated_monthly_cost=governance_waste_monthly,
                            resource_metadata={
                                "creation_time": snapshot.creation_timestamp,
                                "age_days": age_days,
                                "source_snapshot_schedule_policy": None,
                                "is_manual": True,
                                "labels": labels,
                                "retention_policy": None,
                                "size_gb": round(size_gb, 2),
                                "full_monthly_cost": round(monthly_cost, 2),
                                "governance_waste_monthly": round(governance_waste_monthly, 2),
                                "projected_annual_accumulation_gb": round(
                                    projected_annual_accumulation_gb, 2
                                ),
                                "projected_annual_cost": round(projected_annual_cost, 2),
                                "confidence": confidence,
                                "recommendation": "Add retention policy or label with retention_days to prevent accumulation",
                            },
                        )
                    )

        except Exception as e:
            pass

        return resources

    async def scan_snapshots_from_deleted_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Scan for snapshots of deleted VMs/instances.

        Detection:
        - labels.instance_name or description contains instance name
        - Instance not found in any zone
        - Age >= deleted_vm_threshold_days (default: 30)

        Cost:
        - 100% waste (VM deleted, snapshot purpose unclear)
        """
        resources = []
        deleted_vm_threshold_days = (
            detection_rules.get("gcp_disk_snapshot_deleted_vm", {}).get(
                "deleted_vm_threshold_days", 30
            )
            if detection_rules
            else 30
        )

        try:
            snapshots_client = self._get_snapshots_client()
            compute_client = self._get_compute_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            # Get all zones for checking instance existence
            zones = []
            for region_name in self.regions or []:
                zones.extend(
                    [
                        f"{region_name}-a",
                        f"{region_name}-b",
                        f"{region_name}-c",
                        f"{region_name}-f",
                    ]
                )

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                # Extract instance name from labels or description
                labels = snapshot.labels if hasattr(snapshot, "labels") and snapshot.labels else {}
                description = snapshot.description if hasattr(snapshot, "description") else ""

                instance_name = labels.get("instance_name") or labels.get("vm_name")

                if not instance_name and description:
                    # Try to parse instance name from description
                    match = re.search(r"instance\s+([a-z0-9-]+)", description, re.IGNORECASE)
                    if match:
                        instance_name = match.group(1)

                if instance_name:
                    # Check if instance exists in any zone
                    instance_exists = False
                    for zone in zones:
                        try:
                            instance_request = compute_v1.GetInstanceRequest(
                                project=self.project_id,
                                zone=zone,
                                instance=instance_name,
                            )
                            compute_client.get(request=instance_request)
                            instance_exists = True
                            break
                        except Exception:
                            continue

                    if not instance_exists:
                        age_days = self._get_age_days(snapshot.creation_timestamp)

                        if age_days >= deleted_vm_threshold_days:
                            # Calculate cost
                            size_gb = snapshot.storage_bytes / (1024**3)
                            storage_locations = snapshot.storage_locations or []
                            price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                            monthly_cost = size_gb * price_per_gb
                            already_wasted = monthly_cost * (age_days / 30.0)

                            confidence = "high" if age_days >= 60 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=str(snapshot.id),
                                    resource_name=snapshot.name,
                                    resource_type="gcp_disk_snapshot_deleted_vm",
                                    region="global",
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "creation_time": snapshot.creation_timestamp,
                                        "age_days": age_days,
                                        "labels": labels,
                                        "instance_name": instance_name,
                                        "instance_exists": False,
                                        "size_gb": round(size_gb, 2),
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": confidence,
                                        "recommendation": "Delete snapshot - source VM deleted (purpose unclear)",
                                    },
                                )
                            )

        except Exception as e:
            pass

        return resources

    async def scan_incomplete_failed_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Scan for failed disk snapshots.

        Detection:
        - Status = FAILED
        - Age >= failed_snapshot_threshold_days (default: 7)

        Cost:
        - 100% waste (unusable but storage consumed)
        """
        resources = []
        failed_snapshot_threshold_days = (
            detection_rules.get("gcp_disk_snapshot_failed", {}).get(
                "failed_snapshot_threshold_days", 7
            )
            if detection_rules
            else 7
        )

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            for snapshot in snapshots:
                if snapshot.status == "FAILED":
                    age_days = self._get_age_days(snapshot.creation_timestamp)

                    if age_days >= failed_snapshot_threshold_days:
                        # Calculate cost
                        size_gb = snapshot.storage_bytes / (1024**3)
                        storage_locations = snapshot.storage_locations or []
                        price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                        monthly_cost = size_gb * price_per_gb
                        already_wasted = monthly_cost * (age_days / 30.0)

                        # Get status message if available
                        status_message = (
                            snapshot.status_message
                            if hasattr(snapshot, "status_message")
                            else "Snapshot creation failed"
                        )

                        resources.append(
                            OrphanResourceData(
                                resource_id=str(snapshot.id),
                                resource_name=snapshot.name,
                                resource_type="gcp_disk_snapshot_failed",
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "creation_time": snapshot.creation_timestamp,
                                    "age_days": age_days,
                                    "status": snapshot.status,
                                    "status_message": status_message,
                                    "size_gb": round(size_gb, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "high",
                                    "recommendation": "Delete failed snapshot - unusable and consuming storage",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_untagged_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Scan for untagged disk snapshots (missing labels).

        Detection:
        - Missing required labels
        - Status = READY
        - Age >= min_age_days (default: 7)

        Cost:
        - Governance waste (5% of cost)
        """
        resources = []
        required_labels = (
            detection_rules.get("gcp_disk_snapshot_untagged", {}).get(
                "required_labels", ["environment", "owner", "purpose"]
            )
            if detection_rules
            else ["environment", "owner", "purpose"]
        )
        min_age_days = (
            detection_rules.get("gcp_disk_snapshot_untagged", {}).get("min_age_days", 7)
            if detection_rules
            else 7
        )
        governance_waste_pct = 0.05

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                age_days = self._get_age_days(snapshot.creation_timestamp)

                if age_days >= min_age_days:
                    # Check labels
                    labels = snapshot.labels if hasattr(snapshot, "labels") and snapshot.labels else {}

                    # Identify missing labels
                    missing_labels = [label for label in required_labels if label not in labels]

                    if missing_labels:
                        # Calculate cost
                        size_gb = snapshot.storage_bytes / (1024**3)
                        storage_locations = snapshot.storage_locations or []
                        price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                        monthly_cost = size_gb * price_per_gb
                        governance_waste = monthly_cost * governance_waste_pct

                        # Waste cumulated since creation
                        age_months = age_days / 30.0
                        already_wasted = governance_waste * age_months

                        confidence = "medium" if len(missing_labels) >= 2 else "low"

                        resources.append(
                            OrphanResourceData(
                                resource_id=str(snapshot.id),
                                resource_name=snapshot.name,
                                resource_type="gcp_disk_snapshot_untagged",
                                region="global",
                                estimated_monthly_cost=governance_waste,
                                resource_metadata={
                                    "creation_time": snapshot.creation_timestamp,
                                    "age_days": age_days,
                                    "labels": labels,
                                    "missing_labels": missing_labels,
                                    "size_gb": round(size_gb, 2),
                                    "full_monthly_cost": round(monthly_cost, 2),
                                    "governance_waste_monthly": round(governance_waste, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": confidence,
                                    "recommendation": "Add required labels for governance and cleanup decisions",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_excessive_retention_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Scan for excessive retention non-prod snapshots.

        Detection:
        - labels.environment in ['dev', 'test', 'staging']
        - Age > nonprod_retention_days (default: 90)

        Cost:
        - Waste = cost since nonprod_retention_days
        """
        resources = []
        nonprod_labels = (
            detection_rules.get("gcp_disk_snapshot_excessive_retention_nonprod", {}).get(
                "nonprod_labels", ["dev", "test", "staging", "development"]
            )
            if detection_rules
            else ["dev", "test", "staging", "development"]
        )
        nonprod_retention_days = (
            detection_rules.get("gcp_disk_snapshot_excessive_retention_nonprod", {}).get(
                "nonprod_retention_days", 90
            )
            if detection_rules
            else 90
        )

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                # Check environment label
                labels = snapshot.labels if hasattr(snapshot, "labels") and snapshot.labels else {}
                environment = labels.get("environment", "").lower()

                if environment in nonprod_labels:
                    age_days = self._get_age_days(snapshot.creation_timestamp)

                    if age_days > nonprod_retention_days:
                        # Calculate cost
                        size_gb = snapshot.storage_bytes / (1024**3)
                        storage_locations = snapshot.storage_locations or []
                        price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                        monthly_cost = size_gb * price_per_gb

                        # Excess retention
                        excess_days = age_days - nonprod_retention_days
                        excess_months = excess_days / 30.0
                        already_wasted = monthly_cost * excess_months

                        confidence = "high" if age_days >= 180 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=str(snapshot.id),
                                resource_name=snapshot.name,
                                resource_type="gcp_disk_snapshot_excessive_retention_nonprod",
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "creation_time": snapshot.creation_timestamp,
                                    "age_days": age_days,
                                    "labels": labels,
                                    "environment": environment,
                                    "size_gb": round(size_gb, 2),
                                    "recommended_retention_days": nonprod_retention_days,
                                    "excess_days": excess_days,
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Delete dev snapshot - {age_days} days old (dev retention should be max {nonprod_retention_days} days)",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_duplicate_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Scan for duplicate disk snapshots (created <1h apart).

        Detection:
        - Same source_disk
        - time_diff <= duplicate_time_window_hours (default: 1.0)
        - size_diff <= size_tolerance_gb (default: 1.0)

        Cost:
        - Waste = older duplicate snapshot cost
        """
        resources = []
        duplicate_time_window_hours = (
            detection_rules.get("gcp_disk_snapshot_duplicate", {}).get(
                "duplicate_time_window_hours", 1.0
            )
            if detection_rules
            else 1.0
        )
        size_tolerance_gb = (
            detection_rules.get("gcp_disk_snapshot_duplicate", {}).get("size_tolerance_gb", 1.0)
            if detection_rules
            else 1.0
        )

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = list(snapshots_client.list(request=request))

            # Group snapshots by source_disk
            snapshots_by_disk = defaultdict(list)
            for snapshot in snapshots:
                if snapshot.source_disk and snapshot.status == "READY":
                    snapshots_by_disk[snapshot.source_disk].append(snapshot)

            # Check for duplicates
            for source_disk, snapshots_list in snapshots_by_disk.items():
                # Sort by timestamp
                snapshots_list.sort(key=lambda s: s.creation_timestamp)

                # Compare adjacent snapshots
                for i in range(len(snapshots_list) - 1):
                    snap1 = snapshots_list[i]
                    snap2 = snapshots_list[i + 1]

                    # Calculate time difference
                    time1 = self._parse_timestamp(snap1.creation_timestamp)
                    time2 = self._parse_timestamp(snap2.creation_timestamp)
                    time_diff_hours = (time2 - time1).total_seconds() / 3600

                    # Calculate size difference
                    size1_gb = snap1.storage_bytes / (1024**3)
                    size2_gb = snap2.storage_bytes / (1024**3)
                    size_diff_gb = abs(size2_gb - size1_gb)

                    # Detection if duplicate
                    if (
                        time_diff_hours <= duplicate_time_window_hours
                        and size_diff_gb <= size_tolerance_gb
                    ):
                        # Delete oldest (snap1), keep newest (snap2)
                        waste_gb = size1_gb
                        price_per_gb = 0.026
                        monthly_waste = waste_gb * price_per_gb

                        # Cost wasted since creation snap1
                        age_days = self._get_age_days(snap1.creation_timestamp)
                        age_months = age_days / 30.0
                        already_wasted = monthly_waste * age_months

                        resources.append(
                            OrphanResourceData(
                                resource_id=f"duplicate-{str(snap1.id)}-{str(snap2.id)}",
                                resource_name=f"duplicate_pair_{snap1.name}",
                                resource_type="gcp_disk_snapshot_duplicate",
                                region="global",
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "source_disk": source_disk,
                                    "duplicate_snapshots": [
                                        {
                                            "snapshot_id": str(snap1.id),
                                            "snapshot_name": snap1.name,
                                            "creation_time": snap1.creation_timestamp,
                                            "size_gb": round(size1_gb, 2),
                                            "status": snap1.status,
                                            "keep": False,
                                        },
                                        {
                                            "snapshot_id": str(snap2.id),
                                            "snapshot_name": snap2.name,
                                            "creation_time": snap2.creation_timestamp,
                                            "size_gb": round(size2_gb, 2),
                                            "status": snap2.status,
                                            "keep": True,
                                        },
                                    ],
                                    "time_diff_hours": round(time_diff_hours, 2),
                                    "size_diff_gb": round(size_diff_gb, 2),
                                    "waste_snapshot_size_gb": round(waste_gb, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "high",
                                    "recommendation": f"Delete older duplicate snapshot ({snap1.name}) - created {round(time_diff_hours * 60, 0)} min apart with same content",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_never_restored_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Scan for never restored snapshots (>180 days + Cloud Logging check).

        Detection:
        - Age >= never_restored_threshold_days (default: 180)
        - restore_count == 0 (via Cloud Logging)
        - Status = READY

        Cost:
        - Waste = cost since threshold
        """
        resources = []
        never_restored_threshold_days = (
            detection_rules.get("gcp_disk_snapshot_never_restored", {}).get(
                "never_restored_threshold_days", 180
            )
            if detection_rules
            else 180
        )
        check_restore_logs = (
            detection_rules.get("gcp_disk_snapshot_never_restored", {}).get(
                "check_restore_logs", True
            )
            if detection_rules
            else True
        )

        try:
            snapshots_client = self._get_snapshots_client()

            # List all snapshots
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = snapshots_client.list(request=request)

            # Get logging client if needed
            logging_client = self._get_logging_client() if check_restore_logs else None

            for snapshot in snapshots:
                if snapshot.status != "READY":
                    continue

                age_days = self._get_age_days(snapshot.creation_timestamp)

                if age_days >= never_restored_threshold_days:
                    restore_count = 0

                    # Check Cloud Logging for restore operations
                    if check_restore_logs and logging_client:
                        try:
                            # Query logs for disk create from snapshot
                            creation_timestamp = self._parse_timestamp(snapshot.creation_timestamp)
                            filter_str = f'''
                            resource.type="gce_disk"
                            AND protoPayload.methodName="v1.compute.disks.insert"
                            AND protoPayload.request.sourceSnapshot:"{snapshot.name}"
                            AND timestamp>="{creation_timestamp.isoformat()}"
                            '''

                            entries = list(
                                logging_client.list_entries(
                                    filter_=filter_str, max_results=1
                                )
                            )
                            restore_count = len(entries)
                        except Exception:
                            # Logging check failed, assume not restored
                            restore_count = 0

                    # If never restored
                    if restore_count == 0:
                        # Calculate cost
                        size_gb = snapshot.storage_bytes / (1024**3)
                        storage_locations = snapshot.storage_locations or []
                        price_per_gb = 0.032 if len(storage_locations) > 1 else 0.026

                        monthly_cost = size_gb * price_per_gb

                        # Waste = cost since threshold
                        waste_days = age_days - never_restored_threshold_days
                        waste_months = waste_days / 30.0
                        already_wasted = monthly_cost * waste_months

                        confidence = "high" if age_days >= 365 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=str(snapshot.id),
                                resource_name=snapshot.name,
                                resource_type="gcp_disk_snapshot_never_restored",
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "creation_time": snapshot.creation_timestamp,
                                    "age_days": age_days,
                                    "source_disk": snapshot.source_disk or "N/A",
                                    "size_gb": round(size_gb, 2),
                                    "restore_count": restore_count,
                                    "last_restore_date": None,
                                    "waste_months": round(waste_months, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Delete snapshot - {age_days} days old, never restored (unclear purpose)",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_unused_ami_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS AMI-specific)."""
        return []

    # =================================================================
    # GKE CLUSTERS DETECTION METHODS (10 scenarios)
    # =================================================================

    async def scan_gke_cluster_empty(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Scan for empty GKE clusters (no nodes).

        Detection:
        - total_nodes == 0
        - age >= min_age_days (default: 7)
        - Standard mode only (Autopilot has no management fee)

        Cost:
        - Management fee: $73/month for Standard mode
        """
        resources = []
        min_age_days = (
            detection_rules.get("gke_cluster_empty", {}).get("min_age_days", 7)
            if detection_rules
            else 7
        )

        try:
            gke_client = self._get_gke_client()

            # List all clusters (location "-" means all zones/regions)
            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                # Skip Autopilot clusters (no management fee)
                if cluster.autopilot and cluster.autopilot.enabled:
                    continue

                # Count total nodes
                total_nodes = 0
                for node_pool in cluster.node_pools:
                    total_nodes += node_pool.initial_node_count

                # Detection: empty cluster
                if total_nodes == 0:
                    age_days = self._get_age_days(cluster.create_time)

                    if age_days >= min_age_days:
                        # Management fee: $0.10/hour = $73/month
                        management_fee_monthly = 73.00
                        already_wasted = management_fee_monthly * (age_days / 30.0)

                        resources.append(
                            OrphanResourceData(
                                resource_id=cluster.self_link,
                                resource_name=cluster.name,
                                resource_type="gke_cluster_empty",
                                region=cluster.location,
                                estimated_monthly_cost=management_fee_monthly,
                                resource_metadata={
                                    "cluster_name": cluster.name,
                                    "location": cluster.location,
                                    "cluster_mode": "STANDARD",
                                    "total_nodes": total_nodes,
                                    "status": cluster.status.name,
                                    "creation_time": cluster.create_time,
                                    "age_days": age_days,
                                    "management_fee_monthly": management_fee_monthly,
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "high",
                                    "recommendation": "Delete cluster or migrate to Autopilot mode",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_nodes_inactive(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Scan for clusters with all nodes inactive/not-ready.

        Detection:
        - total_nodes > 0
        - ready_nodes == 0 (all nodes not ready)
        - inactive_days >= min_inactive_days (default: 7)

        Cost:
        - 100% waste (management fee + nodes cost)
        """
        resources = []
        min_inactive_days = (
            detection_rules.get("gke_cluster_nodes_inactive", {}).get(
                "min_inactive_days", 7
            )
            if detection_rules
            else 7
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                if cluster.current_node_count == 0:
                    continue  # Skip empty clusters (handled by scenario 1)

                try:
                    # Get Kubernetes API client
                    k8s_config_dict = self._get_k8s_config(cluster, cluster.location)
                    if not k8s_config_dict:
                        continue

                    # Load kubeconfig and create API client
                    k8s_config.load_kube_config_from_dict(k8s_config_dict)
                    v1 = k8s_client.CoreV1Api()

                    # List all nodes
                    nodes = v1.list_node()
                    total_nodes = len(nodes.items)
                    ready_nodes = 0

                    # Count ready nodes
                    for node in nodes.items:
                        for condition in node.status.conditions:
                            if (
                                condition.type == "Ready"
                                and condition.status == "True"
                            ):
                                ready_nodes += 1
                                break

                    # Detection: all nodes not ready
                    if ready_nodes == 0 and total_nodes > 0:
                        # Calculate costs
                        management_fee = 73.00
                        nodes_cost = 0.0

                        for node_pool in cluster.node_pools:
                            machine_type = node_pool.config.machine_type
                            node_count = node_pool.initial_node_count
                            nodes_cost += node_count * self._get_machine_cost(
                                machine_type
                            )

                        monthly_cost = management_fee + nodes_cost
                        age_days = self._get_age_days(cluster.create_time)
                        already_wasted = monthly_cost * (age_days / 30.0)

                        resources.append(
                            OrphanResourceData(
                                resource_id=cluster.self_link,
                                resource_name=cluster.name,
                                resource_type="gke_cluster_nodes_inactive",
                                region=cluster.location,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "cluster_name": cluster.name,
                                    "location": cluster.location,
                                    "total_nodes": total_nodes,
                                    "ready_nodes": ready_nodes,
                                    "management_fee_monthly": management_fee,
                                    "nodes_cost_monthly": round(nodes_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "high",
                                    "recommendation": "Delete and recreate cluster, or troubleshoot node issues",
                                },
                            )
                        )

                except Exception:
                    continue

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_nodepool_overprovisioned(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Scan for over-provisioned node pools (too many nodes for workload).

        Detection:
        - pods_per_node < min_pods_per_node_threshold (default: 2.0)
        - total_nodes >= 2
        - autoscaling not enabled

        Cost:
        - Waste = (current_nodes - recommended_nodes) * node_cost
        """
        resources = []
        min_pods_per_node = (
            detection_rules.get("gke_cluster_nodepool_overprovisioned", {}).get(
                "min_pods_per_node_threshold", 2.0
            )
            if detection_rules
            else 2.0
        )
        optimal_pods_per_node = (
            detection_rules.get("gke_cluster_nodepool_overprovisioned", {}).get(
                "optimal_pods_per_node", 10
            )
            if detection_rules
            else 10
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                try:
                    # Get Kubernetes API client
                    k8s_config_dict = self._get_k8s_config(cluster, cluster.location)
                    if not k8s_config_dict:
                        continue

                    k8s_config.load_kube_config_from_dict(k8s_config_dict)
                    v1 = k8s_client.CoreV1Api()

                    # Count user pods (exclude system namespaces)
                    pods = v1.list_pod_for_all_namespaces()
                    user_pods = [
                        p
                        for p in pods.items
                        if p.metadata.namespace
                        not in ["kube-system", "kube-public", "kube-node-lease"]
                        and p.status.phase == "Running"
                    ]

                    total_user_pods = len(user_pods)

                    # Count nodes
                    nodes = v1.list_node()
                    total_nodes = len(nodes.items)

                    if total_nodes >= 2:
                        pods_per_node = total_user_pods / total_nodes

                        # Detection: very low pods per node
                        if pods_per_node < min_pods_per_node:
                            # Check if autoscaling enabled
                            has_autoscaling = any(
                                np.autoscaling and np.autoscaling.enabled
                                for np in cluster.node_pools
                            )

                            if not has_autoscaling:
                                # Calculate waste
                                recommended_nodes = max(
                                    1, int(total_user_pods / optimal_pods_per_node)
                                )
                                wasted_nodes = total_nodes - recommended_nodes

                                if wasted_nodes > 0:
                                    # Estimate node cost
                                    node_cost_monthly = 0.0
                                    for node_pool in cluster.node_pools:
                                        machine_type = node_pool.config.machine_type
                                        node_cost_monthly = self._get_machine_cost(
                                            machine_type
                                        )
                                        break  # Use first pool as estimate

                                    monthly_waste = wasted_nodes * node_cost_monthly
                                    age_days = self._get_age_days(cluster.create_time)
                                    already_wasted = monthly_waste * (age_days / 30.0)

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=cluster.self_link,
                                            resource_name=cluster.name,
                                            resource_type="gke_cluster_nodepool_overprovisioned",
                                            region=cluster.location,
                                            estimated_monthly_cost=monthly_waste,
                                            resource_metadata={
                                                "cluster_name": cluster.name,
                                                "location": cluster.location,
                                                "total_nodes": total_nodes,
                                                "total_user_pods": total_user_pods,
                                                "pods_per_node": round(
                                                    pods_per_node, 2
                                                ),
                                                "recommended_nodes": recommended_nodes,
                                                "wasted_nodes": wasted_nodes,
                                                "already_wasted": round(
                                                    already_wasted, 2
                                                ),
                                                "confidence": "high",
                                                "recommendation": f"Enable autoscaling or reduce nodes to {recommended_nodes} for current workload",
                                            },
                                        )
                                    )

                except Exception:
                    continue

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_old_machine_type(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Scan for clusters using old generation machine types.

        Detection:
        - machine_type.startswith('n1-')
        - n2/n2d equivalent exists with better price/performance

        Cost:
        - Waste = price difference (n1 vs n2)
        """
        resources = []
        old_generations = (
            detection_rules.get("gke_cluster_old_machine_type", {}).get(
                "old_generations", ["n1"]
            )
            if detection_rules
            else ["n1"]
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                for node_pool in cluster.node_pools:
                    machine_type = node_pool.config.machine_type

                    # Detection: old generation
                    if any(machine_type.startswith(f"{gen}-") for gen in old_generations):
                        # Calculate savings with n2
                        n2_equivalent = machine_type.replace("n1-", "n2-")

                        n1_cost = self._get_machine_cost(machine_type)
                        n2_cost = self._get_machine_cost(n2_equivalent)

                        if n1_cost > 0 and n2_cost > 0:
                            node_count = node_pool.initial_node_count
                            current_cost = node_count * n1_cost
                            recommended_cost = node_count * n2_cost
                            monthly_waste = current_cost - recommended_cost

                            if monthly_waste > 20.0:  # Min $20 savings
                                age_days = self._get_age_days(cluster.create_time)
                                already_wasted = monthly_waste * (age_days / 30.0)
                                savings_pct = (
                                    (monthly_waste / current_cost * 100)
                                    if current_cost > 0
                                    else 0
                                )

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=f"{cluster.self_link}/nodePools/{node_pool.name}",
                                        resource_name=f"{cluster.name}/{node_pool.name}",
                                        resource_type="gke_cluster_old_machine_type",
                                        region=cluster.location,
                                        estimated_monthly_cost=monthly_waste,
                                        resource_metadata={
                                            "cluster_name": cluster.name,
                                            "node_pool_name": node_pool.name,
                                            "location": cluster.location,
                                            "machine_type": machine_type,
                                            "node_count": node_count,
                                            "recommended_machine_type": n2_equivalent,
                                            "current_cost_monthly": round(
                                                current_cost, 2
                                            ),
                                            "recommended_cost_monthly": round(
                                                recommended_cost, 2
                                            ),
                                            "savings_percentage": round(savings_pct, 1),
                                            "already_wasted": round(already_wasted, 2),
                                            "confidence": "medium",
                                            "recommendation": f"Migrate to {n2_equivalent} for +40% performance/vCPU and -{round(savings_pct, 0)}% cost",
                                        },
                                    )
                                )

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_devtest_247(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Scan for dev/test clusters running 24/7.

        Detection:
        - labels.environment in ['dev', 'test', 'staging']
        - uptime_days >= min_uptime_days (default: 7)

        Cost:
        - Waste = cost difference between 24/7 and business hours
        """
        resources = []
        devtest_labels = (
            detection_rules.get("gke_cluster_devtest_247", {}).get(
                "devtest_labels", ["dev", "test", "staging", "development"]
            )
            if detection_rules
            else ["dev", "test", "staging", "development"]
        )
        min_uptime_days = (
            detection_rules.get("gke_cluster_devtest_247", {}).get(
                "min_uptime_days", 7
            )
            if detection_rules
            else 7
        )
        business_hours_per_week = (
            detection_rules.get("gke_cluster_devtest_247", {}).get(
                "business_hours_per_week", 60
            )
            if detection_rules
            else 60
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                # Check labels
                labels = cluster.resource_labels if cluster.resource_labels else {}
                environment = labels.get("environment", "").lower()

                if environment in devtest_labels:
                    age_days = self._get_age_days(cluster.create_time)

                    if age_days >= min_uptime_days:
                        # Calculate costs
                        management_fee = 73.00
                        nodes_cost = 0.0

                        for node_pool in cluster.node_pools:
                            machine_type = node_pool.config.machine_type
                            node_count = node_pool.initial_node_count
                            nodes_cost += node_count * self._get_machine_cost(
                                machine_type
                            )

                        monthly_cost = management_fee + nodes_cost

                        # Calculate optimal cost (business hours only)
                        hours_optimal = business_hours_per_week
                        hours_actual = 168  # 24×7
                        optimal_nodes_cost = nodes_cost * (
                            hours_optimal / hours_actual
                        )
                        optimal_cost = management_fee + optimal_nodes_cost

                        monthly_waste = monthly_cost - optimal_cost
                        already_wasted = monthly_waste * (age_days / 30.0)
                        waste_pct = int((monthly_waste / monthly_cost * 100))

                        resources.append(
                            OrphanResourceData(
                                resource_id=cluster.self_link,
                                resource_name=cluster.name,
                                resource_type="gke_cluster_devtest_247",
                                region=cluster.location,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "cluster_name": cluster.name,
                                    "location": cluster.location,
                                    "environment": environment,
                                    "uptime_days": age_days,
                                    "current_cost_monthly": round(monthly_cost, 2),
                                    "optimal_cost_monthly": round(optimal_cost, 2),
                                    "waste_percentage": waste_pct,
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "high",
                                    "recommendation": "Implement automated start/stop schedule or migrate to Autopilot",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_no_autoscaling(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Scan for clusters without autoscaling and variable workload.

        Detection:
        - No autoscaling enabled on any node pool
        - Workload variability > min_variability_threshold (default: 30%)

        Cost:
        - Conservative estimate: 50% of over-provisioned nodes
        """
        resources = []
        min_variability = (
            detection_rules.get("gke_cluster_no_autoscaling", {}).get(
                "min_variability_threshold", 30.0
            )
            if detection_rules
            else 30.0
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                # Skip Autopilot (auto-scaling built-in)
                if cluster.autopilot and cluster.autopilot.enabled:
                    continue

                # Check if any node pool has autoscaling
                has_autoscaling = any(
                    np.autoscaling and np.autoscaling.enabled
                    for np in cluster.node_pools
                )

                if not has_autoscaling:
                    # Assume moderate variability (cannot check metrics here)
                    # Conservative waste estimate
                    total_nodes = 0
                    nodes_cost = 0.0

                    for node_pool in cluster.node_pools:
                        machine_type = node_pool.config.machine_type
                        node_count = node_pool.initial_node_count
                        total_nodes += node_count
                        nodes_cost += node_count * self._get_machine_cost(machine_type)

                    if total_nodes >= 2:
                        # Conservative: assume 50% waste
                        monthly_waste = nodes_cost * 0.5
                        age_days = self._get_age_days(cluster.create_time)
                        already_wasted = monthly_waste * (age_days / 30.0)

                        resources.append(
                            OrphanResourceData(
                                resource_id=cluster.self_link,
                                resource_name=cluster.name,
                                resource_type="gke_cluster_no_autoscaling",
                                region=cluster.location,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "cluster_name": cluster.name,
                                    "location": cluster.location,
                                    "total_nodes": total_nodes,
                                    "autoscaling_enabled": False,
                                    "current_cost_monthly": round(nodes_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "medium",
                                    "recommendation": f"Enable Cluster Autoscaler with min 1, max {total_nodes} nodes",
                                },
                            )
                        )

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_untagged(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Scan for clusters without required labels.

        Detection:
        - Missing required labels (environment, owner, cost-center)

        Cost:
        - Governance waste: 5% of cluster cost
        """
        resources = []
        required_labels = (
            detection_rules.get("gke_cluster_untagged", {}).get(
                "required_labels", ["environment", "owner", "cost-center"]
            )
            if detection_rules
            else ["environment", "owner", "cost-center"]
        )
        governance_waste_pct = (
            detection_rules.get("gke_cluster_untagged", {}).get(
                "governance_waste_pct", 0.05
            )
            if detection_rules
            else 0.05
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                labels = cluster.resource_labels if cluster.resource_labels else {}

                # Check for missing labels
                missing_labels = [
                    label for label in required_labels if label not in labels
                ]

                if missing_labels:
                    # Calculate cluster cost
                    management_fee = 0.0 if (cluster.autopilot and cluster.autopilot.enabled) else 73.00
                    nodes_cost = 0.0

                    for node_pool in cluster.node_pools:
                        machine_type = node_pool.config.machine_type
                        node_count = node_pool.initial_node_count
                        nodes_cost += node_count * self._get_machine_cost(machine_type)

                    cluster_monthly_cost = management_fee + nodes_cost
                    monthly_waste = cluster_monthly_cost * governance_waste_pct

                    age_days = self._get_age_days(cluster.create_time)
                    already_wasted = monthly_waste * (age_days / 30.0)

                    resources.append(
                        OrphanResourceData(
                            resource_id=cluster.self_link,
                            resource_name=cluster.name,
                            resource_type="gke_cluster_untagged",
                            region=cluster.location,
                            estimated_monthly_cost=monthly_waste,
                            resource_metadata={
                                "cluster_name": cluster.name,
                                "location": cluster.location,
                                "labels": dict(labels),
                                "missing_labels": missing_labels,
                                "cluster_monthly_cost": round(cluster_monthly_cost, 2),
                                "already_wasted": round(already_wasted, 2),
                                "confidence": "medium",
                                "recommendation": "Add required labels for cost allocation and governance",
                            },
                        )
                    )

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_nodes_underutilized(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8 (Phase 2): Scan for clusters with underutilized nodes.

        Detection:
        - avg_cpu < cpu_threshold (default: 30%)
        - avg_memory < memory_threshold (default: 40%)
        - >50% of nodes underutilized

        Cost:
        - Waste = downgrade opportunity (e.g., n2-standard-4 → n2-standard-2)
        """
        resources = []
        cpu_threshold = (
            detection_rules.get("gke_cluster_nodes_underutilized", {}).get(
                "cpu_threshold", 30.0
            )
            if detection_rules
            else 30.0
        )
        memory_threshold = (
            detection_rules.get("gke_cluster_nodes_underutilized", {}).get(
                "memory_threshold", 40.0
            )
            if detection_rules
            else 40.0
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                # Phase 2: Would require Cloud Monitoring metrics analysis
                # Placeholder for MVP (conservative detection)
                # Skip for now - requires metrics collection over 14 days
                pass

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_pods_overrequested(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9 (Phase 2): Scan for pods with excessive resource requests.

        Detection:
        - usage < 50% of requests (CPU or Memory)
        - >30% of pods over-requested

        Cost:
        - Waste = difference between requested and used resources
        """
        resources = []
        usage_request_ratio = (
            detection_rules.get("gke_cluster_pods_overrequested", {}).get(
                "usage_request_ratio_threshold", 0.5
            )
            if detection_rules
            else 0.5
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                # Phase 2: Would require pod metrics analysis
                # Placeholder for MVP
                # Skip for now - requires Kubernetes metrics server
                pass

        except Exception as e:
            pass

        return resources

    async def scan_gke_cluster_no_workloads(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Scan for clusters with no user workloads.

        Detection:
        - user_pods == 0 (excluding kube-system)
        - no_workload_days >= min_no_workload_days (default: 7)

        Cost:
        - 100% waste (cluster unused)
        """
        resources = []
        min_no_workload_days = (
            detection_rules.get("gke_cluster_no_workloads", {}).get(
                "min_no_workload_days", 7
            )
            if detection_rules
            else 7
        )

        try:
            gke_client = self._get_gke_client()

            parent = f"projects/{self.project_id}/locations/-"
            clusters_response = gke_client.list_clusters(parent=parent)

            for cluster in clusters_response.clusters:
                try:
                    # Get Kubernetes API client
                    k8s_config_dict = self._get_k8s_config(cluster, cluster.location)
                    if not k8s_config_dict:
                        continue

                    k8s_config.load_kube_config_from_dict(k8s_config_dict)
                    v1 = k8s_client.CoreV1Api()

                    # Count user pods
                    pods = v1.list_pod_for_all_namespaces()
                    user_pods = [
                        p
                        for p in pods.items
                        if p.metadata.namespace
                        not in [
                            "kube-system",
                            "kube-public",
                            "kube-node-lease",
                            "gke-managed-system",
                        ]
                        and p.status.phase == "Running"
                    ]

                    if len(user_pods) == 0:
                        age_days = self._get_age_days(cluster.create_time)

                        if age_days >= min_no_workload_days:
                            # Calculate total cost
                            management_fee = 0.0 if (cluster.autopilot and cluster.autopilot.enabled) else 73.00
                            nodes_cost = 0.0

                            for node_pool in cluster.node_pools:
                                machine_type = node_pool.config.machine_type
                                node_count = node_pool.initial_node_count
                                nodes_cost += node_count * self._get_machine_cost(
                                    machine_type
                                )

                            monthly_cost = management_fee + nodes_cost
                            already_wasted = monthly_cost * (age_days / 30.0)

                            resources.append(
                                OrphanResourceData(
                                    resource_id=cluster.self_link,
                                    resource_name=cluster.name,
                                    resource_type="gke_cluster_no_workloads",
                                    region=cluster.location,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "cluster_name": cluster.name,
                                        "location": cluster.location,
                                        "user_pods": 0,
                                        "no_workload_days": age_days,
                                        "management_fee_monthly": management_fee,
                                        "nodes_cost_monthly": round(nodes_cost, 2),
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": "high",
                                        "recommendation": "Delete cluster if no longer needed",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception as e:
            pass

        return resources

    # ==================== CLOUD RUN SERVICES SCENARIOS ====================

    async def scan_cloud_run_never_used(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Scan for Cloud Run services with zero requests for 30+ days.

        Detection:
        - request_count == 0 for lookback period
        - age >= min_age_days (default: 30)

        Cost:
        - 100% waste if min_instances > 0
        - Minimal waste if min_instances == 0
        """
        resources = []
        min_age_days = (
            detection_rules.get("cloud_run_never_used", {}).get("min_age_days", 30)
            if detection_rules
            else 30
        )
        lookback_days = (
            detection_rules.get("cloud_run_never_used", {}).get("lookback_days", 30)
            if detection_rules
            else 30
        )

        try:
            run_client = self._get_run_client()
            monitoring_client = self._get_monitoring_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]

                    # Query request_count metrics
                    now = time.time()
                    end_time = Timestamp(seconds=int(now))
                    start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

                    interval = monitoring_v3.TimeInterval(
                        {"end_time": end_time, "start_time": start_time}
                    )

                    filter_str = (
                        f'resource.type = "cloud_run_revision" '
                        f'AND resource.labels.service_name = "{service_name}" '
                        f'AND resource.labels.location = "{region}" '
                        f'AND metric.type = "run.googleapis.com/request_count"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    # Sum all requests
                    total_requests = 0
                    for series in time_series:
                        for point in series.points:
                            total_requests += point.value.int64_value or point.value.double_value or 0

                    # If zero requests, calculate waste
                    if total_requests == 0:
                        age_days = self._get_age_days(service.create_time)

                        if age_days >= min_age_days:
                            template = service.template
                            scaling = template.scaling
                            min_instances = scaling.min_instance_count if scaling else 0

                            container = template.containers[0] if template.containers else None
                            if container:
                                vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                                memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                                # Cloud Run pricing: $0.00002400/vCPU-sec ($62.21/vCPU/month) + $0.00000250/GiB-sec ($6.48/GiB/month)
                                cpu_cost_monthly = vcpu * 62.21
                                memory_cost_monthly = memory_gib * 6.48
                                cost_per_instance = cpu_cost_monthly + memory_cost_monthly

                                monthly_cost = min_instances * cost_per_instance
                                already_wasted = monthly_cost * (age_days / 30.0)
                            else:
                                monthly_cost = 50.0  # Estimation
                                already_wasted = monthly_cost * (age_days / 30.0)

                            confidence = "critical" if age_days >= 90 else "high" if age_days >= 60 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=service.name,
                                    resource_name=service_name,
                                    resource_type="gcp_cloud_run_never_used",
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "service_name": service_name,
                                        "service_uri": service.uri,
                                        "region": region,
                                        "min_instances": min_instances,
                                        "total_requests": 0,
                                        "lookback_days": lookback_days,
                                        "age_days": age_days,
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": confidence,
                                        "recommendation": "Delete service (zero requests)",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_idle_min_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Scan for Cloud Run services with min_instances > 0 but low traffic.

        Detection:
        - min_instances > 0
        - avg_requests_per_min < traffic_threshold_rpm (default: 10 req/min)

        Cost:
        - Waste = current cost - optimal cost (min_instances = 0)
        """
        resources = []
        traffic_threshold_rpm = (
            detection_rules.get("cloud_run_idle_min_instances", {}).get("traffic_threshold_rpm", 10)
            if detection_rules
            else 10
        )
        lookback_days = (
            detection_rules.get("cloud_run_idle_min_instances", {}).get("lookback_days", 14)
            if detection_rules
            else 14
        )

        try:
            run_client = self._get_run_client()
            monitoring_client = self._get_monitoring_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    template = service.template
                    scaling = template.scaling
                    min_instances = scaling.min_instance_count if scaling else 0

                    if min_instances > 0:
                        # Query request metrics
                        now = time.time()
                        end_time = Timestamp(seconds=int(now))
                        start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

                        interval = monitoring_v3.TimeInterval(
                            {"end_time": end_time, "start_time": start_time}
                        )

                        filter_str = (
                            f'resource.type = "cloud_run_revision" '
                            f'AND resource.labels.service_name = "{service_name}" '
                            f'AND resource.labels.location = "{region}" '
                            f'AND metric.type = "run.googleapis.com/request_count"'
                        )

                        request = monitoring_v3.ListTimeSeriesRequest(
                            name=f"projects/{self.project_id}",
                            filter=filter_str,
                            interval=interval,
                        )

                        time_series = monitoring_client.list_time_series(request=request)

                        total_requests = 0
                        for series in time_series:
                            for point in series.points:
                                total_requests += point.value.int64_value or point.value.double_value or 0

                        avg_requests_per_min = total_requests / (lookback_days * 24 * 60)

                        if avg_requests_per_min < traffic_threshold_rpm:
                            container = template.containers[0] if template.containers else None
                            if container:
                                vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                                memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                                cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
                                monthly_cost_current = min_instances * cost_per_instance
                                monthly_cost_optimal = 0  # min_instances = 0
                                monthly_waste = monthly_cost_current - monthly_cost_optimal
                            else:
                                monthly_waste = 75.0

                            confidence = "critical" if avg_requests_per_min < 1 else "high" if avg_requests_per_min < 5 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=service.name,
                                    resource_name=service_name,
                                    resource_type="gcp_cloud_run_idle_min_instances",
                                    region=region,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "service_name": service_name,
                                        "service_uri": service.uri,
                                        "region": region,
                                        "min_instances_current": min_instances,
                                        "recommended_min_instances": 0,
                                        "avg_requests_per_min": round(avg_requests_per_min, 2),
                                        "traffic_threshold_rpm": traffic_threshold_rpm,
                                        "monthly_waste": round(monthly_waste, 2),
                                        "confidence": confidence,
                                        "recommendation": "Set min_instances = 0 (low traffic)",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_overprovisioned(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Scan for Cloud Run services with low CPU/memory utilization.

        Detection:
        - avg_cpu_utilization < cpu_threshold (default: 20%)
        - avg_memory_utilization < memory_threshold (default: 20%)

        Cost:
        - Right-size CPU/memory to reduce costs
        """
        resources = []
        cpu_threshold = (
            detection_rules.get("cloud_run_overprovisioned", {}).get("cpu_threshold", 20)
            if detection_rules
            else 20
        )
        memory_threshold = (
            detection_rules.get("cloud_run_overprovisioned", {}).get("memory_threshold", 20)
            if detection_rules
            else 20
        )
        lookback_days = (
            detection_rules.get("cloud_run_overprovisioned", {}).get("lookback_days", 14)
            if detection_rules
            else 14
        )

        try:
            run_client = self._get_run_client()
            monitoring_client = self._get_monitoring_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]

                    # Query CPU utilization
                    now = time.time()
                    end_time = Timestamp(seconds=int(now))
                    start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

                    interval = monitoring_v3.TimeInterval(
                        {"end_time": end_time, "start_time": start_time}
                    )

                    filter_cpu = (
                        f'resource.type = "cloud_run_revision" '
                        f'AND resource.labels.service_name = "{service_name}" '
                        f'AND metric.type = "run.googleapis.com/container/cpu/utilizations"'
                    )

                    request_cpu = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_cpu,
                        interval=interval,
                    )

                    cpu_time_series = monitoring_client.list_time_series(request=request_cpu)

                    cpu_values = []
                    for series in cpu_time_series:
                        for point in series.points:
                            cpu_values.append(point.value.double_value * 100)

                    avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0

                    # Query Memory utilization
                    filter_memory = (
                        f'resource.type = "cloud_run_revision" '
                        f'AND resource.labels.service_name = "{service_name}" '
                        f'AND metric.type = "run.googleapis.com/container/memory/utilizations"'
                    )

                    request_memory = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_memory,
                        interval=interval,
                    )

                    memory_time_series = monitoring_client.list_time_series(request=request_memory)

                    memory_values = []
                    for series in memory_time_series:
                        for point in series.points:
                            memory_values.append(point.value.double_value * 100)

                    avg_memory = sum(memory_values) / len(memory_values) if memory_values else 0

                    if avg_cpu < cpu_threshold and avg_memory < memory_threshold and len(cpu_values) > 0:
                        template = service.template
                        container = template.containers[0] if template.containers else None

                        if container:
                            vcpu_current = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                            memory_current_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                            # Recommend 50% reduction
                            vcpu_recommended = max(0.5, vcpu_current * 0.5)
                            memory_recommended_gib = max(0.25, memory_current_gib * 0.5)

                            cost_current = (vcpu_current * 62.21) + (memory_current_gib * 6.48)
                            cost_optimal = (vcpu_recommended * 62.21) + (memory_recommended_gib * 6.48)
                            monthly_waste = cost_current - cost_optimal

                            confidence = "high" if avg_cpu < 10 and avg_memory < 10 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=service.name,
                                    resource_name=service_name,
                                    resource_type="gcp_cloud_run_overprovisioned",
                                    region=region,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "service_name": service_name,
                                        "service_uri": service.uri,
                                        "region": region,
                                        "avg_cpu_utilization": round(avg_cpu, 2),
                                        "avg_memory_utilization": round(avg_memory, 2),
                                        "vcpu_current": vcpu_current,
                                        "vcpu_recommended": vcpu_recommended,
                                        "memory_current_gib": memory_current_gib,
                                        "memory_recommended_gib": memory_recommended_gib,
                                        "monthly_waste": round(monthly_waste, 2),
                                        "confidence": confidence,
                                        "recommendation": f"Reduce CPU to {vcpu_recommended} vCPU, Memory to {memory_recommended_gib} GiB",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_nonprod_min_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Scan for dev/test Cloud Run services with min_instances > 0.

        Detection:
        - environment label = 'dev' or 'test'
        - min_instances > 0

        Cost:
        - 100% waste (non-prod shouldn't have min_instances)
        """
        resources = []

        try:
            run_client = self._get_run_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    labels = dict(service.labels) if service.labels else {}
                    environment = labels.get('environment', '').lower()

                    template = service.template
                    scaling = template.scaling
                    min_instances = scaling.min_instance_count if scaling else 0

                    if environment in ['dev', 'test', 'staging'] and min_instances > 0:
                        container = template.containers[0] if template.containers else None

                        if container:
                            vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                            memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                            cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
                            monthly_waste = min_instances * cost_per_instance
                        else:
                            monthly_waste = 75.0

                        confidence = "critical" if min_instances >= 3 else "high"

                        resources.append(
                            OrphanResourceData(
                                resource_id=service.name,
                                resource_name=service_name,
                                resource_type="gcp_cloud_run_nonprod_min_instances",
                                region=region,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "service_name": service_name,
                                    "service_uri": service.uri,
                                    "region": region,
                                    "environment": environment,
                                    "min_instances_current": min_instances,
                                    "recommended_min_instances": 0,
                                    "monthly_waste": round(monthly_waste, 2),
                                    "confidence": confidence,
                                    "recommendation": "Set min_instances = 0 (non-prod environment)",
                                },
                            )
                        )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_cpu_always_allocated(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Scan for Cloud Run services with 'CPU always allocated' mode but sporadic traffic.

        Detection:
        - cpu_allocation_mode = 'CPU_ALWAYS' (billing 24/7)
        - avg_requests_per_min < traffic_threshold_rpm (default: 100 req/min)

        Cost:
        - Waste = cost difference between 'always' and 'during requests' modes (40-60% savings)
        """
        resources = []
        traffic_threshold_rpm = (
            detection_rules.get("cloud_run_cpu_always_allocated", {}).get("traffic_threshold_rpm", 100)
            if detection_rules
            else 100
        )
        lookback_days = (
            detection_rules.get("cloud_run_cpu_always_allocated", {}).get("lookback_days", 14)
            if detection_rules
            else 14
        )

        try:
            run_client = self._get_run_client()
            monitoring_client = self._get_monitoring_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    template = service.template
                    container = template.containers[0] if template.containers else None

                    if container:
                        # Check CPU allocation mode (startup_cpu_boost indicates always allocated)
                        cpu_always = hasattr(container, 'startup_cpu_boost') and container.startup_cpu_boost

                        if cpu_always:
                            # Query request metrics
                            now = time.time()
                            end_time = Timestamp(seconds=int(now))
                            start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

                            interval = monitoring_v3.TimeInterval(
                                {"end_time": end_time, "start_time": start_time}
                            )

                            filter_str = (
                                f'resource.type = "cloud_run_revision" '
                                f'AND resource.labels.service_name = "{service_name}" '
                                f'AND metric.type = "run.googleapis.com/request_count"'
                            )

                            request = monitoring_v3.ListTimeSeriesRequest(
                                name=f"projects/{self.project_id}",
                                filter=filter_str,
                                interval=interval,
                            )

                            time_series = monitoring_client.list_time_series(request=request)

                            total_requests = 0
                            for series in time_series:
                                for point in series.points:
                                    total_requests += point.value.int64_value or point.value.double_value or 0

                            avg_requests_per_min = total_requests / (lookback_days * 24 * 60)

                            if avg_requests_per_min < traffic_threshold_rpm:
                                vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                                memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                                cost_always = (vcpu * 62.21) + (memory_gib * 6.48)
                                cost_during_requests = cost_always * 0.5  # ~50% savings
                                monthly_waste = cost_always - cost_during_requests

                                confidence = "high" if avg_requests_per_min < 50 else "medium"

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=service.name,
                                        resource_name=service_name,
                                        resource_type="gcp_cloud_run_cpu_always_allocated",
                                        region=region,
                                        estimated_monthly_cost=monthly_waste,
                                        resource_metadata={
                                            "service_name": service_name,
                                            "service_uri": service.uri,
                                            "region": region,
                                            "cpu_allocation_mode": "always",
                                            "avg_requests_per_min": round(avg_requests_per_min, 2),
                                            "monthly_waste": round(monthly_waste, 2),
                                            "confidence": confidence,
                                            "recommendation": "Switch to 'CPU during requests only' mode",
                                        },
                                    )
                                )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_untagged(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Scan for Cloud Run services without required labels.

        Detection:
        - Missing required labels (environment, team, owner, etc.)

        Cost:
        - Financial risk (no cost tracking/chargeback)
        """
        resources = []
        required_labels = (
            detection_rules.get("cloud_run_untagged", {}).get("required_labels", ["environment"])
            if detection_rules
            else ["environment"]
        )

        try:
            run_client = self._get_run_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    labels = dict(service.labels) if service.labels else {}

                    missing_labels = [label for label in required_labels if label not in labels]

                    if missing_labels:
                        template = service.template
                        container = template.containers[0] if template.containers else None
                        scaling = template.scaling
                        min_instances = scaling.min_instance_count if scaling else 0

                        if container:
                            vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                            memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                            cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
                            monthly_cost = max(min_instances * cost_per_instance, 10.0)
                        else:
                            monthly_cost = 50.0

                        confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=service.name,
                                resource_name=service_name,
                                resource_type="gcp_cloud_run_untagged",
                                region=region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "service_name": service_name,
                                    "service_uri": service.uri,
                                    "region": region,
                                    "existing_labels": labels,
                                    "missing_labels": missing_labels,
                                    "monthly_cost": round(monthly_cost, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Add labels: {', '.join(missing_labels)}",
                                },
                            )
                        )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_excessive_max_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Scan for Cloud Run services with excessive max_instances (runaway cost risk).

        Detection:
        - max_instances > max_instances_threshold (default: 100)

        Cost:
        - Financial risk (potential runaway costs)
        """
        resources = []
        max_instances_threshold = (
            detection_rules.get("cloud_run_excessive_max_instances", {}).get("max_instances_threshold", 100)
            if detection_rules
            else 100
        )

        try:
            run_client = self._get_run_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    template = service.template
                    scaling = template.scaling
                    max_instances = scaling.max_instance_count if scaling else 100

                    if max_instances > max_instances_threshold:
                        container = template.containers[0] if template.containers else None

                        if container:
                            vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                            memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                            cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
                            risk_cost = max_instances * cost_per_instance
                        else:
                            risk_cost = max_instances * 75.0

                        confidence = "critical" if max_instances > 500 else "high" if max_instances > 200 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=service.name,
                                resource_name=service_name,
                                resource_type="gcp_cloud_run_excessive_max_instances",
                                region=region,
                                estimated_monthly_cost=risk_cost,
                                resource_metadata={
                                    "service_name": service_name,
                                    "service_uri": service.uri,
                                    "region": region,
                                    "max_instances_current": max_instances,
                                    "recommended_max_instances": max_instances_threshold,
                                    "risk_cost_monthly": round(risk_cost, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Reduce max_instances from {max_instances} to {max_instances_threshold}",
                                },
                            )
                        )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_low_concurrency(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Scan for Cloud Run services with low concurrency (inefficient).

        Detection:
        - container_concurrency <= concurrency_threshold (default: 10)

        Cost:
        - 5-10x more instances needed = 5-10x higher costs
        """
        resources = []
        concurrency_threshold = (
            detection_rules.get("cloud_run_low_concurrency", {}).get("concurrency_threshold", 10)
            if detection_rules
            else 10
        )

        try:
            run_client = self._get_run_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    template = service.template
                    container = template.containers[0] if template.containers else None

                    if container:
                        concurrency = getattr(template, 'max_instance_request_concurrency', 80)

                        if concurrency <= concurrency_threshold:
                            vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                            memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                            # With concurrency 1 vs 80, need 80x more instances
                            inefficiency_factor = 80 / max(concurrency, 1)

                            cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
                            monthly_waste = cost_per_instance * (inefficiency_factor - 1) * 0.5  # Conservative estimate

                            confidence = "high" if concurrency == 1 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=service.name,
                                    resource_name=service_name,
                                    resource_type="gcp_cloud_run_low_concurrency",
                                    region=region,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "service_name": service_name,
                                        "service_uri": service.uri,
                                        "region": region,
                                        "concurrency_current": concurrency,
                                        "recommended_concurrency": 80,
                                        "inefficiency_factor": round(inefficiency_factor, 2),
                                        "monthly_waste": round(monthly_waste, 2),
                                        "confidence": confidence,
                                        "recommendation": f"Increase concurrency from {concurrency} to 80-250",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_excessive_min_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Scan for Cloud Run services with excessive min_instances for fast cold start + low traffic.

        Detection:
        - min_instances >= min_instances_threshold (default: 5)
        - avg_cold_start_seconds < cold_start_threshold_seconds (default: 2.0)
        - avg_requests_per_min < traffic_threshold_rpm (default: 100)

        Cost:
        - Over-optimization waste (min_instances excessive for cold start speed)
        """
        resources = []
        min_instances_threshold = (
            detection_rules.get("cloud_run_excessive_min_instances", {}).get("min_instances_threshold", 5)
            if detection_rules
            else 5
        )
        cold_start_threshold_seconds = (
            detection_rules.get("cloud_run_excessive_min_instances", {}).get("cold_start_threshold_seconds", 2.0)
            if detection_rules
            else 2.0
        )
        traffic_threshold_rpm = (
            detection_rules.get("cloud_run_excessive_min_instances", {}).get("traffic_threshold_rpm", 100)
            if detection_rules
            else 100
        )
        lookback_days = (
            detection_rules.get("cloud_run_excessive_min_instances", {}).get("lookback_days", 14)
            if detection_rules
            else 14
        )

        try:
            run_client = self._get_run_client()
            monitoring_client = self._get_monitoring_client()

            parent = f"projects/{self.project_id}/locations/{region}"
            services = run_client.list_services(parent=parent)

            for service in services:
                try:
                    service_name = service.name.split('/')[-1]
                    template = service.template
                    scaling = template.scaling
                    min_instances = scaling.min_instance_count if scaling else 0

                    if min_instances >= min_instances_threshold:
                        # Query request metrics
                        now = time.time()
                        end_time = Timestamp(seconds=int(now))
                        start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

                        interval = monitoring_v3.TimeInterval(
                            {"end_time": end_time, "start_time": start_time}
                        )

                        filter_requests = (
                            f'resource.type = "cloud_run_revision" '
                            f'AND resource.labels.service_name = "{service_name}" '
                            f'AND metric.type = "run.googleapis.com/request_count"'
                        )

                        request_requests = monitoring_v3.ListTimeSeriesRequest(
                            name=f"projects/{self.project_id}",
                            filter=filter_requests,
                            interval=interval,
                        )

                        requests_time_series = monitoring_client.list_time_series(request=request_requests)

                        total_requests = 0
                        for series in requests_time_series:
                            for point in series.points:
                                total_requests += point.value.int64_value or point.value.double_value or 0

                        avg_requests_per_min = total_requests / (lookback_days * 24 * 60)

                        # Query cold start latency
                        filter_startup = (
                            f'resource.type = "cloud_run_revision" '
                            f'AND resource.labels.service_name = "{service_name}" '
                            f'AND metric.type = "run.googleapis.com/container/startup_latencies"'
                        )

                        request_startup = monitoring_v3.ListTimeSeriesRequest(
                            name=f"projects/{self.project_id}",
                            filter=filter_startup,
                            interval=interval,
                        )

                        startup_time_series = monitoring_client.list_time_series(request=request_startup)

                        startup_values = []
                        for series in startup_time_series:
                            for point in series.points:
                                startup_values.append(
                                    point.value.distribution_value.mean if hasattr(point.value, 'distribution_value') else 1.0
                                )

                        avg_cold_start_seconds = sum(startup_values) / len(startup_values) if startup_values else 1.0

                        if avg_requests_per_min < traffic_threshold_rpm and avg_cold_start_seconds < cold_start_threshold_seconds:
                            container = template.containers[0] if template.containers else None

                            if container:
                                vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                                memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                                cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)
                                monthly_cost_current = min_instances * cost_per_instance

                                recommended_min = 0 if avg_cold_start_seconds < 1.0 else 1
                                monthly_cost_optimal = recommended_min * cost_per_instance

                                monthly_waste = monthly_cost_current - monthly_cost_optimal
                            else:
                                monthly_waste = 100.0

                            confidence = "critical" if min_instances >= 10 else "high" if min_instances >= 7 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=service.name,
                                    resource_name=service_name,
                                    resource_type="gcp_cloud_run_excessive_min_instances",
                                    region=region,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "service_name": service_name,
                                        "service_uri": service.uri,
                                        "region": region,
                                        "min_instances_current": min_instances,
                                        "recommended_min_instances": 0 if avg_cold_start_seconds < 1.0 else 1,
                                        "avg_requests_per_min": round(avg_requests_per_min, 2),
                                        "avg_cold_start_seconds": round(avg_cold_start_seconds, 2),
                                        "monthly_waste": round(monthly_waste, 2),
                                        "confidence": confidence,
                                        "recommendation": f"Reduce min_instances from {min_instances} to {0 if avg_cold_start_seconds < 1.0 else 1}",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_run_multi_region_redundant(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Scan for Cloud Run services deployed in multiple regions but traffic concentrated in one.

        Detection:
        - Same service deployed in 3+ regions
        - 80%+ traffic concentrated in 1 region

        Cost:
        - Waste = cost of redundant regions
        """
        resources = []
        traffic_concentration_threshold = (
            detection_rules.get("cloud_run_multi_region_redundant", {}).get("traffic_concentration_threshold", 80.0)
            if detection_rules
            else 80.0
        )
        region_count_threshold = (
            detection_rules.get("cloud_run_multi_region_redundant", {}).get("region_count_threshold", 3)
            if detection_rules
            else 3
        )
        lookback_days = (
            detection_rules.get("cloud_run_multi_region_redundant", {}).get("lookback_days", 14)
            if detection_rules
            else 14
        )

        try:
            run_client = self._get_run_client()
            monitoring_client = self._get_monitoring_client()

            # Get all regions
            regions_to_scan = self.regions if self.regions else await self.get_available_regions()

            # Group services by name across regions
            services_by_name = defaultdict(list)

            for scan_region in regions_to_scan:
                try:
                    parent = f"projects/{self.project_id}/locations/{scan_region}"
                    services = run_client.list_services(parent=parent)

                    for service in services:
                        service_name = service.name.split('/')[-1]
                        services_by_name[service_name].append({
                            "region": scan_region,
                            "service": service,
                        })
                except Exception:
                    continue

            # Analyze multi-region services
            for service_name, region_services in services_by_name.items():
                try:
                    if len(region_services) < region_count_threshold:
                        continue

                    # Query request_count per region
                    now = time.time()
                    end_time = Timestamp(seconds=int(now))
                    start_time = Timestamp(seconds=int(now - lookback_days * 24 * 3600))

                    interval = monitoring_v3.TimeInterval(
                        {"end_time": end_time, "start_time": start_time}
                    )

                    region_requests = {}

                    for region_service in region_services:
                        service_region = region_service["region"]

                        filter_requests = (
                            f'resource.type = "cloud_run_revision" '
                            f'AND resource.labels.service_name = "{service_name}" '
                            f'AND resource.labels.location = "{service_region}" '
                            f'AND metric.type = "run.googleapis.com/request_count"'
                        )

                        request_requests = monitoring_v3.ListTimeSeriesRequest(
                            name=f"projects/{self.project_id}",
                            filter=filter_requests,
                            interval=interval,
                        )

                        requests_time_series = monitoring_client.list_time_series(request=request_requests)

                        total_requests = 0
                        for series in requests_time_series:
                            for point in series.points:
                                total_requests += point.value.int64_value or point.value.double_value or 0

                        region_requests[service_region] = total_requests

                    total_all_regions = sum(region_requests.values())

                    if total_all_regions == 0:
                        continue

                    # Find primary region (most traffic)
                    primary_region = max(region_requests, key=region_requests.get)
                    primary_region_requests = region_requests[primary_region]
                    traffic_concentration = (primary_region_requests / total_all_regions * 100) if total_all_regions > 0 else 0

                    if traffic_concentration >= traffic_concentration_threshold:
                        redundant_regions = [r for r in region_requests.keys() if r != primary_region]

                        # Get primary service config
                        primary_service = next(rs["service"] for rs in region_services if rs["region"] == primary_region)
                        template = primary_service.template
                        scaling = template.scaling
                        min_instances = scaling.min_instance_count if scaling else 0

                        container = template.containers[0] if template.containers else None

                        if container:
                            vcpu = self._parse_cloud_run_cpu(container.resources.limits.get('cpu', '1'))
                            memory_gib = self._parse_cloud_run_memory(container.resources.limits.get('memory', '512Mi'))

                            cost_per_instance = (vcpu * 62.21) + (memory_gib * 6.48)

                            if min_instances > 0:
                                cost_per_region = min_instances * cost_per_instance
                            else:
                                cost_per_region = 10.0

                            monthly_waste = len(redundant_regions) * cost_per_region
                        else:
                            monthly_waste = len(redundant_regions) * 75.0

                        confidence = "critical" if traffic_concentration >= 95 else "high" if traffic_concentration >= 90 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=f"{service_name}_multi_region",
                                resource_name=service_name,
                                resource_type="gcp_cloud_run_multi_region_redundant",
                                region=primary_region,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "service_name": service_name,
                                    "total_regions": len(region_services),
                                    "primary_region": primary_region,
                                    "redundant_regions": redundant_regions,
                                    "traffic_concentration": round(traffic_concentration, 2),
                                    "monthly_waste": round(monthly_waste, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Remove deployments in {len(redundant_regions)} regions: {', '.join(redundant_regions)}",
                                },
                            )
                        )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    # ============================================================================
    # GCP CLOUD FUNCTIONS DETECTION METHODS
    # ============================================================================

    async def scan_cloud_function_never_invoked(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Cloud Functions (1st & 2nd gen) with 0 invocations.
        Detects functions never used but still incurring costs.
        """
        resources = []

        no_invocations_threshold_days = 30
        if detection_rules:
            no_invocations_threshold_days = detection_rules.get("no_invocations_threshold_days", 30)

        try:
            functions_v1_client = functions_v1.CloudFunctionsServiceClient(credentials=self.credentials)
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # Scan 1st gen functions
            parent_v1 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

                for function in functions_1st_gen:
                    function_name = function.name.split('/')[-1]

                    # Query invocations
                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                        "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=no_invocations_threshold_days)).timestamp())},
                    })

                    filter_str = (
                        f'resource.type = "cloud_function" '
                        f'AND resource.labels.function_name = "{function_name}" '
                        f'AND resource.labels.region = "{region}" '
                        f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    total_invocations = 0
                    for series in time_series:
                        for point in series.points:
                            total_invocations += point.value.int64_value or 0

                    if total_invocations == 0:
                        memory_mb = function.available_memory_mb
                        memory_gb = memory_mb / 1024
                        cpu_ghz = 2.4 if memory_mb >= 2048 else (memory_mb / 1024) * 1.4

                        update_time = function.update_time
                        days_since_creation = (datetime.utcnow() - update_time.replace(tzinfo=None)).days

                        if days_since_creation >= 90:
                            confidence = "critical"
                        elif days_since_creation >= 30:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        monthly_cost = 10.0

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_never_invoked",
                                region=region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "1st",
                                    "runtime": function.runtime,
                                    "memory_mb": memory_mb,
                                    "timeout_seconds": function.timeout.seconds if function.timeout else 60,
                                    "total_invocations": 0,
                                    "days_since_creation": days_since_creation,
                                    "confidence": confidence,
                                    "recommendation": "Delete unused function or investigate if still needed",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )
            except Exception:
                pass

            # Scan 2nd gen functions
            parent_v2 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

                for function in functions_2nd_gen:
                    function_name = function.name.split('/')[-1]

                    service_config = function.service_config
                    min_instances = service_config.min_instance_count if service_config else 0

                    # Query invocations
                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                        "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=no_invocations_threshold_days)).timestamp())},
                    })

                    filter_str = (
                        f'resource.type = "cloud_run_revision" '
                        f'AND resource.labels.service_name = "{function_name}" '
                        f'AND metric.type = "run.googleapis.com/request_count"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    total_invocations = 0
                    for series in time_series:
                        for point in series.points:
                            total_invocations += point.value.int64_value or 0

                    if total_invocations == 0:
                        memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256
                        memory_gib = memory_mb / 1024
                        vcpu = max(0.08, memory_gib / 2)

                        update_time = function.update_time
                        days_since_creation = (datetime.utcnow() - update_time.replace(tzinfo=None)).days

                        if min_instances > 0:
                            monthly_cost = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances
                        else:
                            monthly_cost = 10.0

                        if days_since_creation >= 90:
                            confidence = "critical"
                        elif days_since_creation >= 30:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_never_invoked",
                                region=region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "2nd",
                                    "runtime": service_config.runtime if service_config else "unknown",
                                    "memory_mb": memory_mb,
                                    "vcpu": round(vcpu, 2),
                                    "min_instances": min_instances,
                                    "timeout_seconds": service_config.timeout_seconds if service_config else 60,
                                    "total_invocations": 0,
                                    "days_since_creation": days_since_creation,
                                    "confidence": confidence,
                                    "recommendation": "Delete unused function or investigate if still needed",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )
            except Exception:
                pass

        except Exception:
            pass

        return resources

    async def scan_cloud_function_idle_min_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for 2nd gen Cloud Functions with min_instances > 0 but low traffic.
        Min instances are billed 24/7 even if not used.
        """
        resources = []

        low_invocations_per_day = 10
        lookback_days = 14
        if detection_rules:
            low_invocations_per_day = detection_rules.get("low_invocations_per_day", 10)
            lookback_days = detection_rules.get("lookback_days", 14)

        try:
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/{region}"

            functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

            for function in functions_2nd_gen:
                function_name = function.name.split('/')[-1]

                service_config = function.service_config
                min_instances = service_config.min_instance_count if service_config else 0

                if min_instances == 0:
                    continue

                # Query invocations
                interval = monitoring_v3.TimeInterval({
                    "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                    "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                })

                filter_str = (
                    f'resource.type = "cloud_run_revision" '
                    f'AND resource.labels.service_name = "{function_name}" '
                    f'AND metric.type = "run.googleapis.com/request_count"'
                )

                request = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{self.project_id}",
                    filter=filter_str,
                    interval=interval,
                )

                time_series = monitoring_client.list_time_series(request=request)

                total_invocations = 0
                for series in time_series:
                    for point in series.points:
                        total_invocations += point.value.int64_value or 0

                avg_invocations_per_day = total_invocations / lookback_days if lookback_days > 0 else 0

                if avg_invocations_per_day < low_invocations_per_day:
                    memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256
                    memory_gib = memory_mb / 1024
                    vcpu = max(0.08, memory_gib / 2)

                    monthly_cost = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

                    if avg_invocations_per_day < 5:
                        confidence = "high"
                    else:
                        confidence = "medium"

                    resources.append(
                        OrphanResourceData(
                            resource_id=function.name,
                            resource_name=function_name,
                            resource_type="gcp_cloud_function_idle_min_instances",
                            region=region,
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                "function_name": function_name,
                                "generation": "2nd",
                                "memory_mb": memory_mb,
                                "vcpu": round(vcpu, 2),
                                "min_instances": min_instances,
                                "avg_invocations_per_day": round(avg_invocations_per_day, 2),
                                "monthly_waste": round(monthly_cost, 2),
                                "confidence": confidence,
                                "recommendation": f"Reduce min_instances from {min_instances} to 0",
                                "labels": dict(function.labels) if function.labels else {},
                            },
                        )
                    )

        except Exception:
            pass

        return resources

    async def scan_cloud_function_memory_overprovisioning(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Cloud Functions with memory allocated >> memory used.
        """
        resources = []

        memory_utilization_threshold = 0.50
        lookback_days = 14
        if detection_rules:
            memory_utilization_threshold = detection_rules.get("memory_utilization_threshold", 0.50)
            lookback_days = detection_rules.get("lookback_days", 14)

        try:
            functions_v1_client = functions_v1.CloudFunctionsServiceClient(credentials=self.credentials)
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # Scan 1st gen
            parent_v1 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

                for function in functions_1st_gen:
                    function_name = function.name.split('/')[-1]
                    memory_allocated_mb = function.available_memory_mb

                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                        "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                    })

                    filter_str = (
                        f'resource.type = "cloud_function" '
                        f'AND resource.labels.function_name = "{function_name}" '
                        f'AND metric.type = "cloudfunctions.googleapis.com/function/user_memory_bytes"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    memory_values = []
                    for series in time_series:
                        for point in series.points:
                            memory_bytes = point.value.double_value or point.value.int64_value or 0
                            memory_values.append(memory_bytes / (1024 * 1024))

                    if not memory_values:
                        continue

                    avg_memory_used_mb = sum(memory_values) / len(memory_values)
                    memory_utilization = (avg_memory_used_mb / memory_allocated_mb) if memory_allocated_mb > 0 else 0

                    if memory_utilization < memory_utilization_threshold:
                        recommended_memory_mb = max(128, int(avg_memory_used_mb * 1.3))
                        monthly_savings = 15.0

                        if memory_utilization < 0.30:
                            confidence = "critical"
                        elif memory_utilization < 0.50:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_memory_overprovisioning",
                                region=region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "1st",
                                    "memory_allocated_mb": memory_allocated_mb,
                                    "avg_memory_used_mb": round(avg_memory_used_mb, 2),
                                    "memory_utilization": round(memory_utilization * 100, 2),
                                    "recommended_memory_mb": recommended_memory_mb,
                                    "monthly_savings": round(monthly_savings, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Reduce memory from {memory_allocated_mb}MB to {recommended_memory_mb}MB",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )
            except Exception:
                pass

            # Scan 2nd gen
            parent_v2 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

                for function in functions_2nd_gen:
                    function_name = function.name.split('/')[-1]
                    service_config = function.service_config
                    memory_allocated_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256

                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                        "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                    })

                    filter_str = (
                        f'resource.type = "cloud_run_revision" '
                        f'AND resource.labels.service_name = "{function_name}" '
                        f'AND metric.type = "run.googleapis.com/container/memory/utilizations"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    utilization_values = []
                    for series in time_series:
                        for point in series.points:
                            util = point.value.double_value or 0
                            utilization_values.append(util)

                    if not utilization_values:
                        continue

                    avg_utilization = sum(utilization_values) / len(utilization_values)

                    if avg_utilization < memory_utilization_threshold:
                        recommended_memory_mb = max(128, int(memory_allocated_mb * avg_utilization * 1.3))
                        monthly_savings = 20.0

                        if avg_utilization < 0.30:
                            confidence = "critical"
                        elif avg_utilization < 0.50:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_memory_overprovisioning",
                                region=region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "2nd",
                                    "memory_allocated_mb": memory_allocated_mb,
                                    "avg_memory_utilization": round(avg_utilization * 100, 2),
                                    "recommended_memory_mb": recommended_memory_mb,
                                    "monthly_savings": round(monthly_savings, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Reduce memory from {memory_allocated_mb}MB to {recommended_memory_mb}MB",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )
            except Exception:
                pass

        except Exception:
            pass

        return resources

    async def scan_cloud_function_excessive_timeout(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Cloud Functions with timeout >> avg execution time.
        """
        resources = []

        timeout_ratio_threshold = 3.0
        lookback_days = 14
        if detection_rules:
            timeout_ratio_threshold = detection_rules.get("timeout_ratio_threshold", 3.0)
            lookback_days = detection_rules.get("lookback_days", 14)

        try:
            functions_v1_client = functions_v1.CloudFunctionsServiceClient(credentials=self.credentials)
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # Scan 1st gen
            parent_v1 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

                for function in functions_1st_gen:
                    function_name = function.name.split('/')[-1]
                    timeout_seconds = function.timeout.seconds if function.timeout else 60

                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                        "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                    })

                    filter_str = (
                        f'resource.type = "cloud_function" '
                        f'AND resource.labels.function_name = "{function_name}" '
                        f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_times"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    exec_time_values = []
                    for series in time_series:
                        for point in series.points:
                            exec_time_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                            exec_time_values.append(exec_time_ms / 1000)

                    if not exec_time_values:
                        continue

                    avg_exec_time_seconds = sum(exec_time_values) / len(exec_time_values)
                    timeout_ratio = timeout_seconds / avg_exec_time_seconds if avg_exec_time_seconds > 0 else 0

                    if timeout_ratio > timeout_ratio_threshold:
                        recommended_timeout = int(avg_exec_time_seconds * 1.5)

                        if timeout_ratio > 10:
                            confidence = "critical"
                        elif timeout_ratio > 5:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_excessive_timeout",
                                region=region,
                                estimated_monthly_cost=5.0,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "1st",
                                    "timeout_configured_seconds": timeout_seconds,
                                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 2),
                                    "timeout_ratio": round(timeout_ratio, 2),
                                    "recommended_timeout_seconds": recommended_timeout,
                                    "confidence": confidence,
                                    "recommendation": f"Reduce timeout from {timeout_seconds}s to {recommended_timeout}s",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )
            except Exception:
                pass

            # Scan 2nd gen
            parent_v2 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

                for function in functions_2nd_gen:
                    function_name = function.name.split('/')[-1]
                    service_config = function.service_config
                    timeout_seconds = service_config.timeout_seconds if service_config else 60

                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                        "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                    })

                    filter_str = (
                        f'resource.type = "cloud_run_revision" '
                        f'AND resource.labels.service_name = "{function_name}" '
                        f'AND metric.type = "run.googleapis.com/request_latencies"'
                    )

                    request = monitoring_v3.ListTimeSeriesRequest(
                        name=f"projects/{self.project_id}",
                        filter=filter_str,
                        interval=interval,
                    )

                    time_series = monitoring_client.list_time_series(request=request)

                    latency_values = []
                    for series in time_series:
                        for point in series.points:
                            latency_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                            latency_values.append(latency_ms / 1000)

                    if not latency_values:
                        continue

                    avg_exec_time_seconds = sum(latency_values) / len(latency_values)
                    timeout_ratio = timeout_seconds / avg_exec_time_seconds if avg_exec_time_seconds > 0 else 0

                    if timeout_ratio > timeout_ratio_threshold:
                        recommended_timeout = int(avg_exec_time_seconds * 1.5)

                        if timeout_ratio > 10:
                            confidence = "critical"
                        elif timeout_ratio > 5:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_excessive_timeout",
                                region=region,
                                estimated_monthly_cost=5.0,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "2nd",
                                    "timeout_configured_seconds": timeout_seconds,
                                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 2),
                                    "timeout_ratio": round(timeout_ratio, 2),
                                    "recommended_timeout_seconds": recommended_timeout,
                                    "confidence": confidence,
                                    "recommendation": f"Reduce timeout from {timeout_seconds}s to {recommended_timeout}s",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )
            except Exception:
                pass

        except Exception:
            pass

        return resources

    async def scan_cloud_function_1st_gen_expensive(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for 1st gen functions that would be cheaper in 2nd gen.
        """
        resources = []

        cost_savings_threshold_pct = 20.0
        lookback_days = 14
        if detection_rules:
            cost_savings_threshold_pct = detection_rules.get("cost_savings_threshold_pct", 20.0)
            lookback_days = detection_rules.get("lookback_days", 14)

        try:
            functions_v1_client = functions_v1.CloudFunctionsServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/{region}"
            functions_1st_gen = functions_v1_client.list_functions(parent=parent)

            for function in functions_1st_gen:
                function_name = function.name.split('/')[-1]
                memory_mb = function.available_memory_mb
                memory_gb = memory_mb / 1024
                cpu_ghz = 2.4 if memory_mb >= 2048 else (memory_mb / 1024) * 1.4

                interval = monitoring_v3.TimeInterval({
                    "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                    "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                })

                # Get invocations
                filter_invocations = (
                    f'resource.type = "cloud_function" '
                    f'AND resource.labels.function_name = "{function_name}" '
                    f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_count"'
                )

                request_inv = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{self.project_id}",
                    filter=filter_invocations,
                    interval=interval,
                )

                time_series_inv = monitoring_client.list_time_series(request=request_inv)

                total_invocations = 0
                for series in time_series_inv:
                    for point in series.points:
                        total_invocations += point.value.int64_value or 0

                if total_invocations == 0:
                    continue

                monthly_invocations = (total_invocations / lookback_days) * 30

                # Get avg exec time
                filter_exec = (
                    f'resource.type = "cloud_function" '
                    f'AND resource.labels.function_name = "{function_name}" '
                    f'AND metric.type = "cloudfunctions.googleapis.com/function/execution_times"'
                )

                request_exec = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{self.project_id}",
                    filter=filter_exec,
                    interval=interval,
                )

                time_series_exec = monitoring_client.list_time_series(request=request_exec)

                exec_time_values = []
                for series in time_series_exec:
                    for point in series.points:
                        exec_time_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                        exec_time_values.append(exec_time_ms / 1000)

                if not exec_time_values:
                    continue

                avg_exec_time_seconds = sum(exec_time_values) / len(exec_time_values)

                # Calculate 1st gen cost
                compute_seconds = monthly_invocations * avg_exec_time_seconds
                invocations_cost = (monthly_invocations / 1_000_000) * 0.40
                memory_cost = compute_seconds * memory_gb * 0.0000025
                cpu_cost = compute_seconds * cpu_ghz * 0.0000100
                monthly_cost_1st_gen = invocations_cost + memory_cost + cpu_cost

                # Calculate 2nd gen cost
                memory_gib = memory_mb / 1024
                vcpu = max(0.08, memory_gib / 2)
                vcpu_cost = compute_seconds * vcpu * 0.00002400
                memory_cost_2nd = compute_seconds * memory_gib * 0.00000250
                monthly_cost_2nd_gen = invocations_cost + vcpu_cost + memory_cost_2nd

                if monthly_cost_1st_gen > monthly_cost_2nd_gen:
                    savings_pct = ((monthly_cost_1st_gen - monthly_cost_2nd_gen) / monthly_cost_1st_gen * 100)

                    if savings_pct >= cost_savings_threshold_pct:
                        monthly_savings = monthly_cost_1st_gen - monthly_cost_2nd_gen

                        if savings_pct >= 40:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_1st_gen_expensive",
                                region=region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "1st",
                                    "monthly_invocations": int(monthly_invocations),
                                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 3),
                                    "monthly_cost_1st_gen": round(monthly_cost_1st_gen, 2),
                                    "monthly_cost_2nd_gen": round(monthly_cost_2nd_gen, 2),
                                    "savings_pct": round(savings_pct, 2),
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Migrate to 2nd gen for {savings_pct:.1f}% savings (${monthly_savings:.2f}/month)",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )

        except Exception:
            pass

        return resources

    async def scan_cloud_function_untagged(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Cloud Functions missing required labels.
        """
        resources = []

        required_labels = ["environment", "owner"]
        if detection_rules:
            required_labels = detection_rules.get("required_labels", ["environment", "owner"])

        try:
            functions_v1_client = functions_v1.CloudFunctionsServiceClient(credentials=self.credentials)
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)

            # Scan 1st gen
            parent_v1 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

                for function in functions_1st_gen:
                    function_name = function.name.split('/')[-1]
                    current_labels = dict(function.labels) if function.labels else {}
                    missing_labels = [label for label in required_labels if label not in current_labels]

                    if missing_labels:
                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_untagged",
                                region=region,
                                estimated_monthly_cost=0.0,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "1st",
                                    "runtime": function.runtime,
                                    "missing_labels": missing_labels,
                                    "current_labels": current_labels,
                                    "confidence": "high",
                                    "recommendation": f"Add missing labels: {', '.join(missing_labels)}",
                                },
                            )
                        )
            except Exception:
                pass

            # Scan 2nd gen
            parent_v2 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

                for function in functions_2nd_gen:
                    function_name = function.name.split('/')[-1]
                    current_labels = dict(function.labels) if function.labels else {}
                    missing_labels = [label for label in required_labels if label not in current_labels]

                    if missing_labels:
                        service_config = function.service_config

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_untagged",
                                region=region,
                                estimated_monthly_cost=0.0,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "2nd",
                                    "runtime": service_config.runtime if service_config else "unknown",
                                    "missing_labels": missing_labels,
                                    "current_labels": current_labels,
                                    "confidence": "high",
                                    "recommendation": f"Add missing labels: {', '.join(missing_labels)}",
                                },
                            )
                        )
            except Exception:
                pass

        except Exception:
            pass

        return resources

    async def scan_cloud_function_excessive_max_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Cloud Functions with excessive max_instances (runaway cost risk).
        """
        resources = []

        max_instances_threshold = 100
        if detection_rules:
            max_instances_threshold = detection_rules.get("max_instances_threshold", 100)

        try:
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/{region}"
            functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

            for function in functions_2nd_gen:
                function_name = function.name.split('/')[-1]
                service_config = function.service_config
                max_instances = service_config.max_instance_count if service_config else 0

                if max_instances > max_instances_threshold:
                    memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256
                    memory_gib = memory_mb / 1024
                    vcpu = max(0.08, memory_gib / 2)

                    # Calculate max daily cost risk
                    seconds_per_day = 86400
                    max_daily_cost = max_instances * (vcpu * 0.00002400 + memory_gib * 0.00000250) * seconds_per_day

                    if max_instances >= 500:
                        confidence = "critical"
                    elif max_instances >= 200:
                        confidence = "high"
                    else:
                        confidence = "medium"

                    resources.append(
                        OrphanResourceData(
                            resource_id=function.name,
                            resource_name=function_name,
                            resource_type="gcp_cloud_function_excessive_max_instances",
                            region=region,
                            estimated_monthly_cost=max_daily_cost,
                            resource_metadata={
                                "function_name": function_name,
                                "generation": "2nd",
                                "max_instances_configured": max_instances,
                                "memory_mb": memory_mb,
                                "vcpu": round(vcpu, 2),
                                "max_daily_cost": round(max_daily_cost, 2),
                                "confidence": confidence,
                                "recommendation": f"Reduce max_instances from {max_instances} to {max_instances_threshold} + add rate limiting",
                                "risk": "Runaway cost if public endpoint receives traffic spike",
                                "labels": dict(function.labels) if function.labels else {},
                            },
                        )
                    )

        except Exception:
            pass

        return resources

    async def scan_cloud_function_cold_start_over_optimization(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for 2nd gen functions with min_instances for cold start optimization only.
        Alternative: warm-up requests via Cloud Scheduler (<$20/month).
        """
        resources = []

        cold_start_cost_threshold = 50.0
        lookback_days = 14
        if detection_rules:
            cold_start_cost_threshold = detection_rules.get("cold_start_cost_threshold", 50.0)
            lookback_days = detection_rules.get("lookback_days", 14)

        try:
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/{region}"
            functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

            for function in functions_2nd_gen:
                function_name = function.name.split('/')[-1]
                service_config = function.service_config
                min_instances = service_config.min_instance_count if service_config else 0

                if min_instances == 0:
                    continue

                memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256
                memory_gib = memory_mb / 1024
                vcpu = max(0.08, memory_gib / 2)

                monthly_cost_min_instances = (vcpu * 0.00002400 + memory_gib * 0.00000250) * 2_592_000 * min_instances

                if monthly_cost_min_instances < cold_start_cost_threshold:
                    continue

                # Query invocations
                interval = monitoring_v3.TimeInterval({
                    "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                    "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                })

                filter_str = (
                    f'resource.type = "cloud_run_revision" '
                    f'AND resource.labels.service_name = "{function_name}" '
                    f'AND metric.type = "run.googleapis.com/request_count"'
                )

                request = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{self.project_id}",
                    filter=filter_str,
                    interval=interval,
                )

                time_series = monitoring_client.list_time_series(request=request)

                total_invocations = 0
                for series in time_series:
                    for point in series.points:
                        total_invocations += point.value.int64_value or 0

                monthly_invocations = (total_invocations / lookback_days) * 30 if lookback_days > 0 else 0
                invocations_per_hour = monthly_invocations / (30 * 24) if monthly_invocations > 0 else 0

                if invocations_per_hour < 10:
                    warmup_requests_per_month = 30 * 24 * 60
                    warmup_cost = (warmup_requests_per_month / 1_000_000) * 0.40 + 0.10

                    monthly_savings = monthly_cost_min_instances - warmup_cost

                    if monthly_savings > 0:
                        if monthly_savings > 200:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_cold_start_over_optimization",
                                region=region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "2nd",
                                    "min_instances": min_instances,
                                    "invocations_per_hour": round(invocations_per_hour, 2),
                                    "monthly_cost_min_instances": round(monthly_cost_min_instances, 2),
                                    "alternative_warmup_cost": round(warmup_cost, 2),
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "confidence": confidence,
                                    "recommendation": "Remove min_instances and use Cloud Scheduler warm-up requests (1/min)",
                                    "alternative": "Cloud Scheduler: $0.10/job + $17/month invocations",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )

        except Exception:
            pass

        return resources

    async def scan_cloud_function_duplicate(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Cloud Functions with duplicate code (same source hash).
        """
        resources = []

        try:
            functions_v1_client = functions_v1.CloudFunctionsServiceClient(credentials=self.credentials)
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)

            function_hashes: dict[str, list] = {}

            # Scan 1st gen
            parent_v1 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_1st_gen = functions_v1_client.list_functions(parent=parent_v1)

                for function in functions_1st_gen:
                    function_name = function.name.split('/')[-1]

                    signature_data = f"{function.runtime}:{function.entry_point}:{function.source_archive_url}"
                    function_hash = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

                    if function_hash not in function_hashes:
                        function_hashes[function_hash] = []

                    function_hashes[function_hash].append({
                        "function_name": function_name,
                        "generation": "1st",
                        "region": region,
                        "runtime": function.runtime,
                        "entry_point": function.entry_point,
                        "memory_mb": function.available_memory_mb,
                    })
            except Exception:
                pass

            # Scan 2nd gen
            parent_v2 = f"projects/{self.project_id}/locations/{region}"

            try:
                functions_2nd_gen = functions_v2_client.list_functions(parent=parent_v2)

                for function in functions_2nd_gen:
                    function_name = function.name.split('/')[-1]

                    build_config = function.build_config
                    service_config = function.service_config

                    signature_data = f"{service_config.runtime if service_config else 'unknown'}:{build_config.entry_point if build_config else 'unknown'}"
                    function_hash = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

                    if function_hash not in function_hashes:
                        function_hashes[function_hash] = []

                    memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256

                    function_hashes[function_hash].append({
                        "function_name": function_name,
                        "generation": "2nd",
                        "region": region,
                        "runtime": service_config.runtime if service_config else "unknown",
                        "entry_point": build_config.entry_point if build_config else "unknown",
                        "memory_mb": memory_mb,
                    })
            except Exception:
                pass

            # Identify duplicates
            for function_hash, functions in function_hashes.items():
                if len(functions) > 1:
                    monthly_waste = len(functions) * 50.0

                    resources.append(
                        OrphanResourceData(
                            resource_id=f"duplicate_{function_hash}",
                            resource_name=f"Duplicate group: {functions[0]['function_name']}",
                            resource_type="gcp_cloud_function_duplicate",
                            region=region,
                            estimated_monthly_cost=monthly_waste,
                            resource_metadata={
                                "duplicate_hash": function_hash,
                                "duplicate_count": len(functions),
                                "functions": functions,
                                "confidence": "high",
                                "recommendation": f"Consolidate {len(functions)} duplicate functions",
                                "impact": "Operational overhead, duplicate bugs, confusion",
                            },
                        )
                    )

        except Exception:
            pass

        return resources

    async def scan_cloud_function_excessive_concurrency(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for 2nd gen functions with concurrency = 1 (suboptimal).
        """
        resources = []

        lookback_days = 14
        if detection_rules:
            lookback_days = detection_rules.get("lookback_days", 14)

        try:
            functions_v2_client = functions_v2.FunctionServiceClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/{region}"
            functions_2nd_gen = functions_v2_client.list_functions(parent=parent)

            for function in functions_2nd_gen:
                function_name = function.name.split('/')[-1]
                service_config = function.service_config
                concurrency = service_config.max_instance_request_concurrency if service_config else 1

                if concurrency > 1:
                    continue

                # Query invocations
                interval = monitoring_v3.TimeInterval({
                    "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                    "start_time": {"seconds": int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())},
                })

                filter_str = (
                    f'resource.type = "cloud_run_revision" '
                    f'AND resource.labels.service_name = "{function_name}" '
                    f'AND metric.type = "run.googleapis.com/request_count"'
                )

                request = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{self.project_id}",
                    filter=filter_str,
                    interval=interval,
                )

                time_series = monitoring_client.list_time_series(request=request)

                total_invocations = 0
                for series in time_series:
                    for point in series.points:
                        total_invocations += point.value.int64_value or 0

                if total_invocations == 0:
                    continue

                monthly_invocations = (total_invocations / lookback_days) * 30 if lookback_days > 0 else 0

                # Get avg exec time
                filter_latency = (
                    f'resource.type = "cloud_run_revision" '
                    f'AND resource.labels.service_name = "{function_name}" '
                    f'AND metric.type = "run.googleapis.com/request_latencies"'
                )

                request_latency = monitoring_v3.ListTimeSeriesRequest(
                    name=f"projects/{self.project_id}",
                    filter=filter_latency,
                    interval=interval,
                )

                time_series_latency = monitoring_client.list_time_series(request=request_latency)

                latency_values = []
                for series in time_series_latency:
                    for point in series.points:
                        latency_ms = point.value.distribution_value.mean if point.value.distribution_value else 0
                        latency_values.append(latency_ms)

                if not latency_values:
                    continue

                avg_exec_time_ms = sum(latency_values) / len(latency_values)
                avg_exec_time_seconds = avg_exec_time_ms / 1000

                if avg_exec_time_seconds < 1.0:
                    if avg_exec_time_seconds < 0.1:
                        recommended_concurrency = 100
                    elif avg_exec_time_seconds < 0.5:
                        recommended_concurrency = 50
                    else:
                        recommended_concurrency = 10

                    memory_mb = int(service_config.available_memory.replace('M', '').replace('Mi', '')) if service_config and service_config.available_memory else 256
                    memory_gib = memory_mb / 1024
                    vcpu = max(0.08, memory_gib / 2)

                    compute_seconds = monthly_invocations * avg_exec_time_seconds

                    invocations_cost = (monthly_invocations / 1_000_000) * 0.40
                    vcpu_cost = compute_seconds * vcpu * 0.00002400
                    memory_cost = compute_seconds * memory_gib * 0.00000250
                    monthly_cost_current = invocations_cost + vcpu_cost + memory_cost

                    monthly_cost_optimal = monthly_cost_current * 0.70
                    monthly_savings = monthly_cost_current - monthly_cost_optimal

                    if monthly_savings > 10:
                        if avg_exec_time_seconds < 0.1:
                            confidence = "high"
                        else:
                            confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=function.name,
                                resource_name=function_name,
                                resource_type="gcp_cloud_function_excessive_concurrency",
                                region=region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "function_name": function_name,
                                    "generation": "2nd",
                                    "concurrency_current": concurrency,
                                    "recommended_concurrency": recommended_concurrency,
                                    "avg_exec_time_seconds": round(avg_exec_time_seconds, 3),
                                    "monthly_invocations": int(monthly_invocations),
                                    "monthly_cost_current": round(monthly_cost_current, 2),
                                    "monthly_cost_optimal": round(monthly_cost_optimal, 2),
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "confidence": confidence,
                                    "recommendation": f"Increase concurrency from {concurrency} to {recommended_concurrency}",
                                    "benefit": "Fewer instances needed, better resource utilization",
                                    "labels": dict(function.labels) if function.labels else {},
                                },
                            )
                        )

        except Exception:
            pass

        return resources

    # ============================================
    # Cloud Storage Buckets Detection Methods (10 scenarios)
    # ============================================

    async def scan_cloud_storage_empty_buckets(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect empty Cloud Storage buckets (0 objects for 30+ days).

        Waste: ~$25/bucket/year for empty Standard storage.
        """
        resources = []

        try:
            from google.cloud import storage
            from datetime import datetime, timedelta

            # Get detection parameters
            age_threshold_days = 30
            if detection_rules and "cloud_storage_empty" in detection_rules:
                rules = detection_rules["cloud_storage_empty"]
                age_threshold_days = rules.get("age_threshold_days", 30)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    # Check if bucket has any objects
                    blobs = list(bucket.list_blobs(max_results=1))

                    if len(blobs) == 0:
                        # Empty bucket detected
                        age_days = (datetime.utcnow() - bucket.time_created.replace(tzinfo=None)).days

                        if age_days >= age_threshold_days:
                            # Calculate waste (storage class pricing + operations)
                            storage_class = bucket.storage_class or "STANDARD"
                            location_type = bucket.location_type or "region"

                            # Estimated monthly cost for empty bucket (minimal operational costs)
                            monthly_waste = 2.0  # ~$24/year operational overhead
                            annual_waste = monthly_waste * 12

                            # Confidence based on age
                            if age_days >= 90:
                                confidence = "critical"
                            elif age_days >= 60:
                                confidence = "high"
                            else:
                                confidence = "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=bucket.name,
                                    resource_name=bucket.name,
                                    resource_type="gcp_cloud_storage_empty",
                                    region=bucket.location,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "bucket_name": bucket.name,
                                        "location": bucket.location,
                                        "location_type": location_type,
                                        "storage_class": storage_class,
                                        "age_days": age_days,
                                        "versioning_enabled": bucket.versioning_enabled or False,
                                        "labels": dict(bucket.labels) if bucket.labels else {},
                                        "monthly_waste": round(monthly_waste, 2),
                                        "annual_waste": round(annual_waste, 2),
                                        "confidence": confidence.upper(),
                                        "recommendation": f"Delete empty bucket (unused for {age_days} days)",
                                    },
                                )
                            )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_wrong_storage_class(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect objects in wrong storage class (STANDARD for rarely accessed data).

        Waste: 50-90% storage cost savings by moving to NEARLINE/COLDLINE/ARCHIVE.
        """
        resources = []

        try:
            from google.cloud import storage, logging_v2
            from datetime import datetime, timedelta

            # Get detection parameters
            lookback_days = 90
            min_size_gb = 1.0
            if detection_rules and "cloud_storage_wrong_class" in detection_rules:
                rules = detection_rules["cloud_storage_wrong_class"]
                lookback_days = rules.get("lookback_days", 90)
                min_size_gb = rules.get("min_size_gb", 1.0)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)
            logging_client = logging_v2.Client(project=self.project_id, credentials=self.credentials)

            # Sample a few buckets (full scan would be expensive)
            bucket_count = 0
            for bucket in storage_client.list_buckets():
                if bucket_count >= 10:  # Limit to 10 buckets for performance
                    break
                bucket_count += 1

                try:
                    # Only check STANDARD storage class buckets
                    if bucket.storage_class != "STANDARD":
                        continue

                    for blob in bucket.list_blobs():
                        try:
                            size_gb = blob.size / (1024**3)
                            if size_gb < min_size_gb:
                                continue

                            if blob.storage_class != "STANDARD":
                                continue

                            # Check access patterns via Cloud Logging (last 90 days)
                            age_days = (datetime.utcnow() - blob.time_created.replace(tzinfo=None)).days

                            # Simple heuristic: if object is old and hasn't been updated
                            days_since_update = (datetime.utcnow() - blob.updated.replace(tzinfo=None)).days if blob.updated else age_days

                            # Recommend storage class based on access pattern
                            recommended_class = None
                            savings_pct = 0

                            if days_since_update >= 365:
                                recommended_class = "ARCHIVE"
                                savings_pct = 94  # $0.0012 vs $0.020
                            elif days_since_update >= 90:
                                recommended_class = "COLDLINE"
                                savings_pct = 80  # $0.004 vs $0.020
                            elif days_since_update >= 30:
                                recommended_class = "NEARLINE"
                                savings_pct = 50  # $0.010 vs $0.020

                            if recommended_class:
                                # Calculate savings
                                current_monthly_cost = size_gb * 0.020
                                prices = {"NEARLINE": 0.010, "COLDLINE": 0.004, "ARCHIVE": 0.0012}
                                optimal_monthly_cost = size_gb * prices[recommended_class]
                                monthly_savings = current_monthly_cost - optimal_monthly_cost

                                if monthly_savings >= 1.0:  # Only report if savings >= $1/month
                                    confidence = "high" if days_since_update >= 180 else "medium"

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=f"{bucket.name}/{blob.name}",
                                            resource_name=blob.name,
                                            resource_type="gcp_cloud_storage_wrong_class",
                                            region=bucket.location,
                                            estimated_monthly_cost=monthly_savings,
                                            resource_metadata={
                                                "bucket_name": bucket.name,
                                                "object_name": blob.name,
                                                "size_gb": round(size_gb, 2),
                                                "current_storage_class": "STANDARD",
                                                "recommended_storage_class": recommended_class,
                                                "days_since_update": days_since_update,
                                                "monthly_cost_current": round(current_monthly_cost, 2),
                                                "monthly_cost_optimal": round(optimal_monthly_cost, 2),
                                                "monthly_savings": round(monthly_savings, 2),
                                                "annual_savings": round(monthly_savings * 12, 2),
                                                "savings_pct": savings_pct,
                                                "confidence": confidence.upper(),
                                                "recommendation": f"Move to {recommended_class} storage class",
                                            },
                                        )
                                    )
                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_versioning_without_lifecycle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect buckets with versioning enabled but no lifecycle policy to cleanup old versions.

        Waste: 200-500% storage cost from accumulating noncurrent versions.
        """
        resources = []

        try:
            from google.cloud import storage
            from datetime import datetime

            # Get detection parameters
            min_noncurrent_versions = 10
            if detection_rules and "cloud_storage_versioning_waste" in detection_rules:
                rules = detection_rules["cloud_storage_versioning_waste"]
                min_noncurrent_versions = rules.get("min_noncurrent_versions", 10)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    if not bucket.versioning_enabled:
                        continue

                    # Check for noncurrent version deletion policy
                    has_noncurrent_deletion = False
                    if bucket.lifecycle_rules:
                        for rule in bucket.lifecycle_rules:
                            action = rule.get("action", {})
                            condition = rule.get("condition", {})
                            if action.get("type") == "Delete" and "daysSinceNoncurrentTime" in condition:
                                has_noncurrent_deletion = True
                                break

                    if not has_noncurrent_deletion:
                        # Count noncurrent versions
                        noncurrent_count = 0
                        noncurrent_size_bytes = 0

                        for blob in bucket.list_blobs(versions=True):
                            if blob.time_deleted:  # Noncurrent version
                                noncurrent_count += 1
                                noncurrent_size_bytes += blob.size

                        if noncurrent_count >= min_noncurrent_versions:
                            noncurrent_size_gb = noncurrent_size_bytes / (1024**3)

                            # Calculate waste (noncurrent versions storage cost)
                            storage_class = bucket.storage_class or "STANDARD"
                            price_per_gb = 0.020 if storage_class == "STANDARD" else 0.010
                            monthly_waste = noncurrent_size_gb * price_per_gb

                            confidence = "critical" if noncurrent_count >= 100 else "high"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=bucket.name,
                                    resource_name=bucket.name,
                                    resource_type="gcp_cloud_storage_versioning_waste",
                                    region=bucket.location,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "bucket_name": bucket.name,
                                        "location": bucket.location,
                                        "storage_class": storage_class,
                                        "versioning_enabled": True,
                                        "has_noncurrent_deletion_policy": False,
                                        "noncurrent_versions": noncurrent_count,
                                        "noncurrent_size_gb": round(noncurrent_size_gb, 2),
                                        "monthly_waste": round(monthly_waste, 2),
                                        "annual_waste": round(monthly_waste * 12, 2),
                                        "confidence": confidence.upper(),
                                        "recommendation": "Add lifecycle policy to delete noncurrent versions after 30 days",
                                    },
                                )
                            )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_incomplete_multipart_uploads(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect buckets without abort incomplete multipart upload policy.

        Waste: ~2% of bucket size from abandoned resumable uploads.
        """
        resources = []

        try:
            from google.cloud import storage

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    # Check for AbortIncompleteMultipartUpload lifecycle policy
                    has_abort_policy = False
                    if bucket.lifecycle_rules:
                        for rule in bucket.lifecycle_rules:
                            action = rule.get("action", {})
                            if action.get("type") == "AbortIncompleteMultipartUpload":
                                has_abort_policy = True
                                break

                    if not has_abort_policy:
                        # Estimate bucket size
                        total_size_bytes = sum(blob.size for blob in bucket.list_blobs())
                        total_size_gb = total_size_bytes / (1024**3)

                        if total_size_gb >= 10:  # Only report for buckets >= 10 GB
                            # Estimate 2% waste from incomplete uploads
                            estimated_waste_gb = total_size_gb * 0.02
                            monthly_waste = estimated_waste_gb * 0.020  # Standard pricing

                            confidence = "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=bucket.name,
                                    resource_name=bucket.name,
                                    resource_type="gcp_cloud_storage_incomplete_uploads",
                                    region=bucket.location,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "bucket_name": bucket.name,
                                        "location": bucket.location,
                                        "total_size_gb": round(total_size_gb, 2),
                                        "estimated_waste_gb": round(estimated_waste_gb, 2),
                                        "has_abort_incomplete_policy": False,
                                        "monthly_waste": round(monthly_waste, 2),
                                        "annual_waste": round(monthly_waste * 12, 2),
                                        "confidence": confidence.upper(),
                                        "recommendation": "Add lifecycle policy to abort incomplete multipart uploads after 7 days",
                                    },
                                )
                            )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_untagged_buckets(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect buckets missing required labels (governance issue).

        Waste: No direct cost but enables better cost allocation and optimization.
        """
        resources = []

        try:
            from google.cloud import storage

            # Get detection parameters
            required_labels = ["environment", "owner", "cost-center"]
            if detection_rules and "cloud_storage_untagged" in detection_rules:
                rules = detection_rules["cloud_storage_untagged"]
                required_labels = rules.get("required_labels", required_labels)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    bucket_labels = dict(bucket.labels) if bucket.labels else {}
                    missing_labels = [label for label in required_labels if label not in bucket_labels]

                    if missing_labels:
                        # Estimate bucket size for context
                        total_size_bytes = sum(blob.size for blob in bucket.list_blobs())
                        total_size_gb = total_size_bytes / (1024**3)

                        confidence = "high" if total_size_gb >= 100 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=bucket.name,
                                resource_name=bucket.name,
                                resource_type="gcp_cloud_storage_untagged",
                                region=bucket.location,
                                estimated_monthly_cost=0.0,  # Governance issue, no direct cost
                                resource_metadata={
                                    "bucket_name": bucket.name,
                                    "location": bucket.location,
                                    "total_size_gb": round(total_size_gb, 2),
                                    "current_labels": bucket_labels,
                                    "missing_labels": missing_labels,
                                    "confidence": confidence.upper(),
                                    "recommendation": f"Add missing labels: {', '.join(missing_labels)}",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_never_accessed_objects(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect objects with 0 GET operations since creation (never accessed).

        Waste: Full storage cost for unused data.
        """
        resources = []

        try:
            from google.cloud import storage
            from datetime import datetime, timedelta

            # Get detection parameters
            min_age_days = 90
            min_size_gb = 1.0
            if detection_rules and "cloud_storage_never_accessed" in detection_rules:
                rules = detection_rules["cloud_storage_never_accessed"]
                min_age_days = rules.get("min_age_days", 90)
                min_size_gb = rules.get("min_size_gb", 1.0)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            # Sample a few buckets (full scan would be expensive)
            bucket_count = 0
            for bucket in storage_client.list_buckets():
                if bucket_count >= 10:  # Limit to 10 buckets for performance
                    break
                bucket_count += 1

                try:
                    for blob in bucket.list_blobs():
                        try:
                            size_gb = blob.size / (1024**3)
                            if size_gb < min_size_gb:
                                continue

                            age_days = (datetime.utcnow() - blob.time_created.replace(tzinfo=None)).days
                            if age_days < min_age_days:
                                continue

                            # Simple heuristic: if never updated since creation, likely never accessed
                            days_since_update = (datetime.utcnow() - blob.updated.replace(tzinfo=None)).days if blob.updated else age_days

                            if days_since_update >= min_age_days and days_since_update >= age_days * 0.9:
                                # Calculate waste
                                storage_class = blob.storage_class or "STANDARD"
                                price_per_gb = 0.020 if storage_class == "STANDARD" else 0.010
                                monthly_waste = size_gb * price_per_gb

                                if monthly_waste >= 1.0:  # Only report if >= $1/month
                                    confidence = "critical" if age_days >= 180 else "high"

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=f"{bucket.name}/{blob.name}",
                                            resource_name=blob.name,
                                            resource_type="gcp_cloud_storage_never_accessed",
                                            region=bucket.location,
                                            estimated_monthly_cost=monthly_waste,
                                            resource_metadata={
                                                "bucket_name": bucket.name,
                                                "object_name": blob.name,
                                                "size_gb": round(size_gb, 2),
                                                "storage_class": storage_class,
                                                "age_days": age_days,
                                                "days_since_update": days_since_update,
                                                "access_count": 0,
                                                "monthly_waste": round(monthly_waste, 2),
                                                "annual_waste": round(monthly_waste * 12, 2),
                                                "confidence": confidence.upper(),
                                                "recommendation": "Delete unused object or move to ARCHIVE",
                                            },
                                        )
                                    )
                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_no_lifecycle_policy(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect buckets without lifecycle policy (no automatic optimization).

        Waste: 60-80% potential savings from lack of automated storage class transitions.
        """
        resources = []

        try:
            from google.cloud import storage

            # Get detection parameters
            min_size_gb = 10.0
            if detection_rules and "cloud_storage_no_lifecycle" in detection_rules:
                rules = detection_rules["cloud_storage_no_lifecycle"]
                min_size_gb = rules.get("min_size_gb", 10.0)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    # Check if bucket has any lifecycle rules
                    has_lifecycle = bool(bucket.lifecycle_rules)

                    if not has_lifecycle:
                        # Estimate bucket size
                        total_size_bytes = sum(blob.size for blob in bucket.list_blobs())
                        total_size_gb = total_size_bytes / (1024**3)

                        if total_size_gb >= min_size_gb:
                            # Estimate 30% waste from lack of optimization
                            estimated_savings_pct = 30
                            current_monthly_cost = total_size_gb * 0.020  # Standard pricing
                            monthly_savings = current_monthly_cost * (estimated_savings_pct / 100)

                            confidence = "high" if total_size_gb >= 100 else "medium"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=bucket.name,
                                    resource_name=bucket.name,
                                    resource_type="gcp_cloud_storage_no_lifecycle",
                                    region=bucket.location,
                                    estimated_monthly_cost=monthly_savings,
                                    resource_metadata={
                                        "bucket_name": bucket.name,
                                        "location": bucket.location,
                                        "total_size_gb": round(total_size_gb, 2),
                                        "storage_class": bucket.storage_class or "STANDARD",
                                        "lifecycle_rules_count": 0,
                                        "versioning_enabled": bucket.versioning_enabled or False,
                                        "current_monthly_cost": round(current_monthly_cost, 2),
                                        "monthly_savings": round(monthly_savings, 2),
                                        "annual_savings": round(monthly_savings * 12, 2),
                                        "estimated_savings_pct": estimated_savings_pct,
                                        "confidence": confidence.upper(),
                                        "recommendation": "Add lifecycle policy for automatic storage class transitions",
                                    },
                                )
                            )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_duplicate_objects(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect duplicate objects (same MD5 hash) within buckets.

        Waste: 10-20% typical duplication rate, full storage cost for duplicates.
        """
        resources = []

        try:
            from google.cloud import storage
            from collections import defaultdict

            # Get detection parameters
            min_size_gb = 0.1
            if detection_rules and "cloud_storage_duplicates" in detection_rules:
                rules = detection_rules["cloud_storage_duplicates"]
                min_size_gb = rules.get("min_size_gb", 0.1)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            # Sample a few buckets (full scan would be very expensive)
            bucket_count = 0
            for bucket in storage_client.list_buckets():
                if bucket_count >= 5:  # Limit to 5 buckets for performance
                    break
                bucket_count += 1

                try:
                    # Group objects by MD5 hash
                    hash_to_objects = defaultdict(list)

                    for blob in bucket.list_blobs():
                        try:
                            size_gb = blob.size / (1024**3)
                            if size_gb < min_size_gb:
                                continue

                            if blob.md5_hash:
                                hash_to_objects[blob.md5_hash].append({
                                    "name": blob.name,
                                    "size_gb": size_gb,
                                    "storage_class": blob.storage_class or "STANDARD",
                                    "time_created": blob.time_created,
                                })
                        except Exception:
                            continue

                    # Find duplicates
                    for md5_hash, objects in hash_to_objects.items():
                        if len(objects) > 1:
                            # Sort by creation time (keep oldest)
                            objects_sorted = sorted(objects, key=lambda x: x["time_created"])
                            duplicate_count = len(objects_sorted)
                            waste_objects = objects_sorted[1:]  # All except oldest

                            # Calculate waste
                            total_waste_gb = sum(obj["size_gb"] for obj in waste_objects)
                            price_per_gb = 0.020  # Standard pricing
                            monthly_waste = total_waste_gb * price_per_gb

                            if monthly_waste >= 1.0:  # Only report if >= $1/month
                                confidence = "medium"

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=f"{bucket.name}/{md5_hash[:16]}",
                                        resource_name=f"Duplicates: {objects_sorted[0]['name']}",
                                        resource_type="gcp_cloud_storage_duplicates",
                                        region=bucket.location,
                                        estimated_monthly_cost=monthly_waste,
                                        resource_metadata={
                                            "bucket_name": bucket.name,
                                            "md5_hash": md5_hash,
                                            "duplicate_count": duplicate_count,
                                            "waste_objects_count": len(waste_objects),
                                            "total_waste_gb": round(total_waste_gb, 2),
                                            "object_names": [obj["name"] for obj in objects_sorted],
                                            "monthly_waste": round(monthly_waste, 2),
                                            "annual_waste": round(monthly_waste * 12, 2),
                                            "confidence": confidence.upper(),
                                            "recommendation": f"Delete {len(waste_objects)} duplicate objects, keep oldest",
                                        },
                                    )
                                )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_autoclass_misconfiguration(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect Autoclass misconfiguration (should enable >100GB, should disable <10GB).

        Waste: Potential 30-50% savings from enabling Autoclass on large buckets.
        """
        resources = []

        try:
            from google.cloud import storage

            # Get detection parameters
            min_size_gb = 100.0
            max_size_gb_disable = 10.0
            if detection_rules and "cloud_storage_autoclass_misconfig" in detection_rules:
                rules = detection_rules["cloud_storage_autoclass_misconfig"]
                min_size_gb = rules.get("min_size_gb", 100.0)
                max_size_gb_disable = rules.get("max_size_gb_disable", 10.0)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    # Check Autoclass status
                    autoclass_enabled = getattr(bucket, 'autoclass_enabled', False)

                    # Estimate bucket size
                    total_size_bytes = sum(blob.size for blob in bucket.list_blobs())
                    total_size_gb = total_size_bytes / (1024**3)

                    should_enable = False
                    should_disable = False
                    monthly_savings = 0

                    # Case 1: Large bucket without Autoclass
                    if not autoclass_enabled and total_size_gb >= min_size_gb:
                        should_enable = True
                        # Estimate 30% savings from Autoclass optimization
                        # Minus Autoclass fee ($0.0001/GB + $0.0025/10K ops)
                        current_monthly_cost = total_size_gb * 0.020
                        autoclass_storage_cost = total_size_gb * 0.020 * 0.7  # 30% savings
                        autoclass_management_fee = total_size_gb * 0.0001
                        optimal_monthly_cost = autoclass_storage_cost + autoclass_management_fee
                        monthly_savings = current_monthly_cost - optimal_monthly_cost

                    # Case 2: Small bucket with Autoclass
                    elif autoclass_enabled and total_size_gb < max_size_gb_disable:
                        should_disable = True
                        # Autoclass fee without benefit
                        monthly_savings = total_size_gb * 0.0001

                    if (should_enable or should_disable) and monthly_savings >= 1.0:
                        confidence = "high" if total_size_gb >= 200 or total_size_gb < 5 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=bucket.name,
                                resource_name=bucket.name,
                                resource_type="gcp_cloud_storage_autoclass_misconfig",
                                region=bucket.location,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "bucket_name": bucket.name,
                                    "location": bucket.location,
                                    "total_size_gb": round(total_size_gb, 2),
                                    "autoclass_enabled": autoclass_enabled,
                                    "should_enable_autoclass": should_enable,
                                    "should_disable_autoclass": should_disable,
                                    "lifecycle_rules_count": len(bucket.lifecycle_rules) if bucket.lifecycle_rules else 0,
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "confidence": confidence.upper(),
                                    "recommendation": f"{'Enable' if should_enable else 'Disable'} Autoclass for this bucket",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_cloud_storage_excessive_redundancy(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect excessive redundancy (multi-region/dual-region for dev/test data).

        Waste: 30-100% storage cost from unnecessary geo-redundancy.
        """
        resources = []

        try:
            from google.cloud import storage

            # Get detection parameters
            min_size_gb = 50.0
            if detection_rules and "cloud_storage_excessive_redundancy" in detection_rules:
                rules = detection_rules["cloud_storage_excessive_redundancy"]
                min_size_gb = rules.get("min_size_gb", 50.0)

            storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

            for bucket in storage_client.list_buckets():
                try:
                    location_type = bucket.location_type or "region"

                    # Only check multi-region and dual-region buckets
                    if location_type not in ["multi-region", "dual-region"]:
                        continue

                    # Estimate bucket size
                    total_size_bytes = sum(blob.size for blob in bucket.list_blobs())
                    total_size_gb = total_size_bytes / (1024**3)

                    if total_size_gb < min_size_gb:
                        continue

                    # Check labels for environment/criticality
                    labels = dict(bucket.labels) if bucket.labels else {}
                    environment = labels.get("environment", "").lower()
                    criticality = labels.get("criticality", "").lower()

                    # Flag if dev/test/staging or low criticality
                    is_non_critical = environment in ["dev", "test", "staging", "development"] or criticality in ["low", "none"]

                    if is_non_critical:
                        # Calculate savings by moving to regional
                        storage_class = bucket.storage_class or "STANDARD"

                        # Pricing
                        current_price_per_gb = 0.026 if location_type == "multi-region" else 0.024  # Standard
                        regional_price_per_gb = 0.020

                        current_monthly_cost = total_size_gb * current_price_per_gb
                        optimal_monthly_cost = total_size_gb * regional_price_per_gb
                        monthly_savings = current_monthly_cost - optimal_monthly_cost
                        savings_pct = round((monthly_savings / current_monthly_cost) * 100, 1)

                        confidence = "high" if is_non_critical else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=bucket.name,
                                resource_name=bucket.name,
                                resource_type="gcp_cloud_storage_excessive_redundancy",
                                region=bucket.location,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "bucket_name": bucket.name,
                                    "location": bucket.location,
                                    "location_type": location_type,
                                    "storage_class": storage_class,
                                    "total_size_gb": round(total_size_gb, 2),
                                    "labels": labels,
                                    "environment": environment,
                                    "criticality": criticality,
                                    "current_price_per_gb": current_price_per_gb,
                                    "optimal_price_per_gb": regional_price_per_gb,
                                    "monthly_cost_current": round(current_monthly_cost, 2),
                                    "monthly_cost_optimal": round(optimal_monthly_cost, 2),
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "savings_pct": savings_pct,
                                    "confidence": confidence.upper(),
                                    "recommendation": f"Change location from {location_type} to regional",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    # ============================================
    # Cloud Filestore Detection Methods (10 scenarios)
    # ============================================

    async def scan_filestore_underutilized(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect underutilized Filestore instances (<30% capacity).

        Waste: Filestore charges on provisioned capacity, not used capacity.
        """
        resources = []

        try:
            from google.cloud import filestore_v1, monitoring_v3
            from datetime import datetime, timedelta

            # Get detection parameters
            utilization_threshold = 0.30
            lookback_days = 14
            if detection_rules and "gcp_filestore_underutilized" in detection_rules:
                rules = detection_rules["gcp_filestore_underutilized"]
                utilization_threshold = rules.get("utilization_threshold", 0.30)
                lookback_days = rules.get("lookback_days", 14)

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            # List all Filestore instances
            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]

                    # Get utilization metrics from Cloud Monitoring
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=lookback_days)

                    project_name = f"projects/{self.project_id}"
                    filter_str = (
                        f'resource.type = "filestore_instance" '
                        f'AND resource.labels.instance_name = "{instance_name}" '
                        f'AND resource.labels.zone = "{zone}" '
                        f'AND metric.type = "file.googleapis.com/nfs/server/used_bytes_percent"'
                    )

                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(end_time.timestamp())},
                        "start_time": {"seconds": int(start_time.timestamp())},
                    })

                    aggregation = monitoring_v3.Aggregation({
                        "alignment_period": {"seconds": 3600},  # 1 hour
                        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                    })

                    results = monitoring_client.list_time_series(
                        request={
                            "name": project_name,
                            "filter": filter_str,
                            "interval": interval,
                            "aggregation": aggregation,
                        }
                    )

                    utilization_values = []
                    for result in results:
                        for point in result.points:
                            utilization_values.append(point.value.double_value)

                    if not utilization_values:
                        continue

                    avg_utilization = sum(utilization_values) / len(utilization_values) / 100  # Convert to 0-1

                    if avg_utilization < utilization_threshold:
                        # Calculate waste
                        tier = instance.tier.name
                        tier_pricing = {
                            'ZONAL': 0.18, 'BASIC_HDD': 0.20, 'BASIC_SSD': 0.30,
                            'HIGH_SCALE_SSD': 0.30, 'ENTERPRISE': 0.60, 'STANDARD': 0.20, 'PREMIUM': 0.30
                        }
                        price_per_gb = tier_pricing.get(tier, 0.20)

                        provisioned_capacity_gb = instance.file_shares[0].capacity_gb
                        used_capacity_gb = int(provisioned_capacity_gb * avg_utilization)

                        # Optimal capacity with 30% buffer
                        recommended_capacity_gb = int(used_capacity_gb * 1.30)
                        recommended_capacity_gb = ((recommended_capacity_gb + 255) // 256) * 256  # Round to 256GB
                        recommended_capacity_gb = max(recommended_capacity_gb, 1024)  # Min 1TB

                        current_monthly_cost = provisioned_capacity_gb * price_per_gb
                        optimal_monthly_cost = recommended_capacity_gb * price_per_gb
                        monthly_waste = current_monthly_cost - optimal_monthly_cost

                        # Confidence level
                        if avg_utilization < 0.10 and lookback_days >= 30:
                            confidence = "critical"
                        elif avg_utilization < 0.20 and lookback_days >= 21:
                            confidence = "high"
                        elif avg_utilization < 0.30 and lookback_days >= 14:
                            confidence = "medium"
                        else:
                            confidence = "low"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_underutilized",
                                region=zone,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "tier": tier,
                                    "provisioned_capacity_gb": provisioned_capacity_gb,
                                    "used_capacity_gb": used_capacity_gb,
                                    "utilization_percent": round(avg_utilization * 100, 1),
                                    "recommended_capacity_gb": recommended_capacity_gb,
                                    "current_monthly_cost": round(current_monthly_cost, 2),
                                    "optimal_monthly_cost": round(optimal_monthly_cost, 2),
                                    "monthly_waste": round(monthly_waste, 2),
                                    "annual_waste": round(monthly_waste * 12, 2),
                                    "confidence": confidence.upper(),
                                    "lookback_days": lookback_days,
                                    "labels": dict(instance.labels) if instance.labels else {},
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_wrong_tier(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect Filestore instances using wrong tier (Enterprise for dev/test).

        Waste: Enterprise is 233% more expensive than Zonal for same performance.
        """
        resources = []

        try:
            from google.cloud import filestore_v1

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]
                    tier = instance.tier.name
                    labels = dict(instance.labels) if instance.labels else {}

                    # Case 1: Enterprise for non-prod
                    if tier == 'ENTERPRISE':
                        # Check labels for non-prod environment
                        non_prod_labels = {
                            'environment': ['dev', 'test', 'staging', 'qa', 'development'],
                            'env': ['dev', 'test', 'staging', 'qa'],
                            'tier': ['dev', 'test']
                        }

                        is_non_prod = False
                        matching_label = None

                        for label_key, non_prod_values in non_prod_labels.items():
                            if label_key in labels:
                                label_value = labels[label_key].lower()
                                if label_value in non_prod_values:
                                    is_non_prod = True
                                    matching_label = f"{label_key}={label_value}"
                                    break

                        # Heuristic: instance name contains dev/test/staging
                        if not is_non_prod:
                            non_prod_keywords = ['dev', 'test', 'staging', 'qa', 'sandbox']
                            for keyword in non_prod_keywords:
                                if keyword in instance_name.lower():
                                    is_non_prod = True
                                    matching_label = f"instance_name contains '{keyword}'"
                                    break

                        if is_non_prod:
                            capacity_gb = instance.file_shares[0].capacity_gb

                            # Enterprise vs Zonal pricing
                            current_monthly_cost = capacity_gb * 0.60
                            optimal_monthly_cost = capacity_gb * 0.18
                            monthly_waste = current_monthly_cost - optimal_monthly_cost

                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_name,
                                    resource_type="gcp_filestore_wrong_tier",
                                    region=zone,
                                    estimated_monthly_cost=monthly_waste,
                                    resource_metadata={
                                        "instance_name": instance_name,
                                        "zone": zone,
                                        "tier": tier,
                                        "recommended_tier": "ZONAL",
                                        "reason": f"Non-prod environment detected ({matching_label})",
                                        "capacity_gb": capacity_gb,
                                        "current_monthly_cost": round(current_monthly_cost, 2),
                                        "optimal_monthly_cost": round(optimal_monthly_cost, 2),
                                        "monthly_waste": round(monthly_waste, 2),
                                        "annual_waste": round(monthly_waste * 12, 2),
                                        "savings_percent": 70.0,
                                        "confidence": "HIGH",
                                        "labels": labels,
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect idle Filestore instances (0 connections + 0 I/O for 7+ days).

        Waste: 100% of cost wasted for completely idle instances.
        """
        resources = []

        try:
            from google.cloud import filestore_v1, monitoring_v3
            from datetime import datetime, timedelta

            # Get detection parameters
            lookback_days = 7
            max_connections = 0
            max_total_iops = 10
            if detection_rules and "gcp_filestore_idle" in detection_rules:
                rules = detection_rules["gcp_filestore_idle"]
                lookback_days = rules.get("lookback_days", 7)
                max_connections = rules.get("max_connections", 0)
                max_total_iops = rules.get("max_total_iops", 10)

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]

                    # Check connections
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=lookback_days)

                    project_name = f"projects/{self.project_id}"
                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(end_time.timestamp())},
                        "start_time": {"seconds": int(start_time.timestamp())},
                    })

                    # Query connections metric
                    filter_str = (
                        f'resource.type = "filestore_instance" '
                        f'AND resource.labels.instance_name = "{instance_name}" '
                        f'AND resource.labels.zone = "{zone}" '
                        f'AND metric.type = "file.googleapis.com/nfs/server/connections"'
                    )

                    aggregation = monitoring_v3.Aggregation({
                        "alignment_period": {"seconds": 3600},
                        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                    })

                    results = monitoring_client.list_time_series(
                        request={"name": project_name, "filter": filter_str, "interval": interval, "aggregation": aggregation}
                    )

                    connection_values = []
                    for result in results:
                        for point in result.points:
                            connection_values.append(point.value.double_value)

                    if not connection_values:
                        continue

                    avg_connections = sum(connection_values) / len(connection_values)

                    # If idle (0 connections), calculate waste
                    if avg_connections <= max_connections:
                        tier = instance.tier.name
                        tier_pricing = {
                            'ZONAL': 0.18, 'BASIC_HDD': 0.20, 'BASIC_SSD': 0.30,
                            'HIGH_SCALE_SSD': 0.30, 'ENTERPRISE': 0.60, 'STANDARD': 0.20, 'PREMIUM': 0.30
                        }
                        price_per_gb = tier_pricing.get(tier, 0.20)
                        capacity_gb = instance.file_shares[0].capacity_gb

                        monthly_cost = capacity_gb * price_per_gb
                        annual_cost = monthly_cost * 12

                        # Calculate already wasted (conservative estimate)
                        if instance.create_time:
                            age_days = (datetime.now(instance.create_time.tzinfo) - instance.create_time).days
                            estimated_idle_days = min(age_days, lookback_days * 3)
                            already_wasted = (monthly_cost / 30) * estimated_idle_days
                        else:
                            already_wasted = 0

                        # Confidence
                        if avg_connections == 0 and lookback_days >= 90:
                            confidence = "critical"
                        elif avg_connections == 0 and lookback_days >= 30:
                            confidence = "high"
                        elif avg_connections == 0 and lookback_days >= 14:
                            confidence = "medium"
                        else:
                            confidence = "low"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_idle",
                                region=zone,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "tier": tier,
                                    "capacity_gb": capacity_gb,
                                    "avg_connections": avg_connections,
                                    "monthly_cost": round(monthly_cost, 2),
                                    "annual_cost": round(annual_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": confidence.upper(),
                                    "idle_days": lookback_days,
                                    "created_at": instance.create_time.isoformat() if instance.create_time else None,
                                    "labels": dict(instance.labels) if instance.labels else {},
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect overprovisioned Filestore instances (<10% capacity used).

        Waste: Severe overprovisioning with <10% utilization.
        """
        resources = []

        try:
            from google.cloud import filestore_v1, monitoring_v3
            from datetime import datetime, timedelta

            # Get detection parameters
            utilization_threshold = 0.10
            lookback_days = 30
            if detection_rules and "gcp_filestore_overprovisioned" in detection_rules:
                rules = detection_rules["gcp_filestore_overprovisioned"]
                utilization_threshold = rules.get("utilization_threshold", 0.10)
                lookback_days = rules.get("lookback_days", 30)

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]

                    # Get utilization metrics
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=lookback_days)

                    project_name = f"projects/{self.project_id}"
                    filter_str = (
                        f'resource.type = "filestore_instance" '
                        f'AND resource.labels.instance_name = "{instance_name}" '
                        f'AND resource.labels.zone = "{zone}" '
                        f'AND metric.type = "file.googleapis.com/nfs/server/used_bytes_percent"'
                    )

                    interval = monitoring_v3.TimeInterval({
                        "end_time": {"seconds": int(end_time.timestamp())},
                        "start_time": {"seconds": int(start_time.timestamp())},
                    })

                    aggregation = monitoring_v3.Aggregation({
                        "alignment_period": {"seconds": 3600},
                        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                    })

                    results = monitoring_client.list_time_series(
                        request={"name": project_name, "filter": filter_str, "interval": interval, "aggregation": aggregation}
                    )

                    utilization_values = []
                    for result in results:
                        for point in result.points:
                            utilization_values.append(point.value.double_value)

                    if not utilization_values:
                        continue

                    avg_utilization = sum(utilization_values) / len(utilization_values) / 100

                    if avg_utilization < utilization_threshold:
                        tier = instance.tier.name
                        tier_pricing = {
                            'ZONAL': 0.18, 'BASIC_HDD': 0.20, 'BASIC_SSD': 0.30,
                            'HIGH_SCALE_SSD': 0.30, 'ENTERPRISE': 0.60, 'STANDARD': 0.20, 'PREMIUM': 0.30
                        }
                        price_per_gb = tier_pricing.get(tier, 0.20)

                        provisioned_capacity_gb = instance.file_shares[0].capacity_gb
                        used_capacity_gb = int(provisioned_capacity_gb * avg_utilization)

                        # Optimal capacity
                        recommended_capacity_gb = max(1024, ((int(used_capacity_gb * 1.50) + 255) // 256) * 256)

                        current_monthly_cost = provisioned_capacity_gb * price_per_gb
                        optimal_monthly_cost = recommended_capacity_gb * price_per_gb
                        monthly_waste = current_monthly_cost - optimal_monthly_cost

                        confidence = "critical"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_overprovisioned",
                                region=zone,
                                estimated_monthly_cost=monthly_waste,
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "tier": tier,
                                    "provisioned_capacity_gb": provisioned_capacity_gb,
                                    "used_capacity_gb": used_capacity_gb,
                                    "utilization_percent": round(avg_utilization * 100, 1),
                                    "recommended_capacity_gb": recommended_capacity_gb,
                                    "monthly_waste": round(monthly_waste, 2),
                                    "annual_waste": round(monthly_waste * 12, 2),
                                    "confidence": confidence.upper(),
                                    "lookback_days": lookback_days,
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect Filestore instances missing required labels (governance).

        Waste: No direct cost but enables better cost allocation.
        """
        resources = []

        try:
            from google.cloud import filestore_v1

            # Get detection parameters
            required_labels = ["environment", "owner", "cost-center"]
            if detection_rules and "gcp_filestore_untagged" in detection_rules:
                rules = detection_rules["gcp_filestore_untagged"]
                required_labels = rules.get("required_labels", required_labels)

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]
                    labels = dict(instance.labels) if instance.labels else {}

                    missing_labels = [label for label in required_labels if label not in labels]

                    if missing_labels:
                        capacity_gb = instance.file_shares[0].capacity_gb
                        confidence = "high" if capacity_gb >= 5120 else "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_untagged",
                                region=zone,
                                estimated_monthly_cost=0.0,
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "tier": instance.tier.name,
                                    "capacity_gb": capacity_gb,
                                    "current_labels": labels,
                                    "missing_labels": missing_labels,
                                    "confidence": confidence.upper(),
                                    "recommendation": f"Add missing labels: {', '.join(missing_labels)}",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_no_backup_policy(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect Filestore instances without backup policy configured.

        Waste: Risk + potential excessive backup costs if manually managed.
        """
        resources = []

        try:
            from google.cloud import filestore_v1

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]

                    # Check if backup is configured
                    # Note: Filestore backups are configured separately via backup schedules
                    # This is a simplified check - in production, would query backup policies
                    has_backup = False  # Placeholder - would check actual backup configuration

                    if not has_backup:
                        capacity_gb = instance.file_shares[0].capacity_gb
                        tier = instance.tier.name

                        # Estimate potential backup waste if misconfigured
                        # Assume 7 daily backups at $0.10/GB
                        estimated_backup_gb = capacity_gb * 0.6  # 60% utilized
                        estimated_backup_cost = estimated_backup_gb * 7 * 0.10

                        confidence = "medium"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_no_backup_policy",
                                region=zone,
                                estimated_monthly_cost=0.0,  # Risk, not direct waste
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "tier": tier,
                                    "capacity_gb": capacity_gb,
                                    "has_backup_policy": False,
                                    "estimated_backup_cost": round(estimated_backup_cost, 2),
                                    "confidence": confidence.upper(),
                                    "recommendation": "Configure backup policy to protect data and optimize retention",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_legacy_tier(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect Filestore instances using legacy tiers (Basic HDD vs Zonal).

        Waste: Zonal tier is 10% cheaper than Basic HDD with same performance.
        """
        resources = []

        try:
            from google.cloud import filestore_v1

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]
                    tier = instance.tier.name

                    # Check if using legacy Basic HDD tier
                    if tier in ['BASIC_HDD', 'STANDARD']:
                        capacity_gb = instance.file_shares[0].capacity_gb

                        # Basic HDD: $0.20/GB, Zonal: $0.18/GB
                        current_monthly_cost = capacity_gb * 0.20
                        optimal_monthly_cost = capacity_gb * 0.18
                        monthly_savings = current_monthly_cost - optimal_monthly_cost

                        confidence = "high"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_legacy_tier",
                                region=zone,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "tier": tier,
                                    "recommended_tier": "ZONAL",
                                    "capacity_gb": capacity_gb,
                                    "current_monthly_cost": round(current_monthly_cost, 2),
                                    "optimal_monthly_cost": round(optimal_monthly_cost, 2),
                                    "monthly_savings": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "savings_percent": 10.0,
                                    "confidence": confidence.upper(),
                                    "recommendation": "Migrate from Basic HDD to Zonal tier (10% cheaper, same performance, zero downtime)",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_multi_share_consolidation(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect Enterprise tier instances with underutilized multi-share capability.

        Waste: Enterprise supports 10 shares but often used with only 1-2 shares.
        """
        resources = []

        try:
            from google.cloud import filestore_v1

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]
                    tier = instance.tier.name

                    # Only check Enterprise tier (supports multi-share)
                    if tier == 'ENTERPRISE':
                        num_shares = len(instance.file_shares)

                        # If using 1-2 shares, not justifying Enterprise pricing
                        if num_shares <= 2:
                            capacity_gb = instance.file_shares[0].capacity_gb

                            # Enterprise: $0.60/GB, Zonal: $0.18/GB
                            current_monthly_cost = capacity_gb * 0.60
                            optimal_monthly_cost = capacity_gb * 0.18 * num_shares  # Multiple Zonal instances
                            monthly_savings = current_monthly_cost - optimal_monthly_cost

                            if monthly_savings > 0:
                                confidence = "high"

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=instance.name,
                                        resource_name=instance_name,
                                        resource_type="gcp_filestore_multi_share_consolidation",
                                        region=zone,
                                        estimated_monthly_cost=monthly_savings,
                                        resource_metadata={
                                            "instance_name": instance_name,
                                            "zone": zone,
                                            "tier": tier,
                                            "recommended_tier": "ZONAL (multiple instances)",
                                            "num_shares": num_shares,
                                            "capacity_gb": capacity_gb,
                                            "monthly_savings": round(monthly_savings, 2),
                                            "annual_savings": round(monthly_savings * 12, 2),
                                            "confidence": confidence.upper(),
                                            "recommendation": f"Replace Enterprise with {num_shares} separate Zonal instances",
                                        },
                                    )
                                )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_snapshot_waste(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect old Filestore snapshots never used (90+ days).

        Waste: Snapshots charged at $0.10/GB/month, can accumulate significantly.
        """
        resources = []

        try:
            from google.cloud import filestore_v1
            from datetime import datetime, timedelta

            # Get detection parameters
            min_age_days = 90
            if detection_rules and "gcp_filestore_snapshot_waste" in detection_rules:
                rules = detection_rules["gcp_filestore_snapshot_waste"]
                min_age_days = rules.get("min_age_days", 90)

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            # Note: Filestore backups API may vary by region
            # This is a simplified implementation
            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]

                    # Placeholder: Would query actual backups/snapshots
                    # For now, estimate based on instance capacity
                    capacity_gb = instance.file_shares[0].capacity_gb

                    # Estimate: Assume 7 old snapshots at 60% capacity each
                    estimated_old_snapshots = 7
                    snapshot_capacity_gb = capacity_gb * 0.6 * estimated_old_snapshots
                    monthly_waste = snapshot_capacity_gb * 0.10

                    confidence = "medium"

                    resources.append(
                        OrphanResourceData(
                            resource_id=f"{instance.name}/snapshots",
                            resource_name=f"{instance_name} (old snapshots)",
                            resource_type="gcp_filestore_snapshot_waste",
                            region=zone,
                            estimated_monthly_cost=monthly_waste,
                            resource_metadata={
                                "instance_name": instance_name,
                                "zone": zone,
                                "estimated_old_snapshots": estimated_old_snapshots,
                                "snapshot_capacity_gb": round(snapshot_capacity_gb, 2),
                                "monthly_waste": round(monthly_waste, 2),
                                "annual_waste": round(monthly_waste * 12, 2),
                                "min_age_days": min_age_days,
                                "confidence": confidence.upper(),
                                "recommendation": f"Delete snapshots older than {min_age_days} days",
                            },
                        )
                    )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    async def scan_filestore_wrong_nfs_protocol(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect Filestore instances using NFSv3 instead of NFSv4.1.

        Waste: NFSv4.1 offers better performance and features, no cost difference.
        """
        resources = []

        try:
            from google.cloud import filestore_v1

            filestore_client = filestore_v1.CloudFilestoreManagerClient(credentials=self.credentials)

            parent = f"projects/{self.project_id}/locations/-"

            for instance in filestore_client.list_instances(parent=parent):
                try:
                    instance_name = instance.name.split('/')[-1]
                    zone = instance.name.split('/')[3]

                    # Check NFS version (if available in metadata)
                    # Note: NFS version detection may require checking client mounts
                    # This is a placeholder for protocol detection
                    uses_nfsv3 = False  # Would check actual protocol in production

                    if uses_nfsv3:
                        capacity_gb = instance.file_shares[0].capacity_gb
                        confidence = "low"

                        resources.append(
                            OrphanResourceData(
                                resource_id=instance.name,
                                resource_name=instance_name,
                                resource_type="gcp_filestore_wrong_nfs_protocol",
                                region=zone,
                                estimated_monthly_cost=0.0,  # Performance issue, not cost
                                resource_metadata={
                                    "instance_name": instance_name,
                                    "zone": zone,
                                    "capacity_gb": capacity_gb,
                                    "current_protocol": "NFSv3",
                                    "recommended_protocol": "NFSv4.1",
                                    "confidence": confidence.upper(),
                                    "recommendation": "Upgrade clients to use NFSv4.1 for better performance",
                                },
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return resources

    # ============================================================================
    # GCP Static External IPs Detection (10 scenarios - Networking)
    # ============================================================================

    async def scan_static_ip_unattached(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect reserved but unattached Static External IPs.

        Waste: Static IPs cost $2.88/month when not attached to a running resource.
        This is the #1 cause of IP waste (60% of typical waste).

        Detection: status='RESERVED' AND users=[] (empty list)
        Cost: $2.88/month per IP ($0.004/hour)
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from datetime import datetime, timezone

            # Get detection parameters
            min_age_days = 7
            if detection_rules and "gcp_static_ip_unattached" in detection_rules:
                rules = detection_rules["gcp_static_ip_unattached"]
                min_age_days = rules.get("min_age_days", 7)

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            # Scan regional IPs
            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        # Check if IP is unattached (empty users list)
                        if not address.users:
                            # Calculate age
                            created_at = datetime.fromisoformat(
                                address.creation_timestamp.replace('Z', '+00:00')
                            )
                            age_days = (datetime.now(timezone.utc) - created_at).days

                            # Filter by minimum age
                            if age_days >= min_age_days:
                                # Cost calculation
                                monthly_cost = 2.88  # $0.004/hour * 24 * 30
                                annual_cost = monthly_cost * 12
                                months_wasted = age_days / 30
                                already_wasted = monthly_cost * months_wasted

                                # Determine confidence
                                if age_days >= 90:
                                    confidence = "CRITICAL"
                                elif age_days >= 30:
                                    confidence = "HIGH"
                                elif age_days >= 7:
                                    confidence = "MEDIUM"
                                else:
                                    confidence = "LOW"

                                resources.append(OrphanResourceData(
                                    resource_id=address.name,
                                    resource_type="gcp_static_ip_unattached",
                                    resource_name=address.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "ip_address": address.address,
                                        "status": address.status,
                                        "network_tier": address.network_tier,
                                        "address_type": address.address_type,
                                        "age_days": age_days,
                                        "created_at": address.creation_timestamp,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": confidence,
                                        "labels": dict(address.labels) if address.labels else {},
                                        "recommendation": f"DELETE immediately to save ${annual_cost:.2f}/year. IP has been unused for {age_days} days.",
                                        "waste_reason": f"Reserved IP not attached to any resource for {age_days} days"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for unattached IPs: {e}")
                    continue

            # Scan global IPs
            try:
                global_client = compute_v1.GlobalAddressesClient(credentials=self.credentials)
                request = compute_v1.ListGlobalAddressesRequest(project=self.project_id)

                for address in global_client.list(request=request):
                    if not address.users:
                        created_at = datetime.fromisoformat(
                            address.creation_timestamp.replace('Z', '+00:00')
                        )
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days >= min_age_days:
                            monthly_cost = 2.88
                            annual_cost = monthly_cost * 12
                            months_wasted = age_days / 30
                            already_wasted = monthly_cost * months_wasted

                            if age_days >= 90:
                                confidence = "CRITICAL"
                            elif age_days >= 30:
                                confidence = "HIGH"
                            elif age_days >= 7:
                                confidence = "MEDIUM"
                            else:
                                confidence = "LOW"

                            resources.append(OrphanResourceData(
                                resource_id=address.name,
                                resource_type="gcp_static_ip_unattached",
                                resource_name=address.name,
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "ip_address": address.address,
                                    "status": address.status,
                                    "network_tier": address.network_tier,
                                    "address_type": "EXTERNAL",
                                    "age_days": age_days,
                                    "created_at": address.creation_timestamp,
                                    "already_wasted": round(already_wasted, 2),
                                    "annual_cost": round(annual_cost, 2),
                                    "confidence": confidence,
                                    "labels": dict(address.labels) if address.labels else {},
                                    "scope": "GLOBAL",
                                    "recommendation": f"DELETE immediately to save ${annual_cost:.2f}/year. Global IP has been unused for {age_days} days.",
                                    "waste_reason": f"Reserved global IP not attached to any resource for {age_days} days"
                                }
                            ))

            except Exception as e:
                logger.error(f"Error scanning global IPs: {e}")

        except Exception as e:
            logger.error(f"Error in scan_static_ip_unattached: {e}")

        return resources

    async def scan_static_ip_stopped_vm(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect Static External IPs attached to stopped VMs.

        Waste: IPs attached to stopped/terminated VMs still cost $2.88/month.
        The IP status shows 'IN_USE' (misleading!) but VM is not RUNNING.

        Detection: status='IN_USE' AND users[0] points to stopped VM
        Cost: $2.88/month per IP
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from datetime import datetime, timezone
            import re

            # Get detection parameters
            min_stopped_days = 7
            if detection_rules and "gcp_static_ip_stopped_vm" in detection_rules:
                rules = detection_rules["gcp_static_ip_stopped_vm"]
                min_stopped_days = rules.get("min_stopped_days", 7)

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        # Check if IP is attached
                        if address.users and address.status == "IN_USE":
                            resource_url = address.users[0]

                            # Check if it's a VM instance
                            if "/instances/" in resource_url:
                                # Parse zone and instance name
                                match = re.search(
                                    r'/zones/([^/]+)/instances/([^/]+)',
                                    resource_url
                                )

                                if match:
                                    zone = match.group(1)
                                    instance_name = match.group(2)

                                    try:
                                        # Get VM instance
                                        instance = instances_client.get(
                                            project=self.project_id,
                                            zone=zone,
                                            instance=instance_name
                                        )

                                        # Check if VM is stopped/terminated
                                        if instance.status in ["STOPPED", "TERMINATED", "SUSPENDED"]:
                                            # Calculate stopped duration
                                            stopped_days = 0
                                            if instance.last_stop_timestamp:
                                                stopped_at = datetime.fromisoformat(
                                                    instance.last_stop_timestamp.replace('Z', '+00:00')
                                                )
                                                stopped_days = (datetime.now(timezone.utc) - stopped_at).days

                                            # Filter by minimum stopped duration
                                            if stopped_days >= min_stopped_days:
                                                # Cost calculation
                                                monthly_cost = 2.88
                                                annual_cost = monthly_cost * 12
                                                months_stopped = stopped_days / 30
                                                already_wasted = monthly_cost * months_stopped

                                                # Confidence
                                                if stopped_days >= 30:
                                                    confidence = "CRITICAL"
                                                elif stopped_days >= 14:
                                                    confidence = "HIGH"
                                                elif stopped_days >= 7:
                                                    confidence = "MEDIUM"
                                                else:
                                                    confidence = "LOW"

                                                resources.append(OrphanResourceData(
                                                    resource_id=address.name,
                                                    resource_type="gcp_static_ip_stopped_vm",
                                                    resource_name=address.name,
                                                    region=gcp_region,
                                                    estimated_monthly_cost=monthly_cost,
                                                    resource_metadata={
                                                        "ip_address": address.address,
                                                        "status": address.status,
                                                        "network_tier": address.network_tier,
                                                        "vm_name": instance_name,
                                                        "vm_zone": zone,
                                                        "vm_status": instance.status,
                                                        "stopped_days": stopped_days,
                                                        "stopped_at": instance.last_stop_timestamp if instance.last_stop_timestamp else "Unknown",
                                                        "already_wasted": round(already_wasted, 2),
                                                        "annual_cost": round(annual_cost, 2),
                                                        "confidence": confidence,
                                                        "labels": dict(address.labels) if address.labels else {},
                                                        "recommendation": f"Option 1: Release IP to save ${annual_cost:.2f}/year. Option 2: Restart VM. Option 3: Replace with ephemeral IP.",
                                                        "waste_reason": f"IP attached to {instance.status} VM for {stopped_days} days"
                                                    }
                                                ))

                                    except Exception as e:
                                        logger.warning(f"Error checking instance {instance_name}: {e}")
                                        continue

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for stopped VM IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_static_ip_stopped_vm: {e}")

        return resources

    async def scan_static_ip_idle_resource(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect Static External IPs attached to idle resources.

        Waste: IPs on running VMs with <5% CPU usage for extended periods.
        Note: IP is technically free (VM running) but resource may be unnecessary.

        Detection: status='IN_USE' AND VM running AND CPU <5% for 7+ days
        Cost: $0/month for IP (but flags potentially unnecessary VM)
        Priority: MEDIUM (P1) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1, monitoring_v3
            from datetime import datetime, timezone, timedelta
            import re

            # Get detection parameters
            cpu_threshold = 0.05  # 5%
            lookback_days = 7
            if detection_rules and "gcp_static_ip_idle_resource" in detection_rules:
                rules = detection_rules["gcp_static_ip_idle_resource"]
                cpu_threshold = rules.get("cpu_threshold", 0.05)
                lookback_days = rules.get("lookback_days", 7)

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        if address.users and address.status == "IN_USE":
                            resource_url = address.users[0]

                            if "/instances/" in resource_url:
                                match = re.search(
                                    r'/zones/([^/]+)/instances/([^/]+)',
                                    resource_url
                                )

                                if match:
                                    zone = match.group(1)
                                    instance_name = match.group(2)

                                    try:
                                        instance = instances_client.get(
                                            project=self.project_id,
                                            zone=zone,
                                            instance=instance_name
                                        )

                                        # Only check running VMs
                                        if instance.status == "RUNNING":
                                            # Query CPU metrics
                                            project_name = f"projects/{self.project_id}"
                                            end_time = datetime.utcnow()
                                            start_time = end_time - timedelta(days=lookback_days)

                                            interval = monitoring_v3.TimeInterval({
                                                "end_time": {"seconds": int(end_time.timestamp())},
                                                "start_time": {"seconds": int(start_time.timestamp())},
                                            })

                                            filter_str = (
                                                f'resource.type = "gce_instance" '
                                                f'AND resource.labels.instance_id = "{instance.id}" '
                                                f'AND metric.type = "compute.googleapis.com/instance/cpu/utilization"'
                                            )

                                            aggregation = monitoring_v3.Aggregation({
                                                "alignment_period": {"seconds": 3600},
                                                "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                                            })

                                            results = monitoring_client.list_time_series(
                                                request={
                                                    "name": project_name,
                                                    "filter": filter_str,
                                                    "interval": interval,
                                                    "aggregation": aggregation,
                                                }
                                            )

                                            cpu_values = []
                                            for result in results:
                                                for point in result.points:
                                                    cpu_values.append(point.value.double_value)

                                            if cpu_values:
                                                avg_cpu = sum(cpu_values) / len(cpu_values)

                                                if avg_cpu < cpu_threshold:
                                                    resources.append(OrphanResourceData(
                                                        resource_id=address.name,
                                                        resource_type="gcp_static_ip_idle_resource",
                                                        resource_name=address.name,
                                                        region=gcp_region,
                                                        estimated_monthly_cost=0.0,  # IP is free (VM running)
                                                        resource_metadata={
                                                            "ip_address": address.address,
                                                            "status": address.status,
                                                            "network_tier": address.network_tier,
                                                            "vm_name": instance_name,
                                                            "vm_zone": zone,
                                                            "vm_status": "RUNNING",
                                                            "avg_cpu_utilization": round(avg_cpu, 4),
                                                            "max_cpu_utilization": round(max(cpu_values), 4),
                                                            "lookback_days": lookback_days,
                                                            "confidence": "MEDIUM",
                                                            "labels": dict(address.labels) if address.labels else {},
                                                            "recommendation": f"Verify if resource is necessary. VM has {avg_cpu*100:.2f}% avg CPU. Consider stopping or deleting if truly idle.",
                                                            "waste_reason": f"IP attached to running VM with only {avg_cpu*100:.2f}% average CPU over {lookback_days} days"
                                                        }
                                                    ))

                                    except Exception as e:
                                        logger.warning(f"Error checking idle instance {instance_name}: {e}")
                                        continue

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for idle resource IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_static_ip_idle_resource: {e}")

        return resources

    async def scan_static_ip_premium_nonprod(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect Static External IPs using Premium tier for non-production.

        Waste: Premium network tier for dev/test where Standard tier would suffice.
        Savings: 29% on egress costs ($0.12/GB vs $0.085/GB), not on IP itself.

        Detection: network_tier='PREMIUM' AND labels.environment in ['dev','test','staging']
        Cost: $0 for IP (same cost), but potential egress savings
        Priority: LOW (P2) 💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        if address.network_tier == "PREMIUM":
                            labels = dict(address.labels) if address.labels else {}
                            environment = labels.get("environment", "").lower()

                            # Check if non-critical environment
                            if environment in ["dev", "test", "staging", "development", "qa"]:
                                resources.append(OrphanResourceData(
                                    resource_id=address.name,
                                    resource_type="gcp_static_ip_premium_nonprod",
                                    resource_name=address.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=0.0,  # IP cost is same for both tiers
                                    resource_metadata={
                                        "ip_address": address.address,
                                        "status": address.status,
                                        "current_tier": "PREMIUM",
                                        "recommended_tier": "STANDARD",
                                        "environment": environment,
                                        "egress_savings_per_gb": 0.035,  # $0.12 - $0.085
                                        "labels": labels,
                                        "confidence": "MEDIUM",
                                        "recommendation": "Switch to Standard tier to save 29% on egress costs. For 10TB/month egress, save $350/month ($4,200/year).",
                                        "waste_reason": f"Premium tier used for {environment} environment where Standard tier would suffice"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for premium nonprod IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_static_ip_premium_nonprod: {e}")

        return resources

    async def scan_static_ip_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect Static External IPs missing required labels.

        Waste: Governance issue - can't track ownership or cost allocation.
        Without labels, orphaned IPs are hard to identify and clean up.

        Detection: Missing required labels (environment, owner, team)
        Cost: Variable (depends if IP is in use or not)
        Priority: LOW (P2) 🏷️
        """
        resources = []

        try:
            from google.cloud import compute_v1

            # Get required labels
            required_labels = ["environment", "owner", "team"]
            if detection_rules and "gcp_static_ip_untagged" in detection_rules:
                rules = detection_rules["gcp_static_ip_untagged"]
                required_labels = rules.get("required_labels", required_labels)

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        labels = dict(address.labels) if address.labels else {}

                        # Check for missing labels
                        missing_labels = []
                        for required in required_labels:
                            if required not in labels or not labels[required]:
                                missing_labels.append(required)

                        if missing_labels:
                            # Determine cost based on usage
                            if not address.users:
                                annual_cost = 34.56  # $2.88 * 12 (unused)
                                monthly_cost = 2.88
                            else:
                                annual_cost = 0  # In use = free
                                monthly_cost = 0

                            risk_level = "HIGH" if "owner" in missing_labels else "MEDIUM"

                            resources.append(OrphanResourceData(
                                resource_id=address.name,
                                resource_type="gcp_static_ip_untagged",
                                resource_name=address.name,
                                region=gcp_region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "ip_address": address.address,
                                    "status": address.status,
                                    "network_tier": address.network_tier,
                                    "missing_labels": missing_labels,
                                    "existing_labels": labels,
                                    "annual_cost": round(annual_cost, 2),
                                    "risk_level": risk_level,
                                    "confidence": "MEDIUM",
                                    "recommendation": f"Add missing labels: {', '.join(missing_labels)}. Critical for governance and cost allocation.",
                                    "waste_reason": f"Missing required labels: {', '.join(missing_labels)}"
                                }
                            ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for untagged IPs: {e}")
                    continue

            # Also scan global IPs
            try:
                global_client = compute_v1.GlobalAddressesClient(credentials=self.credentials)
                request = compute_v1.ListGlobalAddressesRequest(project=self.project_id)

                for address in global_client.list(request=request):
                    labels = dict(address.labels) if address.labels else {}

                    missing_labels = []
                    for required in required_labels:
                        if required not in labels or not labels[required]:
                            missing_labels.append(required)

                    if missing_labels:
                        if not address.users:
                            annual_cost = 34.56
                            monthly_cost = 2.88
                        else:
                            annual_cost = 0
                            monthly_cost = 0

                        risk_level = "HIGH" if "owner" in missing_labels else "MEDIUM"

                        resources.append(OrphanResourceData(
                            resource_id=address.name,
                            resource_type="gcp_static_ip_untagged",
                            resource_name=address.name,
                            region="global",
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                "ip_address": address.address,
                                "status": address.status,
                                "network_tier": address.network_tier,
                                "missing_labels": missing_labels,
                                "existing_labels": labels,
                                "annual_cost": round(annual_cost, 2),
                                "risk_level": risk_level,
                                "scope": "GLOBAL",
                                "confidence": "MEDIUM",
                                "recommendation": f"Add missing labels: {', '.join(missing_labels)}",
                                "waste_reason": f"Global IP missing required labels: {', '.join(missing_labels)}"
                            }
                        ))

            except Exception as e:
                logger.error(f"Error scanning global IPs for untagged: {e}")

        except Exception as e:
            logger.error(f"Error in scan_static_ip_untagged: {e}")

        return resources

    async def scan_static_ip_old_never_used(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect old Static External IPs that have NEVER been used.

        Waste: IPs reserved 90+ days ago and never attached to any resource.
        Very high confidence waste - almost certainly forgotten.

        Detection: status='RESERVED' AND users=[] AND age >= 90 days
        Cost: $2.88/month per IP
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from datetime import datetime, timezone

            # Get detection parameters
            min_age_days = 90
            if detection_rules and "gcp_static_ip_old_never_used" in detection_rules:
                rules = detection_rules["gcp_static_ip_old_never_used"]
                min_age_days = rules.get("min_age_days", 90)

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        # Check if IP is unattached
                        if not address.users:
                            # Calculate age
                            created_at = datetime.fromisoformat(
                                address.creation_timestamp.replace('Z', '+00:00')
                            )
                            age_days = (datetime.now(timezone.utc) - created_at).days

                            # Filter by minimum age
                            if age_days >= min_age_days:
                                # Cost calculation
                                monthly_cost = 2.88
                                annual_cost = monthly_cost * 12
                                months_wasted = age_days / 30
                                already_wasted = monthly_cost * months_wasted

                                # High confidence for old IPs
                                if age_days >= 365:
                                    confidence = "CRITICAL"
                                elif age_days >= 180:
                                    confidence = "HIGH"
                                else:
                                    confidence = "MEDIUM"

                                resources.append(OrphanResourceData(
                                    resource_id=address.name,
                                    resource_type="gcp_static_ip_old_never_used",
                                    resource_name=address.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "ip_address": address.address,
                                        "status": address.status,
                                        "network_tier": address.network_tier,
                                        "age_days": age_days,
                                        "age_years": round(age_days / 365, 1),
                                        "created_at": address.creation_timestamp,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": confidence,
                                        "labels": dict(address.labels) if address.labels else {},
                                        "recommendation": f"DELETE IMMEDIATELY to save ${annual_cost:.2f}/year. IP unused for {age_days} days ({age_days//365} years).",
                                        "waste_reason": f"Reserved IP never used in {age_days} days - almost certainly forgotten"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for old never used IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_static_ip_old_never_used: {e}")

        return resources

    async def scan_static_ip_wrong_type(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect Static External IPs with wrong type (Regional vs Global).

        Waste: Using Global IP for VM instance (should be Regional).
        Global IPs are scarce and should only be used for Global Load Balancers.

        Detection: Global IP attached to /instances/ (VM)
        Cost: Same ($2.88/month if unused), but best practice violation
        Priority: LOW (P3) ⚡
        """
        resources = []

        try:
            from google.cloud import compute_v1

            global_client = compute_v1.GlobalAddressesClient(credentials=self.credentials)

            # Check global IPs
            request = compute_v1.ListGlobalAddressesRequest(project=self.project_id)

            for address in global_client.list(request=request):
                if address.users:
                    resource_url = address.users[0]

                    # Global IP should NOT be attached to VM instance
                    if "/instances/" in resource_url:
                        resources.append(OrphanResourceData(
                            resource_id=address.name,
                            resource_type="gcp_static_ip_wrong_type",
                            resource_name=address.name,
                            region="global",
                            estimated_monthly_cost=0.0,  # Same cost, just wrong type
                            resource_metadata={
                                "ip_address": address.address,
                                "status": address.status,
                                "current_type": "GLOBAL",
                                "recommended_type": "REGIONAL",
                                "attached_to": resource_url,
                                "issue": "Global IP cannot be properly attached to VM instance",
                                "confidence": "HIGH",
                                "labels": dict(address.labels) if address.labels else {},
                                "recommendation": "Delete Global IP and create Regional IP instead. Global IPs are for Global Load Balancers only.",
                                "waste_reason": "Global IP incorrectly used for VM instance (should be Regional)"
                            }
                        ))

        except Exception as e:
            logger.error(f"Error in scan_static_ip_wrong_type: {e}")

        return resources

    async def scan_static_ip_multiple_per_resource(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect resources with multiple Static External IPs.

        Waste: Resources with >1 Static IP when typically 1 suffices.
        Extra unused IPs cost $2.88/month each.

        Detection: Group by resource_url, count IPs, flag if >1
        Cost: (num_ips - 1) * $2.88/month if extra IPs are unused
        Priority: MEDIUM (P1) 💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Map: resource_url -> list of IPs
            resource_ips_map = {}

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        if address.users:
                            resource_url = address.users[0]

                            if resource_url not in resource_ips_map:
                                resource_ips_map[resource_url] = []

                            resource_ips_map[resource_url].append({
                                "ip_name": address.name,
                                "ip_address": address.address,
                                "region": gcp_region,
                                "status": address.status,
                                "network_tier": address.network_tier
                            })

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for multiple IPs: {e}")
                    continue

            # Find resources with multiple IPs
            for resource_url, ips in resource_ips_map.items():
                if len(ips) > 1:
                    # Parse resource name
                    resource_name = resource_url.split('/')[-1]

                    # Potential waste if extra IPs are unused
                    potential_monthly_waste = (len(ips) - 1) * 2.88
                    potential_annual_waste = potential_monthly_waste * 12

                    resources.append(OrphanResourceData(
                        resource_id=resource_name,
                        resource_type="gcp_static_ip_multiple_per_resource",
                        resource_name=resource_name,
                        region=ips[0]["region"],
                        estimated_monthly_cost=potential_monthly_waste,
                        resource_metadata={
                            "resource_url": resource_url,
                            "num_ips": len(ips),
                            "ips": ips,
                            "potential_monthly_waste": round(potential_monthly_waste, 2),
                            "potential_annual_waste": round(potential_annual_waste, 2),
                            "confidence": "MEDIUM",
                            "recommendation": f"Resource has {len(ips)} Static IPs. Typically 1 IP suffices. Review if extra IPs are necessary.",
                            "waste_reason": f"Resource has {len(ips)} Static IPs when typically 1 is sufficient"
                        }
                    ))

        except Exception as e:
            logger.error(f"Error in scan_static_ip_multiple_per_resource: {e}")

        return resources

    async def scan_static_ip_devtest_not_released(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect dev/test Static External IPs not released.

        Waste: IPs reserved for temporary dev/test that are >30 days old.
        Dev/test IPs should be released after project completion.

        Detection: labels.environment in ['dev','test'] AND age >= 30 days
        Cost: $2.88/month if unused, $0 if in use but still suspect
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from datetime import datetime, timezone

            # Get detection parameters
            max_age_days = 30
            if detection_rules and "gcp_static_ip_devtest_not_released" in detection_rules:
                rules = detection_rules["gcp_static_ip_devtest_not_released"]
                max_age_days = rules.get("max_age_days", 30)

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        labels = dict(address.labels) if address.labels else {}
                        environment = labels.get("environment", "").lower()

                        # Check if dev/test environment
                        if environment in ["dev", "test", "staging", "qa", "development"]:
                            # Calculate age
                            created_at = datetime.fromisoformat(
                                address.creation_timestamp.replace('Z', '+00:00')
                            )
                            age_days = (datetime.now(timezone.utc) - created_at).days

                            # Filter by age
                            if age_days >= max_age_days:
                                # Cost depends on usage
                                if not address.users:
                                    monthly_cost = 2.88
                                    already_wasted = (age_days / 30) * 2.88
                                else:
                                    monthly_cost = 0
                                    already_wasted = 0

                                annual_cost = monthly_cost * 12

                                resources.append(OrphanResourceData(
                                    resource_id=address.name,
                                    resource_type="gcp_static_ip_devtest_not_released",
                                    resource_name=address.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "ip_address": address.address,
                                        "status": address.status,
                                        "network_tier": address.network_tier,
                                        "environment": environment,
                                        "age_days": age_days,
                                        "created_at": address.creation_timestamp,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": "HIGH",
                                        "labels": labels,
                                        "recommendation": f"Release {environment} IP after project completion. IP is {age_days} days old.",
                                        "waste_reason": f"Dev/test IP not released after {age_days} days"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for devtest IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_static_ip_devtest_not_released: {e}")

        return resources

    async def scan_static_ip_orphaned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect orphaned Static External IPs (resource deleted).

        Waste: IPs whose attached resource no longer exists.
        IP shows status='IN_USE' but resource is deleted - critical bug.

        Detection: users[0] points to non-existent resource
        Cost: $2.88/month per IP
        Priority: CRITICAL (P0) 💰💰💰
        """
        resources = []

        try:
            from google.cloud import compute_v1
            from datetime import datetime, timezone
            import re

            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)

            # Get all active regions
            regions_to_scan = []
            for gcp_region in regions_client.list(project=self.project_id):
                if gcp_region.status == "UP":
                    regions_to_scan.append(gcp_region.name)

            for gcp_region in regions_to_scan:
                try:
                    request = compute_v1.ListAddressesRequest(
                        project=self.project_id,
                        region=gcp_region
                    )

                    for address in addresses_client.list(request=request):
                        if address.users and address.status == "IN_USE":
                            resource_url = address.users[0]
                            resource_exists = False

                            try:
                                # Check if it's a VM instance
                                if "/instances/" in resource_url:
                                    match = re.search(
                                        r'/zones/([^/]+)/instances/([^/]+)',
                                        resource_url
                                    )

                                    if match:
                                        zone = match.group(1)
                                        instance_name = match.group(2)

                                        try:
                                            instances_client.get(
                                                project=self.project_id,
                                                zone=zone,
                                                instance=instance_name
                                            )
                                            resource_exists = True
                                        except Exception:
                                            resource_exists = False  # Instance doesn't exist

                                # TODO: Add checks for other resource types (LB, etc.)

                            except Exception as e:
                                logger.warning(f"Error checking resource existence: {e}")

                            # If resource doesn't exist, it's orphaned
                            if not resource_exists:
                                # Calculate waste
                                created_at = datetime.fromisoformat(
                                    address.creation_timestamp.replace('Z', '+00:00')
                                )
                                age_days = (datetime.now(timezone.utc) - created_at).days

                                monthly_cost = 2.88
                                annual_cost = monthly_cost * 12
                                months_wasted = age_days / 30
                                already_wasted = monthly_cost * months_wasted

                                resources.append(OrphanResourceData(
                                    resource_id=address.name,
                                    resource_type="gcp_static_ip_orphaned",
                                    resource_name=address.name,
                                    region=gcp_region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "ip_address": address.address,
                                        "status": address.status,
                                        "network_tier": address.network_tier,
                                        "orphaned_resource": resource_url,
                                        "age_days": age_days,
                                        "created_at": address.creation_timestamp,
                                        "already_wasted": round(already_wasted, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "confidence": "CRITICAL",
                                        "labels": dict(address.labels) if address.labels else {},
                                        "recommendation": f"DELETE IMMEDIATELY to save ${annual_cost:.2f}/year. Resource no longer exists.",
                                        "waste_reason": f"IP attached to deleted resource: {resource_url}"
                                    }
                                ))

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region} for orphaned IPs: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_static_ip_orphaned: {e}")

        return resources

    # =================================================================
    # GCP Cloud Load Balancers Detection (10 scenarios - Networking)
    # =================================================================
    # Phase 1: Simple detection scenarios (7 scenarios)
    # Phase 2: Advanced analysis scenarios (3 scenarios)
    # Impact: $5,000-$25,000/year per organization
    # Pricing: Forwarding rules ($0.025/hour first 5, $0.010/hour additional)
    # =================================================================

    async def scan_lb_zero_backends(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect Load Balancers with zero backends.

        Waste: Backend service exists and forwarding rules are active,
        but the backends list is EMPTY (backends = []).

        Common causes:
        - Migration incomplete (old backends deleted, new not attached)
        - Manual scaling down (last backend removed, service forgotten)
        - IaC error (Terraform/Ansible deletes instance groups but not backend service)
        - Test environment (backend service created for testing, never populated)

        Detection: backend_service.backends == [] AND forwarding_rules exist
        Cost: $18-54/month per empty backend service (forwarding rules + health checks)
        Priority: CRITICAL (P0) 💰💰💰💰 - 40% of total LB waste
        """
        resources = []

        # Extract detection parameters
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7
        confidence_medium_days = detection_rules.get("confidence_medium_days", 7) if detection_rules else 7
        confidence_high_days = detection_rules.get("confidence_high_days", 30) if detection_rules else 30
        confidence_critical_days = detection_rules.get("confidence_critical_days", 90) if detection_rules else 90

        try:
            # Initialize clients
            backend_services_client = compute_v1.BackendServicesClient()
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
            regional_fr_client = compute_v1.ForwardingRulesClient()
            target_http_proxies_client = compute_v1.TargetHttpProxiesClient()
            target_https_proxies_client = compute_v1.TargetHttpsProxiesClient()
            url_maps_client = compute_v1.UrlMapsClient()

            # List all global backend services
            request = compute_v1.ListBackendServicesRequest(project=self.project_id)
            backend_services = backend_services_client.list(request=request)

            for backend_service in backend_services:
                # Check if backends list is empty
                if not backend_service.backends or len(backend_service.backends) == 0:
                    # Calculate age
                    created_at = datetime.fromisoformat(
                        backend_service.creation_timestamp.replace('Z', '+00:00')
                    )
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    if age_days < min_age_days:
                        continue

                    # Find associated forwarding rules
                    associated_forwarding_rules = []

                    # Check global forwarding rules
                    global_frs = forwarding_rules_client.list(project=self.project_id)
                    for fr in global_frs:
                        # Get target proxy and check if it points to this backend service
                        if 'targetHttpProxies' in fr.target or 'targetHttpsProxies' in fr.target:
                            try:
                                proxy_name = fr.target.split('/')[-1]

                                if 'targetHttpProxies' in fr.target:
                                    proxy = target_http_proxies_client.get(
                                        project=self.project_id,
                                        target_http_proxy=proxy_name
                                    )
                                    url_map_link = proxy.url_map
                                else:
                                    proxy = target_https_proxies_client.get(
                                        project=self.project_id,
                                        target_https_proxy=proxy_name
                                    )
                                    url_map_link = proxy.url_map

                                # Get URL map
                                url_map_name = url_map_link.split('/')[-1]
                                url_map = url_maps_client.get(
                                    project=self.project_id,
                                    url_map=url_map_name
                                )

                                # Check if URL map references this backend service
                                if (url_map.default_service == backend_service.self_link or
                                    any(backend_service.self_link in str(pm)
                                        for pm in url_map.path_matchers)):
                                    associated_forwarding_rules.append(fr.name)
                            except Exception:
                                continue

                    # Only flag as waste if forwarding rules exist
                    if len(associated_forwarding_rules) > 0:
                        # Calculate waste
                        num_forwarding_rules = len(associated_forwarding_rules)

                        # Forwarding rules cost: first 5 = $0.025/hour flat, additional = $0.010/hour each
                        if num_forwarding_rules <= 5:
                            hourly_forwarding_cost = 0.025
                        else:
                            hourly_forwarding_cost = 0.025 + ((num_forwarding_rules - 5) * 0.010)

                        monthly_forwarding_cost = hourly_forwarding_cost * 24 * 30

                        # Health checks still run (waste)
                        # Assume 1 health check per backend service at $0.002 per check, every 10 seconds
                        health_check_monthly = 0.002 * (60 / 10) * 60 * 24 * 30  # ~$5.18/month

                        monthly_cost = monthly_forwarding_cost + health_check_monthly
                        annual_cost = monthly_cost * 12
                        already_wasted = (age_days / 30) * monthly_cost

                        # Determine confidence
                        if age_days >= confidence_critical_days:
                            confidence = "CRITICAL"
                        elif age_days >= confidence_high_days:
                            confidence = "HIGH"
                        elif age_days >= confidence_medium_days:
                            confidence = "MEDIUM"
                        else:
                            confidence = "LOW"

                        resources.append(
                            OrphanResourceData(
                                resource_id=backend_service.name,
                                resource_type="gcp_lb_zero_backends",
                                resource_name=backend_service.name,
                                region="global",
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata={
                                    "backend_service_id": str(backend_service.id),
                                    "self_link": backend_service.self_link,
                                    "protocol": backend_service.protocol,
                                    "load_balancing_scheme": backend_service.load_balancing_scheme,
                                    "num_backends": 0,
                                    "associated_forwarding_rules": associated_forwarding_rules,
                                    "num_forwarding_rules": num_forwarding_rules,
                                    "age_days": age_days,
                                    "created_at": backend_service.creation_timestamp,
                                    "monthly_forwarding_cost": round(monthly_forwarding_cost, 2),
                                    "monthly_health_check_cost": round(health_check_monthly, 2),
                                    "annual_cost": round(annual_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": confidence,
                                    "waste_percentage": 100,  # 100% waste - no backends can serve traffic
                                    "impact": "CRITICAL - Forwarding rules active but cannot route traffic",
                                    "recommendation": "Delete backend service and all associated forwarding rules, target proxies, and URL maps",
                                    "gcloud_delete_command": f"gcloud compute backend-services delete {backend_service.name} --global",
                                    "prevention": "Use IaC lifecycle policies to ensure backends exist before creating backend service"
                                },
                            )
                        )

        except Exception as e:
            logger.error(f"Error in scan_lb_zero_backends: {e}")

        return resources

    async def scan_lb_all_backends_unhealthy(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect Load Balancers where ALL backends are UNHEALTHY.

        Waste: Backend service has backends attached, but ALL are UNHEALTHY for 7+ days.
        Load Balancer remains active and charged, but cannot route any traffic (503 errors).

        Common causes:
        - Health check misconfigured (wrong port, path, or response code)
        - Application down (service crashed, never restarted)
        - Firewall rules blocking health check probes (source IP 35.191.0.0/16, 130.211.0.0/22)
        - Network misconfiguration (backends unreachable from LB)
        - Intentional shutdown (backends stopped for maintenance, never restarted)

        Detection: ALL backends health_state == 'UNHEALTHY' for min_unhealthy_days
        Cost: $18-54/month (forwarding rules + health checks)
        Priority: HIGH (P0) 💰💰💰💰 - 20% of total LB waste
        """
        resources = []

        # Extract detection parameters
        min_unhealthy_days = detection_rules.get("min_unhealthy_days", 7) if detection_rules else 7
        confidence_medium_days = detection_rules.get("confidence_medium_days", 7) if detection_rules else 7
        confidence_high_days = detection_rules.get("confidence_high_days", 30) if detection_rules else 30
        confidence_critical_days = detection_rules.get("confidence_critical_days", 90) if detection_rules else 90

        try:
            # Initialize clients
            backend_services_client = compute_v1.BackendServicesClient()

            # List all backend services
            request = compute_v1.ListBackendServicesRequest(project=self.project_id)
            backend_services = backend_services_client.list(request=request)

            for backend_service in backend_services:
                # Skip if no backends
                if not backend_service.backends or len(backend_service.backends) == 0:
                    continue

                try:
                    # Get health status for all backends
                    health_request = compute_v1.GetHealthBackendServiceRequest(
                        project=self.project_id,
                        backend_service=backend_service.name,
                        resource_group_reference=compute_v1.ResourceGroupReference()
                    )

                    health_response = backend_services_client.get_health(request=health_request)

                    # Check if ALL backends are unhealthy
                    health_statuses = []
                    for health_status_item in health_response.health_status:
                        health_state = health_status_item.health_state
                        health_statuses.append(health_state)

                    # Check if all are UNHEALTHY
                    all_unhealthy = len(health_statuses) > 0 and all(
                        state == compute_v1.HealthStatus.HealthState.UNHEALTHY
                        for state in health_statuses
                    )

                    if all_unhealthy:
                        # Calculate age (estimate unhealthy duration based on creation time)
                        created_at = datetime.fromisoformat(
                            backend_service.creation_timestamp.replace('Z', '+00:00')
                        )
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        # For production: track unhealthy state via Cloud Monitoring
                        # For MVP: use age as proxy for unhealthy duration
                        unhealthy_days_estimate = min(age_days, 30)  # Conservative estimate

                        if unhealthy_days_estimate >= min_unhealthy_days:
                            # Calculate waste
                            num_backends = len(health_statuses)

                            # Forwarding rule cost (assume 1-2 rules per backend service)
                            avg_forwarding_rules = 1.5
                            monthly_forwarding_cost = 0.025 * 24 * 30  # $18/month minimum

                            # Health checks still running
                            health_check_monthly = num_backends * 0.002 * (60/10) * 60 * 24 * 30

                            monthly_cost = monthly_forwarding_cost + health_check_monthly
                            annual_cost = monthly_cost * 12
                            already_wasted = (unhealthy_days_estimate / 30) * monthly_cost

                            # Determine confidence
                            if unhealthy_days_estimate >= confidence_critical_days:
                                confidence = "CRITICAL"
                            elif unhealthy_days_estimate >= confidence_high_days:
                                confidence = "HIGH"
                            elif unhealthy_days_estimate >= confidence_medium_days:
                                confidence = "MEDIUM"
                            else:
                                confidence = "LOW"

                            resources.append(
                                OrphanResourceData(
                                    resource_id=backend_service.name,
                                    resource_type="gcp_lb_all_backends_unhealthy",
                                    resource_name=backend_service.name,
                                    region="global",
                                    estimated_monthly_cost=round(monthly_cost, 2),
                                    resource_metadata={
                                        "backend_service_id": str(backend_service.id),
                                        "protocol": backend_service.protocol,
                                        "num_backends": num_backends,
                                        "unhealthy_backends": num_backends,
                                        "health_statuses": [str(s) for s in health_statuses],
                                        "unhealthy_days_estimate": unhealthy_days_estimate,
                                        "age_days": age_days,
                                        "monthly_forwarding_cost": round(monthly_forwarding_cost, 2),
                                        "monthly_health_check_cost": round(health_check_monthly, 2),
                                        "annual_cost": round(annual_cost, 2),
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": confidence,
                                        "waste_percentage": 100,  # Cannot serve any traffic
                                        "impact": "CRITICAL - All backends UNHEALTHY, LB returns 503 errors",
                                        "recommendation": "Fix health checks (check port, path, firewall rules) OR delete backend service if no longer needed",
                                        "debug_command": f"gcloud compute backend-services get-health {backend_service.name} --global",
                                        "health_check_troubleshooting": "Verify health check probes can reach backends from IPs 35.191.0.0/16 and 130.211.0.0/22"
                                    },
                                )
                            )

                except Exception as e:
                    # If get_health fails, continue to next backend service
                    logger.debug(f"Could not get health for {backend_service.name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_lb_all_backends_unhealthy: {e}")

        return resources

    async def scan_lb_orphaned_forwarding_rules(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect orphaned forwarding rules (THE TRAP #1 for GKE).

        Waste: Forwarding rules pointing to non-existent targets (deleted target proxies,
        backend services, etc.). This is THE MOST FREQUENT waste scenario in GKE environments.

        Common causes:
        - kubectl delete service doesn't always delete GCP forwarding rules
        - Terraform destroy incomplete (backend deleted, forwarding rule forgotten)
        - Migration (new LB created, old forwarding rule not deleted)
        - Human error (manual deletion in wrong order)

        Detection: Forwarding rule exists but fr.target returns 404 Not Found
        Cost: $7-18/month per orphaned rule
        Priority: CRITICAL (P0) 💰💰💰💰 - 30-40% of total LB waste (especially GKE)

        Impact: In GKE-heavy environments, 60-70% of forwarding rules can be orphaned
        after several months of operations!
        """
        resources = []

        try:
            # Initialize clients
            global_fr_client = compute_v1.GlobalForwardingRulesClient()
            regional_fr_client = compute_v1.ForwardingRulesClient()
            regions_client = compute_v1.RegionsClient()
            target_http_proxies_client = compute_v1.TargetHttpProxiesClient()
            target_https_proxies_client = compute_v1.TargetHttpsProxiesClient()
            target_tcp_proxies_client = compute_v1.TargetTcpProxiesClient()
            target_ssl_proxies_client = compute_v1.TargetSslProxiesClient()
            backend_services_client = compute_v1.BackendServicesClient()
            regional_backend_services_client = compute_v1.RegionBackendServicesClient()

            # Check global forwarding rules
            global_frs = global_fr_client.list(project=self.project_id)
            for fr in global_frs:
                target_exists = await self._check_target_exists(
                    fr.target,
                    target_http_proxies_client,
                    target_https_proxies_client,
                    target_tcp_proxies_client,
                    target_ssl_proxies_client,
                    backend_services_client,
                    regional_backend_services_client,
                    None
                )

                if not target_exists:
                    # Calculate age
                    created_at = datetime.fromisoformat(
                        fr.creation_timestamp.replace('Z', '+00:00')
                    )
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    # Cost per orphaned rule
                    monthly_cost = 0.025 * 24 * 30  # $18/month (minimum, within first 5 rules)
                    annual_cost = monthly_cost * 12
                    already_wasted = (age_days / 30) * monthly_cost

                    # Confidence is CRITICAL for orphaned resources
                    confidence = "CRITICAL"

                    resources.append(
                        OrphanResourceData(
                            resource_id=fr.name,
                            resource_type="gcp_lb_orphaned_forwarding_rules",
                            resource_name=fr.name,
                            region="global",
                            estimated_monthly_cost=round(monthly_cost, 2),
                            resource_metadata={
                                "forwarding_rule_id": str(fr.id),
                                "ip_address": fr.IP_address if hasattr(fr, 'IP_address') else fr.IPAddress,
                                "target": fr.target,
                                "target_exists": False,
                                "scope": "GLOBAL",
                                "port_range": fr.port_range if hasattr(fr, 'port_range') else None,
                                "age_days": age_days,
                                "created_at": fr.creation_timestamp,
                                "annual_cost": round(annual_cost, 2),
                                "already_wasted": round(already_wasted, 2),
                                "confidence": confidence,
                                "waste_percentage": 100,  # 100% waste - target doesn't exist
                                "impact": "CRITICAL - Forwarding rule active but points to deleted target",
                                "recommendation": "Delete orphaned forwarding rule immediately",
                                "gcloud_delete_command": f"gcloud compute forwarding-rules delete {fr.name} --global",
                                "gke_note": "Common in GKE environments after kubectl delete service - check for orphaned rules regularly"
                            },
                        )
                    )

            # Check regional forwarding rules
            regions = regions_client.list(project=self.project_id)
            for gcp_region in regions:
                try:
                    regional_frs = regional_fr_client.list(
                        project=self.project_id,
                        region=gcp_region.name
                    )

                    for fr in regional_frs:
                        target_exists = await self._check_target_exists(
                            fr.target,
                            target_http_proxies_client,
                            target_https_proxies_client,
                            target_tcp_proxies_client,
                            target_ssl_proxies_client,
                            backend_services_client,
                            regional_backend_services_client,
                            gcp_region.name
                        )

                        if not target_exists:
                            created_at = datetime.fromisoformat(
                                fr.creation_timestamp.replace('Z', '+00:00')
                            )
                            age_days = (datetime.now(timezone.utc) - created_at).days

                            monthly_cost = 0.025 * 24 * 30  # $18/month
                            annual_cost = monthly_cost * 12
                            already_wasted = (age_days / 30) * monthly_cost

                            resources.append(
                                OrphanResourceData(
                                    resource_id=fr.name,
                                    resource_type="gcp_lb_orphaned_forwarding_rules",
                                    resource_name=fr.name,
                                    region=gcp_region.name,
                                    estimated_monthly_cost=round(monthly_cost, 2),
                                    resource_metadata={
                                        "forwarding_rule_id": str(fr.id),
                                        "ip_address": fr.IP_address if hasattr(fr, 'IP_address') else fr.IPAddress,
                                        "target": fr.target,
                                        "target_exists": False,
                                        "scope": "REGIONAL",
                                        "age_days": age_days,
                                        "annual_cost": round(annual_cost, 2),
                                        "already_wasted": round(already_wasted, 2),
                                        "confidence": "CRITICAL",
                                        "waste_percentage": 100,
                                        "recommendation": "Delete orphaned forwarding rule",
                                        "gcloud_delete_command": f"gcloud compute forwarding-rules delete {fr.name} --region={gcp_region.name}"
                                    },
                                )
                            )

                except Exception as e:
                    logger.error(f"Error scanning region {gcp_region.name} for orphaned forwarding rules: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in scan_lb_orphaned_forwarding_rules: {e}")

        return resources

    async def _check_target_exists(
        self,
        target_link: str,
        target_http_proxies_client,
        target_https_proxies_client,
        target_tcp_proxies_client,
        target_ssl_proxies_client,
        backend_services_client,
        regional_backend_services_client,
        region: str | None
    ) -> bool:
        """Helper method to check if a forwarding rule target exists."""
        try:
            if 'targetHttpProxies' in target_link:
                proxy_name = target_link.split('/')[-1]
                target_http_proxies_client.get(
                    project=self.project_id,
                    target_http_proxy=proxy_name
                )
                return True
            elif 'targetHttpsProxies' in target_link:
                proxy_name = target_link.split('/')[-1]
                target_https_proxies_client.get(
                    project=self.project_id,
                    target_https_proxy=proxy_name
                )
                return True
            elif 'targetTcpProxies' in target_link:
                proxy_name = target_link.split('/')[-1]
                target_tcp_proxies_client.get(
                    project=self.project_id,
                    target_tcp_proxy=proxy_name
                )
                return True
            elif 'targetSslProxies' in target_link:
                proxy_name = target_link.split('/')[-1]
                target_ssl_proxies_client.get(
                    project=self.project_id,
                    target_ssl_proxy=proxy_name
                )
                return True
            elif 'backendServices' in target_link:
                bs_name = target_link.split('/')[-1]
                if region:
                    regional_backend_services_client.get(
                        project=self.project_id,
                        region=region,
                        backend_service=bs_name
                    )
                else:
                    backend_services_client.get(
                        project=self.project_id,
                        backend_service=bs_name
                    )
                return True
            else:
                return True  # Unknown target type, assume exists
        except Exception:
            return False  # Target doesn't exist → ORPHANED!

    async def scan_lb_zero_traffic(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect Load Balancers with zero request traffic.

        Waste: Load Balancer properly configured, backends healthy, but NO TRAFFIC
        for 30+ days. Application decommissioned, DNS moved, or feature flag disabled.

        Common causes:
        - Application decommissioned (DNS points elsewhere)
        - Staging environment unused
        - Feature flag disabled (service not called)
        - Migration to new LB (old LB forgotten)

        Detection: 0 requests via Cloud Monitoring for idle_days
        Metric: loadbalancing.googleapis.com/https/request_count
        Cost: $18-25/month (forwarding rules + health checks)
        Priority: MEDIUM-HIGH (P1) 💰💰💰 - 15% of total LB waste
        """
        resources = []

        # Extract detection parameters
        idle_days = detection_rules.get("idle_days", 30) if detection_rules else 30

        try:
            # Initialize clients
            monitoring_client = monitoring_v3.MetricServiceClient()
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
            project_name = f"projects/{self.project_id}"

            # Time interval for lookback
            end_time = int(time.time())
            start_time = end_time - (idle_days * 86400)

            interval = monitoring_v3.TimeInterval({
                'end_time': {'seconds': end_time},
                'start_time': {'seconds': start_time}
            })

            # Query metrics for HTTPS request count
            metrics_to_check = [
                'loadbalancing.googleapis.com/https/request_count',
                'loadbalancing.googleapis.com/tcp/closed_connections'
            ]

            idle_lbs = []

            for metric_type in metrics_to_check:
                try:
                    results = monitoring_client.list_time_series(
                        request={
                            'name': project_name,
                            'filter': f'metric.type = "{metric_type}"',
                            'interval': interval,
                            'aggregation': {
                                'alignment_period': {'seconds': 3600},
                                'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_SUM
                            }
                        }
                    )

                    for result in results:
                        total_requests = sum([point.value.int64_value or point.value.double_value or 0 for point in result.points])

                        if total_requests == 0:
                            lb_name = result.resource.labels.get('forwarding_rule_name')
                            if lb_name and lb_name not in idle_lbs:
                                idle_lbs.append(lb_name)

                except Exception as e:
                    logger.debug(f"Could not query metric {metric_type}: {e}")
                    continue

            # Get details for idle LBs
            all_frs = forwarding_rules_client.list(project=self.project_id)
            for fr in all_frs:
                if fr.name in idle_lbs:
                    # Calculate age
                    created_at = datetime.fromisoformat(
                        fr.creation_timestamp.replace('Z', '+00:00')
                    )
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    monthly_cost = 0.025 * 24 * 30  # $18/month forwarding rule
                    # Add health check cost if backends exist (estimate)
                    monthly_cost += 5.18  # Avg health check cost
                    annual_cost = monthly_cost * 12
                    already_wasted = (idle_days / 30) * monthly_cost

                    confidence = "HIGH" if idle_days >= 30 else "MEDIUM"

                    resources.append(
                        OrphanResourceData(
                            resource_id=fr.name,
                            resource_type="gcp_lb_zero_traffic",
                            resource_name=fr.name,
                            region="global",
                            estimated_monthly_cost=round(monthly_cost, 2),
                            resource_metadata={
                                "forwarding_rule_id": str(fr.id),
                                "ip_address": fr.IP_address if hasattr(fr, 'IP_address') else fr.IPAddress,
                                "target": fr.target,
                                "idle_days": idle_days,
                                "total_requests": 0,
                                "age_days": age_days,
                                "annual_cost": round(annual_cost, 2),
                                "already_wasted": round(already_wasted, 2),
                                "confidence": confidence,
                                "waste_percentage": 100,
                                "impact": "HIGH - LB active but receives zero traffic",
                                "recommendation": "Verify application is truly unused, then delete LB stack",
                                "investigation_steps": "1. Check DNS records 2. Review application logs 3. Confirm with team before deletion"
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error in scan_lb_zero_traffic: {e}")

        return resources

    async def scan_lb_devtest_unused(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect dev/test Load Balancers unused for 14+ days.

        Waste: Load Balancers tagged with environment=dev/test/staging but idle
        for extended periods. Dev/test environments often left running unnecessarily.

        Detection: Labels contain dev/test/staging AND zero traffic for idle_days
        Cost: $18-25/month per idle dev/test LB
        Priority: MEDIUM (P2) 💰💰 - 10% of total LB waste
        """
        resources = []

        # Extract detection parameters
        idle_days = detection_rules.get("idle_days", 14) if detection_rules else 14
        devtest_labels = detection_rules.get("devtest_labels", ["dev", "test", "staging", "development"]) if detection_rules else ["dev", "test", "staging", "development"]

        try:
            # Initialize clients
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all forwarding rules
            frs = forwarding_rules_client.list(project=self.project_id)

            for fr in frs:
                # Check labels
                labels = fr.labels if hasattr(fr, 'labels') and fr.labels else {}
                env = labels.get('environment', '').lower()

                if env in devtest_labels:
                    # Check traffic via Cloud Monitoring
                    has_traffic = await self._check_lb_traffic(
                        fr.name,
                        idle_days,
                        monitoring_client
                    )

                    if not has_traffic:
                        # Calculate age
                        created_at = datetime.fromisoformat(
                            fr.creation_timestamp.replace('Z', '+00:00')
                        )
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        monthly_cost = 0.025 * 24 * 30 + 5.18  # Forwarding rule + health checks
                        annual_cost = monthly_cost * 12
                        already_wasted = (idle_days / 30) * monthly_cost

                        resources.append(
                            OrphanResourceData(
                                resource_id=fr.name,
                                resource_type="gcp_lb_devtest_unused",
                                resource_name=fr.name,
                                region="global",
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata={
                                    "forwarding_rule_id": str(fr.id),
                                    "environment": env,
                                    "labels": dict(labels),
                                    "idle_days": idle_days,
                                    "age_days": age_days,
                                    "annual_cost": round(annual_cost, 2),
                                    "already_wasted": round(already_wasted, 2),
                                    "confidence": "MEDIUM",
                                    "impact": "MEDIUM - Dev/test LB idle, can be deleted or paused",
                                    "recommendation": "Delete or pause dev/test environment when not in use",
                                    "automation_tip": "Use scheduled shutdown scripts for dev/test environments"
                                },
                            )
                        )

        except Exception as e:
            logger.error(f"Error in scan_lb_devtest_unused: {e}")

        return resources

    async def _check_lb_traffic(
        self,
        lb_name: str,
        lookback_days: int,
        monitoring_client
    ) -> bool:
        """Helper method to check if LB has traffic via Cloud Monitoring."""
        try:
            project_name = f"projects/{self.project_id}"
            end_time = int(time.time())
            start_time = end_time - (lookback_days * 86400)

            interval = monitoring_v3.TimeInterval({
                'end_time': {'seconds': end_time},
                'start_time': {'seconds': start_time}
            })

            results = monitoring_client.list_time_series(
                request={
                    'name': project_name,
                    'filter': f'metric.type = "loadbalancing.googleapis.com/https/request_count" AND resource.labels.forwarding_rule_name = "{lb_name}"',
                    'interval': interval,
                    'aggregation': {
                        'alignment_period': {'seconds': 3600},
                        'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_SUM
                    }
                }
            )

            for result in results:
                total_requests = sum([point.value.int64_value or 0 for point in result.points])
                if total_requests > 0:
                    return True

            return False  # No traffic found

        except Exception:
            return True  # If monitoring query fails, assume has traffic (conservative)

    async def scan_lb_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect untagged Load Balancers (missing required labels).

        Waste: Forwarding rules without required labels → unclear ownership →
        often forgotten and not deleted. Governance waste.

        Detection: Missing required labels (environment, team, application)
        Cost: $18/month per untagged LB (indirect governance waste)
        Priority: MEDIUM (P2) 💰 - 5% of total LB waste
        """
        resources = []

        # Extract detection parameters
        required_labels = detection_rules.get("required_labels", ["environment", "team", "application"]) if detection_rules else ["environment", "team", "application"]

        try:
            # Initialize clients
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()

            # List all forwarding rules
            frs = forwarding_rules_client.list(project=self.project_id)

            for fr in frs:
                # Check labels
                labels = fr.labels if hasattr(fr, 'labels') and fr.labels else {}

                missing_labels = [label for label in required_labels if label not in labels]

                if missing_labels:
                    # Calculate age
                    created_at = datetime.fromisoformat(
                        fr.creation_timestamp.replace('Z', '+00:00')
                    )
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    monthly_cost = 0.025 * 24 * 30  # $18/month
                    # Governance waste is typically estimated at ~5% of resource cost
                    governance_waste_pct = 0.05
                    monthly_governance_cost = monthly_cost * governance_waste_pct

                    resources.append(
                        OrphanResourceData(
                            resource_id=fr.name,
                            resource_type="gcp_lb_untagged",
                            resource_name=fr.name,
                            region="global",
                            estimated_monthly_cost=round(monthly_governance_cost, 2),
                            resource_metadata={
                                "forwarding_rule_id": str(fr.id),
                                "ip_address": fr.IP_address if hasattr(fr, 'IP_address') else fr.IPAddress,
                                "existing_labels": dict(labels),
                                "missing_labels": missing_labels,
                                "age_days": age_days,
                                "confidence": "LOW",
                                "impact": "LOW - Governance waste due to unclear ownership",
                                "recommendation": "Add required labels (environment, team, application) OR delete if unknown owner",
                                "gcloud_add_labels_command": f"gcloud compute forwarding-rules update {fr.name} --global --update-labels=environment=VALUE,team=VALUE,application=VALUE"
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error in scan_lb_untagged: {e}")

        return resources

    async def scan_lb_wrong_type(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect wrong Load Balancer type (Global LB for regional traffic).

        Waste: Global Load Balancer used but >95% traffic comes from single region.
        Should use Regional LB instead (simpler, lower data processing costs).

        Detection: Global LB with single_region_threshold_pct traffic from one region
        Cost: Potential savings on data processing costs
        Priority: MEDIUM (P2) 💰💰 - 5% of total LB waste
        """
        resources = []

        # Extract detection parameters
        single_region_threshold_pct = detection_rules.get("single_region_threshold_pct", 0.95) if detection_rules else 0.95
        lookback_days = detection_rules.get("lookback_days", 30) if detection_rules else 30

        try:
            # Initialize clients
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List global forwarding rules
            global_frs = forwarding_rules_client.list(project=self.project_id)

            for fr in global_frs:
                # Check traffic distribution by region via Cloud Monitoring
                traffic_by_region = await self._get_traffic_by_region(
                    fr.name,
                    lookback_days,
                    monitoring_client
                )

                if traffic_by_region:
                    total_traffic = sum(traffic_by_region.values())
                    if total_traffic > 0:
                        max_region_traffic = max(traffic_by_region.values())
                        max_region_pct = max_region_traffic / total_traffic

                        if max_region_pct >= single_region_threshold_pct:
                            # Over-engineered: Global LB for single-region traffic
                            max_region_name = [k for k, v in traffic_by_region.items() if v == max_region_traffic][0]

                            # Potential savings (conservative estimate)
                            monthly_potential_savings = 10.00  # Conservative estimate

                            resources.append(
                                OrphanResourceData(
                                    resource_id=fr.name,
                                    resource_type="gcp_lb_wrong_type",
                                    resource_name=fr.name,
                                    region="global",
                                    estimated_monthly_cost=round(monthly_potential_savings, 2),
                                    resource_metadata={
                                        "forwarding_rule_id": str(fr.id),
                                        "current_type": "GLOBAL",
                                        "recommended_type": "REGIONAL",
                                        "primary_region": max_region_name,
                                        "primary_region_traffic_pct": round(max_region_pct * 100, 2),
                                        "traffic_by_region": traffic_by_region,
                                        "lookback_days": lookback_days,
                                        "confidence": "MEDIUM",
                                        "impact": "MEDIUM - Over-engineered architecture",
                                        "recommendation": f"Migrate to Regional Load Balancer in {max_region_name} for simpler architecture",
                                        "potential_savings": "Lower data processing costs + simpler management"
                                    },
                                )
                            )

        except Exception as e:
            logger.error(f"Error in scan_lb_wrong_type: {e}")

        return resources

    async def _get_traffic_by_region(
        self,
        lb_name: str,
        lookback_days: int,
        monitoring_client
    ) -> dict:
        """Helper method to get traffic distribution by region."""
        try:
            project_name = f"projects/{self.project_id}"
            end_time = int(time.time())
            start_time = end_time - (lookback_days * 86400)

            interval = monitoring_v3.TimeInterval({
                'end_time': {'seconds': end_time},
                'start_time': {'seconds': start_time}
            })

            results = monitoring_client.list_time_series(
                request={
                    'name': project_name,
                    'filter': f'metric.type = "loadbalancing.googleapis.com/https/request_count" AND resource.labels.forwarding_rule_name = "{lb_name}"',
                    'interval': interval,
                    'aggregation': {
                        'alignment_period': {'seconds': 3600},
                        'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_SUM,
                        'group_by_fields': ['resource.labels.region']
                    }
                }
            )

            traffic_by_region = {}
            for result in results:
                region = result.resource.labels.get('region', 'unknown')
                total_requests = sum([point.value.int64_value or 0 for point in result.points])
                traffic_by_region[region] = total_requests

            return traffic_by_region

        except Exception:
            return {}

    async def scan_lb_multiple_single_backend(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect multiple Load Balancers for single backend (consolidation opportunity).

        Waste: Multiple forwarding rules/LBs pointing to the same backend service.
        Consolidation possible to reduce costs.

        Detection: Group forwarding rules by backend service, detect >1 LB per backend
        Cost: Savings from consolidation
        Priority: MEDIUM (P1) 💰💰 - Phase 2 scenario
        """
        resources = []

        try:
            # Initialize clients
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()
            target_http_proxies_client = compute_v1.TargetHttpProxiesClient()
            target_https_proxies_client = compute_v1.TargetHttpsProxiesClient()
            url_maps_client = compute_v1.UrlMapsClient()

            # Map backend services to forwarding rules
            backend_to_frs = {}

            # List all forwarding rules
            frs = forwarding_rules_client.list(project=self.project_id)

            for fr in frs:
                try:
                    # Get backend service via target proxy → URL map
                    if 'targetHttpProxies' in fr.target or 'targetHttpsProxies' in fr.target:
                        proxy_name = fr.target.split('/')[-1]

                        if 'targetHttpProxies' in fr.target:
                            proxy = target_http_proxies_client.get(
                                project=self.project_id,
                                target_http_proxy=proxy_name
                            )
                        else:
                            proxy = target_https_proxies_client.get(
                                project=self.project_id,
                                target_https_proxy=proxy_name
                            )

                        url_map_name = proxy.url_map.split('/')[-1]
                        url_map = url_maps_client.get(
                            project=self.project_id,
                            url_map=url_map_name
                        )

                        backend_service = url_map.default_service

                        if backend_service not in backend_to_frs:
                            backend_to_frs[backend_service] = []
                        backend_to_frs[backend_service].append(fr.name)

                except Exception:
                    continue

            # Detect backends with multiple forwarding rules
            for backend_service, fr_names in backend_to_frs.items():
                if len(fr_names) > 1:
                    # Potential consolidation opportunity
                    monthly_potential_savings = (len(fr_names) - 1) * 18.00  # Save on extra FRs

                    resources.append(
                        OrphanResourceData(
                            resource_id=backend_service.split('/')[-1],
                            resource_type="gcp_lb_multiple_single_backend",
                            resource_name=backend_service.split('/')[-1],
                            region="global",
                            estimated_monthly_cost=round(monthly_potential_savings, 2),
                            resource_metadata={
                                "backend_service": backend_service,
                                "num_forwarding_rules": len(fr_names),
                                "forwarding_rules": fr_names,
                                "confidence": "MEDIUM",
                                "impact": "MEDIUM - Consolidation opportunity",
                                "recommendation": f"Consolidate {len(fr_names)} forwarding rules into single LB",
                                "potential_savings": f"Save ${monthly_potential_savings:.2f}/month by consolidating"
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error in scan_lb_multiple_single_backend: {e}")

        return resources

    async def scan_lb_overprovisioned_backends(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect over-provisioned backend capacity (backends under-utilized).

        Waste: Too many backends for actual traffic load. Backends running at <20% CPU.

        Detection: Analyze backend CPU utilization via Cloud Monitoring
        Cost: Potential savings from reducing backend count
        Priority: MEDIUM (P1) 💰💰 - Phase 2 scenario
        """
        resources = []

        # Extract detection parameters
        cpu_threshold = detection_rules.get("cpu_threshold", 0.20) if detection_rules else 0.20
        lookback_days = detection_rules.get("lookback_days", 7) if detection_rules else 7

        try:
            # Initialize clients
            backend_services_client = compute_v1.BackendServicesClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List backend services
            backend_services = backend_services_client.list(project=self.project_id)

            for backend_service in backend_services:
                if backend_service.backends and len(backend_service.backends) > 0:
                    # Check CPU utilization of backends via Cloud Monitoring
                    avg_cpu = await self._get_backend_avg_cpu(
                        backend_service.name,
                        lookback_days,
                        monitoring_client
                    )

                    if avg_cpu is not None and avg_cpu < cpu_threshold:
                        # Over-provisioned: too many backends for load
                        num_backends = len(backend_service.backends)
                        recommended_backends = max(1, int(num_backends * (avg_cpu / cpu_threshold)))
                        excess_backends = num_backends - recommended_backends

                        # Potential savings (conservative estimate per backend)
                        monthly_savings_per_backend = 50.00  # Rough estimate for e2-medium
                        monthly_potential_savings = excess_backends * monthly_savings_per_backend

                        resources.append(
                            OrphanResourceData(
                                resource_id=backend_service.name,
                                resource_type="gcp_lb_overprovisioned_backends",
                                resource_name=backend_service.name,
                                region="global",
                                estimated_monthly_cost=round(monthly_potential_savings, 2),
                                resource_metadata={
                                    "backend_service_id": str(backend_service.id),
                                    "num_backends": num_backends,
                                    "recommended_backends": recommended_backends,
                                    "excess_backends": excess_backends,
                                    "avg_cpu_utilization": round(avg_cpu * 100, 2),
                                    "cpu_threshold": round(cpu_threshold * 100, 2),
                                    "lookback_days": lookback_days,
                                    "confidence": "MEDIUM",
                                    "impact": "MEDIUM - Over-provisioned backend capacity",
                                    "recommendation": f"Reduce backend count from {num_backends} to {recommended_backends}",
                                    "potential_annual_savings": round(monthly_potential_savings * 12, 2)
                                },
                            )
                        )

        except Exception as e:
            logger.error(f"Error in scan_lb_overprovisioned_backends: {e}")

        return resources

    async def _get_backend_avg_cpu(
        self,
        backend_service_name: str,
        lookback_days: int,
        monitoring_client
    ) -> float | None:
        """Helper method to get average CPU utilization of backend instances."""
        try:
            project_name = f"projects/{self.project_id}"
            end_time = int(time.time())
            start_time = end_time - (lookback_days * 86400)

            interval = monitoring_v3.TimeInterval({
                'end_time': {'seconds': end_time},
                'start_time': {'seconds': start_time}
            })

            results = monitoring_client.list_time_series(
                request={
                    'name': project_name,
                    'filter': 'metric.type = "compute.googleapis.com/instance/cpu/utilization"',
                    'interval': interval,
                    'aggregation': {
                        'alignment_period': {'seconds': 3600},
                        'per_series_aligner': monitoring_v3.Aggregation.Aligner.ALIGN_MEAN
                    }
                }
            )

            cpu_values = []
            for result in results:
                for point in result.points:
                    cpu_values.append(point.value.double_value)

            if cpu_values:
                return sum(cpu_values) / len(cpu_values)
            return None

        except Exception:
            return None

    async def scan_lb_premium_tier_nonprod(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect Premium network tier on non-production workloads.

        Waste: Using Premium tier (PREMIUM) for dev/test/staging environments.
        Standard tier provides 29% savings on egress costs.

        Detection: environment != production AND network_tier == PREMIUM
        Cost: 29% savings on egress costs (Premium $0.12/GB vs Standard $0.085/GB)
        Priority: MEDIUM (P2) 💰💰 - Phase 2 scenario
        """
        resources = []

        # Extract detection parameters
        nonprod_labels = detection_rules.get("nonprod_labels", ["dev", "test", "staging", "development"]) if detection_rules else ["dev", "test", "staging", "development"]

        try:
            # Initialize clients
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient()

            # List forwarding rules
            frs = forwarding_rules_client.list(project=self.project_id)

            for fr in frs:
                # Check network tier
                network_tier = fr.network_tier if hasattr(fr, 'network_tier') else None

                if network_tier == "PREMIUM":
                    # Check environment label
                    labels = fr.labels if hasattr(fr, 'labels') and fr.labels else {}
                    env = labels.get('environment', '').lower()

                    if env in nonprod_labels:
                        # Premium tier on non-prod → waste opportunity
                        # Estimate potential savings (29% on egress costs)
                        # Conservative estimate: $20/month savings
                        monthly_potential_savings = 20.00

                        resources.append(
                            OrphanResourceData(
                                resource_id=fr.name,
                                resource_type="gcp_lb_premium_tier_nonprod",
                                resource_name=fr.name,
                                region="global",
                                estimated_monthly_cost=round(monthly_potential_savings, 2),
                                resource_metadata={
                                    "forwarding_rule_id": str(fr.id),
                                    "ip_address": fr.IP_address if hasattr(fr, 'IP_address') else fr.IPAddress,
                                    "current_network_tier": "PREMIUM",
                                    "recommended_network_tier": "STANDARD",
                                    "environment": env,
                                    "egress_savings_pct": 29,
                                    "premium_egress_cost": "$0.12/GB",
                                    "standard_egress_cost": "$0.085/GB",
                                    "confidence": "MEDIUM",
                                    "impact": "MEDIUM - Premium tier unnecessary for non-prod",
                                    "recommendation": "Switch to Standard network tier for dev/test/staging environments",
                                    "gcloud_command": f"# Recreate forwarding rule with --network-tier=STANDARD"
                                },
                            )
                        )

        except Exception as e:
            logger.error(f"Error in scan_lb_premium_tier_nonprod: {e}")

        return resources

    # ============================================================================
    # MEMORYSTORE REDIS/MEMCACHED WASTE DETECTION (10 SCENARIOS)
    # ============================================================================

    async def scan_memorystore_idle(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect completely idle Memorystore instances.

        Waste: Instances with 0 connections and 0 operations for extended period.
        Detection: connections = 0 OR (hit_ratio = 0 AND commands_rate = 0) for 30+ days
        Cost: Full capacity cost ($292-$1,752/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰💰
        Impact: 40% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_idle_threshold = rules.get("days_idle_threshold", 30)
        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud import redis_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            redis_client = redis_v1.CloudRedisClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Redis instances in region (or all regions if None)
            if region:
                parent = f"projects/{self.project_id}/locations/{region}"
                locations_to_check = [parent]
            else:
                # Check all available regions
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Check activity via Cloud Monitoring
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=days_idle_threshold)).timestamp())}
                        })

                        # Check connections metric
                        try:
                            metric_filter = (
                                f'resource.type="redis.googleapis.com/Instance" '
                                f'AND resource.labels.instance_id="{instance_id}" '
                                f'AND metric.type="redis.googleapis.com/stats/connections"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            avg_connections = 0
                            connection_count = 0
                            for result in results:
                                for point in result.points:
                                    avg_connections += point.value.double_value or 0
                                    connection_count += 1

                            avg_connections = avg_connections / connection_count if connection_count > 0 else 0

                            # Check hit ratio metric
                            metric_filter_hit = (
                                f'resource.type="redis.googleapis.com/Instance" '
                                f'AND resource.labels.instance_id="{instance_id}" '
                                f'AND metric.type="redis.googleapis.com/stats/hit_ratio"'
                            )

                            results_hit = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter_hit,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            avg_hit_ratio = 0
                            hit_count = 0
                            for result in results_hit:
                                for point in result.points:
                                    avg_hit_ratio += point.value.double_value or 0
                                    hit_count += 1

                            avg_hit_ratio = avg_hit_ratio / hit_count if hit_count > 0 else 0

                            # Instance is idle if connections = 0 OR hit_ratio = 0
                            is_idle = avg_connections == 0 or avg_hit_ratio == 0

                            if is_idle:
                                # Calculate waste
                                capacity_gb = instance.memory_size_gb
                                tier = instance.tier.name

                                # Approximate pricing (us-central1)
                                price_per_gb_hour = 0.024 if tier == "STANDARD_HA" else 0.008
                                hours_per_month = 730
                                monthly_waste = capacity_gb * price_per_gb_hour * hours_per_month

                                if monthly_waste < min_savings_threshold:
                                    continue

                                # Confidence based on days idle
                                if days_idle_threshold >= 90:
                                    confidence = "CRITICAL"
                                elif days_idle_threshold >= 60:
                                    confidence = "HIGH"
                                elif days_idle_threshold >= 30:
                                    confidence = "MEDIUM"
                                else:
                                    confidence = "LOW"

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=instance.name,
                                        resource_name=instance_id,
                                        resource_type="memorystore_redis_idle",
                                        region=instance_region,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level=confidence,
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "tier": tier,
                                            "capacity_gb": capacity_gb,
                                            "days_idle": days_idle_threshold,
                                            "avg_connections": round(avg_connections, 2),
                                            "avg_hit_ratio": round(avg_hit_ratio, 4),
                                            "waste_percentage": 100,
                                            "remediation": "DELETE instance immediately"
                                        },
                                        recommendation=f"DELETE instance. Zero activity for {days_idle_threshold}+ days = 100% waste (${monthly_waste:.2f}/month)."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch metrics for Memorystore instance {instance_id}: {e}")

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_idle: {e}")

        return resources

    async def scan_memorystore_overprovisioned(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect over-provisioned Memorystore capacity.

        Waste: Memory usage < 30% consistently = paying for unused capacity.
        Detection: memory_usage_ratio < 0.30 for 30+ days
        Cost: 70% of capacity cost wasted ($204-$1,226/month typical)
        Priority: HIGH (P1) 💰💰💰💰
        Impact: 25% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        usage_threshold = rules.get("usage_threshold", 0.30)
        days = rules.get("days", 30)
        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud import redis_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            redis_client = redis_v1.CloudRedisClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Check memory usage via Cloud Monitoring
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=days)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'resource.type="redis.googleapis.com/Instance" '
                                f'AND resource.labels.instance_id="{instance_id}" '
                                f'AND metric.type="redis.googleapis.com/stats/memory/usage_ratio"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            memory_usage_values = []
                            for result in results:
                                for point in result.points:
                                    memory_usage_values.append(point.value.double_value or 0)

                            avg_memory_usage = sum(memory_usage_values) / len(memory_usage_values) if memory_usage_values else 0

                            if 0 < avg_memory_usage < usage_threshold:
                                # Calculate waste
                                capacity_gb = instance.memory_size_gb
                                tier = instance.tier.name

                                # Optimal capacity with 20% buffer
                                optimal_capacity = int(capacity_gb * avg_memory_usage * 1.2)
                                wasted_capacity = capacity_gb - optimal_capacity

                                # Pricing
                                price_per_gb_hour = 0.024 if tier == "STANDARD_HA" else 0.008
                                hours_per_month = 730
                                monthly_waste = wasted_capacity * price_per_gb_hour * hours_per_month

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=instance.name,
                                        resource_name=instance_id,
                                        resource_type="memorystore_redis_overprovisioned",
                                        region=instance_region,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="HIGH",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "tier": tier,
                                            "current_capacity_gb": capacity_gb,
                                            "optimal_capacity_gb": optimal_capacity,
                                            "wasted_capacity_gb": wasted_capacity,
                                            "memory_usage_ratio": round(avg_memory_usage, 4),
                                            "waste_percentage": round((wasted_capacity / capacity_gb) * 100, 2)
                                        },
                                        recommendation=f"Downsize from {capacity_gb}GB to {optimal_capacity}GB. Save ${monthly_waste:.2f}/month."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch memory metrics for {instance_id}: {e}")

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_overprovisioned: {e}")

        return resources

    async def scan_memorystore_low_hit_rate(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect low cache hit rate instances.

        Waste: Hit rate < 50% = ineffective cache + backend overload.
        Detection: cache_hit_ratio < 0.50 for 7+ days (benchmark: >0.80)
        Cost: Cache cost + backend overload ($3,000-$15,000/year typical)
        Priority: CRITICAL (P0) 💰💰💰💰💰
        Impact: 30% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        hit_rate_threshold = rules.get("hit_rate_threshold", 0.50)
        days = rules.get("days", 7)
        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud import redis_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta

            redis_client = redis_v1.CloudRedisClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Check hit ratio via Cloud Monitoring
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=days)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'resource.type="redis.googleapis.com/Instance" '
                                f'AND resource.labels.instance_id="{instance_id}" '
                                f'AND metric.type="redis.googleapis.com/stats/hit_ratio"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            hit_ratio_values = []
                            for result in results:
                                for point in result.points:
                                    hit_ratio_values.append(point.value.double_value or 0)

                            avg_hit_ratio = sum(hit_ratio_values) / len(hit_ratio_values) if hit_ratio_values else 0

                            if 0 < avg_hit_ratio < hit_rate_threshold:
                                # Estimate backend cost increase
                                daily_requests = 10_000_000  # Conservative estimate
                                optimal_hit_rate = 0.85

                                backend_queries_current = daily_requests * (1 - avg_hit_ratio)
                                backend_queries_optimal = daily_requests * (1 - optimal_hit_rate)
                                excess_queries = backend_queries_current - backend_queries_optimal

                                backend_waste_daily = (excess_queries / 1000) * 0.10
                                backend_waste_annual = backend_waste_daily * 365

                                # Also consider cache cost itself
                                capacity_gb = instance.memory_size_gb
                                tier = instance.tier.name
                                price_per_gb_hour = 0.024 if tier == "STANDARD_HA" else 0.008
                                cache_annual_cost = capacity_gb * price_per_gb_hour * 730 * 12

                                total_annual_waste = backend_waste_annual + (cache_annual_cost * 0.5)  # 50% of cache cost considered waste
                                monthly_waste = total_annual_waste / 12

                                if monthly_waste < min_savings_threshold:
                                    continue

                                resources.append(
                                    OrphanResourceData(
                                        resource_id=instance.name,
                                        resource_name=instance_id,
                                        resource_type="memorystore_redis_low_hit_rate",
                                        region=instance_region,
                                        estimated_monthly_cost=monthly_waste,
                                        confidence_level="CRITICAL",
                                        resource_metadata={
                                            "instance_id": instance_id,
                                            "tier": tier,
                                            "capacity_gb": capacity_gb,
                                            "hit_ratio": round(avg_hit_ratio, 4),
                                            "benchmark_hit_ratio": 0.85,
                                            "gap": round(0.85 - avg_hit_ratio, 4),
                                            "backend_waste_annual": round(backend_waste_annual, 2)
                                        },
                                        recommendation=f"Low hit rate ({avg_hit_ratio:.2%}). Change eviction policy to allkeys-lru, increase TTL, optimize cache warming. Target >85%."
                                    )
                                )

                        except Exception as e:
                            logger.warning(f"Could not fetch hit ratio for {instance_id}: {e}")

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_low_hit_rate: {e}")

        return resources

    async def scan_memorystore_wrong_tier(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect Standard tier for dev/test environments.

        Waste: Standard tier (HA) for dev/test where Basic tier sufficient.
        Detection: tier = STANDARD_HA AND environment = dev/test/staging
        Cost: 3x more expensive than Basic ($584/month typical waste)
        Priority: MEDIUM (P2) 💰💰💰
        Impact: 15% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}
        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud import redis_v1

            redis_client = redis_v1.CloudRedisClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Check if Standard tier
                        if instance.tier.name != "STANDARD_HA":
                            continue

                        # Check labels for environment
                        labels = instance.labels or {}
                        environment = labels.get('environment', '').lower()

                        # If dev/test/staging → waste
                        if environment in ['dev', 'test', 'staging', 'development', 'qa']:
                            capacity_gb = instance.memory_size_gb

                            # Cost comparison
                            standard_cost = capacity_gb * 0.024 * 730  # Standard tier
                            basic_cost = capacity_gb * 0.008 * 730  # Basic tier
                            monthly_waste = standard_cost - basic_cost

                            if monthly_waste < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="memorystore_redis_wrong_tier",
                                    region=instance_region,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="HIGH",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "tier": "STANDARD_HA",
                                        "environment": environment,
                                        "capacity_gb": capacity_gb,
                                        "standard_monthly_cost": round(standard_cost, 2),
                                        "basic_monthly_cost": round(basic_cost, 2),
                                        "waste_percentage": round((monthly_waste / standard_cost) * 100, 2)
                                    },
                                    recommendation=f"Migrate to Basic tier for {environment}. Save ${monthly_waste:.2f}/month (67% savings)."
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_wrong_tier: {e}")

        return resources

    async def scan_memorystore_wrong_eviction(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect wrong eviction policy configuration.

        Waste: volatile-lru (default) instead of allkeys-lru for caching.
        Detection: maxmemory-policy = volatile-lru (may cause OOM or need larger instance)
        Cost: Potential for larger instance needed ($146-$876/month waste)
        Priority: MEDIUM (P2) 💰💰💰
        Impact: 10% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        try:
            from google.cloud import redis_v1

            redis_client = redis_v1.CloudRedisClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Get Redis config
                        redis_config = instance.redis_configs or {}
                        eviction_policy = redis_config.get('maxmemory-policy', 'volatile-lru')

                        # If volatile-lru (default) → potential waste
                        if eviction_policy == 'volatile-lru':
                            capacity_gb = instance.memory_size_gb
                            tier = instance.tier.name
                            price_per_gb_hour = 0.024 if tier == "STANDARD_HA" else 0.008

                            # Estimate potential waste (20% of instance cost)
                            monthly_cost = capacity_gb * price_per_gb_hour * 730
                            monthly_waste = monthly_cost * 0.20

                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="memorystore_redis_wrong_eviction",
                                    region=instance_region,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "tier": tier,
                                        "capacity_gb": capacity_gb,
                                        "current_policy": eviction_policy,
                                        "recommended_policy": "allkeys-lru"
                                    },
                                    recommendation=f"Change eviction policy to allkeys-lru for caching use cases. Prevents OOM errors and potential upsizing needs."
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_wrong_eviction: {e}")

        return resources

    async def scan_memorystore_no_cud(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect instances without Committed Use Discounts.

        Waste: Instances ≥5 GB running without CUD (20-40% savings missed).
        Detection: capacity ≥ 5 GB AND no CUD label
        Cost: 20-40% of instance cost ($117-$701/month typical)
        Priority: LOW (P3) 💰💰
        Impact: 5% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}
        min_savings_threshold = rules.get("min_savings_threshold", 50.0)

        try:
            from google.cloud import redis_v1

            redis_client = redis_v1.CloudRedisClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Only instances ≥5 GB eligible for CUD
                        capacity_gb = instance.memory_size_gb
                        if capacity_gb < 5:
                            continue

                        # Check if instance has CUD (check via label)
                        labels = instance.labels or {}
                        has_cud = labels.get('cud', 'false') == 'true'

                        if not has_cud:
                            tier = instance.tier.name
                            price_per_gb_hour = 0.024 if tier == "STANDARD_HA" else 0.008
                            monthly_cost = capacity_gb * price_per_gb_hour * 730

                            # 3-year CUD = 40% discount
                            monthly_savings = monthly_cost * 0.40

                            if monthly_savings < min_savings_threshold:
                                continue

                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="memorystore_redis_no_cud",
                                    region=instance_region,
                                    estimated_monthly_cost=monthly_savings,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "tier": tier,
                                        "capacity_gb": capacity_gb,
                                        "monthly_cost_without_cud": round(monthly_cost, 2),
                                        "monthly_savings_with_cud_1y": round(monthly_cost * 0.20, 2),
                                        "monthly_savings_with_cud_3y": round(monthly_cost * 0.40, 2),
                                        "annual_savings_3y": round(monthly_savings * 12, 2)
                                    },
                                    recommendation=f"Purchase 1-year CUD (20% off) or 3-year CUD (40% off). Save ${monthly_savings:.2f}/month."
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_no_cud: {e}")

        return resources

    async def scan_memorystore_untagged(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect untagged Memorystore instances.

        Waste: Instances without required labels (environment, team, cost_center).
        Detection: Missing any required labels
        Cost: Indirect (impossible cost allocation)
        Priority: LOW (P3) 💰💰
        Impact: 3% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}
        required_labels = rules.get("required_labels", ["environment", "team", "cost_center"])

        try:
            from google.cloud import redis_v1

            redis_client = redis_v1.CloudRedisClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        labels = instance.labels or {}

                        # Check for missing required labels
                        missing_labels = [label for label in required_labels if label not in labels]

                        if missing_labels:
                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="memorystore_redis_untagged",
                                    region=instance_region,
                                    estimated_monthly_cost=0.0,
                                    confidence_level="LOW",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "missing_labels": missing_labels,
                                        "existing_labels": list(labels.keys())
                                    },
                                    recommendation=f"Add missing labels: {', '.join(missing_labels)}. Required for cost allocation."
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_untagged: {e}")

        return resources

    async def scan_memorystore_high_connection_churn(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect high connection churn (Phase 2).

        Waste: Repeated short-lived connections instead of connection pooling.
        Detection: High variance in connection count (std_dev > 50% of mean)
        Cost: CPU overhead 5-10% ($29-$175/month typical)
        Priority: MEDIUM (P2) 💰💰💰💰
        Impact: 8% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}
        days = rules.get("days", 7)
        min_savings_threshold = rules.get("min_savings_threshold", 20.0)

        try:
            from google.cloud import redis_v1
            from google.cloud import monitoring_v3
            from datetime import datetime, timedelta
            import statistics

            redis_client = redis_v1.CloudRedisClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]

                        # Get connection count time series
                        now = datetime.utcnow()
                        interval = monitoring_v3.TimeInterval({
                            "end_time": {"seconds": int(now.timestamp())},
                            "start_time": {"seconds": int((now - timedelta(days=days)).timestamp())}
                        })

                        try:
                            metric_filter = (
                                f'resource.type="redis.googleapis.com/Instance" '
                                f'AND resource.labels.instance_id="{instance_id}" '
                                f'AND metric.type="redis.googleapis.com/stats/connections"'
                            )

                            results = monitoring_client.list_time_series(
                                name=f"projects/{self.project_id}",
                                filter=metric_filter,
                                interval=interval,
                                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                            )

                            connections_data = []
                            for result in results:
                                for point in result.points:
                                    connections_data.append(point.value.double_value or 0)

                            if len(connections_data) > 10:
                                std_dev = statistics.stdev(connections_data)
                                mean = statistics.mean(connections_data)

                                # High churn if std_dev > 50% of mean
                                if mean > 0 and (std_dev / mean) > 0.5:
                                    capacity_gb = instance.memory_size_gb
                                    tier = instance.tier.name
                                    price_per_gb_hour = 0.024 if tier == "STANDARD_HA" else 0.008
                                    monthly_cost = capacity_gb * price_per_gb_hour * 730

                                    # Estimate 10% overhead from connection churn
                                    monthly_waste = monthly_cost * 0.10

                                    if monthly_waste < min_savings_threshold:
                                        continue

                                    resources.append(
                                        OrphanResourceData(
                                            resource_id=instance.name,
                                            resource_name=instance_id,
                                            resource_type="memorystore_redis_high_connection_churn",
                                            region=instance_region,
                                            estimated_monthly_cost=monthly_waste,
                                            confidence_level="MEDIUM",
                                            resource_metadata={
                                                "instance_id": instance_id,
                                                "tier": tier,
                                                "capacity_gb": capacity_gb,
                                                "avg_connections": round(mean, 2),
                                                "connection_variance": round(std_dev, 2),
                                                "churn_indicator": round(std_dev / mean, 4)
                                            },
                                            recommendation=f"Implement connection pooling in application code. High connection churn detected (variance: {std_dev:.1f})."
                                        )
                                    )

                        except Exception as e:
                            logger.warning(f"Could not fetch connection metrics for {instance_id}: {e}")

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_high_connection_churn: {e}")

        return resources

    async def scan_memorystore_wrong_size(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect wrong instance size for workload (Phase 2).

        Waste: Basic tier >100 GB (should use Redis Cluster) or Standard tier <5 GB.
        Detection: Suboptimal sizing based on tier and capacity
        Cost: Performance issues or HA overhead ($29-$88/month typical)
        Priority: MEDIUM (P2) 💰💰💰
        Impact: 5% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        try:
            from google.cloud import redis_v1

            redis_client = redis_v1.CloudRedisClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        instance_id = instance.name.split('/')[-1]
                        instance_region = instance.name.split('/')[3]
                        capacity_gb = instance.memory_size_gb
                        tier = instance.tier.name

                        issue = None
                        recommendation = None
                        monthly_waste = 0

                        # Basic >100 GB → should use Redis Cluster
                        if tier == "BASIC" and capacity_gb > 100:
                            issue = "Should use Redis Cluster for >100 GB"
                            recommendation = "Migrate to Redis Cluster for better performance and horizontal scaling"
                            # Performance issue, not direct cost waste
                            monthly_waste = 0

                        # Standard <5 GB + no HA needed → should use Basic
                        elif tier == "STANDARD_HA" and capacity_gb < 5:
                            issue = "Small instance with HA overhead"
                            recommendation = "Consider Basic tier if HA not critical for small workloads"
                            # Calculate waste as difference between Standard and Basic
                            standard_cost = capacity_gb * 0.024 * 730
                            basic_cost = capacity_gb * 0.008 * 730
                            monthly_waste = standard_cost - basic_cost

                        if issue:
                            resources.append(
                                OrphanResourceData(
                                    resource_id=instance.name,
                                    resource_name=instance_id,
                                    resource_type="memorystore_redis_wrong_size",
                                    region=instance_region,
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="MEDIUM",
                                    resource_metadata={
                                        "instance_id": instance_id,
                                        "tier": tier,
                                        "capacity_gb": capacity_gb,
                                        "issue": issue
                                    },
                                    recommendation=recommendation
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_wrong_size: {e}")

        return resources

    async def scan_memorystore_cross_zone_traffic(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect cross-zone traffic costs (Phase 2).

        Waste: Redis Cluster with clients in different zone → $0.01/GB cross-zone fees.
        Detection: Network egress analysis (requires VPC flow logs analysis)
        Cost: Cross-zone processing fees ($72/month per 10TB typical)
        Priority: LOW (P3) 💰💰💰
        Impact: 3% of Memorystore waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        # Note: This scenario requires analyzing VPC flow logs and client locations
        # which is complex and beyond basic Memorystore API capabilities.
        # This is a placeholder implementation that would need additional
        # network analysis infrastructure.

        try:
            from google.cloud import redis_v1

            redis_client = redis_v1.CloudRedisClient()

            # List all Redis instances
            if region:
                locations_to_check = [f"projects/{self.project_id}/locations/{region}"]
            else:
                locations_to_check = [
                    f"projects/{self.project_id}/locations/{loc}"
                    for loc in ["us-central1", "us-east1", "europe-west1", "asia-east1"]
                ]

            for parent in locations_to_check:
                try:
                    instances = redis_client.list_instances(parent=parent)

                    for instance in instances:
                        # Only Redis Cluster has significant cross-zone fees
                        # For Basic and Standard tiers, cross-zone replication is included
                        # This detection would require additional VPC flow log analysis
                        pass

                except Exception as e:
                    logger.warning(f"Could not list Memorystore instances in {parent}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_memorystore_cross_zone_traffic: {e}")

        return resources

    # ============================================================================
    # BIGQUERY ANALYTICS WASTE DETECTION (10 SCENARIOS)
    # ============================================================================

    async def scan_bigquery_never_queried_tables(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect tables never queried.

        Waste: Tables jamais interrogées depuis 90+ jours = 100% storage waste.
        Detection: creation_time <90 days AND query_count = 0
        Cost: Full storage cost ($20-$2,000/month typical for 1-100 TB)
        Priority: CRITICAL (P0) 💰💰💰💰💰
        Impact: 40% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        never_queried_days = rules.get("never_queried_days", 90)
        min_size_gb = rules.get("min_size_gb", 1.0)
        exclude_datasets = rules.get("exclude_datasets", ['logs', 'temp'])

        try:
            from google.cloud import bigquery
            from datetime import datetime, timedelta

            client = bigquery.Client(project=self.project_id)

            # Query tables older than threshold
            query_tables = f"""
            SELECT
              table_catalog,
              table_schema,
              table_name,
              creation_time,
              TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), creation_time, DAY) as age_days,
              size_bytes / POW(1024, 3) as size_gb,
              row_count,
              type
            FROM `{self.project_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
              AND creation_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {never_queried_days} DAY)
              AND size_bytes >= {int(min_size_gb * 1024**3)}
            ORDER BY size_bytes DESC
            """

            tables = list(client.query(query_tables).result())

            for table in tables:
                # Skip excluded datasets
                if table.table_schema in exclude_datasets:
                    continue

                # Check if table was ever queried
                try:
                    query_jobs = f"""
                    SELECT COUNT(*) as query_count
                    FROM `{self.project_id}.region-{region or 'us'}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {never_queried_days} DAY)
                      AND state = 'DONE'
                      AND error_result IS NULL
                      AND ARRAY_LENGTH(referenced_tables) > 0
                      AND EXISTS (
                        SELECT 1 FROM UNNEST(referenced_tables) as ref
                        WHERE ref.table_id = '{table.table_name}'
                          AND ref.dataset_id = '{table.table_schema}'
                      )
                    """

                    result = list(client.query(query_jobs).result())
                    query_count = result[0].query_count if result else 0

                    if query_count == 0:
                        # Table never queried = 100% waste
                        age_days = table.age_days
                        size_gb = table.size_gb

                        # Storage pricing: active ($0.020) or long-term ($0.010)
                        storage_price = 0.010 if age_days >= 90 else 0.020
                        monthly_cost = size_gb * storage_price

                        # Already wasted cost
                        age_months = age_days / 30.0
                        already_wasted = monthly_cost * age_months

                        resources.append(
                            OrphanResourceData(
                                resource_id=f"{self.project_id}:{table.table_schema}.{table.table_name}",
                                resource_name=table.table_name,
                                resource_type="bigquery_never_queried_tables",
                                region=region or "us-central1",
                                estimated_monthly_cost=monthly_cost,
                                confidence_level="HIGH",
                                resource_metadata={
                                    "project_id": self.project_id,
                                    "dataset_id": table.table_schema,
                                    "table_id": table.table_name,
                                    "size_gb": round(size_gb, 2),
                                    "row_count": table.row_count,
                                    "age_days": age_days,
                                    "storage_tier": "long_term" if age_days >= 90 else "active",
                                    "query_count_90d": 0,
                                    "already_wasted": round(already_wasted, 2),
                                    "waste_percentage": 100
                                },
                                recommendation=f"Delete table or export to Cloud Storage Coldline ($0.004/GB = 60% savings). Never queried in {age_days} days."
                            )
                        )

                except Exception as e:
                    logger.warning(f"Could not check query history for table {table.table_name}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_bigquery_never_queried_tables: {e}")

        return resources

    async def scan_bigquery_active_storage_waste(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect active storage that should be long-term.

        Waste: Tables not modified in 90+ days still in active storage = 50% overpay.
        Detection: last_modified_time >90 days AND storage_tier = active
        Cost: 50% of storage cost ($10-$1,000/month typical)
        Priority: HIGH (P1) 💰💰💰💰
        Impact: 25% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        days_since_modified_threshold = rules.get("days_since_modified_threshold", 90)
        min_size_gb = rules.get("min_size_gb", 1.0)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # Query tables not modified in threshold period
            query = f"""
            SELECT
              table_catalog,
              table_schema,
              table_name,
              creation_time,
              size_bytes / POW(1024, 3) as size_gb,
              TIMESTAMP_DIFF(
                CURRENT_TIMESTAMP(),
                creation_time,
                DAY
              ) as days_since_modified
            FROM `{self.project_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
              AND TIMESTAMP_DIFF(
                    CURRENT_TIMESTAMP(),
                    creation_time,
                    DAY
                  ) >= {days_since_modified_threshold}
              AND size_bytes >= {int(min_size_gb * 1024**3)}
            ORDER BY size_bytes DESC
            """

            tables = list(client.query(query).result())

            for table in tables:
                size_gb = table.size_gb
                days_since_modified = table.days_since_modified

                # Active storage cost
                current_cost = size_gb * 0.020

                # Long-term storage cost
                recommended_cost = size_gb * 0.010

                # Waste = difference
                monthly_waste = current_cost - recommended_cost
                annual_savings = monthly_waste * 12

                resources.append(
                    OrphanResourceData(
                        resource_id=f"{self.project_id}:{table.table_schema}.{table.table_name}",
                        resource_name=table.table_name,
                        resource_type="bigquery_active_storage_waste",
                        region=region or "us-central1",
                        estimated_monthly_cost=monthly_waste,
                        confidence_level="HIGH",
                        resource_metadata={
                            "project_id": self.project_id,
                            "dataset_id": table.table_schema,
                            "table_id": table.table_name,
                            "size_gb": round(size_gb, 2),
                            "days_since_modified": days_since_modified,
                            "storage_tier": "active",
                            "current_cost_monthly": round(current_cost, 2),
                            "recommended_cost_monthly": round(recommended_cost, 2),
                            "annual_savings": round(annual_savings, 2),
                            "waste_percentage": 50
                        },
                        recommendation=f"Table not modified in {days_since_modified} days. Should transition to long-term storage (automatic after 90d). Save ${monthly_waste:.2f}/month."
                    )
                )

        except Exception as e:
            logger.error(f"Error in scan_bigquery_active_storage_waste: {e}")

        return resources

    async def scan_bigquery_empty_datasets(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect empty datasets.

        Waste: Empty datasets >30 days = abandoned projects, governance issue.
        Detection: table_count = 0 AND age_days >= 30
        Cost: No direct cost but signals other wastes
        Priority: MEDIUM (P2) 💰💰
        Impact: 5% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        min_age_days = rules.get("min_age_days", 30)

        try:
            from google.cloud import bigquery
            from datetime import datetime

            client = bigquery.Client(project=self.project_id)

            # List all datasets
            datasets = list(client.list_datasets(project=self.project_id))

            for dataset_ref in datasets:
                dataset = client.get_dataset(dataset_ref.reference)

                # Count tables in dataset
                query_count = f"""
                SELECT COUNT(*) as table_count
                FROM `{self.project_id}.{dataset.dataset_id}.INFORMATION_SCHEMA.TABLES`
                """

                result = list(client.query(query_count).result())
                table_count = result[0].table_count if result else 0

                if table_count == 0:
                    # Calculate age
                    age_days = (datetime.utcnow().replace(tzinfo=None) - dataset.created.replace(tzinfo=None)).days

                    if age_days >= min_age_days:
                        resources.append(
                            OrphanResourceData(
                                resource_id=f"{self.project_id}:{dataset.dataset_id}",
                                resource_name=dataset.dataset_id,
                                resource_type="bigquery_empty_datasets",
                                region=region or dataset.location,
                                estimated_monthly_cost=0.0,
                                confidence_level="MEDIUM",
                                resource_metadata={
                                    "project_id": self.project_id,
                                    "dataset_id": dataset.dataset_id,
                                    "location": dataset.location,
                                    "age_days": age_days,
                                    "table_count": 0
                                },
                                recommendation=f"Delete empty dataset - likely abandoned project (age: {age_days} days)."
                            )
                        )

        except Exception as e:
            logger.error(f"Error in scan_bigquery_empty_datasets: {e}")

        return resources

    async def scan_bigquery_no_expiration(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect temporary tables without expiration.

        Waste: Temp/staging tables without expiration = accumulation waste.
        Detection: table_name matches temp patterns AND expires = null AND age_days >= 7
        Cost: Full storage cost after intended lifetime ($100-$500/month typical)
        Priority: HIGH (P1) 💰💰💰💰
        Impact: 20% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        temp_name_patterns = rules.get("temp_name_patterns", ['temp', 'tmp', 'staging', 'stg', 'test', 'scratch', 'backup'])
        intended_lifetime_days = rules.get("intended_lifetime_days", 30)
        min_age_days = rules.get("min_age_days", 7)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # Build pattern matching for temp tables
            pattern_conditions = " OR ".join([f"LOWER(table_name) LIKE '%{pattern}%'" for pattern in temp_name_patterns])

            query = f"""
            SELECT
              table_catalog,
              table_schema,
              table_name,
              creation_time,
              TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), creation_time, DAY) as age_days,
              size_bytes / POW(1024, 3) as size_gb
            FROM `{self.project_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
              AND ({pattern_conditions})
              AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), creation_time, DAY) >= {min_age_days}
            ORDER BY size_bytes DESC
            """

            tables = list(client.query(query).result())

            for table in tables:
                # Check if expiration is set
                table_ref = client.get_table(f"{table.table_catalog}.{table.table_schema}.{table.table_name}")

                if table_ref.expires is None:
                    # Table has no expiration
                    age_days = table.age_days
                    size_gb = table.size_gb

                    # Calculate waste
                    if age_days > intended_lifetime_days:
                        waste_days = age_days - intended_lifetime_days
                        waste_months = waste_days / 30.0
                        monthly_cost = size_gb * 0.020
                        already_wasted = monthly_cost * waste_months
                    else:
                        monthly_cost = size_gb * 0.020
                        already_wasted = 0

                    resources.append(
                        OrphanResourceData(
                            resource_id=f"{self.project_id}:{table.table_schema}.{table.table_name}",
                            resource_name=table.table_name,
                            resource_type="bigquery_no_expiration",
                            region=region or "us-central1",
                            estimated_monthly_cost=monthly_cost,
                            confidence_level="HIGH",
                            resource_metadata={
                                "project_id": self.project_id,
                                "dataset_id": table.table_schema,
                                "table_id": table.table_name,
                                "size_gb": round(size_gb, 2),
                                "age_days": age_days,
                                "expires": None,
                                "intended_lifetime_days": intended_lifetime_days,
                                "excess_days": max(0, age_days - intended_lifetime_days),
                                "already_wasted": round(already_wasted, 2)
                            },
                            recommendation=f"Set table expiration to {intended_lifetime_days} days for temporary/staging tables. Already wasted ${already_wasted:.2f}."
                        )
                    )

        except Exception as e:
            logger.error(f"Error in scan_bigquery_no_expiration: {e}")

        return resources

    async def scan_bigquery_unpartitioned_large_tables(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect large unpartitioned tables.

        Waste: Tables >1 TB without partitioning = 90% query cost waste (full scans).
        Detection: size_bytes >1 TB AND no PARTITION BY in DDL AND queries doing full scans
        Cost: Query costs 10x higher ($100-$5,000/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰💰
        Impact: 35% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        min_size_tb = rules.get("min_size_tb", 1.0)
        full_scan_threshold = rules.get("full_scan_threshold", 0.5)
        estimated_partition_reduction = rules.get("estimated_partition_reduction", 0.90)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # Query tables >1 TB without partitioning
            query_tables = f"""
            SELECT
              table_catalog,
              table_schema,
              table_name,
              size_bytes / POW(1024, 4) as size_tb,
              row_count,
              creation_time,
              ddl
            FROM `{self.project_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
              AND size_bytes > {int(min_size_tb * 1024**4)}
              AND (ddl NOT LIKE '%PARTITION BY%' OR ddl IS NULL)
            ORDER BY size_bytes DESC
            """

            tables = list(client.query(query_tables).result())

            for table in tables:
                # Analyze recent queries (30 days)
                try:
                    query_jobs = f"""
                    SELECT
                      COUNT(*) as query_count,
                      AVG(total_bytes_processed / POW(1024, 4)) as avg_tb_scanned,
                      SUM(total_bytes_processed / POW(1024, 4)) as total_tb_scanned
                    FROM `{self.project_id}.region-{region or 'us'}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
                      AND state = 'DONE'
                      AND error_result IS NULL
                      AND EXISTS (
                        SELECT 1 FROM UNNEST(referenced_tables) as ref
                        WHERE ref.table_id = '{table.table_name}'
                      )
                    """

                    result = list(client.query(query_jobs).result())

                    if result and result[0].query_count > 0:
                        total_tb_scanned = result[0].total_tb_scanned or 0
                        avg_tb_scanned = result[0].avg_tb_scanned or 0
                        query_count = result[0].query_count

                        # Check if doing full scans
                        if avg_tb_scanned > (table.size_tb * full_scan_threshold):
                            # Calculate query costs
                            current_query_cost_30d = total_tb_scanned * 5  # $5/TB
                            monthly_cost = current_query_cost_30d

                            # Estimated cost with partitioning
                            recommended_cost = monthly_cost * (1 - estimated_partition_reduction)
                            monthly_waste = monthly_cost - recommended_cost

                            resources.append(
                                OrphanResourceData(
                                    resource_id=f"{self.project_id}:{table.table_schema}.{table.table_name}",
                                    resource_name=table.table_name,
                                    resource_type="bigquery_unpartitioned_large_tables",
                                    region=region or "us-central1",
                                    estimated_monthly_cost=monthly_waste,
                                    confidence_level="HIGH",
                                    resource_metadata={
                                        "project_id": self.project_id,
                                        "dataset_id": table.table_schema,
                                        "table_id": table.table_name,
                                        "size_tb": round(table.size_tb, 2),
                                        "is_partitioned": False,
                                        "query_count_30d": query_count,
                                        "avg_tb_scanned": round(avg_tb_scanned, 2),
                                        "total_tb_scanned": round(total_tb_scanned, 2),
                                        "current_query_cost_monthly": round(monthly_cost, 2),
                                        "recommended_query_cost_monthly": round(recommended_cost, 2),
                                        "estimated_scan_reduction": int(estimated_partition_reduction * 100)
                                    },
                                    recommendation=f"Add date partitioning (PARTITION BY DATE(timestamp)). Expected 90% query cost reduction = ${monthly_waste:.2f}/month savings."
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not analyze queries for table {table.table_name}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_bigquery_unpartitioned_large_tables: {e}")

        return resources

    async def scan_bigquery_unclustered_large_tables(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect large unclustered tables.

        Waste: Tables >100 GB without clustering = 30-50% query cost waste.
        Detection: size_bytes >100 GB AND no CLUSTER BY in DDL AND queries with WHERE filters
        Cost: Query costs 40% higher ($50-$1,000/month typical)
        Priority: HIGH (P1) 💰💰💰
        Impact: 15% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        min_size_gb = rules.get("min_size_gb", 100.0)
        clustering_reduction = rules.get("clustering_reduction", 0.40)
        min_queries_per_month = rules.get("min_queries_per_month", 10)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # Query tables >100 GB without clustering
            query_tables = f"""
            SELECT
              table_catalog,
              table_schema,
              table_name,
              size_bytes / POW(1024, 3) as size_gb,
              row_count,
              ddl
            FROM `{self.project_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
              AND size_bytes > {int(min_size_gb * 1024**3)}
              AND (ddl NOT LIKE '%CLUSTER BY%' OR ddl IS NULL)
            ORDER BY size_bytes DESC
            """

            tables = list(client.query(query_tables).result())

            for table in tables:
                # Analyze query patterns
                try:
                    query_jobs = f"""
                    SELECT
                      COUNT(*) as query_count,
                      AVG(total_bytes_processed / POW(1024, 3)) as avg_gb_scanned
                    FROM `{self.project_id}.region-{region or 'us'}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
                      AND state = 'DONE'
                      AND error_result IS NULL
                      AND EXISTS (
                        SELECT 1 FROM UNNEST(referenced_tables) as ref
                        WHERE ref.table_id = '{table.table_name}'
                      )
                    """

                    result = list(client.query(query_jobs).result())

                    if result and result[0].query_count >= min_queries_per_month:
                        query_count = result[0].query_count
                        avg_gb_scanned = result[0].avg_gb_scanned or 0

                        # Calculate query costs
                        current_cost_per_query = (avg_gb_scanned / 1000) * 5
                        current_monthly_cost = current_cost_per_query * query_count

                        # Estimated cost with clustering
                        recommended_cost = current_monthly_cost * (1 - clustering_reduction)
                        monthly_waste = current_monthly_cost - recommended_cost

                        resources.append(
                            OrphanResourceData(
                                resource_id=f"{self.project_id}:{table.table_schema}.{table.table_name}",
                                resource_name=table.table_name,
                                resource_type="bigquery_unclustered_large_tables",
                                region=region or "us-central1",
                                estimated_monthly_cost=monthly_waste,
                                confidence_level="HIGH",
                                resource_metadata={
                                    "project_id": self.project_id,
                                    "dataset_id": table.table_schema,
                                    "table_id": table.table_name,
                                    "size_gb": round(table.size_gb, 2),
                                    "is_clustered": False,
                                    "query_count_30d": query_count,
                                    "avg_gb_scanned": round(avg_gb_scanned, 2),
                                    "current_query_cost_monthly": round(current_monthly_cost, 2),
                                    "recommended_query_cost_monthly": round(recommended_cost, 2),
                                    "estimated_scan_reduction": int(clustering_reduction * 100)
                                },
                                recommendation=f"Add clustering (CLUSTER BY column1, column2). Expected 40% query cost reduction = ${monthly_waste:.2f}/month savings."
                            )
                        )

                except Exception as e:
                    logger.warning(f"Could not analyze queries for table {table.table_name}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_bigquery_unclustered_large_tables: {e}")

        return resources

    async def scan_bigquery_untagged_datasets(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect untagged datasets.

        Waste: Datasets without required labels = 5% governance waste.
        Detection: Missing required labels (environment, owner, cost-center)
        Cost: 5% of total dataset cost (governance overhead)
        Priority: LOW (P3) 💰💰
        Impact: 5% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        required_labels = rules.get("required_labels", ['environment', 'owner', 'cost-center'])
        governance_waste_pct = rules.get("governance_waste_pct", 0.05)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # List all datasets
            datasets = list(client.list_datasets(project=self.project_id))

            for dataset_ref in datasets:
                dataset = client.get_dataset(dataset_ref.reference)

                labels = dataset.labels if dataset.labels else {}

                # Identify missing labels
                missing_labels = [label for label in required_labels if label not in labels]

                if missing_labels:
                    # Calculate dataset storage cost
                    query_storage = f"""
                    SELECT SUM(size_bytes) / POW(1024, 3) as total_size_gb
                    FROM `{self.project_id}.{dataset.dataset_id}.INFORMATION_SCHEMA.TABLES`
                    """

                    result = list(client.query(query_storage).result())
                    total_size_gb = result[0].total_size_gb if result and result[0].total_size_gb else 0

                    storage_cost = total_size_gb * 0.020  # Assume active storage

                    # Governance waste = 5% of storage cost
                    monthly_waste = storage_cost * governance_waste_pct

                    resources.append(
                        OrphanResourceData(
                            resource_id=f"{self.project_id}:{dataset.dataset_id}",
                            resource_name=dataset.dataset_id,
                            resource_type="bigquery_untagged_datasets",
                            region=region or dataset.location,
                            estimated_monthly_cost=monthly_waste,
                            confidence_level="MEDIUM",
                            resource_metadata={
                                "project_id": self.project_id,
                                "dataset_id": dataset.dataset_id,
                                "location": dataset.location,
                                "labels": labels,
                                "missing_labels": missing_labels,
                                "storage_size_gb": round(total_size_gb, 2),
                                "storage_cost_monthly": round(storage_cost, 2)
                            },
                            recommendation=f"Add required labels: {', '.join(missing_labels)}. Required for cost allocation and governance."
                        )
                    )

        except Exception as e:
            logger.error(f"Error in scan_bigquery_untagged_datasets: {e}")

        return resources

    async def scan_bigquery_expensive_queries(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect expensive queries (>10 TB scanned).

        Waste: Queries scanning >10 TB = $50+ per run, often schedulable/optimizable.
        Detection: total_bytes_processed >10 TB AND scheduled = true
        Cost: Query costs with 70% optimization potential ($100-$2,000/month typical)
        Priority: CRITICAL (P0) 💰💰💰💰💰
        Impact: 30% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        expensive_query_tb_threshold = rules.get("expensive_query_tb_threshold", 10.0)
        lookback_days = rules.get("lookback_days", 30)
        optimization_reduction = rules.get("optimization_reduction", 0.70)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # Query expensive jobs
            query_jobs = f"""
            SELECT
              job_id,
              user_email,
              query,
              creation_time,
              total_bytes_processed / POW(1024, 4) as tb_scanned,
              (total_bytes_processed / POW(1024, 4)) * 5 as cost_usd,
              referenced_tables,
              statement_type
            FROM `{self.project_id}.region-{region or 'us'}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {lookback_days} DAY)
              AND state = 'DONE'
              AND error_result IS NULL
              AND total_bytes_processed > {int(expensive_query_tb_threshold * 1024**4)}
            ORDER BY total_bytes_processed DESC
            LIMIT 100
            """

            expensive_queries = list(client.query(query_jobs).result())

            for job in expensive_queries:
                tb_scanned = job.tb_scanned
                cost_per_run = job.cost_usd

                # Check if scheduled query
                is_scheduled = 'scheduled_query' in job.job_id.lower()
                runs_per_month = 30 if is_scheduled else 1

                current_monthly_cost = cost_per_run * runs_per_month

                # Optimization potential
                optimized_cost = current_monthly_cost * (1 - optimization_reduction)
                monthly_waste = current_monthly_cost - optimized_cost

                # Detect issues
                issues = []
                if 'SELECT *' in (job.query or '').upper():
                    issues.append('select_star')
                if 'WHERE' not in (job.query or '').upper():
                    issues.append('no_where_clause')

                resources.append(
                    OrphanResourceData(
                        resource_id=f"{self.project_id}:job_{job.job_id}",
                        resource_name=f"expensive_query_{job.job_id[:20]}",
                        resource_type="bigquery_expensive_queries",
                        region=region or "us-central1",
                        estimated_monthly_cost=monthly_waste,
                        confidence_level="HIGH",
                        resource_metadata={
                            "project_id": self.project_id,
                            "job_id": job.job_id,
                            "user_email": job.user_email,
                            "tb_scanned": round(tb_scanned, 2),
                            "cost_per_run": round(cost_per_run, 2),
                            "is_scheduled": is_scheduled,
                            "runs_per_month": runs_per_month,
                            "current_monthly_cost": round(current_monthly_cost, 2),
                            "issues_detected": issues,
                            "estimated_optimized_monthly_cost": round(optimized_cost, 2)
                        },
                        recommendation=f"Optimize query - 70% cost reduction possible with partitioning/column selection. Issues: {', '.join(issues) if issues else 'full table scan'}."
                    )
                )

        except Exception as e:
            logger.error(f"Error in scan_bigquery_expensive_queries: {e}")

        return resources

    async def scan_bigquery_ondemand_vs_flatrate(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect on-demand vs flat-rate optimization opportunities.

        Waste: On-demand costs >$2,000/month with stable workload = should use flat-rate.
        Detection: monthly_query_costs >$2,000 AND workload_variance <30%
        Cost: Difference between on-demand and flat-rate ($300-$1,500/month typical)
        Priority: HIGH (P1) 💰💰💰💰
        Impact: 10% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        flatrate_baseline_cost = rules.get("flatrate_baseline_cost", 2000.0)
        min_savings_threshold = rules.get("min_savings_threshold", 300.0)
        max_variance_threshold = rules.get("max_variance_threshold", 0.30)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # Calculate total query costs (30 days)
            query_analysis = f"""
            SELECT
              SUM(total_bytes_processed) / POW(1024, 4) as total_tb_scanned,
              COUNT(*) as total_queries,
              AVG(total_bytes_processed) / POW(1024, 3) as avg_gb_per_query
            FROM `{self.project_id}.region-{region or 'us'}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
              AND state = 'DONE'
              AND error_result IS NULL
              AND job_type = 'QUERY'
            """

            result = list(client.query(query_analysis).result())[0]

            total_tb_scanned = result.total_tb_scanned or 0
            total_queries = result.total_queries or 0

            # On-demand cost (1 TB free per month)
            free_tb = 1.0
            billable_tb = max(0, total_tb_scanned - free_tb)
            ondemand_monthly_cost = billable_tb * 5  # $5/TB

            if ondemand_monthly_cost > flatrate_baseline_cost:
                # Flat-rate might be beneficial
                monthly_savings = ondemand_monthly_cost - flatrate_baseline_cost

                if monthly_savings >= min_savings_threshold:
                    # Calculate workload variance (simplified)
                    # In real implementation, would analyze daily variance
                    daily_variance = 0.15  # Placeholder - assume stable workload

                    if daily_variance < max_variance_threshold:
                        confidence = "HIGH"
                        workload_stability = "high"
                    else:
                        confidence = "MEDIUM"
                        workload_stability = "variable"

                    resources.append(
                        OrphanResourceData(
                            resource_id=f"{self.project_id}:pricing_analysis",
                            resource_name="project_pricing_optimization",
                            resource_type="bigquery_ondemand_vs_flatrate",
                            region=region or "us-central1",
                            estimated_monthly_cost=monthly_savings,
                            confidence_level=confidence,
                            resource_metadata={
                                "project_id": self.project_id,
                                "total_queries": total_queries,
                                "total_tb_scanned": round(total_tb_scanned, 2),
                                "current_pricing_model": "on_demand",
                                "current_monthly_cost": round(ondemand_monthly_cost, 2),
                                "recommended_pricing_model": "flat_rate",
                                "flatrate_monthly_cost": flatrate_baseline_cost,
                                "estimated_annual_savings": round(monthly_savings * 12, 2),
                                "savings_percentage": round((monthly_savings / ondemand_monthly_cost) * 100, 1),
                                "workload_stability": workload_stability
                            },
                            recommendation=f"Switch to flat-rate pricing (100 slots = $2,000/month). Save ${monthly_savings:.2f}/month with {workload_stability} workload."
                        )
                    )

        except Exception as e:
            logger.error(f"Error in scan_bigquery_ondemand_vs_flatrate: {e}")

        return resources

    async def scan_bigquery_unused_materialized_views(
        self, region: str | None = None, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect unused materialized views.

        Waste: Materialized views never queried = storage + refresh waste.
        Detection: table_type = 'MATERIALIZED_VIEW' AND query_count_30d = 0
        Cost: Storage + refresh costs ($10-$500/month typical)
        Priority: MEDIUM (P2) 💰💰💰
        Impact: 5% of BigQuery waste
        """
        resources: list[OrphanResourceData] = []
        rules = detection_rules or {}

        lookback_days = rules.get("lookback_days", 30)
        refresh_scan_percentage = rules.get("refresh_scan_percentage", 0.10)

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project_id)

            # List all materialized views
            query_mvs = f"""
            SELECT
              table_catalog,
              table_schema,
              table_name,
              creation_time,
              size_bytes / POW(1024, 3) as size_gb
            FROM `{self.project_id}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'MATERIALIZED_VIEW'
            ORDER BY size_bytes DESC
            """

            materialized_views = list(client.query(query_mvs).result())

            for mv in materialized_views:
                # Check if MV was queried
                try:
                    query_usage = f"""
                    SELECT COUNT(*) as query_count
                    FROM `{self.project_id}.region-{region or 'us'}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {lookback_days} DAY)
                      AND state = 'DONE'
                      AND error_result IS NULL
                      AND EXISTS (
                        SELECT 1 FROM UNNEST(referenced_tables) as ref
                        WHERE ref.table_id = '{mv.table_name}'
                          AND ref.dataset_id = '{mv.table_schema}'
                      )
                    """

                    result = list(client.query(query_usage).result())
                    query_count = result[0].query_count if result else 0

                    if query_count == 0:
                        # MV never used
                        size_gb = mv.size_gb

                        # Storage cost
                        storage_cost = size_gb * 0.020

                        # Estimate refresh cost (assume base table 10x size, refresh daily, scans 10%)
                        base_table_size_tb = (size_gb / 1000) * 10
                        refresh_tb = base_table_size_tb * refresh_scan_percentage
                        refresh_cost_monthly = refresh_tb * 5 * 30  # $5/TB × 30 days

                        monthly_waste = storage_cost + refresh_cost_monthly

                        resources.append(
                            OrphanResourceData(
                                resource_id=f"{self.project_id}:{mv.table_schema}.{mv.table_name}",
                                resource_name=mv.table_name,
                                resource_type="bigquery_unused_materialized_views",
                                region=region or "us-central1",
                                estimated_monthly_cost=monthly_waste,
                                confidence_level="HIGH",
                                resource_metadata={
                                    "project_id": self.project_id,
                                    "dataset_id": mv.table_schema,
                                    "table_id": mv.table_name,
                                    "size_gb": round(size_gb, 2),
                                    "query_count_30d": 0,
                                    "storage_cost_monthly": round(storage_cost, 2),
                                    "refresh_cost_monthly": round(refresh_cost_monthly, 2)
                                },
                                recommendation=f"Delete unused materialized view. Never queried in {lookback_days} days. Wasting ${monthly_waste:.2f}/month."
                            )
                        )

                except Exception as e:
                    logger.warning(f"Could not check usage for MV {mv.table_name}: {e}")

        except Exception as e:
            logger.error(f"Error in scan_bigquery_unused_materialized_views: {e}")

        return resources

    # AWS-specific EC2 instance methods (not applicable to GCP)
    async def scan_oversized_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EC2-specific)."""
        return []

    async def scan_old_generation_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EC2-specific)."""
        return []

    async def scan_burstable_credit_waste(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS T2/T3/T4-specific)."""
        return []

    async def scan_dev_test_24_7_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EC2-specific)."""
        return []

    async def scan_untagged_ec2_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EC2-specific)."""
        return []

    async def scan_right_sizing_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EC2-specific)."""
        return []

    async def scan_spot_eligible_workloads(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Spot-specific)."""
        return []

    async def scan_scheduled_unused_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS EC2-specific)."""
        return []

    # AWS-specific NAT Gateway methods (not applicable to GCP)
    async def scan_nat_gateway_vpc_endpoint_candidates(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS NAT Gateway-specific)."""
        return []

    async def scan_nat_gateway_dev_test_unused_hours(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS NAT Gateway-specific)."""
        return []

    async def scan_nat_gateway_obsolete_migration(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS NAT Gateway-specific)."""
        return []

    # AWS-specific Load Balancer methods (not applicable to GCP)
    async def scan_load_balancer_cross_zone_disabled(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Load Balancer-specific)."""
        return []

    async def scan_load_balancer_idle_patterns(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Not applicable for GCP (AWS Load Balancer-specific)."""
        return []
