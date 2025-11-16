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
