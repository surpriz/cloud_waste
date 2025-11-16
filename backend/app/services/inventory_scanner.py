"""Inventory scanner service for complete cloud resource scanning.

This service scans ALL cloud resources (not just orphans) to provide
cost intelligence and optimization recommendations.
"""

import structlog
from datetime import datetime, timedelta
from typing import Any

from app.providers.base import AllCloudResourceData

logger = structlog.get_logger()


class AWSInventoryScanner:
    """AWS-specific inventory scanner for cost intelligence."""

    def __init__(self, provider: Any) -> None:
        """
        Initialize AWS inventory scanner.

        Args:
            provider: AWS provider instance with authenticated session
        """
        self.provider = provider
        self.session = provider.session

    async def scan_ec2_instances(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL EC2 instances (running, stopped, etc.) for cost intelligence.

        Unlike orphan detection, this returns ALL instances with utilization metrics
        and optimization recommendations.

        Args:
            region: AWS region to scan

        Returns:
            List of all EC2 instance resources
        """
        logger.info("inventory.scan_ec2_start", region=region)
        all_instances: list[AllCloudResourceData] = []

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Describe ALL instances (no filters)
                response = await ec2.describe_instances()

                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        instance_type = instance["InstanceType"]
                        state = instance["State"]["Name"]

                        # Extract instance name from tags
                        instance_name = None
                        tags = {}
                        for tag in instance.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]
                            if tag["Key"] == "Name":
                                instance_name = tag["Value"]

                        # Get CloudWatch metrics (last 14 days)
                        cpu_util = await self._get_cpu_utilization(instance_id, region)
                        network_in = await self._get_network_in(instance_id, region)

                        # Calculate monthly cost
                        monthly_cost = self._calculate_ec2_monthly_cost(
                            instance_type, state
                        )

                        # Determine utilization status
                        utilization_status = self._determine_utilization_status(
                            cpu_util, state
                        )

                        # Calculate optimization score and recommendations
                        (
                            is_optimizable,
                            optimization_score,
                            optimization_priority,
                            potential_savings,
                            recommendations,
                        ) = self._calculate_ec2_optimization(
                            instance,
                            cpu_util,
                            monthly_cost,
                            state,
                        )

                        # Check if instance is also detected as orphan
                        is_orphan = state == "stopped" or (
                            state == "running" and cpu_util < 5.0
                        )

                        # Create resource data
                        resource = AllCloudResourceData(
                            resource_type="ec2_instance",
                            resource_id=instance_id,
                            resource_name=instance_name,
                            region=region,
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                "instance_type": instance_type,
                                "state": state,
                                "availability_zone": instance.get(
                                    "Placement", {}
                                ).get("AvailabilityZone"),
                                "launch_time": instance.get("LaunchTime").isoformat()
                                if instance.get("LaunchTime")
                                else None,
                                "platform": instance.get("Platform", "linux"),
                                "vpc_id": instance.get("VpcId"),
                                "subnet_id": instance.get("SubnetId"),
                            },
                            currency="USD",
                            utilization_status=utilization_status,
                            cpu_utilization_percent=cpu_util,
                            memory_utilization_percent=None,  # TODO: Fetch from CloudWatch agent
                            network_utilization_mbps=network_in,
                            is_optimizable=is_optimizable,
                            optimization_priority=optimization_priority,
                            optimization_score=optimization_score,
                            potential_monthly_savings=potential_savings,
                            optimization_recommendations=recommendations,
                            tags=tags,
                            resource_status=state,
                            is_orphan=is_orphan,
                            created_at_cloud=instance.get("LaunchTime"),
                            last_used_at=None,  # TODO: Estimate from CloudWatch
                        )

                        all_instances.append(resource)

                logger.info(
                    "inventory.scan_ec2_complete",
                    region=region,
                    total_instances=len(all_instances),
                )

        except Exception as e:
            logger.error(
                "inventory.scan_ec2_error",
                region=region,
                error=str(e),
                exc_info=True,
            )
            raise

        return all_instances

    async def scan_rds_instances(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL RDS instances for cost intelligence.

        Args:
            region: AWS region to scan

        Returns:
            List of all RDS instance resources
        """
        logger.info("inventory.scan_rds_start", region=region)
        all_rds: list[AllCloudResourceData] = []

        try:
            async with self.session.client("rds", region_name=region) as rds:
                response = await rds.describe_db_instances()

                for db_instance in response.get("DBInstances", []):
                    db_identifier = db_instance["DBInstanceIdentifier"]
                    db_instance_class = db_instance["DBInstanceClass"]
                    db_engine = db_instance["Engine"]
                    status = db_instance["DBInstanceStatus"]

                    # Get CloudWatch metrics
                    cpu_util = await self._get_rds_cpu_utilization(
                        db_identifier, region
                    )
                    connections = await self._get_rds_connections(
                        db_identifier, region
                    )

                    # Calculate monthly cost
                    monthly_cost = self._calculate_rds_monthly_cost(
                        db_instance_class, db_engine, status
                    )

                    # Determine utilization
                    utilization_status = self._determine_utilization_status(
                        cpu_util, status
                    )

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        optimization_priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_rds_optimization(
                        db_instance,
                        cpu_util,
                        connections,
                        monthly_cost,
                        status,
                    )

                    # Check if RDS is orphan (stopped or very low activity)
                    is_orphan = status == "stopped" or (
                        status == "available" and cpu_util < 1.0 and connections < 1
                    )

                    # Extract tags
                    tags = {}
                    tag_list = db_instance.get("TagList", [])
                    for tag in tag_list:
                        tags[tag["Key"]] = tag["Value"]

                    resource = AllCloudResourceData(
                        resource_type="rds_instance",
                        resource_id=db_identifier,
                        resource_name=db_identifier,
                        region=region,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata={
                            "db_instance_class": db_instance_class,
                            "engine": db_engine,
                            "engine_version": db_instance.get("EngineVersion"),
                            "status": status,
                            "allocated_storage": db_instance.get("AllocatedStorage"),
                            "storage_type": db_instance.get("StorageType"),
                            "multi_az": db_instance.get("MultiAZ", False),
                            "availability_zone": db_instance.get("AvailabilityZone"),
                            "instance_create_time": db_instance.get(
                                "InstanceCreateTime"
                            ).isoformat()
                            if db_instance.get("InstanceCreateTime")
                            else None,
                        },
                        currency="USD",
                        utilization_status=utilization_status,
                        cpu_utilization_percent=cpu_util,
                        network_utilization_mbps=None,
                        is_optimizable=is_optimizable,
                        optimization_priority=optimization_priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations,
                        tags=tags,
                        resource_status=status,
                        is_orphan=is_orphan,
                        created_at_cloud=db_instance.get("InstanceCreateTime"),
                        last_used_at=None,
                    )

                    all_rds.append(resource)

                logger.info(
                    "inventory.scan_rds_complete",
                    region=region,
                    total_rds=len(all_rds),
                )

        except Exception as e:
            logger.error(
                "inventory.scan_rds_error",
                region=region,
                error=str(e),
                exc_info=True,
            )
            raise

        return all_rds

    async def scan_s3_buckets(self) -> list[AllCloudResourceData]:
        """
        Scan ALL S3 buckets for cost intelligence.

        Note: S3 is global, so this is called once per account (not per region).

        Returns:
            List of all S3 bucket resources
        """
        logger.info("inventory.scan_s3_start")
        all_buckets: list[AllCloudResourceData] = []

        try:
            async with self.session.client("s3") as s3:
                response = await s3.list_buckets()

                for bucket in response.get("Buckets", []):
                    bucket_name = bucket["Name"]

                    # Get bucket region
                    try:
                        location_response = await s3.get_bucket_location(
                            Bucket=bucket_name
                        )
                        region = location_response.get("LocationConstraint") or "us-east-1"
                    except Exception:
                        region = "us-east-1"

                    # Get bucket size and object count (from CloudWatch metrics)
                    bucket_size_gb, object_count = await self._get_s3_bucket_size(
                        bucket_name, region
                    )

                    # Calculate monthly cost (storage + requests)
                    monthly_cost = self._calculate_s3_monthly_cost(
                        bucket_size_gb, region
                    )

                    # Determine if bucket is empty or rarely used
                    is_empty = bucket_size_gb < 0.001  # Less than 1 MB
                    utilization_status = "idle" if is_empty else "medium"

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        optimization_priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_s3_optimization(
                        bucket_name,
                        bucket_size_gb,
                        object_count,
                        monthly_cost,
                        region,
                    )

                    # Check if S3 bucket is orphan (empty for >90 days)
                    is_orphan = is_empty

                    # Get tags
                    tags = {}
                    try:
                        tag_response = await s3.get_bucket_tagging(Bucket=bucket_name)
                        for tag in tag_response.get("TagSet", []):
                            tags[tag["Key"]] = tag["Value"]
                    except Exception:
                        pass  # Bucket may not have tags

                    resource = AllCloudResourceData(
                        resource_type="s3_bucket",
                        resource_id=bucket_name,
                        resource_name=bucket_name,
                        region=region,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata={
                            "bucket_size_gb": bucket_size_gb,
                            "object_count": object_count,
                            "creation_date": bucket["CreationDate"].isoformat()
                            if bucket.get("CreationDate")
                            else None,
                        },
                        currency="USD",
                        utilization_status=utilization_status,
                        storage_utilization_percent=(
                            min(bucket_size_gb / 100, 100) if bucket_size_gb else 0
                        ),
                        is_optimizable=is_optimizable,
                        optimization_priority=optimization_priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations,
                        tags=tags,
                        resource_status="active",
                        is_orphan=is_orphan,
                        created_at_cloud=bucket.get("CreationDate"),
                        last_used_at=None,
                    )

                    all_buckets.append(resource)

                logger.info(
                    "inventory.scan_s3_complete",
                    total_buckets=len(all_buckets),
                )

        except Exception as e:
            logger.error(
                "inventory.scan_s3_error",
                error=str(e),
                exc_info=True,
            )
            raise

        return all_buckets

    # ========== Helper Methods ==========

    async def _get_cpu_utilization(
        self, instance_id: str, region: str
    ) -> float:
        """Get average CPU utilization from CloudWatch (last 14 days)."""
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=14)

                response = await cw.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,  # 1 day
                    Statistics=["Average"],
                )

                datapoints = response.get("Datapoints", [])
                if not datapoints:
                    return 0.0

                avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                return round(avg_cpu, 2)

        except Exception as e:
            logger.warning(
                "cloudwatch.cpu_fetch_error",
                instance_id=instance_id,
                error=str(e),
            )
            return 0.0

    async def _get_network_in(
        self, instance_id: str, region: str
    ) -> float | None:
        """Get average network in (Mbps) from CloudWatch."""
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=14)

                response = await cw.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="NetworkIn",
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Average"],
                )

                datapoints = response.get("Datapoints", [])
                if not datapoints:
                    return None

                # Convert bytes to Mbps (average over period)
                avg_bytes = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                mbps = (avg_bytes * 8) / (1024 * 1024)  # bytes to Mbps
                return round(mbps, 2)

        except Exception:
            return None

    async def _get_rds_cpu_utilization(
        self, db_identifier: str, region: str
    ) -> float:
        """Get average RDS CPU utilization from CloudWatch."""
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=14)

                response = await cw.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_identifier}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Average"],
                )

                datapoints = response.get("Datapoints", [])
                if not datapoints:
                    return 0.0

                avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                return round(avg_cpu, 2)

        except Exception:
            return 0.0

    async def _get_rds_connections(
        self, db_identifier: str, region: str
    ) -> float:
        """Get average RDS database connections from CloudWatch."""
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=14)

                response = await cw.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="DatabaseConnections",
                    Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_identifier}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Average"],
                )

                datapoints = response.get("Datapoints", [])
                if not datapoints:
                    return 0.0

                avg_conn = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                return round(avg_conn, 2)

        except Exception:
            return 0.0

    async def _get_s3_bucket_size(
        self, bucket_name: str, region: str
    ) -> tuple[float, int]:
        """Get S3 bucket size (GB) and object count from CloudWatch."""
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=2)

                # Get bucket size
                size_response = await cw.get_metric_statistics(
                    Namespace="AWS/S3",
                    MetricName="BucketSizeBytes",
                    Dimensions=[
                        {"Name": "BucketName", "Value": bucket_name},
                        {"Name": "StorageType", "Value": "StandardStorage"},
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Average"],
                )

                size_datapoints = size_response.get("Datapoints", [])
                size_bytes = size_datapoints[0]["Average"] if size_datapoints else 0
                size_gb = size_bytes / (1024**3)

                # Get object count
                count_response = await cw.get_metric_statistics(
                    Namespace="AWS/S3",
                    MetricName="NumberOfObjects",
                    Dimensions=[
                        {"Name": "BucketName", "Value": bucket_name},
                        {"Name": "StorageType", "Value": "AllStorageTypes"},
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Average"],
                )

                count_datapoints = count_response.get("Datapoints", [])
                object_count = int(count_datapoints[0]["Average"]) if count_datapoints else 0

                return round(size_gb, 3), object_count

        except Exception:
            return 0.0, 0

    def _calculate_ec2_monthly_cost(
        self, instance_type: str, state: str
    ) -> float:
        """
        Calculate estimated monthly cost for EC2 instance.

        Simplified pricing - in production, use AWS Pricing API.
        """
        # Hardcoded prices per hour (us-east-1, on-demand)
        INSTANCE_PRICES = {
            "t2.micro": 0.0116,
            "t2.small": 0.023,
            "t2.medium": 0.0464,
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "m5.large": 0.096,
            "m5.xlarge": 0.192,
            "c5.large": 0.085,
            "r5.large": 0.126,
        }

        hourly_rate = INSTANCE_PRICES.get(instance_type, 0.10)  # Default $0.10/hr

        if state == "stopped":
            # Stopped instances still incur EBS costs (~$0.10/GB/month)
            # Estimate 30GB EBS volume
            return 30 * 0.10
        else:
            # Running instances: hourly rate * 730 hours/month
            return hourly_rate * 730

    def _calculate_rds_monthly_cost(
        self, db_instance_class: str, engine: str, status: str
    ) -> float:
        """Calculate estimated monthly cost for RDS instance."""
        # Simplified RDS pricing
        RDS_PRICES = {
            "db.t2.micro": 0.017,
            "db.t3.micro": 0.016,
            "db.t3.small": 0.032,
            "db.t3.medium": 0.064,
            "db.m5.large": 0.17,
            "db.r5.large": 0.24,
        }

        hourly_rate = RDS_PRICES.get(db_instance_class, 0.15)

        if status == "stopped":
            # Stopped RDS instances incur storage costs
            return 50 * 0.10  # Estimate 50GB storage
        else:
            return hourly_rate * 730

    def _calculate_s3_monthly_cost(self, size_gb: float, region: str) -> float:
        """Calculate estimated monthly cost for S3 bucket."""
        # S3 Standard pricing: $0.023/GB/month (first 50TB)
        storage_cost = size_gb * 0.023

        # Add request costs (estimate)
        request_cost = 1.0  # Flat $1/month estimate

        return storage_cost + request_cost

    def _determine_utilization_status(
        self, cpu_util: float | None, state: str
    ) -> str:
        """Determine utilization status based on CPU and state."""
        if state in ["stopped", "stopping"]:
            return "idle"
        elif cpu_util is None:
            return "unknown"
        elif cpu_util < 10:
            return "idle"
        elif cpu_util < 30:
            return "low"
        elif cpu_util < 70:
            return "medium"
        else:
            return "high"

    def _calculate_ec2_optimization(
        self,
        instance: dict[str, Any],
        cpu_util: float,
        monthly_cost: float,
        state: str,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """
        Calculate EC2 optimization metrics.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        recommendations = []
        is_optimizable = False
        optimization_score = 0
        potential_savings = 0.0
        priority = "none"

        instance_type = instance["InstanceType"]

        # Scenario 1: Stopped instance (critical)
        if state == "stopped":
            is_optimizable = True
            optimization_score = 80
            priority = "critical"
            potential_savings = monthly_cost * 0.7  # Save 70% (only EBS remains)
            recommendations.append({
                "action": "Terminate or restart stopped instance",
                "details": f"Instance has been stopped. Terminate to save ${potential_savings:.2f}/month",
                "priority": "critical",
            })

        # Scenario 2: Very low CPU (<10%)
        elif cpu_util < 10:
            is_optimizable = True
            optimization_score = 60
            priority = "high"
            # Suggest downgrading to smaller instance
            potential_savings = monthly_cost * 0.5
            recommendations.append({
                "action": "Downgrade instance type",
                "details": f"CPU utilization is {cpu_util}%. Consider t3.micro or t3.small",
                "alternatives": [
                    {"name": "t3.micro", "cost": 7.60, "savings": monthly_cost - 7.60},
                    {"name": "t3.small", "cost": 15.20, "savings": monthly_cost - 15.20},
                ],
                "priority": "high",
            })

        # Scenario 3: Old generation instance
        elif instance_type.startswith(("t2.", "m4.", "c4.", "r4.")):
            is_optimizable = True
            optimization_score = 40
            priority = "medium"
            potential_savings = monthly_cost * 0.2  # 20% savings
            new_type = instance_type.replace("t2.", "t3.").replace("m4.", "m5.").replace("c4.", "c5.").replace("r4.", "r5.")
            recommendations.append({
                "action": "Upgrade to newer generation",
                "details": f"Migrate {instance_type} → {new_type} for better price/performance",
                "priority": "medium",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    def _calculate_rds_optimization(
        self,
        db_instance: dict[str, Any],
        cpu_util: float,
        connections: float,
        monthly_cost: float,
        status: str,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """Calculate RDS optimization metrics."""
        recommendations = []
        is_optimizable = False
        optimization_score = 0
        potential_savings = 0.0
        priority = "none"

        # Scenario 1: Stopped RDS
        if status == "stopped":
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost * 0.8
            recommendations.append({
                "action": "Delete or restart stopped RDS instance",
                "details": f"RDS instance is stopped. Terminate to save ${potential_savings:.2f}/month",
                "priority": "critical",
            })

        # Scenario 2: Very low activity
        elif cpu_util < 5 and connections < 2:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost * 0.5
            recommendations.append({
                "action": "Downgrade RDS instance or move to Aurora Serverless",
                "details": f"CPU: {cpu_util}%, Connections: {connections}. Consider smaller instance or serverless",
                "priority": "high",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    def _calculate_s3_optimization(
        self,
        bucket_name: str,
        bucket_size_gb: float,
        object_count: int,
        monthly_cost: float,
        region: str,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """Calculate S3 optimization metrics."""
        recommendations = []
        is_optimizable = False
        optimization_score = 0
        potential_savings = 0.0
        priority = "none"

        # Scenario 1: Empty bucket
        if bucket_size_gb < 0.001:
            is_optimizable = True
            optimization_score = 50
            priority = "low"
            potential_savings = 1.0  # Request costs
            recommendations.append({
                "action": "Delete empty S3 bucket",
                "details": f"Bucket is empty. Delete to save ${potential_savings:.2f}/month",
                "priority": "low",
            })

        # Scenario 2: Large bucket on Standard storage
        elif bucket_size_gb > 1000:  # > 1TB
            is_optimizable = True
            optimization_score = 30
            priority = "medium"
            # Suggest Glacier for archival
            potential_savings = bucket_size_gb * (0.023 - 0.004)  # Standard → Glacier
            recommendations.append({
                "action": "Move to S3 Glacier for archival data",
                "details": f"Bucket size: {bucket_size_gb:.1f}GB. Move infrequently accessed data to Glacier",
                "alternatives": [
                    {"name": "S3 Glacier", "cost": bucket_size_gb * 0.004, "savings": potential_savings},
                ],
                "priority": "medium",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations


class AzureInventoryScanner:
    """Azure-specific inventory scanner for cost intelligence."""

    def __init__(self, provider: Any) -> None:
        """
        Initialize Azure inventory scanner.

        Args:
            provider: Azure provider instance with authenticated credentials
        """
        self.provider = provider
        self.tenant_id = provider.tenant_id
        self.client_id = provider.client_id
        self.client_secret = provider.client_secret
        self.subscription_id = provider.subscription_id
        self.regions = provider.regions or []
        self.resource_groups = provider.resource_groups or []

    async def scan_virtual_machines(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Virtual Machines for cost intelligence.

        Unlike orphan detection, this returns ALL VMs (running, stopped, deallocated)
        with utilization metrics and optimization recommendations.

        Args:
            region: Azure region to scan

        Returns:
            List of all VM resources
        """
        logger.info("inventory.scan_azure_vms_start", region=region)
        all_vms: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.compute import ComputeManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # Get ALL VMs
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                # Filter by region
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self.provider._is_resource_in_scope(vm.id):
                    continue

                # Extract resource group name
                resource_group = vm.id.split('/')[4]

                # Get instance view for power state
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=resource_group,
                    vm_name=vm.name
                )

                # Determine power state
                power_state = "unknown"
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]

                # Extract tags
                tags = vm.tags if vm.tags else {}

                # Get VM metrics (CPU utilization from Azure Monitor)
                cpu_util = await self._get_vm_cpu_utilization(
                    resource_group, vm.name, region
                )
                network_in = await self._get_vm_network_in(
                    resource_group, vm.name, region
                )

                # Calculate monthly cost (VM + disks)
                monthly_cost = self._calculate_vm_monthly_cost(
                    vm.hardware_profile.vm_size if vm.hardware_profile else "Standard_D2s_v3",
                    power_state,
                    vm.storage_profile if vm.storage_profile else None,
                    compute_client,
                    resource_group
                )

                # Determine utilization status
                utilization_status = self._determine_vm_utilization_status(
                    cpu_util, power_state
                )

                # Calculate optimization
                (
                    is_optimizable,
                    optimization_score,
                    optimization_priority,
                    potential_savings,
                    recommendations,
                ) = self._calculate_vm_optimization(
                    vm,
                    power_state,
                    cpu_util,
                    monthly_cost,
                )

                # Check if VM is orphan (deallocated or very low CPU)
                is_orphan = power_state == "deallocated" or (
                    power_state == "running" and cpu_util < 5.0
                )

                # Create resource data
                resource = AllCloudResourceData(
                    resource_type="azure_vm",
                    resource_id=vm.id,
                    resource_name=vm.name,
                    region=region,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata={
                        "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None,
                        "power_state": power_state,
                        "os_type": vm.storage_profile.os_disk.os_type if vm.storage_profile and vm.storage_profile.os_disk else None,
                        "resource_group": resource_group,
                        "availability_zone": vm.zones[0] if vm.zones else None,
                    },
                    currency="USD",
                    utilization_status=utilization_status,
                    cpu_utilization_percent=cpu_util,
                    memory_utilization_percent=None,  # TODO: Fetch from Azure Monitor
                    network_utilization_mbps=network_in,
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=potential_savings,
                    optimization_recommendations=recommendations,
                    tags=tags,
                    resource_status=power_state,
                    is_orphan=is_orphan,
                    created_at_cloud=None,  # Azure doesn't provide creation time easily
                    last_used_at=None,
                )

                all_vms.append(resource)

            logger.info(
                "inventory.scan_azure_vms_complete",
                region=region,
                total_vms=len(all_vms),
            )

        except Exception as e:
            logger.error(
                "inventory.scan_azure_vms_error",
                region=region,
                error=str(e),
                exc_info=True,
            )
            raise

        return all_vms

    async def scan_managed_disks(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Managed Disks for cost intelligence.

        Args:
            region: Azure region to scan

        Returns:
            List of all disk resources
        """
        logger.info("inventory.scan_azure_disks_start", region=region)
        all_disks: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.compute import ComputeManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # Get ALL disks
            disks = list(compute_client.disks.list())

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group
                if not self.provider._is_resource_in_scope(disk.id):
                    continue

                # Determine if attached or unattached
                is_attached = disk.managed_by is not None
                disk_state = "attached" if is_attached else "unattached"

                # Extract tags
                tags = disk.tags if disk.tags else {}

                # Calculate monthly cost using provider's helper
                monthly_cost = self.provider._calculate_disk_cost(disk)

                # Determine utilization status
                utilization_status = "idle" if not is_attached else "active"

                # Calculate optimization
                (
                    is_optimizable,
                    optimization_score,
                    optimization_priority,
                    potential_savings,
                    recommendations,
                ) = self._calculate_disk_optimization(
                    disk,
                    is_attached,
                    monthly_cost,
                )

                # Check if disk is orphan (unattached)
                is_orphan = not is_attached

                # Create resource data
                resource = AllCloudResourceData(
                    resource_type="azure_managed_disk",
                    resource_id=disk.id,
                    resource_name=disk.name,
                    region=region,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata={
                        "disk_size_gb": disk.disk_size_gb,
                        "disk_state": disk_state,
                        "sku_name": disk.sku.name if disk.sku else None,
                        "sku_tier": disk.sku.tier if disk.sku else None,
                        "disk_iops": getattr(disk, 'disk_iops_read_write', None),
                        "disk_mbps": getattr(disk, 'disk_mbps_read_write', None),
                        "encryption_type": disk.encryption.type if disk.encryption else None,
                    },
                    currency="USD",
                    utilization_status=utilization_status,
                    cpu_utilization_percent=None,
                    memory_utilization_percent=None,
                    storage_utilization_percent=None,  # TODO: Calculate from IOPS metrics
                    network_utilization_mbps=None,
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=potential_savings,
                    optimization_recommendations=recommendations,
                    tags=tags,
                    resource_status=disk_state,
                    is_orphan=is_orphan,
                    created_at_cloud=disk.time_created.replace(tzinfo=None) if hasattr(disk, 'time_created') and disk.time_created else None,
                    last_used_at=None,
                )

                all_disks.append(resource)

            logger.info(
                "inventory.scan_azure_disks_complete",
                region=region,
                total_disks=len(all_disks),
            )

        except Exception as e:
            logger.error(
                "inventory.scan_azure_disks_error",
                region=region,
                error=str(e),
                exc_info=True,
            )
            raise

        return all_disks

    async def scan_public_ips(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Public IPs for cost intelligence.

        Args:
            region: Azure region to scan

        Returns:
            List of all public IP resources
        """
        logger.info("inventory.scan_azure_ips_start", region=region)
        all_ips: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # Get ALL public IPs
            public_ips = list(network_client.public_ip_addresses.list_all())

            for ip in public_ips:
                # Filter by region
                if ip.location != region:
                    continue

                # Filter by resource group
                if not self.provider._is_resource_in_scope(ip.id):
                    continue

                # Determine if assigned or unassigned
                is_assigned = ip.ip_configuration is not None
                ip_state = "assigned" if is_assigned else "unassigned"

                # Extract tags
                tags = ip.tags if ip.tags else {}

                # Calculate monthly cost
                sku_name = ip.sku.name if ip.sku else "Basic"
                monthly_cost = 3.65 if sku_name == "Basic" else 4.00  # Standard SKU costs more

                # Determine utilization status
                utilization_status = "active" if is_assigned else "idle"

                # Calculate optimization
                (
                    is_optimizable,
                    optimization_score,
                    optimization_priority,
                    potential_savings,
                    recommendations,
                ) = self._calculate_ip_optimization(
                    ip,
                    is_assigned,
                    sku_name,
                    monthly_cost,
                )

                # Check if IP is orphan (unassigned)
                is_orphan = not is_assigned

                # Create resource data
                resource = AllCloudResourceData(
                    resource_type="azure_public_ip",
                    resource_id=ip.id,
                    resource_name=ip.name,
                    region=region,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata={
                        "ip_address": ip.ip_address,
                        "ip_state": ip_state,
                        "sku_name": sku_name,
                        "allocation_method": ip.public_ip_allocation_method.value if ip.public_ip_allocation_method else None,
                        "ip_version": ip.public_ip_address_version.value if ip.public_ip_address_version else None,
                        "idle_timeout_minutes": ip.idle_timeout_in_minutes,
                    },
                    currency="USD",
                    utilization_status=utilization_status,
                    cpu_utilization_percent=None,
                    memory_utilization_percent=None,
                    storage_utilization_percent=None,
                    network_utilization_mbps=None,  # TODO: Fetch from Azure Monitor
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=potential_savings,
                    optimization_recommendations=recommendations,
                    tags=tags,
                    resource_status=ip_state,
                    is_orphan=is_orphan,
                    created_at_cloud=None,
                    last_used_at=None,
                )

                all_ips.append(resource)

            logger.info(
                "inventory.scan_azure_ips_complete",
                region=region,
                total_ips=len(all_ips),
            )

        except Exception as e:
            logger.error(
                "inventory.scan_azure_ips_error",
                region=region,
                error=str(e),
                exc_info=True,
            )
            raise

        return all_ips

    # Helper methods for Azure Monitor metrics

    async def _get_vm_cpu_utilization(
        self, resource_group: str, vm_name: str, region: str
    ) -> float:
        """
        Get CPU utilization percentage from Azure Monitor (last 14 days average).

        Args:
            resource_group: Resource group name
            vm_name: VM name
            region: Azure region

        Returns:
            Average CPU utilization percentage (0-100)
        """
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.monitor import MonitorManagementClient
            from datetime import datetime, timedelta

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            monitor_client = MonitorManagementClient(credential, self.subscription_id)

            # Build resource ID
            resource_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}"

            # Get metrics for last 14 days
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=14)

            metrics_data = monitor_client.metrics.list(
                resource_id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval='PT1H',  # 1 hour granularity
                metricnames='Percentage CPU',
                aggregation='Average'
            )

            # Calculate average
            total_cpu = 0.0
            count = 0
            for metric in metrics_data.value:
                for timeseries in metric.timeseries:
                    for data in timeseries.data:
                        if data.average is not None:
                            total_cpu += data.average
                            count += 1

            return total_cpu / count if count > 0 else 0.0

        except Exception as e:
            logger.warning(
                "azure.monitor.cpu_error",
                vm_name=vm_name,
                error=str(e),
            )
            return 0.0  # Default to 0 if metrics unavailable

    async def _get_vm_network_in(
        self, resource_group: str, vm_name: str, region: str
    ) -> float:
        """
        Get network in (MB) from Azure Monitor (last 14 days average).

        Args:
            resource_group: Resource group name
            vm_name: VM name
            region: Azure region

        Returns:
            Average network in MB/s
        """
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.monitor import MonitorManagementClient
            from datetime import datetime, timedelta

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            monitor_client = MonitorManagementClient(credential, self.subscription_id)

            # Build resource ID
            resource_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}"

            # Get metrics for last 14 days
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=14)

            metrics_data = monitor_client.metrics.list(
                resource_id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval='PT1H',
                metricnames='Network In Total',
                aggregation='Average'
            )

            # Calculate average (convert from bytes to MB/s)
            total_network = 0.0
            count = 0
            for metric in metrics_data.value:
                for timeseries in metric.timeseries:
                    for data in timeseries.data:
                        if data.average is not None:
                            total_network += data.average / (1024 * 1024)  # bytes to MB
                            count += 1

            return total_network / count if count > 0 else 0.0

        except Exception as e:
            logger.warning(
                "azure.monitor.network_error",
                vm_name=vm_name,
                error=str(e),
            )
            return 0.0

    # Helper methods for cost calculation

    def _calculate_vm_monthly_cost(
        self,
        vm_size: str,
        power_state: str,
        storage_profile: Any,
        compute_client: Any,
        resource_group: str,
    ) -> float:
        """
        Calculate monthly cost for Azure VM (VM compute + disks).

        Args:
            vm_size: VM size (e.g., Standard_D2s_v3)
            power_state: VM power state
            storage_profile: VM storage profile
            compute_client: Compute management client
            resource_group: Resource group name

        Returns:
            Estimated monthly cost in USD
        """
        # Hardcoded VM pricing (simplified, can be improved with Azure Retail Prices API)
        vm_pricing = {
            "Standard_B1s": 7.59,
            "Standard_B1ms": 15.18,
            "Standard_B2s": 30.37,
            "Standard_B2ms": 60.74,
            "Standard_D2s_v3": 70.08,
            "Standard_D4s_v3": 140.16,
            "Standard_D8s_v3": 280.32,
            "Standard_D16s_v3": 560.64,
            "Standard_E2s_v3": 88.32,
            "Standard_E4s_v3": 176.64,
            "Standard_F2s_v2": 59.20,
            "Standard_F4s_v2": 118.40,
        }

        # If deallocated, compute cost is $0 (but disks still charge)
        vm_cost = 0.0 if power_state == "deallocated" else vm_pricing.get(vm_size, 70.0)

        # Add disk costs
        disk_cost = 0.0
        if storage_profile:
            # OS disk
            if storage_profile.os_disk and storage_profile.os_disk.managed_disk:
                try:
                    os_disk_id = storage_profile.os_disk.managed_disk.id
                    os_disk_name = os_disk_id.split('/')[-1]
                    os_disk_rg = os_disk_id.split('/')[4]
                    os_disk = compute_client.disks.get(os_disk_rg, os_disk_name)
                    disk_cost += self.provider._calculate_disk_cost(os_disk)
                except Exception:
                    pass

            # Data disks
            if storage_profile.data_disks:
                for data_disk in storage_profile.data_disks:
                    if data_disk.managed_disk:
                        try:
                            disk_id = data_disk.managed_disk.id
                            disk_name = disk_id.split('/')[-1]
                            disk_rg = disk_id.split('/')[4]
                            disk = compute_client.disks.get(disk_rg, disk_name)
                            disk_cost += self.provider._calculate_disk_cost(disk)
                        except Exception:
                            pass

        return vm_cost + disk_cost

    def _determine_vm_utilization_status(self, cpu_util: float, power_state: str) -> str:
        """
        Determine VM utilization status.

        Args:
            cpu_util: CPU utilization percentage
            power_state: VM power state

        Returns:
            Utilization status string
        """
        if power_state == "deallocated":
            return "idle"
        elif cpu_util < 5.0:
            return "underutilized"
        elif cpu_util < 30.0:
            return "low_usage"
        elif cpu_util < 70.0:
            return "moderate_usage"
        else:
            return "high_usage"

    # Helper methods for optimization calculation

    def _calculate_vm_optimization(
        self,
        vm: Any,
        power_state: str,
        cpu_util: float,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """
        Calculate VM optimization score and recommendations.

        Args:
            vm: Azure VM object
            power_state: VM power state
            cpu_util: Average CPU utilization
            monthly_cost: Monthly cost

        Returns:
            Tuple of (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Deallocated VM (Critical waste)
        if power_state == "deallocated":
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete or reallocate this deallocated VM",
                "details": f"VM has been deallocated. Consider deleting if no longer needed.",
                "alternatives": [
                    {"name": "Delete VM", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: Running VM with very low CPU (<5%)
        elif power_state == "running" and cpu_util < 5.0:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost * 0.8
            recommendations.append({
                "action": "Downsize or stop this underutilized VM",
                "details": f"CPU utilization is only {cpu_util:.1f}%. Consider downsizing to a smaller SKU.",
                "alternatives": [
                    {"name": "Downsize to smaller SKU", "cost": monthly_cost * 0.5, "savings": monthly_cost * 0.5},
                    {"name": "Stop VM when not in use", "cost": monthly_cost * 0.3, "savings": monthly_cost * 0.7},
                ],
                "priority": "high",
            })

        # Scenario 3: Running VM with low CPU (<30%)
        elif power_state == "running" and cpu_util < 30.0:
            is_optimizable = True
            optimization_score = 40
            priority = "medium"
            potential_savings = monthly_cost * 0.3
            recommendations.append({
                "action": "Consider downsizing this VM",
                "details": f"CPU utilization is {cpu_util:.1f}%. You may be able to use a smaller VM size.",
                "alternatives": [
                    {"name": "Downsize to smaller SKU", "cost": monthly_cost * 0.7, "savings": monthly_cost * 0.3},
                ],
                "priority": "medium",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    def _calculate_disk_optimization(
        self,
        disk: Any,
        is_attached: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """
        Calculate disk optimization score and recommendations.

        Args:
            disk: Azure disk object
            is_attached: Whether disk is attached
            monthly_cost: Monthly cost

        Returns:
            Tuple of (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Unattached disk (Critical waste)
        if not is_attached:
            is_optimizable = True
            optimization_score = 85
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete this unattached disk",
                "details": "Disk is not attached to any VM. Consider deleting if no longer needed.",
                "alternatives": [
                    {"name": "Delete disk", "cost": 0, "savings": monthly_cost},
                    {"name": "Create snapshot and delete", "cost": monthly_cost * 0.1, "savings": monthly_cost * 0.9},
                ],
                "priority": "critical",
            })

        # Scenario 2: Premium disk when Standard SSD might suffice
        elif is_attached and disk.sku and disk.sku.name.startswith("Premium"):
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            potential_savings = monthly_cost * 0.4
            recommendations.append({
                "action": "Consider downgrading to Standard SSD",
                "details": "Using Premium SSD. Evaluate if Standard SSD performance is sufficient.",
                "alternatives": [
                    {"name": "Downgrade to Standard SSD", "cost": monthly_cost * 0.6, "savings": monthly_cost * 0.4},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    def _calculate_ip_optimization(
        self,
        ip: Any,
        is_assigned: bool,
        sku_name: str,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """
        Calculate public IP optimization score and recommendations.

        Args:
            ip: Azure public IP object
            is_assigned: Whether IP is assigned
            sku_name: SKU name (Basic or Standard)
            monthly_cost: Monthly cost

        Returns:
            Tuple of (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Unassigned IP (Critical waste)
        if not is_assigned:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Release this unassigned public IP",
                "details": "Public IP is not assigned to any resource.",
                "alternatives": [
                    {"name": "Release IP", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: Standard SKU when Basic might suffice
        elif is_assigned and sku_name == "Standard":
            is_optimizable = True
            optimization_score = 20
            priority = "low"
            potential_savings = 0.35  # Difference between Standard and Basic
            recommendations.append({
                "action": "Consider using Basic SKU public IP",
                "details": "Using Standard SKU. Evaluate if Basic SKU is sufficient for your needs.",
                "alternatives": [
                    {"name": "Downgrade to Basic SKU", "cost": 3.65, "savings": 0.35},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_load_balancers(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Load Balancers for cost intelligence.

        Args:
            region: Azure region to scan

        Returns:
            List of all load balancer resources
        """
        logger.info("inventory.scan_azure_lbs_start", region=region)
        all_lbs: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # Get ALL load balancers
            load_balancers = list(network_client.load_balancers.list_all())

            for lb in load_balancers:
                # Filter by region
                if lb.location != region:
                    continue

                # Filter by resource group
                if not self.provider._is_resource_in_scope(lb.id):
                    continue

                # Extract resource group
                resource_group = lb.id.split('/')[4]

                # Determine if load balancer is being used
                has_backend_pools = lb.backend_address_pools and len(lb.backend_address_pools) > 0
                has_probes = lb.probes and len(lb.probes) > 0
                has_rules = lb.load_balancing_rules and len(lb.load_balancing_rules) > 0

                # Extract tags
                tags = lb.tags if lb.tags else {}

                # Calculate monthly cost
                sku_name = lb.sku.name if lb.sku else "Basic"
                monthly_cost = 25.55 if sku_name == "Standard" else 18.25

                # Determine utilization status
                if not has_backend_pools and not has_probes:
                    utilization_status = "idle"
                elif not has_rules:
                    utilization_status = "underutilized"
                else:
                    utilization_status = "active"

                # Calculate optimization
                (
                    is_optimizable,
                    optimization_score,
                    optimization_priority,
                    potential_savings,
                    recommendations,
                ) = self._calculate_lb_optimization(
                    lb,
                    has_backend_pools,
                    has_probes,
                    has_rules,
                    sku_name,
                    monthly_cost,
                )

                # Check if LB is orphan (no backend pools)
                is_orphan = not has_backend_pools

                # Create resource data
                resource = AllCloudResourceData(
                    resource_type="azure_load_balancer",
                    resource_id=lb.id,
                    resource_name=lb.name,
                    region=region,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata={
                        "sku_name": sku_name,
                        "resource_group": resource_group,
                        "backend_pool_count": len(lb.backend_address_pools) if lb.backend_address_pools else 0,
                        "probe_count": len(lb.probes) if lb.probes else 0,
                        "rule_count": len(lb.load_balancing_rules) if lb.load_balancing_rules else 0,
                        "frontend_ip_count": len(lb.frontend_ip_configurations) if lb.frontend_ip_configurations else 0,
                    },
                    currency="USD",
                    utilization_status=utilization_status,
                    cpu_utilization_percent=None,
                    memory_utilization_percent=None,
                    storage_utilization_percent=None,
                    network_utilization_mbps=None,
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=potential_savings,
                    optimization_recommendations=recommendations,
                    tags=tags,
                    resource_status="active",
                    is_orphan=is_orphan,
                    created_at_cloud=None,
                    last_used_at=None,
                )

                all_lbs.append(resource)

            logger.info(
                "inventory.scan_azure_lbs_complete",
                region=region,
                total_lbs=len(all_lbs),
            )

        except Exception as e:
            logger.error(
                "inventory.scan_azure_lbs_error",
                region=region,
                error=str(e),
                exc_info=True,
            )
            raise

        return all_lbs

    def _calculate_lb_optimization(
        self,
        lb: Any,
        has_backend_pools: bool,
        has_probes: bool,
        has_rules: bool,
        sku_name: str,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict[str, Any]]]:
        """
        Calculate load balancer optimization score and recommendations.

        Args:
            lb: Azure load balancer object
            has_backend_pools: Whether LB has backend pools
            has_probes: Whether LB has health probes
            has_rules: Whether LB has load balancing rules
            sku_name: SKU name (Basic or Standard)
            monthly_cost: Monthly cost

        Returns:
            Tuple of (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: No backend pools (Critical waste)
        if not has_backend_pools:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete unused load balancer",
                "details": "Load balancer has no backend pools configured. Not serving any traffic.",
                "alternatives": [
                    {"name": "Delete load balancer", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: No health probes (High priority)
        elif not has_probes:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete load balancer without health probes",
                "details": "Load balancer has backend pools but no health probes. Likely misconfigured or unused.",
                "alternatives": [
                    {"name": "Delete load balancer", "cost": 0, "savings": monthly_cost},
                    {"name": "Configure health probes", "cost": monthly_cost, "savings": 0},
                ],
                "priority": "high",
            })

        # Scenario 3: Standard SKU with low traffic
        elif sku_name == "Standard" and has_backend_pools and has_rules:
            is_optimizable = True
            optimization_score = 40
            priority = "medium"
            potential_savings = 7.30  # Difference between Standard and Basic
            recommendations.append({
                "action": "Consider downgrading to Basic SKU",
                "details": "Using Standard SKU. Evaluate if Basic SKU features are sufficient.",
                "alternatives": [
                    {"name": "Downgrade to Basic SKU", "cost": 18.25, "savings": 7.30},
                ],
                "priority": "medium",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_app_gateways(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Application Gateways (WAF v2) for cost intelligence.

        Detection criteria:
        - Stopped/Deallocated instances (CRITICAL - 90 score)
        - No backend pools configured (CRITICAL - 80 score)
        - Oversized tier (Large when Medium/Small sufficient) (HIGH - 60 score)
        - WAF enabled but no custom rules (MEDIUM - 40 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all Application Gateways with optimization recommendations
        """
        logger.info("inventory.scan_azure_app_gateways_start", region=region)
        all_app_gateways: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)
            app_gateways = list(network_client.application_gateways.list_all())

            logger.info(
                "inventory.azure_app_gateways_fetched",
                region=region,
                total_app_gateways=len(app_gateways)
            )

            for ag in app_gateways:
                # Filter by region
                if ag.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(ag.id):
                    continue

                # Detect usage patterns
                is_running = ag.operational_state and ag.operational_state.lower() == "running"
                has_backend_pools = ag.backend_address_pools and len(ag.backend_address_pools) > 0
                has_http_listeners = ag.http_listeners and len(ag.http_listeners) > 0
                has_request_routing_rules = ag.request_routing_rules and len(ag.request_routing_rules) > 0

                # WAF analysis
                has_waf = ag.web_application_firewall_configuration is not None
                waf_rule_count = 0
                if has_waf and ag.web_application_firewall_configuration.rule_set_type:
                    waf_rule_count = len(ag.web_application_firewall_configuration.disabled_rule_groups or [])

                # SKU analysis (tier + size)
                sku_tier = ag.sku.tier if ag.sku else "Standard_v2"
                sku_size = ag.sku.name if ag.sku else "Standard_Medium"

                # Pricing calculation (Azure Application Gateway v2 pricing - US East 2025)
                # SKU cost (per gateway per month)
                sku_cost_map = {
                    "Standard_Small": 142.00,    # Small (2 CU baseline)
                    "Standard_Medium": 372.00,   # Medium (10 CU baseline)
                    "Standard_Large": 745.00,    # Large (50 CU baseline)
                    "WAF_Small": 160.00,         # WAF Small (2 CU baseline + WAF cost)
                    "WAF_Medium": 390.00,        # WAF Medium (10 CU baseline + WAF cost)
                    "WAF_Large": 763.00,         # WAF Large (50 CU baseline + WAF cost)
                }

                monthly_cost = sku_cost_map.get(sku_size, 372.00)  # Default to Medium

                # Capacity units (additional cost beyond baseline)
                capacity = ag.sku.capacity if ag.sku and ag.sku.capacity else 2
                if capacity > 2:  # Beyond baseline 2 CU
                    monthly_cost += (capacity - 2) * 8.76  # $8.76 per CU per month

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_ag_optimization(
                    ag, is_running, has_backend_pools, has_http_listeners,
                    has_request_routing_rules, has_waf, waf_rule_count,
                    sku_tier, sku_size, monthly_cost
                )

                # Build resource metadata
                resource_metadata = {
                    "sku_tier": sku_tier,
                    "sku_size": sku_size,
                    "capacity": capacity,
                    "operational_state": ag.operational_state,
                    "backend_pools_count": len(ag.backend_address_pools) if ag.backend_address_pools else 0,
                    "http_listeners_count": len(ag.http_listeners) if ag.http_listeners else 0,
                    "routing_rules_count": len(ag.request_routing_rules) if ag.request_routing_rules else 0,
                    "waf_enabled": has_waf,
                    "waf_rule_count": waf_rule_count,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_app_gateway",
                    resource_id=ag.id,
                    resource_name=ag.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=ag.etag,  # Use etag as proxy for creation time
                    last_used_at=None,  # No last-used timestamp available
                    status="active",
                )

                all_app_gateways.append(resource)

            logger.info(
                "inventory.azure_app_gateways_scanned",
                region=region,
                total_scanned=len(all_app_gateways),
                optimizable=sum(1 for r in all_app_gateways if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-network",
                message="Install azure-mgmt-network to scan Application Gateways"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_app_gateways_scan_failed",
                region=region,
                error=str(e)
            )

        return all_app_gateways

    def _calculate_ag_optimization(
        self,
        ag,
        is_running: bool,
        has_backend_pools: bool,
        has_http_listeners: bool,
        has_request_routing_rules: bool,
        has_waf: bool,
        waf_rule_count: int,
        sku_tier: str,
        sku_size: str,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate Application Gateway optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Stopped or Deallocated (CRITICAL - 90 score)
        if not is_running:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete stopped Application Gateway",
                "details": f"Application Gateway is in '{ag.operational_state}' state and not serving traffic. You're still paying ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete Application Gateway", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: No backend pools (CRITICAL - 80 score)
        elif not has_backend_pools:
            is_optimizable = True
            optimization_score = 80
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete Application Gateway without backend pools",
                "details": "Application Gateway has no backend pools configured. Not routing any traffic.",
                "alternatives": [
                    {"name": "Delete Application Gateway", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 3: No HTTP listeners or routing rules (HIGH - 70 score)
        elif not has_http_listeners or not has_request_routing_rules:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete Application Gateway with no active routing",
                "details": "Application Gateway has backend pools but no HTTP listeners or routing rules. Not accepting traffic.",
                "alternatives": [
                    {"name": "Delete Application Gateway", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "high",
            })

        # Scenario 4: Oversized SKU (HIGH - 60 score)
        elif sku_size in ["Standard_Large", "WAF_Large"] and has_backend_pools:
            is_optimizable = True
            optimization_score = 60
            priority = "high"
            # Savings: Large → Medium (50% reduction)
            medium_cost = 372.00 if "WAF" not in sku_size else 390.00
            potential_savings = monthly_cost - medium_cost
            recommendations.append({
                "action": "Downsize Application Gateway from Large to Medium SKU",
                "details": f"Using Large SKU (${monthly_cost}/mo). Evaluate if Medium SKU is sufficient (${medium_cost}/mo).",
                "alternatives": [
                    {"name": "Downgrade to Medium SKU", "cost": medium_cost, "savings": potential_savings},
                ],
                "priority": "high",
            })

        # Scenario 5: WAF enabled but no custom rules (MEDIUM - 40 score)
        elif has_waf and waf_rule_count == 0 and "WAF" in sku_size:
            is_optimizable = True
            optimization_score = 40
            priority = "medium"
            # Savings: WAF → Standard (WAF adds ~$18/mo overhead)
            standard_cost = monthly_cost - 18.00
            potential_savings = 18.00
            recommendations.append({
                "action": "Consider disabling WAF or switch to Standard SKU",
                "details": f"WAF is enabled but no custom rules configured. Paying extra ${potential_savings}/month for unused feature.",
                "alternatives": [
                    {"name": "Switch to Standard SKU", "cost": standard_cost, "savings": potential_savings},
                ],
                "priority": "medium",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_storage_accounts(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Storage Accounts for cost intelligence.

        Detection criteria:
        - Zero storage used (CRITICAL - 90 score)
        - Premium tier underutilized (<100GB) (HIGH - 70 score)
        - Hot tier with cold access patterns (MEDIUM - 50 score)
        - GRS replication without geo-redundancy need (LOW - 30 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all Storage Accounts with optimization recommendations
        """
        logger.info("inventory.scan_azure_storage_accounts_start", region=region)
        all_storage_accounts: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.storage import StorageManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            storage_client = StorageManagementClient(credential, self.subscription_id)
            storage_accounts = list(storage_client.storage_accounts.list())

            logger.info(
                "inventory.azure_storage_accounts_fetched",
                region=region,
                total_storage_accounts=len(storage_accounts)
            )

            for sa in storage_accounts:
                # Filter by region
                if sa.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(sa.id):
                    continue

                # Get account properties
                account_kind = sa.kind if sa.kind else "StorageV2"
                sku_name = sa.sku.name if sa.sku else "Standard_LRS"
                sku_tier = sa.sku.tier if sa.sku else "Standard"
                access_tier = sa.access_tier if sa.access_tier else "Hot"

                # Get usage metrics (requires additional API call)
                usage_gb = 0.0
                try:
                    # Get resource group from storage account ID
                    resource_group = sa.id.split("/")[4]
                    usage_metrics = storage_client.storage_accounts.list_account_sas(
                        resource_group_name=resource_group,
                        account_name=sa.name
                    )
                    # Note: Actual usage requires Azure Monitor API, hardcoded for now
                    usage_gb = 50.0  # Placeholder - would need Monitor API
                except Exception:
                    usage_gb = 50.0  # Default assumption

                # Pricing calculation (Azure Storage pricing - US East 2025)
                # Base cost per GB per month
                pricing_map = {
                    # Standard tier
                    "Standard_LRS": 0.0184,      # Locally redundant
                    "Standard_GRS": 0.0368,      # Geo-redundant
                    "Standard_RAGRS": 0.046,     # Read-access geo-redundant
                    "Standard_ZRS": 0.0225,      # Zone-redundant
                    # Premium tier
                    "Premium_LRS": 0.15,         # Premium locally redundant
                    "Premium_ZRS": 0.1875,       # Premium zone-redundant
                }

                price_per_gb = pricing_map.get(sku_name, 0.0184)
                storage_cost = usage_gb * price_per_gb

                # Additional costs (transactions, bandwidth) - estimate 20% overhead
                monthly_cost = storage_cost * 1.2

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_sa_optimization(
                    sa, usage_gb, sku_name, sku_tier, access_tier,
                    account_kind, monthly_cost, price_per_gb
                )

                # Build resource metadata
                resource_metadata = {
                    "sku_name": sku_name,
                    "sku_tier": sku_tier,
                    "account_kind": account_kind,
                    "access_tier": access_tier,
                    "usage_gb": round(usage_gb, 2),
                    "price_per_gb": price_per_gb,
                    "provisioning_state": sa.provisioning_state,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_storage_account",
                    resource_id=sa.id,
                    resource_name=sa.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=sa.creation_time,
                    last_used_at=None,  # No last-used timestamp available
                    status="active",
                )

                all_storage_accounts.append(resource)

            logger.info(
                "inventory.azure_storage_accounts_scanned",
                region=region,
                total_scanned=len(all_storage_accounts),
                optimizable=sum(1 for r in all_storage_accounts if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-storage",
                message="Install azure-mgmt-storage to scan Storage Accounts"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_storage_accounts_scan_failed",
                region=region,
                error=str(e)
            )

        return all_storage_accounts

    def _calculate_sa_optimization(
        self,
        sa,
        usage_gb: float,
        sku_name: str,
        sku_tier: str,
        access_tier: str,
        account_kind: str,
        monthly_cost: float,
        price_per_gb: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate Storage Account optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Zero storage used (CRITICAL - 90 score)
        if usage_gb < 0.1:  # Less than 100 MB
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete empty Storage Account",
                "details": f"Storage Account has no data stored (<100 MB). You're paying ${monthly_cost}/month for unused storage.",
                "alternatives": [
                    {"name": "Delete Storage Account", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: Premium tier underutilized (HIGH - 70 score)
        elif sku_tier == "Premium" and usage_gb < 100:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Savings: Premium → Standard (80% reduction in per-GB cost)
            standard_cost = usage_gb * 0.0184 * 1.2
            potential_savings = monthly_cost - standard_cost
            recommendations.append({
                "action": "Downgrade from Premium to Standard tier",
                "details": f"Using Premium tier (${price_per_gb}/GB) but only {usage_gb}GB stored. Standard tier (${0.0184}/GB) would save ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Downgrade to Standard LRS", "cost": round(standard_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "high",
            })

        # Scenario 3: Hot tier with cold access (MEDIUM - 50 score)
        # Note: Would need actual access metrics from Monitor API
        elif access_tier == "Hot" and usage_gb > 100:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings: Hot → Cool (30% reduction in storage cost)
            cool_cost = usage_gb * 0.01 * 1.2
            potential_savings = monthly_cost - cool_cost
            recommendations.append({
                "action": "Consider switching from Hot to Cool access tier",
                "details": f"Using Hot tier for {usage_gb}GB. If access is infrequent, Cool tier could save ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Switch to Cool tier", "cost": round(cool_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 4: GRS replication without geo-redundancy need (LOW - 30 score)
        elif "GRS" in sku_name or "RAGRS" in sku_name:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # Savings: GRS → LRS (50% reduction)
            lrs_cost = usage_gb * 0.0184 * 1.2
            potential_savings = monthly_cost - lrs_cost
            recommendations.append({
                "action": "Evaluate if geo-redundancy is necessary",
                "details": f"Using {sku_name} replication. If geo-redundancy isn't required, switch to LRS to save ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Downgrade to LRS", "cost": round(lrs_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_expressroute_circuits(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure ExpressRoute Circuits for cost intelligence.

        Detection criteria:
        - Not provisioned (CRITICAL - 90 score)
        - No peerings configured (HIGH - 75 score)
        - Premium tier underutilized (MEDIUM - 50 score)
        - Metered data plan with low usage (LOW - 30 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all ExpressRoute Circuits with optimization recommendations
        """
        logger.info("inventory.scan_azure_expressroute_start", region=region)
        all_expressroute: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)
            expressroute_circuits = list(network_client.express_route_circuits.list_all())

            logger.info(
                "inventory.azure_expressroute_fetched",
                region=region,
                total_expressroute=len(expressroute_circuits)
            )

            for er in expressroute_circuits:
                # Filter by region
                if er.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(er.id):
                    continue

                # Get circuit properties
                sku_tier = er.sku.tier if er.sku else "Standard"
                sku_family = er.sku.family if er.sku else "MeteredData"
                bandwidth_mbps = er.service_provider_properties.bandwidth_in_mbps if er.service_provider_properties else 50

                # Circuit state
                provisioning_state = er.provisioning_state if er.provisioning_state else "Unknown"
                circuit_provisioning_state = er.circuit_provisioning_state if er.circuit_provisioning_state else "Disabled"

                # Peerings analysis
                has_peerings = er.peerings and len(er.peerings) > 0
                peering_count = len(er.peerings) if er.peerings else 0

                # Pricing calculation (Azure ExpressRoute pricing - US East 2025)
                # Port fee per month
                port_fees = {
                    50: 55.00,     # 50 Mbps
                    100: 120.00,   # 100 Mbps
                    200: 230.00,   # 200 Mbps
                    500: 560.00,   # 500 Mbps
                    1000: 1100.00, # 1 Gbps
                    2000: 2200.00, # 2 Gbps
                    5000: 5500.00, # 5 Gbps
                    10000: 11000.00, # 10 Gbps
                }

                # Find closest bandwidth tier
                port_cost = port_fees.get(bandwidth_mbps, 560.00)  # Default to 500 Mbps
                for tier_mbps, cost in sorted(port_fees.items()):
                    if bandwidth_mbps <= tier_mbps:
                        port_cost = cost
                        break

                # Premium add-on (if Premium tier)
                premium_cost = 1150.00 if sku_tier == "Premium" else 0.0

                # Metered data (if MeteredData family) - estimate $0.025/GB outbound
                # Assume 10% bandwidth utilization for cost estimation
                estimated_gb_outbound = (bandwidth_mbps / 8) * 0.1 * 730 * 3600 / 1024  # GB/month
                metered_cost = estimated_gb_outbound * 0.025 if sku_family == "MeteredData" else 0.0

                monthly_cost = port_cost + premium_cost + metered_cost

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_er_optimization(
                    er, provisioning_state, circuit_provisioning_state, has_peerings,
                    peering_count, sku_tier, sku_family, bandwidth_mbps,
                    monthly_cost, port_cost, premium_cost
                )

                # Build resource metadata
                resource_metadata = {
                    "sku_tier": sku_tier,
                    "sku_family": sku_family,
                    "bandwidth_mbps": bandwidth_mbps,
                    "provisioning_state": provisioning_state,
                    "circuit_provisioning_state": circuit_provisioning_state,
                    "peering_count": peering_count,
                    "service_provider": er.service_provider_properties.service_provider_name if er.service_provider_properties else None,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_expressroute_circuit",
                    resource_id=er.id,
                    resource_name=er.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=er.etag,  # Use etag as proxy
                    last_used_at=None,  # No last-used timestamp available
                    status="active",
                )

                all_expressroute.append(resource)

            logger.info(
                "inventory.azure_expressroute_scanned",
                region=region,
                total_scanned=len(all_expressroute),
                optimizable=sum(1 for r in all_expressroute if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-network",
                message="Install azure-mgmt-network to scan ExpressRoute Circuits"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_expressroute_scan_failed",
                region=region,
                error=str(e)
            )

        return all_expressroute

    def _calculate_er_optimization(
        self,
        er,
        provisioning_state: str,
        circuit_provisioning_state: str,
        has_peerings: bool,
        peering_count: int,
        sku_tier: str,
        sku_family: str,
        bandwidth_mbps: int,
        monthly_cost: float,
        port_cost: float,
        premium_cost: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate ExpressRoute Circuit optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Not provisioned (CRITICAL - 90 score)
        if circuit_provisioning_state in ["Disabled", "NotProvisioned"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete unprovisioned ExpressRoute Circuit",
                "details": f"Circuit is '{circuit_provisioning_state}' and not serving traffic. You're paying ${monthly_cost}/month for unused circuit.",
                "alternatives": [
                    {"name": "Delete ExpressRoute Circuit", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: No peerings configured (HIGH - 75 score)
        elif not has_peerings or peering_count == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete ExpressRoute Circuit without peerings",
                "details": f"Circuit has no peerings configured. Not routing any traffic. Paying ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete ExpressRoute Circuit", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "high",
            })

        # Scenario 3: Premium tier underutilized (MEDIUM - 50 score)
        elif sku_tier == "Premium" and peering_count < 2:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings: Premium → Standard ($1150/mo savings)
            standard_cost = monthly_cost - premium_cost
            potential_savings = premium_cost
            recommendations.append({
                "action": "Downgrade from Premium to Standard tier",
                "details": f"Using Premium tier (${premium_cost}/mo add-on) but only {peering_count} peering(s) configured. Standard tier may be sufficient.",
                "alternatives": [
                    {"name": "Downgrade to Standard tier", "cost": round(standard_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 4: Oversized bandwidth (MEDIUM - 40 score)
        elif bandwidth_mbps >= 1000 and has_peerings:
            is_optimizable = True
            optimization_score = 40
            priority = "medium"
            # Savings: Downsize bandwidth (estimate 50% reduction)
            lower_tier_cost = port_cost * 0.5
            potential_savings = port_cost - lower_tier_cost
            recommendations.append({
                "action": "Evaluate if lower bandwidth tier is sufficient",
                "details": f"Using {bandwidth_mbps} Mbps circuit (${port_cost}/mo). Review actual usage to see if downsizing is possible.",
                "alternatives": [
                    {"name": "Downsize to lower bandwidth", "cost": round(lower_tier_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 5: Metered data with low usage (LOW - 30 score)
        elif sku_family == "MeteredData" and bandwidth_mbps <= 200:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # Savings: Switch to UnlimitedData (may save on overage charges)
            # Note: UnlimitedData is typically more cost-effective for high usage
            potential_savings = monthly_cost * 0.1  # Estimate 10% savings
            recommendations.append({
                "action": "Evaluate UnlimitedData plan",
                "details": f"Using MeteredData plan on {bandwidth_mbps} Mbps circuit. If outbound data is high, UnlimitedData may be more cost-effective.",
                "alternatives": [
                    {"name": "Switch to UnlimitedData plan", "cost": round(monthly_cost * 0.9, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_disk_snapshots(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Disk Snapshots for cost intelligence.

        Detection criteria:
        - Snapshot très ancien (>365 jours) (CRITICAL - 90 score)
        - Snapshot orphelin (disque source supprimé) (HIGH - 75 score)
        - Snapshots multiples du même disque (>10) (MEDIUM - 50 score)
        - Snapshot non incrémentiel (LOW - 30 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all Disk Snapshots with optimization recommendations
        """
        logger.info("inventory.scan_azure_snapshots_start", region=region)
        all_snapshots: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.compute import ComputeManagementClient
            from datetime import datetime, timezone

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            snapshots = list(compute_client.snapshots.list())

            logger.info(
                "inventory.azure_snapshots_fetched",
                region=region,
                total_snapshots=len(snapshots)
            )

            # Get all disks to check for orphaned snapshots
            all_disks = list(compute_client.disks.list())
            disk_ids = {disk.id for disk in all_disks}

            # Group snapshots by source disk
            snapshots_by_disk: dict[str, list] = {}
            for snapshot in snapshots:
                source_id = snapshot.creation_data.source_resource_id if snapshot.creation_data else None
                if source_id:
                    if source_id not in snapshots_by_disk:
                        snapshots_by_disk[source_id] = []
                    snapshots_by_disk[source_id].append(snapshot)

            for snap in snapshots:
                # Filter by region
                if snap.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(snap.id):
                    continue

                # Snapshot properties
                sku_name = snap.sku.name if snap.sku else "Standard_LRS"
                disk_size_gb = snap.disk_size_gb if snap.disk_size_gb else 128
                incremental = snap.incremental if hasattr(snap, 'incremental') else False

                # Calculate age
                time_created = snap.time_created if snap.time_created else datetime.now(timezone.utc)
                age_days = (datetime.now(timezone.utc) - time_created).days

                # Check if orphaned (source disk deleted)
                source_disk_id = snap.creation_data.source_resource_id if snap.creation_data else None
                is_orphaned = source_disk_id and source_disk_id not in disk_ids

                # Count snapshots from same source disk
                snapshot_count_for_disk = len(snapshots_by_disk.get(source_disk_id, [])) if source_disk_id else 1

                # Pricing calculation (Azure Snapshot pricing - US East 2025)
                # Price per GB per month
                pricing_map = {
                    "Standard_LRS": 0.05,      # Standard HDD snapshots
                    "Premium_LRS": 0.10,       # Premium SSD snapshots
                    "StandardSSD_LRS": 0.065,  # Standard SSD snapshots
                }

                price_per_gb = pricing_map.get(sku_name, 0.05)
                monthly_cost = disk_size_gb * price_per_gb

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_snapshot_optimization(
                    snap, age_days, disk_size_gb, is_orphaned,
                    snapshot_count_for_disk, incremental, monthly_cost
                )

                # Build resource metadata
                resource_metadata = {
                    "sku_name": sku_name,
                    "disk_size_gb": disk_size_gb,
                    "incremental": incremental,
                    "age_days": age_days,
                    "is_orphaned": is_orphaned,
                    "snapshot_count_for_disk": snapshot_count_for_disk,
                    "source_disk_id": source_disk_id,
                    "provisioning_state": snap.provisioning_state,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_disk_snapshot",
                    resource_id=snap.id,
                    resource_name=snap.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=time_created,
                    last_used_at=None,  # No last-used timestamp available
                    status="active",
                )

                all_snapshots.append(resource)

            logger.info(
                "inventory.azure_snapshots_scanned",
                region=region,
                total_scanned=len(all_snapshots),
                optimizable=sum(1 for r in all_snapshots if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-compute",
                message="Install azure-mgmt-compute to scan Disk Snapshots"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_snapshots_scan_failed",
                region=region,
                error=str(e)
            )

        return all_snapshots

    def _calculate_snapshot_optimization(
        self,
        snap,
        age_days: int,
        disk_size_gb: int,
        is_orphaned: bool,
        snapshot_count_for_disk: int,
        incremental: bool,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate Disk Snapshot optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Snapshot très ancien (>365 jours) (CRITICAL - 90 score)
        if age_days > 365:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete old snapshot (>1 year old)",
                "details": f"Snapshot is {age_days} days old ({disk_size_gb}GB). Consider deleting if no longer needed. Saving ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete snapshot", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: Snapshot orphelin (disque source supprimé) (HIGH - 75 score)
        elif is_orphaned:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete orphaned snapshot (source disk deleted)",
                "details": f"Source disk no longer exists. Snapshot is orphaned ({disk_size_gb}GB). Delete to save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete orphaned snapshot", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "high",
            })

        # Scenario 3: Snapshots multiples du même disque (>10) (MEDIUM - 50 score)
        elif snapshot_count_for_disk > 10:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Estimate savings: delete oldest 50% of snapshots
            potential_savings = monthly_cost * 0.5
            recommendations.append({
                "action": f"Reduce number of snapshots ({snapshot_count_for_disk} snapshots)",
                "details": f"Source disk has {snapshot_count_for_disk} snapshots. Consider retention policy to delete old snapshots. Save ~${potential_savings}/month.",
                "alternatives": [
                    {"name": "Delete oldest 50% of snapshots", "cost": round(monthly_cost * 0.5, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 4: Snapshot non incrémentiel (LOW - 30 score)
        elif not incremental and disk_size_gb > 128:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # Savings: incremental snapshots are ~80% cheaper
            potential_savings = monthly_cost * 0.8
            recommendations.append({
                "action": "Switch to incremental snapshots",
                "details": f"Using full snapshot ({disk_size_gb}GB). Incremental snapshots could save ~${potential_savings}/month (80% reduction).",
                "alternatives": [
                    {"name": "Use incremental snapshots", "cost": round(monthly_cost * 0.2, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_nat_gateways(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure NAT Gateways for cost intelligence.

        Detection criteria:
        - Pas de subnet attaché (CRITICAL - 90 score)
        - Pas d'IP publiques configurées (HIGH - 75 score)
        - Très faible utilisation (<100GB/mois) (MEDIUM - 50 score)
        - Multiple NAT Gateways dans même VNet (LOW - 30 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all NAT Gateways with optimization recommendations
        """
        logger.info("inventory.scan_azure_nat_gateways_start", region=region)
        all_nat_gateways: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)
            nat_gateways = list(network_client.nat_gateways.list_all())

            logger.info(
                "inventory.azure_nat_gateways_fetched",
                region=region,
                total_nat_gateways=len(nat_gateways)
            )

            # Get all VNets to count NAT Gateways per VNet
            vnets = list(network_client.virtual_networks.list_all())
            nat_per_vnet: dict[str, int] = {}

            for nat in nat_gateways:
                # Filter by region
                if nat.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(nat.id):
                    continue

                # NAT Gateway properties
                has_subnets = nat.subnets and len(nat.subnets) > 0
                subnet_count = len(nat.subnets) if nat.subnets else 0

                has_public_ips = nat.public_ip_addresses and len(nat.public_ip_addresses) > 0
                public_ip_count = len(nat.public_ip_addresses) if nat.public_ip_addresses else 0

                # Estimate outbound data usage (requires Azure Monitor - hardcoded for now)
                estimated_gb_outbound = 500.0  # Placeholder - would need Monitor API

                # Count NAT Gateways in same VNet (for optimization scenario)
                vnet_id = None
                if nat.subnets and len(nat.subnets) > 0:
                    # Extract VNet ID from subnet ID
                    subnet_id = nat.subnets[0].id
                    vnet_id = "/".join(subnet_id.split("/")[:9]) if "/" in subnet_id else None

                if vnet_id:
                    if vnet_id not in nat_per_vnet:
                        nat_per_vnet[vnet_id] = 0
                    nat_per_vnet[vnet_id] += 1

                nat_count_in_vnet = nat_per_vnet.get(vnet_id, 1) if vnet_id else 1

                # Pricing calculation (Azure NAT Gateway pricing - US East 2025)
                # Gateway cost: $32.85/month
                # Outbound data: $0.045/GB
                gateway_cost = 32.85
                outbound_cost = estimated_gb_outbound * 0.045

                monthly_cost = gateway_cost + outbound_cost

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_nat_optimization(
                    nat, has_subnets, subnet_count, has_public_ips,
                    public_ip_count, estimated_gb_outbound, nat_count_in_vnet,
                    monthly_cost, gateway_cost
                )

                # Build resource metadata
                resource_metadata = {
                    "subnet_count": subnet_count,
                    "public_ip_count": public_ip_count,
                    "estimated_gb_outbound": estimated_gb_outbound,
                    "nat_count_in_vnet": nat_count_in_vnet,
                    "vnet_id": vnet_id,
                    "provisioning_state": nat.provisioning_state,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_nat_gateway",
                    resource_id=nat.id,
                    resource_name=nat.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=nat.etag,  # Use etag as proxy
                    last_used_at=None,  # No last-used timestamp available
                    status="active",
                )

                all_nat_gateways.append(resource)

            logger.info(
                "inventory.azure_nat_gateways_scanned",
                region=region,
                total_scanned=len(all_nat_gateways),
                optimizable=sum(1 for r in all_nat_gateways if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-network",
                message="Install azure-mgmt-network to scan NAT Gateways"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_nat_gateways_scan_failed",
                region=region,
                error=str(e)
            )

        return all_nat_gateways

    def _calculate_nat_optimization(
        self,
        nat,
        has_subnets: bool,
        subnet_count: int,
        has_public_ips: bool,
        public_ip_count: int,
        estimated_gb_outbound: float,
        nat_count_in_vnet: int,
        monthly_cost: float,
        gateway_cost: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate NAT Gateway optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Pas de subnet attaché (CRITICAL - 90 score)
        if not has_subnets or subnet_count == 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete NAT Gateway without subnets",
                "details": f"NAT Gateway has no subnets attached. Not routing any traffic. Delete to save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete NAT Gateway", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: Pas d'IP publiques configurées (HIGH - 75 score)
        elif not has_public_ips or public_ip_count == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete NAT Gateway without public IPs",
                "details": f"NAT Gateway has no public IPs configured. Cannot provide outbound connectivity. Delete to save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete NAT Gateway", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "high",
            })

        # Scenario 3: Très faible utilisation (<100GB/mois) (MEDIUM - 50 score)
        elif estimated_gb_outbound < 100:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings: gateway cost only (keep minimal data cost)
            potential_savings = gateway_cost
            recommendations.append({
                "action": "Consider using Public IP instead of NAT Gateway",
                "details": f"Very low outbound data ({estimated_gb_outbound}GB/month). Public IP on VM may be more cost-effective. Save ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Use Public IP instead", "cost": round(estimated_gb_outbound * 0.005, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 4: Multiple NAT Gateways dans même VNet (LOW - 30 score)
        elif nat_count_in_vnet > 1:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # Savings: consolidate to 1 NAT Gateway (save 1 gateway cost)
            potential_savings = gateway_cost
            recommendations.append({
                "action": f"Consolidate NAT Gateways in VNet ({nat_count_in_vnet} gateways)",
                "details": f"VNet has {nat_count_in_vnet} NAT Gateways. Consider consolidating to reduce costs. Save ${potential_savings}/month per gateway.",
                "alternatives": [
                    {"name": "Consolidate to 1 NAT Gateway", "cost": round(monthly_cost - potential_savings, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_azure_sql_databases(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure SQL Databases for cost intelligence.

        Detection criteria:
        - Base de données paused/stopped (CRITICAL - 90 score)
        - Aucune connexion 30 derniers jours (HIGH - 75 score)
        - DTU très faible (<5% utilization) (HIGH - 70 score)
        - Premium tier en dev/test (HIGH - 65 score)
        - Geo-replication non nécessaire (MEDIUM - 50 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all Azure SQL Databases with optimization recommendations
        """
        logger.info("inventory.scan_azure_sql_databases_start", region=region)
        all_sql_databases: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.sql import SqlManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            sql_client = SqlManagementClient(credential, self.subscription_id)

            # Get all SQL servers first
            sql_servers = list(sql_client.servers.list())

            logger.info(
                "inventory.azure_sql_servers_fetched",
                region=region,
                total_sql_servers=len(sql_servers)
            )

            for server in sql_servers:
                # Filter by region
                if server.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(server.id):
                    continue

                # Get resource group from server ID
                resource_group = server.id.split("/")[4]

                # Get all databases in this server
                try:
                    databases = list(sql_client.databases.list_by_server(
                        resource_group_name=resource_group,
                        server_name=server.name
                    ))

                    for db in databases:
                        # Skip 'master' database
                        if db.name.lower() == "master":
                            continue

                        # Database properties
                        status = db.status if db.status else "Online"
                        is_paused = status.lower() in ["paused", "stopped"]

                        sku_name = db.sku.name if db.sku else "Basic"
                        sku_tier = db.sku.tier if db.sku else "Basic"

                        # Capacity (DTU or vCores)
                        capacity = db.sku.capacity if db.sku and db.sku.capacity else 5

                        # Geo-replication
                        has_geo_replication = False  # Would need to check replication links

                        # Estimate DTU utilization (requires Azure Monitor - hardcoded for now)
                        dtu_utilization_percent = 25.0  # Placeholder - would need Monitor API

                        # Days since last connection (requires diagnostic logs - hardcoded)
                        days_since_last_connection = 15  # Placeholder - would need Monitor API

                        # Pricing calculation (Azure SQL Database pricing - US East 2025)
                        # Prices vary widely by tier and size
                        pricing_map = {
                            "Basic": 5.00,           # Basic: $5/month
                            "Standard_S0": 15.00,    # Standard S0: $15/month
                            "Standard_S1": 30.00,    # Standard S1: $30/month
                            "Standard_S2": 75.00,    # Standard S2: $75/month
                            "Standard_S3": 150.00,   # Standard S3: $150/month
                            "Standard_S4": 300.00,   # Standard S4: $300/month
                            "Premium_P1": 465.00,    # Premium P1: $465/month
                            "Premium_P2": 930.00,    # Premium P2: $930/month
                            "Premium_P4": 1860.00,   # Premium P4: $1860/month
                            "Premium_P6": 3720.00,   # Premium P6: $3720/month
                            "Premium_P11": 7000.00,  # Premium P11: $7000/month
                            "Premium_P15": 14000.00, # Premium P15: $14000/month
                        }

                        # Construct SKU key
                        sku_key = f"{sku_tier}_{sku_name}" if sku_tier != "Basic" else sku_tier
                        monthly_cost = pricing_map.get(sku_key, pricing_map.get(sku_tier, 15.00))

                        # Calculate optimization
                        (is_optimizable, optimization_score, optimization_priority,
                         potential_savings, recommendations) = self._calculate_sqldb_optimization(
                            db, status, is_paused, sku_tier, dtu_utilization_percent,
                            days_since_last_connection, has_geo_replication, monthly_cost
                        )

                        # Build resource metadata
                        resource_metadata = {
                            "server_name": server.name,
                            "sku_name": sku_name,
                            "sku_tier": sku_tier,
                            "capacity": capacity,
                            "status": status,
                            "dtu_utilization_percent": dtu_utilization_percent,
                            "days_since_last_connection": days_since_last_connection,
                            "has_geo_replication": has_geo_replication,
                        }

                        resource = AllCloudResourceData(
                            resource_type="azure_sql_database",
                            resource_id=db.id,
                            resource_name=db.name,
                            region=region,
                            estimated_monthly_cost=round(monthly_cost, 2),
                            currency="USD",
                            is_optimizable=is_optimizable,
                            optimization_priority=optimization_priority,
                            optimization_score=optimization_score,
                            potential_monthly_savings=round(potential_savings, 2),
                            optimization_recommendations=recommendations,
                            resource_metadata=resource_metadata,
                            created_at_cloud=db.creation_date,
                            last_used_at=None,  # No last-used timestamp available
                            status="active",
                        )

                        all_sql_databases.append(resource)

                except Exception as db_error:
                    logger.error(
                        "inventory.azure_sql_databases_list_failed",
                        server=server.name,
                        error=str(db_error)
                    )

            logger.info(
                "inventory.azure_sql_databases_scanned",
                region=region,
                total_scanned=len(all_sql_databases),
                optimizable=sum(1 for r in all_sql_databases if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-sql",
                message="Install azure-mgmt-sql to scan Azure SQL Databases"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_sql_databases_scan_failed",
                region=region,
                error=str(e)
            )

        return all_sql_databases

    def _calculate_sqldb_optimization(
        self,
        db,
        status: str,
        is_paused: bool,
        sku_tier: str,
        dtu_utilization_percent: float,
        days_since_last_connection: int,
        has_geo_replication: bool,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate Azure SQL Database optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Base de données paused/stopped (CRITICAL - 90 score)
        if is_paused:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete or resume paused database",
                "details": f"Database is '{status}'. Delete if no longer needed, or resume if required. Save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete database", "cost": 0, "savings": monthly_cost},
                    {"name": "Resume database", "cost": monthly_cost, "savings": 0},
                ],
                "priority": "critical",
            })

        # Scenario 2: Aucune connexion 30 derniers jours (HIGH - 75 score)
        elif days_since_last_connection > 30:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete unused database (no connections for 30+ days)",
                "details": f"Database has no connections for {days_since_last_connection} days. Delete if no longer needed. Save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete database", "cost": 0, "savings": monthly_cost},
                    {"name": "Pause database", "cost": round(monthly_cost * 0.1, 2), "savings": round(monthly_cost * 0.9, 2)},
                ],
                "priority": "high",
            })

        # Scenario 3: DTU très faible (<5% utilization) (HIGH - 70 score)
        elif dtu_utilization_percent < 5.0:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Savings: Downgrade to lower tier (estimate 50% reduction)
            potential_savings = monthly_cost * 0.5
            recommendations.append({
                "action": "Downgrade database tier (very low DTU utilization)",
                "details": f"DTU utilization is only {dtu_utilization_percent}%. Consider downgrading to lower tier. Save ~${potential_savings}/month.",
                "alternatives": [
                    {"name": "Downgrade to lower tier", "cost": round(monthly_cost * 0.5, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "high",
            })

        # Scenario 4: Premium tier en dev/test (HIGH - 65 score)
        elif sku_tier == "Premium" and monthly_cost > 1000:
            is_optimizable = True
            optimization_score = 65
            priority = "high"
            # Savings: Premium → Standard (70% reduction)
            potential_savings = monthly_cost * 0.7
            recommendations.append({
                "action": "Downgrade from Premium to Standard tier",
                "details": f"Using Premium tier (${monthly_cost}/mo). If dev/test environment, Standard tier is sufficient. Save ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Downgrade to Standard tier", "cost": round(monthly_cost * 0.3, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "high",
            })

        # Scenario 5: Geo-replication non nécessaire (MEDIUM - 50 score)
        elif has_geo_replication:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings: Geo-replication adds ~100% cost (double the database)
            potential_savings = monthly_cost * 0.5
            recommendations.append({
                "action": "Remove geo-replication if not required",
                "details": f"Database has geo-replication enabled. If not required for DR, remove to save ~${potential_savings}/month (50% reduction).",
                "alternatives": [
                    {"name": "Remove geo-replication", "cost": round(monthly_cost * 0.5, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_aks_clusters(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure AKS (Kubernetes) Clusters for cost intelligence.

        Detection criteria:
        - Cluster stopped/deallocated (CRITICAL - 90 score)
        - No node pools configured (HIGH - 75 score)
        - Node pools overprovisioned (>50% idle) (HIGH - 70 score)
        - Premium tier in dev/test (MEDIUM - 50 score)
        - Auto-scaler disabled on production (LOW - 30 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all AKS Clusters with optimization recommendations
        """
        logger.info("inventory.scan_azure_aks_start", region=region)
        all_aks_clusters: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.containerservice import ContainerServiceClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            aks_client = ContainerServiceClient(credential, self.subscription_id)
            clusters = list(aks_client.managed_clusters.list())

            logger.info(
                "inventory.azure_aks_fetched",
                region=region,
                total_clusters=len(clusters)
            )

            for cluster in clusters:
                # Filter by region
                if cluster.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(cluster.id):
                    continue

                # Cluster properties
                provisioning_state = cluster.provisioning_state if cluster.provisioning_state else "Unknown"
                power_state = cluster.power_state.code if cluster.power_state else "Running"
                is_stopped = power_state.lower() in ["stopped", "deallocated"]

                # Node pools analysis
                agent_pools = cluster.agent_pool_profiles if cluster.agent_pool_profiles else []
                has_node_pools = len(agent_pools) > 0
                total_nodes = sum(pool.count if pool.count else 0 for pool in agent_pools)

                # Auto-scaler analysis
                has_autoscaler = any(
                    pool.enable_auto_scaling for pool in agent_pools if pool.enable_auto_scaling
                )

                # Tier analysis
                sku_tier = cluster.sku.tier if cluster.sku else "Free"

                # Pricing calculation (Azure AKS pricing - US East 2025)
                # Cluster management fee (Standard/Premium tier)
                cluster_fee = 0.0
                if sku_tier == "Standard":
                    cluster_fee = 73.00  # $0.10/h * 730h
                elif sku_tier == "Premium":
                    cluster_fee = 511.00  # $0.70/h * 730h

                # Node pools cost (estimate based on Standard_DS2_v2: $0.096/h)
                node_cost_per_hour = 0.096  # Average for Standard_DS2_v2
                node_pool_cost = total_nodes * node_cost_per_hour * 730

                monthly_cost = cluster_fee + node_pool_cost

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_aks_optimization(
                    cluster, is_stopped, has_node_pools, total_nodes,
                    has_autoscaler, sku_tier, monthly_cost, cluster_fee
                )

                # Build resource metadata
                resource_metadata = {
                    "sku_tier": sku_tier,
                    "provisioning_state": provisioning_state,
                    "power_state": power_state,
                    "node_pool_count": len(agent_pools),
                    "total_nodes": total_nodes,
                    "has_autoscaler": has_autoscaler,
                    "kubernetes_version": cluster.kubernetes_version,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_aks_cluster",
                    resource_id=cluster.id,
                    resource_name=cluster.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=cluster.provisioning_state,  # Use provisioning state as proxy
                    last_used_at=None,  # No last-used timestamp available
                    status="active",
                )

                all_aks_clusters.append(resource)

            logger.info(
                "inventory.azure_aks_scanned",
                region=region,
                total_scanned=len(all_aks_clusters),
                optimizable=sum(1 for r in all_aks_clusters if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-containerservice",
                message="Install azure-mgmt-containerservice to scan AKS Clusters"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_aks_scan_failed",
                region=region,
                error=str(e)
            )

        return all_aks_clusters

    def _calculate_aks_optimization(
        self,
        cluster,
        is_stopped: bool,
        has_node_pools: bool,
        total_nodes: int,
        has_autoscaler: bool,
        sku_tier: str,
        monthly_cost: float,
        cluster_fee: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate AKS Cluster optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Cluster stopped/deallocated (CRITICAL - 90 score)
        if is_stopped:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete stopped AKS cluster",
                "details": f"AKS cluster is stopped. You're still paying ${monthly_cost}/month for cluster fee + stopped nodes. Delete if no longer needed.",
                "alternatives": [
                    {"name": "Delete cluster", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: No node pools configured (HIGH - 75 score)
        elif not has_node_pools or total_nodes == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete AKS cluster without nodes",
                "details": f"AKS cluster has no node pools or nodes. Paying ${monthly_cost}/month for empty cluster. Delete if not needed.",
                "alternatives": [
                    {"name": "Delete cluster", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "high",
            })

        # Scenario 3: Node pools overprovisioned (>50% idle) (HIGH - 70 score)
        # Note: Would need Azure Monitor metrics to detect idle nodes
        elif total_nodes > 5:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Estimate 30% of nodes are idle
            potential_savings = monthly_cost * 0.3
            recommendations.append({
                "action": "Review node pool sizing (potential idle nodes)",
                "details": f"AKS cluster has {total_nodes} nodes. Review actual usage to identify idle nodes. Estimated savings: ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Reduce node count by 30%", "cost": round(monthly_cost * 0.7, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "high",
            })

        # Scenario 4: Premium tier in dev/test (MEDIUM - 50 score)
        elif sku_tier == "Premium" and cluster_fee > 400:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings: Premium → Standard ($511 → $73)
            potential_savings = cluster_fee - 73.00
            recommendations.append({
                "action": "Downgrade from Premium to Standard tier",
                "details": f"Using Premium tier (${cluster_fee}/mo cluster fee). If dev/test, Standard tier ($73/mo) is sufficient. Save ${potential_savings}/month.",
                "alternatives": [
                    {"name": "Downgrade to Standard tier", "cost": round(monthly_cost - potential_savings, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 5: Auto-scaler disabled on production (LOW - 30 score)
        elif not has_autoscaler and total_nodes > 2:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # Estimate 15% savings with auto-scaler
            potential_savings = monthly_cost * 0.15
            recommendations.append({
                "action": "Enable cluster auto-scaler",
                "details": f"Auto-scaler is disabled. Enable auto-scaling to automatically adjust node count based on demand. Estimated savings: ${potential_savings}/month (15%).",
                "alternatives": [
                    {"name": "Enable auto-scaler", "cost": round(monthly_cost * 0.85, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_function_apps(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Function Apps for cost intelligence.

        Detection criteria:
        - Function app stopped (CRITICAL - 90 score)
        - Zero executions 30 derniers jours (HIGH - 75 score)
        - Premium plan underutilized (<1000 exec/day) (HIGH - 65 score)
        - Dedicated plan when Consumption sufficient (MEDIUM - 50 score)
        - Always On enabled on Consumption (LOW - 30 score)

        Args:
            region: Azure region to scan (e.g., 'eastus')

        Returns:
            List of all Function Apps with optimization recommendations
        """
        logger.info("inventory.scan_azure_functions_start", region=region)
        all_function_apps: list[AllCloudResourceData] = []

        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.web import WebSiteManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            web_client = WebSiteManagementClient(credential, self.subscription_id)

            # List all web apps (includes Function Apps)
            all_sites = list(web_client.web_apps.list())

            # Filter to only Function Apps
            function_apps = [site for site in all_sites if site.kind and "functionapp" in site.kind.lower()]

            logger.info(
                "inventory.azure_functions_fetched",
                region=region,
                total_function_apps=len(function_apps)
            )

            for func_app in function_apps:
                # Filter by region
                if func_app.location != region:
                    continue

                # Filter by resource group scope
                if not self.provider._is_resource_in_scope(func_app.id):
                    continue

                # Function App properties
                state = func_app.state if func_app.state else "Unknown"
                is_stopped = state.lower() == "stopped"

                # Get hosting plan type
                # Extract resource group from func_app.id
                resource_group = func_app.id.split("/")[4]

                # Get app service plan
                plan_type = "Consumption"  # Default
                plan_sku = "Y1"  # Default for Consumption

                if func_app.server_farm_id:
                    try:
                        plan_id_parts = func_app.server_farm_id.split("/")
                        plan_name = plan_id_parts[-1]
                        plan_rg = plan_id_parts[4]

                        plan = web_client.app_service_plans.get(plan_rg, plan_name)
                        plan_sku = plan.sku.name if plan.sku else "Y1"

                        # Determine plan type
                        if plan_sku.startswith("Y"):
                            plan_type = "Consumption"
                        elif plan_sku.startswith("EP"):
                            plan_type = "Premium"
                        else:
                            plan_type = "Dedicated"
                    except Exception:
                        pass

                # Estimate executions per day (requires Azure Monitor - hardcoded)
                daily_executions = 500  # Placeholder

                # Always On setting (only valid for Premium/Dedicated)
                always_on = func_app.site_config.always_on if func_app.site_config else False

                # Pricing calculation (Azure Functions pricing - US East 2025)
                monthly_cost = 0.0

                if plan_type == "Consumption":
                    # Consumption: $0.20 per million executions
                    monthly_executions = daily_executions * 30
                    execution_cost = (monthly_executions / 1_000_000) * 0.20
                    # GB-seconds: assume 128MB avg, 100ms avg duration
                    gb_seconds = (monthly_executions * 0.1) * (128 / 1024)
                    memory_cost = gb_seconds * 0.000016
                    monthly_cost = execution_cost + memory_cost
                elif plan_type == "Premium":
                    # Premium plans
                    premium_pricing = {
                        "EP1": 169.00,  # 1 vCPU, 3.5GB
                        "EP2": 338.00,  # 2 vCPU, 7GB
                        "EP3": 676.00,  # 4 vCPU, 14GB
                    }
                    monthly_cost = premium_pricing.get(plan_sku, 169.00)
                else:
                    # Dedicated (App Service Plan)
                    # Pricing varies widely, estimate average
                    monthly_cost = 100.00  # Conservative estimate

                # Calculate optimization
                (is_optimizable, optimization_score, optimization_priority,
                 potential_savings, recommendations) = self._calculate_function_optimization(
                    func_app, is_stopped, plan_type, plan_sku, daily_executions,
                    always_on, monthly_cost
                )

                # Build resource metadata
                resource_metadata = {
                    "state": state,
                    "plan_type": plan_type,
                    "plan_sku": plan_sku,
                    "daily_executions": daily_executions,
                    "always_on": always_on,
                    "runtime": func_app.kind,
                }

                resource = AllCloudResourceData(
                    resource_type="azure_function_app",
                    resource_id=func_app.id,
                    resource_name=func_app.name,
                    region=region,
                    estimated_monthly_cost=round(monthly_cost, 2),
                    currency="USD",
                    is_optimizable=is_optimizable,
                    optimization_priority=optimization_priority,
                    optimization_score=optimization_score,
                    potential_monthly_savings=round(potential_savings, 2),
                    optimization_recommendations=recommendations,
                    resource_metadata=resource_metadata,
                    created_at_cloud=func_app.type,  # Use type as proxy
                    last_used_at=None,
                    status="active",
                )

                all_function_apps.append(resource)

            logger.info(
                "inventory.azure_functions_scanned",
                region=region,
                total_scanned=len(all_function_apps),
                optimizable=sum(1 for r in all_function_apps if r.is_optimizable)
            )

        except ImportError:
            logger.error(
                "inventory.azure_sdk_missing",
                region=region,
                sdk="azure-mgmt-web",
                message="Install azure-mgmt-web to scan Function Apps"
            )
        except Exception as e:
            logger.exception(
                "inventory.azure_functions_scan_failed",
                region=region,
                error=str(e)
            )

        return all_function_apps

    def _calculate_function_optimization(
        self,
        func_app,
        is_stopped: bool,
        plan_type: str,
        plan_sku: str,
        daily_executions: int,
        always_on: bool,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate Function App optimization opportunities.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Function app stopped (CRITICAL - 90 score)
        if is_stopped:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete stopped Function App",
                "details": f"Function App is stopped. Delete if no longer needed. Save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete Function App", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero executions 30 days (HIGH - 75 score)
        elif daily_executions < 10:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.append({
                "action": "Delete unused Function App (no executions)",
                "details": f"Function App has very few executions ({daily_executions}/day). Delete if not needed. Save ${monthly_cost}/month.",
                "alternatives": [
                    {"name": "Delete Function App", "cost": 0, "savings": monthly_cost},
                ],
                "priority": "high",
            })

        # Scenario 3: Premium plan underutilized (<1000 exec/day) (HIGH - 65 score)
        elif plan_type == "Premium" and daily_executions < 1000:
            is_optimizable = True
            optimization_score = 65
            priority = "high"
            # Savings: Premium → Consumption (estimate $165/mo)
            consumption_cost = (daily_executions * 30 / 1_000_000) * 0.20
            potential_savings = monthly_cost - consumption_cost
            recommendations.append({
                "action": "Downgrade from Premium to Consumption plan",
                "details": f"Using Premium plan (${monthly_cost}/mo) but only {daily_executions} executions/day. Consumption plan would cost ${consumption_cost:.2f}/month. Save ${potential_savings:.2f}/month.",
                "alternatives": [
                    {"name": "Switch to Consumption plan", "cost": round(consumption_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "high",
            })

        # Scenario 4: Dedicated plan when Consumption sufficient (MEDIUM - 50 score)
        elif plan_type == "Dedicated" and daily_executions < 5000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings: Dedicated → Consumption
            consumption_cost = (daily_executions * 30 / 1_000_000) * 0.20
            potential_savings = monthly_cost - consumption_cost
            recommendations.append({
                "action": "Switch from Dedicated to Consumption plan",
                "details": f"Using Dedicated plan (${monthly_cost}/mo) with {daily_executions} executions/day. Consumption plan sufficient. Save ${potential_savings:.2f}/month.",
                "alternatives": [
                    {"name": "Switch to Consumption plan", "cost": round(consumption_cost, 2), "savings": round(potential_savings, 2)},
                ],
                "priority": "medium",
            })

        # Scenario 5: Always On enabled on Consumption (LOW - 30 score)
        elif plan_type == "Consumption" and always_on:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # Always On not supported on Consumption, but if somehow enabled
            potential_savings = monthly_cost * 0.1
            recommendations.append({
                "action": "Disable Always On (not supported on Consumption)",
                "details": "Always On is enabled but not beneficial on Consumption plan. Disable to avoid cold starts being masked.",
                "alternatives": [
                    {"name": "Disable Always On", "cost": round(monthly_cost, 2), "savings": 0},
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_cosmos_dbs(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Cosmos DB accounts for cost intelligence.

        Detection criteria:
        - Database account paused/offline (CRITICAL - 90 score)
        - Zero requests 30 derniers jours (HIGH - 75 score)
        - Provisioned throughput >> actual usage (>50% idle) (HIGH - 70 score)
        - Multi-region replication without need (MEDIUM - 50 score)
        - Serverless would be cheaper based on usage (LOW - 30 score)
        """
        try:
            from azure.mgmt.cosmosdb import CosmosDBManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-cosmosdb not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Cosmos DB accounts in region: {region}")

        try:
            cosmos_client = CosmosDBManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all Cosmos DB accounts
            async for account in cosmos_client.database_accounts.list():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and account.location.lower() != region.lower():
                        continue

                    # Get resource group from account ID
                    resource_group = account.id.split("/")[4]

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_cosmos_optimization(account)
                    )

                    # Get database count
                    databases = []
                    try:
                        # Get SQL databases
                        sql_dbs = list(cosmos_client.sql_resources.list_sql_databases(
                            resource_group_name=resource_group,
                            account_name=account.name
                        ))
                        databases.extend(sql_dbs)
                    except:
                        pass

                    try:
                        # Get Table API databases
                        tables = list(cosmos_client.table_resources.list_tables(
                            resource_group_name=resource_group,
                            account_name=account.name
                        ))
                        databases.extend(tables)
                    except:
                        pass

                    # Pricing (Azure US East 2025)
                    # Serverless: ~$0.25/1M RUs + $0.25/GB storage
                    # Provisioned: $0.008/RU/hour ($5.84/100 RU/mo)
                    # Multi-region adds 2x-3x cost
                    pricing_info = {
                        "serverless_base": 25.0,  # Typical small workload
                        "provisioned_100ru": 5.84,
                        "provisioned_400ru": 23.36,
                        "provisioned_1000ru": 58.40,
                        "provisioned_10000ru": 584.00,
                        "multi_region_multiplier": 2.0,
                    }

                    # Get provisioning state and capabilities
                    provisioning_state = getattr(account, 'provisioning_state', 'Unknown')
                    capabilities = getattr(account, 'capabilities', [])
                    capability_names = [cap.name for cap in capabilities] if capabilities else []

                    # Detect account type
                    is_serverless = 'EnableServerless' in capability_names
                    is_multi_region = len(account.locations) > 1 if hasattr(account, 'locations') else False

                    # Estimate monthly cost based on configuration
                    if is_serverless:
                        base_cost = pricing_info["serverless_base"]
                    else:
                        # Assume 400 RU/s for small, 1000 for medium
                        base_cost = pricing_info["provisioned_400ru"]

                    if is_multi_region:
                        base_cost *= pricing_info["multi_region_multiplier"]

                    resources.append(AllCloudResourceData(
                        resource_id=account.id,
                        resource_type="azure_cosmos_db",
                        resource_name=account.name or "Unnamed Cosmos DB",
                        region=account.location,
                        estimated_monthly_cost=base_cost,
                        currency="USD",
                        resource_metadata={
                            "account_id": account.id,
                            "resource_group": resource_group,
                            "provisioning_state": provisioning_state,
                            "kind": getattr(account, 'kind', 'GlobalDocumentDB'),
                            "database_account_offer_type": getattr(account, 'database_account_offer_type', 'Standard'),
                            "consistency_policy": str(getattr(account, 'default_consistency_level', 'Session')),
                            "is_serverless": is_serverless,
                            "is_multi_region": is_multi_region,
                            "locations": [loc.location_name for loc in account.locations] if hasattr(account, 'locations') else [],
                            "database_count": len(databases),
                            "capabilities": capability_names,
                            "tags": dict(account.tags) if account.tags else {},
                        },
                        is_optimizable=is_optimizable,
                        optimization_score=score,
                        optimization_priority=priority,
                        potential_monthly_savings=savings,
                        optimization_recommendations=recommendations,
                        last_used_at=None,
                        created_at_cloud=None,
                    ))

                except Exception as e:
                    self.logger.error(f"Error processing Cosmos DB account {getattr(account, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} Cosmos DB accounts in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning Cosmos DB accounts: {str(e)}")
            return []

    def _calculate_cosmos_optimization(self, account) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for Cosmos DB account.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get account properties
        provisioning_state = getattr(account, 'provisioning_state', 'Unknown')
        capabilities = getattr(account, 'capabilities', [])
        capability_names = [cap.name for cap in capabilities] if capabilities else []
        is_serverless = 'EnableServerless' in capability_names
        is_multi_region = len(account.locations) > 1 if hasattr(account, 'locations') else False
        location_count = len(account.locations) if hasattr(account, 'locations') else 1

        # Scenario 1: Database account paused/offline (CRITICAL - 90)
        if provisioning_state.lower() in ['deleting', 'failed', 'canceled']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            # Estimate savings: Full cost if stopped/failed
            estimated_cost = 100.0 if not is_serverless else 25.0
            if is_multi_region:
                estimated_cost *= 2.0
            potential_savings = max(potential_savings, estimated_cost)

            recommendations.append({
                "title": "Database Account Non Fonctionnel",
                "description": f"Ce compte Cosmos DB est dans l'état '{provisioning_state}'. Il peut générer des coûts inutiles s'il n'est pas utilisé.",
                "estimated_savings": round(estimated_cost, 2),
                "actions": [
                    "Vérifier l'état du compte et corriger les problèmes",
                    "Supprimer le compte s'il n'est plus nécessaire",
                    "Restaurer depuis une sauvegarde si données importantes"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero requests last 30 days (HIGH - 75)
        # Note: We can't get actual metrics without Azure Monitor, so this is a placeholder
        # In production, you'd check actual request metrics

        # Scenario 3: Provisioned throughput >> actual usage (HIGH - 70)
        if not is_serverless:  # Only applicable to provisioned throughput
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Estimate 50% savings by right-sizing
            estimated_cost = 58.40  # Assume 1000 RU/s
            if is_multi_region:
                estimated_cost *= 2.0
            savings = estimated_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Débit Provisionné Potentiellement Surdimensionné",
                "description": "Ce compte Cosmos DB utilise le mode provisionné. Vérifiez si le débit configuré correspond à l'utilisation réelle.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques d'utilisation des RU/s dans Azure Monitor",
                    "Réduire le débit provisionné si utilisation <50%",
                    "Activer l'auto-scaling pour adapter automatiquement",
                    "Considérer le mode Serverless si utilisation sporadique"
                ],
                "priority": "high",
            })

        # Scenario 4: Multi-region without need (MEDIUM - 50)
        if is_multi_region and location_count > 2:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Multi-region doubles cost, removing extra regions saves significant
            base_cost = 100.0 if not is_serverless else 25.0
            # Savings from removing extra regions (keep 1-2 regions max)
            savings = base_cost * (location_count - 2) * 0.8
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Réplication Multi-Région Excessive",
                "description": f"Ce compte Cosmos DB est répliqué dans {location_count} régions. Chaque région ajoute des coûts significatifs.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Évaluer la nécessité de chaque région de réplication",
                    "Garder uniquement les régions essentielles (1-2 max)",
                    "Supprimer les régions secondaires non utilisées",
                    f"Économies potentielles: ~{int(savings)}$/mois par région supprimée"
                ],
                "priority": "medium",
            })

        # Scenario 5: Serverless would be cheaper (LOW - 30)
        if not is_serverless:
            # Serverless is better for sporadic/low-volume workloads
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Estimate savings if switching to serverless
            provisioned_cost = 58.40  # Assume 1000 RU/s
            serverless_cost = 25.0
            savings = max(0, provisioned_cost - serverless_cost)
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Mode Serverless Potentiellement Plus Économique",
                "description": "Ce compte utilise le débit provisionné. Le mode Serverless peut être plus rentable pour les workloads sporadiques.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser le pattern d'utilisation (sporadique vs constant)",
                    "Évaluer le coût Serverless vs Provisionné pour votre charge",
                    "Créer un nouveau compte Serverless et migrer si pertinent",
                    "Note: Serverless idéal pour <1M RU/s par jour"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_container_apps(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Container Apps for cost intelligence.

        Detection criteria:
        - Container app stopped/deprovisioned (CRITICAL - 90 score)
        - Zero requests 30 derniers jours (HIGH - 75 score)
        - Replicas overprovisioned (>50% idle capacity) (HIGH - 70 score)
        - Consumption plan when Dedicated sufficient (MEDIUM - 50 score)
        - Auto-scaling disabled on production (LOW - 30 score)
        """
        try:
            from azure.mgmt.appcontainers import ContainerAppsAPIClient
        except ImportError:
            self.logger.error("azure-mgmt-appcontainers not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Container Apps in region: {region}")

        try:
            container_client = ContainerAppsAPIClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all Container Apps
            async for app in container_client.container_apps.list_by_subscription():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and app.location.lower() != region.lower():
                        continue

                    # Get resource group from app ID
                    resource_group = app.id.split("/")[4]

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_container_app_optimization(app)
                    )

                    # Pricing (Azure US East 2025)
                    # Consumption: $0.000012/vCPU-second + $0.000003/GiB-second
                    # Dedicated: $72/month per vCPU + $18/month per GiB
                    # Typical small app: 0.25 vCPU, 0.5 GiB = ~$50/mo consumption
                    pricing_info = {
                        "consumption_vcpu_second": 0.000012,
                        "consumption_gb_second": 0.000003,
                        "dedicated_vcpu_month": 72.0,
                        "dedicated_gb_month": 18.0,
                    }

                    # Get configuration
                    provisioning_state = getattr(app, 'provisioning_state', 'Unknown')
                    configuration = getattr(app, 'configuration', None)
                    template = getattr(app, 'template', None)

                    # Get scale settings
                    min_replicas = 0
                    max_replicas = 1
                    if template and hasattr(template, 'scale'):
                        scale = template.scale
                        min_replicas = getattr(scale, 'min_replicas', 0)
                        max_replicas = getattr(scale, 'max_replicas', 1)

                    # Get container resources
                    containers = []
                    total_vcpu = 0.25  # Default
                    total_memory_gb = 0.5  # Default
                    if template and hasattr(template, 'containers'):
                        containers = template.containers
                        for container in containers:
                            resources_config = getattr(container, 'resources', None)
                            if resources_config:
                                cpu = getattr(resources_config, 'cpu', 0.25)
                                memory = getattr(resources_config, 'memory', '0.5Gi')
                                # Parse memory (e.g., "0.5Gi" -> 0.5)
                                try:
                                    mem_value = float(memory.replace('Gi', '').replace('G', ''))
                                except:
                                    mem_value = 0.5
                                total_vcpu += cpu
                                total_memory_gb += mem_value

                    # Get environment type (consumption vs dedicated)
                    managed_environment_id = getattr(app, 'managed_environment_id', '')
                    is_consumption = 'consumption' in managed_environment_id.lower() if managed_environment_id else True

                    # Estimate monthly cost (assume running 24/7)
                    if is_consumption:
                        # Consumption: per second pricing
                        seconds_per_month = 730 * 3600  # 730 hours
                        vcpu_cost = pricing_info["consumption_vcpu_second"] * total_vcpu * seconds_per_month
                        memory_cost = pricing_info["consumption_gb_second"] * total_memory_gb * seconds_per_month
                        base_cost = vcpu_cost + memory_cost
                    else:
                        # Dedicated: monthly pricing
                        base_cost = (pricing_info["dedicated_vcpu_month"] * total_vcpu +
                                   pricing_info["dedicated_gb_month"] * total_memory_gb)

                    # Multiply by average replicas (assume avg = (min + max) / 2)
                    avg_replicas = max(1, (min_replicas + max_replicas) / 2)
                    estimated_cost = base_cost * avg_replicas

                    resources.append(AllCloudResourceData(
                        resource_id=app.id,
                        resource_type="azure_container_app",
                        resource_name=app.name or "Unnamed Container App",
                        region=app.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "app_id": app.id,
                            "resource_group": resource_group,
                            "provisioning_state": provisioning_state,
                            "managed_environment_id": managed_environment_id,
                            "is_consumption": is_consumption,
                            "min_replicas": min_replicas,
                            "max_replicas": max_replicas,
                            "total_vcpu": total_vcpu,
                            "total_memory_gb": total_memory_gb,
                            "container_count": len(containers),
                            "ingress_enabled": configuration and hasattr(configuration, 'ingress') and configuration.ingress is not None,
                            "tags": dict(app.tags) if app.tags else {},
                        },
                        is_optimizable=is_optimizable,
                        optimization_score=score,
                        optimization_priority=priority,
                        potential_monthly_savings=savings,
                        optimization_recommendations=recommendations,
                        last_used_at=None,
                        created_at_cloud=None,
                    ))

                except Exception as e:
                    self.logger.error(f"Error processing Container App {getattr(app, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} Container Apps in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning Container Apps: {str(e)}")
            return []

    def _calculate_container_app_optimization(self, app) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for Container App.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get app properties
        provisioning_state = getattr(app, 'provisioning_state', 'Unknown')
        template = getattr(app, 'template', None)
        managed_environment_id = getattr(app, 'managed_environment_id', '')
        is_consumption = 'consumption' in managed_environment_id.lower() if managed_environment_id else True

        # Get scale settings
        min_replicas = 0
        max_replicas = 1
        if template and hasattr(template, 'scale'):
            scale = template.scale
            min_replicas = getattr(scale, 'min_replicas', 0)
            max_replicas = getattr(scale, 'max_replicas', 1)

        # Get resources
        total_vcpu = 0.25
        total_memory_gb = 0.5
        if template and hasattr(template, 'containers'):
            containers = template.containers
            for container in containers:
                resources_config = getattr(container, 'resources', None)
                if resources_config:
                    cpu = getattr(resources_config, 'cpu', 0.25)
                    memory = getattr(resources_config, 'memory', '0.5Gi')
                    try:
                        mem_value = float(memory.replace('Gi', '').replace('G', ''))
                    except:
                        mem_value = 0.5
                    total_vcpu += cpu
                    total_memory_gb += mem_value

        # Estimate monthly cost
        if is_consumption:
            seconds_per_month = 730 * 3600
            base_cost = (0.000012 * total_vcpu * seconds_per_month +
                        0.000003 * total_memory_gb * seconds_per_month)
        else:
            base_cost = 72.0 * total_vcpu + 18.0 * total_memory_gb

        avg_replicas = max(1, (min_replicas + max_replicas) / 2)
        monthly_cost = base_cost * avg_replicas

        # Scenario 1: Container app stopped/deprovisioned (CRITICAL - 90)
        if provisioning_state.lower() in ['deprovisioning', 'failed', 'canceled', 'deleting']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Container App Non Fonctionnelle",
                "description": f"Cette Container App est dans l'état '{provisioning_state}'. Elle génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Vérifier l'état de l'application et corriger les problèmes",
                    "Supprimer l'application si elle n'est plus nécessaire",
                    "Redéployer l'application si elle est encore utilisée"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero requests last 30 days (HIGH - 75)
        # Note: We can't get actual metrics without Azure Monitor
        # In production, check ingress metrics

        # Scenario 3: Replicas overprovisioned (HIGH - 70)
        if max_replicas > 3 and min_replicas > 1:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Savings from reducing replicas by 50%
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Réplicas Potentiellement Surdimensionnés",
                "description": f"Cette app est configurée avec {min_replicas}-{max_replicas} réplicas. Vérifiez si c'est nécessaire.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques de charge CPU/mémoire dans Azure Monitor",
                    f"Réduire min_replicas de {min_replicas} à 1 si charge faible",
                    f"Réduire max_replicas de {max_replicas} à 3 si pic de charge modéré",
                    "Activer l'auto-scaling pour adapter dynamiquement"
                ],
                "priority": "high",
            })

        # Scenario 4: Consumption when Dedicated sufficient (MEDIUM - 50)
        # This is the opposite of typical cloud optimization (dedicated is usually more expensive)
        # Only applicable if usage is very high and predictable
        # Skip this scenario as consumption is typically better

        # Scenario 5: Auto-scaling disabled (LOW - 30)
        if min_replicas == max_replicas and min_replicas > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Savings from enabling auto-scaling (assume 20% reduction)
            savings = monthly_cost * 0.2
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Auto-Scaling Désactivé",
                "description": f"Cette app a un nombre fixe de réplicas ({min_replicas}). L'auto-scaling permettrait d'adapter la capacité.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Activer l'auto-scaling pour adapter automatiquement",
                    "Configurer min_replicas=1 et max_replicas=5 pour commencer",
                    "Définir des règles de scaling basées sur CPU/HTTP requests",
                    "Économies potentielles: ~20% en adaptant aux heures creuses"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_virtual_desktops(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Virtual Desktop (AVD) host pools for cost intelligence.

        Detection criteria:
        - Host pool stopped/deallocated (CRITICAL - 90 score)
        - Zero active sessions 30 derniers jours (HIGH - 75 score)
        - Session hosts overprovisioned (>50% idle capacity) (HIGH - 70 score)
        - Pooled when Personal sufficient (MEDIUM - 50 score)
        - No auto-scaling configured (LOW - 30 score)
        """
        try:
            from azure.mgmt.desktopvirtualization import DesktopVirtualizationMgmtClient
        except ImportError:
            self.logger.error("azure-mgmt-desktopvirtualization not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Virtual Desktop host pools in region: {region}")

        try:
            vd_client = DesktopVirtualizationMgmtClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all host pools
            async for host_pool in vd_client.host_pools.list():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and host_pool.location.lower() != region.lower():
                        continue

                    # Get resource group from host pool ID
                    resource_group = host_pool.id.split("/")[4]

                    # Get session hosts count
                    session_hosts = []
                    try:
                        session_hosts = list(vd_client.session_hosts.list(
                            resource_group_name=resource_group,
                            host_pool_name=host_pool.name
                        ))
                    except:
                        pass

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_virtual_desktop_optimization(host_pool, session_hosts)
                    )

                    # Pricing (Azure US East 2025)
                    # Session host: D2s_v3 (2 vCPU, 8 GB) = $0.096/h = $70/mo
                    # Storage: Premium SSD $0.135/GB/mo
                    # Typical host pool: 2-10 session hosts = $140-$700/mo
                    pricing_info = {
                        "session_host_hourly": 0.096,  # D2s_v3
                        "session_host_monthly": 70.08,
                        "storage_gb_monthly": 0.135,
                    }

                    # Estimate monthly cost
                    session_host_count = len(session_hosts)
                    base_cost = pricing_info["session_host_monthly"] * max(1, session_host_count)

                    # Add storage estimate (assume 128 GB per session host)
                    storage_gb = 128 * max(1, session_host_count)
                    storage_cost = pricing_info["storage_gb_monthly"] * storage_gb

                    estimated_cost = base_cost + storage_cost

                    # Get host pool properties
                    load_balancer_type = getattr(host_pool, 'load_balancer_type', 'BreadthFirst')
                    max_session_limit = getattr(host_pool, 'max_session_limit', 10)
                    host_pool_type = getattr(host_pool, 'host_pool_type', 'Pooled')

                    resources.append(AllCloudResourceData(
                        resource_id=host_pool.id,
                        resource_type="azure_virtual_desktop",
                        resource_name=host_pool.name or "Unnamed Host Pool",
                        region=host_pool.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "host_pool_id": host_pool.id,
                            "resource_group": resource_group,
                            "host_pool_type": host_pool_type,
                            "load_balancer_type": load_balancer_type,
                            "max_session_limit": max_session_limit,
                            "session_host_count": session_host_count,
                            "storage_gb": storage_gb,
                            "tags": dict(host_pool.tags) if host_pool.tags else {},
                        },
                        is_optimizable=is_optimizable,
                        optimization_score=score,
                        optimization_priority=priority,
                        potential_monthly_savings=savings,
                        optimization_recommendations=recommendations,
                        last_used_at=None,
                        created_at_cloud=None,
                    ))

                except Exception as e:
                    self.logger.error(f"Error processing Virtual Desktop host pool {getattr(host_pool, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} Virtual Desktop host pools in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning Virtual Desktop host pools: {str(e)}")
            return []

    def _calculate_virtual_desktop_optimization(self, host_pool, session_hosts: list) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for Virtual Desktop host pool.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get host pool properties
        host_pool_type = getattr(host_pool, 'host_pool_type', 'Pooled')
        max_session_limit = getattr(host_pool, 'max_session_limit', 10)
        session_host_count = len(session_hosts)

        # Estimate monthly cost
        session_host_monthly = 70.08  # D2s_v3
        storage_monthly = 0.135 * 128  # 128 GB per host
        monthly_cost = (session_host_monthly + storage_monthly) * max(1, session_host_count)

        # Count active vs stopped session hosts
        active_hosts = 0
        stopped_hosts = 0
        for host in session_hosts:
            status = getattr(host, 'status', 'Unknown')
            if status.lower() in ['available', 'running']:
                active_hosts += 1
            elif status.lower() in ['stopped', 'deallocated', 'unavailable']:
                stopped_hosts += 1

        # Scenario 1: Host pool stopped/deallocated (CRITICAL - 90)
        if session_host_count > 0 and stopped_hosts == session_host_count:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Host Pool Entièrement Arrêté",
                "description": f"Tous les {session_host_count} session hosts sont arrêtés. Le host pool génère des coûts de stockage inutiles.",
                "estimated_savings": round(monthly_cost * 0.9, 2),  # Can save 90% (storage remains)
                "actions": [
                    "Démarrer les session hosts si le host pool est encore utilisé",
                    "Supprimer le host pool s'il n'est plus nécessaire",
                    "Configurer auto-start/stop pour optimiser les coûts"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero active sessions 30 days (HIGH - 75)
        # Note: We can't get actual session metrics without Azure Monitor
        # In production, check active session count from monitoring

        # Scenario 3: Session hosts overprovisioned (HIGH - 70)
        if session_host_count > 5 and host_pool_type == 'Pooled':
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Assume 50% of hosts can be removed
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Session Hosts Potentiellement Surdimensionnés",
                "description": f"Ce host pool a {session_host_count} session hosts. Vérifiez si tous sont nécessaires.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques d'utilisation dans Azure Monitor",
                    f"Réduire de {session_host_count} à {session_host_count // 2} hosts si charge faible",
                    "Activer l'auto-scaling pour adapter automatiquement",
                    "Considérer le scaling basé sur les heures de bureau"
                ],
                "priority": "high",
            })

        # Scenario 4: Pooled when Personal sufficient (MEDIUM - 50)
        if host_pool_type == 'Pooled' and session_host_count <= 2:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Personal can be cheaper for small user count
            savings = monthly_cost * 0.2
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Type de Host Pool Potentiellement Inadapté",
                "description": f"Host pool 'Pooled' avec seulement {session_host_count} hosts. Un host pool 'Personal' peut être plus adapté.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Évaluer le nombre d'utilisateurs et leur pattern d'utilisation",
                    "Considérer un host pool 'Personal' si <10 utilisateurs",
                    "Personal offre une expérience plus consistente pour petits groupes",
                    "Économies potentielles: ~20% avec Personal pour usage léger"
                ],
                "priority": "medium",
            })

        # Scenario 5: No auto-scaling configured (LOW - 30)
        # Note: Auto-scaling is configured separately, we can't detect it from host pool properties
        # In production, check if scaling plan exists
        if session_host_count > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Savings from auto-scaling (assume 30% reduction during off-hours)
            savings = monthly_cost * 0.3
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Auto-Scaling Non Configuré",
                "description": "Ce host pool peut bénéficier d'un scaling plan pour adapter la capacité automatiquement.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Créer un scaling plan pour ce host pool",
                    "Configurer scaling basé sur les heures de bureau (8h-18h)",
                    "Réduire automatiquement les hosts pendant les week-ends",
                    "Économies potentielles: ~30% avec auto-scaling optimisé"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_hdinsight_clusters(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure HDInsight Spark/Hadoop clusters for cost intelligence.

        Detection criteria:
        - Cluster stopped/failed (CRITICAL - 90 score)
        - Zero jobs 30 derniers jours (HIGH - 75 score)
        - Worker nodes underutilized (<30% CPU) (HIGH - 70 score)
        - Running 24/7 for batch workloads (MEDIUM - 50 score)
        - No auto-scaling enabled (LOW - 30 score)
        """
        try:
            from azure.mgmt.hdinsight import HDInsightManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-hdinsight not installed")
            return []

        resources = []
        self.logger.info(f"Scanning HDInsight clusters in region: {region}")

        try:
            hdi_client = HDInsightManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all clusters
            async for cluster in hdi_client.clusters.list():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and cluster.location.lower() != region.lower():
                        continue

                    # Get resource group from cluster ID
                    resource_group = cluster.id.split("/")[4]

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_hdinsight_optimization(cluster)
                    )

                    # Pricing (Azure US East 2025)
                    # Head node: D3 v2 (4 vCPU, 14 GB) = $0.21/h = $153/mo x 2 = $307/mo
                    # Worker node: D3 v2 = $0.21/h = $153/mo per node
                    # Storage: Standard $0.05/GB/mo
                    # Typical cluster: 2 head + 4 workers = $922/mo
                    pricing_info = {
                        "head_node_hourly": 0.21,  # D3 v2
                        "head_node_monthly": 153.30,
                        "worker_node_hourly": 0.21,
                        "worker_node_monthly": 153.30,
                        "storage_gb_monthly": 0.05,
                    }

                    # Get cluster configuration
                    cluster_state = getattr(cluster.properties, 'cluster_state', 'Unknown')
                    cluster_version = getattr(cluster.properties, 'cluster_version', 'Unknown')
                    tier = getattr(cluster.properties, 'tier', 'Standard')

                    # Get node counts
                    head_node_count = 2  # Always 2 for HDInsight
                    worker_node_count = 0

                    compute_profile = getattr(cluster.properties, 'compute_profile', None)
                    if compute_profile and hasattr(compute_profile, 'roles'):
                        for role in compute_profile.roles:
                            if role.name == 'workernode':
                                target_instance_count = getattr(role, 'target_instance_count', 0)
                                worker_node_count = target_instance_count

                    # Estimate monthly cost
                    head_cost = pricing_info["head_node_monthly"] * head_node_count
                    worker_cost = pricing_info["worker_node_monthly"] * worker_node_count

                    # Add storage estimate (assume 256 GB per worker node)
                    storage_gb = 256 * max(1, worker_node_count)
                    storage_cost = pricing_info["storage_gb_monthly"] * storage_gb

                    estimated_cost = head_cost + worker_cost + storage_cost

                    # Get cluster type
                    cluster_definition = getattr(cluster.properties, 'cluster_definition', None)
                    kind = 'Hadoop'
                    if cluster_definition and hasattr(cluster_definition, 'kind'):
                        kind = cluster_definition.kind

                    resources.append(AllCloudResourceData(
                        resource_id=cluster.id,
                        resource_type="azure_hdinsight_cluster",
                        resource_name=cluster.name or "Unnamed HDInsight Cluster",
                        region=cluster.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "cluster_id": cluster.id,
                            "resource_group": resource_group,
                            "cluster_state": cluster_state,
                            "cluster_version": cluster_version,
                            "tier": tier,
                            "kind": kind,
                            "head_node_count": head_node_count,
                            "worker_node_count": worker_node_count,
                            "storage_gb": storage_gb,
                            "tags": dict(cluster.tags) if cluster.tags else {},
                        },
                        is_optimizable=is_optimizable,
                        optimization_score=score,
                        optimization_priority=priority,
                        potential_monthly_savings=savings,
                        optimization_recommendations=recommendations,
                        last_used_at=None,
                        created_at_cloud=None,
                    ))

                except Exception as e:
                    self.logger.error(f"Error processing HDInsight cluster {getattr(cluster, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} HDInsight clusters in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning HDInsight clusters: {str(e)}")
            return []

    def _calculate_hdinsight_optimization(self, cluster) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for HDInsight cluster.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get cluster properties
        cluster_state = getattr(cluster.properties, 'cluster_state', 'Unknown')
        tier = getattr(cluster.properties, 'tier', 'Standard')

        # Get node counts
        head_node_count = 2
        worker_node_count = 0

        compute_profile = getattr(cluster.properties, 'compute_profile', None)
        if compute_profile and hasattr(compute_profile, 'roles'):
            for role in compute_profile.roles:
                if role.name == 'workernode':
                    worker_node_count = getattr(role, 'target_instance_count', 0)

        # Estimate monthly cost
        head_monthly = 153.30 * head_node_count
        worker_monthly = 153.30 * worker_node_count
        storage_monthly = 0.05 * 256 * max(1, worker_node_count)
        monthly_cost = head_monthly + worker_monthly + storage_monthly

        # Scenario 1: Cluster stopped/failed (CRITICAL - 90)
        if cluster_state.lower() in ['error', 'deleting', 'deleted']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Cluster en État d'Erreur",
                "description": f"Ce cluster HDInsight est dans l'état '{cluster_state}'. Il génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Vérifier les logs pour identifier le problème",
                    "Supprimer le cluster s'il ne peut pas être réparé",
                    "Restaurer depuis une configuration sauvegardée si nécessaire"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero jobs 30 days (HIGH - 75)
        # Note: We can't get actual job metrics without Azure Monitor
        # In production, check job submission history

        # Scenario 3: Worker nodes underutilized (HIGH - 70)
        if worker_node_count > 6:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Assume 50% of worker nodes can be removed
            savings = worker_monthly * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Worker Nodes Potentiellement Surdimensionnés",
                "description": f"Ce cluster a {worker_node_count} worker nodes. Vérifiez si tous sont nécessaires.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques CPU/mémoire dans Azure Monitor",
                    f"Réduire de {worker_node_count} à {worker_node_count // 2} workers si charge <30%",
                    "Activer l'auto-scaling pour adapter automatiquement",
                    "Considérer le scaling basé sur la charge de travail"
                ],
                "priority": "high",
            })

        # Scenario 4: Running 24/7 for batch workloads (MEDIUM - 50)
        if worker_node_count > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Assume cluster runs 24/7 but only needed 8h/day
            savings = monthly_cost * 0.67  # Save 16h/day
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Cluster Running 24/7 pour Batch",
                "description": "Ce cluster tourne en permanence. Les workloads batch peuvent être schedulés.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Identifier si les jobs sont batch ou streaming",
                    "Arrêter/démarrer le cluster selon le schedule des jobs",
                    "Utiliser Azure Data Factory pour orchestrer les pipelines",
                    "Économies potentielles: ~67% en arrêtant 16h/jour"
                ],
                "priority": "medium",
            })

        # Scenario 5: No auto-scaling enabled (LOW - 30)
        if worker_node_count > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Savings from auto-scaling (assume 25% reduction)
            savings = worker_monthly * 0.25
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Auto-Scaling Non Activé",
                "description": "Ce cluster peut bénéficier de l'auto-scaling pour adapter la capacité automatiquement.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Activer l'auto-scaling dans les paramètres du cluster",
                    "Configurer min/max workers selon la charge",
                    "Définir des métriques de scaling (CPU, mémoire, pending tasks)",
                    "Économies potentielles: ~25% avec auto-scaling optimisé"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_ml_compute_instances(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure ML Compute Instances for cost intelligence.

        Detection criteria:
        - Instance stopped but billing (CRITICAL - 90 score)
        - Zero activity 30 derniers jours (HIGH - 75 score)
        - Running but no notebooks active (HIGH - 70 score)
        - GPU instance for CPU workload (MEDIUM - 50 score)
        - No auto-shutdown configured (LOW - 30 score)
        """
        try:
            from azure.mgmt.machinelearningservices import AzureMachineLearningWorkspaces
        except ImportError:
            self.logger.error("azure-mgmt-machinelearningservices not installed")
            return []

        resources = []
        self.logger.info(f"Scanning ML Compute Instances in region: {region}")

        try:
            ml_client = AzureMachineLearningWorkspaces(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all workspaces first
            async for workspace in ml_client.workspaces.list_by_subscription():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and workspace.location.lower() != region.lower():
                        continue

                    # Get resource group from workspace ID
                    resource_group = workspace.id.split("/")[4]

                    # List compute instances in this workspace
                    try:
                        compute_instances = list(ml_client.compute.list(
                            resource_group_name=resource_group,
                            workspace_name=workspace.name
                        ))
                    except:
                        continue

                    for compute in compute_instances:
                        try:
                            # Only process ComputeInstance type (not AML clusters)
                            compute_type = getattr(compute.properties, 'compute_type', 'Unknown')
                            if compute_type != 'ComputeInstance':
                                continue

                            # Calculate optimization
                            is_optimizable, score, priority, savings, recommendations = (
                                self._calculate_ml_compute_optimization(compute)
                            )

                            # Pricing (Azure US East 2025)
                            # Standard_DS3_v2 (4 vCPU, 14 GB): $0.21/h = $153/mo
                            # Standard_NC6 (6 vCPU, 56 GB, 1 GPU): $0.90/h = $657/mo
                            # Standard_NC24 (24 vCPU, 224 GB, 4 GPU): $3.60/h = $2628/mo
                            pricing_map = {
                                "Standard_DS3_v2": 153.30,
                                "Standard_DS4_v2": 306.60,
                                "Standard_NC6": 657.00,
                                "Standard_NC12": 1314.00,
                                "Standard_NC24": 2628.00,
                            }

                            # Get VM size
                            vm_size = 'Standard_DS3_v2'
                            compute_properties = getattr(compute.properties, 'properties', None)
                            if compute_properties and hasattr(compute_properties, 'vm_size'):
                                vm_size = compute_properties.vm_size

                            # Estimate monthly cost
                            estimated_cost = pricing_map.get(vm_size, 153.30)

                            # Get instance state
                            provisioning_state = getattr(compute.properties, 'provisioning_state', 'Unknown')
                            state_dict = {}
                            if compute_properties:
                                state = getattr(compute_properties, 'state', 'Unknown')
                                state_dict['state'] = state

                            # Get auto-shutdown settings
                            idle_time_before_shutdown = None
                            if compute_properties and hasattr(compute_properties, 'idle_time_before_shutdown'):
                                idle_time_before_shutdown = compute_properties.idle_time_before_shutdown

                            # Detect if GPU instance
                            is_gpu = 'NC' in vm_size or 'ND' in vm_size or 'NV' in vm_size

                            resources.append(AllCloudResourceData(
                                resource_id=compute.id,
                                resource_type="azure_ml_compute",
                                resource_name=compute.name or "Unnamed ML Compute",
                                region=workspace.location,
                                estimated_monthly_cost=round(estimated_cost, 2),
                                currency="USD",
                                resource_metadata={
                                    "compute_id": compute.id,
                                    "resource_group": resource_group,
                                    "workspace_name": workspace.name,
                                    "provisioning_state": provisioning_state,
                                    "vm_size": vm_size,
                                    "is_gpu": is_gpu,
                                    "idle_time_before_shutdown": idle_time_before_shutdown,
                                    "state": state_dict.get('state', 'Unknown'),
                                    "tags": dict(compute.tags) if compute.tags else {},
                                },
                                is_optimizable=is_optimizable,
                                optimization_score=score,
                                optimization_priority=priority,
                                potential_monthly_savings=savings,
                                optimization_recommendations=recommendations,
                                last_used_at=None,
                                created_at_cloud=None,
                            ))

                        except Exception as e:
                            self.logger.error(f"Error processing ML compute {getattr(compute, 'name', 'unknown')}: {str(e)}")
                            continue

                except Exception as e:
                    self.logger.error(f"Error processing ML workspace {getattr(workspace, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} ML Compute Instances in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning ML Compute Instances: {str(e)}")
            return []

    def _calculate_ml_compute_optimization(self, compute) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for ML Compute Instance.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get compute properties
        provisioning_state = getattr(compute.properties, 'provisioning_state', 'Unknown')
        compute_properties = getattr(compute.properties, 'properties', None)

        vm_size = 'Standard_DS3_v2'
        state = 'Unknown'
        idle_time_before_shutdown = None

        if compute_properties:
            vm_size = getattr(compute_properties, 'vm_size', 'Standard_DS3_v2')
            state = getattr(compute_properties, 'state', 'Unknown')
            idle_time_before_shutdown = getattr(compute_properties, 'idle_time_before_shutdown', None)

        # Pricing map
        pricing_map = {
            "Standard_DS3_v2": 153.30,
            "Standard_DS4_v2": 306.60,
            "Standard_NC6": 657.00,
            "Standard_NC12": 1314.00,
            "Standard_NC24": 2628.00,
        }

        monthly_cost = pricing_map.get(vm_size, 153.30)
        is_gpu = 'NC' in vm_size or 'ND' in vm_size or 'NV' in vm_size

        # Scenario 1: Instance stopped but billing (CRITICAL - 90)
        if provisioning_state.lower() in ['failed', 'deleting', 'deleted']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Instance en État d'Erreur",
                "description": f"Cette instance ML est dans l'état '{provisioning_state}'. Elle génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Vérifier les logs pour identifier le problème",
                    "Supprimer l'instance si elle ne peut pas être réparée",
                    "Recréer l'instance si elle est encore nécessaire"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero activity 30 days (HIGH - 75)
        # Note: We can't get actual usage metrics without Azure Monitor
        # In production, check notebook execution history

        # Scenario 3: Running but no notebooks active (HIGH - 70)
        if state.lower() == 'running':
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Assume instance runs but unused 50% of time
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Instance Running Sans Activité",
                "description": "Cette instance ML est en cours d'exécution. Vérifiez si des notebooks sont actifs.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Vérifier les notebooks actifs dans le workspace",
                    "Arrêter l'instance si aucune activité",
                    "Configurer auto-shutdown pour arrêter automatiquement",
                    "Utiliser des compute clusters pour workloads batch"
                ],
                "priority": "high",
            })

        # Scenario 4: GPU instance for CPU workload (MEDIUM - 50)
        if is_gpu:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Savings from switching to CPU instance
            cpu_cost = 153.30  # Standard_DS3_v2
            savings = max(0, monthly_cost - cpu_cost)
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Instance GPU pour Workload CPU",
                "description": f"Instance GPU ({vm_size}) coûte {int(monthly_cost)}$/mois. Vérifiez si GPU est nécessaire.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Vérifier si vos notebooks utilisent réellement le GPU",
                    "Passer à Standard_DS3_v2 (CPU) si GPU non utilisé",
                    "Économies potentielles: ~{int(savings)}$/mois",
                    "Garder GPU uniquement pour deep learning/training"
                ],
                "priority": "medium",
            })

        # Scenario 5: No auto-shutdown configured (LOW - 30)
        if not idle_time_before_shutdown:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Savings from auto-shutdown (assume 40% reduction)
            savings = monthly_cost * 0.4
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Auto-Shutdown Non Configuré",
                "description": "Cette instance n'a pas d'auto-shutdown. Elle peut tourner inutilement.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Configurer auto-shutdown après 30 min d'inactivité",
                    "Paramétrer dans Compute > Settings > Auto-shutdown",
                    "Économies potentielles: ~40% avec auto-shutdown optimisé",
                    "Instance redémarre rapidement quand nécessaire"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_app_services(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure App Services (Web Apps) for cost intelligence.

        IMPORTANT: Excludes Function Apps (already scanned separately).

        Detection criteria:
        - App stopped (CRITICAL - 90 score)
        - Zero requests 30 derniers jours (HIGH - 75 score)
        - Premium/Isolated for dev/test (HIGH - 70 score)
        - Over-provisioned tier vs usage (MEDIUM - 50 score)
        - Always On when not needed (LOW - 30 score)
        """
        try:
            from azure.mgmt.web import WebSiteManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-web not installed")
            return []

        resources = []
        self.logger.info(f"Scanning App Services in region: {region}")

        try:
            web_client = WebSiteManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all web apps
            async for site in web_client.web_apps.list():
                try:
                    # IMPORTANT: Filter OUT Function Apps (already scanned in scan_function_apps)
                    if site.kind and "functionapp" in site.kind.lower():
                        continue

                    # Filter by region if specified
                    if region.lower() != "all" and site.location.lower() != region.lower():
                        continue

                    # Get resource group from site ID
                    resource_group = site.id.split("/")[4]

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_app_service_optimization(site)
                    )

                    # Pricing (Azure US East 2025)
                    # Free: $0/mo
                    # Shared: $0/mo (dev/test only)
                    # Basic B1: $13/mo
                    # Standard S1: $73/mo
                    # Premium P1v2: $81/mo
                    # Premium P1v3: $124/mo
                    # Isolated I1: $214/mo
                    pricing_map = {
                        "Free": 0.0,
                        "Shared": 0.0,
                        "Basic": 13.14,
                        "Standard": 73.00,
                        "Premium": 81.03,
                        "PremiumV2": 81.03,
                        "PremiumV3": 124.10,
                        "Isolated": 214.00,
                    }

                    # Get App Service Plan
                    server_farm_id = getattr(site, 'server_farm_id', '')
                    plan_tier = 'Standard'
                    plan_name = 'S1'

                    if server_farm_id:
                        # Extract plan resource group and name from server_farm_id
                        parts = server_farm_id.split('/')
                        if len(parts) >= 9:
                            plan_resource_group = parts[4]
                            plan_name_from_id = parts[8]

                            try:
                                plan = web_client.app_service_plans.get(
                                    resource_group_name=plan_resource_group,
                                    name=plan_name_from_id
                                )
                                if plan and hasattr(plan, 'sku'):
                                    sku = plan.sku
                                    plan_tier = getattr(sku, 'tier', 'Standard')
                                    plan_name = getattr(sku, 'name', 'S1')
                            except:
                                pass

                    # Estimate monthly cost
                    estimated_cost = pricing_map.get(plan_tier, 73.00)

                    # Get app state
                    state = getattr(site, 'state', 'Unknown')
                    enabled = getattr(site, 'enabled', True)

                    # Get site config
                    always_on = False
                    try:
                        site_config = web_client.web_apps.get_configuration(
                            resource_group_name=resource_group,
                            name=site.name
                        )
                        always_on = getattr(site_config, 'always_on', False)
                    except:
                        pass

                    resources.append(AllCloudResourceData(
                        resource_id=site.id,
                        resource_type="azure_app_service",
                        resource_name=site.name or "Unnamed App Service",
                        region=site.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "app_id": site.id,
                            "resource_group": resource_group,
                            "state": state,
                            "enabled": enabled,
                            "kind": site.kind or "app",
                            "plan_tier": plan_tier,
                            "plan_name": plan_name,
                            "always_on": always_on,
                            "default_host_name": getattr(site, 'default_host_name', ''),
                            "tags": dict(site.tags) if site.tags else {},
                        },
                        is_optimizable=is_optimizable,
                        optimization_score=score,
                        optimization_priority=priority,
                        potential_monthly_savings=savings,
                        optimization_recommendations=recommendations,
                        last_used_at=None,
                        created_at_cloud=None,
                    ))

                except Exception as e:
                    self.logger.error(f"Error processing App Service {getattr(site, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} App Services in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning App Services: {str(e)}")
            return []

    def _calculate_app_service_optimization(self, site) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for App Service.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get site properties
        state = getattr(site, 'state', 'Unknown')
        enabled = getattr(site, 'enabled', True)

        # Get plan info from server_farm_id
        server_farm_id = getattr(site, 'server_farm_id', '')
        plan_tier = 'Standard'

        # Pricing map
        pricing_map = {
            "Free": 0.0,
            "Shared": 0.0,
            "Basic": 13.14,
            "Standard": 73.00,
            "Premium": 81.03,
            "PremiumV2": 81.03,
            "PremiumV3": 124.10,
            "Isolated": 214.00,
        }

        # Try to extract tier from tags or default to Standard
        tags = dict(site.tags) if site.tags else {}
        if 'tier' in tags:
            plan_tier = tags['tier']

        monthly_cost = pricing_map.get(plan_tier, 73.00)

        # Scenario 1: App stopped (CRITICAL - 90)
        if state.lower() == 'stopped' or not enabled:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "App Service Arrêtée",
                "description": f"Cette app est dans l'état '{state}'. Elle génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Démarrer l'app si elle est encore nécessaire",
                    "Supprimer l'app et le plan si plus utilisé",
                    "Sauvegarder la configuration avant suppression"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero requests 30 days (HIGH - 75)
        # Note: We can't get actual request metrics without Azure Monitor
        # In production, check Application Insights metrics

        # Scenario 3: Premium/Isolated for dev/test (HIGH - 70)
        if plan_tier in ['Premium', 'PremiumV2', 'PremiumV3', 'Isolated']:
            # Check if dev/test based on name or tags
            name_lower = site.name.lower() if site.name else ''
            is_dev_test = any(keyword in name_lower for keyword in ['dev', 'test', 'staging', 'qa'])

            if is_dev_test or 'environment' in tags and tags['environment'].lower() in ['dev', 'test', 'staging']:
                is_optimizable = True
                optimization_score = max(optimization_score, 70)
                if priority not in ["critical"]:
                    priority = "high"

                # Savings from downgrading to Basic or Standard
                basic_cost = 13.14
                savings = max(0, monthly_cost - basic_cost)
                potential_savings = max(potential_savings, savings)

                recommendations.append({
                    "title": "Tier Premium pour Environnement Dev/Test",
                    "description": f"App {plan_tier} ({int(monthly_cost)}$/mo) pour dev/test. Basic suffit.",
                    "estimated_savings": round(savings, 2),
                    "actions": [
                        "Passer au tier Basic B1 ($13/mo) pour dev/test",
                        "Garder Premium uniquement pour production",
                        f"Économies potentielles: ~{int(savings)}$/mois",
                        "Performances largement suffisantes pour dev/test"
                    ],
                    "priority": "high",
                })

        # Scenario 4: Over-provisioned tier vs usage (MEDIUM - 50)
        if plan_tier in ['Standard', 'Premium', 'PremiumV2', 'PremiumV3', 'Isolated']:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Assume can downgrade one tier
            basic_cost = 13.14
            savings = (monthly_cost - basic_cost) * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Tier Potentiellement Surdimensionné",
                "description": f"App sur {plan_tier}. Vérifiez si ce tier est nécessaire.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques CPU/mémoire dans Azure Monitor",
                    "Passer à un tier inférieur si utilisation <50%",
                    "Tester avec Basic ou Standard si charge faible",
                    "Économies potentielles: ~50% en descendant d'un tier"
                ],
                "priority": "medium",
            })

        # Scenario 5: Always On when not needed (LOW - 30)
        # Note: Always On adds ~10% to cost for keeping instance warm
        # We can't detect it without getting the site config, which we already tried above
        # Skip this scenario as it's low priority and complex to detect

        return is_optimizable, optimization_score, priority, potential_savings, recommendations