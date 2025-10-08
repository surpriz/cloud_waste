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
        "gwlb": 7.50,  # Gateway Load Balancer
        # TOP 15 high-cost idle resources
        "fsx_lustre_per_gb": 0.145,  # FSx for Lustre
        "fsx_windows_per_gb": 0.13,  # FSx for Windows
        "fsx_ontap_per_gb": 0.144,  # FSx for NetApp ONTAP
        "fsx_openzfs_per_gb": 0.14,  # FSx for OpenZFS
        "neptune_db_r5_large": 0.348,  # Neptune db.r5.large (per hour) = ~$250/month
        "neptune_db_r5_xlarge": 0.696,  # Neptune db.r5.xlarge = ~$500/month
        "msk_kafka_m5_large": 0.21,  # MSK kafka.m5.large (per broker/hour) = ~$150/month
        "msk_kafka_m5_xlarge": 0.42,  # MSK kafka.m5.xlarge = ~$300/month
        "eks_cluster": 73.00,  # EKS Control Plane
        "sagemaker_ml_m5_large": 0.115,  # SageMaker ml.m5.large (per hour) = ~$83/month
        "sagemaker_ml_m5_xlarge": 0.23,  # SageMaker ml.m5.xlarge = ~$165/month
        "redshift_dc2_large": 0.25,  # Redshift dc2.large (per hour) = ~$180/month
        "redshift_dc2_xlarge": 1.00,  # Redshift dc2.xlarge = ~$720/month
        "elasticache_cache_m5_large": 0.126,  # ElastiCache cache.m5.large (per hour) = ~$90/month
        "elasticache_cache_r5_large": 0.188,  # ElastiCache cache.r5.large = ~$135/month
        "vpn_connection": 36.00,  # VPN Connection
        "transit_gateway_attachment": 36.00,  # Transit Gateway Attachment (per month)
        "opensearch_m5_large": 0.161,  # OpenSearch m5.large.search (per hour) = ~$116/month
        "opensearch_r5_large": 0.228,  # OpenSearch r5.large.search = ~$164/month
        "global_accelerator": 18.00,  # Global Accelerator (base cost)
        "kinesis_shard": 15.00,  # Kinesis shard (per month)
        "vpc_endpoint": 7.20,  # VPC Endpoint (per month)
        "documentdb_r5_large": 0.277,  # DocumentDB db.r5.large (per hour) = ~$199/month
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
        Scan for unattached AND attached-but-unused EBS volumes in a region.

        Uses CloudWatch metrics to detect:
        - Unattached volumes (status = 'available')
        - Volumes never used (never attached or no I/O activity)
        - Volumes used in the past but abandoned (no recent activity)
        - Attached volumes with no I/O activity for extended periods

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
        detect_attached_unused = detection_rules.get("detect_attached_unused", True)
        min_idle_days_attached = detection_rules.get("min_idle_days_attached", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get ALL volumes (both available and in-use)
                response = await ec2.describe_volumes()

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    volume_type = volume["VolumeType"]
                    created_at = volume["CreateTime"]
                    volume_state = volume["State"]  # 'available', 'in-use', etc.
                    attachments = volume.get("Attachments", [])

                    # Determine if volume is attached
                    is_attached = len(attachments) > 0 and volume_state == "in-use"
                    attached_instance_id = None
                    if is_attached:
                        attached_instance_id = attachments[0].get("InstanceId")

                    # Calculate volume age in days
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    # Skip if volume is too young
                    if age_days < min_age_days:
                        continue

                    # Check usage history via CloudWatch
                    usage_history = await self._check_volume_usage_history(
                        volume_id, region, created_at
                    )

                    # Determine if this volume should be flagged as orphaned
                    should_flag = False
                    orphan_type = ""

                    if not is_attached:
                        # CASE 1: Unattached volume
                        # Skip if volume was recently active (not orphaned)
                        if usage_history["usage_category"] != "recently_active":
                            should_flag = True
                            orphan_type = "unattached"
                    elif is_attached and detect_attached_unused:
                        # CASE 2: Attached volume but unused
                        # Check if there's no I/O activity for min_idle_days_attached
                        days_since_last_use = usage_history.get("days_since_last_use")

                        # Flag if never used OR idle for min_idle_days_attached
                        if usage_history["usage_category"] == "never_used" and age_days >= min_idle_days_attached:
                            should_flag = True
                            orphan_type = "attached_never_used"
                        elif days_since_last_use and days_since_last_use >= min_idle_days_attached:
                            should_flag = True
                            orphan_type = "attached_idle"

                    # Skip if should not be flagged
                    if not should_flag:
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

                    # Determine confidence level and reason based on orphan type
                    if orphan_type == "unattached":
                        # Original logic for unattached volumes
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

                    elif orphan_type == "attached_never_used":
                        # Attached to an instance but NEVER used
                        if age_days >= 60:
                            confidence = "high"
                            reason = f"Attached to {attached_instance_id} but never used in {age_days} days"
                        elif age_days >= min_idle_days_attached:
                            confidence = "medium"
                            reason = f"Attached to {attached_instance_id} but never used in {age_days} days"
                        else:
                            confidence = "low"
                            reason = f"Attached to {attached_instance_id} but no I/O detected yet ({age_days} days old)"

                    elif orphan_type == "attached_idle":
                        # Attached but idle for extended period
                        days_idle = usage_history.get("days_since_last_use", 0)
                        if days_idle >= 60:
                            confidence = "high"
                            reason = f"Attached to {attached_instance_id} but idle for {days_idle} days (was active before)"
                        elif days_idle >= min_idle_days_attached:
                            confidence = "medium"
                            reason = f"Attached to {attached_instance_id} but idle for {days_idle} days"
                        else:
                            confidence = "low"
                            reason = f"Attached to {attached_instance_id} but no recent I/O activity"

                    else:
                        # Fallback
                        confidence = "low"
                        reason = "Detected as potentially orphaned"

                    # Build metadata
                    metadata = {
                        "size_gb": size_gb,
                        "volume_type": volume_type,
                        "created_at": created_at.isoformat(),
                        "availability_zone": volume["AvailabilityZone"],
                        "encrypted": volume.get("Encrypted", False),
                        "age_days": age_days,
                        "confidence": confidence,
                        "orphan_reason": reason,
                        "orphan_type": orphan_type,  # 'unattached', 'attached_never_used', 'attached_idle'
                        "usage_history": usage_history,
                        "volume_state": volume_state,
                        "is_attached": is_attached,
                    }

                    # Add attachment info if volume is attached
                    if is_attached and attached_instance_id:
                        metadata["attached_instance_id"] = attached_instance_id
                        metadata["attachment_device"] = attachments[0].get("Device", "Unknown")
                        metadata["attachment_time"] = attachments[0].get("AttachTime").isoformat() if attachments[0].get("AttachTime") else None

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_cost, 2),
                            resource_metadata=metadata,
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
        Scan for unassigned Elastic IP addresses AND associated IPs on stopped instances.

        Detects:
        - Elastic IPs not associated with any instance or network interface
        - Elastic IPs associated to stopped EC2 instances (still charged!)
        - Elastic IPs associated to orphaned ENIs (network interfaces not attached)

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

                # Get all instances to check their state
                instances_response = await ec2.describe_instances()
                instance_states = {}
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_states[instance["InstanceId"]] = instance["State"]["Name"]

                for address in response.get("Addresses", []):
                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    association_id = address.get("AssociationId")
                    instance_id = address.get("InstanceId")
                    network_interface_id = address.get("NetworkInterfaceId")

                    # Determine orphan status
                    should_flag = False
                    orphan_type = ""

                    if not association_id:
                        # CASE 1: Not associated at all (original logic)
                        should_flag = True
                        orphan_type = "unassociated"
                    elif instance_id and instance_id in instance_states:
                        # CASE 2: Associated to an instance - check if instance is stopped
                        instance_state = instance_states[instance_id]
                        if instance_state == "stopped":
                            should_flag = True
                            orphan_type = "associated_stopped_instance"
                    elif network_interface_id and not instance_id:
                        # CASE 3: Associated to ENI but ENI not attached to instance
                        should_flag = True
                        orphan_type = "associated_orphaned_eni"

                    if not should_flag:
                        continue

                    # Extract tags
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
                    age_days = -1
                    if created_date:
                        age_days = (datetime.now(timezone.utc) - created_date).days
                        if age_days < min_age_days:
                            continue

                    # Determine confidence and reason based on orphan type
                    if orphan_type == "unassociated":
                        # Original logic for unassociated IPs
                        if created_date:
                            confidence = "high" if age_days >= confidence_threshold_days else "medium"
                            reason = f"Not associated for {age_days} days"
                        else:
                            # No creation date available
                            if min_age_days > 0:
                                continue  # Skip - can't verify age requirement
                            confidence = "low"
                            reason = "Not associated (age unknown - add 'CreatedDate' tag for tracking)"

                    elif orphan_type == "associated_stopped_instance":
                        # IP associated to stopped instance - CHARGED!
                        confidence = "high"
                        reason = f"Associated to stopped instance {instance_id} (charged $3.60/month)"

                    elif orphan_type == "associated_orphaned_eni":
                        # IP associated to ENI but ENI not attached to instance
                        confidence = "high"
                        reason = f"Associated to orphaned network interface {network_interface_id} (charged)"

                    else:
                        # Fallback
                        confidence = "low"
                        reason = "Detected as potentially orphaned"

                    # Build metadata
                    metadata = {
                        "public_ip": public_ip,
                        "domain": address.get("Domain", "vpc"),
                        "age_days": age_days,
                        "confidence": confidence,
                        "orphan_reason": reason,
                        "orphan_type": orphan_type,
                        "is_associated": bool(association_id),
                    }

                    # Add association info if available
                    if instance_id:
                        metadata["associated_instance_id"] = instance_id
                        metadata["instance_state"] = instance_states.get(instance_id, "unknown")
                    if network_interface_id:
                        metadata["network_interface_id"] = network_interface_id

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

    async def scan_orphaned_snapshots(
        self, region: str, detection_rules: dict | None = None, orphaned_volume_ids: list[str] | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for orphaned EBS snapshots in a region.

        Detects:
        - Snapshots where source volume no longer exists
        - Snapshots of volumes that are idle/orphaned (if enabled)

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules
            orphaned_volume_ids: List of volume IDs detected as orphaned/idle (optional)

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        # Get detection rules or use defaults
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        min_age_days = rules.get("min_age_days", 90)
        confidence_threshold_days = rules.get("confidence_threshold_days", 180)
        detect_idle_volume_snapshots = rules.get("detect_idle_volume_snapshots", True)
        detect_redundant_snapshots = rules.get("detect_redundant_snapshots", True)
        max_snapshots_per_volume = rules.get("max_snapshots_per_volume", 7)
        detect_unused_ami_snapshots = rules.get("detect_unused_ami_snapshots", True)
        min_ami_unused_days = rules.get("min_ami_unused_days", 180)
        enabled = rules.get("enabled", True)

        if not enabled:
            return orphans

        # Use provided orphaned volume IDs or empty list
        if orphaned_volume_ids is None:
            orphaned_volume_ids = []

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                # Get all existing volumes with their status
                volumes_response = await ec2.describe_volumes()
                volume_info = {}
                for vol in volumes_response.get("Volumes", []):
                    volume_info[vol["VolumeId"]] = {
                        "state": vol["State"],
                        "attachments": vol.get("Attachments", []),
                    }

                # Get all AMIs owned by this account (for unused AMI detection)
                amis_response = await ec2.describe_images(Owners=[account_id])
                all_amis = amis_response.get("Images", [])

                # Build AMI usage info
                ami_snapshot_ids = set()  # Snapshots used by AMIs
                unused_ami_snapshot_ids = set()  # Snapshots of unused AMIs

                if detect_unused_ami_snapshots:
                    for ami in all_amis:
                        ami_id = ami["ImageId"]
                        ami_creation_date = datetime.fromisoformat(ami["CreationDate"].replace('Z', '+00:00'))
                        ami_age_days = (datetime.now(timezone.utc) - ami_creation_date).days

                        # Extract snapshot IDs from AMI block device mappings
                        ami_snapshots = []
                        for block_device in ami.get("BlockDeviceMappings", []):
                            if "Ebs" in block_device and "SnapshotId" in block_device["Ebs"]:
                                snapshot_id = block_device["Ebs"]["SnapshotId"]
                                ami_snapshots.append(snapshot_id)
                                ami_snapshot_ids.add(snapshot_id)

                        # Check if AMI has been used to launch instances
                        if ami_age_days >= min_ami_unused_days:
                            # Check if any instances use this AMI
                            instances_with_ami = await ec2.describe_instances(
                                Filters=[{"Name": "image-id", "Values": [ami_id]}]
                            )

                            has_instances = False
                            for reservation in instances_with_ami.get("Reservations", []):
                                if len(reservation.get("Instances", [])) > 0:
                                    has_instances = True
                                    break

                            # If AMI unused, mark its snapshots as orphaned
                            if not has_instances:
                                unused_ami_snapshot_ids.update(ami_snapshots)

                # Group snapshots by volume for redundancy detection
                snapshots_by_volume = {}
                if detect_redundant_snapshots:
                    for snapshot in all_snapshots:
                        volume_id = snapshot.get("VolumeId")
                        if volume_id:
                            if volume_id not in snapshots_by_volume:
                                snapshots_by_volume[volume_id] = []
                            snapshots_by_volume[volume_id].append(snapshot)

                    # Sort snapshots by creation date (newest first) for each volume
                    for volume_id in snapshots_by_volume:
                        snapshots_by_volume[volume_id].sort(
                            key=lambda s: s["StartTime"], reverse=True
                        )

                cutoff_date = datetime.now(timezone.utc) - timedelta(days=min_age_days)

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    volume_id = snapshot.get("VolumeId")
                    start_time = snapshot["StartTime"]

                    # Check if snapshot is old enough and volume doesn't exist
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    # Determine orphan status
                    should_flag = False
                    orphan_type = ""
                    source_volume_status = "unknown"
                    redundant_info = None
                    ami_info = None

                    # CASE 1: Volume no longer exists (original logic)
                    if volume_id not in volume_info and age_days >= min_age_days:
                        should_flag = True
                        orphan_type = "volume_deleted"
                        source_volume_status = "deleted"

                    # CASE 2: Snapshot of idle/orphaned volume
                    elif detect_idle_volume_snapshots and volume_id in orphaned_volume_ids:
                        should_flag = True
                        orphan_type = "idle_volume_snapshot"
                        if volume_id in volume_info:
                            vol_state = volume_info[volume_id]["state"]
                            is_attached = len(volume_info[volume_id]["attachments"]) > 0
                            if not is_attached:
                                source_volume_status = "unattached"
                            else:
                                source_volume_status = "attached_idle"
                        else:
                            source_volume_status = "deleted"

                    # CASE 3: Redundant snapshot (too many snapshots for same volume)
                    elif detect_redundant_snapshots and volume_id and volume_id in snapshots_by_volume:
                        volume_snapshots = snapshots_by_volume[volume_id]
                        if len(volume_snapshots) > max_snapshots_per_volume:
                            # Find position of this snapshot in the sorted list
                            snapshot_index = next(
                                (i for i, s in enumerate(volume_snapshots) if s["SnapshotId"] == snapshot_id),
                                None
                            )
                            # Flag snapshots beyond the retention limit
                            if snapshot_index is not None and snapshot_index >= max_snapshots_per_volume:
                                should_flag = True
                                orphan_type = "redundant_snapshot"
                                redundant_info = {
                                    "total_snapshots": len(volume_snapshots),
                                    "retention_limit": max_snapshots_per_volume,
                                    "position": snapshot_index + 1,
                                }
                                source_volume_status = "exists" if volume_id in volume_info else "deleted"

                    # CASE 4: Snapshot of unused AMI
                    elif detect_unused_ami_snapshots and snapshot_id in unused_ami_snapshot_ids:
                        should_flag = True
                        orphan_type = "unused_ami_snapshot"
                        # Find the AMI that uses this snapshot
                        associated_ami = None
                        for ami in all_amis:
                            for block_device in ami.get("BlockDeviceMappings", []):
                                if block_device.get("Ebs", {}).get("SnapshotId") == snapshot_id:
                                    associated_ami = ami["ImageId"]
                                    break
                            if associated_ami:
                                break
                        ami_info = {
                            "ami_id": associated_ami,
                            "ami_unused": True,
                        }
                        source_volume_status = "ami_snapshot"

                    if not should_flag:
                        continue

                    # Continue with orphan processing
                    if should_flag:
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                        # Determine confidence level based on orphan type and age
                        if orphan_type == "volume_deleted":
                            # Original logic for deleted volumes
                            if age_days >= confidence_threshold_days:
                                confidence = "high"
                                reason = f"Snapshot {age_days} days old with deleted source volume (safe to delete)"
                            elif age_days >= min_age_days * 2:
                                confidence = "high"
                                reason = f"Snapshot {age_days} days old with deleted source volume"
                            elif age_days >= min_age_days:
                                confidence = "medium"
                                reason = f"Snapshot {age_days} days old with deleted source volume"
                            else:
                                confidence = "low"
                                reason = f"Recent snapshot ({age_days} days) with deleted source volume (verify before deleting)"

                        elif orphan_type == "idle_volume_snapshot":
                            # Snapshot of idle/orphaned volume
                            if source_volume_status == "unattached":
                                confidence = "high"
                                reason = f"Snapshot of unattached volume {volume_id} (volume is orphaned)"
                            elif source_volume_status == "attached_idle":
                                confidence = "medium"
                                reason = f"Snapshot of idle volume {volume_id} (volume has no I/O activity)"
                            else:
                                confidence = "medium"
                                reason = f"Snapshot of orphaned volume {volume_id}"

                        elif orphan_type == "redundant_snapshot":
                            # Redundant snapshot (exceeds retention limit)
                            total = redundant_info["total_snapshots"]
                            limit = redundant_info["retention_limit"]
                            position = redundant_info["position"]
                            confidence = "high"
                            reason = f"Redundant snapshot #{position} of {total} (retention limit: {limit})"

                        elif orphan_type == "unused_ami_snapshot":
                            # Snapshot of unused AMI
                            ami_id = ami_info.get("ami_id", "unknown")
                            confidence = "high"
                            reason = f"Snapshot of unused AMI {ami_id} (AMI not used for 180+ days)"

                        else:
                            # Fallback
                            confidence = "low"
                            reason = "Detected as potentially orphaned"

                        # Extract name/description
                        description = snapshot.get("Description", "")
                        name = None
                        for tag in snapshot.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        # Build metadata
                        metadata = {
                            "size_gb": size_gb,
                            "volume_id": volume_id or "Unknown",
                            "created_at": start_time.isoformat(),
                            "age_days": age_days,
                            "description": description,
                            "encrypted": snapshot.get("Encrypted", False),
                            "confidence": confidence,
                            "orphan_reason": reason,
                            "orphan_type": orphan_type,  # 'volume_deleted', 'idle_volume_snapshot', 'redundant_snapshot', 'unused_ami_snapshot'
                            "source_volume_status": source_volume_status,  # 'deleted', 'unattached', 'attached_idle', 'exists', 'ami_snapshot'
                        }

                        # Add redundant snapshot info if applicable
                        if redundant_info:
                            metadata["redundant_info"] = redundant_info

                        # Add AMI info if applicable
                        if ami_info:
                            metadata["ami_info"] = ami_info

                        orphans.append(
                            OrphanResourceData(
                                resource_type="ebs_snapshot",
                                resource_id=snapshot_id,
                                resource_name=name or description,
                                region=region,
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata=metadata,
                            )
                        )

        except ClientError as e:
            print(f"Error scanning orphaned snapshots in {region}: {e}")

        return orphans

    async def scan_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for EC2 instances stopped for extended periods.

        Detects instances in 'stopped' state with state transition > threshold.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of stopped instance resources
        """
        orphans: list[OrphanResourceData] = []

        # Get detection rules or use defaults
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        min_stopped_days = rules.get("min_stopped_days", 30)
        confidence_threshold_days = rules.get("confidence_threshold_days", 60)
        enabled = rules.get("enabled", True)

        if not enabled:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_instances(
                    Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
                )

                cutoff_date = datetime.now(timezone.utc) - timedelta(
                    days=min_stopped_days
                )

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

                        # Calculate stopped days
                        stopped_days = 0
                        if stopped_date:
                            stopped_days = (
                                datetime.now(timezone.utc) - stopped_date
                            ).days

                        # Only include if stopped >= min_stopped_days
                        if stopped_date and stopped_days >= min_stopped_days:
                            instance_type = instance["InstanceType"]

                            # Extract name from tags
                            name = None
                            for tag in instance.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            # Determine confidence level based on stopped days
                            if stopped_days >= confidence_threshold_days:
                                confidence = "high"
                                reason = f"EC2 instance stopped for {stopped_days} days (high confidence)"
                            else:
                                confidence = "low"
                                reason = f"EC2 instance stopped for {stopped_days} days (low confidence)"

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
                                        "state": "stopped",
                                        "stopped_date": stopped_date.isoformat(),
                                        "stopped_days": stopped_days,
                                        "state_transition_reason": state_transition_reason,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "orphan_type": "stopped",
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning stopped instances in {region}: {e}")

        return orphans

    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for EC2 instances that are running but have very low utilization.

        Detects instances in 'running' state with:
        - Average CPU utilization < threshold (default 5%)
        - Network traffic < threshold (default 1MB over 30 days)

        Uses CloudWatch metrics to assess actual resource usage.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of idle running instance resources
        """
        orphans: list[OrphanResourceData] = []

        # Get detection rules or use defaults
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_idle_running = rules.get("detect_idle_running", True)
        cpu_threshold = rules.get("cpu_threshold_percent", 5.0)
        network_threshold = rules.get("network_threshold_bytes", 1_000_000)
        min_idle_days = rules.get("min_idle_days", 7)
        idle_confidence_threshold = rules.get("idle_confidence_threshold_days", 30)
        enabled = rules.get("enabled", True)

        print(f"🔍 [DEBUG] scan_idle_running_instances called for region: {region}")
        print(f"🔍 [DEBUG] Rules: enabled={enabled}, detect_idle_running={detect_idle_running}, min_idle_days={min_idle_days}")

        if not enabled or not detect_idle_running:
            print(f"🔍 [DEBUG] Skipping idle running detection (enabled={enabled}, detect_idle_running={detect_idle_running})")
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    # Get all running instances
                    response = await ec2.describe_instances(
                        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
                    )

                    print(f"🔍 [DEBUG] EC2 API response received for region {region}")
                    total_instances = sum(len(r.get("Instances", [])) for r in response.get("Reservations", []))
                    print(f"🔍 [DEBUG] Found {total_instances} running instances in {region}")

                    now = datetime.now(timezone.utc)
                    # Lookback period: max(min_idle_days, 30) to ensure enough data
                    # TEST MODE: If min_idle_days = 0, use shorter lookback (2 hours)
                    if min_idle_days == 0:
                        lookback_days = 0
                        start_time = now - timedelta(hours=2)  # 2 hours for immediate testing
                    else:
                        lookback_days = max(min_idle_days, 30)
                        start_time = now - timedelta(days=lookback_days)

                    for reservation in response.get("Reservations", []):
                        for instance in reservation.get("Instances", []):
                            instance_id = instance["InstanceId"]
                            instance_type = instance["InstanceType"]
                            launch_time = instance["LaunchTime"]

                            # Calculate instance age
                            instance_age_days = (now - launch_time).days

                            # Skip instances younger than min_idle_days
                            if instance_age_days < min_idle_days:
                                continue

                            # Extract name from tags
                            name = None
                            for tag in instance.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            # Query CloudWatch for CPU utilization (average over lookback period)
                            try:
                                # TEST MODE: Use shorter period (5 min) if min_idle_days = 0
                                period = 300 if min_idle_days == 0 else 86400  # 5 min or 1 day

                                cpu_response = await cw.get_metric_statistics(
                                    Namespace="AWS/EC2",
                                    MetricName="CPUUtilization",
                                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=period,
                                    Statistics=["Average"],
                                )

                                # Calculate average CPU over entire period
                                cpu_datapoints = cpu_response.get("Datapoints", [])
                                if not cpu_datapoints:
                                    # TEST MODE: If min_idle_days = 0, accept instances without metrics (assume idle)
                                    if min_idle_days == 0:
                                        avg_cpu = 0.0  # Assume idle for testing
                                    else:
                                        # No CPU data available - skip
                                        continue
                                else:
                                    avg_cpu = sum(dp["Average"] for dp in cpu_datapoints) / len(cpu_datapoints)

                            except Exception as e:
                                print(f"Error fetching CPU metrics for {instance_id}: {e}")
                                continue

                            # Query CloudWatch for Network traffic
                            try:
                                network_in_response = await cw.get_metric_statistics(
                                    Namespace="AWS/EC2",
                                    MetricName="NetworkIn",
                                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=period,
                                    Statistics=["Sum"],
                                )

                                network_out_response = await cw.get_metric_statistics(
                                    Namespace="AWS/EC2",
                                    MetricName="NetworkOut",
                                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=period,
                                    Statistics=["Sum"],
                                )

                                # Sum all network traffic
                                network_in = sum(
                                    dp["Sum"] for dp in network_in_response.get("Datapoints", [])
                                )
                                network_out = sum(
                                    dp["Sum"] for dp in network_out_response.get("Datapoints", [])
                                )
                                total_network = network_in + network_out

                                # TEST MODE: If no network data and min_idle_days = 0, assume idle
                                if total_network == 0 and min_idle_days == 0 and not network_in_response.get("Datapoints"):
                                    total_network = 0  # Assume idle for testing

                            except Exception as e:
                                print(f"Error fetching network metrics for {instance_id}: {e}")
                                # TEST MODE: If min_idle_days = 0, assume idle (no network)
                                if min_idle_days == 0:
                                    total_network = 0  # Assume idle for testing
                                else:
                                    # If we can't get network data, exclude from detection
                                    total_network = network_threshold + 1

                            # Determine if instance is idle based on thresholds
                            is_cpu_idle = avg_cpu < cpu_threshold
                            is_network_idle = total_network < network_threshold

                            if is_cpu_idle and is_network_idle:
                                # Instance is idle - determine confidence based on age
                                # Format lookback period message
                                if min_idle_days == 0:
                                    lookback_msg = "2 hours"
                                else:
                                    lookback_msg = f"{lookback_days} days"

                                if instance_age_days >= idle_confidence_threshold:
                                    confidence = "high"
                                    reason = f"Instance running with {avg_cpu:.1f}% avg CPU and {total_network / 1_000_000:.2f}MB network traffic over {lookback_msg} (high confidence)"
                                elif min_idle_days > 0 and instance_age_days >= min_idle_days * 2:
                                    confidence = "medium"
                                    reason = f"Instance running with {avg_cpu:.1f}% avg CPU and {total_network / 1_000_000:.2f}MB network traffic over {lookback_msg} (medium confidence)"
                                else:
                                    confidence = "low"
                                    reason = f"Instance running with {avg_cpu:.1f}% avg CPU and {total_network / 1_000_000:.2f}MB network traffic over {lookback_msg} (low confidence)"

                                # Calculate estimated monthly cost based on instance type
                                # Simplified pricing - you can enhance this with actual pricing data
                                estimated_cost = self._estimate_ec2_instance_cost(instance_type)

                                print(f"✅ [DEBUG] Found idle running instance: {instance_id} ({name or 'unnamed'}) - CPU: {avg_cpu:.1f}%, Network: {total_network}B, Cost: ${estimated_cost}")

                                orphans.append(
                                    OrphanResourceData(
                                        resource_type="ec2_instance",
                                        resource_id=instance_id,
                                        resource_name=name,
                                        region=region,
                                        estimated_monthly_cost=estimated_cost,
                                        resource_metadata={
                                            "instance_type": instance_type,
                                            "state": "running",
                                            "launch_time": launch_time.isoformat(),
                                            "instance_age_days": instance_age_days,
                                            "avg_cpu_percent": round(avg_cpu, 2),
                                            "total_network_bytes": int(total_network),
                                            "lookback_days": lookback_days,
                                            "confidence": confidence,
                                            "orphan_reason": reason,
                                            "orphan_type": "idle_running",
                                        },
                                    )
                                )

        except ClientError as e:
            print(f"❌ [ERROR] Error scanning idle running instances in {region}: {e}")
        except Exception as e:
            print(f"❌ [ERROR] Unexpected error in scan_idle_running_instances for {region}: {type(e).__name__}: {e}")

        print(f"🔍 [DEBUG] scan_idle_running_instances completed for {region}: Found {len(orphans)} idle instances")
        return orphans

    def _estimate_ec2_instance_cost(self, instance_type: str) -> float:
        """
        Estimate monthly cost for EC2 instance type.

        Simplified pricing estimation. For production, use AWS Pricing API.

        Args:
            instance_type: EC2 instance type (e.g., "t2.micro", "m5.large")

        Returns:
            Estimated monthly cost in USD
        """
        # Simplified pricing map (us-east-1, on-demand, Linux)
        # Format: instance_type -> hourly_cost
        pricing_map = {
            # T2 instances (burstable)
            "t2.nano": 0.0058,
            "t2.micro": 0.0116,
            "t2.small": 0.023,
            "t2.medium": 0.0464,
            "t2.large": 0.0928,
            "t2.xlarge": 0.1856,
            "t2.2xlarge": 0.3712,
            # T3 instances (burstable)
            "t3.nano": 0.0052,
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "t3.large": 0.0832,
            "t3.xlarge": 0.1664,
            "t3.2xlarge": 0.3328,
            # M5 instances (general purpose)
            "m5.large": 0.096,
            "m5.xlarge": 0.192,
            "m5.2xlarge": 0.384,
            "m5.4xlarge": 0.768,
            "m5.8xlarge": 1.536,
            "m5.12xlarge": 2.304,
            "m5.16xlarge": 3.072,
            "m5.24xlarge": 4.608,
            # C5 instances (compute optimized)
            "c5.large": 0.085,
            "c5.xlarge": 0.17,
            "c5.2xlarge": 0.34,
            "c5.4xlarge": 0.68,
            "c5.9xlarge": 1.53,
            "c5.12xlarge": 2.04,
            "c5.18xlarge": 3.06,
            "c5.24xlarge": 4.08,
            # R5 instances (memory optimized)
            "r5.large": 0.126,
            "r5.xlarge": 0.252,
            "r5.2xlarge": 0.504,
            "r5.4xlarge": 1.008,
            "r5.8xlarge": 2.016,
            "r5.12xlarge": 3.024,
            "r5.16xlarge": 4.032,
            "r5.24xlarge": 6.048,
        }

        hourly_cost = pricing_map.get(instance_type, 0.05)  # Default fallback
        monthly_cost = hourly_cost * 730  # 730 hours per month average

        return round(monthly_cost, 2)

    async def scan_unused_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for load balancers with no healthy backends, no listeners, or no traffic.

        Detects ALB/NLB/CLB/GWLB with multiple orphan scenarios:
        1. Zero healthy target instances
        2. No listeners configured (unusable LB)
        3. Zero requests/traffic (CloudWatch metrics)
        4. Critical: Abandoned for 90+ days with zero backends

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of unused load balancer resources
        """
        orphans: list[OrphanResourceData] = []

        # Get configuration from detection_rules or use defaults
        from app.models.detection_rule import DEFAULT_DETECTION_RULES
        rules = detection_rules or DEFAULT_DETECTION_RULES.get("load_balancer", {})

        min_age_days = rules.get("min_age_days", 7)
        confidence_threshold_days = rules.get("confidence_threshold_days", 30)
        critical_age_days = rules.get("critical_age_days", 90)
        detect_no_listeners = rules.get("detect_no_listeners", True)
        detect_zero_requests = rules.get("detect_zero_requests", True)
        min_requests_30d = rules.get("min_requests_30d", 100)
        detect_no_target_groups = rules.get("detect_no_target_groups", True)
        detect_never_used = rules.get("detect_never_used", True)
        never_used_min_age_days = rules.get("never_used_min_age_days", 30)
        detect_unhealthy_long_term = rules.get("detect_unhealthy_long_term", True)
        unhealthy_long_term_days = rules.get("unhealthy_long_term_days", 90)
        detect_sg_blocks_traffic = rules.get("detect_sg_blocks_traffic", True)

        try:
            # Scan Application/Network/Gateway Load Balancers (ELBv2)
            async with self.session.client("elbv2", region_name=region) as elbv2:
                response = await elbv2.describe_load_balancers()

                async with self.session.client("cloudwatch", region_name=region) as cloudwatch:
                    for lb in response.get("LoadBalancers", []):
                        lb_arn = lb["LoadBalancerArn"]
                        lb_name = lb["LoadBalancerName"]
                        lb_type = lb["Type"]  # 'application', 'network', or 'gateway'
                        created_at = lb["CreatedTime"]
                        age_days = (datetime.now(created_at.tzinfo) - created_at).days

                        # Skip resources younger than min_age_days
                        if age_days < min_age_days:
                            continue

                        # Get listeners count
                        listeners_response = await elbv2.describe_listeners(
                            LoadBalancerArn=lb_arn
                        )
                        listener_count = len(listeners_response.get("Listeners", []))

                        # Get target groups for this LB
                        tg_response = await elbv2.describe_target_groups(
                            LoadBalancerArn=lb_arn
                        )

                        target_groups = tg_response.get("TargetGroups", [])
                        target_group_count = len(target_groups)

                        healthy_target_count = 0
                        total_target_count = 0
                        unhealthy_since_days = None  # Track how long unhealthy

                        for tg in target_groups:
                            tg_arn = tg["TargetGroupArn"]
                            health_response = await elbv2.describe_target_health(
                                TargetGroupArn=tg_arn
                            )

                            targets = health_response.get("TargetHealthDescriptions", [])
                            total_target_count += len(targets)

                            for target in targets:
                                if target["TargetHealth"]["State"] == "healthy":
                                    healthy_target_count += 1

                        # Get security groups to check if traffic is blocked
                        security_groups = lb.get("SecurityGroups", [])
                        sg_blocks_traffic = False

                        if detect_sg_blocks_traffic and security_groups:
                            async with self.session.client("ec2", region_name=region) as ec2:
                                try:
                                    sg_response = await ec2.describe_security_groups(
                                        GroupIds=security_groups
                                    )
                                    # Check if ANY security group has ingress rules
                                    has_ingress = False
                                    for sg in sg_response.get("SecurityGroups", []):
                                        if sg.get("IpPermissions"):
                                            has_ingress = True
                                            break
                                    sg_blocks_traffic = not has_ingress
                                except Exception as e:
                                    print(f"Warning: Could not check security groups for {lb_name}: {e}")

                        # Determine if orphaned and why
                        is_orphaned = False
                        orphan_type = None
                        orphan_reasons = []

                        # Scenario 1: No listeners configured (LB is unusable)
                        if detect_no_listeners and listener_count == 0:
                            is_orphaned = True
                            orphan_type = "no_listeners"
                            orphan_reasons.append("No listeners configured")

                        # Scenario 4: No target groups (LB has no backends configured)
                        elif detect_no_target_groups and target_group_count == 0:
                            is_orphaned = True
                            orphan_type = "no_target_groups"
                            orphan_reasons.append("No target groups attached")

                        # Scenario 2: Zero healthy targets
                        elif healthy_target_count == 0 and total_target_count == 0:
                            is_orphaned = True
                            orphan_type = "no_healthy_targets"
                            orphan_reasons.append("No healthy backend targets")

                        # Scenario 6: Unhealthy long-term (all targets unhealthy for 90+ days)
                        elif detect_unhealthy_long_term and healthy_target_count == 0 and total_target_count > 0 and age_days >= unhealthy_long_term_days:
                            is_orphaned = True
                            orphan_type = "unhealthy_long_term"
                            orphan_reasons.append(f"All {total_target_count} targets unhealthy for {age_days}+ days")

                        # Scenario 3 & 5: Check CloudWatch metrics for traffic (ALB/NLB)
                        total_requests = None
                        metric_name = None

                        if lb_type == "application":
                            metric_name = "RequestCount"
                        elif lb_type == "network":
                            metric_name = "ActiveFlowCount"

                        if metric_name and (detect_zero_requests or detect_never_used):
                            try:
                                end_time = datetime.now(timezone.utc)
                                start_time = end_time - timedelta(days=30)

                                metrics_response = await cloudwatch.get_metric_statistics(
                                    Namespace="AWS/ApplicationELB" if lb_type == "application" else "AWS/NetworkELB",
                                    MetricName=metric_name,
                                    Dimensions=[
                                        {"Name": "LoadBalancer", "Value": lb_arn.split(":")[-1]}
                                    ],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=2592000,  # 30 days in seconds
                                    Statistics=["Sum"],
                                )

                                datapoints = metrics_response.get("Datapoints", [])
                                total_requests = sum(dp.get("Sum", 0) for dp in datapoints)

                                # Scenario 3: Low traffic on already orphaned LB
                                if detect_zero_requests and is_orphaned and total_requests < min_requests_30d:
                                    orphan_reasons.append(f"Very low traffic: {int(total_requests)} {metric_name} in 30 days")

                                # Scenario 5: Never used since creation (>30 days)
                                if detect_never_used and not is_orphaned and total_requests == 0 and age_days >= never_used_min_age_days:
                                    is_orphaned = True
                                    orphan_type = "never_used"
                                    orphan_reasons.append(f"Never received any traffic since creation ({age_days} days ago)")

                            except Exception as e:
                                print(f"Warning: Could not fetch CloudWatch metrics for {lb_name}: {e}")

                        # Scenario 7: Security group blocks all traffic
                        if sg_blocks_traffic:
                            if not is_orphaned:
                                is_orphaned = True
                                orphan_type = "sg_blocks_traffic"
                                orphan_reasons.append("Security group blocks all inbound traffic (0 ingress rules)")
                            else:
                                orphan_reasons.append("Security group blocks all inbound traffic")

                        if is_orphaned:
                            # Calculate confidence level
                            if age_days >= critical_age_days and healthy_target_count == 0:
                                confidence = "critical"
                            elif age_days >= confidence_threshold_days:
                                confidence = "high"
                            elif age_days >= min_age_days:
                                confidence = "medium"
                            else:
                                confidence = "low"

                            # Calculate cost
                            if lb_type == "application":
                                cost = self.PRICING["alb"]
                            elif lb_type == "network":
                                cost = self.PRICING["nlb"]
                            else:  # gateway
                                cost = self.PRICING["gwlb"]

                            # Calculate wasted amount
                            wasted_amount = round((age_days / 30) * cost, 2)

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="load_balancer",
                                    resource_id=lb_arn,
                                    resource_name=lb_name,
                                    region=region,
                                    estimated_monthly_cost=cost,
                                    resource_metadata={
                                        "type": lb_type,
                                        "type_full": {
                                            "application": "Application Load Balancer (ALB)",
                                            "network": "Network Load Balancer (NLB)",
                                            "gateway": "Gateway Load Balancer (GWLB)"
                                        }.get(lb_type, lb_type.upper()),
                                        "dns_name": lb.get("DNSName", "N/A"),
                                        "created_at": created_at.isoformat(),
                                        "scheme": lb.get("Scheme", "N/A"),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_type": orphan_type,
                                        "orphan_reason": "; ".join(orphan_reasons),
                                        "orphan_reasons": orphan_reasons,
                                        "listener_count": listener_count,
                                        "healthy_target_count": healthy_target_count,
                                        "total_target_count": total_target_count,
                                        "wasted_amount": wasted_amount,
                                    },
                                )
                            )

            # Scan Classic Load Balancers (ELB)
            async with self.session.client("elb", region_name=region) as elb:
                response = await elb.describe_load_balancers()

                async with self.session.client("cloudwatch", region_name=region) as cloudwatch:
                    for lb in response.get("LoadBalancerDescriptions", []):
                        lb_name = lb["LoadBalancerName"]
                        created_at = lb["CreatedTime"]
                        age_days = (datetime.now(created_at.tzinfo) - created_at).days

                        # Skip resources younger than min_age_days
                        if age_days < min_age_days:
                            continue

                        # Get listener count
                        listener_count = len(lb.get("ListenerDescriptions", []))

                        # Check instance health
                        health_response = await elb.describe_instance_health(
                            LoadBalancerName=lb_name
                        )

                        instances = health_response.get("InstanceStates", [])
                        total_target_count = len(instances)
                        healthy_target_count = sum(1 for inst in instances if inst["State"] == "InService")

                        # Get security groups to check if traffic is blocked
                        security_groups = lb.get("SecurityGroups", [])
                        sg_blocks_traffic = False

                        if detect_sg_blocks_traffic and security_groups:
                            async with self.session.client("ec2", region_name=region) as ec2:
                                try:
                                    sg_response = await ec2.describe_security_groups(
                                        GroupIds=security_groups
                                    )
                                    # Check if ANY security group has ingress rules
                                    has_ingress = False
                                    for sg in sg_response.get("SecurityGroups", []):
                                        if sg.get("IpPermissions"):
                                            has_ingress = True
                                            break
                                    sg_blocks_traffic = not has_ingress
                                except Exception as e:
                                    print(f"Warning: Could not check security groups for {lb_name}: {e}")

                        # Determine if orphaned and why
                        is_orphaned = False
                        orphan_type = None
                        orphan_reasons = []

                        # Scenario 1: No listeners configured
                        if detect_no_listeners and listener_count == 0:
                            is_orphaned = True
                            orphan_type = "no_listeners"
                            orphan_reasons.append("No listeners configured")

                        # Scenario 2: No healthy instances (0 instances)
                        elif healthy_target_count == 0 and total_target_count == 0:
                            is_orphaned = True
                            orphan_type = "no_healthy_targets"
                            orphan_reasons.append("No healthy backend instances")

                        # Scenario 6: Unhealthy long-term (all instances unhealthy for 90+ days)
                        elif detect_unhealthy_long_term and healthy_target_count == 0 and total_target_count > 0 and age_days >= unhealthy_long_term_days:
                            is_orphaned = True
                            orphan_type = "unhealthy_long_term"
                            orphan_reasons.append(f"All {total_target_count} instances unhealthy for {age_days}+ days")

                        # Scenario 3 & 5: Check CloudWatch metrics for requests
                        total_requests = None

                        if detect_zero_requests or detect_never_used:
                            try:
                                end_time = datetime.now(timezone.utc)
                                start_time = end_time - timedelta(days=30)

                                metrics_response = await cloudwatch.get_metric_statistics(
                                    Namespace="AWS/ELB",
                                    MetricName="RequestCount",
                                    Dimensions=[
                                        {"Name": "LoadBalancerName", "Value": lb_name}
                                    ],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=2592000,  # 30 days in seconds
                                    Statistics=["Sum"],
                                )

                                datapoints = metrics_response.get("Datapoints", [])
                                total_requests = sum(dp.get("Sum", 0) for dp in datapoints)

                                # Scenario 3: Low traffic on already orphaned LB
                                if detect_zero_requests and is_orphaned and total_requests < min_requests_30d:
                                    orphan_reasons.append(f"Very low traffic: {int(total_requests)} requests in 30 days")

                                # Scenario 5: Never used since creation (>30 days)
                                if detect_never_used and not is_orphaned and total_requests == 0 and age_days >= never_used_min_age_days:
                                    is_orphaned = True
                                    orphan_type = "never_used"
                                    orphan_reasons.append(f"Never received any traffic since creation ({age_days} days ago)")

                            except Exception as e:
                                print(f"Warning: Could not fetch CloudWatch metrics for {lb_name}: {e}")

                        # Scenario 7: Security group blocks all traffic
                        if sg_blocks_traffic:
                            if not is_orphaned:
                                is_orphaned = True
                                orphan_type = "sg_blocks_traffic"
                                orphan_reasons.append("Security group blocks all inbound traffic (0 ingress rules)")
                            else:
                                orphan_reasons.append("Security group blocks all inbound traffic")

                        if is_orphaned:
                            # Calculate confidence level
                            if age_days >= critical_age_days and healthy_target_count == 0:
                                confidence = "critical"
                            elif age_days >= confidence_threshold_days:
                                confidence = "high"
                            elif age_days >= min_age_days:
                                confidence = "medium"
                            else:
                                confidence = "low"

                            cost = self.PRICING["clb"]
                            wasted_amount = round((age_days / 30) * cost, 2)

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="load_balancer",
                                    resource_id=lb_name,
                                    resource_name=lb_name,
                                    region=region,
                                    estimated_monthly_cost=cost,
                                    resource_metadata={
                                        "type": "classic",
                                        "type_full": "Classic Load Balancer (CLB)",
                                        "dns_name": lb.get("DNSName", "N/A"),
                                        "created_at": created_at.isoformat(),
                                        "scheme": lb.get("Scheme", "N/A"),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_type": orphan_type,
                                        "orphan_reason": "; ".join(orphan_reasons),
                                        "orphan_reasons": orphan_reasons,
                                        "listener_count": listener_count,
                                        "healthy_target_count": healthy_target_count,
                                        "total_target_count": total_target_count,
                                        "wasted_amount": wasted_amount,
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

    async def scan_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for NAT gateways with no outbound traffic or misconfigured routing.

        Detection scenarios:
        1. Zero or very low traffic (BytesOutToDestination < threshold)
        2. No route table references (orphaned)
        3. Route tables not associated with any subnet
        4. VPC without Internet Gateway (broken config)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of unused NAT gateway resources
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("nat_gateway", {})

        # Check if detection is enabled
        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 7)
        max_bytes_30d = detection_rules.get("max_bytes_30d", 1_000_000)
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 30)
        critical_age_days = detection_rules.get("critical_age_days", 90)
        detect_no_routes = detection_rules.get("detect_no_routes", True)
        detect_no_igw = detection_rules.get("detect_no_igw", True)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all NAT Gateways
                nat_response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                # Get all route tables for routing analysis
                route_tables_response = await ec2.describe_route_tables()
                all_route_tables = route_tables_response.get("RouteTables", [])

                # Get all Internet Gateways for VPC validation
                igw_response = await ec2.describe_internet_gateways()
                vpcs_with_igw = set()
                for igw in igw_response.get("InternetGateways", []):
                    for attachment in igw.get("Attachments", []):
                        if attachment.get("State") == "available":
                            vpcs_with_igw.add(attachment.get("VpcId"))

                async with self.session.client("cloudwatch", region_name=region) as cw:
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=30)

                    for nat_gw in nat_response.get("NatGateways", []):
                        nat_gw_id = nat_gw["NatGatewayId"]
                        vpc_id = nat_gw.get("VpcId", "Unknown")
                        created_at = nat_gw["CreateTime"]
                        age_days = (end_time - created_at).days

                        # Skip if NAT Gateway is too young
                        if age_days < min_age_days:
                            continue

                        # Analyze routing configuration
                        route_tables_with_nat = []
                        associated_subnets_count = 0

                        for rt in all_route_tables:
                            if rt.get("VpcId") != vpc_id:
                                continue

                            # Check if this route table references our NAT Gateway
                            has_nat_route = False
                            for route in rt.get("Routes", []):
                                if route.get("NatGatewayId") == nat_gw_id:
                                    has_nat_route = True
                                    break

                            if has_nat_route:
                                route_tables_with_nat.append(rt)
                                # Count associated subnets
                                associated_subnets_count += len(rt.get("Associations", []))

                        has_routes = len(route_tables_with_nat) > 0
                        has_associated_subnets = associated_subnets_count > 0
                        vpc_has_igw = vpc_id in vpcs_with_igw

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

                        total_bytes = sum(
                            dp["Sum"]
                            for dp in metrics_response.get("Datapoints", [])
                        )

                        # Determine if orphaned based on multiple criteria
                        is_orphaned = False
                        orphan_reasons = []
                        orphan_type = None

                        # Scenario 1: No route tables reference this NAT Gateway
                        if detect_no_routes and not has_routes:
                            is_orphaned = True
                            orphan_type = "no_routes"
                            orphan_reasons.append("Not referenced in any route table")

                        # Scenario 2: Has routes but none are associated with subnets
                        elif has_routes and not has_associated_subnets:
                            is_orphaned = True
                            orphan_type = "routes_not_associated"
                            orphan_reasons.append(
                                f"Referenced in {len(route_tables_with_nat)} route table(s) but none associated with subnets"
                            )

                        # Scenario 3: VPC has no Internet Gateway (broken config)
                        if detect_no_igw and not vpc_has_igw:
                            is_orphaned = True
                            if not orphan_type:
                                orphan_type = "no_igw"
                            orphan_reasons.append(
                                "VPC has no Internet Gateway (NAT Gateway cannot route to internet)"
                            )

                        # Scenario 4: Low/zero traffic
                        if total_bytes < max_bytes_30d:
                            if not is_orphaned:
                                orphan_type = "low_traffic"
                            orphan_reasons.append(
                                f"Only {(total_bytes / 1024):.2f} KB traffic in 30 days"
                            )
                            is_orphaned = True

                        # Skip if not orphaned
                        if not is_orphaned:
                            continue

                        # Calculate confidence level (enhanced with critical)
                        if age_days >= critical_age_days and total_bytes == 0:
                            confidence = "critical"
                            wasted_amount = round((age_days / 30) * self.PRICING["nat_gateway"], 2)
                            orphan_reason = f"CRITICAL: Abandoned for {age_days} days with zero traffic (${wasted_amount} wasted)"
                        elif age_days >= confidence_threshold_days:
                            confidence = "high"
                            orphan_reason = f"Unused for {age_days} days ({'; '.join(orphan_reasons)})"
                        elif age_days >= min_age_days:
                            confidence = "medium"
                            orphan_reason = f"Likely unused for {age_days} days ({'; '.join(orphan_reasons)})"
                        else:
                            confidence = "low"
                            orphan_reason = f"Recently created ({age_days} days) but {'; '.join(orphan_reasons)}"

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
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "bytes_out_30d": int(total_bytes),
                                    "confidence": confidence,
                                    "orphan_reason": orphan_reason,
                                    "orphan_type": orphan_type,
                                    # Enhanced metadata
                                    "has_routes": has_routes,
                                    "route_tables_count": len(route_tables_with_nat),
                                    "associated_subnets_count": associated_subnets_count,
                                    "vpc_has_igw": vpc_has_igw,
                                    "orphan_reasons": orphan_reasons,
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning unused NAT gateways in {region}: {e}")

        return orphans

    async def scan_unused_fsx_file_systems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for unused FSx file systems using CloudWatch metrics.

        Detection: File systems with no data read/write activity for 30+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned FSx file systems
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3
        confidence_threshold_days = (
            detection_rules.get("confidence_threshold_days", 30)
            if detection_rules
            else 30
        )

        try:
            async with self.session.client("fsx", region_name=region) as fsx:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await fsx.describe_file_systems()

                    for fs in response.get("FileSystems", []):
                        fs_id = fs["FileSystemId"]
                        fs_type = fs["FileSystemType"]  # LUSTRE, WINDOWS, ONTAP, OPENZFS
                        created_at = fs["CreationTime"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for data transfer metrics (30-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=30)

                        # Different metrics based on file system type
                        metric_name = "DataReadBytes" if fs_type == "LUSTRE" else "DataWriteBytes"

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/FSx",
                            MetricName=metric_name,
                            Dimensions=[
                                {"Name": "FileSystemId", "Value": fs_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=86400,  # 1 day
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_bytes = sum(dp["Sum"] for dp in datapoints)

                        # Determine usage category
                        ever_used = total_bytes > 1_000_000  # > 1MB = used
                        last_active_date = None

                        if datapoints:
                            sorted_points = sorted(
                                datapoints, key=lambda x: x["Timestamp"], reverse=True
                            )
                            for dp in sorted_points:
                                if dp["Sum"] > 1_000_000:
                                    last_active_date = dp["Timestamp"]
                                    break

                        # Categorize usage
                        if not ever_used:
                            usage_category = "never_used"
                        elif last_active_date:
                            days_since_last_use = (now - last_active_date).days
                            if days_since_last_use < 7:
                                usage_category = "recently_active"
                            elif days_since_last_use < 30:
                                usage_category = "recently_abandoned"
                            else:
                                usage_category = "long_abandoned"
                        else:
                            usage_category = "never_used"

                        # Skip recently active resources
                        if usage_category == "recently_active":
                            continue

                        # Determine confidence and orphan reason
                        if usage_category == "never_used" and age_days >= 30:
                            confidence = "high"
                            reason = f"Never used since creation {age_days} days ago"
                        elif usage_category == "long_abandoned":
                            confidence = "high"
                            days_abandoned = (
                                (now - last_active_date).days if last_active_date else 0
                            )
                            reason = f"No activity for {days_abandoned} days (was active before)"
                        elif usage_category == "recently_abandoned":
                            confidence = "medium"
                            days_abandoned = (
                                (now - last_active_date).days if last_active_date else 0
                            )
                            reason = f"No activity for {days_abandoned} days"
                        else:
                            confidence = "low"
                            reason = f"Created {age_days} days ago, usage pattern unclear"

                        # Calculate cost based on storage capacity and type
                        storage_capacity = fs["StorageCapacity"]  # in GB
                        pricing_key = f"fsx_{fs_type.lower()}_per_gb"
                        if pricing_key in self.PRICING:
                            monthly_cost = storage_capacity * self.PRICING[pricing_key]
                        else:
                            monthly_cost = storage_capacity * 0.14  # Default FSx pricing

                        # Extract name from tags
                        name = None
                        for tag in fs.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        orphans.append(
                            OrphanResourceData(
                                resource_type="fsx_file_system",
                                resource_id=fs_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "file_system_type": fs_type,
                                    "storage_capacity_gb": storage_capacity,
                                    "lifecycle_status": fs.get("Lifecycle", "Unknown"),
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "confidence": confidence,
                                    "orphan_reason": reason,
                                    "total_bytes_transferred_30d": int(total_bytes),
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning FSx file systems in {region}: {e}")

        return orphans

    async def scan_idle_neptune_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Neptune clusters using CloudWatch metrics.

        Detection: Neptune clusters with no active connections for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned Neptune clusters
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("neptune", region_name=region) as neptune:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await neptune.describe_db_clusters()

                    for cluster in response.get("DBClusters", []):
                        cluster_id = cluster["DBClusterIdentifier"]
                        created_at = cluster["ClusterCreateTime"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for DatabaseConnections metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/Neptune",
                            MetricName="DatabaseConnections",
                            Dimensions=[
                                {"Name": "DBClusterIdentifier", "Value": cluster_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Average"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        avg_connections = (
                            sum(dp["Average"] for dp in datapoints) / len(datapoints)
                            if datapoints
                            else 0
                        )

                        # If average connections < 0.1 over 7 days, consider idle
                        if avg_connections < 0.1:
                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No active connections for 7+ days (cluster age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No active connections detected (cluster age: {age_days} days)"

                            # Estimate cost based on instance type
                            instance_class = cluster.get("DBClusterInstanceClass", "db.r5.large")
                            if "r5.large" in instance_class:
                                monthly_cost = self.PRICING["neptune_db_r5_large"] * 730
                            elif "r5.xlarge" in instance_class:
                                monthly_cost = self.PRICING["neptune_db_r5_xlarge"] * 730
                            else:
                                monthly_cost = 250.00  # Default estimate

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="neptune_cluster",
                                    resource_id=cluster_id,
                                    resource_name=cluster_id,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "engine": cluster.get("Engine", "neptune"),
                                        "engine_version": cluster.get("EngineVersion", "Unknown"),
                                        "status": cluster.get("Status", "Unknown"),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "avg_connections_7d": round(avg_connections, 2),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning Neptune clusters in {region}: {e}")

        return orphans

    async def scan_idle_msk_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle MSK (Managed Kafka) clusters using CloudWatch metrics.

        Detection: MSK clusters with no data in/out for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned MSK clusters
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("kafka", region_name=region) as kafka:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await kafka.list_clusters_v2()

                    for cluster in response.get("ClusterInfoList", []):
                        cluster_arn = cluster["ClusterArn"]
                        cluster_name = cluster["ClusterName"]
                        created_at = cluster["CreationTime"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for BytesInPerSec metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/Kafka",
                            MetricName="BytesInPerSec",
                            Dimensions=[
                                {"Name": "Cluster Name", "Value": cluster_name},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Average"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        avg_bytes_in = (
                            sum(dp["Average"] for dp in datapoints) / len(datapoints)
                            if datapoints
                            else 0
                        )

                        # If average < 1 byte/sec over 7 days, consider idle
                        if avg_bytes_in < 1:
                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No data traffic for 7+ days (cluster age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No data traffic detected (cluster age: {age_days} days)"

                            # Estimate cost based on broker count and instance type
                            broker_node_info = cluster.get("Provisioned", {}).get(
                                "BrokerNodeGroupInfo", {}
                            )
                            broker_count = cluster.get("Provisioned", {}).get(
                                "NumberOfBrokerNodes", 3
                            )
                            instance_type = broker_node_info.get("InstanceType", "kafka.m5.large")

                            if "m5.large" in instance_type:
                                cost_per_broker = self.PRICING["msk_kafka_m5_large"] * 730
                            elif "m5.xlarge" in instance_type:
                                cost_per_broker = self.PRICING["msk_kafka_m5_xlarge"] * 730
                            else:
                                cost_per_broker = 150.00  # Default

                            monthly_cost = cost_per_broker * broker_count

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="msk_cluster",
                                    resource_id=cluster_arn,
                                    resource_name=cluster_name,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "broker_count": broker_count,
                                        "instance_type": instance_type,
                                        "state": cluster.get("State", "Unknown"),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "avg_bytes_in_per_sec_7d": round(avg_bytes_in, 2),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning MSK clusters in {region}: {e}")

        return orphans

    async def scan_idle_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle EKS clusters (no worker nodes or no activity).

        Detection: EKS clusters with 0 nodes or no API activity for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned EKS clusters
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("eks", region_name=region) as eks:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await eks.list_clusters()

                    for cluster_name in response.get("clusters", []):
                        cluster_info = await eks.describe_cluster(name=cluster_name)
                        cluster = cluster_info["cluster"]

                        created_at = cluster["createdAt"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Check node groups
                        nodegroups_response = await eks.list_nodegroups(
                            clusterName=cluster_name
                        )
                        nodegroups = nodegroups_response.get("nodegroups", [])

                        total_nodes = 0
                        for ng_name in nodegroups:
                            ng_info = await eks.describe_nodegroup(
                                clusterName=cluster_name, nodegroupName=ng_name
                            )
                            ng = ng_info["nodegroup"]
                            total_nodes += ng.get("scalingConfig", {}).get("desiredSize", 0)

                        # Query CloudWatch for cluster API calls (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        # Note: EKS doesn't have direct API call metrics, so we check if nodes = 0
                        is_orphaned = False
                        reason = ""
                        confidence = "medium"

                        if total_nodes == 0:
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No worker nodes for 7+ days (cluster age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No worker nodes (cluster age: {age_days} days)"
                            is_orphaned = True

                        if is_orphaned:
                            orphans.append(
                                OrphanResourceData(
                                    resource_type="eks_cluster",
                                    resource_id=cluster_name,
                                    resource_name=cluster_name,
                                    region=region,
                                    estimated_monthly_cost=self.PRICING["eks_cluster"],
                                    resource_metadata={
                                        "version": cluster.get("version", "Unknown"),
                                        "status": cluster.get("status", "Unknown"),
                                        "nodegroup_count": len(nodegroups),
                                        "total_nodes": total_nodes,
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning EKS clusters in {region}: {e}")

        return orphans

    async def scan_idle_sagemaker_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle SageMaker endpoints using CloudWatch metrics.

        Detection: Endpoints with no invocations for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned SageMaker endpoints
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("sagemaker", region_name=region) as sagemaker:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await sagemaker.list_endpoints()

                    for endpoint in response.get("Endpoints", []):
                        endpoint_name = endpoint["EndpointName"]
                        created_at = endpoint["CreationTime"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for Invocations metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/SageMaker",
                            MetricName="ModelInvocations",
                            Dimensions=[
                                {"Name": "EndpointName", "Value": endpoint_name},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_invocations = sum(dp["Sum"] for dp in datapoints)

                        # If 0 invocations over 7 days, consider idle
                        if total_invocations == 0:
                            # Get endpoint config to estimate cost
                            endpoint_config_name = endpoint["EndpointConfigName"]
                            config_response = await sagemaker.describe_endpoint_config(
                                EndpointConfigName=endpoint_config_name
                            )

                            # Get instance type from production variants
                            instance_type = "ml.m5.large"  # Default
                            instance_count = 1
                            for variant in config_response.get("ProductionVariants", []):
                                instance_type = variant.get("InstanceType", "ml.m5.large")
                                instance_count = variant.get("InitialInstanceCount", 1)
                                break

                            # Estimate cost
                            if "m5.large" in instance_type:
                                cost_per_instance = self.PRICING["sagemaker_ml_m5_large"] * 730
                            elif "m5.xlarge" in instance_type:
                                cost_per_instance = self.PRICING["sagemaker_ml_m5_xlarge"] * 730
                            else:
                                cost_per_instance = 83.00  # Default

                            monthly_cost = cost_per_instance * instance_count

                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No invocations for 7+ days (endpoint age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = (
                                    f"No invocations detected (endpoint age: {age_days} days)"
                                )

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="sagemaker_endpoint",
                                    resource_id=endpoint_name,
                                    resource_name=endpoint_name,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "instance_type": instance_type,
                                        "instance_count": instance_count,
                                        "status": endpoint.get("EndpointStatus", "Unknown"),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "invocations_7d": int(total_invocations),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning SageMaker endpoints in {region}: {e}")

        return orphans

    async def scan_idle_redshift_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Redshift clusters using CloudWatch metrics.

        Detection: Clusters with no database connections for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned Redshift clusters
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("redshift", region_name=region) as redshift:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await redshift.describe_clusters()

                    for cluster in response.get("Clusters", []):
                        cluster_id = cluster["ClusterIdentifier"]
                        created_at = cluster["ClusterCreateTime"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for DatabaseConnections metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/Redshift",
                            MetricName="DatabaseConnections",
                            Dimensions=[
                                {"Name": "ClusterIdentifier", "Value": cluster_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Average"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        avg_connections = (
                            sum(dp["Average"] for dp in datapoints) / len(datapoints)
                            if datapoints
                            else 0
                        )

                        # If average connections < 0.1 over 7 days, consider idle
                        if avg_connections < 0.1:
                            # Estimate cost based on node type
                            node_type = cluster.get("NodeType", "dc2.large")
                            num_nodes = cluster.get("NumberOfNodes", 1)

                            if "dc2.large" in node_type:
                                cost_per_node = self.PRICING["redshift_dc2_large"] * 730
                            elif "dc2.xlarge" in node_type or "dc2.8xlarge" in node_type:
                                cost_per_node = self.PRICING["redshift_dc2_xlarge"] * 730
                            else:
                                cost_per_node = 180.00  # Default

                            monthly_cost = cost_per_node * num_nodes

                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No database connections for 7+ days (cluster age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No connections detected (cluster age: {age_days} days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="redshift_cluster",
                                    resource_id=cluster_id,
                                    resource_name=cluster_id,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "node_type": node_type,
                                        "num_nodes": num_nodes,
                                        "cluster_status": cluster.get("ClusterStatus", "Unknown"),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "avg_connections_7d": round(avg_connections, 2),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning Redshift clusters in {region}: {e}")

        return orphans

    async def scan_idle_elasticache_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle ElastiCache clusters using CloudWatch metrics.

        Detection: Clusters with no cache hits/gets for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned ElastiCache clusters
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("elasticache", region_name=region) as elasticache:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    # Check Redis clusters
                    response = await elasticache.describe_cache_clusters()

                    for cluster in response.get("CacheClusters", []):
                        cluster_id = cluster["CacheClusterId"]
                        created_at = cluster.get("CacheClusterCreateTime")
                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for CacheHits metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/ElastiCache",
                            MetricName="CacheHits",
                            Dimensions=[
                                {"Name": "CacheClusterId", "Value": cluster_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_hits = sum(dp["Sum"] for dp in datapoints)

                        # If 0 cache hits over 7 days, consider idle
                        if total_hits == 0:
                            # Estimate cost based on node type
                            node_type = cluster.get("CacheNodeType", "cache.m5.large")
                            num_nodes = cluster.get("NumCacheNodes", 1)

                            if "m5.large" in node_type:
                                cost_per_node = self.PRICING["elasticache_cache_m5_large"] * 730
                            elif "r5.large" in node_type:
                                cost_per_node = self.PRICING["elasticache_cache_r5_large"] * 730
                            else:
                                cost_per_node = 90.00  # Default

                            monthly_cost = cost_per_node * num_nodes

                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No cache hits for 7+ days (cluster age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No cache activity detected (cluster age: {age_days} days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="elasticache_cluster",
                                    resource_id=cluster_id,
                                    resource_name=cluster_id,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "node_type": node_type,
                                        "num_nodes": num_nodes,
                                        "engine": cluster.get("Engine", "Unknown"),
                                        "engine_version": cluster.get("EngineVersion", "Unknown"),
                                        "status": cluster.get("CacheClusterStatus", "Unknown"),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "cache_hits_7d": int(total_hits),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning ElastiCache clusters in {region}: {e}")

        return orphans

    async def scan_idle_vpn_connections(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle VPN connections using CloudWatch metrics.

        Detection: VPN connections with no data transfer for 30+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned VPN connections
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await ec2.describe_vpn_connections()

                    for vpn in response.get("VpnConnections", []):
                        vpn_id = vpn["VpnConnectionId"]
                        state = vpn.get("State", "unknown")

                        # Skip deleted/deleting VPNs
                        if state in ["deleted", "deleting"]:
                            continue

                        # Query CloudWatch for TunnelDataIn metric (30-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=30)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/VPN",
                            MetricName="TunnelDataIn",
                            Dimensions=[
                                {"Name": "VpnId", "Value": vpn_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=86400,  # 1 day
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_bytes = sum(dp["Sum"] for dp in datapoints)

                        # If < 1MB over 30 days, consider idle
                        if total_bytes < 1_000_000:
                            # Extract name from tags
                            name = None
                            for tag in vpn.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            # Determine confidence (we don't have creation date for VPN)
                            if total_bytes == 0:
                                confidence = "high"
                                reason = "No data transfer for 30+ days"
                            else:
                                confidence = "medium"
                                reason = f"Very low data transfer ({int(total_bytes)} bytes in 30 days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="vpn_connection",
                                    resource_id=vpn_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=self.PRICING["vpn_connection"],
                                    resource_metadata={
                                        "state": state,
                                        "type": vpn.get("Type", "Unknown"),
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "bytes_transferred_30d": int(total_bytes),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning VPN connections in {region}: {e}")

        return orphans

    async def scan_idle_transit_gateway_attachments(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Transit Gateway attachments using CloudWatch metrics.

        Detection: Attachments with no data transfer for 30+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned TGW attachments
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await ec2.describe_transit_gateway_attachments()

                    for attachment in response.get("TransitGatewayAttachments", []):
                        attachment_id = attachment["TransitGatewayAttachmentId"]
                        state = attachment.get("State", "unknown")

                        # Skip deleted/deleting attachments
                        if state in ["deleted", "deleting", "failed"]:
                            continue

                        created_at = attachment.get("CreationTime")
                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for BytesIn metric (30-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=30)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/TransitGateway",
                            MetricName="BytesIn",
                            Dimensions=[
                                {"Name": "TransitGatewayAttachment", "Value": attachment_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=86400,  # 1 day
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_bytes = sum(dp["Sum"] for dp in datapoints)

                        # If < 1MB over 30 days, consider idle
                        if total_bytes < 1_000_000:
                            # Extract name from tags
                            name = None
                            for tag in attachment.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            # Determine confidence
                            if age_days >= 30 and total_bytes == 0:
                                confidence = "high"
                                reason = f"No data transfer for 30+ days (attachment age: {age_days} days)"
                            elif total_bytes == 0:
                                confidence = "medium"
                                reason = f"No data transfer (attachment age: {age_days} days)"
                            else:
                                confidence = "low"
                                reason = f"Very low data transfer ({int(total_bytes)} bytes in 30 days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="transit_gateway_attachment",
                                    resource_id=attachment_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=self.PRICING[
                                        "transit_gateway_attachment"
                                    ],
                                    resource_metadata={
                                        "state": state,
                                        "resource_type": attachment.get(
                                            "ResourceType", "Unknown"
                                        ),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "bytes_transferred_30d": int(total_bytes),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning Transit Gateway attachments in {region}: {e}")

        return orphans

    async def scan_idle_opensearch_domains(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle OpenSearch domains using CloudWatch metrics.

        Detection: Domains with no search/indexing requests for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned OpenSearch domains
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("opensearch", region_name=region) as opensearch:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await opensearch.list_domain_names()

                    for domain_info in response.get("DomainNames", []):
                        domain_name = domain_info["DomainName"]

                        # Get domain details
                        domain_response = await opensearch.describe_domain(
                            DomainName=domain_name
                        )
                        domain = domain_response["DomainStatus"]

                        created_at = domain.get("Created")
                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for SearchRate metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/ES",
                            MetricName="SearchRate",
                            Dimensions=[
                                {"Name": "DomainName", "Value": domain_name},
                                {"Name": "ClientId", "Value": domain["ARN"].split(":")[4]},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_searches = sum(dp["Sum"] for dp in datapoints)

                        # If 0 searches over 7 days, consider idle
                        if total_searches == 0:
                            # Estimate cost based on instance type and count
                            cluster_config = domain.get("ClusterConfig", {})
                            instance_type = cluster_config.get(
                                "InstanceType", "m5.large.search"
                            )
                            instance_count = cluster_config.get("InstanceCount", 1)

                            if "m5.large" in instance_type:
                                cost_per_instance = self.PRICING["opensearch_m5_large"] * 730
                            elif "r5.large" in instance_type:
                                cost_per_instance = self.PRICING["opensearch_r5_large"] * 730
                            else:
                                cost_per_instance = 116.00  # Default

                            monthly_cost = cost_per_instance * instance_count

                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No search requests for 7+ days (domain age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No search activity detected (domain age: {age_days} days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="opensearch_domain",
                                    resource_id=domain_name,
                                    resource_name=domain_name,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "instance_type": instance_type,
                                        "instance_count": instance_count,
                                        "engine_version": domain.get(
                                            "EngineVersion", "Unknown"
                                        ),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "search_requests_7d": int(total_searches),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning OpenSearch domains in {region}: {e}")

        return orphans

    async def scan_idle_global_accelerators(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Global Accelerators (no endpoints or no traffic).

        Detection: Accelerators with 0 endpoints or no processed bytes for 30+ days.

        Args:
            region: AWS region to scan (Global Accelerator is global but we need region for API)
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned Global Accelerators
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        # Global Accelerator is a global service, only check in us-west-2
        if region != "us-west-2":
            return orphans

        try:
            async with self.session.client(
                "globalaccelerator", region_name="us-west-2"
            ) as ga:
                async with self.session.client("cloudwatch", region_name="us-west-2") as cw:
                    response = await ga.list_accelerators()

                    for accelerator in response.get("Accelerators", []):
                        accelerator_arn = accelerator["AcceleratorArn"]
                        accelerator_name = accelerator.get("Name", accelerator_arn.split("/")[-1])
                        created_at = accelerator.get("CreatedTime")

                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Check endpoints
                        listeners_response = await ga.list_listeners(
                            AcceleratorArn=accelerator_arn
                        )
                        total_endpoints = 0

                        for listener in listeners_response.get("Listeners", []):
                            listener_arn = listener["ListenerArn"]
                            endpoint_groups = await ga.list_endpoint_groups(
                                ListenerArn=listener_arn
                            )
                            for eg in endpoint_groups.get("EndpointGroups", []):
                                total_endpoints += len(eg.get("EndpointDescriptions", []))

                        # If no endpoints, it's definitely orphaned
                        is_orphaned = False
                        reason = ""
                        confidence = "medium"

                        if total_endpoints == 0:
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No endpoints configured for 7+ days (accelerator age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No endpoints configured (accelerator age: {age_days} days)"
                            is_orphaned = True

                        if is_orphaned:
                            orphans.append(
                                OrphanResourceData(
                                    resource_type="global_accelerator",
                                    resource_id=accelerator_arn,
                                    resource_name=accelerator_name,
                                    region="global",
                                    estimated_monthly_cost=self.PRICING["global_accelerator"],
                                    resource_metadata={
                                        "enabled": accelerator.get("Enabled", False),
                                        "status": accelerator.get("Status", "Unknown"),
                                        "endpoint_count": total_endpoints,
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning Global Accelerators: {e}")

        return orphans

    async def scan_idle_kinesis_streams(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Kinesis streams using CloudWatch metrics.

        Detection: Streams with no incoming/outgoing records for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned Kinesis streams
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("kinesis", region_name=region) as kinesis:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await kinesis.list_streams()

                    for stream_name in response.get("StreamNames", []):
                        # Get stream details
                        stream_info = await kinesis.describe_stream(StreamName=stream_name)
                        stream = stream_info["StreamDescription"]

                        created_at = stream.get("StreamCreationTimestamp")
                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for IncomingRecords metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/Kinesis",
                            MetricName="IncomingRecords",
                            Dimensions=[
                                {"Name": "StreamName", "Value": stream_name},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Sum"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        total_records = sum(dp["Sum"] for dp in datapoints)

                        # If 0 records over 7 days, consider idle
                        if total_records == 0:
                            # Calculate cost based on shard count
                            shard_count = len(stream.get("Shards", []))
                            monthly_cost = self.PRICING["kinesis_shard"] * shard_count

                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No incoming records for 7+ days (stream age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No data activity detected (stream age: {age_days} days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="kinesis_stream",
                                    resource_id=stream_name,
                                    resource_name=stream_name,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "shard_count": shard_count,
                                        "status": stream.get("StreamStatus", "Unknown"),
                                        "retention_hours": stream.get(
                                            "RetentionPeriodHours", 24
                                        ),
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "incoming_records_7d": int(total_records),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning Kinesis streams in {region}: {e}")

        return orphans

    async def scan_unused_vpc_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for unused VPC endpoints (no network interfaces or no traffic).

        Detection: VPC endpoints with 0 network interfaces for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned VPC endpoints
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_vpc_endpoints()

                for endpoint in response.get("VpcEndpoints", []):
                    endpoint_id = endpoint["VpcEndpointId"]
                    created_at = endpoint.get("CreationTimestamp")

                    if not created_at:
                        continue

                    age_days = (datetime.now(timezone.utc) - created_at).days

                    if age_days < min_age_days:
                        continue

                    # Check network interfaces
                    network_interfaces = endpoint.get("NetworkInterfaceIds", [])
                    subnet_ids = endpoint.get("SubnetIds", [])

                    # If no network interfaces or subnets, consider unused
                    if len(network_interfaces) == 0 and len(subnet_ids) == 0:
                        # Extract name from tags
                        name = None
                        for tag in endpoint.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        # Determine confidence
                        if age_days >= 7:
                            confidence = "high"
                            reason = f"No network interfaces for 7+ days (endpoint age: {age_days} days)"
                        else:
                            confidence = "medium"
                            reason = f"No network interfaces (endpoint age: {age_days} days)"

                        orphans.append(
                            OrphanResourceData(
                                resource_type="vpc_endpoint",
                                resource_id=endpoint_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=self.PRICING["vpc_endpoint"],
                                resource_metadata={
                                    "vpc_id": endpoint.get("VpcId", "Unknown"),
                                    "service_name": endpoint.get("ServiceName", "Unknown"),
                                    "state": endpoint.get("State", "Unknown"),
                                    "endpoint_type": endpoint.get("VpcEndpointType", "Unknown"),
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "confidence": confidence,
                                    "orphan_reason": reason,
                                    "network_interface_count": len(network_interfaces),
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning VPC endpoints in {region}: {e}")

        return orphans

    async def scan_idle_documentdb_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle DocumentDB clusters using CloudWatch metrics.

        Detection: Clusters with no database connections for 7+ days.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned DocumentDB clusters
        """
        orphans = []
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3

        try:
            async with self.session.client("docdb", region_name=region) as docdb:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await docdb.describe_db_clusters()

                    for cluster in response.get("DBClusters", []):
                        cluster_id = cluster["DBClusterIdentifier"]
                        created_at = cluster.get("ClusterCreateTime")

                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for DatabaseConnections metric (7-day lookback)
                        now = datetime.now(timezone.utc)
                        start_time = now - timedelta(days=7)

                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/DocDB",
                            MetricName="DatabaseConnections",
                            Dimensions=[
                                {"Name": "DBClusterIdentifier", "Value": cluster_id},
                            ],
                            StartTime=start_time,
                            EndTime=now,
                            Period=3600,  # 1 hour
                            Statistics=["Average"],
                        )

                        datapoints = metrics_response.get("Datapoints", [])
                        avg_connections = (
                            sum(dp["Average"] for dp in datapoints) / len(datapoints)
                            if datapoints
                            else 0
                        )

                        # If average connections < 0.1 over 7 days, consider idle
                        if avg_connections < 0.1:
                            # Estimate cost based on instance class (from cluster members)
                            cluster_members = cluster.get("DBClusterMembers", [])
                            instance_count = len(cluster_members)

                            # Default to r5.large pricing
                            monthly_cost = self.PRICING["documentdb_r5_large"] * 730 * max(
                                instance_count, 1
                            )

                            # Determine confidence
                            if age_days >= 7:
                                confidence = "high"
                                reason = f"No database connections for 7+ days (cluster age: {age_days} days)"
                            else:
                                confidence = "medium"
                                reason = f"No connections detected (cluster age: {age_days} days)"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="documentdb_cluster",
                                    resource_id=cluster_id,
                                    resource_name=cluster_id,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "engine": cluster.get("Engine", "docdb"),
                                        "engine_version": cluster.get("EngineVersion", "Unknown"),
                                        "status": cluster.get("Status", "Unknown"),
                                        "instance_count": instance_count,
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "orphan_reason": reason,
                                        "avg_connections_7d": round(avg_connections, 2),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning DocumentDB clusters in {region}: {e}")

        return orphans
