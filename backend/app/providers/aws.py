"""AWS cloud provider implementation."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import aioboto3
import boto3
from botocore.exceptions import ClientError

from app.providers.base import CloudProviderBase, OrphanResourceData


class AWSProvider(CloudProviderBase):
    """
    AWS implementation of the cloud provider interface.

    Scans AWS resources across regions to detect orphaned and unused resources.
    Uses boto3 for synchronous operations and aioboto3 for async operations.
    """

    # AWS pricing constants (USD per month)
    PRICING = {
        "ebs_gp3_per_gb": 0.08,  # General Purpose SSD (gp3)
        "ebs_gp2_per_gb": 0.10,  # General Purpose SSD (gp2)
        "ebs_io1_per_gb": 0.125,  # Provisioned IOPS SSD (io1)
        "ebs_io2_per_gb": 0.125,  # Provisioned IOPS SSD (io2)
        "ebs_st1_per_gb": 0.045,  # Throughput Optimized HDD (st1)
        "ebs_sc1_per_gb": 0.015,  # Cold HDD (sc1)
        "ebs_standard_per_gb": 0.05,  # Magnetic (standard)
        "snapshot_per_gb": 0.05,  # EBS Snapshot
        "elastic_ip": 3.60,  # Unassociated Elastic IP
        "nat_gateway": 32.40,  # NAT Gateway (base cost)
        "alb": 22.00,  # Application Load Balancer
        "nlb": 22.00,  # Network Load Balancer
        "clb": 18.00,  # Classic Load Balancer
    }

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        regions: list[str] | None = None,
    ) -> None:
        """
        Initialize AWS provider.

        Args:
            access_key: AWS Access Key ID
            secret_key: AWS Secret Access Key
            regions: List of AWS regions to scan (None = all regions)
        """
        super().__init__(access_key, secret_key, regions)
        self.session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate AWS credentials using STS GetCallerIdentity.

        Returns:
            Dict with account_id, arn, user_id

        Raises:
            ClientError: If credentials are invalid
        """
        async with self.session.client("sts", region_name="us-east-1") as sts:
            response = await sts.get_caller_identity()
            return {
                "account_id": response["Account"],
                "arn": response["Arn"],
                "user_id": response["UserId"],
            }

    async def get_available_regions(self) -> list[str]:
        """
        Get list of available AWS regions for EC2.

        Returns:
            List of region names (e.g., ['us-east-1', 'eu-west-1'])
        """
        async with self.session.client("ec2", region_name="us-east-1") as ec2:
            response = await ec2.describe_regions()
            return [region["RegionName"] for region in response["Regions"]]

    async def _check_volume_usage_history(
        self, volume_id: str, region: str, created_at: datetime
    ) -> dict:
        """
        Check EBS volume usage history via CloudWatch metrics.

        Returns dict with:
        - ever_used: bool (True if volume has any historical activity)
        - last_active_date: datetime or None
        - total_read_ops: int
        - total_write_ops: int
        - usage_category: str ("never_used", "recently_abandoned", "long_abandoned")
        """
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                now = datetime.now(timezone.utc)

                # Check last 90 days of activity (or since creation if younger)
                lookback_days = min(90, (now - created_at).days)
                start_time = now - timedelta(days=lookback_days)

                # Get VolumeReadOps metric
                read_response = await cw.get_metric_statistics(
                    Namespace="AWS/EBS",
                    MetricName="VolumeReadOps",
                    Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
                    StartTime=start_time,
                    EndTime=now,
                    Period=86400,  # 1 day
                    Statistics=["Sum"],
                )

                # Get VolumeWriteOps metric
                write_response = await cw.get_metric_statistics(
                    Namespace="AWS/EBS",
                    MetricName="VolumeWriteOps",
                    Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
                    StartTime=start_time,
                    EndTime=now,
                    Period=86400,  # 1 day
                    Statistics=["Sum"],
                )

                # Calculate total operations
                read_datapoints = read_response.get("Datapoints", [])
                write_datapoints = write_response.get("Datapoints", [])

                total_read_ops = sum(dp["Sum"] for dp in read_datapoints)
                total_write_ops = sum(dp["Sum"] for dp in write_datapoints)
                total_ops = total_read_ops + total_write_ops

                # Determine last active date
                all_datapoints = read_datapoints + write_datapoints
                last_active_date = None
                if all_datapoints:
                    # Find most recent datapoint with activity
                    active_datapoints = [
                        dp for dp in all_datapoints if dp.get("Sum", 0) > 0
                    ]
                    if active_datapoints:
                        last_active_date = max(dp["Timestamp"] for dp in active_datapoints)

                # Determine usage category
                ever_used = total_ops > 0

                if not ever_used:
                    usage_category = "never_used"
                elif last_active_date:
                    days_since_last_use = (now - last_active_date).days
                    if days_since_last_use < 7:
                        usage_category = "recently_active"  # Not orphan
                    elif days_since_last_use < 30:
                        usage_category = "recently_abandoned"
                    else:
                        usage_category = "long_abandoned"
                else:
                    usage_category = "unknown"

                return {
                    "ever_used": ever_used,
                    "last_active_date": last_active_date.isoformat() if last_active_date else None,
                    "total_read_ops": int(total_read_ops),
                    "total_write_ops": int(total_write_ops),
                    "usage_category": usage_category,
                    "days_since_last_use": (now - last_active_date).days if last_active_date else None,
                }

        except Exception as e:
            print(f"Error checking volume usage history for {volume_id}: {e}")
            return {
                "ever_used": None,
                "last_active_date": None,
                "total_read_ops": 0,
                "total_write_ops": 0,
                "usage_category": "unknown",
                "days_since_last_use": None,
            }

    async def scan_unattached_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for unattached EBS volumes in a region with intelligent orphan detection.

        Uses CloudWatch metrics to detect:
        - Volumes never used (never attached or no I/O activity)
        - Volumes used in the past but abandoned (no recent activity)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules (uses defaults if None)

        Returns:
            List of truly orphaned EBS volume resources
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        # Check if detection is enabled
        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 7)
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "status", "Values": ["available"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    volume_type = volume["VolumeType"]
                    created_at = volume["CreateTime"]

                    # Calculate volume age in days
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    # Skip if volume is too young
                    if age_days < min_age_days:
                        continue

                    # Check usage history via CloudWatch
                    usage_history = await self._check_volume_usage_history(
                        volume_id, region, created_at
                    )

                    # Skip if volume was recently active (not orphaned)
                    if usage_history["usage_category"] == "recently_active":
                        continue

                    # Calculate monthly cost based on volume type
                    price_key = f"ebs_{volume_type}_per_gb"
                    price_per_gb = self.PRICING.get(
                        price_key, self.PRICING["ebs_gp2_per_gb"]
                    )
                    monthly_cost = size_gb * price_per_gb

                    # Extract name from tags
                    name = None
                    for tag in volume.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    # Determine confidence level based on usage history
                    if usage_history["usage_category"] == "never_used" and age_days >= 30:
                        confidence = "high"
                        reason = f"Never used since creation {age_days} days ago"
                    elif usage_history["usage_category"] == "long_abandoned":
                        confidence = "high"
                        days_abandoned = usage_history.get("days_since_last_use", 0)
                        reason = f"No activity for {days_abandoned} days (was active before)"
                    elif usage_history["usage_category"] == "recently_abandoned":
                        confidence = "medium"
                        days_abandoned = usage_history.get("days_since_last_use", 0)
                        reason = f"No activity for {days_abandoned} days"
                    elif usage_history["usage_category"] == "never_used" and age_days < 30:
                        confidence = "low"
                        reason = f"Created {age_days} days ago, never used yet (may be for future use)"
                    else:
                        # Unknown usage history (CloudWatch metrics unavailable)
                        if age_days == 0:
                            confidence = "low"
                            reason = "Recently created (less than 24h), usage pattern unclear"
                        elif age_days >= confidence_threshold_days:
                            confidence = "medium"
                            reason = f"Unattached for {age_days} days (usage history unavailable)"
                        else:
                            confidence = "low"
                            reason = f"Unattached for {age_days} days (usage history unavailable)"

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_cost, 2),
                            resource_metadata={
                                "size_gb": size_gb,
                                "volume_type": volume_type,
                                "created_at": created_at.isoformat(),
                                "availability_zone": volume["AvailabilityZone"],
                                "encrypted": volume.get("Encrypted", False),
                                "age_days": age_days,
                                "confidence": confidence,
                                "orphan_reason": reason,
                                "usage_history": usage_history,
                            },
                        )
                    )

        except ClientError as e:
            # Log error but don't fail entire scan
            print(f"Error scanning unattached volumes in {region}: {e}")

        return orphans

    async def scan_unassigned_ips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for unassigned Elastic IP addresses in a region.

        Detects Elastic IPs not associated with any instance or network interface.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules for this resource type

        Returns:
            List of orphan Elastic IP resources
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        # Check if detection is enabled
        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 3)
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 7)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_addresses()

                for address in response.get("Addresses", []):
                    # Check if IP is not associated
                    if "AssociationId" not in address:
                        allocation_id = address.get("AllocationId", "N/A")
                        public_ip = address.get("PublicIp", "Unknown")

                        # AWS EC2 API doesn't provide allocation time for Elastic IPs
                        # We need to use CloudWatch Logs or CloudTrail to get precise creation time
                        # Workaround: Check the "NetworkInterfaceOwnerId" last state change

                        # For MVP: Use a heuristic - if the IP has never been associated,
                        # it's likely recent OR very old (both cases warrant investigation)
                        # If user wants age filtering, they must add "CreatedDate" tag manually

                        name = None
                        created_date = None

                        for tag in address.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                            elif tag["Key"] == "CreatedDate":
                                # User can manually tag IPs with creation date in ISO format
                                try:
                                    from datetime import datetime
                                    created_date = datetime.fromisoformat(tag["Value"].replace('Z', '+00:00'))
                                except Exception:
                                    pass

                        # Calculate age if creation date is available
                        if created_date:
                            age_days = (datetime.now(timezone.utc) - created_date).days
                            if age_days < min_age_days:
                                continue
                            confidence = "high" if age_days >= confidence_threshold_days else "medium"
                            reason = f"Not associated for {age_days} days"
                        else:
                            # No creation date available - can't determine age
                            # If user requires min_age > 0, skip to avoid false positives
                            if min_age_days > 0:
                                continue  # Skip - can't verify age requirement

                            # Only detect if min_age = 0 (immediate detection)
                            age_days = -1  # -1 indicates unknown age
                            confidence = "low"
                            reason = "Not associated (age unknown - add 'CreatedDate' tag for tracking)"

                        # Build metadata
                        metadata = {
                            "public_ip": public_ip,
                            "domain": address.get("Domain", "vpc"),
                            "age_days": age_days,
                            "confidence": confidence,
                            "orphan_reason": reason,
                        }

                        # Add created_at if we have it from the tag
                        if created_date:
                            metadata["created_at"] = created_date.isoformat()

                        orphans.append(
                            OrphanResourceData(
                                resource_type="elastic_ip",
                                resource_id=allocation_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=self.PRICING["elastic_ip"],
                                resource_metadata=metadata,
                            )
                        )

        except ClientError as e:
            print(f"Error scanning unassigned IPs in {region}: {e}")

        return orphans

    async def scan_orphaned_snapshots(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for orphaned EBS snapshots in a region.

        Detects snapshots older than 90 days where source volume no longer exists.

        Args:
            region: AWS region to scan

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])

                # Get all existing volume IDs
                volumes_response = await ec2.describe_volumes()
                existing_volume_ids = {
                    vol["VolumeId"] for vol in volumes_response.get("Volumes", [])
                }

                cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)

                for snapshot in response.get("Snapshots", []):
                    snapshot_id = snapshot["SnapshotId"]
                    volume_id = snapshot.get("VolumeId")
                    start_time = snapshot["StartTime"]

                    # Check if snapshot is old and volume doesn't exist
                    if start_time < cutoff_date and volume_id not in existing_volume_ids:
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                        # Extract name/description
                        description = snapshot.get("Description", "")
                        name = None
                        for tag in snapshot.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        orphans.append(
                            OrphanResourceData(
                                resource_type="ebs_snapshot",
                                resource_id=snapshot_id,
                                resource_name=name or description,
                                region=region,
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata={
                                    "size_gb": size_gb,
                                    "volume_id": volume_id or "Unknown",
                                    "created_at": start_time.isoformat(),
                                    "description": description,
                                    "encrypted": snapshot.get("Encrypted", False),
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning orphaned snapshots in {region}: {e}")

        return orphans

    async def scan_stopped_instances(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for EC2 instances stopped for more than 30 days.

        Detects instances in 'stopped' state with state transition > 30 days ago.

        Args:
            region: AWS region to scan

        Returns:
            List of stopped instance resources
        """
        orphans: list[OrphanResourceData] = []

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_instances(
                    Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
                )

                cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        state_transition_reason = instance.get(
                            "StateTransitionReason", ""
                        )

                        # Extract timestamp from state transition reason
                        # Format: "User initiated (2024-01-15 10:30:45 GMT)"
                        stopped_date = None
                        if "(" in state_transition_reason:
                            try:
                                date_str = state_transition_reason.split("(")[1].split(
                                    ")"
                                )[0]
                                stopped_date = datetime.strptime(
                                    date_str, "%Y-%m-%d %H:%M:%S %Z"
                                ).replace(tzinfo=timezone.utc)
                            except (ValueError, IndexError):
                                pass

                        # Only include if stopped > 30 days
                        if stopped_date and stopped_date < cutoff_date:
                            instance_type = instance["InstanceType"]

                            # Extract name from tags
                            name = None
                            for tag in instance.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            # Note: Stopped instances don't incur compute costs,
                            # but EBS volumes attached still cost money
                            # We'll estimate based on attached volumes
                            volume_cost = 0.0
                            for bdm in instance.get("BlockDeviceMappings", []):
                                if "Ebs" in bdm:
                                    volume_id = bdm["Ebs"].get("VolumeId")
                                    if volume_id:
                                        # Simplified: assume 8GB gp2 per volume
                                        volume_cost += 8 * self.PRICING["ebs_gp2_per_gb"]

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="ec2_instance",
                                    resource_id=instance_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=round(volume_cost, 2),
                                    resource_metadata={
                                        "instance_type": instance_type,
                                        "stopped_date": stopped_date.isoformat(),
                                        "stopped_days": (
                                            datetime.now(timezone.utc) - stopped_date
                                        ).days,
                                        "state_transition_reason": state_transition_reason,
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning stopped instances in {region}: {e}")

        return orphans

    async def scan_unused_load_balancers(
        self, region: str
    ) -> list[OrphanResourceData]:
        """
        Scan for load balancers with no healthy backends.

        Detects ALB/NLB/CLB with zero healthy target instances.

        Args:
            region: AWS region to scan

        Returns:
            List of unused load balancer resources
        """
        orphans: list[OrphanResourceData] = []

        try:
            # Scan Application/Network Load Balancers (ALBv2)
            async with self.session.client("elbv2", region_name=region) as elbv2:
                response = await elbv2.describe_load_balancers()

                for lb in response.get("LoadBalancers", []):
                    lb_arn = lb["LoadBalancerArn"]
                    lb_name = lb["LoadBalancerName"]
                    lb_type = lb["Type"]  # 'application' or 'network'

                    # Get target groups for this LB
                    tg_response = await elbv2.describe_target_groups(
                        LoadBalancerArn=lb_arn
                    )

                    has_healthy_targets = False
                    for tg in tg_response.get("TargetGroups", []):
                        tg_arn = tg["TargetGroupArn"]
                        health_response = await elbv2.describe_target_health(
                            TargetGroupArn=tg_arn
                        )

                        # Check if any target is healthy
                        for target in health_response.get(
                            "TargetHealthDescriptions", []
                        ):
                            if target["TargetHealth"]["State"] == "healthy":
                                has_healthy_targets = True
                                break

                        if has_healthy_targets:
                            break

                    # If no healthy targets, mark as orphan
                    if not has_healthy_targets:
                        cost = (
                            self.PRICING["alb"]
                            if lb_type == "application"
                            else self.PRICING["nlb"]
                        )

                        orphans.append(
                            OrphanResourceData(
                                resource_type="load_balancer",
                                resource_id=lb_arn,
                                resource_name=lb_name,
                                region=region,
                                estimated_monthly_cost=cost,
                                resource_metadata={
                                    "type": lb_type,
                                    "dns_name": lb["DNSName"],
                                    "created_at": lb["CreatedTime"].isoformat(),
                                    "scheme": lb["Scheme"],
                                },
                            )
                        )

            # Scan Classic Load Balancers
            async with self.session.client("elb", region_name=region) as elb:
                response = await elb.describe_load_balancers()

                for lb in response.get("LoadBalancerDescriptions", []):
                    lb_name = lb["LoadBalancerName"]

                    # Check instance health
                    health_response = await elb.describe_instance_health(
                        LoadBalancerName=lb_name
                    )

                    has_healthy = False
                    for instance in health_response.get("InstanceStates", []):
                        if instance["State"] == "InService":
                            has_healthy = True
                            break

                    if not has_healthy:
                        orphans.append(
                            OrphanResourceData(
                                resource_type="load_balancer",
                                resource_id=lb_name,
                                resource_name=lb_name,
                                region=region,
                                estimated_monthly_cost=self.PRICING["clb"],
                                resource_metadata={
                                    "type": "classic",
                                    "dns_name": lb["DNSName"],
                                    "created_at": lb["CreatedTime"].isoformat(),
                                    "scheme": lb["Scheme"],
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning unused load balancers in {region}: {e}")

        return orphans

    async def scan_stopped_databases(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for RDS instances stopped for more than 7 days.

        AWS automatically starts stopped RDS instances after 7 days,
        but repeated stopping indicates potential waste.

        Args:
            region: AWS region to scan

        Returns:
            List of stopped RDS instance resources
        """
        orphans: list[OrphanResourceData] = []

        try:
            async with self.session.client("rds", region_name=region) as rds:
                response = await rds.describe_db_instances()

                for db in response.get("DBInstances", []):
                    status = db["DBInstanceStatus"]

                    # RDS stopped state
                    if status == "stopped":
                        db_id = db["DBInstanceIdentifier"]
                        db_class = db["DBInstanceClass"]
                        engine = db["Engine"]
                        storage_gb = db["AllocatedStorage"]

                        # Simplified cost: storage only (compute is free when stopped)
                        # RDS storage is ~$0.115/GB/month for gp2
                        monthly_cost = storage_gb * 0.115

                        orphans.append(
                            OrphanResourceData(
                                resource_type="rds_instance",
                                resource_id=db_id,
                                resource_name=db_id,
                                region=region,
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata={
                                    "status": status,
                                    "db_class": db_class,
                                    "engine": engine,
                                    "engine_version": db.get("EngineVersion", ""),
                                    "storage_gb": storage_gb,
                                    "storage_type": db.get("StorageType", "gp2"),
                                    "multi_az": db.get("MultiAZ", False),
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning stopped databases in {region}: {e}")

        return orphans

    async def scan_unused_nat_gateways(self, region: str) -> list[OrphanResourceData]:
        """
        Scan for NAT gateways with no outbound traffic.

        Uses CloudWatch metrics to detect NAT gateways with zero BytesOutToDestination
        over the last 30 days.

        Args:
            region: AWS region to scan

        Returns:
            List of unused NAT gateway resources
        """
        orphans: list[OrphanResourceData] = []

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                async with self.session.client("cloudwatch", region_name=region) as cw:
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=30)

                    for nat_gw in response.get("NatGateways", []):
                        nat_gw_id = nat_gw["NatGatewayId"]
                        vpc_id = nat_gw.get("VpcId", "Unknown")

                        # Query CloudWatch for BytesOutToDestination metric
                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/NATGateway",
                            MetricName="BytesOutToDestination",
                            Dimensions=[{"Name": "NatGatewayId", "Value": nat_gw_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,  # 1 day
                            Statistics=["Sum"],
                        )

                        # Check if total bytes out is zero or very low
                        total_bytes = sum(
                            dp["Sum"]
                            for dp in metrics_response.get("Datapoints", [])
                        )

                        # If less than 1MB over 30 days, consider unused
                        if total_bytes < 1_000_000:
                            # Extract name from tags
                            name = None
                            for tag in nat_gw.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="nat_gateway",
                                    resource_id=nat_gw_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=self.PRICING["nat_gateway"],
                                    resource_metadata={
                                        "vpc_id": vpc_id,
                                        "subnet_id": nat_gw.get("SubnetId", "Unknown"),
                                        "created_at": nat_gw["CreateTime"].isoformat(),
                                        "bytes_out_30d": int(total_bytes),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning unused NAT gateways in {region}: {e}")

        return orphans
