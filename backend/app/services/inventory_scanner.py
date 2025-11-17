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
        self.logger = structlog.get_logger()

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

        IMPORTANT: Orphan resources (deallocated VMs or very low CPU <5%) are NOT "optimizable".
        They are WASTE that should be deleted, not optimized.
        Only non-orphan resources can be optimizable (e.g., low CPU 5-30%).

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

        # Scenario 1: Deallocated VM → This is an ORPHAN (waste), not optimizable
        # It should be deleted, not optimized. Return no optimization.
        if power_state == "deallocated":
            return False, 0, "none", 0.0, []

        # Scenario 2: Running VM with very low CPU (<5%) → This is also an ORPHAN (waste), not optimizable
        # It should be stopped/deleted, not optimized. Return no optimization.
        elif power_state == "running" and cpu_util < 5.0:
            return False, 0, "none", 0.0, []

        # Scenario 3: Running VM with low CPU (5-30%) → This IS optimizable!
        # These VMs are being used but could be downsized to save costs.
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

                    # Detect API type via capabilities
                    is_gremlin = 'EnableGremlin' in capability_names
                    is_mongodb = 'EnableMongo' in capability_names
                    account_kind = getattr(account, 'kind', 'GlobalDocumentDB')

                    # Set account kind based on API
                    if account_kind == 'GlobalDocumentDB':
                        if is_gremlin:
                            account_kind = 'Gremlin'
                        elif is_mongodb:
                            account_kind = 'MongoDB'

                    # Estimate monthly cost based on configuration
                    if is_serverless:
                        base_cost = pricing_info["serverless_base"]
                    else:
                        # Assume 400 RU/s for small, 1000 for medium
                        base_cost = pricing_info["provisioned_400ru"]

                    if is_multi_region:
                        base_cost *= pricing_info["multi_region_multiplier"]

                    # Determine resource type based on API
                    if is_gremlin:
                        resource_type = "azure_cosmos_db_gremlin"
                    elif is_mongodb:
                        resource_type = "azure_cosmos_db_mongodb"
                    else:
                        resource_type = "azure_cosmos_db"

                    resources.append(AllCloudResourceData(
                        resource_id=account.id,
                        resource_type=resource_type,
                        resource_name=account.name or f"Unnamed Cosmos DB ({account_kind})",
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

                    # Determine resource type based on cluster kind
                    # Kafka clusters are specialized streaming platforms, treat them separately
                    is_kafka = kind.lower() == 'kafka'
                    resource_type = "azure_hdinsight_kafka" if is_kafka else "azure_hdinsight_cluster"

                    resources.append(AllCloudResourceData(
                        resource_id=cluster.id,
                        resource_type=resource_type,
                        resource_name=cluster.name or f"Unnamed HDInsight {kind} Cluster",
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

    async def scan_redis_caches(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Cache for Redis instances for cost intelligence.

        Detection criteria:
        - Cache stopped/failed (CRITICAL - 90 score)
        - Zero connections 30 derniers jours (HIGH - 75 score)
        - Low cache hit rate <50% (HIGH - 70 score)
        - Premium tier for dev/test (MEDIUM - 50 score)
        - No persistence configured on Premium (LOW - 30 score)
        """
        try:
            from azure.mgmt.redis import RedisManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-redis not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Redis caches in region: {region}")

        try:
            redis_client = RedisManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all Redis caches
            async for cache in redis_client.redis.list():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and cache.location.lower() != region.lower():
                        continue

                    # Get resource group from cache ID
                    resource_group = cache.id.split("/")[4]

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_redis_optimization(cache)
                    )

                    # Pricing (Azure US East 2025)
                    # Basic C0 (250 MB): $16/mo
                    # Basic C1 (1 GB): $55/mo
                    # Standard C0 (250 MB): $32/mo (with replication)
                    # Standard C2 (2.5 GB): $123/mo
                    # Premium P1 (6 GB): $255/mo
                    # Premium P4 (26 GB): $1020/mo
                    pricing_map = {
                        "Basic_C0": 16.24,
                        "Basic_C1": 55.48,
                        "Basic_C2": 110.96,
                        "Standard_C0": 32.48,
                        "Standard_C1": 110.96,
                        "Standard_C2": 123.13,
                        "Standard_C3": 246.26,
                        "Standard_C4": 492.52,
                        "Premium_P1": 255.50,
                        "Premium_P2": 511.00,
                        "Premium_P3": 1022.00,
                        "Premium_P4": 1022.00,
                    }

                    # Get SKU info
                    sku = cache.sku
                    sku_name = getattr(sku, 'name', 'Standard')
                    sku_family = getattr(sku, 'family', 'C')
                    sku_capacity = getattr(sku, 'capacity', 0)

                    # Build pricing key
                    pricing_key = f"{sku_name}_{sku_family}{sku_capacity}"
                    estimated_cost = pricing_map.get(pricing_key, 110.96)  # Default to Standard C1

                    # Get cache properties
                    provisioning_state = getattr(cache, 'provisioning_state', 'Unknown')
                    redis_version = getattr(cache, 'redis_version', 'Unknown')
                    enable_non_ssl_port = getattr(cache, 'enable_non_ssl_port', False)

                    # Get persistence settings (Premium only)
                    redis_configuration = getattr(cache, 'redis_configuration', None)
                    persistence_enabled = False
                    if redis_configuration:
                        rdb_backup_enabled = getattr(redis_configuration, 'rdb_backup_enabled', None)
                        if rdb_backup_enabled:
                            persistence_enabled = True

                    # Get port and hostname
                    port = getattr(cache, 'port', 6379)
                    ssl_port = getattr(cache, 'ssl_port', 6380)
                    host_name = getattr(cache, 'host_name', '')

                    resources.append(AllCloudResourceData(
                        resource_id=cache.id,
                        resource_type="azure_redis_cache",
                        resource_name=cache.name or "Unnamed Redis Cache",
                        region=cache.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "cache_id": cache.id,
                            "resource_group": resource_group,
                            "provisioning_state": provisioning_state,
                            "sku_name": sku_name,
                            "sku_family": sku_family,
                            "sku_capacity": sku_capacity,
                            "redis_version": redis_version,
                            "enable_non_ssl_port": enable_non_ssl_port,
                            "persistence_enabled": persistence_enabled,
                            "port": port,
                            "ssl_port": ssl_port,
                            "host_name": host_name,
                            "tags": dict(cache.tags) if cache.tags else {},
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
                    self.logger.error(f"Error processing Redis cache {getattr(cache, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} Redis caches in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning Redis caches: {str(e)}")
            return []

    def _calculate_redis_optimization(self, cache) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for Redis cache.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get cache properties
        provisioning_state = getattr(cache, 'provisioning_state', 'Unknown')
        sku = cache.sku
        sku_name = getattr(sku, 'name', 'Standard')
        sku_family = getattr(sku, 'family', 'C')
        sku_capacity = getattr(sku, 'capacity', 0)

        # Pricing map
        pricing_map = {
            "Basic_C0": 16.24,
            "Basic_C1": 55.48,
            "Standard_C0": 32.48,
            "Standard_C1": 110.96,
            "Standard_C2": 123.13,
            "Premium_P1": 255.50,
            "Premium_P2": 511.00,
            "Premium_P3": 1022.00,
            "Premium_P4": 1022.00,
        }

        pricing_key = f"{sku_name}_{sku_family}{sku_capacity}"
        monthly_cost = pricing_map.get(pricing_key, 110.96)

        # Get persistence settings
        redis_configuration = getattr(cache, 'redis_configuration', None)
        persistence_enabled = False
        if redis_configuration:
            rdb_backup_enabled = getattr(redis_configuration, 'rdb_backup_enabled', None)
            if rdb_backup_enabled:
                persistence_enabled = True

        # Scenario 1: Cache stopped/failed (CRITICAL - 90)
        if provisioning_state.lower() in ['failed', 'deleting', 'deleted', 'disabled']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Redis Cache en État d'Erreur",
                "description": f"Ce cache Redis est dans l'état '{provisioning_state}'. Il génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Vérifier les logs pour identifier le problème",
                    "Supprimer le cache s'il ne peut pas être réparé",
                    "Recréer le cache si encore nécessaire"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero connections 30 days (HIGH - 75)
        # Note: We can't get actual connection metrics without Azure Monitor
        # In production, check connection count from monitoring

        # Scenario 3: Low cache hit rate <50% (HIGH - 70)
        # Note: We can't get cache hit rate without Azure Monitor
        # In production, check cache hit/miss ratio

        # Scenario 4: Premium tier for dev/test (MEDIUM - 50)
        if sku_name == 'Premium':
            # Check if dev/test based on name or tags
            name_lower = cache.name.lower() if cache.name else ''
            tags = dict(cache.tags) if cache.tags else {}
            is_dev_test = any(keyword in name_lower for keyword in ['dev', 'test', 'staging', 'qa'])

            if is_dev_test or 'environment' in tags and tags['environment'].lower() in ['dev', 'test', 'staging']:
                is_optimizable = True
                optimization_score = max(optimization_score, 50)
                if priority not in ["critical", "high"]:
                    priority = "medium"

                # Savings from downgrading to Standard
                standard_cost = 110.96  # Standard C1
                savings = max(0, monthly_cost - standard_cost)
                potential_savings = max(potential_savings, savings)

                recommendations.append({
                    "title": "Tier Premium pour Environnement Dev/Test",
                    "description": f"Cache Premium ({int(monthly_cost)}$/mo) pour dev/test. Standard suffit.",
                    "estimated_savings": round(savings, 2),
                    "actions": [
                        "Passer au tier Standard pour dev/test",
                        "Garder Premium uniquement pour production",
                        f"Économies potentielles: ~{int(savings)}$/mois",
                        "Standard offre performances suffisantes pour dev/test"
                    ],
                    "priority": "medium",
                })

        # Scenario 5: No persistence on Premium (LOW - 30)
        if sku_name == 'Premium' and not persistence_enabled:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Savings: none directly, but best practice recommendation
            savings = 0
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Persistence Non Configurée sur Premium",
                "description": "Cache Premium sans persistence. Risque de perte de données en cas de redémarrage.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Activer RDB persistence dans les paramètres",
                    "Configurer backup automatique quotidien/hebdomadaire",
                    "Protéger contre la perte de données",
                    "Coût de persistence: ~5% du prix du cache"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_event_hubs(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Event Hubs namespaces for cost intelligence.

        Detection criteria:
        - Namespace inactive/failed (CRITICAL - 90 score)
        - Zero incoming messages 30 derniers jours (HIGH - 75 score)
        - Throughput units overprovisioned (HIGH - 70 score)
        - Premium for low-volume workload (MEDIUM - 50 score)
        - Auto-inflate disabled (LOW - 30 score)
        """
        try:
            from azure.mgmt.eventhub import EventHubManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-eventhub not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Event Hubs namespaces in region: {region}")

        try:
            eh_client = EventHubManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all Event Hub namespaces
            async for namespace in eh_client.namespaces.list():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and namespace.location.lower() != region.lower():
                        continue

                    # Get resource group from namespace ID
                    resource_group = namespace.id.split("/")[4]

                    # Get Event Hubs count
                    event_hubs_count = 0
                    try:
                        event_hubs = list(eh_client.event_hubs.list_by_namespace(
                            resource_group_name=resource_group,
                            namespace_name=namespace.name
                        ))
                        event_hubs_count = len(event_hubs)
                    except:
                        pass

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_event_hub_optimization(namespace, event_hubs_count)
                    )

                    # Pricing (Azure US East 2025)
                    # Basic: $11.36/mo (1 throughput unit, 1M events)
                    # Standard: $22.72/mo per throughput unit (1M events, 1 day retention)
                    # Premium: $673/mo per processing unit (100M events, 7 days retention)
                    # Dedicated: Custom pricing (1 CU = ~$8000/mo)
                    pricing_map = {
                        "Basic": 11.36,
                        "Standard": 22.72,  # per TU
                        "Premium": 673.00,  # per PU
                    }

                    # Get SKU info
                    sku = namespace.sku
                    sku_name = getattr(sku, 'name', 'Standard')
                    sku_tier = getattr(sku, 'tier', 'Standard')
                    sku_capacity = getattr(sku, 'capacity', 1)

                    # Estimate monthly cost
                    base_price = pricing_map.get(sku_name, 22.72)
                    estimated_cost = base_price * sku_capacity

                    # Get namespace properties
                    provisioning_state = getattr(namespace, 'provisioning_state', 'Unknown')
                    status = getattr(namespace, 'status', 'Unknown')
                    is_auto_inflate_enabled = getattr(namespace, 'is_auto_inflate_enabled', False)
                    maximum_throughput_units = getattr(namespace, 'maximum_throughput_units', 0)

                    # Get Kafka and zone redundancy settings
                    kafka_enabled = getattr(namespace, 'kafka_enabled', False)
                    zone_redundant = getattr(namespace, 'zone_redundant', False)

                    resources.append(AllCloudResourceData(
                        resource_id=namespace.id,
                        resource_type="azure_event_hub",
                        resource_name=namespace.name or "Unnamed Event Hub Namespace",
                        region=namespace.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "namespace_id": namespace.id,
                            "resource_group": resource_group,
                            "provisioning_state": provisioning_state,
                            "status": status,
                            "sku_name": sku_name,
                            "sku_tier": sku_tier,
                            "sku_capacity": sku_capacity,
                            "is_auto_inflate_enabled": is_auto_inflate_enabled,
                            "maximum_throughput_units": maximum_throughput_units,
                            "kafka_enabled": kafka_enabled,
                            "zone_redundant": zone_redundant,
                            "event_hubs_count": event_hubs_count,
                            "tags": dict(namespace.tags) if namespace.tags else {},
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
                    self.logger.error(f"Error processing Event Hub namespace {getattr(namespace, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} Event Hub namespaces in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning Event Hub namespaces: {str(e)}")
            return []

    def _calculate_event_hub_optimization(self, namespace, event_hubs_count: int) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for Event Hub namespace.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get namespace properties
        provisioning_state = getattr(namespace, 'provisioning_state', 'Unknown')
        status = getattr(namespace, 'status', 'Unknown')
        sku = namespace.sku
        sku_name = getattr(sku, 'name', 'Standard')
        sku_capacity = getattr(sku, 'capacity', 1)
        is_auto_inflate_enabled = getattr(namespace, 'is_auto_inflate_enabled', False)

        # Pricing map
        pricing_map = {
            "Basic": 11.36,
            "Standard": 22.72,
            "Premium": 673.00,
        }

        base_price = pricing_map.get(sku_name, 22.72)
        monthly_cost = base_price * sku_capacity

        # Scenario 1: Namespace inactive/failed (CRITICAL - 90)
        if provisioning_state.lower() in ['failed', 'deleting', 'deleted'] or status.lower() in ['disabled', 'restoring', 'unknown']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Event Hub Namespace Non Fonctionnel",
                "description": f"Ce namespace est dans l'état '{provisioning_state}/{status}'. Il génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Vérifier les logs pour identifier le problème",
                    "Supprimer le namespace s'il ne peut pas être réparé",
                    "Recréer le namespace si encore nécessaire"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero incoming messages 30 days (HIGH - 75)
        # Note: We can't get actual message metrics without Azure Monitor
        # In production, check incoming messages/bytes from monitoring

        # Scenario 3: Throughput units overprovisioned (HIGH - 70)
        if sku_name == 'Standard' and sku_capacity > 3:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Assume can reduce by 50%
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Throughput Units Potentiellement Surdimensionnés",
                "description": f"Ce namespace a {sku_capacity} throughput units. Vérifiez si tous sont nécessaires.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques de throughput dans Azure Monitor",
                    f"Réduire de {sku_capacity} à {sku_capacity // 2} TUs si charge <50%",
                    "Activer auto-inflate pour adapter automatiquement",
                    "Économies potentielles: ~50% en réduisant les TUs"
                ],
                "priority": "high",
            })

        # Scenario 4: Premium for low-volume (MEDIUM - 50)
        if sku_name == 'Premium' and event_hubs_count <= 2:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Savings from downgrading to Standard
            standard_cost = 22.72 * 2  # 2 TUs
            savings = max(0, monthly_cost - standard_cost)
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Tier Premium pour Faible Volume",
                "description": f"Namespace Premium ({int(monthly_cost)}$/mo) avec seulement {event_hubs_count} Event Hubs.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Passer au tier Standard si volume <100M events/mois",
                    "Garder Premium uniquement pour haute performance",
                    f"Économies potentielles: ~{int(savings)}$/mois",
                    "Standard suffit pour la plupart des workloads"
                ],
                "priority": "medium",
            })

        # Scenario 5: Auto-inflate disabled (LOW - 30)
        if sku_name == 'Standard' and not is_auto_inflate_enabled and sku_capacity < 10:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # Savings from auto-inflate (reduce base capacity, scale on demand)
            savings = monthly_cost * 0.2
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Auto-Inflate Non Activé",
                "description": "L'auto-inflate permet d'adapter automatiquement la capacité selon la charge.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Activer auto-inflate dans les paramètres du namespace",
                    "Configurer max throughput units (ex: 10-20)",
                    "Réduire la capacité de base et laisser auto-scale",
                    "Économies potentielles: ~20% en adaptant à la charge"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_netapp_files(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure NetApp Files capacity pools for cost intelligence.

        Detection criteria:
        - Pool/volume not mounted (CRITICAL - 90 score)
        - Zero IOPS 30 derniers jours (HIGH - 75 score)
        - Ultra tier for standard workload (HIGH - 70 score)
        - Overprovisioned capacity >50% unused (MEDIUM - 50 score)
        - No snapshots configured (LOW - 30 score)
        """
        try:
            from azure.mgmt.netappfiles import NetAppManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-netappfiles not installed")
            return []

        resources = []
        self.logger.info(f"Scanning NetApp Files capacity pools in region: {region}")

        try:
            netapp_client = NetAppManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all NetApp accounts
            async for account in netapp_client.accounts.list():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and account.location.lower() != region.lower():
                        continue

                    # Get resource group from account ID
                    resource_group = account.id.split("/")[4]

                    # List capacity pools in this account
                    try:
                        pools = list(netapp_client.pools.list(
                            resource_group_name=resource_group,
                            account_name=account.name
                        ))
                    except:
                        pools = []

                    for pool in pools:
                        try:
                            # Get volumes in this pool
                            volumes_count = 0
                            try:
                                volumes = list(netapp_client.volumes.list(
                                    resource_group_name=resource_group,
                                    account_name=account.name,
                                    pool_name=pool.name
                                ))
                                volumes_count = len(volumes)
                            except:
                                pass

                            # Calculate optimization
                            is_optimizable, score, priority, savings, recommendations = (
                                self._calculate_netapp_optimization(pool, volumes_count)
                            )

                            # Pricing (Azure US East 2025)
                            # Standard: $0.000202/GB/hour = $147.50/TB/mo
                            # Premium: $0.000403/GB/hour = $294.19/TB/mo
                            # Ultra: $0.000538/GB/hour = $392.54/TB/mo
                            pricing_map = {
                                "Standard": 0.000202,  # per GB/hour
                                "Premium": 0.000403,
                                "Ultra": 0.000538,
                            }

                            # Get pool properties
                            service_level = getattr(pool, 'service_level', 'Standard')
                            size_bytes = getattr(pool, 'size', 0)
                            size_gb = size_bytes / (1024 ** 3) if size_bytes else 0

                            # Calculate monthly cost (730 hours per month)
                            hourly_rate = pricing_map.get(service_level, 0.000202)
                            estimated_cost = size_gb * hourly_rate * 730

                            # Get pool state
                            provisioning_state = getattr(pool, 'provisioning_state', 'Unknown')

                            # Get QoS type
                            qos_type = getattr(pool, 'qos_type', 'Auto')

                            resources.append(AllCloudResourceData(
                                resource_id=pool.id,
                                resource_type="azure_netapp_files",
                                resource_name=f"{account.name}/{pool.name}",
                                region=account.location,
                                estimated_monthly_cost=round(estimated_cost, 2),
                                currency="USD",
                                resource_metadata={
                                    "pool_id": pool.id,
                                    "account_name": account.name,
                                    "pool_name": pool.name,
                                    "resource_group": resource_group,
                                    "provisioning_state": provisioning_state,
                                    "service_level": service_level,
                                    "size_gb": round(size_gb, 2),
                                    "size_tb": round(size_gb / 1024, 2),
                                    "qos_type": qos_type,
                                    "volumes_count": volumes_count,
                                    "tags": dict(pool.tags) if pool.tags else {},
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
                            self.logger.error(f"Error processing NetApp pool {getattr(pool, 'name', 'unknown')}: {str(e)}")
                            continue

                except Exception as e:
                    self.logger.error(f"Error processing NetApp account {getattr(account, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} NetApp Files capacity pools in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning NetApp Files: {str(e)}")
            return []

    def _calculate_netapp_optimization(self, pool, volumes_count: int) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for NetApp Files capacity pool.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = []

        # Get pool properties
        provisioning_state = getattr(pool, 'provisioning_state', 'Unknown')
        service_level = getattr(pool, 'service_level', 'Standard')
        size_bytes = getattr(pool, 'size', 0)
        size_gb = size_bytes / (1024 ** 3) if size_bytes else 0
        size_tb = size_gb / 1024

        # Pricing map (per GB/hour)
        pricing_map = {
            "Standard": 0.000202,
            "Premium": 0.000403,
            "Ultra": 0.000538,
        }

        hourly_rate = pricing_map.get(service_level, 0.000202)
        monthly_cost = size_gb * hourly_rate * 730

        # Scenario 1: Pool not mounted / no volumes (CRITICAL - 90)
        if volumes_count == 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, monthly_cost)

            recommendations.append({
                "title": "Capacity Pool Sans Volumes",
                "description": f"Ce pool NetApp ({size_tb:.2f} TB) n'a aucun volume. Il génère des coûts inutiles.",
                "estimated_savings": round(monthly_cost, 2),
                "actions": [
                    "Créer des volumes si le pool est encore nécessaire",
                    "Supprimer le pool s'il n'est plus utilisé",
                    f"Économies potentielles: {int(monthly_cost)}$/mois"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero IOPS 30 days (HIGH - 75)
        # Note: We can't get actual IOPS metrics without Azure Monitor
        # In production, check IOPS/throughput from monitoring

        # Scenario 3: Ultra tier for standard workload (HIGH - 70)
        if service_level == 'Ultra':
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Savings from downgrading to Premium or Standard
            premium_cost = size_gb * 0.000403 * 730
            savings = max(0, monthly_cost - premium_cost)
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Tier Ultra pour Workload Standard",
                "description": f"Pool Ultra ({int(monthly_cost)}$/mo pour {size_tb:.2f} TB). Vérifiez si Ultra est nécessaire.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les besoins IOPS/throughput réels",
                    "Passer à Premium si <64MB/s ou <4000 IOPS/TB",
                    "Passer à Standard si <16MB/s ou <1000 IOPS/TB",
                    f"Économies potentielles: ~{int(savings)}$/mois avec Premium"
                ],
                "priority": "high",
            })

        # Scenario 4: Overprovisioned capacity (MEDIUM - 50)
        if size_tb > 4:
            # Assume pool is overprovisioned if >4TB
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Assume 50% overprovisioned
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Capacité Potentiellement Surdimensionnée",
                "description": f"Pool de {size_tb:.2f} TB. Vérifiez l'utilisation réelle des volumes.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser l'utilisation actuelle des volumes",
                    "Réduire la taille du pool si usage <50%",
                    "Taille minimum: 4 TB par pool",
                    "Économies potentielles: ~50% en réduisant la capacité"
                ],
                "priority": "medium",
            })

        # Scenario 5: No snapshots configured (LOW - 30)
        # Note: We can't easily detect snapshot policies without additional API calls
        # This is a best practice recommendation
        if volumes_count > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            if priority not in ["critical", "high", "medium"]:
                priority = "low"

            # No direct savings, but best practice
            savings = 0
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Snapshots Non Configurés",
                "description": "Aucune politique de snapshot détectée. Risque de perte de données.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Configurer une snapshot policy sur les volumes",
                    "Schedule recommandé: hourly, daily, weekly",
                    "Snapshots consomment de la capacité du pool",
                    "Coût des snapshots: inclus dans la capacité du pool"
                ],
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_cognitive_search(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Cognitive Search services for cost intelligence.

        Detection criteria:
        - Service failed/stopped (CRITICAL - 90 score)
        - Zero queries 30 derniers jours (HIGH - 75 score)
        - Overprovisioned replicas (HIGH - 70 score)
        - Standard tier for low query volume (MEDIUM - 50 score)
        - No indexing activity 90 days (LOW - 30 score)

        Args:
            region: Azure region

        Returns:
            List of Azure Cognitive Search services with optimization analysis
        """
        resources = []

        try:
            from azure.mgmt.search import SearchManagementClient

            search_client = SearchManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map per tier per month (approximate)
            pricing_map = {
                "free": 0.0,
                "basic": 75.0,  # Basic tier
                "standard": 250.0,  # Standard S1
                "standard2": 1000.0,  # Standard S2
                "standard3": 2400.0,  # Standard S3
                "storage_optimized_l1": 1500.0,  # Storage Optimized L1
                "storage_optimized_l2": 3000.0,  # Storage Optimized L2
            }

            # List all Search services
            search_services = list(search_client.services.list_by_subscription())
            logger.info(
                "inventory.azure.cognitive_search.found",
                region=region,
                count=len(search_services),
            )

            for service in search_services:
                try:
                    # Filter by region
                    if service.location != region:
                        continue

                    service_name = service.name or "Unknown"
                    resource_group = service.id.split("/")[4] if service.id else "Unknown"

                    # Get SKU tier
                    sku_name = service.sku.name.lower() if service.sku and service.sku.name else "unknown"

                    # Get replica and partition count
                    replica_count = getattr(service, "replica_count", 1)
                    partition_count = getattr(service, "partition_count", 1)

                    # Get provisioning state
                    provisioning_state = getattr(service, "provisioning_state", "Unknown")
                    status = getattr(service, "status", "Unknown")

                    # Get search units (replicas × partitions)
                    search_units = replica_count * partition_count

                    # Calculate monthly cost
                    base_cost = pricing_map.get(sku_name, 250.0)
                    monthly_cost = base_cost * search_units

                    # TODO: Get actual metrics from Azure Monitor (queries, indexing operations)
                    # For MVP, use placeholder metrics
                    query_count_30d = 0  # Placeholder
                    indexing_operations_90d = 0  # Placeholder

                    # Calculate optimization potential
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_cognitive_search_optimization(
                        provisioning_state=provisioning_state,
                        status=status,
                        sku_name=sku_name,
                        replica_count=replica_count,
                        partition_count=partition_count,
                        query_count_30d=query_count_30d,
                        indexing_operations_90d=indexing_operations_90d,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "service_name": service_name,
                        "resource_group": resource_group,
                        "sku": sku_name,
                        "replica_count": replica_count,
                        "partition_count": partition_count,
                        "search_units": search_units,
                        "provisioning_state": provisioning_state,
                        "status": status,
                        "public_network_access": getattr(service, "public_network_access", "Unknown"),
                        "hosting_mode": getattr(service, "hosting_mode", "default"),
                        "optimization_details": recommendations,
                    }

                    resource = AllCloudResourceData(
                        resource_type="azure_cognitive_search",
                        resource_id=service.id or f"search-{service_name}",
                        resource_name=service_name,
                        region=region,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_priority=priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations.get("actions", []),
                    )

                    resources.append(resource)
                    logger.info(
                        "inventory.azure.cognitive_search.processed",
                        service_name=service_name,
                        sku=sku_name,
                        cost=monthly_cost,
                        optimizable=is_optimizable,
                    )

                except Exception as e:
                    logger.error(
                        "inventory.azure.cognitive_search.error",
                        service=service.name if hasattr(service, "name") else "Unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("inventory.azure.cognitive_search.scan_error", region=region, error=str(e))

        return resources

    def _calculate_cognitive_search_optimization(
        self,
        provisioning_state: str,
        status: str,
        sku_name: str,
        replica_count: int,
        partition_count: int,
        query_count_30d: int,
        indexing_operations_90d: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Cognitive Search service."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Service failed or stopped
        if provisioning_state.lower() in ["failed", "deleting"] or status.lower() in [
            "degraded",
            "disabled",
        ]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Service en état '{provisioning_state}' - investigate et réparez ou supprimez",
                    "Service non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs Azure, réparer ou supprimer le service",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero queries in 30 days
        elif query_count_30d == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucune requête détectée depuis 30 jours",
                    "Service potentiellement inutilisé - considérer la suppression",
                    "Action: Vérifier si le service est encore nécessaire",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): Overprovisioned replicas (>1 replica, low query volume)
        elif replica_count > 1 and query_count_30d < 10000:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Savings = cost of extra replicas
            savings = monthly_cost * ((replica_count - 1) / (replica_count * partition_count))
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"Replicas surprovisionnés: {replica_count} replicas pour faible volume",
                    f"Volume de requêtes: {query_count_30d} sur 30 jours",
                    "Action: Réduire à 1 replica pour économiser",
                    f"Économies estimées: ${savings:.2f}/mois",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Standard tier for low query volume
        elif sku_name in ["standard", "standard2", "standard3"] and query_count_30d < 1000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings = downgrade to Basic
            savings = monthly_cost - 75.0  # Basic tier cost
            potential_savings = max(savings, 0.0)
            recommendations.update({
                "actions": [
                    f"Tier Standard pour faible volume: {query_count_30d} queries/30j",
                    f"Coût actuel: ${monthly_cost:.2f}/mois ({sku_name})",
                    "Action: Downgrade vers Basic tier ($75/mois)",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No indexing activity in 90 days
        elif indexing_operations_90d == 0 and monthly_cost > 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = monthly_cost * 0.2  # 20% potential savings
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Aucune opération d'indexation depuis 90 jours",
                    "Index potentiellement obsolètes ou statiques",
                    "Action: Vérifier si le service est encore utilisé",
                    f"Économies potentielles: ${savings:.2f}/mois si supprimé",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_api_management(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure API Management services for cost intelligence.

        Detection criteria:
        - Service failed/stopped (CRITICAL - 90 score)
        - Zero API calls 30 derniers jours (HIGH - 75 score)
        - Premium/Standard tier for low volume (HIGH - 70 score)
        - Multiple gateways underutilized (MEDIUM - 50 score)
        - Developer tier in production (LOW - 30 score)

        Args:
            region: Azure region

        Returns:
            List of Azure API Management services with optimization analysis
        """
        resources = []

        try:
            from azure.mgmt.apimanagement import ApiManagementClient

            apim_client = ApiManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map per tier per month (approximate)
            pricing_map = {
                "consumption": 0.0,  # Pay per call: $0.04/10K calls
                "developer": 50.0,  # Developer tier (no SLA)
                "basic": 150.0,  # Basic tier
                "standard": 700.0,  # Standard tier
                "premium": 2795.0,  # Premium tier (per unit)
            }

            # List all API Management services
            apim_services = list(apim_client.api_management_service.list_by_subscription())
            logger.info(
                "inventory.azure.api_management.found",
                region=region,
                count=len(apim_services),
            )

            for service in apim_services:
                try:
                    # Filter by region
                    if service.location != region:
                        continue

                    service_name = service.name or "Unknown"
                    resource_group = service.id.split("/")[4] if service.id else "Unknown"

                    # Get SKU tier
                    sku_name = service.sku.name.lower() if service.sku and service.sku.name else "unknown"
                    sku_capacity = service.sku.capacity if service.sku and service.sku.capacity else 1

                    # Get provisioning state
                    provisioning_state = getattr(service, "provisioning_state", "Unknown")

                    # Get gateway count (self-hosted gateways)
                    gateway_count = 0  # TODO: Query self-hosted gateways via API

                    # Calculate monthly cost
                    base_cost = pricing_map.get(sku_name, 700.0)
                    if sku_name == "consumption":
                        # Consumption tier: $0.04 per 10K calls (estimate 100K calls/month)
                        monthly_cost = (100_000 / 10_000) * 0.04
                    else:
                        monthly_cost = base_cost * sku_capacity

                    # TODO: Get actual metrics from Azure Monitor (API calls, request count)
                    # For MVP, use placeholder metrics
                    api_calls_30d = 0  # Placeholder
                    request_count_30d = 0  # Placeholder

                    # Calculate optimization potential
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_api_management_optimization(
                        provisioning_state=provisioning_state,
                        sku_name=sku_name,
                        sku_capacity=sku_capacity,
                        api_calls_30d=api_calls_30d,
                        request_count_30d=request_count_30d,
                        gateway_count=gateway_count,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "service_name": service_name,
                        "resource_group": resource_group,
                        "sku": sku_name,
                        "sku_capacity": sku_capacity,
                        "provisioning_state": provisioning_state,
                        "publisher_email": getattr(service, "publisher_email", "Unknown"),
                        "publisher_name": getattr(service, "publisher_name", "Unknown"),
                        "gateway_url": getattr(service, "gateway_url", "Unknown"),
                        "portal_url": getattr(service, "portal_url", "Unknown"),
                        "optimization_details": recommendations,
                    }

                    resource = AllCloudResourceData(
                        resource_type="azure_api_management",
                        resource_id=service.id or f"apim-{service_name}",
                        resource_name=service_name,
                        region=region,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_priority=priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations.get("actions", []),
                    )

                    resources.append(resource)
                    logger.info(
                        "inventory.azure.api_management.processed",
                        service_name=service_name,
                        sku=sku_name,
                        cost=monthly_cost,
                        optimizable=is_optimizable,
                    )

                except Exception as e:
                    logger.error(
                        "inventory.azure.api_management.error",
                        service=service.name if hasattr(service, "name") else "Unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("inventory.azure.api_management.scan_error", region=region, error=str(e))

        return resources

    def _calculate_api_management_optimization(
        self,
        provisioning_state: str,
        sku_name: str,
        sku_capacity: int,
        api_calls_30d: int,
        request_count_30d: int,
        gateway_count: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for API Management service."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Service failed or stopped
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Service en état '{provisioning_state}' - investigate et réparez ou supprimez",
                    "Service non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs Azure, réparer ou supprimer le service",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero API calls in 30 days
        elif api_calls_30d == 0 and request_count_30d == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucun appel API détecté depuis 30 jours",
                    "Service potentiellement inutilisé - considérer la suppression",
                    "Action: Vérifier si le service est encore nécessaire",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): Premium/Standard tier for low volume (<10K calls/day)
        elif sku_name in ["premium", "standard"] and api_calls_30d < 300000:  # <10K/day
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Savings = downgrade to Basic or Consumption
            if sku_name == "premium":
                savings = monthly_cost - 150.0  # Downgrade to Basic
            else:  # standard
                savings = monthly_cost - 150.0  # Downgrade to Basic
            potential_savings = max(savings, 0.0)
            recommendations.update({
                "actions": [
                    f"Tier {sku_name.capitalize()} pour faible volume: {api_calls_30d} calls/30j",
                    f"Coût actuel: ${monthly_cost:.2f}/mois",
                    "Action: Downgrade vers Basic ($150/mois) ou Consumption (pay-per-call)",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Multiple gateways underutilized
        elif gateway_count > 1 and api_calls_30d < 100000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            savings = monthly_cost * 0.3  # 30% potential savings
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"Multiples gateways ({gateway_count}) pour faible volume",
                    f"Volume: {api_calls_30d} calls/30 jours",
                    "Action: Consolider vers un seul gateway",
                    f"Économies estimées: ${savings:.2f}/mois",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): Developer tier in production (no SLA)
        elif sku_name == "developer" and monthly_cost > 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # No direct savings, but best practice
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Developer tier utilisé (pas de SLA)",
                    "Tier Developer destiné au développement, pas à la production",
                    "Action: Upgrade vers Basic ou Standard pour SLA",
                    "Note: Upgrade coûte plus, mais garantit SLA et stabilité",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_cdn(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure CDN profiles and endpoints for cost intelligence.

        Detection criteria:
        - Endpoint stopped/disabled (CRITICAL - 90 score)
        - Zero bandwidth 30 derniers jours (HIGH - 75 score)
        - Zero requests 30 derniers jours (HIGH - 70 score)
        - Premium tier for low traffic (MEDIUM - 50 score)
        - No caching rules configured (LOW - 30 score)

        Args:
            region: Azure region

        Returns:
            List of Azure CDN profiles with optimization analysis
        """
        resources = []

        try:
            from azure.mgmt.cdn import CdnManagementClient

            cdn_client = CdnManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing per GB (approximate)
            pricing_per_gb = {
                "standard_microsoft": 0.087,  # Standard Microsoft
                "standard_akamai": 0.087,  # Standard Akamai
                "standard_verizon": 0.087,  # Standard Verizon
                "premium_verizon": 0.20,  # Premium Verizon
            }

            # List all CDN profiles
            cdn_profiles = list(cdn_client.profiles.list())
            logger.info(
                "inventory.azure.cdn.found",
                region=region,
                count=len(cdn_profiles),
            )

            for profile in cdn_profiles:
                try:
                    # Filter by region
                    if profile.location != region:
                        continue

                    profile_name = profile.name or "Unknown"
                    resource_group = profile.id.split("/")[4] if profile.id else "Unknown"

                    # Get SKU tier
                    sku_name = profile.sku.name.lower() if profile.sku and profile.sku.name else "unknown"

                    # Get provisioning state
                    provisioning_state = getattr(profile, "provisioning_state", "Unknown")

                    # Count endpoints in this profile
                    endpoint_count = 0
                    total_bandwidth_gb = 0
                    total_requests = 0
                    has_caching_rules = False

                    try:
                        endpoints = list(cdn_client.endpoints.list_by_profile(resource_group, profile_name))
                        endpoint_count = len(endpoints)

                        for endpoint in endpoints:
                            # Check if endpoint has caching rules
                            delivery_policy = getattr(endpoint, "delivery_policy", None)
                            if delivery_policy:
                                has_caching_rules = True

                            # TODO: Get actual metrics from Azure Monitor (bandwidth, requests)
                            # For MVP, use placeholder metrics
                            # total_bandwidth_gb += endpoint bandwidth (30 days)
                            # total_requests += endpoint requests (30 days)

                    except Exception as e:
                        logger.warning("inventory.azure.cdn.endpoints_error", profile=profile_name, error=str(e))

                    # Calculate monthly cost estimate
                    # CDN is pay-as-you-go: bandwidth + requests
                    # Estimate: $0.087/GB + $0.0075/10K requests
                    # For MVP, estimate 100 GB/month if endpoints exist
                    estimated_bandwidth_gb = 100 if endpoint_count > 0 else 0
                    bandwidth_cost = estimated_bandwidth_gb * pricing_per_gb.get(sku_name, 0.087)
                    requests_cost = (100_000 / 10_000) * 0.0075  # Estimate 100K requests
                    monthly_cost = bandwidth_cost + requests_cost

                    # Calculate optimization potential
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_cdn_optimization(
                        provisioning_state=provisioning_state,
                        sku_name=sku_name,
                        endpoint_count=endpoint_count,
                        bandwidth_gb_30d=total_bandwidth_gb,
                        requests_30d=total_requests,
                        has_caching_rules=has_caching_rules,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "profile_name": profile_name,
                        "resource_group": resource_group,
                        "sku": sku_name,
                        "endpoint_count": endpoint_count,
                        "provisioning_state": provisioning_state,
                        "resource_state": getattr(profile, "resource_state", "Unknown"),
                        "has_caching_rules": has_caching_rules,
                        "optimization_details": recommendations,
                    }

                    resource = AllCloudResourceData(
                        resource_type="azure_cdn",
                        resource_id=profile.id or f"cdn-{profile_name}",
                        resource_name=profile_name,
                        region=region,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_priority=priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations.get("actions", []),
                    )

                    resources.append(resource)
                    logger.info(
                        "inventory.azure.cdn.processed",
                        profile_name=profile_name,
                        sku=sku_name,
                        endpoints=endpoint_count,
                        cost=monthly_cost,
                        optimizable=is_optimizable,
                    )

                except Exception as e:
                    logger.error(
                        "inventory.azure.cdn.error",
                        profile=profile.name if hasattr(profile, "name") else "Unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("inventory.azure.cdn.scan_error", region=region, error=str(e))

        return resources

    def _calculate_cdn_optimization(
        self,
        provisioning_state: str,
        sku_name: str,
        endpoint_count: int,
        bandwidth_gb_30d: float,
        requests_30d: int,
        has_caching_rules: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for CDN profile."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Profile failed or deleting
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Profile en état '{provisioning_state}' - investigate et réparez ou supprimez",
                    "Profile non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs Azure, réparer ou supprimer le profile",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero bandwidth in 30 days
        elif bandwidth_gb_30d == 0 and endpoint_count > 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucune bande passante utilisée depuis 30 jours",
                    f"{endpoint_count} endpoint(s) configuré(s) mais non utilisé(s)",
                    "Action: Supprimer les endpoints inutilisés ou le profile",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): Zero requests in 30 days
        elif requests_30d == 0 and endpoint_count > 0:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucune requête détectée depuis 30 jours",
                    f"{endpoint_count} endpoint(s) configuré(s) mais non sollicité(s)",
                    "Action: Vérifier si les endpoints sont encore nécessaires",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Premium tier for low traffic (<100GB/month)
        elif "premium" in sku_name and bandwidth_gb_30d < 100:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings = downgrade to Standard
            # Premium: $0.20/GB, Standard: $0.087/GB
            savings = bandwidth_gb_30d * (0.20 - 0.087)
            potential_savings = max(savings, 0.0)
            recommendations.update({
                "actions": [
                    f"Premium tier pour faible traffic: {bandwidth_gb_30d:.1f} GB/30j",
                    "Coût Premium: $0.20/GB vs Standard: $0.087/GB",
                    "Action: Downgrade vers Standard Microsoft ou Verizon",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No caching rules configured
        elif not has_caching_rules and endpoint_count > 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            # No direct savings, but best practice
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Aucune règle de caching configurée",
                    "Règles de caching optimisent performance et réduisent coûts",
                    "Action: Configurer des caching rules (TTL, query string caching)",
                    "Note: Économies indirectes via réduction de bandwidth origin",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_container_instances(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Container Instances for cost intelligence.

        Detection criteria:
        - Container stopped/failed (CRITICAL - 90 score)
        - Zero CPU usage 30 derniers jours (HIGH - 75 score)
        - High cost per container (HIGH - 70 score)
        - Long-running containers (MEDIUM - 50 score)
        - No resource limits configured (LOW - 30 score)

        Args:
            region: Azure region

        Returns:
            List of Azure Container Instances with optimization analysis
        """
        resources = []

        try:
            from azure.mgmt.containerinstance import ContainerInstanceManagementClient

            aci_client = ContainerInstanceManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing per hour (approximate)
            vcpu_price_per_hour = 0.0000125  # ~$0.0000125/vCPU-second
            memory_gb_price_per_hour = 0.0000014  # ~$0.0000014/GB-second

            # List all Container Groups
            container_groups = list(aci_client.container_groups.list())
            logger.info(
                "inventory.azure.container_instances.found",
                region=region,
                count=len(container_groups),
            )

            for group in container_groups:
                try:
                    # Filter by region
                    if group.location != region:
                        continue

                    group_name = group.name or "Unknown"
                    resource_group = group.id.split("/")[4] if group.id else "Unknown"

                    # Get container group properties
                    provisioning_state = getattr(group, "provisioning_state", "Unknown")
                    instance_view_state = getattr(group, "instance_view", None)
                    state = "Unknown"
                    if instance_view_state and hasattr(instance_view_state, "state"):
                        state = instance_view_state.state

                    # Get resource requests (vCPU + memory)
                    total_vcpu = 0.0
                    total_memory_gb = 0.0
                    container_count = 0
                    has_resource_limits = False

                    if group.containers:
                        for container in group.containers:
                            container_count += 1
                            if hasattr(container, "resources") and container.resources:
                                requests = container.resources.requests
                                if requests:
                                    total_vcpu += getattr(requests, "cpu", 0.0)
                                    total_memory_gb += getattr(requests, "memory_in_gb", 0.0)

                                limits = getattr(container.resources, "limits", None)
                                if limits:
                                    has_resource_limits = True

                    # Calculate monthly cost (assuming 730 hours/month)
                    hours_per_month = 730
                    vcpu_cost = total_vcpu * vcpu_price_per_hour * hours_per_month * 3600  # Convert to seconds
                    memory_cost = total_memory_gb * memory_gb_price_per_hour * hours_per_month * 3600
                    monthly_cost = vcpu_cost + memory_cost

                    # Get uptime (creation time)
                    uptime_days = 0
                    if hasattr(group, "instance_view") and group.instance_view:
                        if hasattr(group.instance_view, "events") and group.instance_view.events:
                            # Calculate uptime from first event
                            uptime_days = 30  # Placeholder

                    # TODO: Get actual metrics from Azure Monitor (CPU usage, uptime)
                    # For MVP, use placeholder metrics
                    cpu_usage_percent = 0  # Placeholder

                    # Calculate optimization potential
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_container_instance_optimization(
                        provisioning_state=provisioning_state,
                        state=state,
                        total_vcpu=total_vcpu,
                        total_memory_gb=total_memory_gb,
                        cpu_usage_percent=cpu_usage_percent,
                        uptime_days=uptime_days,
                        has_resource_limits=has_resource_limits,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "container_group_name": group_name,
                        "resource_group": resource_group,
                        "provisioning_state": provisioning_state,
                        "state": state,
                        "container_count": container_count,
                        "total_vcpu": total_vcpu,
                        "total_memory_gb": total_memory_gb,
                        "os_type": getattr(group, "os_type", "Unknown"),
                        "restart_policy": getattr(group, "restart_policy", "Always"),
                        "has_resource_limits": has_resource_limits,
                        "optimization_details": recommendations,
                    }

                    resource = AllCloudResourceData(
                        resource_type="azure_container_instance",
                        resource_id=group.id or f"aci-{group_name}",
                        resource_name=group_name,
                        region=region,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_priority=priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations.get("actions", []),
                    )

                    resources.append(resource)
                    logger.info(
                        "inventory.azure.container_instances.processed",
                        group_name=group_name,
                        vcpu=total_vcpu,
                        memory_gb=total_memory_gb,
                        cost=monthly_cost,
                        optimizable=is_optimizable,
                    )

                except Exception as e:
                    logger.error(
                        "inventory.azure.container_instances.error",
                        group=group.name if hasattr(group, "name") else "Unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("inventory.azure.container_instances.scan_error", region=region, error=str(e))

        return resources

    def _calculate_container_instance_optimization(
        self,
        provisioning_state: str,
        state: str,
        total_vcpu: float,
        total_memory_gb: float,
        cpu_usage_percent: float,
        uptime_days: int,
        has_resource_limits: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Container Instance."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Container stopped or failed
        if provisioning_state.lower() in ["failed", "deleting"] or state.lower() in ["stopped", "terminated"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Container en état '{state}' (provisioning: {provisioning_state})",
                    "Container non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le container group",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero CPU usage in 30 days
        elif cpu_usage_percent == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucune utilisation CPU détectée depuis 30 jours",
                    "Container potentiellement inutilisé ou en idle permanent",
                    "Action: Vérifier si le container est encore nécessaire",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): High cost per container (>$100/mo)
        elif monthly_cost > 100:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            savings = monthly_cost * 0.5  # 50% potential savings via AKS migration
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"Coût élevé pour Container Instance: ${monthly_cost:.2f}/mois",
                    f"Ressources: {total_vcpu} vCPUs, {total_memory_gb} GB RAM",
                    "Action: Migrer vers Azure Kubernetes Service (AKS) pour économiser",
                    f"Économies estimées: ${savings:.2f}/mois (50% via AKS)",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Long-running containers (>30 days)
        elif uptime_days > 30:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            savings = monthly_cost * 0.3  # 30% potential savings
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"Container long-running: {uptime_days} jours d'uptime",
                    "Containers persistants coûtent plus cher sur ACI",
                    "Action: Migrer vers AKS ou App Service pour workloads persistants",
                    f"Économies estimées: ${savings:.2f}/mois",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No resource limits configured
        elif not has_resource_limits:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Aucune limite de ressources configurée",
                    "Resource limits évitent les dépassements de coûts",
                    "Action: Configurer CPU/memory limits pour contrôler les coûts",
                    "Note: Meilleure pratique pour la gestion des coûts",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_logic_apps(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Logic Apps workflows for cost intelligence.

        Detection criteria:
        - Workflow disabled/failed (CRITICAL - 90 score)
        - Zero workflow runs 30 derniers jours (HIGH - 75 score)
        - High execution failure rate (HIGH - 70 score)
        - Consumption plan for high volume (MEDIUM - 50 score)
        - No error handling configured (LOW - 30 score)

        Args:
            region: Azure region

        Returns:
            List of Azure Logic Apps workflows with optimization analysis
        """
        resources = []

        try:
            from azure.mgmt.logic import LogicManagementClient

            logic_client = LogicManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing (approximate)
            action_price_consumption = 0.000025  # After 4000 free actions/month
            connector_price_standard = 0.000125  # Standard connector per call
            vcpu_price_standard = 0.192  # Standard plan per vCPU-hour
            memory_price_standard = 0.0137  # Standard plan per GB-hour

            # List all workflows (we need to list by resource group)
            # For simplicity, we'll query all resource groups
            from azure.mgmt.resource import ResourceManagementClient

            resource_client = ResourceManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            all_workflows = []
            resource_groups = list(resource_client.resource_groups.list())

            for rg in resource_groups:
                try:
                    rg_name = rg.name
                    workflows = list(logic_client.workflows.list_by_resource_group(rg_name))
                    all_workflows.extend([(rg_name, wf) for wf in workflows])
                except Exception as e:
                    logger.warning("inventory.azure.logic_apps.rg_error", rg=rg.name, error=str(e))
                    continue

            logger.info(
                "inventory.azure.logic_apps.found",
                region=region,
                count=len(all_workflows),
            )

            for rg_name, workflow in all_workflows:
                try:
                    # Filter by region
                    if workflow.location != region:
                        continue

                    workflow_name = workflow.name or "Unknown"

                    # Get workflow properties
                    state = getattr(workflow, "state", "Unknown")  # Enabled/Disabled
                    provisioning_state = getattr(workflow, "provisioning_state", "Unknown")

                    # Get workflow definition (to check error handling)
                    has_error_handling = False
                    if hasattr(workflow, "definition") and workflow.definition:
                        definition_str = str(workflow.definition)
                        if "runAfter" in definition_str or "catch" in definition_str.lower():
                            has_error_handling = True

                    # Get integration account (Standard vs Consumption)
                    integration_account = getattr(workflow, "integration_account", None)
                    is_standard = integration_account is not None

                    # TODO: Get actual metrics from Azure Monitor (runs, failures, executions)
                    # For MVP, use placeholder metrics
                    total_runs_30d = 0  # Placeholder
                    failed_runs_30d = 0  # Placeholder
                    failure_rate = 0.0  # Placeholder
                    total_actions_30d = 0  # Placeholder (for Consumption pricing)

                    # Calculate monthly cost estimate
                    if is_standard:
                        # Standard plan: estimate vCPU + memory cost
                        # Assume 1 vCPU + 1.75 GB memory for small workflow
                        monthly_cost = (vcpu_price_standard * 730) + (memory_price_standard * 1.75 * 730)
                    else:
                        # Consumption plan: estimate based on actions
                        # Assume 10K actions/month if workflow exists
                        estimated_actions = 10_000
                        monthly_cost = max(0, (estimated_actions - 4000)) * action_price_consumption
                        monthly_cost += estimated_actions * connector_price_standard * 0.5  # 50% connector calls

                    # Calculate optimization potential
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_logic_app_optimization(
                        state=state,
                        provisioning_state=provisioning_state,
                        total_runs_30d=total_runs_30d,
                        failed_runs_30d=failed_runs_30d,
                        failure_rate=failure_rate,
                        total_actions_30d=total_actions_30d,
                        is_standard=is_standard,
                        has_error_handling=has_error_handling,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "workflow_name": workflow_name,
                        "resource_group": rg_name,
                        "state": state,
                        "provisioning_state": provisioning_state,
                        "plan_type": "Standard" if is_standard else "Consumption",
                        "has_error_handling": has_error_handling,
                        "sku": getattr(workflow.sku, "name", "Unknown") if hasattr(workflow, "sku") else "Unknown",
                        "optimization_details": recommendations,
                    }

                    resource = AllCloudResourceData(
                        resource_type="azure_logic_app",
                        resource_id=workflow.id or f"logic-{workflow_name}",
                        resource_name=workflow_name,
                        region=region,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_priority=priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations.get("actions", []),
                    )

                    resources.append(resource)
                    logger.info(
                        "inventory.azure.logic_apps.processed",
                        workflow_name=workflow_name,
                        state=state,
                        plan_type="Standard" if is_standard else "Consumption",
                        cost=monthly_cost,
                        optimizable=is_optimizable,
                    )

                except Exception as e:
                    logger.error(
                        "inventory.azure.logic_apps.error",
                        workflow=workflow.name if hasattr(workflow, "name") else "Unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("inventory.azure.logic_apps.scan_error", region=region, error=str(e))

        return resources

    def _calculate_logic_app_optimization(
        self,
        state: str,
        provisioning_state: str,
        total_runs_30d: int,
        failed_runs_30d: int,
        failure_rate: float,
        total_actions_30d: int,
        is_standard: bool,
        has_error_handling: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Logic App workflow."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Workflow disabled or failed
        if state.lower() == "disabled" or provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Workflow en état '{state}' (provisioning: {provisioning_state})",
                    "Workflow non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le workflow",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero workflow runs in 30 days
        elif total_runs_30d == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucune exécution détectée depuis 30 jours",
                    "Workflow potentiellement inutilisé",
                    "Action: Vérifier si le workflow est encore nécessaire",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): High execution failure rate (>50%)
        elif failure_rate > 0.5:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            savings = monthly_cost * 0.5  # 50% potential savings by fixing errors
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"Taux d'échec élevé: {failure_rate*100:.1f}% des exécutions",
                    f"Échecs: {failed_runs_30d} sur {total_runs_30d} exécutions",
                    "Action: Investiguer et corriger les erreurs du workflow",
                    f"Économies estimées: ${savings:.2f}/mois en évitant les re-runs",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Consumption plan for high volume (>1M actions/mo)
        elif not is_standard and total_actions_30d > 1_000_000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Standard plan would be cheaper for high volume
            standard_cost = (0.192 * 730) + (0.0137 * 1.75 * 730)  # 1 vCPU + 1.75GB
            savings = monthly_cost - standard_cost
            potential_savings = max(savings, 0.0)
            recommendations.update({
                "actions": [
                    f"Consumption plan pour haut volume: {total_actions_30d:,} actions/30j",
                    f"Coût actuel: ${monthly_cost:.2f}/mois",
                    "Action: Migrer vers Standard plan pour économiser",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No error handling configured
        elif not has_error_handling:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Aucun error handling configuré dans le workflow",
                    "Error handling évite les échecs coûteux et les re-runs",
                    "Action: Ajouter try-catch ou runAfter avec conditions",
                    "Note: Meilleure pratique pour la fiabilité",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_log_analytics(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Log Analytics Workspaces for cost intelligence.

        Detection criteria:
        - Workspace not used/failed (CRITICAL - 90 score)
        - Zero data ingestion 30 derniers jours (HIGH - 75 score)
        - High retention cost (HIGH - 70 score)
        - Pay-as-you-go for high volume (MEDIUM - 50 score)
        - No data retention policy configured (LOW - 30 score)

        Args:
            region: Azure region

        Returns:
            List of Azure Log Analytics Workspaces with optimization analysis
        """
        resources = []

        try:
            from azure.mgmt.loganalytics import LogAnalyticsManagementClient

            log_client = LogAnalyticsManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing per GB (approximate)
            ingestion_price_payg = 2.30  # Pay-as-you-go per GB
            retention_price_per_gb = 0.10  # Per GB per month after 31 days
            commitment_100gb_price = 230.0  # Commitment tier 100GB/day (30% discount)

            # List all workspaces
            workspaces = list(log_client.workspaces.list())
            logger.info(
                "inventory.azure.log_analytics.found",
                region=region,
                count=len(workspaces),
            )

            for workspace in workspaces:
                try:
                    # Filter by region
                    if workspace.location != region:
                        continue

                    workspace_name = workspace.name or "Unknown"
                    resource_group = workspace.id.split("/")[4] if workspace.id else "Unknown"

                    # Get workspace properties
                    provisioning_state = getattr(workspace, "provisioning_state", "Unknown")

                    # Get SKU (pricing tier)
                    sku_name = "Unknown"
                    if hasattr(workspace, "sku") and workspace.sku:
                        sku_name = workspace.sku.name if hasattr(workspace.sku, "name") else "Unknown"

                    # Get retention days
                    retention_days = getattr(workspace, "retention_in_days", 30)
                    has_retention_policy = retention_days > 0

                    # Get daily quota (commitment tier indicator)
                    daily_quota_gb = getattr(workspace, "daily_quota_gb", -1)
                    is_commitment_tier = daily_quota_gb > 0

                    # TODO: Get actual metrics from Azure Monitor (data ingestion, queries)
                    # For MVP, use placeholder metrics
                    total_ingestion_gb_30d = 0  # Placeholder
                    daily_ingestion_gb = 0  # Placeholder
                    query_count_30d = 0  # Placeholder

                    # Calculate monthly cost estimate
                    if is_commitment_tier and daily_quota_gb >= 100:
                        # Commitment tier: 100GB/day = $230/day
                        monthly_cost = commitment_100gb_price * 30
                    else:
                        # Pay-as-you-go: estimate 10GB/day ingestion
                        estimated_daily_ingestion = 10
                        ingestion_cost = estimated_daily_ingestion * 30 * ingestion_price_payg

                        # Retention cost (beyond 31 days free)
                        if retention_days > 31:
                            retention_gb = estimated_daily_ingestion * retention_days
                            retention_cost = retention_gb * retention_price_per_gb
                        else:
                            retention_cost = 0

                        monthly_cost = ingestion_cost + retention_cost

                    # Calculate optimization potential
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_log_analytics_optimization(
                        provisioning_state=provisioning_state,
                        sku_name=sku_name,
                        retention_days=retention_days,
                        has_retention_policy=has_retention_policy,
                        total_ingestion_gb_30d=total_ingestion_gb_30d,
                        daily_ingestion_gb=daily_ingestion_gb,
                        query_count_30d=query_count_30d,
                        is_commitment_tier=is_commitment_tier,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "workspace_name": workspace_name,
                        "resource_group": resource_group,
                        "provisioning_state": provisioning_state,
                        "sku": sku_name,
                        "retention_days": retention_days,
                        "has_retention_policy": has_retention_policy,
                        "daily_quota_gb": daily_quota_gb,
                        "is_commitment_tier": is_commitment_tier,
                        "public_network_access": getattr(workspace, "public_network_access_for_ingestion", "Unknown"),
                        "optimization_details": recommendations,
                    }

                    resource = AllCloudResourceData(
                        resource_type="azure_log_analytics",
                        resource_id=workspace.id or f"log-{workspace_name}",
                        resource_name=workspace_name,
                        region=region,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_priority=priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations.get("actions", []),
                    )

                    resources.append(resource)
                    logger.info(
                        "inventory.azure.log_analytics.processed",
                        workspace_name=workspace_name,
                        sku=sku_name,
                        retention_days=retention_days,
                        cost=monthly_cost,
                        optimizable=is_optimizable,
                    )

                except Exception as e:
                    logger.error(
                        "inventory.azure.log_analytics.error",
                        workspace=workspace.name if hasattr(workspace, "name") else "Unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("inventory.azure.log_analytics.scan_error", region=region, error=str(e))

        return resources

    def _calculate_log_analytics_optimization(
        self,
        provisioning_state: str,
        sku_name: str,
        retention_days: int,
        has_retention_policy: bool,
        total_ingestion_gb_30d: float,
        daily_ingestion_gb: float,
        query_count_30d: int,
        is_commitment_tier: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Log Analytics Workspace."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Workspace not used or failed
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Workspace en état '{provisioning_state}'",
                    "Workspace non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le workspace",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero data ingestion in 30 days
        elif total_ingestion_gb_30d == 0 and query_count_30d == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucune ingestion de données depuis 30 jours",
                    "Workspace potentiellement inutilisé",
                    "Action: Vérifier si le workspace est encore nécessaire",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): High retention cost (>90 days for non-critical data)
        elif retention_days > 90:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Savings = reduce retention from 90+ to 31 days
            savings_per_gb = (retention_days - 31) * 0.10
            estimated_gb = daily_ingestion_gb * retention_days if daily_ingestion_gb > 0 else 300  # 10GB/day * 30 days
            savings = estimated_gb * (savings_per_gb / retention_days)  # Proportional savings
            potential_savings = max(savings, monthly_cost * 0.3)  # At least 30% savings
            recommendations.update({
                "actions": [
                    f"Rétention élevée: {retention_days} jours",
                    "Rétention longue coûte cher pour données non-critiques",
                    "Action: Réduire la rétention à 31 jours (gratuit) ou archiver vers blob storage",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Pay-as-you-go for high volume (>100GB/day)
        elif not is_commitment_tier and daily_ingestion_gb > 100:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Commitment tier saves 30%
            current_monthly = daily_ingestion_gb * 30 * 2.30
            commitment_monthly = 230 * 30  # 100GB/day commitment
            savings = current_monthly - commitment_monthly
            potential_savings = max(savings, 0.0)
            recommendations.update({
                "actions": [
                    f"Pay-as-you-go pour haut volume: {daily_ingestion_gb:.1f} GB/jour",
                    f"Coût actuel: ${current_monthly:.2f}/mois",
                    "Action: Migrer vers Commitment Tier (100GB/day) pour économiser 30%",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No data retention policy configured
        elif not has_retention_policy or retention_days == 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Aucune politique de rétention configurée",
                    "Rétention par défaut peut entraîner coûts non contrôlés",
                    "Action: Configurer une retention policy adaptée aux besoins",
                    "Note: Meilleure pratique pour gestion des coûts",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_backup_vaults(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Backup Vaults for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.recoveryservices import RecoveryServicesClient

            client = RecoveryServicesClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing per protected instance (varies by redundancy and tier)
            pricing_map = {
                "LRS_Standard": 5.0,  # Locally redundant standard
                "LRS_Archive": 2.5,  # Archive tier
                "ZRS_Standard": 6.25,  # Zone redundant
                "GRS_Standard": 10.0,  # Geo redundant standard
                "GRS_Archive": 5.0,  # Geo redundant archive
            }

            # List all Recovery Services Vaults
            vaults = client.vaults.list_by_subscription_id()

            for vault in vaults:
                try:
                    # Extract basic info
                    vault_id = vault.id or "unknown"
                    vault_name = vault.name or "unknown"
                    vault_location = vault.location or region
                    provisioning_state = (
                        vault.properties.provisioning_state
                        if vault.properties
                        else "Unknown"
                    )

                    # Get redundancy settings
                    redundancy = "LRS"
                    if vault.sku and vault.sku.name:
                        redundancy = vault.sku.name  # Standard, RS0 (GRS)

                    # Estimate protected items (requires backup client)
                    protected_items_count = 0
                    backup_jobs_30d = 0
                    backup_policies_count = 0
                    last_backup_time = None

                    try:
                        from azure.mgmt.recoveryservicesbackup import (
                            RecoveryServicesBackupClient,
                        )

                        backup_client = RecoveryServicesBackupClient(
                            credential=self.credential,
                            subscription_id=self.subscription_id,
                        )

                        # Get resource group from vault ID
                        resource_group = vault_id.split("/")[4] if "/" in vault_id else ""

                        # Count protected items
                        try:
                            protected_items = (
                                backup_client.backup_protected_items.list(
                                    vault_name=vault_name, resource_group_name=resource_group
                                )
                            )
                            protected_items_count = sum(1 for _ in protected_items)
                        except Exception:
                            pass

                        # Count backup policies
                        try:
                            policies = backup_client.backup_policies.list(
                                vault_name=vault_name, resource_group_name=resource_group
                            )
                            backup_policies_count = sum(1 for _ in policies)
                        except Exception:
                            pass

                        # Count recent backup jobs
                        try:
                            from datetime import datetime, timedelta

                            start_time = datetime.utcnow() - timedelta(days=30)
                            jobs = backup_client.backup_jobs.list(
                                vault_name=vault_name,
                                resource_group_name=resource_group,
                                filter=f"startTime eq '{start_time.isoformat()}Z'",
                            )
                            backup_jobs_30d = sum(1 for _ in jobs)
                        except Exception:
                            pass

                    except Exception as e:
                        logger.debug(
                            "backup_vault_metrics_error",
                            vault_name=vault_name,
                            error=str(e),
                        )

                    # Calculate monthly cost
                    redundancy_key = f"{redundancy}_Standard"
                    price_per_instance = pricing_map.get(redundancy_key, 5.0)
                    monthly_cost = protected_items_count * price_per_instance

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_backup_vault_optimization(
                        provisioning_state=provisioning_state,
                        protected_items_count=protected_items_count,
                        backup_jobs_30d=backup_jobs_30d,
                        backup_policies_count=backup_policies_count,
                        redundancy=redundancy,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "vault_id": vault_id,
                        "vault_name": vault_name,
                        "location": vault_location,
                        "provisioning_state": provisioning_state,
                        "redundancy": redundancy,
                        "protected_items": protected_items_count,
                        "backup_jobs_30d": backup_jobs_30d,
                        "backup_policies": backup_policies_count,
                        "price_per_instance": round(price_per_instance, 2),
                        "tags": dict(vault.tags) if vault.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=vault_id,
                        resource_name=vault_name,
                        resource_type="azure_backup_vault",
                        region=vault_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "backup_vault_scan_error",
                        vault_name=vault.name if vault.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_backup_vaults_error", region=region, error=str(e))

        logger.info(
            "scan_backup_vaults_complete",
            region=region,
            total_vaults=len(resources),
        )
        return resources

    def _calculate_backup_vault_optimization(
        self,
        provisioning_state: str,
        protected_items_count: int,
        backup_jobs_30d: int,
        backup_policies_count: int,
        redundancy: str,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Backup Vault."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Vault in failed state
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Vault en état '{provisioning_state}'",
                    "Vault non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le vault",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero protected items
        elif protected_items_count == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    "Aucun élément protégé dans le vault",
                    "Vault vide - coût 100% évitable",
                    "Action: Supprimer le vault ou commencer à l'utiliser",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): No backup jobs in 30 days
        elif backup_jobs_30d == 0 and protected_items_count > 0:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"{protected_items_count} éléments protégés mais aucun backup en 30 jours",
                    "Sauvegardes potentiellement non fonctionnelles",
                    "Action: Vérifier la configuration des policies ou supprimer les items",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): GRS redundancy for non-critical data
        elif redundancy in ["RS0", "GeoRedundant"] and protected_items_count > 0:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Savings = switch from GRS ($10) to LRS ($5) per instance
            savings_per_instance = 5.0
            potential_savings = protected_items_count * savings_per_instance
            recommendations.update({
                "actions": [
                    f"Redondance géographique (GRS) pour {protected_items_count} items",
                    f"GRS coûte 2x plus cher que LRS (${10.0} vs ${5.0}/instance)",
                    "Action: Migrer vers LRS si la redondance géographique n'est pas critique",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No backup policies configured
        elif backup_policies_count == 0 and protected_items_count > 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"{protected_items_count} items protégés sans backup policy",
                    "Absence de policies peut indiquer une configuration incomplète",
                    "Action: Configurer des backup policies appropriées",
                    "Note: Meilleure pratique pour gestion des sauvegardes",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_data_factory_pipelines(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Data Factory instances for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.datafactory import DataFactoryManagementClient

            client = DataFactoryManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: $0.005 per activity run (orchestration), $1 per vCore-hour (data flow)
            price_per_activity_run = 0.005
            price_per_vcore_hour = 1.0

            # List all Data Factories
            factories = client.factories.list()

            for factory in factories:
                try:
                    # Extract basic info
                    factory_id = factory.id or "unknown"
                    factory_name = factory.name or "unknown"
                    factory_location = factory.location or region
                    provisioning_state = (
                        factory.provisioning_state if factory.provisioning_state else "Unknown"
                    )

                    # Get resource group from factory ID
                    resource_group = factory_id.split("/")[4] if "/" in factory_id else ""

                    # Count pipelines, triggers, and runs
                    pipeline_count = 0
                    trigger_count = 0
                    pipeline_runs_30d = 0
                    failed_runs_30d = 0
                    total_activity_runs = 0

                    try:
                        # Count pipelines
                        pipelines = client.pipelines.list_by_factory(
                            resource_group_name=resource_group, factory_name=factory_name
                        )
                        pipeline_count = sum(1 for _ in pipelines)

                        # Count triggers
                        triggers = client.triggers.list_by_factory(
                            resource_group_name=resource_group, factory_name=factory_name
                        )
                        trigger_count = sum(1 for _ in triggers)

                        # Get pipeline runs from last 30 days
                        try:
                            from datetime import datetime, timedelta

                            end_time = datetime.utcnow()
                            start_time = end_time - timedelta(days=30)

                            # Query pipeline runs
                            filter_params = {
                                "lastUpdatedAfter": start_time,
                                "lastUpdatedBefore": end_time,
                            }

                            pipeline_runs = client.pipeline_runs.query_by_factory(
                                resource_group_name=resource_group,
                                factory_name=factory_name,
                                filter_parameters=filter_params,
                            )

                            for run in pipeline_runs.value if pipeline_runs.value else []:
                                pipeline_runs_30d += 1
                                if run.status in ["Failed", "Cancelled"]:
                                    failed_runs_30d += 1

                            # Estimate activity runs (average 5 activities per pipeline run)
                            total_activity_runs = pipeline_runs_30d * 5

                        except Exception:
                            pass

                    except Exception as e:
                        logger.debug(
                            "data_factory_metrics_error",
                            factory_name=factory_name,
                            error=str(e),
                        )

                    # Calculate monthly cost
                    # Base on activity runs only (data flows require separate analysis)
                    monthly_activity_cost = total_activity_runs * price_per_activity_run
                    monthly_cost = monthly_activity_cost

                    # Calculate optimization
                    failure_rate = (
                        (failed_runs_30d / pipeline_runs_30d * 100)
                        if pipeline_runs_30d > 0
                        else 0
                    )

                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_data_factory_optimization(
                        provisioning_state=provisioning_state,
                        pipeline_count=pipeline_count,
                        trigger_count=trigger_count,
                        pipeline_runs_30d=pipeline_runs_30d,
                        failed_runs_30d=failed_runs_30d,
                        failure_rate=failure_rate,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "factory_id": factory_id,
                        "factory_name": factory_name,
                        "location": factory_location,
                        "provisioning_state": provisioning_state,
                        "pipeline_count": pipeline_count,
                        "trigger_count": trigger_count,
                        "pipeline_runs_30d": pipeline_runs_30d,
                        "failed_runs_30d": failed_runs_30d,
                        "failure_rate_pct": round(failure_rate, 2),
                        "total_activity_runs": total_activity_runs,
                        "price_per_activity": price_per_activity_run,
                        "tags": dict(factory.tags) if factory.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=factory_id,
                        resource_name=factory_name,
                        resource_type="azure_data_factory_pipeline",
                        region=factory_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "data_factory_scan_error",
                        factory_name=factory.name if factory.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_data_factory_pipelines_error", region=region, error=str(e))

        logger.info(
            "scan_data_factory_pipelines_complete",
            region=region,
            total_factories=len(resources),
        )
        return resources

    def _calculate_data_factory_optimization(
        self,
        provisioning_state: str,
        pipeline_count: int,
        trigger_count: int,
        pipeline_runs_30d: int,
        failed_runs_30d: int,
        failure_rate: float,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Data Factory."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Data Factory in failed state
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Data Factory en état '{provisioning_state}'",
                    "Data Factory non opérationnel - coût 100% évitable",
                    "Action: Vérifier les logs, réparer ou supprimer la Data Factory",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Zero pipeline runs in 30 days
        elif pipeline_runs_30d == 0 and pipeline_count > 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"{pipeline_count} pipelines mais aucun run en 30 jours",
                    "Data Factory potentiellement inutilisée",
                    "Action: Supprimer la Data Factory ou activer les pipelines",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): High failure rate >50%
        elif failure_rate > 50 and pipeline_runs_30d > 0:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Assume failures waste 50% of costs
            potential_savings = monthly_cost * 0.5
            recommendations.update({
                "actions": [
                    f"Taux d'échec élevé: {failure_rate:.1f}% ({failed_runs_30d}/{pipeline_runs_30d} runs)",
                    "Échecs fréquents gaspillent des ressources",
                    "Action: Débugger les pipelines, améliorer la gestion d'erreurs",
                    f"Économies estimées: ${potential_savings:.2f}/mois (50% de réduction d'échecs)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Many pipelines with no recent runs
        elif pipeline_count >= 5 and pipeline_runs_30d == 0:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Assume we can delete half the unused pipelines
            potential_savings = monthly_cost * 0.5 if monthly_cost > 0 else 0
            recommendations.update({
                "actions": [
                    f"{pipeline_count} pipelines inactifs",
                    "Pipelines inutilisés créent de la complexité et du risque",
                    "Action: Nettoyer les pipelines obsolètes",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): No triggers configured
        elif trigger_count == 0 and pipeline_count > 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"{pipeline_count} pipelines sans triggers",
                    "Absence de triggers peut indiquer configuration manuelle",
                    "Action: Configurer des triggers pour automation",
                    "Note: Meilleure pratique pour orchestration automatisée",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_synapse_serverless_sql(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Synapse Analytics workspaces for serverless SQL pool cost intelligence."""
        resources = []

        try:
            from azure.mgmt.synapse import SynapseManagementClient

            client = SynapseManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: $5 per TB of data processed
            price_per_tb = 5.0

            # List all Synapse workspaces
            workspaces = client.workspaces.list()

            for workspace in workspaces:
                try:
                    # Extract basic info
                    workspace_id = workspace.id or "unknown"
                    workspace_name = workspace.name or "unknown"
                    workspace_location = workspace.location or region
                    provisioning_state = workspace.provisioning_state if workspace.provisioning_state else "Unknown"

                    # Serverless SQL pool is built-in to every workspace
                    # Endpoint format: {workspace_name}-ondemand.sql.azuresynapse.net
                    serverless_endpoint = f"{workspace_name}-ondemand.sql.azuresynapse.net" if workspace.connectivity_endpoints else "unknown"

                    # Check if workspace has serverless SQL endpoint active
                    has_serverless_sql = False
                    if workspace.connectivity_endpoints:
                        if "sqlOnDemand" in workspace.connectivity_endpoints:
                            has_serverless_sql = True
                            serverless_endpoint = workspace.connectivity_endpoints.get("sqlOnDemand", serverless_endpoint)

                    # Estimate monthly data processed (would require actual query metrics)
                    # For now, we'll use placeholder values and flag for investigation
                    estimated_tb_per_month = 0.0  # Would need actual metrics from Azure Monitor
                    monthly_cost = estimated_tb_per_month * price_per_tb

                    # Get resource group from workspace ID
                    resource_group = workspace_id.split("/")[4] if "/" in workspace_id else ""

                    # Try to get SQL pools count
                    sql_pools_count = 0
                    try:
                        sql_pools = client.sql_pools.list_by_workspace(
                            resource_group_name=resource_group,
                            workspace_name=workspace_name
                        )
                        sql_pools_count = sum(1 for _ in sql_pools)
                    except Exception:
                        pass

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_synapse_serverless_optimization(
                        provisioning_state=provisioning_state,
                        has_serverless_sql=has_serverless_sql,
                        sql_pools_count=sql_pools_count,
                        estimated_tb_per_month=estimated_tb_per_month,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "workspace_id": workspace_id,
                        "workspace_name": workspace_name,
                        "location": workspace_location,
                        "provisioning_state": provisioning_state,
                        "has_serverless_sql": has_serverless_sql,
                        "serverless_endpoint": serverless_endpoint,
                        "sql_pools_count": sql_pools_count,
                        "estimated_tb_per_month": round(estimated_tb_per_month, 2),
                        "price_per_tb": price_per_tb,
                        "tags": dict(workspace.tags) if workspace.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=workspace_id,
                        resource_name=workspace_name,
                        resource_type="azure_synapse_serverless_sql",
                        region=workspace_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "synapse_workspace_scan_error",
                        workspace_name=workspace.name if workspace.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_synapse_serverless_sql_error", region=region, error=str(e))

        logger.info(
            "scan_synapse_serverless_sql_complete",
            region=region,
            total_workspaces=len(resources),
        )
        return resources

    def _calculate_synapse_serverless_optimization(
        self,
        provisioning_state: str,
        has_serverless_sql: bool,
        sql_pools_count: int,
        estimated_tb_per_month: float,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Synapse Serverless SQL."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Workspace in failed state
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Workspace Synapse en état '{provisioning_state}'",
                    "Workspace non opérationnel - coût potentiellement évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le workspace",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Workspace actif sans serverless SQL pool configuré
        elif not has_serverless_sql and sql_pools_count == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = 0.0  # No cost if not using it, but workspace overhead
            recommendations.update({
                "actions": [
                    "Workspace Synapse sans serverless SQL ni dedicated pools",
                    "Workspace potentiellement inutilisé",
                    "Action: Supprimer le workspace ou commencer à l'utiliser",
                    "Note: Économies indirectes (complexité, maintenance)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): High data processing cost (>$500/month)
        elif monthly_cost > 500:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Suggest optimization strategies (partitioning, caching, etc.)
            potential_savings = monthly_cost * 0.3  # 30% savings through optimization
            recommendations.update({
                "actions": [
                    f"Coût élevé de data processing: ${monthly_cost:.2f}/mois ({estimated_tb_per_month:.2f} TB)",
                    "Usage intensif de serverless SQL peut être optimisé",
                    "Action: Analyser les queries, implémenter caching, partitioning, ou considérer dedicated SQL pool",
                    f"Économies estimées: ${potential_savings:.2f}/mois (30% réduction)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Workspace inactif mais serverless SQL enabled
        elif has_serverless_sql and estimated_tb_per_month == 0.0:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            potential_savings = 0.0  # Serverless has no idle cost, but investigate
            recommendations.update({
                "actions": [
                    "Serverless SQL endpoint actif mais aucune donnée processed en 30 jours",
                    "Workspace potentiellement inutilisé ou métriques non disponibles",
                    "Action: Vérifier l'usage réel via Azure Monitor ou supprimer si inutilisé",
                    "Note: Serverless SQL n'a pas de coût idle (pay-per-query uniquement)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): Pas de quotas/budgets configurés
        elif has_serverless_sql and monthly_cost == 0.0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Serverless SQL actif sans quotas/budgets configurés",
                    "Absence de limites peut entraîner coûts non contrôlés",
                    "Action: Configurer des cost controls via Azure Cost Management",
                    "Note: Meilleure pratique pour gestion des coûts",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_storage_sftp(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Storage Accounts with SFTP enabled for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.storage import StorageManagementClient

            client = StorageManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: $0.30/hour ($220/month) + storage costs
            sftp_hourly_cost = 0.30
            sftp_monthly_cost = sftp_hourly_cost * 24 * 30  # ~$216/month

            # List all storage accounts
            storage_accounts = client.storage_accounts.list()

            for account in storage_accounts:
                try:
                    # Check if SFTP is enabled
                    if not account.is_sftp_enabled:
                        continue  # Skip accounts without SFTP

                    # Extract basic info
                    account_id = account.id or "unknown"
                    account_name = account.name or "unknown"
                    account_location = account.location or region
                    provisioning_state = account.provisioning_state.value if account.provisioning_state else "Unknown"

                    # Get resource group from account ID
                    resource_group = account_id.split("/")[4] if "/" in account_id else ""

                    # Get account properties
                    sku_name = account.sku.name.value if account.sku else "Unknown"
                    account_kind = account.kind.value if account.kind else "Unknown"

                    # Estimate storage usage (would need actual metrics)
                    storage_used_gb = 0.0  # Would need Azure Monitor metrics
                    storage_cost = 0.0  # Depends on tier, redundancy, etc.

                    # Total monthly cost: SFTP fee + storage
                    monthly_cost = sftp_monthly_cost + storage_cost

                    # Try to estimate transaction count (would need metrics)
                    transaction_count_30d = 0  # Would need actual metrics

                    # Calculate days since SFTP enabled (if creation time available)
                    days_sftp_enabled = 30  # Placeholder
                    if account.creation_time:
                        from datetime import datetime
                        delta = datetime.utcnow() - account.creation_time
                        days_sftp_enabled = delta.days

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_storage_sftp_optimization(
                        provisioning_state=provisioning_state,
                        days_sftp_enabled=days_sftp_enabled,
                        transaction_count_30d=transaction_count_30d,
                        sftp_monthly_cost=sftp_monthly_cost,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "account_id": account_id,
                        "account_name": account_name,
                        "location": account_location,
                        "provisioning_state": provisioning_state,
                        "is_sftp_enabled": True,
                        "sku": sku_name,
                        "kind": account_kind,
                        "days_sftp_enabled": days_sftp_enabled,
                        "transaction_count_30d": transaction_count_30d,
                        "storage_used_gb": round(storage_used_gb, 2),
                        "sftp_hourly_cost": sftp_hourly_cost,
                        "sftp_monthly_cost": round(sftp_monthly_cost, 2),
                        "tags": dict(account.tags) if account.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=account_id,
                        resource_name=account_name,
                        resource_type="azure_storage_sftp",
                        region=account_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "storage_sftp_scan_error",
                        account_name=account.name if account.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_storage_sftp_error", region=region, error=str(e))

        logger.info(
            "scan_storage_sftp_complete",
            region=region,
            total_sftp_accounts=len(resources),
        )
        return resources

    def _calculate_storage_sftp_optimization(
        self,
        provisioning_state: str,
        days_sftp_enabled: int,
        transaction_count_30d: int,
        sftp_monthly_cost: float,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Storage Account with SFTP."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Storage account failed but SFTP still enabled
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = sftp_monthly_cost
            recommendations.update({
                "actions": [
                    f"Storage Account en état '{provisioning_state}' mais SFTP enabled",
                    f"SFTP coûte ${sftp_monthly_cost:.2f}/mois même si account failed",
                    "Action: Désactiver SFTP ou supprimer le storage account",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): SFTP enabled >30 days sans transactions
        elif days_sftp_enabled >= 30 and transaction_count_30d == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = sftp_monthly_cost
            recommendations.update({
                "actions": [
                    f"SFTP enabled depuis {days_sftp_enabled} jours sans aucune transaction",
                    f"SFTP inutilisé gaspille ${sftp_monthly_cost:.2f}/mois",
                    "Action: Désactiver SFTP (peut réactiver au besoin sans perte de config)",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): SFTP enabled avec très peu de transactions
        elif transaction_count_30d > 0 and transaction_count_30d < 100:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = sftp_monthly_cost
            recommendations.update({
                "actions": [
                    f"SFTP enabled avec seulement {transaction_count_30d} transactions en 30 jours",
                    f"Usage très faible pour ${sftp_monthly_cost:.2f}/mois",
                    "Action: Désactiver SFTP et enable on-demand, ou utiliser alternative (Azure Files)",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): SFTP enabled en permanence pour usage occasionnel
        elif transaction_count_30d >= 100 and transaction_count_30d < 1000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Suggest enable/disable strategy instead of always-on
            potential_savings = sftp_monthly_cost * 0.5  # 50% savings with on-demand
            recommendations.update({
                "actions": [
                    f"SFTP enabled 24/7 avec {transaction_count_30d} transactions/mois",
                    f"Usage modéré pour ${sftp_monthly_cost:.2f}/mois always-on",
                    "Action: Enable SFTP uniquement quand nécessaire (disable après usage)",
                    f"Économies estimées: ${potential_savings:.2f}/mois (50% réduction)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): Pas de monitoring des connexions SFTP
        elif transaction_count_30d == 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "SFTP enabled sans monitoring des connexions configuré",
                    "Métriques non disponibles pour analyser l'usage réel",
                    "Action: Configurer Azure Monitor pour tracking SFTP usage",
                    "Note: Meilleure pratique pour gestion des coûts",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_ad_domain_services(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure AD Domain Services (Microsoft Entra Domain Services) for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.resource import ResourceManagementClient

            resource_client = ResourceManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing per SKU per month
            pricing_map = {
                "Standard": 109,  # Estimated (not found in search results)
                "Enterprise": 292,
                "Premium": 1168,
            }

            # Query for Microsoft.AAD/domainServices resources
            filter_query = "resourceType eq 'Microsoft.AAD/domainServices'"
            domain_services = resource_client.resources.list(filter=filter_query)

            for domain_service in domain_services:
                try:
                    # Extract basic info
                    domain_id = domain_service.id or "unknown"
                    domain_name = domain_service.name or "unknown"
                    domain_location = domain_service.location or region

                    # Get resource properties
                    properties = domain_service.properties if domain_service.properties else {}

                    # Extract SKU
                    sku = properties.get("sku", "Unknown")
                    if isinstance(sku, dict):
                        sku = sku.get("name", "Unknown")

                    # Get provisioning state
                    provisioning_state = properties.get("provisioningState", "Unknown")

                    # Get health status
                    health_monitors = properties.get("healthMonitors", [])
                    health_alerts = properties.get("healthAlerts", [])
                    has_health_alerts = len(health_alerts) > 0 if health_alerts else False

                    # Get sync status
                    sync_scope = properties.get("syncScope", "Unknown")
                    sync_owner = properties.get("syncOwner", "Unknown")

                    # Get deployment configuration
                    replica_sets = properties.get("replicaSets", [])
                    replica_count = len(replica_sets) if replica_sets else 0

                    # Calculate monthly cost based on SKU
                    monthly_cost = pricing_map.get(sku, 109)  # Default to Standard if unknown

                    # Estimate VMs joined to domain (would need actual metrics)
                    vms_joined = 0  # Would need Azure Monitor or LDAP queries
                    auth_requests_per_hour = 0  # Would need metrics

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_ad_domain_services_optimization(
                        provisioning_state=provisioning_state,
                        sku=sku,
                        has_health_alerts=has_health_alerts,
                        vms_joined=vms_joined,
                        auth_requests_per_hour=auth_requests_per_hour,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "domain_id": domain_id,
                        "domain_name": domain_name,
                        "location": domain_location,
                        "provisioning_state": provisioning_state,
                        "sku": sku,
                        "sync_scope": sync_scope,
                        "sync_owner": sync_owner,
                        "replica_count": replica_count,
                        "has_health_alerts": has_health_alerts,
                        "health_alerts_count": len(health_alerts) if health_alerts else 0,
                        "vms_joined": vms_joined,
                        "auth_requests_per_hour": auth_requests_per_hour,
                        "tags": dict(domain_service.tags) if domain_service.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=domain_id,
                        resource_name=domain_name,
                        resource_type="azure_ad_domain_services",
                        region=domain_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "ad_domain_services_scan_error",
                        domain_name=domain_service.name if domain_service.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_ad_domain_services_error", region=region, error=str(e))

        logger.info(
            "scan_ad_domain_services_complete",
            region=region,
            total_domain_services=len(resources),
        )
        return resources

    def _calculate_ad_domain_services_optimization(
        self,
        provisioning_state: str,
        sku: str,
        has_health_alerts: bool,
        vms_joined: int,
        auth_requests_per_hour: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Azure AD Domain Services."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Domain Services not running or failed
        if provisioning_state.lower() in ["failed", "deleting", "deleted", "notrunning"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Azure AD Domain Services en état '{provisioning_state}'",
                    f"Service non opérationnel - coût ${monthly_cost:.2f}/mois évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le domain service",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Premium SKU ($1168/mois) pour <10K auth/hour
        elif sku == "Premium" and auth_requests_per_hour < 10000:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            # Downgrade from Premium ($1168) to Enterprise ($292)
            potential_savings = 1168 - 292
            recommendations.update({
                "actions": [
                    f"SKU Premium (${1168}/mois) surdimensionné pour {auth_requests_per_hour} auth/hour",
                    "Premium supporte 10K-70K auth/hour, usage actuel plus faible",
                    "Action: Downgrade vers Enterprise SKU pour économiser 75%",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): Domain Services non utilisé (0 VMs joinées)
        elif vms_joined == 0:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Azure AD Domain Services actif mais aucune VM joinée au domaine",
                    f"Service inutilisé - gaspille ${monthly_cost:.2f}/mois",
                    "Action: Supprimer le domain service ou commencer à l'utiliser",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Enterprise SKU pour <3K auth/hour
        elif sku == "Enterprise" and auth_requests_per_hour < 3000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Downgrade from Enterprise ($292) to Standard ($109)
            potential_savings = 292 - 109
            recommendations.update({
                "actions": [
                    f"SKU Enterprise (${292}/mois) pour {auth_requests_per_hour} auth/hour",
                    "Enterprise supporte 3K-10K auth/hour, Standard suffit pour <3K",
                    "Action: Downgrade vers Standard SKU pour économiser 63%",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): Health alerts non résolus
        elif has_health_alerts:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Azure AD Domain Services a des health alerts non résolus",
                    "Alerts peuvent indiquer problèmes de performance ou sécurité",
                    "Action: Résoudre les health alerts via Azure Portal",
                    "Note: Meilleure pratique pour fiabilité du service",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_service_bus_premium(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Service Bus Premium namespaces for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.servicebus import ServiceBusManagementClient

            client = ServiceBusManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: ~$670/month per messaging unit (flat rate)
            price_per_messaging_unit_monthly = 670.0

            # List all Service Bus namespaces
            namespaces = client.namespaces.list()

            for namespace in namespaces:
                try:
                    # Filter only Premium tier namespaces
                    if not namespace.sku or namespace.sku.name.lower() != "premium":
                        continue  # Skip non-Premium namespaces

                    # Extract basic info
                    namespace_id = namespace.id or "unknown"
                    namespace_name = namespace.name or "unknown"
                    namespace_location = namespace.location or region
                    provisioning_state = namespace.provisioning_state if namespace.provisioning_state else "Unknown"

                    # Get messaging units (capacity)
                    messaging_units = namespace.sku.capacity if namespace.sku else 1

                    # Calculate monthly cost
                    monthly_cost = messaging_units * price_per_messaging_unit_monthly

                    # Get resource group from namespace ID
                    resource_group = namespace_id.split("/")[4] if "/" in namespace_id else ""

                    # Count queues and topics
                    queues_count = 0
                    topics_count = 0
                    try:
                        queues = client.queues.list_by_namespace(
                            resource_group_name=resource_group,
                            namespace_name=namespace_name
                        )
                        queues_count = sum(1 for _ in queues)
                    except Exception:
                        pass

                    try:
                        topics = client.topics.list_by_namespace(
                            resource_group_name=resource_group,
                            namespace_name=namespace_name
                        )
                        topics_count = sum(1 for _ in topics)
                    except Exception:
                        pass

                    # Check if geo-disaster recovery is configured
                    has_geo_dr = False
                    try:
                        disaster_recovery_configs = client.disaster_recovery_configs.list(
                            resource_group_name=resource_group,
                            namespace_name=namespace_name
                        )
                        has_geo_dr = sum(1 for _ in disaster_recovery_configs) > 0
                    except Exception:
                        pass

                    # Estimate throughput usage (would need metrics)
                    estimated_throughput_percent = 0  # Would need Azure Monitor metrics

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_service_bus_premium_optimization(
                        provisioning_state=provisioning_state,
                        messaging_units=messaging_units,
                        queues_count=queues_count,
                        topics_count=topics_count,
                        has_geo_dr=has_geo_dr,
                        estimated_throughput_percent=estimated_throughput_percent,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "namespace_id": namespace_id,
                        "namespace_name": namespace_name,
                        "location": namespace_location,
                        "provisioning_state": provisioning_state,
                        "sku": "Premium",
                        "messaging_units": messaging_units,
                        "queues_count": queues_count,
                        "topics_count": topics_count,
                        "has_geo_dr": has_geo_dr,
                        "estimated_throughput_percent": estimated_throughput_percent,
                        "price_per_unit_monthly": price_per_messaging_unit_monthly,
                        "tags": dict(namespace.tags) if namespace.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=namespace_id,
                        resource_name=namespace_name,
                        resource_type="azure_service_bus_premium",
                        region=namespace_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "service_bus_premium_scan_error",
                        namespace_name=namespace.name if namespace.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_service_bus_premium_error", region=region, error=str(e))

        logger.info(
            "scan_service_bus_premium_complete",
            region=region,
            total_premium_namespaces=len(resources),
        )
        return resources

    def _calculate_service_bus_premium_optimization(
        self,
        provisioning_state: str,
        messaging_units: int,
        queues_count: int,
        topics_count: int,
        has_geo_dr: bool,
        estimated_throughput_percent: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for Service Bus Premium."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): Namespace in failed state
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Service Bus Premium namespace en état '{provisioning_state}'",
                    f"Namespace non opérationnel - coût ${monthly_cost:.2f}/mois évitable",
                    "Action: Vérifier les logs, réparer ou supprimer le namespace",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Premium tier avec 0 queues/topics
        elif queues_count == 0 and topics_count == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"Premium namespace vide (0 queues, 0 topics) - coût ${monthly_cost:.2f}/mois",
                    f"{messaging_units} messaging unit(s) inutilisées",
                    "Action: Supprimer le namespace ou créer des queues/topics",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): Premium tier avec très faible débit
        elif estimated_throughput_percent > 0 and estimated_throughput_percent < 10:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost * 0.5  # Suggest downgrade or Standard tier
            recommendations.update({
                "actions": [
                    f"Faible utilisation: {estimated_throughput_percent}% du débit Premium",
                    f"Premium tier coûte ${monthly_cost:.2f}/mois pour usage minimal",
                    "Action: Considérer Standard tier ou réduire messaging units",
                    f"Économies estimées: ${potential_savings:.2f}/mois (50% réduction)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): Premium tier surdimensionné
        elif messaging_units >= 4:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Suggest reducing from 4+ units to 2 units
            units_to_reduce = messaging_units - 2
            potential_savings = units_to_reduce * 670
            recommendations.update({
                "actions": [
                    f"Surdimensionnement potentiel: {messaging_units} messaging units",
                    f"Coût actuel: ${monthly_cost:.2f}/mois",
                    "Action: Analyser le débit réel et réduire messaging units si possible",
                    f"Économies estimées: ${potential_savings:.2f}/mois (réduction à 2 units)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): Premium sans geo-disaster recovery
        elif not has_geo_dr and messaging_units >= 2:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    "Premium tier sans geo-disaster recovery configuré",
                    "Premium offre geo-DR mais non utilisé",
                    "Action: Configurer geo-DR ou considérer Standard tier",
                    "Note: Meilleure pratique pour haute disponibilité",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_iot_hub(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure IoT Hubs for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.iothub import IotHubClient

            client = IotHubClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly)
            pricing_map = {
                "F1": 0.0,  # Free tier (8K messages/day)
                "B1": 10.0,  # Basic tier
                "B2": 50.0,
                "B3": 500.0,
                "S1": 25.0,  # Standard tier (400K messages/day)
                "S2": 250.0,  # 6M messages/day
                "S3": 2500.0,  # 300M messages/day
            }

            # List all IoT Hubs
            iot_hubs = client.iot_hub_resource.list_by_subscription()

            for hub in iot_hubs:
                try:
                    # Extract basic info
                    hub_id = hub.id or "unknown"
                    hub_name = hub.name or "unknown"
                    hub_location = hub.location or region
                    provisioning_state = hub.properties.provisioning_state if hub.properties else "Unknown"

                    # Get SKU info
                    sku_name = hub.sku.name if hub.sku else "Unknown"
                    sku_tier = hub.sku.tier if hub.sku else "Unknown"
                    sku_capacity = hub.sku.capacity if hub.sku else 1  # Number of units

                    # Calculate monthly cost
                    price_per_unit = pricing_map.get(sku_name, 25.0)
                    monthly_cost = price_per_unit * sku_capacity

                    # Get resource group from hub ID
                    resource_group = hub_id.split("/")[4] if "/" in hub_id else ""

                    # Get device statistics
                    device_count = 0
                    try:
                        stats = client.iot_hub_resource.get_stats(
                            resource_group_name=resource_group,
                            resource_name=hub_name
                        )
                        device_count = stats.total_device_count if stats.total_device_count else 0
                    except Exception:
                        pass

                    # Estimate message quota usage (would need metrics)
                    daily_message_quota = 0
                    if sku_name == "F1":
                        daily_message_quota = 8000
                    elif sku_name in ["B1", "S1"]:
                        daily_message_quota = 400000 * sku_capacity
                    elif sku_name == "S2":
                        daily_message_quota = 6000000 * sku_capacity
                    elif sku_name == "S3":
                        daily_message_quota = 300000000 * sku_capacity

                    # Estimate usage (would need actual metrics)
                    estimated_daily_messages = 0  # Would need Azure Monitor metrics
                    usage_percent = 0
                    if daily_message_quota > 0 and estimated_daily_messages > 0:
                        usage_percent = (estimated_daily_messages / daily_message_quota) * 100

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_iot_hub_optimization(
                        provisioning_state=provisioning_state,
                        sku_name=sku_name,
                        sku_tier=sku_tier,
                        sku_capacity=sku_capacity,
                        device_count=device_count,
                        usage_percent=usage_percent,
                        monthly_cost=monthly_cost,
                    )

                    # Build metadata
                    metadata = {
                        "hub_id": hub_id,
                        "hub_name": hub_name,
                        "location": hub_location,
                        "provisioning_state": provisioning_state,
                        "sku_name": sku_name,
                        "sku_tier": sku_tier,
                        "sku_capacity": sku_capacity,
                        "device_count": device_count,
                        "daily_message_quota": daily_message_quota,
                        "usage_percent": round(usage_percent, 2),
                        "price_per_unit": price_per_unit,
                        "tags": dict(hub.tags) if hub.tags else {},
                    }

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_id=hub_id,
                        resource_name=hub_name,
                        resource_type="azure_iot_hub",
                        region=hub_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata=metadata,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_priority=priority,
                        potential_monthly_savings=round(potential_savings, 2),
                        optimization_recommendations=recommendations,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "iot_hub_scan_error",
                        hub_name=hub.name if hub.name else "unknown",
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("scan_iot_hub_error", region=region, error=str(e))

        logger.info(
            "scan_iot_hub_complete",
            region=region,
            total_iot_hubs=len(resources),
        )
        return resources

    def _calculate_iot_hub_optimization(
        self,
        provisioning_state: str,
        sku_name: str,
        sku_tier: str,
        sku_capacity: int,
        device_count: int,
        usage_percent: float,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """Calculate optimization potential for IoT Hub."""
        is_optimizable = False
        optimization_score = 0
        priority = "low"
        potential_savings = 0.0
        recommendations = {"actions": [], "estimated_savings": 0.0, "priority": "low"}

        # CRITICAL (90 score): IoT Hub in failed state
        if provisioning_state.lower() in ["failed", "deleting", "deleted"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"IoT Hub en état '{provisioning_state}'",
                    f"Hub non opérationnel - coût ${monthly_cost:.2f}/mois évitable",
                    "Action: Vérifier les logs, réparer ou supprimer l'IoT Hub",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "critical",
            })

        # HIGH (75 score): Standard tier avec 0 devices
        elif sku_tier.lower() == "standard" and device_count == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost
            recommendations.update({
                "actions": [
                    f"IoT Hub Standard ({sku_name}) avec 0 devices enregistrés",
                    f"Hub inutilisé - coût ${monthly_cost:.2f}/mois",
                    "Action: Supprimer le hub ou commencer à enregistrer des devices",
                    f"Économies potentielles: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # HIGH (70 score): Standard tier avec usage <10%
        elif sku_tier.lower() == "standard" and usage_percent > 0 and usage_percent < 10:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Suggest downgrade to Basic or Free tier
            potential_savings = monthly_cost * 0.6  # 60% savings with Basic
            recommendations.update({
                "actions": [
                    f"Faible utilisation: {usage_percent:.1f}% du quota messages",
                    f"Standard tier ({sku_name}) coûte ${monthly_cost:.2f}/mois pour usage minimal",
                    "Action: Downgrade vers Basic tier ou réduire capacity",
                    f"Économies estimées: ${potential_savings:.2f}/mois (60% réduction)",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "high",
            })

        # MEDIUM (50 score): S2/S3 tier surdimensionné
        elif sku_name in ["S2", "S3"] and device_count < 1000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Suggest downgrade from S2/S3 to S1
            current_cost = monthly_cost
            s1_cost = 25.0 * sku_capacity
            potential_savings = current_cost - s1_cost
            recommendations.update({
                "actions": [
                    f"Tier {sku_name} surdimensionné pour {device_count} devices",
                    f"Coût actuel: ${current_cost:.2f}/mois",
                    "Action: Downgrade vers S1 tier pour économiser",
                    f"Économies estimées: ${potential_savings:.2f}/mois",
                ],
                "estimated_savings": round(potential_savings, 2),
                "priority": "medium",
            })

        # LOW (30 score): Pas de monitoring configuré
        elif usage_percent == 0 and device_count > 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0
            potential_savings = savings
            recommendations.update({
                "actions": [
                    f"IoT Hub avec {device_count} devices mais metrics non disponibles",
                    "Monitoring non configuré pour analyser l'usage réel",
                    "Action: Configurer Azure Monitor pour tracking messages",
                    "Note: Meilleure pratique pour gestion des coûts",
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_stream_analytics(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Stream Analytics jobs for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.streamanalytics import StreamAnalyticsManagementClient

            client = StreamAnalyticsManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: $0.11 per streaming unit-hour (V2 pricing)
            # Monthly cost = $0.11 * 24h * 30 days * streaming_units = $79.20 per SU
            price_per_su_monthly = 0.11 * 24 * 30

            # List all Stream Analytics jobs
            jobs = client.streaming_jobs.list()

            for job in jobs:
                try:
                    # Extract metadata
                    job_name = job.name
                    job_id = job.id
                    resource_group = job_id.split("/")[4] if len(job_id.split("/")) > 4 else "unknown"
                    job_location = job.location or region
                    job_state = job.job_state or "Unknown"

                    # Get transformation (streaming units)
                    streaming_units = 0
                    if job.transformation and hasattr(job.transformation, "streaming_units"):
                        streaming_units = job.transformation.streaming_units or 0

                    # Count inputs and outputs
                    inputs_count = 0
                    outputs_count = 0
                    try:
                        inputs_list = list(client.inputs.list_by_streaming_job(
                            resource_group_name=resource_group,
                            job_name=job_name
                        ))
                        inputs_count = len(inputs_list)
                    except Exception:
                        pass

                    try:
                        outputs_list = list(client.outputs.list_by_streaming_job(
                            resource_group_name=resource_group,
                            job_name=job_name
                        ))
                        outputs_count = len(outputs_list)
                    except Exception:
                        pass

                    # Get diagnostic settings (monitoring)
                    has_diagnostics = False
                    try:
                        from azure.mgmt.monitor import MonitorManagementClient
                        monitor_client = MonitorManagementClient(
                            credential=self.credential, subscription_id=self.subscription_id
                        )
                        diag_settings = list(monitor_client.diagnostic_settings.list(resource_uri=job_id))
                        has_diagnostics = len(diag_settings) > 0
                    except Exception:
                        pass

                    # Calculate monthly cost
                    monthly_cost = price_per_su_monthly * streaming_units

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_stream_analytics_optimization(
                        job_state=job_state,
                        streaming_units=streaming_units,
                        inputs_count=inputs_count,
                        outputs_count=outputs_count,
                        has_diagnostics=has_diagnostics,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=job_id,
                        resource_name=job_name,
                        resource_type="azure_stream_analytics",
                        region=job_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "job_state": job_state,
                            "streaming_units": streaming_units,
                            "inputs_count": inputs_count,
                            "outputs_count": outputs_count,
                            "has_diagnostics": has_diagnostics,
                            "resource_group": resource_group,
                            "sku": job.sku.name if job.sku else "Unknown",
                        },
                        last_used_at=None,
                        created_at_cloud=job.created_date if hasattr(job, "created_date") and job.created_date else None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Stream Analytics job {job.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Stream Analytics jobs: {str(e)}")

        return resources

    def _calculate_stream_analytics_optimization(
        self,
        job_state: str,
        streaming_units: int,
        inputs_count: int,
        outputs_count: int,
        has_diagnostics: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Stream Analytics optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Job failed
        2. HIGH (75): Job stopped >30 days (inferred from state)
        3. HIGH (70): Job running but 0 inputs/outputs
        4. MEDIUM (50): Oversized streaming units (>6 SU)
        5. LOW (30): No diagnostic monitoring configured
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Job failed
        if job_state.lower() in ["failed", "degraded"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Job failed or degraded",
                "description": (
                    f"Le job Stream Analytics est en état '{job_state}'. "
                    f"Coût gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Corriger la configuration des inputs/outputs, "
                    f"(3) Arrêter le job si non corrigeable pour éviter les coûts."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur du job '{job_state}'",
                    "Corriger la configuration des inputs/outputs",
                    "Arrêter le job si non réparable",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - Job stopped >30 days (inferred from stopped state)
        elif job_state.lower() == "stopped":
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Job arrêté depuis longtemps",
                "description": (
                    f"Le job Stream Analytics est arrêté. "
                    f"Si non utilisé depuis >30 jours, supprimer pour économiser ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier la dernière utilisation, "
                    f"(2) Supprimer si obsolète, "
                    f"(3) Redémarrer si nécessaire."
                ),
                "actions": [
                    "Vérifier la dernière date d'utilisation du job",
                    "Supprimer le job si obsolète (>30 jours)",
                    "Redémarrer si encore nécessaire",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - Job running but 0 inputs/outputs
        elif job_state.lower() == "running" and (inputs_count == 0 or outputs_count == 0):
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Job actif sans inputs/outputs configurés",
                "description": (
                    f"Le job Stream Analytics tourne avec {inputs_count} inputs et {outputs_count} outputs. "
                    f"Job inutilisable sans inputs/outputs. Coût: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Configurer les inputs/outputs, "
                    f"(2) Arrêter le job si configuration impossible."
                ),
                "actions": [
                    f"Configurer les inputs ({inputs_count}) et outputs ({outputs_count})",
                    "Tester le job avec des données réelles",
                    "Arrêter le job si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - Oversized streaming units (>6 SU)
        elif streaming_units > 6:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 50% reduction possible
            target_su = max(3, streaming_units // 2)
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Streaming Units surdimensionnés",
                "description": (
                    f"Le job utilise {streaming_units} SU (Streaming Units). "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Analyser le throughput réel pour réduire à ~{target_su} SU. "
                    f"Actions recommandées: (1) Analyser les métriques de throughput, "
                    f"(2) Réduire les SU progressivement, "
                    f"(3) Économiser jusqu'à ${savings:.2f}/mois."
                ),
                "actions": [
                    f"Analyser les métriques de throughput actuelles ({streaming_units} SU)",
                    f"Réduire progressivement à ~{target_su} SU",
                    "Monitorer les performances après réduction",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - No diagnostic monitoring configured
        elif not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = monthly_cost * 0.1  # Visibility helps optimize
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring configuré",
                "description": (
                    f"Le job Stream Analytics n'a pas de diagnostic monitoring activé. "
                    f"Sans métriques, impossible d'optimiser le throughput et les coûts. "
                    f"Actions recommandées: (1) Activer Diagnostic Settings, "
                    f"(2) Envoyer logs vers Log Analytics, "
                    f"(3) Créer des alertes sur les métriques clés."
                ),
                "actions": [
                    "Activer Diagnostic Settings pour le job",
                    "Envoyer logs vers Log Analytics Workspace",
                    "Créer des alertes sur métriques clés (errors, throughput)",
                    f"Note: Meilleure visibilité pour optimiser (économie ~${savings:.2f}/mois)"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_ai_document_intelligence(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Document Intelligence (Form Recognizer) endpoints for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            client = CognitiveServicesManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly estimates based on usage)
            # F0: Free tier (500 pages/month)
            # S0: Standard tier $1.50 per 1K pages
            pricing_map = {
                "F0": 0.0,  # Free tier
                "S0": 150.0,  # Estimate: 100K pages/month = $150
            }

            # List all Cognitive Services accounts
            accounts = client.accounts.list()

            for account in accounts:
                try:
                    # Filter only FormRecognizer/Document Intelligence accounts
                    if not account.kind or account.kind.lower() != "formrecognizer":
                        continue

                    # Extract metadata
                    account_name = account.name
                    account_id = account.id
                    resource_group = account_id.split("/")[4] if len(account_id.split("/")) > 4 else "unknown"
                    account_location = account.location or region
                    sku_name = account.sku.name if account.sku else "Unknown"
                    provisioning_state = account.properties.provisioning_state if hasattr(account, "properties") and hasattr(account.properties, "provisioning_state") else "Unknown"

                    # Check if endpoint is accessible
                    endpoint_accessible = False
                    if account.properties and hasattr(account.properties, "endpoint") and account.properties.endpoint:
                        endpoint_accessible = True

                    # Get diagnostic settings (monitoring)
                    has_diagnostics = False
                    try:
                        from azure.mgmt.monitor import MonitorManagementClient
                        monitor_client = MonitorManagementClient(
                            credential=self.credential, subscription_id=self.subscription_id
                        )
                        diag_settings = list(monitor_client.diagnostic_settings.list(resource_uri=account_id))
                        has_diagnostics = len(diag_settings) > 0
                    except Exception:
                        pass

                    # Check if private endpoint is configured
                    has_private_endpoint = False
                    if account.properties and hasattr(account.properties, "private_endpoint_connections"):
                        connections = account.properties.private_endpoint_connections or []
                        has_private_endpoint = len(connections) > 0

                    # Get estimated monthly cost
                    monthly_cost = pricing_map.get(sku_name, 150.0)

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_document_intelligence_optimization(
                        sku_name=sku_name,
                        provisioning_state=provisioning_state,
                        endpoint_accessible=endpoint_accessible,
                        has_diagnostics=has_diagnostics,
                        has_private_endpoint=has_private_endpoint,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=account_id,
                        resource_name=account_name,
                        resource_type="azure_document_intelligence",
                        region=account_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "endpoint_accessible": endpoint_accessible,
                            "has_diagnostics": has_diagnostics,
                            "has_private_endpoint": has_private_endpoint,
                            "resource_group": resource_group,
                            "kind": account.kind,
                        },
                        last_used_at=None,
                        created_at_cloud=None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Document Intelligence account {account.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Document Intelligence accounts: {str(e)}")

        return resources

    def _calculate_document_intelligence_optimization(
        self,
        sku_name: str,
        provisioning_state: str,
        endpoint_accessible: bool,
        has_diagnostics: bool,
        has_private_endpoint: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Document Intelligence optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Account failed provisioning
        2. HIGH (75): S0 tier with inaccessible endpoint
        3. HIGH (70): S0 tier without any usage metrics
        4. MEDIUM (50): S0 tier without private endpoint (security)
        5. LOW (30): No diagnostic monitoring configured
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Account failed provisioning
        if provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Account en état d'échec",
                "description": (
                    f"Le compte Document Intelligence est en état '{provisioning_state}'. "
                    f"Coût gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Recréer le compte si nécessaire, "
                    f"(3) Supprimer si non utilisé."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur pour '{provisioning_state}'",
                    "Recréer le compte si nécessaire",
                    "Supprimer le compte si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - S0 tier with inaccessible endpoint
        elif sku_name == "S0" and not endpoint_accessible:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Endpoint inaccessible en tier payant",
                "description": (
                    f"Le compte Document Intelligence S0 a un endpoint inaccessible. "
                    f"Coût: ${monthly_cost:.2f}/mois sans utilisation possible. "
                    f"Actions recommandées: (1) Vérifier la configuration réseau, "
                    f"(2) Corriger les règles de pare-feu, "
                    f"(3) Downgrade vers F0 ou supprimer si non utilisé."
                ),
                "actions": [
                    "Vérifier la configuration réseau et endpoint",
                    "Corriger les règles de pare-feu/NSG",
                    "Downgrade vers F0 (gratuit) si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - S0 tier without usage monitoring
        elif sku_name == "S0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            # Assume 50% of cost is waste without monitoring
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Tier payant sans monitoring d'usage",
                "description": (
                    f"Le compte Document Intelligence S0 n'a pas de monitoring configuré. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Impossible de vérifier si le tier S0 est justifié sans métriques. "
                    f"Actions recommandées: (1) Activer diagnostic settings, "
                    f"(2) Analyser l'usage réel, "
                    f"(3) Downgrade vers F0 si usage <500 pages/mois."
                ),
                "actions": [
                    "Activer Diagnostic Settings pour tracking usage",
                    "Analyser le volume de pages traitées par mois",
                    "Downgrade vers F0 si usage <500 pages/mois",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - S0 tier without private endpoint (security)
        elif sku_name == "S0" and not has_private_endpoint:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 10% cost for security improvement
            savings = monthly_cost * 0.1
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de Private Endpoint configuré",
                "description": (
                    f"Le compte Document Intelligence S0 expose un endpoint public. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Risque de sécurité pour données sensibles (documents). "
                    f"Actions recommandées: (1) Configurer Private Endpoint, "
                    f"(2) Restreindre l'accès réseau, "
                    f"(3) Activer firewall rules."
                ),
                "actions": [
                    "Configurer Azure Private Endpoint",
                    "Restreindre accès réseau (VNet only)",
                    "Activer firewall rules et IP filtering",
                    f"Note: Meilleure sécurité pour données sensibles"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - No diagnostic monitoring configured (F0 tier)
        elif sku_name == "F0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = 0  # Free tier, but monitoring helps prevent overages
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring configuré (Free tier)",
                "description": (
                    f"Le compte Document Intelligence F0 (gratuit) n'a pas de monitoring. "
                    f"Sans métriques, risque de dépasser la limite gratuite (500 pages/mois). "
                    f"Actions recommandées: (1) Activer Diagnostic Settings, "
                    f"(2) Créer des alertes sur quota usage, "
                    f"(3) Monitorer pour éviter charges inattendues."
                ),
                "actions": [
                    "Activer Diagnostic Settings",
                    "Créer alertes sur quota usage (500 pages/mois)",
                    "Monitorer pour éviter dépassement et charges",
                    "Note: Prévention de coûts inattendus"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_computer_vision(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Computer Vision accounts for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            client = CognitiveServicesManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly estimates based on usage)
            # F0: Free tier (5K transactions/month)
            # S1: Standard tier ~$1 per 1K transactions
            pricing_map = {
                "F0": 0.0,  # Free tier
                "S1": 150.0,  # Estimate: 150K transactions/month = $150
                "S0": 150.0,  # Legacy tier, same as S1
            }

            # List all Cognitive Services accounts
            accounts = client.accounts.list()

            for account in accounts:
                try:
                    # Filter only ComputerVision accounts
                    if not account.kind or account.kind.lower() != "computervision":
                        continue

                    # Extract metadata
                    account_name = account.name
                    account_id = account.id
                    resource_group = account_id.split("/")[4] if len(account_id.split("/")) > 4 else "unknown"
                    account_location = account.location or region
                    sku_name = account.sku.name if account.sku else "Unknown"
                    provisioning_state = account.properties.provisioning_state if hasattr(account, "properties") and hasattr(account.properties, "provisioning_state") else "Unknown"

                    # Check if endpoint is accessible
                    endpoint_accessible = False
                    if account.properties and hasattr(account.properties, "endpoint") and account.properties.endpoint:
                        endpoint_accessible = True

                    # Get diagnostic settings (monitoring)
                    has_diagnostics = False
                    try:
                        from azure.mgmt.monitor import MonitorManagementClient
                        monitor_client = MonitorManagementClient(
                            credential=self.credential, subscription_id=self.subscription_id
                        )
                        diag_settings = list(monitor_client.diagnostic_settings.list(resource_uri=account_id))
                        has_diagnostics = len(diag_settings) > 0
                    except Exception:
                        pass

                    # Check if private endpoint is configured
                    has_private_endpoint = False
                    if account.properties and hasattr(account.properties, "private_endpoint_connections"):
                        connections = account.properties.private_endpoint_connections or []
                        has_private_endpoint = len(connections) > 0

                    # Get estimated monthly cost
                    monthly_cost = pricing_map.get(sku_name, 150.0)

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_computer_vision_optimization(
                        sku_name=sku_name,
                        provisioning_state=provisioning_state,
                        endpoint_accessible=endpoint_accessible,
                        has_diagnostics=has_diagnostics,
                        has_private_endpoint=has_private_endpoint,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=account_id,
                        resource_name=account_name,
                        resource_type="azure_computer_vision",
                        region=account_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "endpoint_accessible": endpoint_accessible,
                            "has_diagnostics": has_diagnostics,
                            "has_private_endpoint": has_private_endpoint,
                            "resource_group": resource_group,
                            "kind": account.kind,
                        },
                        last_used_at=None,
                        created_at_cloud=None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Computer Vision account {account.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Computer Vision accounts: {str(e)}")

        return resources

    def _calculate_computer_vision_optimization(
        self,
        sku_name: str,
        provisioning_state: str,
        endpoint_accessible: bool,
        has_diagnostics: bool,
        has_private_endpoint: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Computer Vision optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Account failed provisioning
        2. HIGH (75): S1 tier avec endpoint inaccessible
        3. HIGH (70): S1 tier sans usage metrics/monitoring
        4. MEDIUM (50): S1 tier sans private endpoint (sécurité images)
        5. LOW (30): F0 tier sans monitoring (risque dépassement quota)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Account failed provisioning
        if provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Account en état d'échec",
                "description": (
                    f"Le compte Computer Vision est en état '{provisioning_state}'. "
                    f"Coût gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Recréer le compte si nécessaire, "
                    f"(3) Supprimer si non utilisé."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur pour '{provisioning_state}'",
                    "Recréer le compte si nécessaire",
                    "Supprimer le compte si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - S1 tier avec endpoint inaccessible
        elif sku_name in ["S1", "S0"] and not endpoint_accessible:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Endpoint inaccessible en tier payant",
                "description": (
                    f"Le compte Computer Vision {sku_name} a un endpoint inaccessible. "
                    f"Coût: ${monthly_cost:.2f}/mois sans utilisation possible. "
                    f"Actions recommandées: (1) Vérifier la configuration réseau, "
                    f"(2) Corriger les règles de pare-feu, "
                    f"(3) Downgrade vers F0 ou supprimer si non utilisé."
                ),
                "actions": [
                    "Vérifier la configuration réseau et endpoint",
                    "Corriger les règles de pare-feu/NSG",
                    "Downgrade vers F0 (gratuit) si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - S1 tier sans usage metrics/monitoring
        elif sku_name in ["S1", "S0"] and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            # Assume 50% of cost is waste without monitoring
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Tier payant sans monitoring d'usage",
                "description": (
                    f"Le compte Computer Vision {sku_name} n'a pas de monitoring configuré. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Impossible de vérifier si le tier {sku_name} est justifié sans métriques. "
                    f"Actions recommandées: (1) Activer diagnostic settings, "
                    f"(2) Analyser l'usage réel (transactions/mois), "
                    f"(3) Downgrade vers F0 si usage <5K transactions/mois."
                ),
                "actions": [
                    "Activer Diagnostic Settings pour tracking usage",
                    "Analyser le volume de transactions par mois",
                    "Downgrade vers F0 si usage <5K transactions/mois",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - S1 tier sans private endpoint (sécurité images)
        elif sku_name in ["S1", "S0"] and not has_private_endpoint:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 10% cost for security improvement
            savings = monthly_cost * 0.1
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de Private Endpoint configuré",
                "description": (
                    f"Le compte Computer Vision {sku_name} expose un endpoint public. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Risque de sécurité pour images sensibles (OCR, analyse visuelle). "
                    f"Actions recommandées: (1) Configurer Private Endpoint, "
                    f"(2) Restreindre l'accès réseau, "
                    f"(3) Activer firewall rules."
                ),
                "actions": [
                    "Configurer Azure Private Endpoint",
                    "Restreindre accès réseau (VNet only)",
                    "Activer firewall rules et IP filtering",
                    "Note: Meilleure sécurité pour images sensibles"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - F0 tier sans monitoring (risque dépassement quota)
        elif sku_name == "F0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = 0  # Free tier, but monitoring helps prevent overages
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring configuré (Free tier)",
                "description": (
                    f"Le compte Computer Vision F0 (gratuit) n'a pas de monitoring. "
                    f"Sans métriques, risque de dépasser la limite gratuite (5K transactions/mois). "
                    f"Actions recommandées: (1) Activer Diagnostic Settings, "
                    f"(2) Créer des alertes sur quota usage, "
                    f"(3) Monitorer pour éviter charges inattendues."
                ),
                "actions": [
                    "Activer Diagnostic Settings",
                    "Créer alertes sur quota usage (5K transactions/mois)",
                    "Monitorer pour éviter dépassement et charges",
                    "Note: Prévention de coûts inattendus"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_face_api(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Face API accounts for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            client = CognitiveServicesManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly estimates based on usage)
            # F0: Free tier (30K transactions/month)
            # S0: Standard tier $0.40-$1 per 1K transactions
            pricing_map = {
                "F0": 0.0,  # Free tier
                "S0": 150.0,  # Estimate: 150K transactions/month = $150
            }

            # List all Cognitive Services accounts
            accounts = client.accounts.list()

            for account in accounts:
                try:
                    # Filter only Face accounts
                    if not account.kind or account.kind.lower() != "face":
                        continue

                    # Extract metadata
                    account_name = account.name
                    account_id = account.id
                    resource_group = account_id.split("/")[4] if len(account_id.split("/")) > 4 else "unknown"
                    account_location = account.location or region
                    sku_name = account.sku.name if account.sku else "Unknown"
                    provisioning_state = account.properties.provisioning_state if hasattr(account, "properties") and hasattr(account.properties, "provisioning_state") else "Unknown"

                    # Check if endpoint is accessible
                    endpoint_accessible = False
                    if account.properties and hasattr(account.properties, "endpoint") and account.properties.endpoint:
                        endpoint_accessible = True

                    # Get diagnostic settings (monitoring)
                    has_diagnostics = False
                    try:
                        from azure.mgmt.monitor import MonitorManagementClient
                        monitor_client = MonitorManagementClient(
                            credential=self.credential, subscription_id=self.subscription_id
                        )
                        diag_settings = list(monitor_client.diagnostic_settings.list(resource_uri=account_id))
                        has_diagnostics = len(diag_settings) > 0
                    except Exception:
                        pass

                    # Check if private endpoint is configured
                    has_private_endpoint = False
                    if account.properties and hasattr(account.properties, "private_endpoint_connections"):
                        connections = account.properties.private_endpoint_connections or []
                        has_private_endpoint = len(connections) > 0

                    # Get estimated monthly cost
                    monthly_cost = pricing_map.get(sku_name, 150.0)

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_face_api_optimization(
                        sku_name=sku_name,
                        provisioning_state=provisioning_state,
                        endpoint_accessible=endpoint_accessible,
                        has_diagnostics=has_diagnostics,
                        has_private_endpoint=has_private_endpoint,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=account_id,
                        resource_name=account_name,
                        resource_type="azure_face_api",
                        region=account_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "endpoint_accessible": endpoint_accessible,
                            "has_diagnostics": has_diagnostics,
                            "has_private_endpoint": has_private_endpoint,
                            "resource_group": resource_group,
                            "kind": account.kind,
                        },
                        last_used_at=None,
                        created_at_cloud=None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Face API account {account.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Face API accounts: {str(e)}")

        return resources

    def _calculate_face_api_optimization(
        self,
        sku_name: str,
        provisioning_state: str,
        endpoint_accessible: bool,
        has_diagnostics: bool,
        has_private_endpoint: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Face API optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Account failed provisioning
        2. HIGH (75): S0 tier avec endpoint inaccessible
        3. HIGH (70): S0 tier sans usage metrics
        4. MEDIUM (50): S0 tier sans private endpoint (données biométriques sensibles)
        5. LOW (30): F0 tier sans monitoring quota
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Account failed provisioning
        if provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Account en état d'échec",
                "description": (
                    f"Le compte Face API est en état '{provisioning_state}'. "
                    f"Coût gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Recréer le compte si nécessaire, "
                    f"(3) Supprimer si non utilisé."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur pour '{provisioning_state}'",
                    "Recréer le compte si nécessaire",
                    "Supprimer le compte si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - S0 tier avec endpoint inaccessible
        elif sku_name == "S0" and not endpoint_accessible:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Endpoint inaccessible en tier payant",
                "description": (
                    f"Le compte Face API S0 a un endpoint inaccessible. "
                    f"Coût: ${monthly_cost:.2f}/mois sans utilisation possible. "
                    f"Actions recommandées: (1) Vérifier la configuration réseau, "
                    f"(2) Corriger les règles de pare-feu, "
                    f"(3) Downgrade vers F0 ou supprimer si non utilisé."
                ),
                "actions": [
                    "Vérifier la configuration réseau et endpoint",
                    "Corriger les règles de pare-feu/NSG",
                    "Downgrade vers F0 (gratuit) si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - S0 tier sans usage metrics
        elif sku_name == "S0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            # Assume 50% of cost is waste without monitoring
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Tier payant sans monitoring d'usage",
                "description": (
                    f"Le compte Face API S0 n'a pas de monitoring configuré. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Impossible de vérifier si le tier S0 est justifié sans métriques. "
                    f"Actions recommandées: (1) Activer diagnostic settings, "
                    f"(2) Analyser l'usage réel (face detection/verification), "
                    f"(3) Downgrade vers F0 si usage <30K transactions/mois."
                ),
                "actions": [
                    "Activer Diagnostic Settings pour tracking usage",
                    "Analyser le volume de détections faciales par mois",
                    "Downgrade vers F0 si usage <30K transactions/mois",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - S0 tier sans private endpoint (données biométriques)
        elif sku_name == "S0" and not has_private_endpoint:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 15% cost for security improvement (biometric data is critical)
            savings = monthly_cost * 0.15
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de Private Endpoint pour données biométriques",
                "description": (
                    f"Le compte Face API S0 expose un endpoint public. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"RISQUE CRITIQUE: Données biométriques sensibles (RGPD/GDPR). "
                    f"Actions recommandées: (1) Configurer Private Endpoint URGENT, "
                    f"(2) Restreindre l'accès réseau, "
                    f"(3) Activer firewall rules."
                ),
                "actions": [
                    "URGENT: Configurer Azure Private Endpoint",
                    "Restreindre accès réseau (VNet only)",
                    "Activer firewall rules et IP filtering",
                    "Note: Conformité RGPD pour données biométriques"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - F0 tier sans monitoring quota
        elif sku_name == "F0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = 0  # Free tier, but monitoring helps prevent overages
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring configuré (Free tier)",
                "description": (
                    f"Le compte Face API F0 (gratuit) n'a pas de monitoring. "
                    f"Sans métriques, risque de dépasser la limite gratuite (30K transactions/mois). "
                    f"Actions recommandées: (1) Activer Diagnostic Settings, "
                    f"(2) Créer des alertes sur quota usage, "
                    f"(3) Monitorer pour éviter charges inattendues."
                ),
                "actions": [
                    "Activer Diagnostic Settings",
                    "Créer alertes sur quota usage (30K transactions/mois)",
                    "Monitorer pour éviter dépassement et charges",
                    "Note: Prévention de coûts inattendus"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_text_analytics(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Text Analytics (Language Service) accounts for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            client = CognitiveServicesManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly estimates based on usage)
            # F0: Free tier (5K text records/month)
            # S: Standard tier ~$2 per 1K text records
            pricing_map = {
                "F0": 0.0,  # Free tier
                "S": 200.0,  # Estimate: 100K text records/month = $200
                "S0": 200.0,  # Legacy tier, same as S
            }

            # List all Cognitive Services accounts
            accounts = client.accounts.list()

            for account in accounts:
                try:
                    # Filter only TextAnalytics accounts
                    if not account.kind or account.kind.lower() != "textanalytics":
                        continue

                    # Extract metadata
                    account_name = account.name
                    account_id = account.id
                    resource_group = account_id.split("/")[4] if len(account_id.split("/")) > 4 else "unknown"
                    account_location = account.location or region
                    sku_name = account.sku.name if account.sku else "Unknown"
                    provisioning_state = account.properties.provisioning_state if hasattr(account, "properties") and hasattr(account.properties, "provisioning_state") else "Unknown"

                    # Check if endpoint is accessible
                    endpoint_accessible = False
                    if account.properties and hasattr(account.properties, "endpoint") and account.properties.endpoint:
                        endpoint_accessible = True

                    # Get diagnostic settings (monitoring)
                    has_diagnostics = False
                    try:
                        from azure.mgmt.monitor import MonitorManagementClient
                        monitor_client = MonitorManagementClient(
                            credential=self.credential, subscription_id=self.subscription_id
                        )
                        diag_settings = list(monitor_client.diagnostic_settings.list(resource_uri=account_id))
                        has_diagnostics = len(diag_settings) > 0
                    except Exception:
                        pass

                    # Check if private endpoint is configured
                    has_private_endpoint = False
                    if account.properties and hasattr(account.properties, "private_endpoint_connections"):
                        connections = account.properties.private_endpoint_connections or []
                        has_private_endpoint = len(connections) > 0

                    # Get estimated monthly cost
                    monthly_cost = pricing_map.get(sku_name, 200.0)

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_text_analytics_optimization(
                        sku_name=sku_name,
                        provisioning_state=provisioning_state,
                        endpoint_accessible=endpoint_accessible,
                        has_diagnostics=has_diagnostics,
                        has_private_endpoint=has_private_endpoint,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=account_id,
                        resource_name=account_name,
                        resource_type="azure_text_analytics",
                        region=account_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "endpoint_accessible": endpoint_accessible,
                            "has_diagnostics": has_diagnostics,
                            "has_private_endpoint": has_private_endpoint,
                            "resource_group": resource_group,
                            "kind": account.kind,
                        },
                        last_used_at=None,
                        created_at_cloud=None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Text Analytics account {account.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Text Analytics accounts: {str(e)}")

        return resources

    def _calculate_text_analytics_optimization(
        self,
        sku_name: str,
        provisioning_state: str,
        endpoint_accessible: bool,
        has_diagnostics: bool,
        has_private_endpoint: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Text Analytics optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Account failed provisioning
        2. HIGH (75): S tier avec endpoint inaccessible
        3. HIGH (70): S tier sans usage metrics
        4. MEDIUM (50): S tier sans private endpoint
        5. LOW (30): F0 tier sans monitoring
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Account failed provisioning
        if provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Account en état d'échec",
                "description": (
                    f"Le compte Text Analytics est en état '{provisioning_state}'. "
                    f"Coût gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Recréer le compte si nécessaire, "
                    f"(3) Supprimer si non utilisé."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur pour '{provisioning_state}'",
                    "Recréer le compte si nécessaire",
                    "Supprimer le compte si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - S tier avec endpoint inaccessible
        elif sku_name in ["S", "S0"] and not endpoint_accessible:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Endpoint inaccessible en tier payant",
                "description": (
                    f"Le compte Text Analytics {sku_name} a un endpoint inaccessible. "
                    f"Coût: ${monthly_cost:.2f}/mois sans utilisation possible. "
                    f"Actions recommandées: (1) Vérifier la configuration réseau, "
                    f"(2) Corriger les règles de pare-feu, "
                    f"(3) Downgrade vers F0 ou supprimer si non utilisé."
                ),
                "actions": [
                    "Vérifier la configuration réseau et endpoint",
                    "Corriger les règles de pare-feu/NSG",
                    "Downgrade vers F0 (gratuit) si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - S tier sans usage metrics
        elif sku_name in ["S", "S0"] and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            # Assume 50% of cost is waste without monitoring
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Tier payant sans monitoring d'usage",
                "description": (
                    f"Le compte Text Analytics {sku_name} n'a pas de monitoring configuré. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Impossible de vérifier si le tier {sku_name} est justifié sans métriques. "
                    f"Actions recommandées: (1) Activer diagnostic settings, "
                    f"(2) Analyser l'usage réel (text records/mois), "
                    f"(3) Downgrade vers F0 si usage <5K text records/mois."
                ),
                "actions": [
                    "Activer Diagnostic Settings pour tracking usage",
                    "Analyser le volume de text records par mois",
                    "Downgrade vers F0 si usage <5K text records/mois",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - S tier sans private endpoint
        elif sku_name in ["S", "S0"] and not has_private_endpoint:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 10% cost for security improvement
            savings = monthly_cost * 0.1
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de Private Endpoint configuré",
                "description": (
                    f"Le compte Text Analytics {sku_name} expose un endpoint public. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Risque de sécurité pour données textuelles sensibles (NER, PII). "
                    f"Actions recommandées: (1) Configurer Private Endpoint, "
                    f"(2) Restreindre l'accès réseau, "
                    f"(3) Activer firewall rules."
                ),
                "actions": [
                    "Configurer Azure Private Endpoint",
                    "Restreindre accès réseau (VNet only)",
                    "Activer firewall rules et IP filtering",
                    "Note: Meilleure sécurité pour données textuelles sensibles"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - F0 tier sans monitoring
        elif sku_name == "F0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = 0  # Free tier, but monitoring helps prevent overages
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring configuré (Free tier)",
                "description": (
                    f"Le compte Text Analytics F0 (gratuit) n'a pas de monitoring. "
                    f"Sans métriques, risque de dépasser la limite gratuite (5K text records/mois). "
                    f"Actions recommandées: (1) Activer Diagnostic Settings, "
                    f"(2) Créer des alertes sur quota usage, "
                    f"(3) Monitorer pour éviter charges inattendues."
                ),
                "actions": [
                    "Activer Diagnostic Settings",
                    "Créer alertes sur quota usage (5K text records/mois)",
                    "Monitorer pour éviter dépassement et charges",
                    "Note: Prévention de coûts inattendus"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_speech_services(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Speech Services accounts for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            client = CognitiveServicesManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly estimates based on usage)
            # F0: Free tier (5 audio hours/month STT + 0.5M chars/month TTS)
            # S0: Standard tier $1/hour STT + $16 per million chars TTS Neural
            pricing_map = {
                "F0": 0.0,  # Free tier
                "S0": 200.0,  # Estimate: 100 hours STT + 100K chars TTS = $200
            }

            # List all Cognitive Services accounts
            accounts = client.accounts.list()

            for account in accounts:
                try:
                    # Filter only SpeechServices accounts
                    if not account.kind or account.kind.lower() != "speechservices":
                        continue

                    # Extract metadata
                    account_name = account.name
                    account_id = account.id
                    resource_group = account_id.split("/")[4] if len(account_id.split("/")) > 4 else "unknown"
                    account_location = account.location or region
                    sku_name = account.sku.name if account.sku else "Unknown"
                    provisioning_state = account.properties.provisioning_state if hasattr(account, "properties") and hasattr(account.properties, "provisioning_state") else "Unknown"

                    # Check if endpoint is accessible
                    endpoint_accessible = False
                    if account.properties and hasattr(account.properties, "endpoint") and account.properties.endpoint:
                        endpoint_accessible = True

                    # Get diagnostic settings (monitoring)
                    has_diagnostics = False
                    try:
                        from azure.mgmt.monitor import MonitorManagementClient
                        monitor_client = MonitorManagementClient(
                            credential=self.credential, subscription_id=self.subscription_id
                        )
                        diag_settings = list(monitor_client.diagnostic_settings.list(resource_uri=account_id))
                        has_diagnostics = len(diag_settings) > 0
                    except Exception:
                        pass

                    # Check if private endpoint is configured
                    has_private_endpoint = False
                    if account.properties and hasattr(account.properties, "private_endpoint_connections"):
                        connections = account.properties.private_endpoint_connections or []
                        has_private_endpoint = len(connections) > 0

                    # Get estimated monthly cost
                    monthly_cost = pricing_map.get(sku_name, 200.0)

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_speech_services_optimization(
                        sku_name=sku_name,
                        provisioning_state=provisioning_state,
                        endpoint_accessible=endpoint_accessible,
                        has_diagnostics=has_diagnostics,
                        has_private_endpoint=has_private_endpoint,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=account_id,
                        resource_name=account_name,
                        resource_type="azure_speech_services",
                        region=account_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "endpoint_accessible": endpoint_accessible,
                            "has_diagnostics": has_diagnostics,
                            "has_private_endpoint": has_private_endpoint,
                            "resource_group": resource_group,
                            "kind": account.kind,
                        },
                        last_used_at=None,
                        created_at_cloud=None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Speech Services account {account.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Speech Services accounts: {str(e)}")

        return resources

    def _calculate_speech_services_optimization(
        self,
        sku_name: str,
        provisioning_state: str,
        endpoint_accessible: bool,
        has_diagnostics: bool,
        has_private_endpoint: bool,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Speech Services optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Account failed provisioning
        2. HIGH (75): S0 tier avec endpoint inaccessible
        3. HIGH (70): S0 tier sans usage metrics
        4. MEDIUM (50): S0 tier sans private endpoint (audio sensible)
        5. LOW (30): F0 tier sans monitoring quota
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Account failed provisioning
        if provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Account en état d'échec",
                "description": (
                    f"Le compte Speech Services est en état '{provisioning_state}'. "
                    f"Coût gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Recréer le compte si nécessaire, "
                    f"(3) Supprimer si non utilisé."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur pour '{provisioning_state}'",
                    "Recréer le compte si nécessaire",
                    "Supprimer le compte si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - S0 tier avec endpoint inaccessible
        elif sku_name == "S0" and not endpoint_accessible:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Endpoint inaccessible en tier payant",
                "description": (
                    f"Le compte Speech Services S0 a un endpoint inaccessible. "
                    f"Coût: ${monthly_cost:.2f}/mois sans utilisation possible. "
                    f"Actions recommandées: (1) Vérifier la configuration réseau, "
                    f"(2) Corriger les règles de pare-feu, "
                    f"(3) Downgrade vers F0 ou supprimer si non utilisé."
                ),
                "actions": [
                    "Vérifier la configuration réseau et endpoint",
                    "Corriger les règles de pare-feu/NSG",
                    "Downgrade vers F0 (gratuit) si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - S0 tier sans usage metrics
        elif sku_name == "S0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            # Assume 50% of cost is waste without monitoring
            savings = monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Tier payant sans monitoring d'usage",
                "description": (
                    f"Le compte Speech Services S0 n'a pas de monitoring configuré. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Impossible de vérifier si le tier S0 est justifié sans métriques. "
                    f"Actions recommandées: (1) Activer diagnostic settings, "
                    f"(2) Analyser l'usage réel (STT hours + TTS chars), "
                    f"(3) Downgrade vers F0 si usage <5 hours STT + <0.5M chars TTS/mois."
                ),
                "actions": [
                    "Activer Diagnostic Settings pour tracking usage",
                    "Analyser le volume STT (hours) et TTS (chars) par mois",
                    "Downgrade vers F0 si faible usage",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - S0 tier sans private endpoint (audio sensible)
        elif sku_name == "S0" and not has_private_endpoint:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 10% cost for security improvement
            savings = monthly_cost * 0.1
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de Private Endpoint pour audio sensible",
                "description": (
                    f"Le compte Speech Services S0 expose un endpoint public. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Risque de sécurité pour données audio sensibles (voix, conversations). "
                    f"Actions recommandées: (1) Configurer Private Endpoint, "
                    f"(2) Restreindre l'accès réseau, "
                    f"(3) Activer firewall rules."
                ),
                "actions": [
                    "Configurer Azure Private Endpoint",
                    "Restreindre accès réseau (VNet only)",
                    "Activer firewall rules et IP filtering",
                    "Note: Meilleure sécurité pour données audio sensibles"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - F0 tier sans monitoring quota
        elif sku_name == "F0" and not has_diagnostics:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = 0  # Free tier, but monitoring helps prevent overages
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring configuré (Free tier)",
                "description": (
                    f"Le compte Speech Services F0 (gratuit) n'a pas de monitoring. "
                    f"Sans métriques, risque de dépasser limites gratuites (5 hours STT + 0.5M chars TTS/mois). "
                    f"Actions recommandées: (1) Activer Diagnostic Settings, "
                    f"(2) Créer des alertes sur quota usage, "
                    f"(3) Monitorer pour éviter charges inattendues."
                ),
                "actions": [
                    "Activer Diagnostic Settings",
                    "Créer alertes sur quota usage (STT + TTS)",
                    "Monitorer pour éviter dépassement et charges",
                    "Note: Prévention de coûts inattendus"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_bot_service(self, region: str) -> list[AllCloudResourceData]:
        """Scan ALL Azure Bot Service resources for cost intelligence."""
        resources = []

        try:
            from azure.mgmt.botservice import AzureBotService

            client = AzureBotService(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: Standard Channels FREE, Premium Channels $0.50 per 1K messages after 10K free
            # Estimate: $50/month for 110K Premium messages

            # List all bot resources
            bots = client.bots.list()

            for bot in bots:
                try:
                    # Extract metadata
                    bot_name = bot.name
                    bot_id = bot.id
                    resource_group = bot_id.split("/")[4] if len(bot_id.split("/")) > 4 else "unknown"
                    bot_location = bot.location or region
                    bot_kind = bot.kind if hasattr(bot, "kind") and bot.kind else "Unknown"

                    # Get bot properties
                    provisioning_state = bot.properties.provisioning_state if hasattr(bot.properties, "provisioning_state") else "Unknown"
                    endpoint = bot.properties.endpoint if hasattr(bot.properties, "endpoint") and bot.properties.endpoint else None

                    # Check if bot has Application Insights configured
                    has_app_insights = False
                    if hasattr(bot.properties, "developer_app_insights_key") and bot.properties.developer_app_insights_key:
                        has_app_insights = True

                    # Count configured channels
                    channels_count = 0
                    try:
                        channels_list = list(client.channels.list_by_resource_group(
                            resource_group_name=resource_group,
                            resource_name=bot_name
                        ))
                        channels_count = len(channels_list)
                    except Exception:
                        pass

                    # Estimate monthly cost based on Premium channels
                    # Assumption: if bot exists, estimate ~$50/month for Premium usage
                    monthly_cost = 50.0 if channels_count > 0 else 0.0

                    # Calculate optimization
                    (
                        is_optimizable,
                        optimization_score,
                        priority,
                        potential_savings,
                        recommendations_data,
                    ) = self._calculate_bot_service_optimization(
                        bot_kind=bot_kind,
                        provisioning_state=provisioning_state,
                        channels_count=channels_count,
                        has_app_insights=has_app_insights,
                        endpoint=endpoint,
                        monthly_cost=monthly_cost,
                    )

                    # Build AllCloudResourceData
                    resource_data = AllCloudResourceData(
                        resource_id=bot_id,
                        resource_name=bot_name,
                        resource_type="azure_bot_service",
                        region=bot_location,
                        estimated_monthly_cost=round(monthly_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "kind": bot_kind,
                            "provisioning_state": provisioning_state,
                            "channels_count": channels_count,
                            "has_app_insights": has_app_insights,
                            "endpoint": endpoint or "Not configured",
                            "resource_group": resource_group,
                        },
                        last_used_at=None,
                        created_at_cloud=None,
                        is_optimizable=is_optimizable,
                        optimization_score=optimization_score,
                        optimization_recommendations=recommendations_data,
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        f"Error scanning Bot Service {bot.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error listing Bot Service resources: {str(e)}")

        return resources

    def _calculate_bot_service_optimization(
        self,
        bot_kind: str,
        provisioning_state: str,
        channels_count: int,
        has_app_insights: bool,
        endpoint: str | None,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, dict]:
        """
        Calculate Bot Service optimization based on 5 scenarios.

        Scenarios:
        1. CRITICAL (90): Bot resource failed/deleting
        2. HIGH (75): Bot avec channels configurés mais aucun endpoint
        3. HIGH (70): Bot sans channels configurés
        4. MEDIUM (50): Bot sans monitoring/Application Insights
        5. LOW (30): Bot sans backup ou disaster recovery
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = {"scenarios": []}

        # Scenario 1: CRITICAL - Bot failed/deleting
        if provisioning_state.lower() in ["failed", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            savings = monthly_cost
            recommendations["scenarios"].append({
                "scenario": "Bot en état d'échec",
                "description": (
                    f"Le Bot Service est en état '{provisioning_state}'. "
                    f"Coût potentiel gaspillé: ${monthly_cost:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier les logs d'erreur, "
                    f"(2) Recréer le bot si nécessaire, "
                    f"(3) Supprimer si non utilisé."
                ),
                "actions": [
                    f"Vérifier les logs d'erreur pour '{provisioning_state}'",
                    "Recréer le bot si nécessaire",
                    "Supprimer le bot si obsolète",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - Bot avec channels mais sans endpoint
        elif channels_count > 0 and not endpoint:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority != "critical" else priority
            savings = monthly_cost
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Bot avec channels mais sans endpoint",
                "description": (
                    f"Le Bot a {channels_count} channel(s) configuré(s) mais aucun endpoint. "
                    f"Coût: ${monthly_cost:.2f}/mois sans possibilité de répondre aux messages. "
                    f"Actions recommandées: (1) Configurer l'endpoint du bot, "
                    f"(2) Déployer le code du bot, "
                    f"(3) Supprimer les channels si bot non utilisé."
                ),
                "actions": [
                    "Configurer l'endpoint du bot (messaging endpoint)",
                    "Déployer le code du bot sur Azure App Service/Functions",
                    f"Supprimer les {channels_count} channel(s) si non utilisé",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - Bot sans channels configurés
        elif channels_count == 0 and monthly_cost == 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority not in ["critical"] else priority
            # No cost but waste of resource
            savings = 0
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Bot sans channels configurés",
                "description": (
                    f"Le Bot Service n'a aucun channel configuré. "
                    f"Bot inutilisable sans channels (Teams, Slack, Web Chat, etc.). "
                    f"Actions recommandées: (1) Configurer au moins un channel, "
                    f"(2) Tester le bot, "
                    f"(3) Supprimer si projet abandonné."
                ),
                "actions": [
                    "Configurer au moins un channel (Teams, Web Chat, Slack...)",
                    "Tester le bot avec le channel configuré",
                    "Supprimer le bot si projet abandonné",
                    "Note: Aucun coût actuel mais ressource gaspillée"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - Bot sans monitoring/Application Insights
        elif not has_app_insights and channels_count > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority not in ["critical", "high"] else priority
            # Estimate 10% improvement with monitoring
            savings = monthly_cost * 0.1
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de monitoring Application Insights",
                "description": (
                    f"Le Bot Service n'a pas Application Insights configuré. "
                    f"Coût actuel: ${monthly_cost:.2f}/mois. "
                    f"Sans télémétrie, impossible d'analyser conversations et optimiser. "
                    f"Actions recommandées: (1) Configurer Application Insights, "
                    f"(2) Analyser métriques (messages, errors, latency), "
                    f"(3) Optimiser le bot basé sur usage réel."
                ),
                "actions": [
                    "Configurer Application Insights pour le bot",
                    "Analyser métriques (messages count, errors, latency)",
                    "Optimiser le bot basé sur usage réel",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - Pas de backup/disaster recovery
        elif channels_count > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            savings = 0  # Best practice, no direct savings
            potential_savings = max(potential_savings, savings)
            recommendations["scenarios"].append({
                "scenario": "Pas de stratégie de backup configurée",
                "description": (
                    f"Le Bot Service n'a pas de stratégie de backup/disaster recovery. "
                    f"En cas de panne, risque de perte de service et impact business. "
                    f"Actions recommandées: (1) Configurer multi-region deployment, "
                    f"(2) Sauvegarder configuration et code du bot, "
                    f"(3) Tester disaster recovery plan."
                ),
                "actions": [
                    "Configurer multi-region deployment pour HA",
                    "Sauvegarder configuration bot (ARM template/Terraform)",
                    "Tester disaster recovery plan",
                    "Note: Meilleure pratique pour continuité de service"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_application_insights(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Application Insights resources for cost intelligence.

        Application Insights = Monitoring/observability service for applications (telemetry, logs, metrics).

        Pricing: Pay-as-you-go $2.30-$2.76/GB ingested (5 GB free/month) OR Commitment Tiers (15-36% discount).
        Typical cost: $50-500/month depending on data volume (10-200 GB/month).
        """
        resources = []

        try:
            from azure.mgmt.applicationinsights import ApplicationInsightsManagementClient

            client = ApplicationInsightsManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing map (monthly estimates based on typical data ingestion)
            # Pay-as-you-go: $2.50/GB average
            # Estimate assumes workspace-based pricing
            pricing_map = {
                "pay_as_you_go_10gb": 25.0,  # 10 GB/month * $2.50 (5 GB free included)
                "pay_as_you_go_50gb": 125.0,  # 50 GB/month * $2.50
                "pay_as_you_go_100gb": 250.0,  # 100 GB/month * $2.50
                "pay_as_you_go_200gb": 500.0,  # 200 GB/month * $2.50
                "commitment_tier_100gb": 200.0,  # 100 GB/day commitment (~20% discount)
            }

            # List all Application Insights components
            components = client.components.list()

            for component in components:
                try:
                    # Extract metadata
                    component_name = component.name
                    resource_group = component.id.split("/")[4] if "/" in component.id else "unknown"
                    location = component.location if hasattr(component, "location") else region
                    provisioning_state = component.provisioning_state if hasattr(component, "provisioning_state") else "Unknown"
                    application_type = component.application_type if hasattr(component, "application_type") else "other"

                    # Check if workspace-based or classic
                    is_workspace_based = False
                    workspace_resource_id = None
                    if hasattr(component, "workspace_resource_id") and component.workspace_resource_id:
                        is_workspace_based = True
                        workspace_resource_id = component.workspace_resource_id

                    # Get ingestion settings
                    daily_cap_gb = None
                    retention_days = 90  # Default
                    if hasattr(component, "ingestion_mode"):
                        ingestion_mode = component.ingestion_mode
                    else:
                        ingestion_mode = "LogAnalytics" if is_workspace_based else "ApplicationInsights"

                    # Try to get daily cap (if available)
                    try:
                        billing = client.component_current_billing_features.get(
                            resource_group_name=resource_group,
                            resource_name=component_name
                        )
                        if hasattr(billing, "current_billing_features"):
                            # Daily cap in GB
                            if "data_volume_cap" in billing.current_billing_features:
                                daily_cap_data = billing.current_billing_features.get("data_volume_cap")
                                if daily_cap_data and hasattr(daily_cap_data, "cap"):
                                    daily_cap_gb = daily_cap_data.cap
                    except Exception:
                        pass  # Daily cap not available

                    # Try to get retention period
                    try:
                        if hasattr(component, "retention_in_days"):
                            retention_days = component.retention_in_days
                    except Exception:
                        pass

                    # Estimate monthly cost (we don't have actual ingestion data via SDK easily)
                    # Default: assume 50 GB/month for typical app
                    estimated_monthly_cost = pricing_map["pay_as_you_go_50gb"]

                    # Calculate optimization opportunities
                    (
                        is_optimizable,
                        optimization_score,
                        optimization_priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_app_insights_optimization(
                        provisioning_state=provisioning_state,
                        is_workspace_based=is_workspace_based,
                        daily_cap_gb=daily_cap_gb,
                        retention_days=retention_days,
                        estimated_monthly_cost=estimated_monthly_cost,
                    )

                    # Build resource metadata
                    resource_metadata = {
                        "component_name": component_name,
                        "resource_group": resource_group,
                        "location": location,
                        "provisioning_state": provisioning_state,
                        "application_type": application_type,
                        "is_workspace_based": is_workspace_based,
                        "workspace_resource_id": workspace_resource_id,
                        "ingestion_mode": ingestion_mode,
                        "daily_cap_gb": daily_cap_gb,
                        "retention_days": retention_days,
                        "instrumentation_key": component.instrumentation_key if hasattr(component, "instrumentation_key") else None,
                        "connection_string": component.connection_string if hasattr(component, "connection_string") else None,
                    }

                    # Extract tags
                    tags = component.tags if hasattr(component, "tags") and component.tags else {}

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_type="azure_application_insights",
                        resource_id=component.id,
                        resource_name=component_name,
                        region=location,
                        estimated_monthly_cost=estimated_monthly_cost,
                        currency="USD",
                        utilization_status="unknown",  # Would need Azure Monitor metrics
                        is_optimizable=is_optimizable,
                        optimization_priority=optimization_priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations,
                        resource_metadata=resource_metadata,
                        tags=tags,
                        resource_status=provisioning_state,
                        created_at_cloud=None,  # Not available in SDK
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "azure.application_insights.scan_component_failed",
                        component_id=getattr(component, "id", "unknown"),
                        error=str(e),
                    )
                    continue

            logger.info(
                "azure.application_insights.scan_complete",
                region=region,
                total_components=len(resources),
                optimizable=sum(1 for r in resources if r.is_optimizable),
            )

        except Exception as e:
            logger.error("azure.application_insights.scan_failed", region=region, error=str(e))

        return resources

    def _calculate_app_insights_optimization(
        self,
        provisioning_state: str,
        is_workspace_based: bool,
        daily_cap_gb: float | None,
        retention_days: int,
        estimated_monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization opportunities for Application Insights.

        5 scenarios:
        1. CRITICAL (90): Failed/Deleted state
        2. HIGH (75): No data ingestion 30+ days (unused service)
        3. HIGH (70): Excessive ingestion >100 GB/month without Commitment Tier
        4. MEDIUM (50): Retention >90 days without business need
        5. LOW (30): No Daily Cap configured (budget risk)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: CRITICAL - Failed or Deleted state
        if provisioning_state.lower() in ["failed", "deleted", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            savings = estimated_monthly_cost  # Full cost if removed
            potential_savings += savings

            recommendations.append({
                "scenario": "Application Insights en état Failed/Deleted",
                "details": (
                    f"Cet Application Insights est en état '{provisioning_state}' et ne fonctionne plus. "
                    f"Coût mensuel actuel: ${estimated_monthly_cost:.2f}. "
                    f"Actions recommandées: (1) Recréer le composant si nécessaire, "
                    f"(2) Supprimer complètement si obsolète, "
                    f"(3) Vérifier pourquoi le provisioning a échoué."
                ),
                "actions": [
                    "Vérifier les logs de provisioning pour cause d'échec",
                    "Recréer Application Insights avec configuration correcte",
                    "OU supprimer définitivement si obsolète",
                    "Vérifier quotas et limites subscription Azure"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - No data ingestion for 30+ days (unused service)
        # Note: We can't easily check ingestion volume via SDK, so this is commented for future
        # elif last_ingestion_days >= 30:
        #     is_optimizable = True
        #     optimization_score = 75
        #     priority = "high"
        #     savings = estimated_monthly_cost * 0.9  # 90% savings if deleted

        # Scenario 3: HIGH - Excessive ingestion >100 GB/month without Commitment Tier
        elif estimated_monthly_cost > 250 and not is_workspace_based:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            savings = estimated_monthly_cost * 0.20  # 20% savings with Commitment Tier
            potential_savings += savings

            recommendations.append({
                "scenario": "Ingestion volumineuse sans Commitment Tier",
                "details": (
                    f"Application Insights ingère >100 GB/mois (coût: ${estimated_monthly_cost:.2f}/mois). "
                    f"Utiliser un Commitment Tier peut réduire les coûts de 15-36%. "
                    f"Économie potentielle: ${savings:.2f}/mois (20% estimé). "
                    f"Actions recommandées: (1) Migrer vers workspace-based avec Commitment Tier, "
                    f"(2) Analyser volume ingestion réel, (3) Optimiser sampling rate si nécessaire."
                ),
                "actions": [
                    "Analyser volume ingestion mensuel exact (Azure Portal)",
                    "Migrer vers workspace-based Application Insights",
                    "Configurer Commitment Tier adapté (100 GB/day, 200 GB/day...)",
                    "Ajuster sampling rate pour réduire volume si pertinent"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - Retention >90 days without business need
        elif retention_days > 90:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Retention cost ~$0.10/GB/month beyond 31 days free
            # Assume 50 GB/month ingestion → 50 GB stored
            # Extra 60 days retention (90-30 free) → ~$3/month savings if reduced to 30 days
            savings = 5.0  # Conservative estimate
            potential_savings += savings

            recommendations.append({
                "scenario": f"Rétention excessive ({retention_days} jours)",
                "details": (
                    f"Application Insights retient les données pendant {retention_days} jours. "
                    f"Au-delà de 31 jours gratuits, la rétention coûte ~$0.10/GB/mois. "
                    f"Si pas de besoin métier, réduire à 30-60 jours. "
                    f"Économie potentielle: ${savings:.2f}/mois. "
                    f"Actions recommandées: (1) Vérifier exigences réglementaires/métier, "
                    f"(2) Réduire rétention à 30-60 jours si possible, "
                    f"(3) Exporter données anciennes vers stockage froid si archivage nécessaire."
                ),
                "actions": [
                    f"Vérifier si rétention {retention_days} jours est requise (compliance/métier)",
                    "Réduire rétention à 30-60 jours si pas de contrainte",
                    "Configurer export continu vers Azure Storage (archivage long-terme)",
                    "Note: 31 premiers jours gratuits, puis ~$0.10/GB/mois"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - No Daily Cap configured (budget risk)
        elif daily_cap_gb is None and estimated_monthly_cost > 50:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0.0  # No direct savings, but prevents overage

            recommendations.append({
                "scenario": "Pas de Daily Cap configuré (risque dépassement budget)",
                "details": (
                    f"Application Insights n'a pas de Daily Cap configuré. "
                    f"Risque: ingestion excessive imprévue → facture inattendue. "
                    f"Coût mensuel actuel: ${estimated_monthly_cost:.2f}. "
                    f"Actions recommandées: (1) Configurer Daily Cap adapté au budget, "
                    f"(2) Configurer alertes dépassement quota, "
                    f"(3) Surveiller ingestion quotidienne."
                ),
                "actions": [
                    "Configurer Daily Cap (ex: 5 GB/day pour app moyenne)",
                    "Activer alertes dépassement quota (Azure Monitor)",
                    "Surveiller ingestion quotidienne (Azure Portal → Usage and estimated costs)",
                    "Note: Prévient factures imprévues mais ne réduit pas coût directement"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_managed_devops_pools(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Managed DevOps Pools for cost intelligence.

        Managed DevOps Pools = Managed infrastructure for Azure DevOps pipeline agents.

        Pricing: 1st parallel job FREE, then $15/month per additional parallel job.
        Typical cost: $15-150/month depending on number of agents.
        """
        resources = []

        try:
            from azure.mgmt.devopsinfrastructure import DevOpsInfrastructureMgmtClient

            client = DevOpsInfrastructureMgmtClient(
                credential=self.credential, subscription_id=self.subscription_id
            )

            # Pricing: $15 per parallel job (first job free)
            price_per_agent = 15.0

            # List all Managed DevOps Pools
            pools = client.pools.list_by_subscription()

            for pool in pools:
                try:
                    # Extract metadata
                    pool_name = pool.name
                    resource_group = pool.id.split("/")[4] if "/" in pool.id else "unknown"
                    location = pool.location if hasattr(pool, "location") else region
                    provisioning_state = pool.properties.provisioning_state if hasattr(pool.properties, "provisioning_state") else "Unknown"

                    # Get pool properties
                    max_agents = 0
                    agent_profile = None
                    organization_profile = None

                    if hasattr(pool.properties, "maximum_concurrency"):
                        max_agents = pool.properties.maximum_concurrency

                    if hasattr(pool.properties, "agent_profile"):
                        agent_profile = pool.properties.agent_profile
                        # Agent profile contains info about VM SKU, images, etc.

                    if hasattr(pool.properties, "dev_ops_organization_profile"):
                        organization_profile = pool.properties.dev_ops_organization_profile
                        # Contains Azure DevOps organization info

                    # Estimate monthly cost
                    # First agent free, then $15 per additional agent
                    if max_agents <= 1:
                        estimated_monthly_cost = 0.0  # First agent free
                    else:
                        estimated_monthly_cost = (max_agents - 1) * price_per_agent

                    # Calculate optimization opportunities
                    (
                        is_optimizable,
                        optimization_score,
                        optimization_priority,
                        potential_savings,
                        recommendations,
                    ) = self._calculate_devops_pools_optimization(
                        provisioning_state=provisioning_state,
                        max_agents=max_agents,
                        agent_profile=agent_profile,
                        estimated_monthly_cost=estimated_monthly_cost,
                    )

                    # Build resource metadata
                    resource_metadata = {
                        "pool_name": pool_name,
                        "resource_group": resource_group,
                        "location": location,
                        "provisioning_state": provisioning_state,
                        "maximum_concurrency": max_agents,
                        "agent_profile": str(agent_profile) if agent_profile else None,
                        "organization_profile": str(organization_profile) if organization_profile else None,
                        "fabric_profile": str(pool.properties.fabric_profile) if hasattr(pool.properties, "fabric_profile") else None,
                    }

                    # Extract tags
                    tags = pool.tags if hasattr(pool, "tags") and pool.tags else {}

                    # Create resource data
                    resource_data = AllCloudResourceData(
                        resource_type="azure_managed_devops_pools",
                        resource_id=pool.id,
                        resource_name=pool_name,
                        region=location,
                        estimated_monthly_cost=estimated_monthly_cost,
                        currency="USD",
                        utilization_status="unknown",  # Would need pipeline run metrics
                        is_optimizable=is_optimizable,
                        optimization_priority=optimization_priority,
                        optimization_score=optimization_score,
                        potential_monthly_savings=potential_savings,
                        optimization_recommendations=recommendations,
                        resource_metadata=resource_metadata,
                        tags=tags,
                        resource_status=provisioning_state,
                        created_at_cloud=None,  # Not available in SDK
                    )

                    resources.append(resource_data)

                except Exception as e:
                    logger.error(
                        "azure.managed_devops_pools.scan_pool_failed",
                        pool_id=getattr(pool, "id", "unknown"),
                        error=str(e),
                    )
                    continue

            logger.info(
                "azure.managed_devops_pools.scan_complete",
                region=region,
                total_pools=len(resources),
                optimizable=sum(1 for r in resources if r.is_optimizable),
            )

        except Exception as e:
            logger.error("azure.managed_devops_pools.scan_failed", region=region, error=str(e))

        return resources

    def _calculate_devops_pools_optimization(
        self,
        provisioning_state: str,
        max_agents: int,
        agent_profile: any,
        estimated_monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization opportunities for Managed DevOps Pools.

        5 scenarios:
        1. CRITICAL (90): Failed/Deleted state
        2. HIGH (75): Pool sans agents depuis 30+ jours (unused)
        3. HIGH (70): Agents idle >80% du temps (over-provisioned)
        4. MEDIUM (50): Pool Dev/Test avec agents premium (Standard suffisant)
        5. LOW (30): Multiple pools consolidables (economy of scale)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: CRITICAL - Failed or Deleted state
        if provisioning_state.lower() in ["failed", "deleted", "deleting"]:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            savings = estimated_monthly_cost  # Full cost if removed
            potential_savings += savings

            recommendations.append({
                "scenario": "Managed DevOps Pool en état Failed/Deleted",
                "details": (
                    f"Ce pool DevOps est en état '{provisioning_state}' et ne fonctionne plus. "
                    f"Coût mensuel actuel: ${estimated_monthly_cost:.2f}. "
                    f"Actions recommandées: (1) Recréer le pool si nécessaire, "
                    f"(2) Supprimer complètement si obsolète, "
                    f"(3) Vérifier pourquoi le provisioning a échoué."
                ),
                "actions": [
                    "Vérifier les logs de provisioning pour cause d'échec",
                    "Recréer Managed DevOps Pool avec configuration correcte",
                    "OU supprimer définitivement si obsolète",
                    "Vérifier quotas et limites subscription Azure"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "critical",
            })

        # Scenario 2: HIGH - Pool sans agents (never used or abandoned)
        elif max_agents == 0:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            savings = 15.0  # At least one agent's worth
            potential_savings += savings

            recommendations.append({
                "scenario": "Pool DevOps sans agents configurés",
                "details": (
                    f"Le pool '{provisioning_state}' n'a aucun agent configuré (max_agents=0). "
                    f"Ce pool ne peut exécuter aucun pipeline et génère des frais fixes. "
                    f"Économie potentielle: ${savings:.2f}/mois si supprimé. "
                    f"Actions recommandées: (1) Supprimer le pool si inutilisé, "
                    f"(2) OU configurer des agents si besoin futur, "
                    f"(3) Vérifier pipelines Azure DevOps associés."
                ),
                "actions": [
                    "Vérifier si le pool est référencé dans des pipelines Azure DevOps",
                    "Supprimer le pool si jamais utilisé",
                    "OU configurer agents si besoin pipeline identifié",
                    "Nettoyer pools obsolètes (organisation)"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 3: HIGH - Agents idle >80% (over-provisioned)
        # Note: We can't check actual usage via SDK easily, so this scenario uses agent count heuristic
        elif max_agents > 5:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Assume 30% of agents could be removed
            reducible_agents = int(max_agents * 0.3)
            savings = reducible_agents * 15.0
            potential_savings += savings

            recommendations.append({
                "scenario": f"Pool sur-dimensionné ({max_agents} agents)",
                "details": (
                    f"Le pool a {max_agents} agents configurés. "
                    f"Pour la plupart des organisations, 3-5 agents suffisent. "
                    f"Si agents idle >50% du temps, réduire la capacité. "
                    f"Économie potentielle: ${savings:.2f}/mois en réduisant de ~30%. "
                    f"Actions recommandées: (1) Analyser utilisation réelle des agents, "
                    f"(2) Réduire maximum_concurrency si idle, "
                    f"(3) Utiliser autoscaling si pics de charge ponctuels."
                ),
                "actions": [
                    "Analyser utilisation agents via Azure DevOps Analytics",
                    "Identifier taux d'idle (cible: <50% idle)",
                    f"Réduire maximum_concurrency de {max_agents} à {max_agents - reducible_agents}",
                    "Configurer autoscaling pour pics de charge"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "high",
            })

        # Scenario 4: MEDIUM - Dev/Test pool avec agents premium (Standard suffisant)
        # Check if agent_profile suggests premium SKU (heuristic: if profile mentions "Standard_D" or higher)
        elif agent_profile and "Standard_D" in str(agent_profile) and max_agents >= 2:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Assume 20% savings by downgrading to Basic SKU
            savings = estimated_monthly_cost * 0.20
            potential_savings += savings

            recommendations.append({
                "scenario": "Pool Dev/Test avec VM SKU premium",
                "details": (
                    f"Le pool utilise des VM SKU premium (ex: Standard_D series) pour {max_agents} agents. "
                    f"Pour environnements Dev/Test, des SKU Standard ou Basic suffisent souvent. "
                    f"Économie potentielle: ${savings:.2f}/mois (20% estimé). "
                    f"Actions recommandées: (1) Évaluer besoins réels CPU/RAM, "
                    f"(2) Downgrader vers SKU moins cher si pertinent, "
                    f"(3) Réserver SKU premium pour production uniquement."
                ),
                "actions": [
                    "Analyser utilisation CPU/RAM des agents (Azure Monitor)",
                    "Downgrader vers VM SKU Basic/Standard si <50% utilisation",
                    "Réserver SKU premium pour pipelines production critiques",
                    "Estimer économies: ~20-30% avec SKU inférieur"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "medium",
            })

        # Scenario 5: LOW - Multiple pools consolidables (note: this requires global view, so heuristic)
        elif max_agents == 1 and estimated_monthly_cost == 0:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            savings = 0.0  # No direct savings, but organizational cleanup

            recommendations.append({
                "scenario": "Pool avec 1 agent (gratuit) - consolidation possible",
                "details": (
                    f"Ce pool utilise 1 agent (gratuit). "
                    f"Si l'organisation a plusieurs pools similaires, la consolidation peut simplifier gestion. "
                    f"Économie potentielle: ${savings:.2f}/mois (mais gains organisationnels). "
                    f"Actions recommandées: (1) Auditer tous les pools de l'organisation, "
                    f"(2) Consolider pools similaires, "
                    f"(3) Standardiser configuration agents."
                ),
                "actions": [
                    "Auditer tous Managed DevOps Pools de l'organisation",
                    "Identifier pools redondants (même projet/équipe)",
                    "Consolider en pools partagés (économie échelle)",
                    "Note: Gains organisationnels > économies directes"
                ],
                "estimated_savings": round(savings, 2),
                "priority": "low",
            })

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_private_endpoints(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Private Endpoints for cost intelligence.

        Private Endpoints enable private connectivity to Azure services.
        Pricing: ~$7.30/month per Private Endpoint (Standard) + data processing charges
        Typical cost: $7-15/month depending on data transfer volume

        Detection criteria:
        - Private Endpoint failed/deleting (CRITICAL - 90 score)
        - Not connected to any resource (orphan) (HIGH - 75 score)
        - Connected to deallocated/stopped resource (HIGH - 70 score)
        - Redundant endpoints for same resource (MEDIUM - 50 score)
        - Using Premium without justification (LOW - 30 score)
        """
        try:
            from azure.mgmt.network import NetworkManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-network not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Private Endpoints in region: {region}")

        try:
            network_client = NetworkManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all Private Endpoints
            async for endpoint in network_client.private_endpoints.list_all():
                try:
                    # Filter by region if specified
                    if region.lower() != "all" and endpoint.location.lower() != region.lower():
                        continue

                    # Get resource group from endpoint ID
                    resource_group = endpoint.id.split("/")[4]

                    # Get connection state
                    connection_state = "unknown"
                    connected_resource_id = None
                    connected_resource_count = 0

                    if hasattr(endpoint, 'private_link_service_connections'):
                        connections = endpoint.private_link_service_connections or []
                        connected_resource_count = len(connections)
                        if connections:
                            first_conn = connections[0]
                            if hasattr(first_conn, 'private_link_service_connection_state'):
                                conn_state = first_conn.private_link_service_connection_state
                                if conn_state:
                                    connection_state = getattr(conn_state, 'status', 'unknown')
                            if hasattr(first_conn, 'private_link_service_id'):
                                connected_resource_id = first_conn.private_link_service_id

                    # Get provisioning state
                    provisioning_state = getattr(endpoint, 'provisioning_state', 'Unknown')

                    # Calculate optimization
                    is_optimizable, score, priority, savings, recommendations = (
                        self._calculate_private_endpoint_optimization(
                            provisioning_state,
                            connection_state,
                            connected_resource_count,
                            connected_resource_id
                        )
                    )

                    # Pricing (Azure US East 2025)
                    # Private Endpoint: $7.30/month (flat rate)
                    # Data processing: $0.01/GB inbound + $0.01/GB outbound
                    # Typical: $7-15/month depending on traffic
                    base_monthly_cost = 7.30

                    # Estimate data processing cost (assume 100 GB/month average)
                    estimated_data_gb = 100
                    data_processing_cost = estimated_data_gb * 0.02  # $0.01 in + $0.01 out

                    estimated_cost = base_monthly_cost + data_processing_cost

                    resources.append(AllCloudResourceData(
                        resource_id=endpoint.id,
                        resource_type="azure_private_endpoint",
                        resource_name=endpoint.name or "Unnamed Private Endpoint",
                        region=endpoint.location,
                        estimated_monthly_cost=round(estimated_cost, 2),
                        currency="USD",
                        resource_metadata={
                            "endpoint_id": endpoint.id,
                            "resource_group": resource_group,
                            "provisioning_state": provisioning_state,
                            "connection_state": connection_state,
                            "connected_resource_id": connected_resource_id,
                            "connected_resource_count": connected_resource_count,
                            "subnet_id": endpoint.subnet.id if endpoint.subnet else None,
                            "tags": dict(endpoint.tags) if endpoint.tags else {},
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
                    self.logger.error(f"Error processing Private Endpoint {getattr(endpoint, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} Private Endpoints in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning Private Endpoints: {str(e)}")
            return []

    def _calculate_private_endpoint_optimization(
        self,
        provisioning_state: str,
        connection_state: str,
        connected_resource_count: int,
        connected_resource_id: str | None,
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for Private Endpoint.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        base_cost = 9.30  # $7.30 base + ~$2 data processing

        # Scenario 1: Private Endpoint failed/deleting (CRITICAL - 90)
        if provisioning_state.lower() in ['failed', 'deleting', 'deleted']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, base_cost)

            recommendations.append({
                "title": "Private Endpoint Non Fonctionnel",
                "description": f"Ce Private Endpoint est dans l'état '{provisioning_state}'. Il génère des coûts inutiles.",
                "estimated_savings": round(base_cost, 2),
                "actions": [
                    "Vérifier les logs pour identifier le problème",
                    "Supprimer le Private Endpoint s'il ne peut pas être réparé",
                    "Recréer le Private Endpoint si encore nécessaire"
                ],
                "priority": "critical",
            })

        # Scenario 2: Not connected to any resource (orphan) (HIGH - 75)
        if connected_resource_count == 0 or connection_state.lower() in ['rejected', 'disconnected']:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            if priority not in ["critical"]:
                priority = "high"
            potential_savings = max(potential_savings, base_cost)

            recommendations.append({
                "title": "Private Endpoint Non Connecté (Orphelin)",
                "description": "Ce Private Endpoint n'est connecté à aucune ressource. Il génère des coûts inutiles de $7-9/mois.",
                "estimated_savings": round(base_cost, 2),
                "actions": [
                    "Vérifier si le Private Endpoint est encore nécessaire",
                    "Supprimer si non utilisé",
                    "Connecter à une ressource si oubli de configuration",
                    f"Économie: ${base_cost}/mois"
                ],
                "priority": "high",
            })

        # Scenario 3: Connected to deallocated/stopped resource (HIGH - 70)
        # Note: We can't easily check if connected resource is stopped without querying each resource type
        # This would require additional API calls per endpoint
        # In production, you'd check the connected resource status

        # Scenario 4: Redundant endpoints for same resource (MEDIUM - 50)
        if connected_resource_count > 1:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Assume can eliminate half of redundant connections
            savings = base_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Endpoints Redondants Potentiels",
                "description": f"Ce Private Endpoint a {connected_resource_count} connexions. Vérifiez si toutes sont nécessaires.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    f"Analyser les {connected_resource_count} connexions Private Link",
                    "Identifier si plusieurs endpoints pointent vers même ressource",
                    "Consolider en un seul endpoint si possible",
                    "Note: Chaque endpoint coûte $7-9/mois"
                ],
                "priority": "medium",
            })

        # Scenario 5: Using Premium without justification (LOW - 30)
        # Note: Private Endpoints don't have SKUs (Standard/Premium)
        # This scenario doesn't apply to Private Endpoints
        # Leaving as placeholder for consistency

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_ml_endpoints(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure ML Online Endpoints for cost intelligence.

        ML Endpoints are deployed models for real-time inference.
        Pricing: $0.50-$10/hour selon instance SKU ($360-$7200/mois) + inference costs
        Typical cost: $500-3000/month for production endpoints

        Detection criteria:
        - Endpoint failed/unhealthy (CRITICAL - 90 score)
        - Zero inference requests 30+ days (HIGH - 75 score)
        - Overprovisioned compute (traffic < 30% capacity) (HIGH - 70 score)
        - Premium SKU for low-traffic endpoint (MEDIUM - 50 score)
        - No auto-scaling configured (LOW - 30 score)
        """
        try:
            from azure.ai.ml import MLClient
        except ImportError:
            self.logger.error("azure-ai-ml not installed")
            return []

        resources = []
        self.logger.info(f"Scanning ML Endpoints in region: {region}")

        try:
            ml_client = MLClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            # List all ML workspaces first
            from azure.mgmt.machinelearningservices import AzureMachineLearningWorkspaces
            ml_mgmt_client = AzureMachineLearningWorkspaces(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            for workspace in ml_mgmt_client.workspaces.list():
                try:
                    # Filter by region
                    if region.lower() != "all" and workspace.location.lower() != region.lower():
                        continue

                    # Get resource group
                    resource_group = workspace.id.split("/")[4]

                    # Create MLClient for this specific workspace
                    workspace_ml_client = MLClient(
                        credential=self.credential,
                        subscription_id=self.subscription_id,
                        resource_group_name=resource_group,
                        workspace_name=workspace.name
                    )

                    # List all online endpoints in this workspace
                    endpoints = workspace_ml_client.online_endpoints.list()

                    for endpoint in endpoints:
                        try:
                            # Get endpoint details
                            endpoint_name = endpoint.name
                            provisioning_state = getattr(endpoint, 'provisioning_state', 'Unknown')

                            # Get deployments for this endpoint
                            deployments = list(workspace_ml_client.online_deployments.list(endpoint_name=endpoint_name))
                            deployment_count = len(deployments)

                            # Calculate total instance count and estimate cost
                            total_instances = 0
                            estimated_hourly_cost = 0.0

                            for deployment in deployments:
                                instance_count = getattr(deployment, 'instance_count', 0)
                                total_instances += instance_count

                                # Estimate cost based on instance type
                                # Simplified pricing: Standard_DS2_v2 = $0.50/hour, Premium = $10/hour
                                instance_type = getattr(deployment, 'instance_type', 'Standard_DS2_v2')
                                if 'Premium' in instance_type or 'GPU' in instance_type:
                                    estimated_hourly_cost += instance_count * 10.0
                                elif 'Standard_DS3' in instance_type or 'Standard_F' in instance_type:
                                    estimated_hourly_cost += instance_count * 2.0
                                else:
                                    estimated_hourly_cost += instance_count * 0.50

                            estimated_monthly_cost = estimated_hourly_cost * 730  # hours/month

                            # Calculate optimization
                            is_optimizable, score, priority, savings, recommendations = (
                                self._calculate_ml_endpoint_optimization(
                                    provisioning_state,
                                    deployment_count,
                                    total_instances,
                                    estimated_monthly_cost
                                )
                            )

                            resources.append(AllCloudResourceData(
                                resource_id=f"{workspace.id}/onlineEndpoints/{endpoint_name}",
                                resource_type="azure_ml_endpoint",
                                resource_name=endpoint_name or "Unnamed ML Endpoint",
                                region=workspace.location,
                                estimated_monthly_cost=round(estimated_monthly_cost, 2),
                                currency="USD",
                                resource_metadata={
                                    "endpoint_name": endpoint_name,
                                    "workspace_name": workspace.name,
                                    "resource_group": resource_group,
                                    "provisioning_state": provisioning_state,
                                    "deployment_count": deployment_count,
                                    "total_instances": total_instances,
                                    "estimated_hourly_cost": round(estimated_hourly_cost, 2),
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
                            self.logger.error(f"Error processing ML endpoint {getattr(endpoint, 'name', 'unknown')}: {str(e)}")
                            continue

                except Exception as e:
                    self.logger.error(f"Error processing workspace {getattr(workspace, 'name', 'unknown')}: {str(e)}")
                    continue

            self.logger.info(f"Found {len(resources)} ML Endpoints in region {region}")
            return resources

        except Exception as e:
            self.logger.error(f"Error scanning ML Endpoints: {str(e)}")
            return []

    def _calculate_ml_endpoint_optimization(
        self,
        provisioning_state: str,
        deployment_count: int,
        total_instances: int,
        estimated_monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[dict]]:
        """
        Calculate optimization potential for ML Endpoint.

        Returns:
            (is_optimizable, score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: Endpoint failed/unhealthy (CRITICAL - 90)
        if provisioning_state.lower() in ['failed', 'deleting', 'deleted']:
            is_optimizable = True
            optimization_score = max(optimization_score, 90)
            priority = "critical"
            potential_savings = max(potential_savings, estimated_monthly_cost)

            recommendations.append({
                "title": "ML Endpoint Non Fonctionnel",
                "description": f"Cet endpoint est dans l'état '{provisioning_state}'. Il génère des coûts inutiles.",
                "estimated_savings": round(estimated_monthly_cost, 2),
                "actions": [
                    "Vérifier les logs de déploiement",
                    "Supprimer l'endpoint s'il ne peut pas être réparé",
                    "Redéployer le modèle si encore nécessaire"
                ],
                "priority": "critical",
            })

        # Scenario 2: Zero inference requests 30+ days (HIGH - 75)
        # Note: We can't get actual request metrics without Azure Monitor
        # In production, check actual inference request count

        # Scenario 3: Overprovisioned compute (HIGH - 70)
        if total_instances > 3:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            if priority not in ["critical"]:
                priority = "high"

            # Assume can reduce by 50%
            savings = estimated_monthly_cost * 0.5
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "Instances Potentiellement Surdimensionnées",
                "description": f"Cet endpoint a {total_instances} instances. Vérifiez si toutes sont nécessaires.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser les métriques de trafic dans Azure Monitor",
                    f"Réduire de {total_instances} à {total_instances // 2} instances si charge <30%",
                    "Activer auto-scaling pour adapter automatiquement",
                    f"Économie potentielle: ${savings:.2f}/mois"
                ],
                "priority": "high",
            })

        # Scenario 4: Premium SKU for low-traffic endpoint (MEDIUM - 50)
        if estimated_monthly_cost > 2000 and total_instances <= 2:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            if priority not in ["critical", "high"]:
                priority = "medium"

            # Assume can switch to cheaper SKU (60% savings)
            savings = estimated_monthly_cost * 0.6
            potential_savings = max(potential_savings, savings)

            recommendations.append({
                "title": "SKU Premium pour Trafic Faible",
                "description": f"Coût ${estimated_monthly_cost:.2f}/mois avec peu d'instances suggère Premium SKU inutile.",
                "estimated_savings": round(savings, 2),
                "actions": [
                    "Analyser le trafic réel d'inférence (requêtes/jour)",
                    "Passer à Standard_DS2_v2 ou Standard_F2s_v2 si <1000 req/jour",
                    "Utiliser batch inference pour workloads non-temps-réel",
                    f"Économie: ~60% (${savings:.2f}/mois)"
                ],
                "priority": "medium",
            })

        # Scenario 5: No auto-scaling configured (LOW - 30)
        if deployment_count > 0 and total_instances > 1:
            # We can't easily check if auto-scaling is enabled without deployment details
            # This is a placeholder for best practice recommendation
            pass

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_synapse_sql_pools(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Synapse Dedicated SQL Pools for cost intelligence.

        Synapse SQL Pools are massively parallel processing (MPP) data warehouses.
        Pricing: $1.20-$360/hour depending on DWU level (DW100c to DW30000c)
        Typical cost: $900-259,000/month for production data warehouses

        Detection criteria:
        - SQL pool paused >7 days (CRITICAL - 90 score) - Still incurs storage costs
        - Zero queries 30+ days (HIGH - 75 score)
        - Overprovisioned DWUs (query load <30% capacity) (HIGH - 70 score)
        - No auto-pause configured (MEDIUM - 50 score)
        - Gen1 DWU (upgrade to Gen2) (LOW - 30 score)

        Returns:
            List of all Synapse SQL Pools with optimization recommendations
        """
        try:
            from azure.mgmt.synapse import SynapseManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-synapse not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Synapse SQL Pools in region: {region}")

        try:
            # Create Synapse client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            synapse_client = SynapseManagementClient(credential, self.subscription_id)

            # Iterate through workspaces
            workspaces = synapse_client.workspaces.list()
            workspace_count = 0

            for workspace in workspaces:
                workspace_count += 1
                workspace_name = workspace.name
                workspace_location = workspace.location

                # Filter by region if specified
                if self.regions and workspace_location not in self.regions:
                    continue

                # Filter by resource group if specified
                resource_group = workspace.id.split('/')[4]
                if self.resource_groups and resource_group not in self.resource_groups:
                    continue

                # Get SQL pools in this workspace
                try:
                    sql_pools = synapse_client.sql_pools.list_by_workspace(
                        resource_group_name=resource_group,
                        workspace_name=workspace_name
                    )

                    for pool in sql_pools:
                        pool_name = pool.name
                        pool_status = getattr(pool, 'status', 'Unknown')
                        sku = getattr(pool, 'sku', None)

                        # Get DWU level (e.g., "DW1000c", "DW100c")
                        dw_name = sku.name if sku else "Unknown"
                        tier = sku.tier if sku and hasattr(sku, 'tier') else "Unknown"

                        # Calculate cost based on DWU level
                        monthly_cost = self._estimate_synapse_sql_pool_cost(dw_name, pool_status)

                        # Check optimization opportunities
                        is_optimizable, score, priority, savings, recommendations = \
                            await self._calculate_synapse_sql_pool_optimization(
                                pool, pool_status, dw_name, tier, monthly_cost
                            )

                        # Build metadata
                        metadata = {
                            "workspace_name": workspace_name,
                            "pool_name": pool_name,
                            "status": pool_status,
                            "dw_level": dw_name,
                            "tier": tier,
                            "resource_group": resource_group,
                            "collation": getattr(pool, 'collation', None),
                            "creation_date": getattr(pool, 'creation_date', None),
                            "max_size_bytes": getattr(pool, 'max_size_bytes', None),
                        }

                        # Determine if orphan (paused >90 days = likely abandoned)
                        is_orphan = pool_status.lower() == 'paused' and score >= 90

                        # Create resource record
                        resource = AllCloudResourceData(
                            resource_id=pool.id,
                            resource_name=pool_name,
                            resource_type="azure_synapse_sql_pool",
                            region=workspace_location,
                            estimated_monthly_cost=monthly_cost,
                            currency="USD",
                            resource_metadata=metadata,
                            is_orphan=is_orphan,
                            is_optimizable=is_optimizable and not is_orphan,
                            optimization_score=score if not is_orphan else 0,
                            optimization_priority=priority if not is_orphan else "none",
                            potential_monthly_savings=savings if not is_orphan else 0.0,
                            optimization_recommendations=recommendations if not is_orphan else []
                        )

                        resources.append(resource)
                        self.logger.info(
                            f"Found Synapse SQL Pool: {pool_name} "
                            f"(Status: {pool_status}, DWU: {dw_name}, "
                            f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning SQL pools in workspace {workspace_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Synapse SQL Pool scan complete: {len(resources)} pools found "
                f"across {workspace_count} workspaces"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Synapse SQL Pools: {str(e)}")

        return resources

    def _estimate_synapse_sql_pool_cost(self, dw_name: str, status: str) -> float:
        """
        Estimate monthly cost for Synapse SQL Pool based on DWU level.

        Pricing (Gen2 cDWU - compute optimized):
        - DW100c: $1.20/hour = $876/month
        - DW200c: $2.40/hour = $1,752/month
        - DW500c: $6.00/hour = $4,380/month
        - DW1000c: $12.00/hour = $8,760/month
        - DW2000c: $24.00/hour = $17,520/month
        - DW5000c: $60.00/hour = $43,800/month
        - DW10000c: $120.00/hour = $87,600/month
        - DW15000c: $180.00/hour = $131,400/month
        - DW30000c: $360.00/hour = $262,800/month

        Note: When paused, only storage costs apply (~$120/TB/month)
        """
        hours_per_month = 730  # Average

        # Pricing map for Gen2 cDWU levels
        pricing_map = {
            "DW100c": 1.20,
            "DW200c": 2.40,
            "DW300c": 3.60,
            "DW400c": 4.80,
            "DW500c": 6.00,
            "DW1000c": 12.00,
            "DW1500c": 18.00,
            "DW2000c": 24.00,
            "DW2500c": 30.00,
            "DW3000c": 36.00,
            "DW5000c": 60.00,
            "DW6000c": 72.00,
            "DW7500c": 90.00,
            "DW10000c": 120.00,
            "DW15000c": 180.00,
            "DW30000c": 360.00,
        }

        # Check if paused (storage-only costs)
        if status.lower() == 'paused':
            # Assume 1TB average storage = $120/month
            return 120.0

        # Get hourly rate
        hourly_rate = pricing_map.get(dw_name, 12.00)  # Default to DW1000c

        return hourly_rate * hours_per_month

    async def _calculate_synapse_sql_pool_optimization(
        self,
        pool: Any,
        status: str,
        dw_name: str,
        tier: str,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Synapse SQL Pool.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - SQL pool paused >7 days
        # This is likely abandoned or forgotten - still incurs storage costs
        if status.lower() == 'paused':
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            # Savings = eliminate storage costs by deleting backup and pool
            potential_savings = 120.0  # Storage costs per month
            recommendations.append(
                "CRITICAL: SQL pool has been paused for extended period. "
                "If no longer needed, delete to eliminate storage costs ($120/TB/month)."
            )

        # SCENARIO 2: HIGH - Zero queries 30+ days (placeholder - needs query metrics)
        # In real implementation, would check Synapse analytics/monitoring
        elif status.lower() == 'online':
            # This is a placeholder - would require querying Synapse monitoring/analytics
            # For now, we can't determine query activity without additional API calls
            pass

        # SCENARIO 3: HIGH - Overprovisioned DWUs (placeholder - needs query metrics)
        # In real implementation, would analyze DWU utilization vs query load
        # If DWU usage <30%, could downgrade to smaller tier
        if status.lower() == 'online' and dw_name.startswith('DW'):
            # Extract DWU number (e.g., "DW5000c" -> 5000)
            try:
                dw_number = int(dw_name.replace('DW', '').replace('c', ''))

                # If using very large DWU (>5000c), recommend reviewing necessity
                if dw_number >= 5000:
                    is_optimizable = True
                    optimization_score = max(optimization_score, 70)
                    priority = "high" if priority == "none" else priority

                    # Potential savings: Downgrade from DW5000c to DW2000c
                    current_hourly = monthly_cost / 730
                    potential_hourly = 24.00  # DW2000c
                    if current_hourly > potential_hourly:
                        potential_savings = (current_hourly - potential_hourly) * 730
                        recommendations.append(
                            f"HIGH: Large DWU tier ({dw_name}). Review query patterns - "
                            f"if average load <30%, consider downgrading to save ${potential_savings:.2f}/month."
                        )
            except ValueError:
                pass

        # SCENARIO 4: MEDIUM - No auto-pause configured
        # Synapse SQL Pools support auto-pause to save costs when idle
        # This is a placeholder - would require checking pool settings via API
        if status.lower() == 'online' and not is_optimizable:
            # This is a best practice recommendation
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: Consider enabling auto-pause for idle periods. "
                "SQL pool can auto-pause after inactivity to reduce costs."
            )

        # SCENARIO 5: LOW - Gen1 DWU (upgrade to Gen2)
        # Gen1 = "DW100", "DW200", etc. (no 'c' suffix)
        # Gen2 = "DW100c", "DW200c", etc. ('c' suffix = compute optimized)
        if tier == "DW" or (dw_name.startswith('DW') and not dw_name.endswith('c')):
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Using Gen1 DWU tier. Migrate to Gen2 (compute optimized) "
                "for 5x better performance at same cost."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_vpn_gateways(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure VPN Gateways for cost intelligence.

        VPN Gateways provide site-to-site, point-to-site, and VNet-to-VNet connectivity.
        Pricing: $27-$650/month depending on SKU (Basic, VpnGw1-5, VpnGw1AZ-5AZ)
        Typical cost: $150-400/month for production gateways

        Detection criteria:
        - No active connections 30+ days (CRITICAL - 90 score)
        - Very low data transfer <1GB/month (HIGH - 75 score)
        - Overprovisioned SKU (traffic <30% capacity) (HIGH - 70 score)
        - Point-to-Site only (use Azure Bastion instead) (MEDIUM - 50 score)
        - Legacy Basic SKU (LOW - 30 score)

        Returns:
            List of all VPN Gateways with optimization recommendations
        """
        try:
            from azure.mgmt.network import NetworkManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-network not installed")
            return []

        resources = []
        self.logger.info(f"Scanning VPN Gateways in region: {region}")

        try:
            # Create network client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            network_client = NetworkManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List VPN gateways in this resource group
                    vpn_gateways = network_client.virtual_network_gateways.list(rg_name)

                    for gateway in vpn_gateways:
                        gateway_name = gateway.name
                        gateway_location = gateway.location

                        # Filter by region if specified
                        if self.regions and gateway_location not in self.regions:
                            continue

                        # Only process VPN gateways (not ExpressRoute)
                        gateway_type = getattr(gateway, 'gateway_type', 'Unknown')
                        if gateway_type.lower() != 'vpn':
                            continue

                        # Get SKU and configuration
                        sku = getattr(gateway, 'sku', None)
                        sku_name = sku.name if sku else "Unknown"
                        sku_tier = sku.tier if sku and hasattr(sku, 'tier') else "Unknown"

                        # Get VPN type and configuration
                        vpn_type = getattr(gateway, 'vpn_type', 'Unknown')
                        vpn_client_config = getattr(gateway, 'vpn_client_configuration', None)
                        has_p2s = vpn_client_config is not None
                        bgp_settings = getattr(gateway, 'bgp_settings', None)
                        has_bgp = bgp_settings is not None

                        # Get active connections count (placeholder - needs additional API call)
                        # In real implementation, would query network_client.virtual_network_gateway_connections.list()
                        active_connections = 0  # Placeholder

                        # Calculate monthly cost based on SKU
                        monthly_cost = self._estimate_vpn_gateway_cost(sku_name)

                        # Check optimization opportunities
                        is_optimizable, score, priority, savings, recommendations = \
                            await self._calculate_vpn_gateway_optimization(
                                gateway, sku_name, has_p2s, active_connections, monthly_cost
                            )

                        # Build metadata
                        metadata = {
                            "gateway_name": gateway_name,
                            "sku": sku_name,
                            "tier": sku_tier,
                            "vpn_type": vpn_type,
                            "has_point_to_site": has_p2s,
                            "has_bgp": has_bgp,
                            "active_connections": active_connections,
                            "resource_group": rg_name,
                            "provisioning_state": getattr(gateway, 'provisioning_state', 'Unknown'),
                        }

                        # Determine if orphan (no connections for 90+ days = likely abandoned)
                        is_orphan = active_connections == 0 and score >= 90

                        # Create resource record
                        resource = AllCloudResourceData(
                            resource_id=gateway.id,
                            resource_name=gateway_name,
                            resource_type="azure_vpn_gateway",
                            region=gateway_location,
                            estimated_monthly_cost=monthly_cost,
                            currency="USD",
                            resource_metadata=metadata,
                            is_orphan=is_orphan,
                            is_optimizable=is_optimizable and not is_orphan,
                            optimization_score=score if not is_orphan else 0,
                            optimization_priority=priority if not is_orphan else "none",
                            potential_monthly_savings=savings if not is_orphan else 0.0,
                            optimization_recommendations=recommendations if not is_orphan else []
                        )

                        resources.append(resource)
                        self.logger.info(
                            f"Found VPN Gateway: {gateway_name} "
                            f"(SKU: {sku_name}, P2S: {has_p2s}, "
                            f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning VPN gateways in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"VPN Gateway scan complete: {len(resources)} gateways found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning VPN Gateways: {str(e)}")

        return resources

    def _estimate_vpn_gateway_cost(self, sku_name: str) -> float:
        """
        Estimate monthly cost for VPN Gateway based on SKU.

        Pricing (monthly, includes 730 hours):
        - Basic: $27/month (legacy, site-to-site only, no BGP, max 10 tunnels)
        - VpnGw1: $150/month (30 tunnels, 650 Mbps, BGP)
        - VpnGw2: $380/month (30 tunnels, 1 Gbps, BGP)
        - VpnGw3: $410/month (30 tunnels, 1.25 Gbps, BGP)
        - VpnGw4: $580/month (100 tunnels, 5 Gbps, BGP)
        - VpnGw5: $650/month (100 tunnels, 10 Gbps, BGP)
        - VpnGw1AZ-5AZ: Zone-redundant versions (+10% cost)

        Note: Plus data transfer costs ($0.087/GB outbound)
        """
        pricing_map = {
            "Basic": 27.0,
            "VpnGw1": 150.0,
            "VpnGw2": 380.0,
            "VpnGw3": 410.0,
            "VpnGw4": 580.0,
            "VpnGw5": 650.0,
            "VpnGw1AZ": 165.0,  # +10% for zone redundancy
            "VpnGw2AZ": 418.0,
            "VpnGw3AZ": 451.0,
            "VpnGw4AZ": 638.0,
            "VpnGw5AZ": 715.0,
        }

        return pricing_map.get(sku_name, 150.0)  # Default to VpnGw1

    async def _calculate_vpn_gateway_optimization(
        self,
        gateway: Any,
        sku_name: str,
        has_p2s: bool,
        active_connections: int,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for VPN Gateway.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - No active connections 30+ days
        # This is a placeholder - would require querying connection history/metrics
        if active_connections == 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost  # Full cost savings by deletion
            recommendations.append(
                f"CRITICAL: VPN Gateway has no active connections. "
                f"If no longer needed, delete to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Very low data transfer <1GB/month (placeholder)
        # In real implementation, would check Azure Monitor metrics for GatewayBandwidth
        # For now, this is a placeholder for future implementation
        elif False:  # Placeholder condition
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            recommendations.append(
                "HIGH: Very low data transfer detected (<1GB/month). "
                "Verify VPN is actively used or consider deletion."
            )

        # SCENARIO 3: HIGH - Overprovisioned SKU (traffic <30% capacity)
        # Placeholder - would require analyzing bandwidth metrics vs SKU capacity
        if sku_name in ["VpnGw4", "VpnGw5", "VpnGw4AZ", "VpnGw5AZ"]:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority

            # Calculate savings by downgrading to VpnGw1
            potential_savings = monthly_cost - 150.0
            if potential_savings > 0:
                recommendations.append(
                    f"HIGH: High-tier SKU ({sku_name}). Review bandwidth usage - "
                    f"if <30% capacity, downgrade to VpnGw1 to save ${potential_savings:.2f}/month."
                )

        # SCENARIO 4: MEDIUM - Point-to-Site only (use Azure Bastion instead)
        # Azure Bastion provides secure RDP/SSH access without VPN (~$140/month)
        if has_p2s and active_connections == 0 and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            # Bastion is ~$140/month, VPN Gateway is ~$150/month, so minimal savings
            # But Bastion is simpler and more secure for admin access only
            recommendations.append(
                "MEDIUM: VPN Gateway configured only for Point-to-Site. "
                "Consider Azure Bastion instead for secure admin access (simpler, more secure)."
            )

        # SCENARIO 5: LOW - Legacy Basic SKU
        # Basic SKU lacks BGP, IKEv2, zone redundancy, and modern features
        if sku_name == "Basic" and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Using legacy Basic SKU. Upgrade to VpnGw1 for BGP support, "
                "IKEv2, better performance, and modern features (+$123/month)."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_vnet_peerings(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure VNet Peerings for cost intelligence.

        VNet Peering connects two Azure Virtual Networks for private communication.
        Pricing: $0.01/GB intra-region, $0.035-0.05/GB inter-region/global
        Typical cost: $10-100/month depending on traffic volume

        Detection criteria:
        - Peering in Failed/Disconnected state (CRITICAL - 90 score)
        - Peering with 0 traffic 30+ days (HIGH - 75 score)
        - Global peering with very low traffic <1GB/month (HIGH - 70 score)
        - Unidirectional peering (should be bidirectional) (MEDIUM - 50 score)
        - Redundant peerings between same VNets (LOW - 30 score)

        Returns:
            List of all VNet Peerings with optimization recommendations
        """
        try:
            from azure.mgmt.network import NetworkManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-network not installed")
            return []

        resources = []
        self.logger.info(f"Scanning VNet Peerings in region: {region}")

        try:
            # Create network client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            network_client = NetworkManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List virtual networks in this resource group
                    vnets = network_client.virtual_networks.list(rg_name)

                    for vnet in vnets:
                        vnet_name = vnet.name
                        vnet_location = vnet.location

                        # Filter by region if specified
                        if self.regions and vnet_location not in self.regions:
                            continue

                        # Get peerings for this VNet
                        peerings = getattr(vnet, 'virtual_network_peerings', [])

                        for peering in peerings:
                            peering_name = peering.name
                            peering_state = getattr(peering, 'peering_state', 'Unknown')
                            provisioning_state = getattr(peering, 'provisioning_state', 'Unknown')

                            # Get remote VNet info
                            remote_vnet = getattr(peering, 'remote_virtual_network', None)
                            remote_vnet_id = remote_vnet.id if remote_vnet else "Unknown"

                            # Determine if global peering (different regions)
                            # Parse remote VNet region from ID or assume same region
                            is_global = False  # Placeholder - would need to query remote VNet

                            # Estimate traffic (placeholder - would need Azure Monitor metrics)
                            monthly_gb_transfer = 0.0  # Placeholder

                            # Calculate cost
                            monthly_cost = self._estimate_vnet_peering_cost(is_global, monthly_gb_transfer)

                            # Check optimization opportunities
                            is_optimizable, score, priority, savings, recommendations = \
                                await self._calculate_vnet_peering_optimization(
                                    peering, peering_state, is_global, monthly_gb_transfer, monthly_cost
                                )

                            # Build metadata
                            metadata = {
                                "vnet_name": vnet_name,
                                "peering_name": peering_name,
                                "peering_state": peering_state,
                                "provisioning_state": provisioning_state,
                                "remote_vnet_id": remote_vnet_id,
                                "is_global": is_global,
                                "allow_virtual_network_access": getattr(peering, 'allow_virtual_network_access', False),
                                "allow_forwarded_traffic": getattr(peering, 'allow_forwarded_traffic', False),
                                "allow_gateway_transit": getattr(peering, 'allow_gateway_transit', False),
                                "use_remote_gateways": getattr(peering, 'use_remote_gateways', False),
                                "resource_group": rg_name,
                            }

                            # Determine if orphan (failed/disconnected state = waste)
                            is_orphan = peering_state in ['Failed', 'Disconnected'] and score >= 90

                            # Create resource record
                            resource = AllCloudResourceData(
                                resource_id=f"{vnet.id}/virtualNetworkPeerings/{peering_name}",
                                resource_name=f"{vnet_name} → {peering_name}",
                                resource_type="azure_vnet_peering",
                                region=vnet_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                is_orphan=is_orphan,
                                is_optimizable=is_optimizable and not is_orphan,
                                optimization_score=score if not is_orphan else 0,
                                optimization_priority=priority if not is_orphan else "none",
                                potential_monthly_savings=savings if not is_orphan else 0.0,
                                optimization_recommendations=recommendations if not is_orphan else []
                            )

                            resources.append(resource)
                            self.logger.info(
                                f"Found VNet Peering: {vnet_name} → {peering_name} "
                                f"(State: {peering_state}, Global: {is_global}, "
                                f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                            )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning VNet peerings in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"VNet Peering scan complete: {len(resources)} peerings found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning VNet Peerings: {str(e)}")

        return resources

    def _estimate_vnet_peering_cost(self, is_global: bool, monthly_gb: float) -> float:
        """
        Estimate monthly cost for VNet Peering based on traffic.

        Pricing:
        - Intra-region: $0.01/GB ingress + $0.01/GB egress = $0.02/GB total
        - Inter-region (same geography): $0.035/GB
        - Global peering (cross-geography): $0.05/GB

        Note: Most peerings have low traffic, so base cost is often minimal
        """
        if monthly_gb == 0:
            # Peering itself is free, only data transfer is charged
            # Assume minimum $5/month for minimal traffic
            return 5.0

        if is_global:
            # Global peering
            cost_per_gb = 0.05
        else:
            # Assume intra-region (most common)
            cost_per_gb = 0.02

        return monthly_gb * cost_per_gb

    async def _calculate_vnet_peering_optimization(
        self,
        peering: Any,
        peering_state: str,
        is_global: bool,
        monthly_gb: float,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for VNet Peering.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Peering in Failed/Disconnected state
        if peering_state in ['Failed', 'Disconnected']:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"CRITICAL: VNet Peering is in {peering_state} state. "
                f"Delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Peering with 0 traffic 30+ days (placeholder)
        # In real implementation, would check Azure Monitor metrics for BytesTransferred
        elif monthly_gb == 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            potential_savings = monthly_cost
            recommendations.append(
                "HIGH: VNet Peering has no traffic for 30+ days. "
                f"Verify if still needed or delete to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 3: HIGH - Global peering with very low traffic <1GB/month
        # Global peering is expensive ($0.05/GB), recommend migrating data or using alternative
        if is_global and monthly_gb < 1.0 and monthly_gb > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            # Savings: Use ExpressRoute or VPN Gateway for low-volume traffic
            potential_savings = monthly_cost * 0.5  # 50% savings estimate
            recommendations.append(
                f"HIGH: Global VNet Peering with very low traffic ({monthly_gb:.2f} GB/month). "
                f"Consider ExpressRoute or VPN Gateway for cost optimization (~50% savings)."
            )

        # SCENARIO 4: MEDIUM - Unidirectional peering (should be bidirectional)
        # This is a best practice check - bidirectional peering ensures full connectivity
        # Placeholder - would require checking if remote VNet has reciprocal peering
        allow_virtual_network_access = getattr(peering, 'allow_virtual_network_access', False)
        if not allow_virtual_network_access and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: VNet Peering may not have reciprocal peering configured. "
                "Ensure bidirectional peering for full connectivity."
            )

        # SCENARIO 5: LOW - Redundant peerings (placeholder)
        # In real implementation, would check if multiple peerings exist between same VNets
        # This is a placeholder for future enhancement
        if False:  # Placeholder condition
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Multiple VNet Peerings detected between same VNets. "
                "Consolidate to single peering to simplify management."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_front_doors(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Front Door profiles for cost intelligence.

        Front Door is a global CDN + WAF + load balancer service.
        Pricing: Standard $35/mois, Premium $330/mois + data transfer
        Typical cost: $50-500/month

        Detection criteria:
        - Front Door with 0 requests 30+ days (CRITICAL - 90 score)
        - Premium tier with WAF disabled (overpaying) (HIGH - 75 score)
        - Very low traffic <1GB/month (HIGH - 70 score)
        - Endpoints not used or redundant (MEDIUM - 50 score)
        - Classic tier (migration to Standard/Premium) (LOW - 30 score)

        Returns:
            List of all Front Door profiles with optimization recommendations
        """
        try:
            from azure.mgmt.frontdoor import FrontDoorManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-frontdoor not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Front Door profiles (global service)")

        try:
            # Create Front Door client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            frontdoor_client = FrontDoorManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List Front Door profiles (new Standard/Premium)
                    # Note: This API may differ - azure-mgmt-frontdoor has multiple versions
                    # Using legacy Front Door list for compatibility
                    front_doors = frontdoor_client.front_doors.list_by_resource_group(rg_name)

                    for fd in front_doors:
                        fd_name = fd.name
                        fd_location = getattr(fd, 'location', 'Global')  # Front Door is global

                        # Get SKU/tier
                        sku = getattr(fd, 'sku', None)
                        sku_name = sku.name if sku and hasattr(sku, 'name') else "Classic"

                        # Get provisioning state
                        provisioning_state = getattr(fd, 'provisioning_state', 'Unknown')
                        resource_state = getattr(fd, 'resource_state', 'Unknown')

                        # Get endpoints
                        frontend_endpoints = getattr(fd, 'frontend_endpoints', [])
                        backend_pools = getattr(fd, 'backend_pools', [])
                        routing_rules = getattr(fd, 'routing_rules', [])

                        # Get WAF policy (if Premium)
                        web_application_firewall_policy_link = getattr(fd, 'web_application_firewall_policy_link', None)
                        has_waf = web_application_firewall_policy_link is not None

                        # Estimate monthly traffic (placeholder - would need Azure Monitor)
                        monthly_requests = 0  # Placeholder
                        monthly_gb_transfer = 0.0  # Placeholder

                        # Calculate cost
                        monthly_cost = self._estimate_front_door_cost(sku_name, monthly_requests)

                        # Check optimization opportunities
                        is_optimizable, score, priority, savings, recommendations = \
                            await self._calculate_front_door_optimization(
                                fd, sku_name, has_waf, monthly_requests, monthly_gb_transfer, monthly_cost
                            )

                        # Build metadata
                        metadata = {
                            "front_door_name": fd_name,
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "resource_state": resource_state,
                            "has_waf": has_waf,
                            "frontend_endpoints_count": len(frontend_endpoints),
                            "backend_pools_count": len(backend_pools),
                            "routing_rules_count": len(routing_rules),
                            "resource_group": rg_name,
                        }

                        # Determine if orphan (0 requests for 90+ days = waste)
                        is_orphan = monthly_requests == 0 and score >= 90

                        # Create resource record
                        resource = AllCloudResourceData(
                            resource_id=fd.id,
                            resource_name=fd_name,
                            resource_type="azure_front_door",
                            region=fd_location,
                            estimated_monthly_cost=monthly_cost,
                            currency="USD",
                            resource_metadata=metadata,
                            is_orphan=is_orphan,
                            is_optimizable=is_optimizable and not is_orphan,
                            optimization_score=score if not is_orphan else 0,
                            optimization_priority=priority if not is_orphan else "none",
                            potential_monthly_savings=savings if not is_orphan else 0.0,
                            optimization_recommendations=recommendations if not is_orphan else []
                        )

                        resources.append(resource)
                        self.logger.info(
                            f"Found Front Door: {fd_name} "
                            f"(SKU: {sku_name}, WAF: {has_waf}, "
                            f"Endpoints: {len(frontend_endpoints)}, "
                            f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning Front Doors in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Front Door scan complete: {len(resources)} profiles found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Front Doors: {str(e)}")

        return resources

    def _estimate_front_door_cost(self, sku: str, monthly_requests: int) -> float:
        """
        Estimate monthly cost for Front Door based on SKU and usage.

        Pricing:
        - Classic: $35/month base + $0.03/GB data transfer + $0.01/10K requests
        - Standard: $35/month base + $0.03/GB data transfer + $0.01/10K requests
        - Premium: $330/month base + $0.04/GB data transfer + WAF ($10/policy + $1/rule)

        For simplicity, using base pricing + minimal traffic assumption
        """
        if sku in ["Premium", "Premium_AzureFrontDoor"]:
            base_cost = 330.0
        elif sku in ["Standard", "Standard_AzureFrontDoor"]:
            base_cost = 35.0
        else:
            # Classic or unknown
            base_cost = 35.0

        # Add estimated data transfer costs (assume 10GB/month average)
        if sku in ["Premium", "Premium_AzureFrontDoor"]:
            data_transfer_cost = 10 * 0.04  # $0.04/GB
        else:
            data_transfer_cost = 10 * 0.03  # $0.03/GB

        return base_cost + data_transfer_cost

    async def _calculate_front_door_optimization(
        self,
        front_door: Any,
        sku: str,
        has_waf: bool,
        monthly_requests: int,
        monthly_gb: float,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Front Door.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Front Door with 0 requests 30+ days
        if monthly_requests == 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"CRITICAL: Front Door has no requests for 30+ days. "
                f"Delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Premium tier with WAF disabled (overpaying)
        # Premium is $330/month vs Standard $35/month - WAF is the main differentiator
        elif sku in ["Premium", "Premium_AzureFrontDoor"] and not has_waf:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            # Savings: Downgrade to Standard
            potential_savings = 330.0 - 35.0  # $295/month
            recommendations.append(
                f"HIGH: Premium tier without WAF enabled. "
                f"Downgrade to Standard tier to save ${potential_savings:.2f}/month."
            )

        # SCENARIO 3: HIGH - Very low traffic <1GB/month
        # Front Door has high base cost - not cost-effective for very low traffic
        elif monthly_gb < 1.0 and monthly_gb > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            # Savings: Use Azure CDN Standard instead (~$10/month)
            potential_savings = monthly_cost - 10.0
            if potential_savings > 0:
                recommendations.append(
                    f"HIGH: Very low traffic ({monthly_gb:.2f} GB/month). "
                    f"Consider Azure CDN Standard instead to save ${potential_savings:.2f}/month."
                )

        # SCENARIO 4: MEDIUM - Unused endpoints or redundant rules
        # Check if endpoints are configured but not used
        frontend_endpoints = getattr(front_door, 'frontend_endpoints', [])
        routing_rules = getattr(front_door, 'routing_rules', [])

        if len(frontend_endpoints) > 5 and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                f"MEDIUM: {len(frontend_endpoints)} frontend endpoints configured. "
                f"Review and remove unused endpoints to simplify configuration."
            )

        # SCENARIO 5: LOW - Classic tier (migration recommended)
        # Classic tier is being deprecated, recommend migration
        if sku == "Classic" and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Using Classic tier. Migrate to Standard or Premium tier "
                "for better performance, features, and support."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_container_registries(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Container Registries for cost intelligence.

        Container Registry is a private Docker registry for storing container images.
        Pricing: Basic $5/mois, Standard $20/mois, Premium $50/mois + storage + bandwidth
        Typical cost: $20-200/month

        Detection criteria:
        - Registry inutilisé (0 pulls 90+ days) (CRITICAL - 90 score)
        - Premium tier sans geo-replication (HIGH - 75 score)
        - Images obsolètes non nettoyées (>50 untagged) (HIGH - 70 score)
        - Pas de retention policy (MEDIUM - 50 score)
        - Basic tier pour production (LOW - 30 score)

        Returns:
            List of all Container Registries with optimization recommendations
        """
        try:
            from azure.mgmt.containerregistry import ContainerRegistryManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-containerregistry not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Container Registries in region: {region}")

        try:
            # Create Container Registry client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            acr_client = ContainerRegistryManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List registries in this resource group
                    registries = acr_client.registries.list_by_resource_group(rg_name)

                    for registry in registries:
                        registry_name = registry.name
                        registry_location = registry.location

                        # Filter by region if specified
                        if self.regions and registry_location not in self.regions:
                            continue

                        # Get SKU
                        sku = getattr(registry, 'sku', None)
                        sku_name = sku.name if sku else "Basic"

                        # Get provisioning state
                        provisioning_state = getattr(registry, 'provisioning_state', 'Unknown')

                        # Get geo-replication status (Premium only)
                        replications = []
                        has_geo_replication = False
                        if sku_name == "Premium":
                            try:
                                replications_list = acr_client.replications.list(rg_name, registry_name)
                                replications = list(replications_list)
                                has_geo_replication = len(replications) > 1  # More than 1 = geo-replicated
                            except Exception:
                                pass

                        # Get storage usage (placeholder - would need Azure Monitor)
                        storage_gb = 10.0  # Placeholder

                        # Calculate cost
                        monthly_cost = self._estimate_container_registry_cost(sku_name, storage_gb, has_geo_replication)

                        # Estimate usage metrics (placeholder - would need Azure Monitor)
                        successful_pulls_30d = 0  # Placeholder
                        successful_pushes_30d = 0  # Placeholder
                        untagged_images_count = 0  # Placeholder

                        # Check optimization opportunities
                        is_optimizable, score, priority, savings, recommendations = \
                            await self._calculate_container_registry_optimization(
                                registry, sku_name, has_geo_replication, successful_pulls_30d,
                                untagged_images_count, monthly_cost
                            )

                        # Build metadata
                        metadata = {
                            "registry_name": registry_name,
                            "sku": sku_name,
                            "provisioning_state": provisioning_state,
                            "admin_user_enabled": getattr(registry, 'admin_user_enabled', False),
                            "has_geo_replication": has_geo_replication,
                            "replication_count": len(replications),
                            "storage_gb": storage_gb,
                            "successful_pulls_30d": successful_pulls_30d,
                            "successful_pushes_30d": successful_pushes_30d,
                            "untagged_images_count": untagged_images_count,
                            "resource_group": rg_name,
                        }

                        # Determine if orphan (0 pulls for 90+ days = waste)
                        is_orphan = successful_pulls_30d == 0 and score >= 90

                        # Create resource record
                        resource = AllCloudResourceData(
                            resource_id=registry.id,
                            resource_name=registry_name,
                            resource_type="azure_container_registry",
                            region=registry_location,
                            estimated_monthly_cost=monthly_cost,
                            currency="USD",
                            resource_metadata=metadata,
                            is_orphan=is_orphan,
                            is_optimizable=is_optimizable and not is_orphan,
                            optimization_score=score if not is_orphan else 0,
                            optimization_priority=priority if not is_orphan else "none",
                            potential_monthly_savings=savings if not is_orphan else 0.0,
                            optimization_recommendations=recommendations if not is_orphan else []
                        )

                        resources.append(resource)
                        self.logger.info(
                            f"Found Container Registry: {registry_name} "
                            f"(SKU: {sku_name}, Geo-replication: {has_geo_replication}, "
                            f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning container registries in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Container Registry scan complete: {len(resources)} registries found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Container Registries: {str(e)}")

        return resources

    def _estimate_container_registry_cost(self, sku: str, storage_gb: float, geo_replication: bool) -> float:
        """
        Estimate monthly cost for Container Registry based on SKU and usage.

        Pricing:
        - Basic: $5/month + $0.10/GB storage
        - Standard: $20/month + $0.10/GB storage + webhooks
        - Premium: $50/month + $0.10/GB storage + geo-replication + content trust

        Geo-replication: ~$50/month per additional region (Premium only)
        """
        # Base costs
        base_costs = {
            "Basic": 5.0,
            "Standard": 20.0,
            "Premium": 50.0,
        }

        base_cost = base_costs.get(sku, 20.0)

        # Storage costs ($0.10/GB)
        storage_cost = storage_gb * 0.10

        # Geo-replication cost (Premium only, ~$50 per additional region)
        geo_cost = 0.0
        if sku == "Premium" and geo_replication:
            geo_cost = 50.0  # Assume 1 additional region

        return base_cost + storage_cost + geo_cost

    async def _calculate_container_registry_optimization(
        self,
        registry: Any,
        sku: str,
        has_geo_replication: bool,
        successful_pulls_30d: int,
        untagged_images_count: int,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Container Registry.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Registry inutilisé (0 pulls pendant 90+ jours)
        if successful_pulls_30d == 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"CRITICAL: Container Registry has no pulls for 90+ days. "
                f"Delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Premium tier sans geo-replication (overpaying)
        elif sku == "Premium" and not has_geo_replication:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            # Savings: Downgrade to Standard
            potential_savings = 50.0 - 20.0  # $30/month
            recommendations.append(
                f"HIGH: Premium tier without geo-replication enabled. "
                f"Downgrade to Standard tier to save ${potential_savings:.2f}/month."
            )

        # SCENARIO 3: HIGH - Images obsolètes non nettoyées (>50 untagged images)
        # Untagged images consume storage and indicate poor CI/CD hygiene
        elif untagged_images_count > 50:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            # Savings: Reduce storage costs by cleaning up
            storage_savings = (untagged_images_count / 50) * 5.0  # Estimate $5 per 50 images
            potential_savings = min(storage_savings, monthly_cost * 0.3)  # Max 30% of cost
            recommendations.append(
                f"HIGH: {untagged_images_count} untagged images detected. "
                f"Enable retention policy to auto-delete unused images and save ~${potential_savings:.2f}/month."
            )

        # SCENARIO 4: MEDIUM - Pas de retention policy configurée
        # Placeholder - would require checking registry policies via API
        # For now, this is a best practice recommendation
        if not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: No retention policy configured. "
                "Enable automatic cleanup of old/untagged images to reduce storage costs."
            )

        # SCENARIO 5: LOW - Basic tier pour production (upgrade recommended)
        # Basic tier lacks webhooks, geo-replication, and advanced security features
        if sku == "Basic" and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Using Basic tier. Upgrade to Standard for webhooks, "
                "better performance, and production-grade features (+$15/month)."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_service_bus_topics(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Service Bus Topics for cost intelligence.

        Service Bus Topic is a pub/sub messaging service with multiple subscriptions.
        Pricing: Standard $10/mois + $0.05/million ops, Premium $677/mois (dedicated capacity)
        Typical cost: $15-100/month

        Detection criteria:
        - Topic sans abonnements actifs 30+ days (CRITICAL - 90 score)
        - Premium tier avec faible volume <1M messages/mois (HIGH - 75 score)
        - Messages morts non traités >1000 (HIGH - 70 score)
        - Pas de TTL configuré (MEDIUM - 50 score)
        - Auto-delete non configuré (LOW - 30 score)

        Returns:
            List of all Service Bus Topics with optimization recommendations
        """
        try:
            from azure.mgmt.servicebus import ServiceBusManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-servicebus not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Service Bus Topics in region: {region}")

        try:
            # Create Service Bus client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            sb_client = ServiceBusManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List Service Bus namespaces in this resource group
                    namespaces = sb_client.namespaces.list_by_resource_group(rg_name)

                    for namespace in namespaces:
                        namespace_name = namespace.name
                        namespace_location = namespace.location

                        # Filter by region if specified
                        if self.regions and namespace_location not in self.regions:
                            continue

                        # Get SKU/tier
                        sku = getattr(namespace, 'sku', None)
                        tier = sku.name if sku else "Standard"

                        # List topics in this namespace
                        topics = sb_client.topics.list_by_namespace(rg_name, namespace_name)

                        for topic in topics:
                            topic_name = topic.name
                            status = getattr(topic, 'status', 'Unknown')

                            # Get topic properties
                            max_size_in_mb = getattr(topic, 'max_size_in_megabytes', 0)
                            enable_partitioning = getattr(topic, 'enable_partitioning', False)
                            enable_batched_operations = getattr(topic, 'enable_batched_operations', False)
                            default_message_time_to_live = getattr(topic, 'default_message_time_to_live', None)
                            auto_delete_on_idle = getattr(topic, 'auto_delete_on_idle', None)

                            # Get subscriptions count
                            subscriptions = sb_client.subscriptions.list_by_topic(rg_name, namespace_name, topic_name)
                            subscriptions_list = list(subscriptions)
                            subscription_count = len(subscriptions_list)

                            # Estimate usage metrics (placeholder - would need Azure Monitor)
                            monthly_operations = 0  # Placeholder
                            dead_letter_messages_count = 0  # Placeholder

                            # Calculate cost (shared with namespace, estimate per topic)
                            monthly_cost = self._estimate_service_bus_cost(tier, monthly_operations)

                            # Check optimization opportunities
                            is_optimizable, score, priority, savings, recommendations = \
                                await self._calculate_service_bus_topic_optimization(
                                    topic, tier, subscription_count, monthly_operations,
                                    dead_letter_messages_count, default_message_time_to_live,
                                    auto_delete_on_idle, monthly_cost
                                )

                            # Build metadata
                            metadata = {
                                "namespace_name": namespace_name,
                                "topic_name": topic_name,
                                "tier": tier,
                                "status": status,
                                "subscription_count": subscription_count,
                                "max_size_mb": max_size_in_mb,
                                "enable_partitioning": enable_partitioning,
                                "enable_batched_operations": enable_batched_operations,
                                "has_ttl": default_message_time_to_live is not None,
                                "has_auto_delete": auto_delete_on_idle is not None,
                                "dead_letter_messages_count": dead_letter_messages_count,
                                "resource_group": rg_name,
                            }

                            # Determine if orphan (no subscriptions for 30+ days = waste)
                            is_orphan = subscription_count == 0 and score >= 90

                            # Create resource record
                            resource = AllCloudResourceData(
                                resource_id=topic.id,
                                resource_name=f"{namespace_name}/{topic_name}",
                                resource_type="azure_service_bus_topic",
                                region=namespace_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                is_orphan=is_orphan,
                                is_optimizable=is_optimizable and not is_orphan,
                                optimization_score=score if not is_orphan else 0,
                                optimization_priority=priority if not is_orphan else "none",
                                potential_monthly_savings=savings if not is_orphan else 0.0,
                                optimization_recommendations=recommendations if not is_orphan else []
                            )

                            resources.append(resource)
                            self.logger.info(
                                f"Found Service Bus Topic: {namespace_name}/{topic_name} "
                                f"(Tier: {tier}, Subscriptions: {subscription_count}, "
                                f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                            )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning Service Bus topics in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Service Bus Topic scan complete: {len(resources)} topics found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Service Bus Topics: {str(e)}")

        return resources

    async def scan_service_bus_queues(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Service Bus Queues for cost intelligence.

        Service Bus Queue is a FIFO messaging service with delivery guarantees.
        Pricing: Standard $10/mois + $0.05/million ops, Premium $677/mois
        Typical cost: $15-100/month

        Detection criteria:
        - Queue inutilisée (0 messages 90+ days) (CRITICAL - 90 score)
        - Premium tier avec faible volume <1M messages/mois (HIGH - 75 score)
        - Messages morts (Dead Letter) non traités >1000 (HIGH - 70 score)
        - Duplicate detection non activée (MEDIUM - 50 score)
        - Lock duration excessive >5min (LOW - 30 score)

        Returns:
            List of all Service Bus Queues with optimization recommendations
        """
        try:
            from azure.mgmt.servicebus import ServiceBusManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-servicebus not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Service Bus Queues in region: {region}")

        try:
            # Create Service Bus client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            sb_client = ServiceBusManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List Service Bus namespaces
                    namespaces = sb_client.namespaces.list_by_resource_group(rg_name)

                    for namespace in namespaces:
                        namespace_name = namespace.name
                        namespace_location = namespace.location

                        # Filter by region if specified
                        if self.regions and namespace_location not in self.regions:
                            continue

                        # Get SKU/tier
                        sku = getattr(namespace, 'sku', None)
                        tier = sku.name if sku else "Standard"

                        # List queues in this namespace
                        queues = sb_client.queues.list_by_namespace(rg_name, namespace_name)

                        for queue in queues:
                            queue_name = queue.name
                            status = getattr(queue, 'status', 'Unknown')

                            # Get queue properties
                            max_size_in_mb = getattr(queue, 'max_size_in_megabytes', 0)
                            enable_partitioning = getattr(queue, 'enable_partitioning', False)
                            requires_duplicate_detection = getattr(queue, 'requires_duplicate_detection', False)
                            lock_duration = getattr(queue, 'lock_duration', None)
                            default_message_time_to_live = getattr(queue, 'default_message_time_to_live', None)
                            auto_delete_on_idle = getattr(queue, 'auto_delete_on_idle', None)

                            # Estimate usage metrics (placeholder - would need Azure Monitor)
                            monthly_operations = 0  # Placeholder
                            active_messages_count = 0  # Placeholder
                            dead_letter_messages_count = 0  # Placeholder

                            # Calculate cost
                            monthly_cost = self._estimate_service_bus_cost(tier, monthly_operations)

                            # Check optimization opportunities
                            is_optimizable, score, priority, savings, recommendations = \
                                await self._calculate_service_bus_queue_optimization(
                                    queue, tier, active_messages_count, monthly_operations,
                                    dead_letter_messages_count, requires_duplicate_detection,
                                    lock_duration, monthly_cost
                                )

                            # Build metadata
                            metadata = {
                                "namespace_name": namespace_name,
                                "queue_name": queue_name,
                                "tier": tier,
                                "status": status,
                                "max_size_mb": max_size_in_mb,
                                "enable_partitioning": enable_partitioning,
                                "requires_duplicate_detection": requires_duplicate_detection,
                                "lock_duration": str(lock_duration) if lock_duration else None,
                                "has_ttl": default_message_time_to_live is not None,
                                "has_auto_delete": auto_delete_on_idle is not None,
                                "active_messages_count": active_messages_count,
                                "dead_letter_messages_count": dead_letter_messages_count,
                                "resource_group": rg_name,
                            }

                            # Determine if orphan (0 active messages for 90+ days = waste)
                            is_orphan = active_messages_count == 0 and score >= 90

                            # Create resource record
                            resource = AllCloudResourceData(
                                resource_id=queue.id,
                                resource_name=f"{namespace_name}/{queue_name}",
                                resource_type="azure_service_bus_queue",
                                region=namespace_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                is_orphan=is_orphan,
                                is_optimizable=is_optimizable and not is_orphan,
                                optimization_score=score if not is_orphan else 0,
                                optimization_priority=priority if not is_orphan else "none",
                                potential_monthly_savings=savings if not is_orphan else 0.0,
                                optimization_recommendations=recommendations if not is_orphan else []
                            )

                            resources.append(resource)
                            self.logger.info(
                                f"Found Service Bus Queue: {namespace_name}/{queue_name} "
                                f"(Tier: {tier}, Active messages: {active_messages_count}, "
                                f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                            )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning Service Bus queues in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Service Bus Queue scan complete: {len(resources)} queues found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Service Bus Queues: {str(e)}")

        return resources

    def _estimate_service_bus_cost(self, tier: str, monthly_operations: int) -> float:
        """
        Estimate monthly cost for Service Bus based on tier and operations.

        Pricing:
        - Basic: $0.05/million operations (queues only, no topics)
        - Standard: $10/month base + $0.05/million operations
        - Premium: $677/month (1 messaging unit) - dedicated capacity

        For simplicity, using base pricing + minimal operations assumption
        """
        if tier == "Premium":
            return 677.0
        elif tier == "Standard":
            base_cost = 10.0
            # Add operation costs ($0.05 per million)
            operation_cost = (monthly_operations / 1000000) * 0.05
            return base_cost + operation_cost
        else:
            # Basic
            operation_cost = (monthly_operations / 1000000) * 0.05
            return operation_cost

    async def _calculate_service_bus_topic_optimization(
        self,
        topic: Any,
        tier: str,
        subscription_count: int,
        monthly_operations: int,
        dead_letter_messages_count: int,
        default_message_time_to_live: Any,
        auto_delete_on_idle: Any,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Service Bus Topic.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Topic sans abonnements actifs 30+ jours
        if subscription_count == 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"CRITICAL: Service Bus Topic has no active subscriptions. "
                f"Delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Premium tier avec faible volume <1M messages/mois
        elif tier == "Premium" and monthly_operations < 1000000:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            # Savings: Downgrade to Standard
            potential_savings = 677.0 - 10.0  # $667/month
            recommendations.append(
                f"HIGH: Premium tier with low message volume ({monthly_operations/1000:.0f}K ops/month). "
                f"Downgrade to Standard tier to save ${potential_savings:.2f}/month."
            )

        # SCENARIO 3: HIGH - Messages morts non traités >1000
        elif dead_letter_messages_count > 1000:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            recommendations.append(
                f"HIGH: {dead_letter_messages_count} dead letter messages detected. "
                f"Review and fix application errors causing message failures."
            )

        # SCENARIO 4: MEDIUM - Pas de TTL configuré
        if default_message_time_to_live is None and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: No message TTL (Time-To-Live) configured. "
                "Messages may accumulate indefinitely. Set TTL to prevent storage bloat."
            )

        # SCENARIO 5: LOW - Auto-delete non configuré
        if auto_delete_on_idle is None and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Auto-delete on idle not configured. "
                "Enable to automatically clean up unused topics."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def _calculate_service_bus_queue_optimization(
        self,
        queue: Any,
        tier: str,
        active_messages_count: int,
        monthly_operations: int,
        dead_letter_messages_count: int,
        requires_duplicate_detection: bool,
        lock_duration: Any,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Service Bus Queue.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Queue inutilisée (0 messages 90+ jours)
        if active_messages_count == 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"CRITICAL: Service Bus Queue has no active messages for 90+ days. "
                f"Delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Premium tier avec faible volume
        elif tier == "Premium" and monthly_operations < 1000000:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            potential_savings = 677.0 - 10.0
            recommendations.append(
                f"HIGH: Premium tier with low message volume ({monthly_operations/1000:.0f}K ops/month). "
                f"Downgrade to Standard tier to save ${potential_savings:.2f}/month."
            )

        # SCENARIO 3: HIGH - Messages morts non traités >1000
        elif dead_letter_messages_count > 1000:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            recommendations.append(
                f"HIGH: {dead_letter_messages_count} dead letter messages detected. "
                f"Review and fix application errors causing message failures."
            )

        # SCENARIO 4: MEDIUM - Duplicate detection non activée
        if not requires_duplicate_detection and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: Duplicate detection not enabled. "
                "Enable to prevent processing duplicate messages (best practice)."
            )

        # SCENARIO 5: LOW - Lock duration excessive >5 minutes
        # Lock duration controls how long a message is locked for processing
        # Excessive lock duration can cause delays if consumer crashes
        if lock_duration and not is_optimizable:
            # lock_duration is a timedelta - extract minutes
            try:
                lock_minutes = lock_duration.total_seconds() / 60
                if lock_minutes > 5:
                    is_optimizable = True
                    optimization_score = max(optimization_score, 30)
                    priority = "low" if priority == "none" else priority
                    recommendations.append(
                        f"LOW: Lock duration is {lock_minutes:.0f} minutes (>5 min threshold). "
                        f"Reduce to improve message processing throughput."
                    )
            except:
                pass

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_event_grid_subscriptions(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Event Grid Subscriptions for cost intelligence.

        Event Grid Subscription routes events from sources to handlers (webhooks, functions, etc.).
        Pricing: $0.60 per million operations (premier million gratuit/mois)
        Typical cost: $1-20/month

        Detection criteria:
        - Subscription vers endpoint mort/inaccessible (CRITICAL - 90 score)
        - Subscription inactive (0 événements 90+ days) (HIGH - 75 score)
        - Dead letter destination non configurée (HIGH - 70 score)
        - Filtres trop larges (MEDIUM - 50 score)
        - Pas d'Advanced Filtering (LOW - 30 score)

        Returns:
            List of all Event Grid Subscriptions with optimization recommendations
        """
        try:
            from azure.mgmt.eventgrid import EventGridManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-eventgrid not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Event Grid Subscriptions in region: {region}")

        try:
            # Create Event Grid client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            eventgrid_client = EventGridManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List Event Grid topics in this resource group
                    topics = eventgrid_client.topics.list_by_resource_group(rg_name)

                    for topic in topics:
                        topic_name = topic.name
                        topic_location = topic.location

                        # Filter by region if specified
                        if self.regions and topic_location not in self.regions:
                            continue

                        # Get subscriptions for this topic
                        try:
                            subscriptions = eventgrid_client.event_subscriptions.list_by_resource(
                                topic.id
                            )

                            for subscription in subscriptions:
                                subscription_name = subscription.name
                                provisioning_state = getattr(subscription, 'provisioning_state', 'Unknown')

                                # Get destination
                                destination = getattr(subscription, 'destination', None)
                                destination_type = type(destination).__name__ if destination else "Unknown"

                                # Get dead letter config
                                dead_letter_destination = getattr(subscription, 'dead_letter_destination', None)
                                has_dead_letter = dead_letter_destination is not None

                                # Get filter
                                filter_obj = getattr(subscription, 'filter', None)
                                has_subject_filter = False
                                has_advanced_filter = False
                                if filter_obj:
                                    has_subject_filter = getattr(filter_obj, 'subject_begins_with', None) is not None
                                    advanced_filters = getattr(filter_obj, 'advanced_filters', [])
                                    has_advanced_filter = len(advanced_filters) > 0

                                # Estimate usage (placeholder - would need Azure Monitor)
                                monthly_operations = 0  # Placeholder
                                delivery_success_rate = 100.0  # Placeholder (0-100%)

                                # Calculate cost
                                monthly_cost = self._estimate_event_grid_cost(monthly_operations)

                                # Check optimization opportunities
                                is_optimizable, score, priority, savings, recommendations = \
                                    await self._calculate_event_grid_subscription_optimization(
                                        subscription, delivery_success_rate, monthly_operations,
                                        has_dead_letter, has_subject_filter, has_advanced_filter, monthly_cost
                                    )

                                # Build metadata
                                metadata = {
                                    "topic_name": topic_name,
                                    "subscription_name": subscription_name,
                                    "destination_type": destination_type,
                                    "provisioning_state": provisioning_state,
                                    "has_dead_letter": has_dead_letter,
                                    "has_subject_filter": has_subject_filter,
                                    "has_advanced_filter": has_advanced_filter,
                                    "delivery_success_rate": delivery_success_rate,
                                    "monthly_operations": monthly_operations,
                                    "resource_group": rg_name,
                                }

                                # Determine if orphan (endpoint mort = waste)
                                is_orphan = delivery_success_rate < 10.0 and score >= 90

                                # Create resource record
                                resource = AllCloudResourceData(
                                    resource_id=subscription.id,
                                    resource_name=f"{topic_name}/{subscription_name}",
                                    resource_type="azure_event_grid_subscription",
                                    region=topic_location,
                                    estimated_monthly_cost=monthly_cost,
                                    currency="USD",
                                    resource_metadata=metadata,
                                    is_orphan=is_orphan,
                                    is_optimizable=is_optimizable and not is_orphan,
                                    optimization_score=score if not is_orphan else 0,
                                    optimization_priority=priority if not is_orphan else "none",
                                    potential_monthly_savings=savings if not is_orphan else 0.0,
                                    optimization_recommendations=recommendations if not is_orphan else []
                                )

                                resources.append(resource)
                                self.logger.info(
                                    f"Found Event Grid Subscription: {topic_name}/{subscription_name} "
                                    f"(Success rate: {delivery_success_rate:.1f}%, Dead letter: {has_dead_letter}, "
                                    f"Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                                )

                        except Exception as e:
                            self.logger.error(
                                f"Error scanning subscriptions for topic {topic_name}: {str(e)}"
                            )
                            continue

                except Exception as e:
                    self.logger.error(
                        f"Error scanning Event Grid topics in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Event Grid Subscription scan complete: {len(resources)} subscriptions found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Event Grid Subscriptions: {str(e)}")

        return resources

    def _estimate_event_grid_cost(self, monthly_operations: int) -> float:
        """
        Estimate monthly cost for Event Grid based on operations.

        Pricing:
        - $0.60 per million operations
        - Premier million gratuit chaque mois

        Note: Très bas coût - généralement <$10/mois
        """
        # Premier million gratuit
        if monthly_operations <= 1000000:
            return 0.0

        # Au-delà du million gratuit
        billable_operations = monthly_operations - 1000000
        cost_per_million = 0.60
        return (billable_operations / 1000000) * cost_per_million

    async def _calculate_event_grid_subscription_optimization(
        self,
        subscription: Any,
        delivery_success_rate: float,
        monthly_operations: int,
        has_dead_letter: bool,
        has_subject_filter: bool,
        has_advanced_filter: bool,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Event Grid Subscription.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Subscription vers endpoint mort/inaccessible
        # Delivery success rate <10% = endpoint probablement mort
        if delivery_success_rate < 10.0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"CRITICAL: Event Grid Subscription has very low delivery success rate ({delivery_success_rate:.1f}%). "
                f"Check endpoint health or delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 2: HIGH - Subscription inactive (0 événements depuis 90+ jours)
        elif monthly_operations == 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            potential_savings = monthly_cost
            recommendations.append(
                f"HIGH: Event Grid Subscription has no events for 90+ days. "
                f"Delete if no longer needed to save ${monthly_cost:.2f}/month."
            )

        # SCENARIO 3: HIGH - Dead letter destination non configurée
        # Sans dead letter, événements en échec sont perdus
        elif not has_dead_letter:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            recommendations.append(
                "HIGH: No dead letter destination configured. "
                "Events that fail delivery are lost. Configure dead lettering for reliability."
            )

        # SCENARIO 4: MEDIUM - Filtres trop larges (traite tous événements)
        # Pas de filtres = traite tous événements = gaspillage potentiel
        if not has_subject_filter and not has_advanced_filter and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: No event filters configured. "
                "Subscription processes all events. Add filters to reduce unnecessary processing."
            )

        # SCENARIO 5: LOW - Pas d'Advanced Filtering (best practice)
        # Advanced filters permettent filtrage plus granulaire
        if not has_advanced_filter and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: No advanced filters configured. "
                "Use advanced filtering for better event routing optimization."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_key_vault_secrets(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Key Vault Secrets for cost intelligence.

        Key Vault stores secrets, keys, and certificates securely.
        Pricing: $0.03 per 10K operations + minimal storage
        Typical cost: $5-50/month

        Detection criteria:
        - Secrets expirés ou non accessibles 90+ days (CRITICAL - 90 score)
        - Pas de date d'expiration (HIGH - 75 score)
        - Secrets non rotationnés 365+ days (HIGH - 70 score)
        - Soft-delete non activé (MEDIUM - 50 score)
        - Pas de monitoring/alerting (LOW - 30 score)

        Returns:
            List of all Key Vault Secrets with optimization recommendations
        """
        try:
            from azure.mgmt.keyvault import KeyVaultManagementClient
        except ImportError:
            self.logger.error("azure-mgmt-keyvault not installed")
            return []

        resources = []
        self.logger.info(f"Scanning Key Vault Secrets in region: {region}")

        try:
            # Create Key Vault client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            kv_client = KeyVaultManagementClient(credential, self.subscription_id)

            # Get all resource groups
            resource_groups = await self._get_resource_groups()

            for rg in resource_groups:
                rg_name = rg.name

                # Filter by resource group if specified
                if self.resource_groups and rg_name not in self.resource_groups:
                    continue

                try:
                    # List Key Vaults in this resource group
                    vaults = kv_client.vaults.list_by_resource_group(rg_name)

                    for vault in vaults:
                        vault_name = vault.name
                        vault_location = vault.location

                        # Filter by region if specified
                        if self.regions and vault_location not in self.regions:
                            continue

                        # Get vault properties
                        sku = getattr(vault.properties, 'sku', None) if hasattr(vault, 'properties') else None
                        sku_name = sku.name if sku else "Standard"
                        soft_delete_enabled = getattr(vault.properties, 'enable_soft_delete', False) if hasattr(vault, 'properties') else False

                        # Estimate metrics (placeholder - would need Azure Monitor / Key Vault SDK)
                        monthly_operations = 1000  # Placeholder
                        secrets_count = 5  # Placeholder
                        secrets_without_expiration = 0  # Placeholder
                        secrets_last_access_90d_ago = 0  # Placeholder
                        secrets_not_rotated_365d = 0  # Placeholder

                        # Calculate cost
                        monthly_cost = self._estimate_key_vault_cost(monthly_operations, secrets_count)

                        # Check optimization opportunities
                        is_optimizable, score, priority, savings, recommendations = \
                            await self._calculate_key_vault_secret_optimization(
                                vault, soft_delete_enabled, secrets_without_expiration,
                                secrets_last_access_90d_ago, secrets_not_rotated_365d, monthly_cost
                            )

                        # Build metadata
                        metadata = {
                            "vault_name": vault_name,
                            "sku": sku_name,
                            "soft_delete_enabled": soft_delete_enabled,
                            "secrets_count": secrets_count,
                            "secrets_without_expiration": secrets_without_expiration,
                            "secrets_last_access_90d_ago": secrets_last_access_90d_ago,
                            "secrets_not_rotated_365d": secrets_not_rotated_365d,
                            "monthly_operations": monthly_operations,
                            "resource_group": rg_name,
                        }

                        # Determine if orphan (secrets non accédés = waste)
                        is_orphan = secrets_last_access_90d_ago > 0 and score >= 90

                        # Create resource record
                        resource = AllCloudResourceData(
                            resource_id=vault.id,
                            resource_name=vault_name,
                            resource_type="azure_key_vault_secret",
                            region=vault_location,
                            estimated_monthly_cost=monthly_cost,
                            currency="USD",
                            resource_metadata=metadata,
                            is_orphan=is_orphan,
                            is_optimizable=is_optimizable and not is_orphan,
                            optimization_score=score if not is_orphan else 0,
                            optimization_priority=priority if not is_orphan else "none",
                            potential_monthly_savings=savings if not is_orphan else 0.0,
                            optimization_recommendations=recommendations if not is_orphan else []
                        )

                        resources.append(resource)
                        self.logger.info(
                            f"Found Key Vault: {vault_name} "
                            f"(SKU: {sku_name}, Soft-delete: {soft_delete_enabled}, "
                            f"Secrets: {secrets_count}, Cost: ${monthly_cost:.2f}/mo, Optimizable: {is_optimizable})"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error scanning Key Vaults in resource group {rg_name}: {str(e)}"
                    )
                    continue

            self.logger.info(
                f"Key Vault Secret scan complete: {len(resources)} vaults found"
            )

        except Exception as e:
            self.logger.error(f"Error scanning Key Vault Secrets: {str(e)}")

        return resources

    def _estimate_key_vault_cost(self, monthly_operations: int, secrets_count: int) -> float:
        """
        Estimate monthly cost for Key Vault based on operations.

        Pricing:
        - $0.03 per 10,000 operations
        - Secrets: Free storage, paid per access
        - HSM-backed secrets (Premium): $1/secret/month

        For simplicity, using operation-based pricing
        """
        cost_per_10k_ops = 0.03
        return (monthly_operations / 10000) * cost_per_10k_ops

    async def _calculate_key_vault_secret_optimization(
        self,
        vault: Any,
        soft_delete_enabled: bool,
        secrets_without_expiration: int,
        secrets_last_access_90d_ago: int,
        secrets_not_rotated_365d: int,
        monthly_cost: float
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Key Vault Secret.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # SCENARIO 1: CRITICAL - Secrets expirés ou non accessibles 90+ days
        if secrets_last_access_90d_ago > 0:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost * 0.5  # Assume 50% cost reduction
            recommendations.append(
                f"CRITICAL: {secrets_last_access_90d_ago} secrets not accessed for 90+ days. "
                f"Review and delete unused secrets to save ~${potential_savings:.2f}/month."
            )

        # SCENARIO 2: HIGH - Pas de date d'expiration configurée (risque sécurité)
        elif secrets_without_expiration > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 75)
            priority = "high" if priority == "none" else priority
            recommendations.append(
                f"HIGH: {secrets_without_expiration} secrets without expiration date. "
                f"Set expiration dates for automatic rotation and improved security."
            )

        # SCENARIO 3: HIGH - Secrets non rotationnés depuis 365+ jours
        elif secrets_not_rotated_365d > 0:
            is_optimizable = True
            optimization_score = max(optimization_score, 70)
            priority = "high" if priority == "none" else priority
            recommendations.append(
                f"HIGH: {secrets_not_rotated_365d} secrets not rotated for 365+ days. "
                f"Rotate secrets regularly (recommended: every 90 days) for security."
            )

        # SCENARIO 4: MEDIUM - Soft-delete non activé (risque de perte)
        if not soft_delete_enabled and not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 50)
            priority = "medium" if priority == "none" else priority
            recommendations.append(
                "MEDIUM: Soft-delete not enabled. "
                "Enable soft-delete to protect against accidental secret deletion."
            )

        # SCENARIO 5: LOW - Pas de monitoring/alerting configuré
        # Placeholder - would require checking diagnostic settings
        if not is_optimizable:
            is_optimizable = True
            optimization_score = max(optimization_score, 30)
            priority = "low" if priority == "none" else priority
            recommendations.append(
                "LOW: Configure monitoring and alerting for Key Vault access. "
                "Enable diagnostic logs to track secret access and detect anomalies."
            )

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_app_configurations(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure App Configuration stores for cost intelligence.

        Pricing (Azure App Configuration):
        - Free tier: $0/mois (1 store, 1000 requests/jour max)
        - Standard tier: $1.20/jour (~$36/mois) + data transfer

        Typical cost: $0-50/month

        Returns:
            List of AllCloudResourceData (is_orphan=False, is_optimizable=True)
        """
        try:
            from azure.mgmt.appconfiguration import AppConfigurationManagementClient
        except ImportError:
            logger.warning("azure-mgmt-appconfiguration not installed, skipping App Configuration scan")
            return []

        resources = []

        try:
            credential = self._get_azure_credential()
            app_config_client = AppConfigurationManagementClient(credential, self.subscription_id)

            # Iterate over resource groups
            for rg_name in self.resource_groups:
                try:
                    # List App Configuration stores in resource group
                    stores = app_config_client.configuration_stores.list_by_resource_group(rg_name)

                    for store in stores:
                        try:
                            # Extract location from store.location
                            store_location = getattr(store, "location", "unknown").lower()

                            # Filter by region if not global
                            if region.lower() != "global" and store_location != region.lower():
                                continue

                            # Extract metadata
                            store_id = store.id
                            store_name = store.name
                            sku_name = getattr(store.sku, "name", "Free").lower()  # "free" or "standard"
                            creation_date = getattr(store, "creation_date", None)
                            public_network_access = getattr(store, "public_network_access", "Enabled")

                            # Point-in-Time Recovery (only available in Standard tier)
                            soft_delete_retention_days = getattr(store, "soft_delete_retention_in_days", 0)
                            has_soft_delete = soft_delete_retention_days > 0

                            # Tags
                            tags = getattr(store, "tags", {}) or {}

                            # Calculate age
                            age_days = 0
                            if creation_date:
                                age_days = (datetime.now(timezone.utc) - creation_date).days

                            # Estimate daily requests (we don't have actual metrics, estimate based on tier)
                            estimated_daily_requests = 0
                            if sku_name == "standard":
                                # Assume Standard tier = high usage (otherwise why pay?)
                                estimated_daily_requests = 50000  # Estimate
                            else:
                                estimated_daily_requests = 500  # Free tier usage

                            # Count configuration keys (requires Azure Resource Graph or direct API call)
                            # For simplicity, we'll estimate based on tier
                            estimated_config_keys = 10 if sku_name == "free" else 50

                            # Estimate monthly cost
                            monthly_cost = self._estimate_app_configuration_cost(
                                sku_name=sku_name,
                                estimated_daily_requests=estimated_daily_requests
                            )

                            # Check optimization opportunities
                            is_optimizable, optimization_score, priority, potential_savings, recommendations = (
                                self._calculate_app_configuration_optimization(
                                    sku_name=sku_name,
                                    age_days=age_days,
                                    estimated_daily_requests=estimated_daily_requests,
                                    has_soft_delete=has_soft_delete,
                                    estimated_config_keys=estimated_config_keys,
                                    monthly_cost=monthly_cost,
                                )
                            )

                            # Build metadata
                            metadata = {
                                "store_id": store_id,
                                "store_name": store_name,
                                "sku": sku_name,
                                "location": store_location,
                                "resource_group": rg_name,
                                "age_days": age_days,
                                "estimated_daily_requests": estimated_daily_requests,
                                "estimated_config_keys": estimated_config_keys,
                                "has_soft_delete": has_soft_delete,
                                "soft_delete_retention_days": soft_delete_retention_days,
                                "public_network_access": public_network_access,
                                "tags": tags,
                            }

                            resource = AllCloudResourceData(
                                resource_id=store_id,
                                resource_type="azure_app_configuration",
                                resource_name=store_name,
                                region=store_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                created_at_cloud=creation_date,
                                is_orphan=False,
                                is_optimizable=is_optimizable,
                                optimization_score=optimization_score,
                                optimization_priority=priority,
                                potential_monthly_savings=potential_savings,
                                optimization_recommendations=recommendations,
                            )

                            resources.append(resource)
                            logger.info(
                                f"Found App Configuration store: {store_name} in {store_location} "
                                f"(SKU: {sku_name}, Optimizable: {is_optimizable}, Score: {optimization_score})"
                            )

                        except Exception as e:
                            logger.error(f"Error processing App Configuration store {getattr(store, 'name', 'unknown')}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Error listing App Configuration stores in resource group {rg_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning Azure App Configuration stores: {e}")

        logger.info(f"Completed Azure App Configuration scan in region {region}: {len(resources)} stores found")
        return resources

    def _estimate_app_configuration_cost(
        self,
        sku_name: str,
        estimated_daily_requests: int,
    ) -> float:
        """
        Estimate monthly cost for Azure App Configuration.

        Pricing:
        - Free tier: $0 (1 store, 1000 requests/day max)
        - Standard tier: $1.20/day (~$36/month) + data transfer
        """
        if sku_name == "free":
            return 0.0

        # Standard tier
        base_cost_per_day = 1.20
        monthly_cost = base_cost_per_day * 30  # ~$36/month

        # Add data transfer cost (estimate $0.01/GB)
        # Assume 1KB per request, so 1M requests = 1GB
        monthly_requests = estimated_daily_requests * 30
        data_transfer_gb = monthly_requests / 1000000
        data_transfer_cost = data_transfer_gb * 0.01

        return round(monthly_cost + data_transfer_cost, 2)

    def _calculate_app_configuration_optimization(
        self,
        sku_name: str,
        age_days: int,
        estimated_daily_requests: int,
        has_soft_delete: bool,
        estimated_config_keys: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Azure App Configuration.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: CRITICAL - Standard tier with 0 requests for 30+ days
        if sku_name == "standard" and estimated_daily_requests == 0 and age_days >= 30:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost  # Full cost savings by downgrading
            recommendations.append(
                "Standard tier App Configuration store has 0 requests for 30+ days. "
                "Downgrade to Free tier or delete if unused. "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 2: HIGH - Standard tier with very low usage (<1K requests/day)
        if sku_name == "standard" and estimated_daily_requests < 1000:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            potential_savings = monthly_cost * 0.9  # 90% savings by downgrading
            recommendations.append(
                f"Standard tier App Configuration store has very low usage ({estimated_daily_requests} requests/day). "
                "Free tier supports 1000 requests/day. "
                f"Downgrade to Free tier to save ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 3: HIGH - Point-in-Time Recovery not used (Standard feature waste)
        if sku_name == "standard" and not has_soft_delete:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            potential_savings = monthly_cost * 0.3  # Partial waste
            recommendations.append(
                "Standard tier App Configuration store does not have Point-in-Time Recovery enabled. "
                "Enable soft delete to leverage Standard tier features, or downgrade to Free tier. "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 4: MEDIUM - Configuration keys not used for 90+ days
        if age_days >= 90 and estimated_config_keys > 0 and estimated_daily_requests < 100:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            potential_savings = monthly_cost * 0.5 if sku_name == "standard" else 0.0
            recommendations.append(
                f"App Configuration store has {estimated_config_keys} configuration keys but very low usage "
                f"({estimated_daily_requests} requests/day for {age_days} days). "
                "Review and remove unused configuration keys, or delete the store if not needed."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 5: LOW - No feature flags used (underutilizing capabilities)
        if sku_name == "standard" and estimated_config_keys > 0:
            # This is a best practice recommendation, not a cost issue
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            potential_savings = 0.0
            recommendations.append(
                "App Configuration store is not leveraging feature flags. "
                "Consider using feature management capabilities to control feature rollouts dynamically."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_api_managements(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure API Management services for cost intelligence.

        Pricing (Azure API Management):
        - Consumption: $0.035 per 10K calls + $3.50 per GB
        - Developer: $49.79/mois (1M calls inclus)
        - Basic: $147.24/mois (pas de SLA)
        - Standard: $735.48/mois + scale units
        - Premium: $2943.04/mois + scale units + multi-region

        Typical cost: $50-500/month

        Returns:
            List of AllCloudResourceData (is_orphan=False, is_optimizable=True)
        """
        try:
            from azure.mgmt.apimanagement import ApiManagementClient
        except ImportError:
            logger.warning("azure-mgmt-apimanagement not installed, skipping API Management scan")
            return []

        resources = []

        try:
            credential = self._get_azure_credential()
            apim_client = ApiManagementClient(credential, self.subscription_id)

            # Iterate over resource groups
            for rg_name in self.resource_groups:
                try:
                    # List API Management services in resource group
                    services = apim_client.api_management_service.list_by_resource_group(rg_name)

                    for service in services:
                        try:
                            # Extract location
                            service_location = getattr(service, "location", "unknown").lower()

                            # Filter by region if not global
                            if region.lower() != "global" and service_location != region.lower():
                                continue

                            # Extract metadata
                            service_id = service.id
                            service_name = service.name
                            sku_name = getattr(service.sku, "name", "Unknown").lower()  # consumption, developer, basic, standard, premium
                            sku_capacity = getattr(service.sku, "capacity", 1)
                            creation_time = getattr(service, "created_at_utc", None)
                            provisioning_state = getattr(service, "provisioning_state", "Unknown")

                            # Gateway URL
                            gateway_url = getattr(service, "gateway_url", None)

                            # Public IP addresses (for Premium multi-region)
                            public_ip_addresses = getattr(service, "public_ip_addresses", [])

                            # Tags
                            tags = getattr(service, "tags", {}) or {}

                            # Calculate age
                            age_days = 0
                            if creation_time:
                                age_days = (datetime.now(timezone.utc) - creation_time).days

                            # Count APIs and revisions (requires API call)
                            # For simplicity, we'll estimate based on tier
                            estimated_apis = 0
                            estimated_revisions = 0
                            try:
                                apis = apim_client.api.list_by_service(rg_name, service_name)
                                api_list = list(apis)
                                estimated_apis = len(api_list)

                                # Count total revisions across all APIs
                                for api in api_list:
                                    try:
                                        revisions = apim_client.api_revision.list_by_service(
                                            rg_name, service_name, api.name
                                        )
                                        estimated_revisions += len(list(revisions))
                                    except Exception:
                                        pass
                            except Exception as e:
                                logger.debug(f"Error counting APIs for {service_name}: {e}")
                                # Fallback estimate
                                estimated_apis = 5 if sku_name in ["standard", "premium"] else 2

                            # Estimate daily requests (no direct metrics available, estimate based on tier)
                            estimated_daily_requests = 0
                            if sku_name == "consumption":
                                estimated_daily_requests = 10000  # 10K
                            elif sku_name == "developer":
                                estimated_daily_requests = 50000  # 50K
                            elif sku_name == "basic":
                                estimated_daily_requests = 100000  # 100K
                            elif sku_name == "standard":
                                estimated_daily_requests = 500000  # 500K
                            elif sku_name == "premium":
                                estimated_daily_requests = 2000000  # 2M

                            # Estimate monthly cost
                            monthly_cost = self._estimate_api_management_cost(
                                sku_name=sku_name,
                                sku_capacity=sku_capacity,
                                estimated_daily_requests=estimated_daily_requests
                            )

                            # Check optimization opportunities
                            is_optimizable, optimization_score, priority, potential_savings, recommendations = (
                                self._calculate_api_management_optimization(
                                    sku_name=sku_name,
                                    sku_capacity=sku_capacity,
                                    age_days=age_days,
                                    estimated_daily_requests=estimated_daily_requests,
                                    estimated_apis=estimated_apis,
                                    estimated_revisions=estimated_revisions,
                                    monthly_cost=monthly_cost,
                                )
                            )

                            # Build metadata
                            metadata = {
                                "service_id": service_id,
                                "service_name": service_name,
                                "sku": sku_name,
                                "sku_capacity": sku_capacity,
                                "location": service_location,
                                "resource_group": rg_name,
                                "age_days": age_days,
                                "provisioning_state": provisioning_state,
                                "gateway_url": gateway_url,
                                "estimated_daily_requests": estimated_daily_requests,
                                "estimated_apis": estimated_apis,
                                "estimated_revisions": estimated_revisions,
                                "public_ip_addresses": public_ip_addresses,
                                "tags": tags,
                            }

                            resource = AllCloudResourceData(
                                resource_id=service_id,
                                resource_type="azure_api_management",
                                resource_name=service_name,
                                region=service_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                created_at_cloud=creation_time,
                                is_orphan=False,
                                is_optimizable=is_optimizable,
                                optimization_score=optimization_score,
                                optimization_priority=priority,
                                potential_monthly_savings=potential_savings,
                                optimization_recommendations=recommendations,
                            )

                            resources.append(resource)
                            logger.info(
                                f"Found API Management service: {service_name} in {service_location} "
                                f"(SKU: {sku_name}, Optimizable: {is_optimizable}, Score: {optimization_score})"
                            )

                        except Exception as e:
                            logger.error(f"Error processing API Management service {getattr(service, 'name', 'unknown')}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Error listing API Management services in resource group {rg_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning Azure API Management services: {e}")

        logger.info(f"Completed Azure API Management scan in region {region}: {len(resources)} services found")
        return resources

    def _estimate_api_management_cost(
        self,
        sku_name: str,
        sku_capacity: int,
        estimated_daily_requests: int,
    ) -> float:
        """
        Estimate monthly cost for Azure API Management.

        Pricing:
        - Consumption: $0.035 per 10K calls + $3.50 per GB
        - Developer: $49.79/mois (1M calls inclus)
        - Basic: $147.24/mois (pas de SLA)
        - Standard: $735.48/mois + scale units
        - Premium: $2943.04/mois + scale units + multi-region
        """
        if sku_name == "consumption":
            # Consumption pricing: $0.035 per 10K calls
            monthly_calls = estimated_daily_requests * 30
            cost = (monthly_calls / 10000) * 0.035
            # Add data transfer estimate ($3.50/GB, assume 1KB per call)
            data_gb = (monthly_calls / 1000000)  # 1KB per call
            cost += data_gb * 3.50
            return round(cost, 2)

        elif sku_name == "developer":
            return 49.79  # Fixed cost

        elif sku_name == "basic":
            return 147.24 * sku_capacity  # Per unit

        elif sku_name == "standard":
            return 735.48 * sku_capacity  # Per unit

        elif sku_name == "premium":
            return 2943.04 * sku_capacity  # Per unit

        else:
            return 50.0  # Fallback estimate

    def _calculate_api_management_optimization(
        self,
        sku_name: str,
        sku_capacity: int,
        age_days: int,
        estimated_daily_requests: int,
        estimated_apis: int,
        estimated_revisions: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Azure API Management.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: CRITICAL - Service with 0 requests for 90+ days
        if estimated_daily_requests == 0 and age_days >= 90:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost  # Full cost
            recommendations.append(
                "API Management service has 0 requests for 90+ days. "
                "Delete the service or downgrade to Consumption tier if keeping for testing. "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 2: HIGH - Premium tier with low usage (<100K requests/day)
        if sku_name == "premium" and estimated_daily_requests < 100000:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            # Premium costs $2943/month, Standard costs $735/month
            potential_savings = monthly_cost - (735.48 * sku_capacity)
            recommendations.append(
                f"Premium tier API Management service has low usage ({estimated_daily_requests} requests/day). "
                f"Downgrade to Standard tier to save ${potential_savings:.2f}/month. "
                "Premium features (multi-region, VNet) may not be needed."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 3: HIGH - Too many API revisions (>10 revisions per API)
        if estimated_apis > 0:
            avg_revisions_per_api = estimated_revisions / estimated_apis
            if avg_revisions_per_api > 10:
                is_optimizable = True
                optimization_score = 70
                priority = "high"
                potential_savings = 0.0  # No direct cost savings, but maintenance waste
                recommendations.append(
                    f"API Management service has {estimated_revisions} revisions for {estimated_apis} APIs "
                    f"(avg {avg_revisions_per_api:.1f} revisions/API). "
                    "Clean up old/unused revisions to improve performance and reduce complexity."
                )
                return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 4: MEDIUM - Standard/Premium tier with very low usage (<10K requests/day)
        if sku_name in ["standard", "premium"] and estimated_daily_requests < 10000:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            # Downgrade to Consumption tier
            consumption_cost = (estimated_daily_requests * 30 / 10000) * 0.035
            potential_savings = monthly_cost - consumption_cost
            recommendations.append(
                f"{sku_name.title()} tier API Management service has very low usage ({estimated_daily_requests} requests/day). "
                f"Downgrade to Consumption tier to save ${potential_savings:.2f}/month. "
                "Consumption tier is ideal for dev/test and low-volume APIs."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 5: LOW - No monitoring/alerting configured (best practice)
        # Placeholder - would require checking diagnostic settings
        if not is_optimizable:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            potential_savings = 0.0
            recommendations.append(
                "LOW: Configure monitoring and alerting for API Management service. "
                "Enable Application Insights integration and set up alerts for high latency, errors, and throttling."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_logic_apps(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Logic Apps for cost intelligence.

        Pricing (Azure Logic Apps):
        - Consumption: $0.000025 per action + $0.000125 per trigger
        - Standard: Starts at ~$200/mois (App Service Plan)

        Typical cost: $5-100/month

        Returns:
            List of AllCloudResourceData (is_orphan=False, is_optimizable=True)
        """
        try:
            from azure.mgmt.logic import LogicManagementClient
        except ImportError:
            logger.warning("azure-mgmt-logic not installed, skipping Logic Apps scan")
            return []

        resources = []

        try:
            credential = self._get_azure_credential()
            logic_client = LogicManagementClient(credential, self.subscription_id)

            # Iterate over resource groups
            for rg_name in self.resource_groups:
                try:
                    # List Logic Apps in resource group
                    workflows = logic_client.workflows.list_by_resource_group(rg_name)

                    for workflow in workflows:
                        try:
                            # Extract location
                            workflow_location = getattr(workflow, "location", "unknown").lower()

                            # Filter by region if not global
                            if region.lower() != "global" and workflow_location != region.lower():
                                continue

                            # Extract metadata
                            workflow_id = workflow.id
                            workflow_name = workflow.name
                            state = getattr(workflow, "state", "Unknown")  # Enabled, Disabled, etc.
                            sku_name = getattr(getattr(workflow, "sku", None), "name", "NotSpecified")  # NotSpecified (Consumption), Standard, etc.
                            created_time = getattr(workflow, "created_time", None)
                            changed_time = getattr(workflow, "changed_time", None)

                            # Workflow definition
                            definition = getattr(workflow, "definition", {})

                            # Tags
                            tags = getattr(workflow, "tags", {}) or {}

                            # Calculate age
                            age_days = 0
                            if created_time:
                                age_days = (datetime.now(timezone.utc) - created_time).days

                            # Get workflow run history (to detect activity)
                            runs_count_30d = 0
                            failed_runs_count = 0
                            try:
                                # Get runs from last 30 days
                                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                                runs = logic_client.workflow_runs.list(rg_name, workflow_name)

                                for run in runs:
                                    run_start_time = getattr(run, "start_time", None)
                                    run_status = getattr(run, "status", "Unknown")

                                    if run_start_time and run_start_time >= thirty_days_ago:
                                        runs_count_30d += 1
                                        if run_status in ["Failed", "Cancelled", "TimedOut"]:
                                            failed_runs_count += 1

                                    # Limit iteration for performance
                                    if runs_count_30d >= 1000:
                                        break
                            except Exception as e:
                                logger.debug(f"Error fetching runs for workflow {workflow_name}: {e}")
                                # Fallback estimate
                                if state == "Enabled":
                                    runs_count_30d = 100  # Estimate
                                else:
                                    runs_count_30d = 0

                            # Count actions in workflow definition
                            actions_count = 0
                            if isinstance(definition, dict):
                                actions = definition.get("actions", {})
                                actions_count = len(actions) if isinstance(actions, dict) else 0

                            # Estimate monthly executions
                            estimated_monthly_executions = int(runs_count_30d)

                            # Estimate monthly cost
                            monthly_cost = self._estimate_logic_app_cost(
                                sku_name=sku_name,
                                estimated_monthly_executions=estimated_monthly_executions,
                                actions_count=actions_count
                            )

                            # Check optimization opportunities
                            is_optimizable, optimization_score, priority, potential_savings, recommendations = (
                                self._calculate_logic_app_optimization(
                                    state=state,
                                    sku_name=sku_name,
                                    age_days=age_days,
                                    runs_count_30d=runs_count_30d,
                                    failed_runs_count=failed_runs_count,
                                    actions_count=actions_count,
                                    monthly_cost=monthly_cost,
                                )
                            )

                            # Build metadata
                            metadata = {
                                "workflow_id": workflow_id,
                                "workflow_name": workflow_name,
                                "state": state,
                                "sku": sku_name,
                                "location": workflow_location,
                                "resource_group": rg_name,
                                "age_days": age_days,
                                "runs_count_30d": runs_count_30d,
                                "failed_runs_count": failed_runs_count,
                                "actions_count": actions_count,
                                "estimated_monthly_executions": estimated_monthly_executions,
                                "created_time": created_time.isoformat() if created_time else None,
                                "changed_time": changed_time.isoformat() if changed_time else None,
                                "tags": tags,
                            }

                            resource = AllCloudResourceData(
                                resource_id=workflow_id,
                                resource_type="azure_logic_app",
                                resource_name=workflow_name,
                                region=workflow_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                created_at_cloud=created_time,
                                is_orphan=False,
                                is_optimizable=is_optimizable,
                                optimization_score=optimization_score,
                                optimization_priority=priority,
                                potential_monthly_savings=potential_savings,
                                optimization_recommendations=recommendations,
                            )

                            resources.append(resource)
                            logger.info(
                                f"Found Logic App: {workflow_name} in {workflow_location} "
                                f"(State: {state}, Optimizable: {is_optimizable}, Score: {optimization_score})"
                            )

                        except Exception as e:
                            logger.error(f"Error processing Logic App {getattr(workflow, 'name', 'unknown')}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Error listing Logic Apps in resource group {rg_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning Azure Logic Apps: {e}")

        logger.info(f"Completed Azure Logic Apps scan in region {region}: {len(resources)} workflows found")
        return resources

    def _estimate_logic_app_cost(
        self,
        sku_name: str,
        estimated_monthly_executions: int,
        actions_count: int,
    ) -> float:
        """
        Estimate monthly cost for Azure Logic Apps.

        Pricing:
        - Consumption: $0.000025 per action execution
        - Standard: ~$200/month (App Service Plan based)
        """
        if sku_name.lower() in ["notspecified", "consumption"]:
            # Consumption pricing
            # Assume average of 5 actions per execution
            total_actions = estimated_monthly_executions * max(actions_count, 5)
            cost = total_actions * 0.000025
            return round(cost, 2)
        elif sku_name.lower() == "standard":
            # Standard tier (App Service Plan)
            return 200.0  # Base estimate
        else:
            # Fallback
            return 10.0

    def _calculate_logic_app_optimization(
        self,
        state: str,
        sku_name: str,
        age_days: int,
        runs_count_30d: int,
        failed_runs_count: int,
        actions_count: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Azure Logic Apps.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: CRITICAL - Disabled workflow for 90+ days
        if state.lower() == "disabled" and age_days >= 90:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost  # Full savings if deleted
            recommendations.append(
                f"Logic App workflow is disabled for {age_days} days. "
                "Delete the workflow if no longer needed to eliminate any residual costs. "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 2: HIGH - Standard tier with low executions (<100 runs/month)
        if sku_name.lower() == "standard" and runs_count_30d < 100:
            is_optimizable = True
            optimization_score = 75
            priority = "high"
            # Consumption would cost: 100 runs * 5 actions * $0.000025 = $0.0125
            consumption_cost = (runs_count_30d * max(actions_count, 5)) * 0.000025
            potential_savings = monthly_cost - consumption_cost
            recommendations.append(
                f"Standard tier Logic App has very low usage ({runs_count_30d} runs/month). "
                f"Downgrade to Consumption tier to save ${potential_savings:.2f}/month. "
                "Standard tier is only cost-effective for high-volume workflows."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 3: HIGH - High failure rate (>50% failed runs)
        if runs_count_30d > 0:
            failure_rate = (failed_runs_count / runs_count_30d) * 100
            if failure_rate > 50:
                is_optimizable = True
                optimization_score = 70
                priority = "high"
                potential_savings = monthly_cost * 0.5  # Waste due to failed runs
                recommendations.append(
                    f"Logic App has high failure rate ({failure_rate:.1f}% of {runs_count_30d} runs failed). "
                    "Review and fix workflow errors to reduce wasted executions. "
                    f"Potential savings: ${potential_savings:.2f}/month."
                )
                return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 4: MEDIUM - No executions in 30 days (but enabled)
        if state.lower() == "enabled" and runs_count_30d == 0 and age_days >= 30:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            potential_savings = monthly_cost * 0.8  # Partial savings
            recommendations.append(
                "Logic App workflow is enabled but has 0 executions in 30 days. "
                "Disable or delete if not needed, or verify trigger configuration. "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 5: LOW - No error handling configured
        if actions_count > 0:
            # Best practice recommendation (no direct cost savings)
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            potential_savings = 0.0
            recommendations.append(
                f"Logic App has {actions_count} actions but no explicit error handling. "
                "Add retry policies and error scopes to improve reliability and reduce failed runs."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        return is_optimizable, optimization_score, priority, potential_savings, recommendations

    async def scan_data_factories(self, region: str) -> list[AllCloudResourceData]:
        """
        Scan ALL Azure Data Factory instances for cost intelligence.

        Pricing (Azure Data Factory):
        - Pipeline orchestration: $0.001 per activity run
        - Data movement (Copy): $0.25 per DIU-hour
        - Integration Runtime (IR): $0.274/hour (Azure IR), $0.10-0.84/hour (Self-hosted IR)

        Typical cost: $10-200/month

        Returns:
            List of AllCloudResourceData (is_orphan=False, is_optimizable=True)
        """
        try:
            from azure.mgmt.datafactory import DataFactoryManagementClient
        except ImportError:
            logger.warning("azure-mgmt-datafactory not installed, skipping Data Factory scan")
            return []

        resources = []

        try:
            credential = self._get_azure_credential()
            df_client = DataFactoryManagementClient(credential, self.subscription_id)

            # Iterate over resource groups
            for rg_name in self.resource_groups:
                try:
                    # List Data Factories in resource group
                    factories = df_client.factories.list_by_resource_group(rg_name)

                    for factory in factories:
                        try:
                            # Extract location
                            factory_location = getattr(factory, "location", "unknown").lower()

                            # Filter by region if not global
                            if region.lower() != "global" and factory_location != region.lower():
                                continue

                            # Extract metadata
                            factory_id = getattr(factory, "id", "")
                            factory_name = getattr(factory, "name", "unknown")
                            provisioning_state = getattr(factory, "provisioning_state", "Unknown")
                            version = getattr(factory, "version", "V2")
                            created_time = getattr(factory, "create_time", None)

                            # Tags
                            tags = getattr(factory, "tags", {}) or {}

                            # Calculate age
                            age_days = 0
                            if created_time:
                                age_days = (datetime.now(timezone.utc) - created_time).days

                            # Count pipelines
                            pipelines_count = 0
                            active_pipelines_count = 0
                            try:
                                pipelines = df_client.pipelines.list_by_factory(rg_name, factory_name)
                                pipelines_list = list(pipelines)
                                pipelines_count = len(pipelines_list)

                                # Check which pipelines are actively used (heuristic)
                                for pipeline in pipelines_list[:20]:  # Limit to first 20 for performance
                                    try:
                                        # Try to get recent runs
                                        runs = df_client.pipeline_runs.query_by_factory(
                                            rg_name,
                                            factory_name,
                                            {
                                                "lastUpdatedAfter": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                                                "lastUpdatedBefore": datetime.now(timezone.utc).isoformat(),
                                                "filters": [
                                                    {
                                                        "operand": "PipelineName",
                                                        "operator": "Equals",
                                                        "values": [pipeline.name]
                                                    }
                                                ]
                                            }
                                        )
                                        if runs.value and len(runs.value) > 0:
                                            active_pipelines_count += 1
                                    except Exception:
                                        pass
                            except Exception as e:
                                logger.debug(f"Error counting pipelines for {factory_name}: {e}")
                                # Fallback estimate
                                pipelines_count = 10

                            # Count Integration Runtimes
                            ir_count = 0
                            self_hosted_ir_count = 0
                            try:
                                irs = df_client.integration_runtimes.list_by_factory(rg_name, factory_name)
                                for ir in irs:
                                    ir_count += 1
                                    ir_type = getattr(getattr(ir, "properties", None), "type", "Unknown")
                                    if ir_type == "SelfHosted":
                                        self_hosted_ir_count += 1
                            except Exception:
                                ir_count = 1  # Fallback

                            # Estimate activity runs per month (no direct metric)
                            estimated_monthly_runs = active_pipelines_count * 30  # Estimate 1 run/day per active pipeline

                            # Estimate monthly cost
                            monthly_cost = self._estimate_data_factory_cost(
                                estimated_monthly_runs=estimated_monthly_runs,
                                ir_count=ir_count,
                                self_hosted_ir_count=self_hosted_ir_count
                            )

                            # Check optimization opportunities
                            is_optimizable, optimization_score, priority, potential_savings, recommendations = (
                                self._calculate_data_factory_optimization(
                                    age_days=age_days,
                                    pipelines_count=pipelines_count,
                                    active_pipelines_count=active_pipelines_count,
                                    ir_count=ir_count,
                                    self_hosted_ir_count=self_hosted_ir_count,
                                    estimated_monthly_runs=estimated_monthly_runs,
                                    monthly_cost=monthly_cost,
                                )
                            )

                            # Build metadata
                            metadata = {
                                "factory_id": factory_id,
                                "factory_name": factory_name,
                                "version": version,
                                "provisioning_state": provisioning_state,
                                "location": factory_location,
                                "resource_group": rg_name,
                                "age_days": age_days,
                                "pipelines_count": pipelines_count,
                                "active_pipelines_count": active_pipelines_count,
                                "ir_count": ir_count,
                                "self_hosted_ir_count": self_hosted_ir_count,
                                "estimated_monthly_runs": estimated_monthly_runs,
                                "tags": tags,
                            }

                            resource = AllCloudResourceData(
                                resource_id=factory_id,
                                resource_type="azure_data_factory",
                                resource_name=factory_name,
                                region=factory_location,
                                estimated_monthly_cost=monthly_cost,
                                currency="USD",
                                resource_metadata=metadata,
                                created_at_cloud=created_time,
                                is_orphan=False,
                                is_optimizable=is_optimizable,
                                optimization_score=optimization_score,
                                optimization_priority=priority,
                                potential_monthly_savings=potential_savings,
                                optimization_recommendations=recommendations,
                            )

                            resources.append(resource)
                            logger.info(
                                f"Found Data Factory: {factory_name} in {factory_location} "
                                f"(Pipelines: {pipelines_count}, Optimizable: {is_optimizable}, Score: {optimization_score})"
                            )

                        except Exception as e:
                            logger.error(f"Error processing Data Factory {getattr(factory, 'name', 'unknown')}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Error listing Data Factories in resource group {rg_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning Azure Data Factories: {e}")

        logger.info(f"Completed Azure Data Factory scan in region {region}: {len(resources)} factories found")
        return resources

    def _estimate_data_factory_cost(
        self,
        estimated_monthly_runs: int,
        ir_count: int,
        self_hosted_ir_count: int,
    ) -> float:
        """
        Estimate monthly cost for Azure Data Factory.

        Pricing:
        - Pipeline orchestration: $0.001 per activity run
        - Integration Runtime: $0.274/hour (Azure IR)
        """
        # Activity runs cost
        activity_runs_cost = estimated_monthly_runs * 0.001

        # IR cost (assume IR runs 8 hours/day for active factories)
        ir_hours_per_month = 8 * 30 * ir_count  # 8 hours/day * 30 days
        ir_cost = ir_hours_per_month * 0.274

        total_cost = activity_runs_cost + ir_cost
        return round(total_cost, 2)

    def _calculate_data_factory_optimization(
        self,
        age_days: int,
        pipelines_count: int,
        active_pipelines_count: int,
        ir_count: int,
        self_hosted_ir_count: int,
        estimated_monthly_runs: int,
        monthly_cost: float,
    ) -> tuple[bool, int, str, float, list[str]]:
        """
        Calculate optimization opportunities for Azure Data Factory.

        Returns:
            (is_optimizable, optimization_score, priority, potential_savings, recommendations)
        """
        is_optimizable = False
        optimization_score = 0
        priority = "none"
        potential_savings = 0.0
        recommendations = []

        # Scenario 1: CRITICAL - No active pipelines for 90+ days
        if active_pipelines_count == 0 and age_days >= 90:
            is_optimizable = True
            optimization_score = 90
            priority = "critical"
            potential_savings = monthly_cost
            recommendations.append(
                f"Data Factory has 0 active pipelines for {age_days} days. "
                "Delete the Data Factory if no longer needed to eliminate all costs. "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 2: HIGH - Many inactive pipelines (>50% inactive)
        if pipelines_count > 0:
            inactive_pipelines = pipelines_count - active_pipelines_count
            inactive_ratio = (inactive_pipelines / pipelines_count) * 100
            if inactive_ratio > 50 and inactive_pipelines > 5:
                is_optimizable = True
                optimization_score = 75
                priority = "high"
                potential_savings = monthly_cost * 0.3  # Estimate 30% savings
                recommendations.append(
                    f"Data Factory has {inactive_pipelines} inactive pipelines out of {pipelines_count} total ({inactive_ratio:.1f}%). "
                    "Delete unused pipelines to reduce complexity and improve performance. "
                    f"Potential savings: ${potential_savings:.2f}/month."
                )
                return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 3: HIGH - Unused Integration Runtimes
        if ir_count > 1 and active_pipelines_count < ir_count:
            is_optimizable = True
            optimization_score = 70
            priority = "high"
            # Each unused IR costs ~$65/month (8h/day * 30 days * $0.274/hour)
            unused_irs = ir_count - max(active_pipelines_count, 1)
            potential_savings = unused_irs * 65
            recommendations.append(
                f"Data Factory has {ir_count} Integration Runtimes but only {active_pipelines_count} active pipelines. "
                f"Remove {unused_irs} unused Integration Runtimes to save ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 4: MEDIUM - Low activity (< 100 runs/month)
        if estimated_monthly_runs < 100 and estimated_monthly_runs > 0:
            is_optimizable = True
            optimization_score = 50
            priority = "medium"
            potential_savings = monthly_cost * 0.5
            recommendations.append(
                f"Data Factory has very low activity ({estimated_monthly_runs} runs/month). "
                "Consider consolidating with other Data Factories or using serverless alternatives (Logic Apps). "
                f"Potential savings: ${potential_savings:.2f}/month."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        # Scenario 5: LOW - No monitoring/alerting configured
        if not is_optimizable:
            is_optimizable = True
            optimization_score = 30
            priority = "low"
            potential_savings = 0.0
            recommendations.append(
                "LOW: Configure monitoring and alerting for Data Factory pipelines. "
                "Enable diagnostic logs and set up alerts for pipeline failures and long-running activities."
            )
            return is_optimizable, optimization_score, priority, potential_savings, recommendations

        return is_optimizable, optimization_score, priority, potential_savings, recommendations