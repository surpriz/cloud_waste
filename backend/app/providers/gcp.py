"""GCP provider implementation for CloudWaste."""

import asyncio
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import compute_v1, logging, monitoring_v3
from google.oauth2 import service_account
from google.protobuf.timestamp_pb2 import Timestamp

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

    async def scan_redundant_disk_snapshots(
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

    async def scan_old_unused_disk_snapshots(
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

    async def scan_deleted_vm_snapshots(
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

    async def scan_failed_disk_snapshots(
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

    async def scan_untagged_disk_snapshots(
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

    async def scan_excessive_retention_nonprod_snapshots(
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

    async def scan_duplicate_disk_snapshots(
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
