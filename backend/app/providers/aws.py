"""AWS cloud provider implementation."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aioboto3
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectionError

from app.providers.base import CloudProviderBase, OrphanResourceData

# Logger for AWS connectivity debugging
logger = logging.getLogger(__name__)


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
        # RDS Instance pricing (common types, per hour converted to monthly)
        "rds_storage_gp2_per_gb": 0.115,  # General Purpose SSD (gp2)
        "rds_storage_gp3_per_gb": 0.092,  # General Purpose SSD (gp3) - newer, cheaper
        "rds_db_t3_micro": 12.24,  # db.t3.micro (~$0.017/hour * 730 hours)
        "rds_db_t3_small": 24.82,  # db.t3.small (~$0.034/hour * 730 hours)
        "rds_db_t3_medium": 49.64,  # db.t3.medium (~$0.068/hour * 730 hours)
        "rds_db_t3_large": 99.28,  # db.t3.large (~$0.136/hour * 730 hours)
        "rds_db_t4g_micro": 11.68,  # db.t4g.micro (~$0.016/hour * 730 hours) - ARM-based
        "rds_db_t4g_small": 23.36,  # db.t4g.small (~$0.032/hour * 730 hours)
        "rds_db_m5_large": 140.16,  # db.m5.large (~$0.192/hour * 730 hours)
        "rds_db_m5_xlarge": 280.32,  # db.m5.xlarge (~$0.384/hour * 730 hours)
        "rds_db_m5_2xlarge": 560.64,  # db.m5.2xlarge (~$0.768/hour * 730 hours)
        # TOP 15 high-cost idle resources
        "fsx_lustre_per_gb": 0.145,  # FSx for Lustre (SSD storage)
        "fsx_windows_per_gb": 0.13,  # FSx for Windows (SSD storage)
        "fsx_windows_hdd_per_gb": 0.013,  # FSx for Windows (HDD storage - 90% cheaper)
        "fsx_ontap_per_gb": 0.144,  # FSx for NetApp ONTAP (SSD storage)
        "fsx_openzfs_per_gb": 0.14,  # FSx for OpenZFS (SSD storage)
        "fsx_backup_per_gb": 0.050,  # FSx backup storage (incremental, more expensive than HDD)
        "fsx_throughput_per_mbps": 2.20,  # FSx throughput capacity ($2.20 per MB/s/month for Windows/ONTAP)
        "neptune_db_r5_large": 0.348,  # Neptune db.r5.large (per hour) = ~$250/month
        "neptune_db_r5_xlarge": 0.696,  # Neptune db.r5.xlarge = ~$500/month
        "msk_kafka_m5_large": 0.21,  # MSK kafka.m5.large (per broker/hour) = ~$150/month
        "msk_kafka_m5_xlarge": 0.42,  # MSK kafka.m5.xlarge = ~$300/month
        # EKS pricing (Control Plane + Worker Nodes)
        "eks_control_plane": 73.00,  # EKS Control Plane ($0.10/hour * 730 hours)
        "eks_t3_small": 15.18,  # t3.small node (~$0.0208/hour * 730)
        "eks_t3_medium": 30.37,  # t3.medium node (~$0.0416/hour * 730)
        "eks_t3_large": 60.74,  # t3.large node (~$0.0832/hour * 730)
        "eks_t3_xlarge": 121.47,  # t3.xlarge node (~$0.1664/hour * 730)
        "eks_m5_large": 69.35,  # m5.large node (~$0.095/hour * 730)
        "eks_m5_xlarge": 138.70,  # m5.xlarge node (~$0.19/hour * 730)
        "eks_m5_2xlarge": 277.40,  # m5.2xlarge node (~$0.38/hour * 730)
        "eks_c5_large": 62.78,  # c5.large node (~$0.086/hour * 730)
        "eks_r5_large": 91.98,  # r5.large node (~$0.126/hour * 730)
        "sagemaker_ml_m5_large": 0.115,  # SageMaker ml.m5.large (per hour) = ~$83/month
        "sagemaker_ml_m5_xlarge": 0.23,  # SageMaker ml.m5.xlarge = ~$165/month
        "redshift_dc2_large": 0.25,  # Redshift dc2.large (per hour) = ~$180/month
        "redshift_dc2_xlarge": 1.00,  # Redshift dc2.xlarge = ~$720/month
        # ElastiCache pricing (us-east-1) - Extended node types
        "elasticache_t3_micro": 0.017,      # cache.t3.micro = ~$12/month
        "elasticache_t3_small": 0.034,      # cache.t3.small = ~$24/month
        "elasticache_t3_medium": 0.068,     # cache.t3.medium = ~$49/month
        "elasticache_t4g_micro": 0.016,     # cache.t4g.micro (Graviton2) = ~$11/month
        "elasticache_t4g_small": 0.032,     # cache.t4g.small = ~$23/month
        "elasticache_t4g_medium": 0.064,    # cache.t4g.medium = ~$46/month
        "elasticache_m5_large": 0.126,      # cache.m5.large = ~$90/month
        "elasticache_m5_xlarge": 0.252,     # cache.m5.xlarge = ~$180/month
        "elasticache_m5_2xlarge": 0.504,    # cache.m5.2xlarge = ~$361/month
        "elasticache_m6g_large": 0.113,     # cache.m6g.large (Graviton2) = ~$81/month
        "elasticache_m6g_xlarge": 0.226,    # cache.m6g.xlarge = ~$162/month
        "elasticache_r5_large": 0.188,      # cache.r5.large (memory-optimized) = ~$135/month
        "elasticache_r5_xlarge": 0.376,     # cache.r5.xlarge = ~$270/month
        "elasticache_r5_2xlarge": 0.752,    # cache.r5.2xlarge = ~$539/month
        "elasticache_r6g_large": 0.169,     # cache.r6g.large (Graviton2) = ~$121/month
        "elasticache_r6g_xlarge": 0.338,    # cache.r6g.xlarge = ~$242/month
        "vpn_connection": 36.00,  # VPN Connection
        "transit_gateway_attachment": 36.00,  # Transit Gateway Attachment (per month)
        "opensearch_m5_large": 0.161,  # OpenSearch m5.large.search (per hour) = ~$116/month
        "opensearch_r5_large": 0.228,  # OpenSearch r5.large.search = ~$164/month
        "global_accelerator": 18.00,  # Global Accelerator (base cost)
        "kinesis_shard": 10.80,  # Kinesis shard ($0.015/hour * 730 hours)
        "kinesis_retention_extended_per_gb": 0.020,  # Extended retention (25-168h)
        "kinesis_retention_long_per_gb": 0.026,  # Long-term retention (>168h)
        "kinesis_enhanced_fanout_per_consumer": 10.95,  # Enhanced Fan-Out ($0.015/hour * 730h)
        "vpc_endpoint": 7.20,  # VPC Endpoint (per month)
        "documentdb_r5_large": 0.277,  # DocumentDB db.r5.large (per hour) = ~$199/month
        # S3 pricing per GB/month (storage only, not including requests/transfer)
        "s3_standard_per_gb": 0.023,  # S3 Standard storage
        "s3_standard_ia_per_gb": 0.0125,  # S3 Standard-IA (Infrequent Access)
        "s3_glacier_per_gb": 0.004,  # S3 Glacier Flexible Retrieval
        "s3_glacier_deep_per_gb": 0.00099,  # S3 Glacier Deep Archive
        # Lambda pricing (us-east-1)
        "lambda_invocation_per_million": 0.20,  # Per 1M requests
        "lambda_gb_second": 0.0000166667,  # Per GB-second compute
        "lambda_provisioned_concurrency_gb_second": 0.0000041667,  # Per GB-second (24/7 charge!)
        "lambda_storage_per_gb": 0.0,  # Free up to 512MB
        # DynamoDB pricing (us-east-1)
        "dynamodb_wcu_per_hour": 0.00013,  # Per WCU/hour (~$0.095/WCU/month)
        "dynamodb_rcu_per_hour": 0.00013,  # Per RCU/hour (~$0.095/RCU/month)
        "dynamodb_storage_per_gb": 0.25,  # Per GB/month
        "dynamodb_ondemand_write_per_million": 1.25,  # Per 1M write requests
        "dynamodb_ondemand_read_per_million": 0.25,  # Per 1M read requests, then $0.00008 per GB-month
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

        # Configure boto3 with longer timeouts for VPS environments
        self.config = Config(
            connect_timeout=60,  # 60 seconds to establish connection
            read_timeout=60,     # 60 seconds to read response
            retries={'max_attempts': 3, 'mode': 'standard'}
        )

        self.session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        logger.info(f"AWSProvider initialized with config: connect_timeout=60s, read_timeout=60s, retries=3")

    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate AWS credentials using STS GetCallerIdentity.

        Returns:
            Dict with account_id, arn, user_id

        Raises:
            ClientError: If credentials are invalid
            EndpointConnectionError: If cannot connect to AWS endpoints
        """
        logger.info("🔍 Starting AWS credential validation...")
        logger.info(f"📍 Attempting to connect to AWS STS endpoint (us-east-1)")

        try:
            async with self.session.client(
                "sts",
                region_name="us-east-1",
                config=self.config
            ) as sts:
                logger.info("✅ STS client created successfully")
                logger.info("📞 Calling sts.get_caller_identity()...")

                response = await sts.get_caller_identity()

                logger.info(f"✅ AWS credentials validated successfully!")
                logger.info(f"   Account ID: {response['Account']}")
                logger.info(f"   ARN: {response['Arn']}")

                return {
                    "account_id": response["Account"],
                    "arn": response["Arn"],
                    "user_id": response["UserId"],
                }

        except EndpointConnectionError as e:
            logger.error(f"❌ ENDPOINT CONNECTION ERROR: Cannot connect to AWS STS")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   This usually means:")
            logger.error(f"   1. Firewall blocking HTTPS (port 443) outbound traffic")
            logger.error(f"   2. DNS cannot resolve sts.amazonaws.com")
            logger.error(f"   3. No internet connectivity from server")
            logger.error(f"")
            logger.error(f"   🔧 TROUBLESHOOTING:")
            logger.error(f"   Run: ./diagnose_aws_connectivity.sh")
            raise

        except ConnectionError as e:
            logger.error(f"❌ CONNECTION ERROR: Network issue connecting to AWS")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Check: Network configuration, proxy settings, firewall rules")
            raise

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"❌ AWS CLIENT ERROR: {error_code}")
            logger.error(f"   Error: {str(e)}")

            if error_code == 'InvalidClientTokenId':
                logger.error(f"   🔑 AWS Access Key ID is invalid or does not exist")
            elif error_code == 'SignatureDoesNotMatch':
                logger.error(f"   🔑 AWS Secret Access Key is incorrect")
            elif error_code == 'AccessDenied':
                logger.error(f"   🚫 AWS credentials do not have permission to call STS")
            else:
                logger.error(f"   ❓ Unexpected AWS error: {error_code}")

            raise

        except Exception as e:
            logger.error(f"❌ UNEXPECTED ERROR during AWS credential validation")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error: {str(e)}")
            logger.exception("Full traceback:")
            raise

    async def get_available_regions(self) -> list[str]:
        """
        Get list of available AWS regions for EC2.

        Returns:
            List of region names (e.g., ['us-east-1', 'eu-west-1'])
        """
        async with self.session.client("ec2", region_name="us-east-1", config=self.config) as ec2:
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

    async def _get_volume_metrics(
        self,
        volume_id: str,
        region: str,
        metric_names: list[str],
        period_days: int = 30,
        statistic: str = "Average",
    ) -> dict[str, float]:
        """
        Get CloudWatch metrics for an EBS volume.

        Args:
            volume_id: Volume ID
            region: AWS region
            metric_names: List of metric names (e.g., ["VolumeReadOps", "VolumeWriteOps", "VolumeReadBytes", "VolumeWriteBytes"])
            period_days: Lookback period in days
            statistic: CloudWatch statistic (Average, Sum, Maximum, Minimum)

        Returns:
            Dict with metric_name → calculated value (averaged across period)
        """
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                now = datetime.now(timezone.utc)
                start_time = now - timedelta(days=period_days)

                results = {}
                for metric_name in metric_names:
                    response = await cw.get_metric_statistics(
                        Namespace="AWS/EBS",
                        MetricName=metric_name,
                        Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
                        StartTime=start_time,
                        EndTime=now,
                        Period=86400,  # 1 day aggregation
                        Statistics=[statistic],
                    )

                    datapoints = response.get("Datapoints", [])
                    if datapoints:
                        # Calculate average/sum across all datapoints
                        if statistic == "Sum":
                            results[metric_name] = sum(dp[statistic] for dp in datapoints)
                        else:  # Average, Maximum, Minimum
                            results[metric_name] = sum(dp[statistic] for dp in datapoints) / len(datapoints)
                    else:
                        results[metric_name] = 0.0

                return results

        except Exception as e:
            print(f"Error fetching CloudWatch metrics for volume {volume_id}: {e}")
            return {metric_name: 0.0 for metric_name in metric_names}

    async def _get_eip_nat_gateway_metrics(
        self,
        nat_gateway_id: str,
        region: str,
        period_days: int = 30,
    ) -> dict[str, float]:
        """
        Get CloudWatch metrics for a NAT Gateway associated with an Elastic IP.

        Used for detecting:
        - SCENARIO 6: EIPs on unused NAT Gateways (no traffic)
        - SCENARIO 9: EIPs on NAT Gateways with zero connections

        Args:
            nat_gateway_id: NAT Gateway ID
            region: AWS region
            period_days: Lookback period in days (default 30)

        Returns:
            Dict with:
                - bytes_in_from_source: Total bytes inbound from source (Sum over period)
                - bytes_out_to_destination: Total bytes outbound to destination (Sum over period)
                - active_connection_count: Average active connections
                - total_traffic_gb: Total traffic in GB (bytes_in + bytes_out)
        """
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                now = datetime.now(timezone.utc)
                start_time = now - timedelta(days=period_days)

                # Fetch NAT Gateway metrics
                metrics_to_fetch = [
                    ("BytesInFromSource", "Sum"),
                    ("BytesOutToDestination", "Sum"),
                    ("ActiveConnectionCount", "Average"),
                ]

                results = {}
                for metric_name, statistic in metrics_to_fetch:
                    response = await cw.get_metric_statistics(
                        Namespace="AWS/NATGateway",
                        MetricName=metric_name,
                        Dimensions=[{"Name": "NatGatewayId", "Value": nat_gateway_id}],
                        StartTime=start_time,
                        EndTime=now,
                        Period=86400,  # 1 day aggregation
                        Statistics=[statistic],
                    )

                    datapoints = response.get("Datapoints", [])
                    if datapoints:
                        if statistic == "Sum":
                            results[metric_name] = sum(dp[statistic] for dp in datapoints)
                        else:  # Average
                            results[metric_name] = sum(dp[statistic] for dp in datapoints) / len(datapoints)
                    else:
                        results[metric_name] = 0.0

                # Calculate total traffic in GB
                bytes_in = results.get("BytesInFromSource", 0.0)
                bytes_out = results.get("BytesOutToDestination", 0.0)
                total_traffic_gb = (bytes_in + bytes_out) / (1024 ** 3)  # Convert bytes to GB

                return {
                    "bytes_in_from_source": bytes_in,
                    "bytes_out_to_destination": bytes_out,
                    "active_connection_count": results.get("ActiveConnectionCount", 0.0),
                    "total_traffic_gb": round(total_traffic_gb, 4),
                }

        except Exception as e:
            print(f"Error fetching CloudWatch metrics for NAT Gateway {nat_gateway_id}: {e}")
            return {
                "bytes_in_from_source": 0.0,
                "bytes_out_to_destination": 0.0,
                "active_connection_count": 0.0,
                "total_traffic_gb": 0.0,
            }

    async def _get_ec2_network_metrics(
        self,
        instance_id: str,
        region: str,
        period_days: int = 30,
    ) -> dict[str, float]:
        """
        Get CloudWatch network metrics for an EC2 instance with an Elastic IP.

        Used for detecting:
        - SCENARIO 7: Idle EIPs on active resources (low NetworkIn/Out)
        - SCENARIO 8: Low-traffic EIPs (< 1 GB/month)
        - SCENARIO 10: EIPs on failed instances (StatusCheckFailed)

        Args:
            instance_id: EC2 instance ID
            region: AWS region
            period_days: Lookback period in days (default 30)

        Returns:
            Dict with:
                - network_in: Total network in bytes (Sum over period)
                - network_out: Total network out bytes (Sum over period)
                - total_traffic_gb: Total traffic in GB (network_in + network_out)
                - status_check_failed: Count of status check failures
                - status_check_failed_instance: Instance-level failures
                - status_check_failed_system: System-level failures
        """
        try:
            async with self.session.client("cloudwatch", region_name=region) as cw:
                now = datetime.now(timezone.utc)
                start_time = now - timedelta(days=period_days)

                # Fetch EC2 network metrics
                metrics_to_fetch = [
                    ("NetworkIn", "Sum"),
                    ("NetworkOut", "Sum"),
                    ("StatusCheckFailed", "Sum"),
                    ("StatusCheckFailed_Instance", "Sum"),
                    ("StatusCheckFailed_System", "Sum"),
                ]

                results = {}
                for metric_name, statistic in metrics_to_fetch:
                    response = await cw.get_metric_statistics(
                        Namespace="AWS/EC2",
                        MetricName=metric_name,
                        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                        StartTime=start_time,
                        EndTime=now,
                        Period=86400,  # 1 day aggregation
                        Statistics=[statistic],
                    )

                    datapoints = response.get("Datapoints", [])
                    if datapoints:
                        results[metric_name] = sum(dp[statistic] for dp in datapoints)
                    else:
                        results[metric_name] = 0.0

                # Calculate total traffic in GB
                network_in = results.get("NetworkIn", 0.0)
                network_out = results.get("NetworkOut", 0.0)
                total_traffic_gb = (network_in + network_out) / (1024 ** 3)  # Convert bytes to GB

                return {
                    "network_in": network_in,
                    "network_out": network_out,
                    "total_traffic_gb": round(total_traffic_gb, 4),
                    "status_check_failed": results.get("StatusCheckFailed", 0.0),
                    "status_check_failed_instance": results.get("StatusCheckFailed_Instance", 0.0),
                    "status_check_failed_system": results.get("StatusCheckFailed_System", 0.0),
                }

        except Exception as e:
            print(f"Error fetching CloudWatch metrics for instance {instance_id}: {e}")
            return {
                "network_in": 0.0,
                "network_out": 0.0,
                "total_traffic_gb": 0.0,
                "status_check_failed": 0.0,
                "status_check_failed_instance": 0.0,
                "status_check_failed_system": 0.0,
            }

    def _calculate_volume_cost(
        self,
        volume_type: str,
        size_gb: int,
        iops: int | None = None,
        throughput: int | None = None,
    ) -> dict[str, float]:
        """
        Calculate comprehensive EBS volume monthly cost including IOPS and throughput.

        Args:
            volume_type: Volume type (gp2, gp3, io1, io2, st1, sc1, standard)
            size_gb: Volume size in GB
            iops: Provisioned IOPS (for io1/io2/gp3 with custom IOPS)
            throughput: Provisioned throughput in MBps (for gp3 only)

        Returns:
            Dict with:
                - total_monthly_cost: Total monthly cost
                - storage_cost: GB storage cost
                - iops_cost: IOPS provisioning cost
                - throughput_cost: Throughput provisioning cost
                - cost_breakdown: Detailed breakdown string
        """
        # Cost components
        storage_cost = 0.0
        iops_cost = 0.0
        throughput_cost = 0.0

        # 1. Calculate storage cost (GB × price/GB)
        price_key = f"ebs_{volume_type}_per_gb"
        price_per_gb = self.PRICING.get(price_key, self.PRICING["ebs_gp2_per_gb"])
        storage_cost = size_gb * price_per_gb

        # 2. Calculate IOPS cost
        if volume_type == "gp3" and iops and iops > 3000:
            # gp3: 3000 IOPS baseline included, $0.005/IOPS above baseline
            iops_cost = (iops - 3000) * 0.005
        elif volume_type in ["io1", "io2"] and iops:
            # io1/io2: $0.065/IOPS/month for all provisioned IOPS
            # Note: io2 has tiered pricing (≤32K IOPS: $0.065, 32K-64K: $0.046)
            if volume_type == "io2" and iops > 32000:
                # First 32K IOPS at $0.065, rest at $0.046
                iops_cost = (32000 * 0.065) + ((iops - 32000) * 0.046)
            else:
                iops_cost = iops * 0.065

        # 3. Calculate throughput cost (gp3 only)
        if volume_type == "gp3" and throughput and throughput > 125:
            # gp3: 125 MBps baseline included, $0.04/MBps above baseline
            throughput_cost = (throughput - 125) * 0.04

        # Total cost
        total_monthly_cost = storage_cost + iops_cost + throughput_cost

        # Build cost breakdown string
        breakdown_parts = [f"{size_gb} GB × ${price_per_gb:.3f} = ${storage_cost:.2f}"]
        if iops_cost > 0:
            if volume_type == "gp3":
                breakdown_parts.append(f"IOPS: ({iops} - 3000) × $0.005 = ${iops_cost:.2f}")
            elif volume_type == "io2" and iops > 32000:
                breakdown_parts.append(
                    f"IOPS: (32K × $0.065) + ({iops - 32000} × $0.046) = ${iops_cost:.2f}"
                )
            else:
                breakdown_parts.append(f"IOPS: {iops} × $0.065 = ${iops_cost:.2f}")
        if throughput_cost > 0:
            breakdown_parts.append(f"Throughput: ({throughput} - 125) MBps × $0.04 = ${throughput_cost:.2f}")

        return {
            "total_monthly_cost": round(total_monthly_cost, 2),
            "storage_cost": round(storage_cost, 2),
            "iops_cost": round(iops_cost, 2),
            "throughput_cost": round(throughput_cost, 2),
            "cost_breakdown": " + ".join(breakdown_parts),
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
                    iops = volume.get("Iops")  # Provisioned IOPS (io1/io2/gp3)
                    throughput = volume.get("Throughput")  # Provisioned throughput (gp3 only)

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

                    # Calculate monthly cost using comprehensive cost calculator (includes IOPS + throughput)
                    cost_data = self._calculate_volume_cost(volume_type, size_gb, iops, throughput)
                    monthly_cost = cost_data["total_monthly_cost"]

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
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": orphan_type,  # 'unattached', 'attached_never_used', 'attached_idle'
                        "usage_history": usage_history,
                        "volume_state": volume_state,
                        "is_attached": is_attached,
                        # Cost breakdown (new)
                        "iops": iops,
                        "throughput": throughput,
                        "cost_breakdown": cost_data["cost_breakdown"],
                        "storage_cost": cost_data["storage_cost"],
                        "iops_cost": cost_data["iops_cost"],
                        "throughput_cost": cost_data["throughput_cost"],
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

    async def scan_volumes_on_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 2: Scan for EBS volumes attached to stopped EC2 instances >30 days.

        Volumes attached to stopped instances are fully charged (GB + IOPS + throughput)
        while the instance compute is free. This represents waste if the instance
        has been stopped for an extended period.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules (uses defaults if None)

        Returns:
            List of EBS volume resources on stopped instances
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        # Check if detection is enabled
        if not detection_rules.get("enabled", True):
            return orphans

        min_stopped_days = detection_rules.get("min_stopped_days", 30)
        min_age_days = detection_rules.get("min_age_days", 7)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all stopped instances
                response = await ec2.describe_instances(
                    Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
                )

                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        instance_type = instance["InstanceType"]
                        instance_state = instance["State"]["Name"]
                        state_transition_time = instance.get("StateTransitionReason", "")

                        # Try to parse stopped duration from StateTransitionReason
                        # Format: "User initiated (YYYY-MM-DD HH:MM:SS GMT)"
                        stopped_since = None
                        stopped_days = 0

                        # Get launch time as fallback
                        launch_time = instance.get("LaunchTime")

                        # Try to get state transition time from tags or other sources
                        # For now, we'll use the instance launch time as an approximation
                        # In production, you might want to track this in CloudWatch or tags
                        if launch_time:
                            # Estimate: if instance was launched long ago and is stopped now,
                            # we consider it as potentially long-stopped
                            # This is a simplified approach
                            now = datetime.now(timezone.utc)
                            instance_age_days = (now - launch_time).days

                            # We can't know exactly when it was stopped without additional tracking
                            # For conservative approach: flag only if instance is old enough
                            if instance_age_days < min_stopped_days:
                                continue  # Instance too young, skip

                            # Assume it's been stopped for a significant portion of its lifetime
                            # (This is imperfect but conservative)
                            stopped_days = min_stopped_days  # Conservative estimate

                        # Get attached volumes
                        for bdm in instance.get("BlockDeviceMappings", []):
                            if "Ebs" not in bdm:
                                continue

                            volume_id = bdm["Ebs"].get("VolumeId")
                            if not volume_id:
                                continue

                            # Get volume details
                            volume_response = await ec2.describe_volumes(VolumeIds=[volume_id])
                            if not volume_response.get("Volumes"):
                                continue

                            volume = volume_response["Volumes"][0]
                            size_gb = volume["Size"]
                            volume_type = volume["VolumeType"]
                            created_at = volume["CreateTime"]
                            iops = volume.get("Iops")
                            throughput = volume.get("Throughput")

                            # Calculate volume age
                            volume_age_days = (datetime.now(timezone.utc) - created_at).days

                            # Skip if volume is too young
                            if volume_age_days < min_age_days:
                                continue

                            # Calculate cost (volume continues to be charged even when instance is stopped)
                            cost_data = self._calculate_volume_cost(volume_type, size_gb, iops, throughput)
                            monthly_cost = cost_data["total_monthly_cost"]

                            # Extract volume name from tags
                            volume_name = None
                            for tag in volume.get("Tags", []):
                                if tag["Key"] == "Name":
                                    volume_name = tag["Value"]
                                    break

                            # Extract instance name from tags
                            instance_name = None
                            for tag in instance.get("Tags", []):
                                if tag["Key"] == "Name":
                                    instance_name = tag["Value"]
                                    break

                            # Determine confidence level based on stopped duration
                            if stopped_days >= 90:
                                confidence = "critical"
                                reason = f"Volume on instance stopped for {stopped_days}+ days (instance: {instance_name or instance_id})"
                            elif stopped_days >= 60:
                                confidence = "high"
                                reason = f"Volume on instance stopped for {stopped_days}+ days (instance: {instance_name or instance_id})"
                            elif stopped_days >= min_stopped_days:
                                confidence = "medium"
                                reason = f"Volume on instance stopped for {stopped_days}+ days (instance: {instance_name or instance_id})"
                            else:
                                confidence = "low"
                                reason = f"Volume on recently stopped instance (instance: {instance_name or instance_id})"

                            # Build metadata
                            metadata = {
                                "size_gb": size_gb,
                                "volume_type": volume_type,
                                "created_at": created_at.isoformat(),
                                "availability_zone": volume["AvailabilityZone"],
                                "encrypted": volume.get("Encrypted", False),
                                "age_days": volume_age_days,
                                "confidence": confidence,
                                "confidence_level": self._calculate_confidence_level(stopped_days, detection_rules),
                                "orphan_reason": reason,
                                "orphan_type": "volume_on_stopped_instance",
                                "volume_state": "in-use",
                                "is_attached": True,
                                "attached_instance_id": instance_id,
                                "instance_name": instance_name,
                                "instance_type": instance_type,
                                "instance_state": instance_state,
                                "stopped_days": stopped_days,
                                "device": bdm.get("DeviceName", "Unknown"),
                                # Cost breakdown
                                "iops": iops,
                                "throughput": throughput,
                                "cost_breakdown": cost_data["cost_breakdown"],
                                "storage_cost": cost_data["storage_cost"],
                                "iops_cost": cost_data["iops_cost"],
                                "throughput_cost": cost_data["throughput_cost"],
                            }

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="ebs_volume",
                                    resource_id=volume_id,
                                    resource_name=volume_name,
                                    region=region,
                                    estimated_monthly_cost=round(monthly_cost, 2),
                                    resource_metadata=metadata,
                                )
                            )

        except ClientError as e:
            print(f"Error scanning volumes on stopped instances in {region}: {e}")

        return orphans

    async def scan_gp2_migration_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 3: Scan for gp2 volumes that should be migrated to gp3 (~20% savings).

        gp2 is the older generation General Purpose SSD. gp3 is newer, cheaper, and more performant.
        Migrating from gp2 ($0.10/GB) to gp3 ($0.08/GB) saves ~20% with same or better performance.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of gp2 volumes recommended for migration
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 30)
        min_size_gb = detection_rules.get("min_size_gb", 100)  # Small volumes = marginal savings

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["gp2"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    created_at = volume["CreateTime"]
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    # Skip if volume is too young or too small
                    if age_days < min_age_days or size_gb < min_size_gb:
                        continue

                    # Calculate current gp2 cost
                    current_cost = size_gb * self.PRICING["ebs_gp2_per_gb"]

                    # Calculate gp3 cost (3000 IOPS + 125 MBps baseline included)
                    suggested_cost = size_gb * self.PRICING["ebs_gp3_per_gb"]
                    monthly_savings = current_cost - suggested_cost
                    savings_percent = (monthly_savings / current_cost) * 100

                    # Extract name from tags
                    name = None
                    for tag in volume.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    reason = f"gp2 volume ({size_gb} GB) should migrate to gp3 for ~{savings_percent:.0f}% cost savings (${monthly_savings:.2f}/month)"

                    metadata = {
                        "size_gb": size_gb,
                        "current_volume_type": "gp2",
                        "suggested_volume_type": "gp3",
                        "created_at": created_at.isoformat(),
                        "availability_zone": volume["AvailabilityZone"],
                        "encrypted": volume.get("Encrypted", False),
                        "age_days": age_days,
                        "current_monthly_cost": round(current_cost, 2),
                        "suggested_monthly_cost": round(suggested_cost, 2),
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "savings_percent": round(savings_percent, 1),
                        "orphan_reason": reason,
                        "orphan_type": "gp2_migration_opportunity",
                        "suggested_iops": 3000,  # gp3 baseline
                        "suggested_throughput": 125,  # gp3 baseline
                        "migration_notes": "gp3 provides same or better performance with 20% cost reduction",
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_savings, 2),  # Potential savings
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning gp2 migration opportunities in {region}: {e}")

        return orphans

    async def scan_unnecessary_io2_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 4: Scan for io2 volumes without compliance requirements (should be io1).

        io2 provides 99.999% durability (vs io1's 99.9%) at same cost. Only needed for
        compliance/critical workloads. Dev/test environments don't need io2.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of io2 volumes that could be downgraded to io1
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 30)
        compliance_tags = detection_rules.get("compliance_tags", [
            "compliance", "hipaa", "pci-dss", "sox", "gdpr", "iso27001", "critical"
        ])

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["io2"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    iops = volume.get("Iops", 0)
                    created_at = volume["CreateTime"]
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    if age_days < min_age_days:
                        continue

                    # Check for compliance tags
                    has_compliance_tag = False
                    environment_tag = None
                    volume_tags = {tag["Key"].lower(): tag["Value"].lower() for tag in volume.get("Tags", [])}

                    for tag_key, tag_value in volume_tags.items():
                        if any(comp_tag.lower() in tag_value for comp_tag in compliance_tags):
                            has_compliance_tag = True
                            break

                    # Check environment tag
                    if "environment" in volume_tags:
                        environment_tag = volume_tags["environment"]

                    # Flag if no compliance tags AND in dev/test environment
                    is_waste = (not has_compliance_tag) or (environment_tag in ["dev", "development", "test", "staging"])

                    if not is_waste:
                        continue

                    # Calculate cost (same for io1 and io2, but io2 is overkill)
                    cost_data = self._calculate_volume_cost("io2", size_gb, iops)
                    monthly_cost = cost_data["total_monthly_cost"]

                    name = volume_tags.get("name")
                    reason = f"io2 volume in {environment_tag or 'non-compliance'} environment - io1 durability (99.9%) is sufficient"

                    metadata = {
                        "size_gb": size_gb,
                        "current_volume_type": "io2",
                        "suggested_volume_type": "io1",
                        "iops": iops,
                        "created_at": created_at.isoformat(),
                        "availability_zone": volume["AvailabilityZone"],
                        "encrypted": volume.get("Encrypted", False),
                        "age_days": age_days,
                        "environment": environment_tag,
                        "has_compliance_tags": has_compliance_tag,
                        "orphan_reason": reason,
                        "orphan_type": "unnecessary_io2",
                        "cost_breakdown": cost_data["cost_breakdown"],
                        "recommendation": "Migrate to io1 (same cost, less durability but sufficient for non-compliance workloads)",
                    }

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
            print(f"Error scanning unnecessary io2 volumes in {region}: {e}")

        return orphans

    async def scan_overprovisioned_iops_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 5: Scan for volumes with over-provisioned IOPS (>2× baseline needed).

        Detects io1/io2/gp3 volumes with IOPS provisioned significantly higher than
        necessary based on volume size and AWS best practices.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of volumes with excessive IOPS provisioning
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 30)
        iops_overprovisioning_factor = detection_rules.get("iops_overprovisioning_factor", 2.0)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Scan io1, io2, and gp3 volumes (types that support provisioned IOPS)
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["io1", "io2", "gp3"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    volume_type = volume["VolumeType"]
                    iops = volume.get("Iops", 0)
                    throughput = volume.get("Throughput")
                    created_at = volume["CreateTime"]
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    if age_days < min_age_days:
                        continue

                    # Calculate baseline IOPS based on volume type and size
                    if volume_type == "gp3":
                        baseline_iops = 3000  # gp3 baseline (free)
                    elif volume_type in ["io1", "io2"]:
                        # AWS recommends 50 IOPS/GB ratio, but conservative baseline is 10-30 IOPS/GB
                        baseline_iops = size_gb * 10  # Conservative baseline
                    else:
                        continue

                    # Check if provisioned IOPS > baseline × factor
                    if not iops or iops <= baseline_iops * iops_overprovisioning_factor:
                        continue

                    # Calculate recommended IOPS (baseline × 1.5 for safety buffer)
                    recommended_iops = int(baseline_iops * 1.5)

                    # Calculate current and recommended costs
                    current_cost_data = self._calculate_volume_cost(volume_type, size_gb, iops, throughput)
                    recommended_cost_data = self._calculate_volume_cost(volume_type, size_gb, recommended_iops, throughput)

                    monthly_savings = current_cost_data["total_monthly_cost"] - recommended_cost_data["total_monthly_cost"]
                    savings_percent = (monthly_savings / current_cost_data["total_monthly_cost"]) * 100

                    # Extract name
                    name = None
                    for tag in volume.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    iops_ratio = iops / baseline_iops if baseline_iops > 0 else 0
                    reason = f"{volume_type} volume with over-provisioned IOPS ({iops} IOPS, {iops_ratio:.1f}× baseline) - reduce to {recommended_iops} IOPS for ${monthly_savings:.2f}/month savings"

                    metadata = {
                        "size_gb": size_gb,
                        "volume_type": volume_type,
                        "provisioned_iops": iops,
                        "baseline_iops": baseline_iops,
                        "recommended_iops": recommended_iops,
                        "iops_ratio": round(iops_ratio, 2),
                        "created_at": created_at.isoformat(),
                        "availability_zone": volume["AvailabilityZone"],
                        "encrypted": volume.get("Encrypted", False),
                        "age_days": age_days,
                        "current_monthly_cost": current_cost_data["total_monthly_cost"],
                        "recommended_monthly_cost": recommended_cost_data["total_monthly_cost"],
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "savings_percent": round(savings_percent, 1),
                        "orphan_reason": reason,
                        "orphan_type": "overprovisioned_iops",
                        "current_cost_breakdown": current_cost_data["cost_breakdown"],
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_savings, 2),
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning overprovisioned IOPS volumes in {region}: {e}")

        return orphans

    async def scan_overprovisioned_throughput_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 6: Scan for gp3 volumes with over-provisioned throughput (>125 MBps baseline).

        gp3 includes 125 MBps throughput for free. Additional throughput costs $0.04/MBps/month.
        Flags volumes with high throughput in non-high-throughput workloads.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of gp3 volumes with excessive throughput provisioning
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 30)
        baseline_throughput = detection_rules.get("baseline_throughput_mbps", 125)
        high_throughput_tags = detection_rules.get("high_throughput_workload_tags", [
            "database", "analytics", "bigdata", "ml", "etl", "data-warehouse"
        ])

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["gp3"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    iops = volume.get("Iops", 3000)
                    throughput = volume.get("Throughput")
                    created_at = volume["CreateTime"]
                    age_days = (datetime.now(timezone.utc) - created_at).days

                    # Skip if no provisioned throughput or within baseline
                    if not throughput or throughput <= baseline_throughput:
                        continue

                    if age_days < min_age_days:
                        continue

                    # Check for high-throughput workload tags
                    volume_tags = {tag["Key"].lower(): tag["Value"].lower() for tag in volume.get("Tags", [])}
                    has_high_throughput_tag = any(
                        ht_tag.lower() in str(volume_tags.values()).lower()
                        for ht_tag in high_throughput_tags
                    )

                    # Check environment
                    environment = volume_tags.get("environment", "")

                    # Flag if high throughput in dev/test or no high-throughput workload tags
                    should_flag = (environment in ["dev", "development", "test", "staging"]) or (not has_high_throughput_tag)

                    if not should_flag:
                        continue

                    # Calculate costs
                    current_cost_data = self._calculate_volume_cost("gp3", size_gb, iops, throughput)
                    recommended_cost_data = self._calculate_volume_cost("gp3", size_gb, iops, baseline_throughput)

                    monthly_savings = current_cost_data["throughput_cost"]  # All throughput above baseline
                    savings_percent = (monthly_savings / current_cost_data["total_monthly_cost"]) * 100

                    name = volume_tags.get("name")

                    reason = f"gp3 volume with unnecessary throughput ({throughput} MBps vs {baseline_throughput} MBps baseline) in {environment or 'non-high-throughput'} workload - ${monthly_savings:.2f}/month savings"

                    metadata = {
                        "size_gb": size_gb,
                        "volume_type": "gp3",
                        "provisioned_throughput": throughput,
                        "baseline_throughput": baseline_throughput,
                        "recommended_throughput": baseline_throughput,
                        "created_at": created_at.isoformat(),
                        "availability_zone": volume["AvailabilityZone"],
                        "encrypted": volume.get("Encrypted", False),
                        "age_days": age_days,
                        "environment": environment,
                        "has_high_throughput_workload_tags": has_high_throughput_tag,
                        "current_monthly_cost": current_cost_data["total_monthly_cost"],
                        "recommended_monthly_cost": recommended_cost_data["total_monthly_cost"],
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "savings_percent": round(savings_percent, 1),
                        "orphan_reason": reason,
                        "orphan_type": "overprovisioned_throughput",
                        "current_cost_breakdown": current_cost_data["cost_breakdown"],
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_savings, 2),
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning overprovisioned throughput volumes in {region}: {e}")

        return orphans

    async def scan_low_iops_usage_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 8: Scan for volumes with provisioned IOPS but low actual usage (<30%).

        Uses CloudWatch metrics to detect io1/io2/gp3 volumes where actual IOPS usage
        is significantly lower than provisioned capacity.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of volumes with under-utilized IOPS
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_observation_days = detection_rules.get("min_observation_days", 30)
        max_iops_utilization = detection_rules.get("max_iops_utilization_percent", 30) / 100  # Convert to decimal
        safety_buffer = detection_rules.get("safety_buffer_factor", 1.5)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["io1", "io2", "gp3"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    volume_type = volume["VolumeType"]
                    iops = volume.get("Iops")
                    throughput = volume.get("Throughput")

                    # Skip if no provisioned IOPS or baseline only (gp3 with 3000 IOPS)
                    if not iops or (volume_type == "gp3" and iops <= 3000):
                        continue

                    # Get IOPS usage metrics from CloudWatch
                    metrics = await self._get_volume_metrics(
                        volume_id, region,
                        ["VolumeReadOps", "VolumeWriteOps"],
                        period_days=min_observation_days,
                        statistic="Average"
                    )

                    avg_read_ops = metrics.get("VolumeReadOps", 0)
                    avg_write_ops = metrics.get("VolumeWriteOps", 0)
                    total_avg_iops = avg_read_ops + avg_write_ops

                    # Calculate IOPS utilization
                    iops_utilization = total_avg_iops / iops if iops > 0 else 0

                    # Skip if utilization is above threshold
                    if iops_utilization >= max_iops_utilization:
                        continue

                    # Calculate recommended IOPS (actual usage × safety buffer)
                    if volume_type == "gp3":
                        recommended_iops = max(3000, int(total_avg_iops * safety_buffer))  # Min 3000 baseline
                    else:  # io1/io2
                        recommended_iops = max(100, int(total_avg_iops * safety_buffer))  # Min 100 IOPS

                    # Calculate costs
                    current_cost_data = self._calculate_volume_cost(volume_type, size_gb, iops, throughput)
                    recommended_cost_data = self._calculate_volume_cost(volume_type, size_gb, recommended_iops, throughput)

                    monthly_savings = current_cost_data["total_monthly_cost"] - recommended_cost_data["total_monthly_cost"]

                    if monthly_savings <= 0:
                        continue

                    name = None
                    for tag in volume.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    reason = f"{volume_type} volume with {iops_utilization*100:.1f}% IOPS utilization ({int(total_avg_iops)} avg vs {iops} provisioned) - reduce to {recommended_iops} IOPS for ${monthly_savings:.2f}/month savings"

                    metadata = {
                        "size_gb": size_gb,
                        "volume_type": volume_type,
                        "provisioned_iops": iops,
                        "avg_read_ops_per_second": round(avg_read_ops, 2),
                        "avg_write_ops_per_second": round(avg_write_ops, 2),
                        "total_avg_iops": round(total_avg_iops, 2),
                        "iops_utilization_percent": round(iops_utilization * 100, 1),
                        "recommended_iops": recommended_iops,
                        "observation_period_days": min_observation_days,
                        "current_monthly_cost": current_cost_data["total_monthly_cost"],
                        "recommended_monthly_cost": recommended_cost_data["total_monthly_cost"],
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "orphan_reason": reason,
                        "orphan_type": "low_iops_usage",
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_savings, 2),
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning low IOPS usage volumes in {region}: {e}")

        return orphans

    async def scan_low_throughput_usage_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 9: Scan for gp3 volumes with provisioned throughput but low usage (<30%).

        Uses CloudWatch metrics to detect gp3 volumes where actual throughput usage
        is significantly lower than provisioned capacity.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of gp3 volumes with under-utilized throughput
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_observation_days = detection_rules.get("min_observation_days", 30)
        max_throughput_utilization = detection_rules.get("max_throughput_utilization_percent", 30) / 100
        baseline_throughput = detection_rules.get("baseline_throughput_mbps", 125)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["gp3"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    iops = volume.get("Iops", 3000)
                    throughput = volume.get("Throughput")

                    # Skip if no provisioned throughput above baseline
                    if not throughput or throughput <= baseline_throughput:
                        continue

                    # Get throughput metrics from CloudWatch
                    metrics = await self._get_volume_metrics(
                        volume_id, region,
                        ["VolumeReadBytes", "VolumeWriteBytes"],
                        period_days=min_observation_days,
                        statistic="Average"
                    )

                    avg_read_bytes = metrics.get("VolumeReadBytes", 0)
                    avg_write_bytes = metrics.get("VolumeWriteBytes", 0)

                    # Convert bytes/sec to MBps
                    total_avg_throughput_mbps = (avg_read_bytes + avg_write_bytes) / (1024 * 1024)

                    # Calculate throughput utilization
                    throughput_utilization = total_avg_throughput_mbps / throughput if throughput > 0 else 0

                    # Skip if utilization is above threshold
                    if throughput_utilization >= max_throughput_utilization:
                        continue

                    # Calculate costs
                    current_cost_data = self._calculate_volume_cost("gp3", size_gb, iops, throughput)
                    recommended_cost_data = self._calculate_volume_cost("gp3", size_gb, iops, baseline_throughput)

                    monthly_savings = current_cost_data["throughput_cost"]  # All throughput cost above baseline

                    if monthly_savings <= 0:
                        continue

                    name = None
                    for tag in volume.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    reason = f"gp3 volume with {throughput_utilization*100:.1f}% throughput utilization ({total_avg_throughput_mbps:.1f} MBps avg vs {throughput} MBps provisioned) - reduce to {baseline_throughput} MBps baseline for ${monthly_savings:.2f}/month savings"

                    metadata = {
                        "size_gb": size_gb,
                        "volume_type": "gp3",
                        "provisioned_throughput_mbps": throughput,
                        "avg_read_mbps": round(avg_read_bytes / (1024 * 1024), 2),
                        "avg_write_mbps": round(avg_write_bytes / (1024 * 1024), 2),
                        "total_avg_throughput_mbps": round(total_avg_throughput_mbps, 2),
                        "throughput_utilization_percent": round(throughput_utilization * 100, 1),
                        "recommended_throughput_mbps": baseline_throughput,
                        "observation_period_days": min_observation_days,
                        "current_monthly_cost": current_cost_data["total_monthly_cost"],
                        "recommended_monthly_cost": recommended_cost_data["total_monthly_cost"],
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "orphan_reason": reason,
                        "orphan_type": "low_throughput_usage",
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_savings, 2),
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning low throughput usage volumes in {region}: {e}")

        return orphans

    async def scan_volume_type_downgrade_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        SCENARIO 10: Scan for volume type downgrade opportunities (io1→gp3 etc).

        Uses CloudWatch to analyze actual usage and recommend cheaper volume types
        that can handle the workload (e.g., io1 with 8K IOPS → gp3 with 10K IOPS saves 90%).

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of volumes with downgrade opportunities
        """
        orphans: list[OrphanResourceData] = []

        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("ebs_volume", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_observation_days = detection_rules.get("min_observation_days", 30)
        min_savings_percent = detection_rules.get("min_savings_percent", 20)
        safety_margin = detection_rules.get("safety_margin_iops", 1.5)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Focus on expensive volume types (io1, io2)
                response = await ec2.describe_volumes(
                    Filters=[{"Name": "volume-type", "Values": ["io1", "io2"]}]
                )

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    volume_type = volume["VolumeType"]
                    iops = volume.get("Iops", 0)

                    # Get actual usage metrics
                    metrics = await self._get_volume_metrics(
                        volume_id, region,
                        ["VolumeReadOps", "VolumeWriteOps", "VolumeReadBytes", "VolumeWriteBytes"],
                        period_days=min_observation_days,
                        statistic="Average"
                    )

                    avg_iops = metrics.get("VolumeReadOps", 0) + metrics.get("VolumeWriteOps", 0)
                    avg_throughput_mbps = (metrics.get("VolumeReadBytes", 0) + metrics.get("VolumeWriteBytes", 0)) / (1024 * 1024)

                    # Check if gp3 can handle this workload
                    # gp3 limits: 16,000 IOPS max, 1,000 MBps max
                    required_iops = int(avg_iops * safety_margin)
                    required_throughput = int(avg_throughput_mbps * safety_margin)

                    if required_iops > 16000 or required_throughput > 1000:
                        continue  # gp3 cannot handle this workload

                    # Calculate current io1/io2 cost
                    current_cost_data = self._calculate_volume_cost(volume_type, size_gb, iops)

                    # Calculate gp3 cost with required IOPS and throughput
                    suggested_iops = max(3000, required_iops)  # gp3 baseline or higher
                    suggested_throughput = max(125, required_throughput)  # gp3 baseline or higher
                    suggested_cost_data = self._calculate_volume_cost("gp3", size_gb, suggested_iops, suggested_throughput)

                    monthly_savings = current_cost_data["total_monthly_cost"] - suggested_cost_data["total_monthly_cost"]
                    savings_percent = (monthly_savings / current_cost_data["total_monthly_cost"]) * 100

                    # Skip if savings below threshold
                    if savings_percent < min_savings_percent:
                        continue

                    name = None
                    for tag in volume.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    reason = f"{volume_type} volume can be downgraded to gp3 (current: {int(avg_iops)} IOPS avg, {avg_throughput_mbps:.1f} MBps avg) - migrate to gp3 ({suggested_iops} IOPS, {suggested_throughput} MBps) for ${monthly_savings:.2f}/month ({savings_percent:.0f}% savings)"

                    metadata = {
                        "size_gb": size_gb,
                        "current_volume_type": volume_type,
                        "suggested_volume_type": "gp3",
                        "avg_iops": round(avg_iops, 2),
                        "avg_throughput_mbps": round(avg_throughput_mbps, 2),
                        "suggested_iops": suggested_iops,
                        "suggested_throughput": suggested_throughput,
                        "observation_period_days": min_observation_days,
                        "current_monthly_cost": current_cost_data["total_monthly_cost"],
                        "suggested_monthly_cost": suggested_cost_data["total_monthly_cost"],
                        "potential_monthly_savings": round(monthly_savings, 2),
                        "savings_percent": round(savings_percent, 1),
                        "orphan_reason": reason,
                        "orphan_type": "volume_type_downgrade_opportunity",
                        "downgrade_rationale": f"gp3 can handle {required_iops} IOPS and {required_throughput} MBps (well within 16K/1000 limits)",
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="ebs_volume",
                            resource_id=volume_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=round(monthly_savings, 2),
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning volume type downgrade opportunities in {region}: {e}")

        return orphans

    async def scan_unassigned_ips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs that are wasting money.

        SCENARIO 1: Unassociated Elastic IPs
        - EIPs not associated with any instance or network interface ($3.60/month waste)

        SCENARIO 2: EIPs on stopped EC2 instances
        - EIPs associated to stopped instances (still charged $3.60/month)
        - Calculates stopped_days to determine confidence level

        Uses AWS native AllocationTime attribute (no manual tags required).

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
        min_stopped_days = detection_rules.get("min_stopped_days", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_addresses()

                # Get all instances to check their state and launch time
                instances_response = await ec2.describe_instances()
                instance_info = {}  # {instance_id: {"state": str, "state_transition_reason": str}}
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_info[instance["InstanceId"]] = {
                            "state": instance["State"]["Name"],
                            "state_transition_reason": instance.get("StateTransitionReason", ""),
                            "launch_time": instance.get("LaunchTime"),
                        }

                for address in response.get("Addresses", []):
                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    association_id = address.get("AssociationId")
                    instance_id = address.get("InstanceId")
                    network_interface_id = address.get("NetworkInterfaceId")

                    # **KEY FIX**: Use AWS native AllocationTime instead of manual tag
                    allocation_time = address.get("AllocationTime")

                    # Calculate age using native AllocationTime
                    if not allocation_time:
                        continue  # Skip if no allocation time (shouldn't happen for VPC EIPs)

                    age_days = (datetime.now(timezone.utc) - allocation_time).days

                    # Determine orphan status
                    should_flag = False
                    orphan_type = ""
                    stopped_days = 0

                    if not association_id:
                        # SCENARIO 1: Unassociated Elastic IP
                        if age_days >= min_age_days:
                            should_flag = True
                            orphan_type = "unassociated"

                    elif instance_id and instance_id in instance_info:
                        # SCENARIO 2: EIP on stopped EC2 instance
                        instance_state = instance_info[instance_id]["state"]
                        if instance_state == "stopped":
                            # Parse StateTransitionReason to calculate stopped_days
                            # Format: "User initiated (2024-01-15 14:32:15 GMT)"
                            state_transition_reason = instance_info[instance_id]["state_transition_reason"]
                            try:
                                # Extract date from StateTransitionReason
                                import re
                                date_match = re.search(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", state_transition_reason)
                                if date_match:
                                    stopped_time_str = date_match.group(1)
                                    stopped_time = datetime.strptime(stopped_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                                    stopped_days = (datetime.now(timezone.utc) - stopped_time).days
                            except Exception:
                                # Fallback: assume stopped recently if we can't parse
                                stopped_days = 0

                            if stopped_days >= min_stopped_days:
                                should_flag = True
                                orphan_type = "associated_stopped_instance"

                    if not should_flag:
                        continue

                    # Extract name from tags
                    name = None
                    tags = address.get("Tags", [])
                    for tag in tags:
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    # Determine confidence and reason
                    if orphan_type == "unassociated":
                        confidence = "high" if age_days >= confidence_threshold_days else "medium"
                        reason = f"Unassociated for {age_days} days ($3.60/month waste)"

                    elif orphan_type == "associated_stopped_instance":
                        confidence = "critical" if stopped_days >= 90 else ("high" if stopped_days >= confidence_threshold_days else "medium")
                        reason = f"Associated to stopped instance {instance_id} for {stopped_days} days ($3.60/month waste)"

                    else:
                        confidence = "low"
                        reason = "Detected as potentially orphaned"

                    # Calculate already wasted cost
                    already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                    # Build metadata
                    metadata = {
                        "public_ip": public_ip,
                        "domain": address.get("Domain", "vpc"),
                        "allocation_time": allocation_time.isoformat(),
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": orphan_type,
                        "is_associated": bool(association_id),
                        "already_wasted": already_wasted,
                    }

                    # SCENARIO 2 specific metadata
                    if orphan_type == "associated_stopped_instance" and instance_id:
                        metadata["associated_instance_id"] = instance_id
                        metadata["instance_state"] = "stopped"
                        metadata["stopped_days"] = stopped_days

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
            print(f"Error scanning Elastic IPs (Scenarios 1-2) in {region}: {e}")

        return orphans

    async def scan_additional_eips_per_instance(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for EC2 instances with multiple Elastic IPs (SCENARIO 3).

        Most instances only need 1 EIP. Multiple EIPs per instance indicate:
        - Over-provisioning (unnecessary redundancy)
        - Misconfiguration (forgot to clean up old IPs)
        - Special use cases (multi-NIC, HA/failover) - justifiable via tags

        Each additional EIP costs $3.60/month.

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources (additional IPs beyond the first)
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        max_eips_per_instance = detection_rules.get("max_eips_per_instance", 1)
        allow_multiple_eips_tags = detection_rules.get("allow_multiple_eips_tags", [
            "multi-nic", "ha", "high-availability", "active-active", "failover", "floating-ip"
        ])
        min_age_days = detection_rules.get("min_age_days", 3)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_addresses()

                # Get instance tags to check for justification
                instances_response = await ec2.describe_instances()
                instance_tags = {}  # {instance_id: [tag_keys]}
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        tags = [tag["Key"].lower() for tag in instance.get("Tags", [])]
                        instance_tags[instance_id] = tags

                # Group EIPs by instance
                instance_eips = {}  # {instance_id: [eip_data]}
                for address in response.get("Addresses", []):
                    instance_id = address.get("InstanceId")
                    if instance_id:  # Only consider IPs associated with instances
                        if instance_id not in instance_eips:
                            instance_eips[instance_id] = []
                        instance_eips[instance_id].append(address)

                # Find instances with more than max_eips_per_instance
                for instance_id, eips in instance_eips.items():
                    if len(eips) <= max_eips_per_instance:
                        continue  # Within limit

                    # Check if instance has justification tags
                    tags = instance_tags.get(instance_id, [])
                    has_justification = any(tag in tags for tag in [t.lower() for t in allow_multiple_eips_tags])

                    if has_justification:
                        continue  # Skip - multiple EIPs are justified

                    # Flag additional EIPs (beyond the first one)
                    for i, address in enumerate(sorted(eips, key=lambda x: x.get("AllocationTime", datetime.min))):
                        if i < max_eips_per_instance:
                            continue  # Keep the first N EIPs

                        allocation_id = address.get("AllocationId", "N/A")
                        public_ip = address.get("PublicIp", "Unknown")
                        allocation_time = address.get("AllocationTime")

                        if not allocation_time:
                            continue

                        age_days = (datetime.now(timezone.utc) - allocation_time).days
                        if age_days < min_age_days:
                            continue

                        # Extract name from tags
                        name = None
                        for tag in address.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        # Confidence based on age
                        confidence = "high" if age_days >= 30 else "medium"
                        reason = f"Instance {instance_id} has {len(eips)} EIPs (max {max_eips_per_instance} recommended). Additional EIP #{i+1} wastes $3.60/month."

                        already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                        metadata = {
                            "public_ip": public_ip,
                            "allocation_time": allocation_time.isoformat(),
                            "age_days": age_days,
                            "confidence": confidence,
                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                            "orphan_reason": reason,
                            "orphan_type": "additional_eip_per_instance",
                            "associated_instance_id": instance_id,
                            "total_eips_on_instance": len(eips),
                            "eip_index": i + 1,
                            "already_wasted": already_wasted,
                        }

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
            print(f"Error scanning additional EIPs per instance (Scenario 3) in {region}: {e}")

        return orphans

    async def scan_eips_on_detached_enis(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs associated with detached ENIs (SCENARIO 4).

        Detects:
        - EIPs associated with ENIs (Elastic Network Interfaces) that are not attached to instances
        - These EIPs are still charged ($3.60/month) even though the ENI is detached
        - Common after instance termination, ENI manual detachment, or configuration changes

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources on detached ENIs
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        detached_eni_min_days = detection_rules.get("detached_eni_min_days", 7)
        min_age_days = detection_rules.get("min_age_days", 3)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all EIPs
                eips_response = await ec2.describe_addresses()

                # Get all ENIs to check their attachment status
                enis_response = await ec2.describe_network_interfaces()
                eni_attachment_info = {}  # {eni_id: {"attached": bool, "attachment_time": datetime}}
                for eni in enis_response.get("NetworkInterfaces", []):
                    eni_id = eni["NetworkInterfaceId"]
                    attachment = eni.get("Attachment")
                    eni_attachment_info[eni_id] = {
                        "attached": attachment is not None and attachment.get("Status") == "attached",
                        "attachment_time": attachment.get("AttachTime") if attachment else None,
                    }

                for address in eips_response.get("Addresses", []):
                    network_interface_id = address.get("NetworkInterfaceId")

                    # Only consider EIPs associated with ENIs (not directly with instances)
                    if not network_interface_id:
                        continue

                    instance_id = address.get("InstanceId")
                    if instance_id:
                        # Skip - ENI is attached to instance (handled by other scenarios)
                        continue

                    # Check if ENI is detached
                    eni_info = eni_attachment_info.get(network_interface_id)
                    if not eni_info or eni_info["attached"]:
                        continue  # ENI is attached or not found

                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    if not allocation_time:
                        continue

                    age_days = (datetime.now(timezone.utc) - allocation_time).days
                    if age_days < min_age_days:
                        continue

                    # Calculate detached days (approximation - we don't have exact detachment time)
                    # We use EIP allocation time as proxy for detachment duration
                    detached_days = age_days

                    if detached_days < detached_eni_min_days:
                        continue

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "critical" if detached_days >= 90 else ("high" if detached_days >= 30 else "medium")
                    reason = f"Associated with detached ENI {network_interface_id} for {detached_days}+ days ($3.60/month waste)"

                    already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat(),
                        "age_days": age_days,
                        "detached_days": detached_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "eip_on_detached_eni",
                        "network_interface_id": network_interface_id,
                        "already_wasted": already_wasted,
                    }

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
            print(f"Error scanning EIPs on detached ENIs (Scenario 4) in {region}: {e}")

        return orphans

    async def scan_never_used_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs that have NEVER been associated with any resource (SCENARIO 5).

        Detects:
        - EIPs allocated but never attached to any instance, ENI, or NAT Gateway
        - Strong indicator of forgotten/test allocation ($3.60/month waste)
        - Higher confidence than simple "unassociated" because it's never been used

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources that were never used
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_never_used_days = detection_rules.get("min_never_used_days", 7)
        min_age_days = detection_rules.get("min_age_days", 3)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_addresses()

                for address in response.get("Addresses", []):
                    # Check if EIP was NEVER associated
                    association_id = address.get("AssociationId")
                    instance_id = address.get("InstanceId")
                    network_interface_id = address.get("NetworkInterfaceId")

                    # AWS Elastic IP attributes:
                    # - If never attached: no AssociationId, no InstanceId, no NetworkInterfaceId
                    # - If currently unattached but was attached before: may have NetworkInterfaceId (of last attachment)
                    # The key is: if AssociationId is None AND NetworkInterfaceOwnerId is "amazon-elb" or missing

                    network_interface_owner_id = address.get("NetworkInterfaceOwnerId")

                    # Only flag if:
                    # 1. Not currently associated (no AssociationId)
                    # 2. No previous association trace (no NetworkInterfaceId OR NetworkInterfaceOwnerId is amazon service)
                    if association_id:
                        continue  # Currently associated

                    if network_interface_id and network_interface_owner_id not in [None, "amazon-elb", "amazon-aws"]:
                        # Was previously associated with user resource
                        continue

                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    if not allocation_time:
                        continue

                    age_days = (datetime.now(timezone.utc) - allocation_time).days

                    if age_days < min_age_days or age_days < min_never_used_days:
                        continue

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "critical" if age_days >= 90 else ("high" if age_days >= 30 else "medium")
                    reason = f"Never associated with any resource for {age_days} days ($3.60/month waste)"

                    already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat(),
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "never_used",
                        "already_wasted": already_wasted,
                    }

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
            print(f"Error scanning never-used EIPs (Scenario 5) in {region}: {e}")

        return orphans

    async def scan_eips_on_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs on unused NAT Gateways (SCENARIO 6).

        Detects:
        - EIPs associated with NAT Gateways that have minimal/no traffic
        - NAT Gateway ($32.40/month) + EIP ($3.60/month) = $36/month total waste
        - Uses CloudWatch metrics to determine if NAT Gateway is actually used
        - This is 10x more expensive than a standalone unused EIP!

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources on unused NAT Gateways
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        nat_gateway_min_idle_days = detection_rules.get("nat_gateway_min_idle_days", 30)
        nat_gateway_traffic_threshold_gb = detection_rules.get("nat_gateway_traffic_threshold_gb", 0.1)
        min_observation_days = detection_rules.get("min_observation_days", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all EIPs
                eips_response = await ec2.describe_addresses()

                # Get all NAT Gateways
                nat_gateways_response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                # Map EIPs to NAT Gateways
                eip_to_nat_gateway = {}  # {eip_allocation_id: nat_gateway_id}
                nat_gateway_info = {}  # {nat_gateway_id: {create_time, public_ip}}

                for nat_gw in nat_gateways_response.get("NatGateways", []):
                    nat_gw_id = nat_gw["NatGatewayId"]
                    create_time = nat_gw.get("CreateTime")

                    # Find EIP allocation ID for this NAT Gateway
                    for address_set in nat_gw.get("NatGatewayAddresses", []):
                        allocation_id = address_set.get("AllocationId")
                        public_ip = address_set.get("PublicIp")
                        if allocation_id:
                            eip_to_nat_gateway[allocation_id] = nat_gw_id
                            nat_gateway_info[nat_gw_id] = {
                                "create_time": create_time,
                                "public_ip": public_ip,
                            }

                # Check each EIP associated with NAT Gateway
                for address in eips_response.get("Addresses", []):
                    allocation_id = address.get("AllocationId", "N/A")

                    if allocation_id not in eip_to_nat_gateway:
                        continue  # Not associated with NAT Gateway

                    nat_gw_id = eip_to_nat_gateway[allocation_id]
                    nat_info = nat_gateway_info.get(nat_gw_id)

                    if not nat_info:
                        continue

                    create_time = nat_info["create_time"]
                    age_days = (datetime.now(timezone.utc) - create_time).days

                    if age_days < nat_gateway_min_idle_days:
                        continue

                    # Get CloudWatch metrics for NAT Gateway
                    metrics = await self._get_eip_nat_gateway_metrics(
                        nat_gw_id, region, period_days=min_observation_days
                    )

                    total_traffic_gb = metrics.get("total_traffic_gb", 0.0)

                    # Flag if traffic is below threshold
                    if total_traffic_gb > nat_gateway_traffic_threshold_gb:
                        continue  # NAT Gateway has sufficient traffic

                    # This NAT Gateway is unused!
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "critical" if age_days >= 90 else ("high" if age_days >= 60 else "medium")

                    # **KEY**: NAT Gateway + EIP = $32.40 + $3.60 = $36/month
                    nat_gateway_cost = 32.40
                    total_monthly_cost = nat_gateway_cost + self.PRICING["elastic_ip"]

                    reason = f"EIP on unused NAT Gateway {nat_gw_id} ({total_traffic_gb:.4f} GB traffic in {min_observation_days} days). Total waste: ${total_monthly_cost:.2f}/month (NAT Gateway ${nat_gateway_cost} + EIP ${self.PRICING['elastic_ip']})"

                    already_wasted = round((age_days / 30) * total_monthly_cost, 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat() if allocation_time else None,
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "eip_on_unused_nat_gateway",
                        "nat_gateway_id": nat_gw_id,
                        "nat_gateway_total_traffic_gb": total_traffic_gb,
                        "observation_period_days": min_observation_days,
                        "nat_gateway_cost_monthly": nat_gateway_cost,
                        "already_wasted": already_wasted,
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="elastic_ip",
                            resource_id=allocation_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=total_monthly_cost,  # Include NAT Gateway cost
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning EIPs on unused NAT Gateways (Scenario 6) in {region}: {e}")

        return orphans

    async def scan_idle_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs on active resources with extremely low network traffic (SCENARIO 7).

        Detects:
        - EIPs on running EC2 instances with minimal NetworkIn/Out (CloudWatch)
        - Instance is "running" but not actually being used
        - Common for forgotten test instances, abandoned projects, or over-provisioned infrastructure
        - Uses CloudWatch NetworkIn/NetworkOut metrics to determine idle status

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources on idle instances
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        min_idle_days = detection_rules.get("min_idle_days", 30)
        idle_network_threshold_bytes = detection_rules.get("idle_network_threshold_bytes", 1_000_000)  # 1 MB
        min_observation_days = detection_rules.get("min_observation_days", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all EIPs
                eips_response = await ec2.describe_addresses()

                # Get all running instances
                instances_response = await ec2.describe_instances(
                    Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
                )
                running_instances = {}  # {instance_id: launch_time}
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        running_instances[instance["InstanceId"]] = instance.get("LaunchTime")

                for address in eips_response.get("Addresses", []):
                    instance_id = address.get("InstanceId")

                    if not instance_id or instance_id not in running_instances:
                        continue  # Only check EIPs on running instances

                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    if not allocation_time:
                        continue

                    launch_time = running_instances[instance_id]
                    running_days = (datetime.now(timezone.utc) - launch_time).days

                    if running_days < min_idle_days:
                        continue

                    # Get CloudWatch network metrics for the instance
                    metrics = await self._get_ec2_network_metrics(
                        instance_id, region, period_days=min_observation_days
                    )

                    total_traffic_bytes = metrics.get("network_in", 0.0) + metrics.get("network_out", 0.0)

                    # Flag if traffic is below idle threshold
                    if total_traffic_bytes > idle_network_threshold_bytes:
                        continue  # Instance has sufficient network activity

                    # This instance (and its EIP) is idle!
                    age_days = (datetime.now(timezone.utc) - allocation_time).days

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "critical" if running_days >= 90 else ("high" if running_days >= 60 else "medium")

                    total_traffic_mb = total_traffic_bytes / (1024 * 1024)
                    reason = f"EIP on idle running instance {instance_id} ({total_traffic_mb:.2f} MB traffic in {min_observation_days} days). Instance running but unused for {running_days} days."

                    already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat(),
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "idle_eip",
                        "associated_instance_id": instance_id,
                        "instance_running_days": running_days,
                        "total_network_traffic_mb": round(total_traffic_mb, 2),
                        "observation_period_days": min_observation_days,
                        "already_wasted": already_wasted,
                    }

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
            print(f"Error scanning idle EIPs (Scenario 7) in {region}: {e}")

        return orphans

    async def scan_low_traffic_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs with low network traffic (SCENARIO 8).

        Detects:
        - EIPs on running instances with low but non-zero traffic (< 1 GB/month)
        - Instance is technically active but severely underutilized
        - Suggests the resource might be over-provisioned or unnecessary
        - Uses CloudWatch NetworkIn/NetworkOut metrics over observation period

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources with low traffic
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        low_traffic_threshold_gb = detection_rules.get("low_traffic_threshold_gb", 1.0)  # 1 GB/month
        min_observation_days = detection_rules.get("min_observation_days", 30)
        min_age_days = detection_rules.get("min_age_days", 3)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all EIPs
                eips_response = await ec2.describe_addresses()

                # Get all running instances
                instances_response = await ec2.describe_instances(
                    Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
                )
                running_instances = {}  # {instance_id: launch_time}
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        running_instances[instance["InstanceId"]] = instance.get("LaunchTime")

                for address in eips_response.get("Addresses", []):
                    instance_id = address.get("InstanceId")

                    if not instance_id or instance_id not in running_instances:
                        continue  # Only check EIPs on running instances

                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    if not allocation_time:
                        continue

                    age_days = (datetime.now(timezone.utc) - allocation_time).days
                    if age_days < min_age_days:
                        continue

                    # Get CloudWatch network metrics for the instance
                    metrics = await self._get_ec2_network_metrics(
                        instance_id, region, period_days=min_observation_days
                    )

                    total_traffic_gb = metrics.get("total_traffic_gb", 0.0)

                    # Flag if traffic is low but not zero (to avoid overlap with Scenario 7)
                    if total_traffic_gb >= low_traffic_threshold_gb:
                        continue  # Traffic is above low-traffic threshold

                    if total_traffic_gb < 0.001:  # Less than 1 MB
                        continue  # Covered by Scenario 7 (idle)

                    # This EIP has low traffic!
                    launch_time = running_instances[instance_id]
                    running_days = (datetime.now(timezone.utc) - launch_time).days

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "high" if running_days >= 60 else ("medium" if running_days >= 30 else "low")

                    reason = f"EIP on low-traffic instance {instance_id} ({total_traffic_gb:.4f} GB in {min_observation_days} days, < {low_traffic_threshold_gb} GB threshold)."

                    already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat(),
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "low_traffic_eip",
                        "associated_instance_id": instance_id,
                        "instance_running_days": running_days,
                        "total_traffic_gb": round(total_traffic_gb, 4),
                        "observation_period_days": min_observation_days,
                        "low_traffic_threshold_gb": low_traffic_threshold_gb,
                        "already_wasted": already_wasted,
                    }

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
            print(f"Error scanning low-traffic EIPs (Scenario 8) in {region}: {e}")

        return orphans

    async def scan_unused_nat_gateway_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs on NAT Gateways with zero active connections (SCENARIO 9).

        Detects:
        - EIPs on NAT Gateways with ActiveConnectionCount = 0 for extended period
        - More precise than Scenario 6 (focuses on active connections vs total traffic)
        - NAT Gateway ($32.40/month) + EIP ($3.60/month) = $36/month waste
        - Uses CloudWatch ActiveConnectionCount metric

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources on NAT Gateways with zero connections
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        nat_gateway_zero_connections_days = detection_rules.get("nat_gateway_zero_connections_days", 30)
        min_observation_days = detection_rules.get("min_observation_days", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all EIPs
                eips_response = await ec2.describe_addresses()

                # Get all NAT Gateways
                nat_gateways_response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                # Map EIPs to NAT Gateways
                eip_to_nat_gateway = {}  # {eip_allocation_id: nat_gateway_id}
                nat_gateway_info = {}  # {nat_gateway_id: {create_time, public_ip}}

                for nat_gw in nat_gateways_response.get("NatGateways", []):
                    nat_gw_id = nat_gw["NatGatewayId"]
                    create_time = nat_gw.get("CreateTime")

                    # Find EIP allocation ID for this NAT Gateway
                    for address_set in nat_gw.get("NatGatewayAddresses", []):
                        allocation_id = address_set.get("AllocationId")
                        public_ip = address_set.get("PublicIp")
                        if allocation_id:
                            eip_to_nat_gateway[allocation_id] = nat_gw_id
                            nat_gateway_info[nat_gw_id] = {
                                "create_time": create_time,
                                "public_ip": public_ip,
                            }

                # Check each EIP associated with NAT Gateway
                for address in eips_response.get("Addresses", []):
                    allocation_id = address.get("AllocationId", "N/A")

                    if allocation_id not in eip_to_nat_gateway:
                        continue  # Not associated with NAT Gateway

                    nat_gw_id = eip_to_nat_gateway[allocation_id]
                    nat_info = nat_gateway_info.get(nat_gw_id)

                    if not nat_info:
                        continue

                    create_time = nat_info["create_time"]
                    age_days = (datetime.now(timezone.utc) - create_time).days

                    if age_days < nat_gateway_zero_connections_days:
                        continue

                    # Get CloudWatch metrics for NAT Gateway
                    metrics = await self._get_eip_nat_gateway_metrics(
                        nat_gw_id, region, period_days=min_observation_days
                    )

                    active_connection_count = metrics.get("active_connection_count", 0.0)

                    # Flag if zero active connections
                    if active_connection_count > 0.1:  # Some tolerance for measurement
                        continue  # NAT Gateway has active connections

                    # This NAT Gateway has ZERO connections!
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "critical" if age_days >= 90 else ("high" if age_days >= 60 else "medium")

                    # **KEY**: NAT Gateway + EIP = $32.40 + $3.60 = $36/month
                    nat_gateway_cost = 32.40
                    total_monthly_cost = nat_gateway_cost + self.PRICING["elastic_ip"]

                    reason = f"EIP on NAT Gateway {nat_gw_id} with ZERO active connections for {age_days} days. Total waste: ${total_monthly_cost:.2f}/month (NAT Gateway ${nat_gateway_cost} + EIP ${self.PRICING['elastic_ip']})"

                    already_wasted = round((age_days / 30) * total_monthly_cost, 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat() if allocation_time else None,
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "eip_on_zero_connection_nat_gateway",
                        "nat_gateway_id": nat_gw_id,
                        "active_connection_count": active_connection_count,
                        "observation_period_days": min_observation_days,
                        "nat_gateway_cost_monthly": nat_gateway_cost,
                        "already_wasted": already_wasted,
                    }

                    orphans.append(
                        OrphanResourceData(
                            resource_type="elastic_ip",
                            resource_id=allocation_id,
                            resource_name=name,
                            region=region,
                            estimated_monthly_cost=total_monthly_cost,  # Include NAT Gateway cost
                            resource_metadata=metadata,
                        )
                    )

        except ClientError as e:
            print(f"Error scanning EIPs on NAT Gateways with zero connections (Scenario 9) in {region}: {e}")

        return orphans

    async def scan_eips_on_failed_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Elastic IPs on EC2 instances failing status checks (SCENARIO 10).

        Detects:
        - EIPs on instances with persistent StatusCheckFailed metrics (CloudWatch)
        - Instance is technically "running" but not operational
        - Common after system failures, network issues, or kernel panics
        - Indicates the EIP is attached to a non-functional resource

        Args:
            region: AWS region to scan
            detection_rules: Optional detection rules

        Returns:
            List of orphan Elastic IP resources on failed instances
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES
            detection_rules = DEFAULT_DETECTION_RULES.get("elastic_ip", {})

        if not detection_rules.get("enabled", True):
            return orphans

        max_status_check_failures = detection_rules.get("max_status_check_failures", 7)  # 7 days of failures
        min_failed_days = detection_rules.get("min_failed_days", 7)
        min_observation_days = detection_rules.get("min_observation_days", 30)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all EIPs
                eips_response = await ec2.describe_addresses()

                # Get all running instances
                instances_response = await ec2.describe_instances(
                    Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
                )
                running_instances = {}  # {instance_id: launch_time}
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        running_instances[instance["InstanceId"]] = instance.get("LaunchTime")

                for address in eips_response.get("Addresses", []):
                    instance_id = address.get("InstanceId")

                    if not instance_id or instance_id not in running_instances:
                        continue  # Only check EIPs on running instances

                    allocation_id = address.get("AllocationId", "N/A")
                    public_ip = address.get("PublicIp", "Unknown")
                    allocation_time = address.get("AllocationTime")

                    if not allocation_time:
                        continue

                    age_days = (datetime.now(timezone.utc) - allocation_time).days

                    # Get CloudWatch status check metrics for the instance
                    metrics = await self._get_ec2_network_metrics(
                        instance_id, region, period_days=min_observation_days
                    )

                    status_check_failed = metrics.get("status_check_failed", 0.0)
                    status_check_failed_instance = metrics.get("status_check_failed_instance", 0.0)
                    status_check_failed_system = metrics.get("status_check_failed_system", 0.0)

                    # Flag if excessive status check failures
                    if status_check_failed < max_status_check_failures:
                        continue  # Instance is healthy or has acceptable failure rate

                    # This instance is failing status checks!
                    launch_time = running_instances[instance_id]
                    running_days = (datetime.now(timezone.utc) - launch_time).days

                    if running_days < min_failed_days:
                        continue

                    # Extract name from tags
                    name = None
                    for tag in address.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    confidence = "critical" if status_check_failed >= 30 else ("high" if status_check_failed >= 14 else "medium")

                    reason = f"EIP on failing instance {instance_id} ({int(status_check_failed)} status check failures in {min_observation_days} days). Instance may be unresponsive or misconfigured."

                    already_wasted = round((age_days / 30) * self.PRICING["elastic_ip"], 2)

                    metadata = {
                        "public_ip": public_ip,
                        "allocation_time": allocation_time.isoformat(),
                        "age_days": age_days,
                        "confidence": confidence,
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": "eip_on_failed_instance",
                        "associated_instance_id": instance_id,
                        "instance_running_days": running_days,
                        "status_check_failed_total": int(status_check_failed),
                        "status_check_failed_instance": int(status_check_failed_instance),
                        "status_check_failed_system": int(status_check_failed_system),
                        "observation_period_days": min_observation_days,
                        "already_wasted": already_wasted,
                    }

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
            print(f"Error scanning EIPs on failed instances (Scenario 10) in {region}: {e}")

        return orphans

    async def scan_orphaned_snapshots(
        self, region: str, detection_rules: dict | None = None, orphaned_volume_ids: list[str] | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for orphaned EBS snapshots (SCENARIO 1: ebs_snapshot_orphaned).

        Detects snapshots where the source volume no longer exists, or snapshots
        of volumes that are idle/orphaned.

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

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    volume_id = snapshot.get("VolumeId")
                    start_time = snapshot["StartTime"]
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    should_flag = False
                    orphan_type = ""
                    source_volume_status = "unknown"

                    # CASE 1: Volume no longer exists
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

                    if not should_flag:
                        continue

                    size_gb = snapshot["VolumeSize"]
                    monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                    # Determine confidence level based on orphan type and age
                    if orphan_type == "volume_deleted":
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
                        if source_volume_status == "unattached":
                            confidence = "high"
                            reason = f"Snapshot of unattached volume {volume_id} (volume is orphaned)"
                        elif source_volume_status == "attached_idle":
                            confidence = "medium"
                            reason = f"Snapshot of idle volume {volume_id} (volume has no I/O activity)"
                        else:
                            confidence = "medium"
                            reason = f"Snapshot of orphaned volume {volume_id}"
                    else:
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
                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                        "orphan_reason": reason,
                        "orphan_type": orphan_type,
                        "source_volume_status": source_volume_status,
                        "scenario": "ebs_snapshot_orphaned",
                    }

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

    async def scan_redundant_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for redundant EBS snapshots (SCENARIO 2: ebs_snapshot_redundant).

        Detects volumes with more than N snapshots, flagging older snapshots
        beyond the retention limit as redundant.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_redundant_snapshots = rules.get("detect_redundant_snapshots", True)
        max_snapshots_per_volume = rules.get("max_snapshots_per_volume", 7)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_redundant_snapshots:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                # Get all existing volumes
                volumes_response = await ec2.describe_volumes()
                volume_info = {}
                for vol in volumes_response.get("Volumes", []):
                    volume_info[vol["VolumeId"]] = {
                        "state": vol["State"],
                        "attachments": vol.get("Attachments", []),
                    }

                # Group snapshots by volume
                snapshots_by_volume = {}
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

                # Flag redundant snapshots
                for volume_id, volume_snapshots in snapshots_by_volume.items():
                    if len(volume_snapshots) > max_snapshots_per_volume:
                        # Flag snapshots beyond the retention limit
                        for i, snapshot in enumerate(volume_snapshots):
                            if i >= max_snapshots_per_volume:
                                snapshot_id = snapshot["SnapshotId"]
                                start_time = snapshot["StartTime"]
                                age_days = (datetime.now(timezone.utc) - start_time).days
                                size_gb = snapshot["VolumeSize"]
                                monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                                # Extract name/description
                                description = snapshot.get("Description", "")
                                name = None
                                for tag in snapshot.get("Tags", []):
                                    if tag["Key"] == "Name":
                                        name = tag["Value"]
                                        break

                                source_volume_status = "exists" if volume_id in volume_info else "deleted"

                                metadata = {
                                    "size_gb": size_gb,
                                    "volume_id": volume_id,
                                    "created_at": start_time.isoformat(),
                                    "age_days": age_days,
                                    "description": description,
                                    "encrypted": snapshot.get("Encrypted", False),
                                    "confidence": "high",
                                    "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                    "orphan_reason": f"Redundant snapshot #{i+1} of {len(volume_snapshots)} (retention limit: {max_snapshots_per_volume})",
                                    "orphan_type": "redundant_snapshot",
                                    "source_volume_status": source_volume_status,
                                    "redundant_info": {
                                        "total_snapshots": len(volume_snapshots),
                                        "retention_limit": max_snapshots_per_volume,
                                        "position": i + 1,
                                    },
                                    "scenario": "ebs_snapshot_redundant",
                                }

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
            print(f"Error scanning redundant snapshots in {region}: {e}")

        return orphans

    async def scan_unused_ami_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for snapshots of unused AMIs (SCENARIO 10: ebs_snapshot_from_unused_ami).

        Detects snapshots backing AMIs that have never been used to launch instances.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_unused_ami_snapshots = rules.get("detect_unused_ami_snapshots", True)
        min_ami_unused_days = rules.get("min_ami_unused_days", 180)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_unused_ami_snapshots:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all AMIs owned by this account
                amis_response = await ec2.describe_images(Owners=[account_id])
                all_amis = amis_response.get("Images", [])

                # Build AMI usage info
                unused_ami_snapshot_ids = set()

                for ami in all_amis:
                    ami_id = ami["ImageId"]
                    ami_creation_date = datetime.fromisoformat(ami["CreationDate"].replace('Z', '+00:00'))
                    ami_age_days = (datetime.now(timezone.utc) - ami_creation_date).days

                    # Only check AMIs old enough
                    if ami_age_days < min_ami_unused_days:
                        continue

                    # Extract snapshot IDs from AMI block device mappings
                    ami_snapshots = []
                    for block_device in ami.get("BlockDeviceMappings", []):
                        if "Ebs" in block_device and "SnapshotId" in block_device["Ebs"]:
                            snapshot_id = block_device["Ebs"]["SnapshotId"]
                            ami_snapshots.append(snapshot_id)

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
                        for snapshot_id in ami_snapshots:
                            unused_ami_snapshot_ids.add((snapshot_id, ami_id))

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                # Flag unused AMI snapshots
                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]

                    # Check if this snapshot is in our unused AMI set
                    associated_ami = None
                    for snap_id, ami_id in unused_ami_snapshot_ids:
                        if snap_id == snapshot_id:
                            associated_ami = ami_id
                            break

                    if associated_ami:
                        start_time = snapshot["StartTime"]
                        age_days = (datetime.now(timezone.utc) - start_time).days
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                        # Extract name/description
                        description = snapshot.get("Description", "")
                        name = None
                        for tag in snapshot.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        metadata = {
                            "size_gb": size_gb,
                            "volume_id": snapshot.get("VolumeId", "Unknown"),
                            "created_at": start_time.isoformat(),
                            "age_days": age_days,
                            "description": description,
                            "encrypted": snapshot.get("Encrypted", False),
                            "confidence": "high",
                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                            "orphan_reason": f"Snapshot of unused AMI {associated_ami} (AMI not used for {min_ami_unused_days}+ days)",
                            "orphan_type": "unused_ami_snapshot",
                            "source_volume_status": "ami_snapshot",
                            "ami_info": {
                                "ami_id": associated_ami,
                                "ami_unused": True,
                            },
                            "scenario": "ebs_snapshot_from_unused_ami",
                        }

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
            print(f"Error scanning unused AMI snapshots in {region}: {e}")

        return orphans

    async def scan_old_unused_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for very old snapshots without compliance tags (SCENARIO 3: ebs_snapshot_old_unused).

        Detects snapshots >365 days old without compliance/governance tags.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_old_unused = rules.get("detect_old_unused", True)
        old_unused_age_days = rules.get("old_unused_age_days", 365)
        compliance_tags = rules.get("compliance_tags", ["Backup", "Compliance", "Governance", "Retention", "Legal"])
        enabled = rules.get("enabled", True)

        if not enabled or not detect_old_unused:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    start_time = snapshot["StartTime"]
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    # Check if snapshot is old enough
                    if age_days < old_unused_age_days:
                        continue

                    # Check if snapshot has any compliance tags
                    tags = snapshot.get("Tags", [])
                    has_compliance_tag = False
                    for tag in tags:
                        if tag["Key"] in compliance_tags:
                            has_compliance_tag = True
                            break

                    # Flag only if no compliance tags
                    if not has_compliance_tag:
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                        # Extract name/description
                        description = snapshot.get("Description", "")
                        name = None
                        for tag in tags:
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        metadata = {
                            "size_gb": size_gb,
                            "volume_id": snapshot.get("VolumeId", "Unknown"),
                            "created_at": start_time.isoformat(),
                            "age_days": age_days,
                            "description": description,
                            "encrypted": snapshot.get("Encrypted", False),
                            "confidence": "high",
                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                            "orphan_reason": f"Snapshot {age_days} days old without compliance/governance tags (likely abandoned)",
                            "orphan_type": "old_unused",
                            "has_compliance_tags": False,
                            "scenario": "ebs_snapshot_old_unused",
                        }

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
            print(f"Error scanning old unused snapshots in {region}: {e}")

        return orphans

    async def scan_snapshots_from_deleted_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for snapshots from deleted instances (SCENARIO 4: ebs_snapshot_from_deleted_instance).

        Detects snapshots with instance IDs in description where the instance no longer exists.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES
        import re

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_deleted_instance_snapshots = rules.get("detect_deleted_instance_snapshots", True)
        min_age_days = rules.get("min_age_days", 90)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_deleted_instance_snapshots:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                # Get all existing instances
                instances_response = await ec2.describe_instances()
                existing_instance_ids = set()
                for reservation in instances_response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        existing_instance_ids.add(instance["InstanceId"])

                # Pattern to match instance IDs in description (i-xxxxxxxxxxxxxxxxx)
                instance_id_pattern = re.compile(r'i-[a-f0-9]{8,17}')

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    description = snapshot.get("Description", "")
                    start_time = snapshot["StartTime"]
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    # Check if snapshot is old enough
                    if age_days < min_age_days:
                        continue

                    # Parse instance IDs from description
                    instance_ids_in_desc = instance_id_pattern.findall(description)

                    if instance_ids_in_desc:
                        # Check if any of these instances still exist
                        all_deleted = True
                        deleted_instance_ids = []
                        for instance_id in instance_ids_in_desc:
                            if instance_id in existing_instance_ids:
                                all_deleted = False
                            else:
                                deleted_instance_ids.append(instance_id)

                        # Flag if at least one instance is deleted
                        if deleted_instance_ids:
                            size_gb = snapshot["VolumeSize"]
                            monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                            # Extract name/description
                            name = None
                            for tag in snapshot.get("Tags", []):
                                if tag["Key"] == "Name":
                                    name = tag["Value"]
                                    break

                            confidence = "high" if all_deleted else "medium"

                            metadata = {
                                "size_gb": size_gb,
                                "volume_id": snapshot.get("VolumeId", "Unknown"),
                                "created_at": start_time.isoformat(),
                                "age_days": age_days,
                                "description": description,
                                "encrypted": snapshot.get("Encrypted", False),
                                "confidence": confidence,
                                "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                "orphan_reason": f"Snapshot from deleted instance(s): {', '.join(deleted_instance_ids)}",
                                "orphan_type": "deleted_instance_snapshot",
                                "deleted_instance_ids": deleted_instance_ids,
                                "all_instances_deleted": all_deleted,
                                "scenario": "ebs_snapshot_from_deleted_instance",
                            }

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
            print(f"Error scanning snapshots from deleted instances in {region}: {e}")

        return orphans

    async def scan_incomplete_failed_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for incomplete/failed snapshots (SCENARIO 5: ebs_snapshot_incomplete_failed).

        Detects snapshots in 'error' state or 'pending' state for >7 days.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_incomplete_failed = rules.get("detect_incomplete_failed", True)
        max_pending_days = rules.get("max_pending_days", 7)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_incomplete_failed:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    state = snapshot.get("State", "")
                    start_time = snapshot["StartTime"]
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    # Flag if in error state OR pending for too long
                    should_flag = False
                    reason = ""

                    if state == "error":
                        should_flag = True
                        reason = f"Snapshot in error state (failed to complete)"
                        confidence = "critical"
                    elif state == "pending" and age_days >= max_pending_days:
                        should_flag = True
                        reason = f"Snapshot stuck in pending state for {age_days} days (likely failed)"
                        confidence = "high"

                    if should_flag:
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                        # Extract name/description
                        description = snapshot.get("Description", "")
                        name = None
                        for tag in snapshot.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        metadata = {
                            "size_gb": size_gb,
                            "volume_id": snapshot.get("VolumeId", "Unknown"),
                            "created_at": start_time.isoformat(),
                            "age_days": age_days,
                            "description": description,
                            "encrypted": snapshot.get("Encrypted", False),
                            "confidence": confidence,
                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                            "orphan_reason": reason,
                            "orphan_type": "incomplete_failed",
                            "snapshot_state": state,
                            "scenario": "ebs_snapshot_incomplete_failed",
                        }

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
            print(f"Error scanning incomplete/failed snapshots in {region}: {e}")

        return orphans

    async def scan_untagged_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for untagged snapshots (SCENARIO 6: ebs_snapshot_untagged_unmanaged).

        Detects snapshots with no tags present (likely abandoned/unmanaged).

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_untagged = rules.get("detect_untagged", True)
        min_untagged_age_days = rules.get("min_untagged_age_days", 30)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_untagged:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    tags = snapshot.get("Tags", [])
                    start_time = snapshot["StartTime"]
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    # Flag if no tags and old enough
                    if not tags and age_days >= min_untagged_age_days:
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]
                        description = snapshot.get("Description", "")

                        metadata = {
                            "size_gb": size_gb,
                            "volume_id": snapshot.get("VolumeId", "Unknown"),
                            "created_at": start_time.isoformat(),
                            "age_days": age_days,
                            "description": description,
                            "encrypted": snapshot.get("Encrypted", False),
                            "confidence": "high",
                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                            "orphan_reason": f"Snapshot {age_days} days old with no tags (likely abandoned/unmanaged)",
                            "orphan_type": "untagged",
                            "has_tags": False,
                            "scenario": "ebs_snapshot_untagged_unmanaged",
                        }

                        orphans.append(
                            OrphanResourceData(
                                resource_type="ebs_snapshot",
                                resource_id=snapshot_id,
                                resource_name=description or snapshot_id,
                                region=region,
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata=metadata,
                            )
                        )

        except ClientError as e:
            print(f"Error scanning untagged snapshots in {region}: {e}")

        return orphans

    async def scan_excessive_retention_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for snapshots with excessive retention in non-prod (SCENARIO 8: ebs_snapshot_excessive_retention).

        Detects snapshots retained too long in dev/test/staging environments.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_excessive_retention = rules.get("detect_excessive_retention", True)
        nonprod_max_days = rules.get("nonprod_max_days", 90)
        nonprod_env_tags = rules.get("nonprod_env_tags", ["Environment", "Env", "Stage"])
        nonprod_env_values = rules.get("nonprod_env_values", ["dev", "development", "test", "testing", "stage", "staging", "qa"])
        enabled = rules.get("enabled", True)

        if not enabled or not detect_excessive_retention:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                for snapshot in all_snapshots:
                    snapshot_id = snapshot["SnapshotId"]
                    tags = snapshot.get("Tags", [])
                    start_time = snapshot["StartTime"]
                    age_days = (datetime.now(timezone.utc) - start_time).days

                    # Check if snapshot is old enough
                    if age_days < nonprod_max_days:
                        continue

                    # Check if snapshot has non-prod environment tag
                    is_nonprod = False
                    env_value = None
                    for tag in tags:
                        if tag["Key"] in nonprod_env_tags:
                            tag_value = tag["Value"].lower()
                            if tag_value in nonprod_env_values:
                                is_nonprod = True
                                env_value = tag_value
                                break

                    # Flag if non-prod and old enough
                    if is_nonprod:
                        size_gb = snapshot["VolumeSize"]
                        monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                        # Extract name/description
                        description = snapshot.get("Description", "")
                        name = None
                        for tag in tags:
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        metadata = {
                            "size_gb": size_gb,
                            "volume_id": snapshot.get("VolumeId", "Unknown"),
                            "created_at": start_time.isoformat(),
                            "age_days": age_days,
                            "description": description,
                            "encrypted": snapshot.get("Encrypted", False),
                            "confidence": "high",
                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                            "orphan_reason": f"Non-prod ({env_value}) snapshot retained for {age_days} days (exceeds {nonprod_max_days} day limit)",
                            "orphan_type": "excessive_retention",
                            "environment": env_value,
                            "is_nonprod": True,
                            "scenario": "ebs_snapshot_excessive_retention",
                        }

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
            print(f"Error scanning excessive retention snapshots in {region}: {e}")

        return orphans

    async def scan_duplicate_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for duplicate snapshots (SCENARIO 9: ebs_snapshot_duplicate_content).

        Detects snapshots of the same volume with same size within short time window.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan snapshot resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ebs_snapshot", {})
        detect_duplicates = rules.get("detect_duplicates", True)
        duplicate_window_hours = rules.get("duplicate_window_hours", 1)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_duplicates:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get account ID
                account_info = await self.validate_credentials()
                account_id = account_info["account_id"]

                # Get all snapshots owned by this account
                response = await ec2.describe_snapshots(OwnerIds=[account_id])
                all_snapshots = response.get("Snapshots", [])

                # Group snapshots by volume ID
                snapshots_by_volume = {}
                for snapshot in all_snapshots:
                    volume_id = snapshot.get("VolumeId")
                    if volume_id:
                        if volume_id not in snapshots_by_volume:
                            snapshots_by_volume[volume_id] = []
                        snapshots_by_volume[volume_id].append(snapshot)

                # Sort by creation time
                for volume_id in snapshots_by_volume:
                    snapshots_by_volume[volume_id].sort(key=lambda s: s["StartTime"])

                # Find duplicates
                for volume_id, volume_snapshots in snapshots_by_volume.items():
                    for i, snapshot in enumerate(volume_snapshots):
                        if i == 0:
                            continue  # Skip first snapshot

                        prev_snapshot = volume_snapshots[i - 1]

                        # Check if same size and within time window
                        if snapshot["VolumeSize"] == prev_snapshot["VolumeSize"]:
                            time_diff = snapshot["StartTime"] - prev_snapshot["StartTime"]
                            time_diff_hours = time_diff.total_seconds() / 3600

                            if time_diff_hours <= duplicate_window_hours:
                                snapshot_id = snapshot["SnapshotId"]
                                start_time = snapshot["StartTime"]
                                age_days = (datetime.now(timezone.utc) - start_time).days
                                size_gb = snapshot["VolumeSize"]
                                monthly_cost = size_gb * self.PRICING["snapshot_per_gb"]

                                # Extract name/description
                                description = snapshot.get("Description", "")
                                name = None
                                for tag in snapshot.get("Tags", []):
                                    if tag["Key"] == "Name":
                                        name = tag["Value"]
                                        break

                                metadata = {
                                    "size_gb": size_gb,
                                    "volume_id": volume_id,
                                    "created_at": start_time.isoformat(),
                                    "age_days": age_days,
                                    "description": description,
                                    "encrypted": snapshot.get("Encrypted", False),
                                    "confidence": "high",
                                    "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                    "orphan_reason": f"Duplicate snapshot created {time_diff_hours:.1f}h after previous snapshot (same volume, same size)",
                                    "orphan_type": "duplicate",
                                    "previous_snapshot_id": prev_snapshot["SnapshotId"],
                                    "time_diff_hours": round(time_diff_hours, 2),
                                    "scenario": "ebs_snapshot_duplicate_content",
                                }

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
            print(f"Error scanning duplicate snapshots in {region}: {e}")

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
                                        "confidence_level": self._calculate_confidence_level(stopped_days, detection_rules),
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
                                            "confidence_level": self._calculate_confidence_level(instance_age_days, detection_rules),
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

    async def scan_oversized_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for over-provisioned EC2 instances (SCENARIO 2: ec2_instance_oversized).

        Detects running instances with average CPU <30% over 30 days.

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan instance resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_oversized = rules.get("detect_oversized", True)
        cpu_threshold = rules.get("oversized_cpu_threshold", 30.0)
        lookback_days = rules.get("oversized_lookback_days", 30)
        min_instance_size = rules.get("oversized_min_instance_size", "xlarge")
        enabled = rules.get("enabled", True)

        if not enabled or not detect_oversized:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2, \
                     self.session.client("cloudwatch", region_name=region) as cloudwatch:

                # Get all running instances
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
                )

                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=lookback_days)

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        launch_time = instance['LaunchTime']

                        # Only check larger instances (xlarge+)
                        if min_instance_size not in instance_type and \
                           '2xlarge' not in instance_type and \
                           '4xlarge' not in instance_type and \
                           '8xlarge' not in instance_type:
                            continue

                        # Get CPU metrics
                        cpu_metrics = await cloudwatch.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUUtilization',
                            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,
                            Statistics=['Average', 'Maximum']
                        )

                        if not cpu_metrics['Datapoints']:
                            continue

                        avg_cpu = sum(dp['Average'] for dp in cpu_metrics['Datapoints']) / len(cpu_metrics['Datapoints'])
                        max_cpu = max((dp['Maximum'] for dp in cpu_metrics['Datapoints']), default=0)

                        if avg_cpu < cpu_threshold:
                            monthly_cost = self._estimate_ec2_instance_cost(instance_type)

                            # Calculate recommended size
                            recommended_type = self._recommend_smaller_instance(instance_type, avg_cpu, max_cpu)
                            recommended_cost = self._estimate_ec2_instance_cost(recommended_type) if recommended_type != instance_type else monthly_cost
                            savings = monthly_cost - recommended_cost

                            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                            name = tags.get('Name', 'Unnamed')

                            metadata = {
                                'instance_type': instance_type,
                                'avg_cpu_30d': round(avg_cpu, 1),
                                'max_cpu_30d': round(max_cpu, 1),
                                'launch_time': launch_time.isoformat(),
                                'current_monthly_cost': monthly_cost,
                                'recommended_type': recommended_type,
                                'recommended_monthly_cost': recommended_cost,
                                'monthly_savings': round(savings, 2),
                                'confidence': 'high' if avg_cpu < 15 else 'medium',
                                'scenario': 'ec2_instance_oversized',
                                'tags': tags
                            }

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="ec2_instance",
                                    resource_id=instance_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=round(savings, 2),
                                    resource_metadata=metadata,
                                )
                            )

        except ClientError as e:
            print(f"Error scanning oversized instances in {region}: {e}")

        return orphans

    async def scan_old_generation_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for old generation EC2 instances (SCENARIO 3: ec2_instance_old_generation).

        Detects instances using obsolete instance types (t2, m4, c4, r4).

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphan instance resources
        """
        orphans: list[OrphanResourceData] = []

        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_old_generation = rules.get("detect_old_generation", True)
        old_generations = rules.get("old_generations", ["t2", "m4", "c4", "r4", "i3", "x1", "p2", "g3"])
        generation_mapping = rules.get("generation_mapping", {
            "t2": "t3", "m4": "m5", "c4": "c5", "r4": "r5",
            "i3": "i3en", "x1": "x2idn", "p2": "p3", "g3": "g4dn"
        })
        enabled = rules.get("enabled", True)

        if not enabled or not detect_old_generation:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
                )

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        launch_time = instance['LaunchTime']

                        family = instance_type.split('.')[0]

                        if family in old_generations:
                            size = instance_type.split('.')[1] if '.' in instance_type else 'large'
                            new_family = generation_mapping.get(family, family)
                            recommended_type = f"{new_family}.{size}"

                            current_cost = self._estimate_ec2_instance_cost(instance_type)
                            new_cost = self._estimate_ec2_instance_cost(recommended_type)
                            savings = current_cost - new_cost

                            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                            name = tags.get('Name', 'Unnamed')

                            metadata = {
                                'instance_type': instance_type,
                                'current_generation': family,
                                'recommended_type': recommended_type,
                                'new_generation': new_family,
                                'launch_time': launch_time.isoformat(),
                                'current_monthly_cost': current_cost,
                                'new_monthly_cost': new_cost,
                                'monthly_savings': round(savings, 2),
                                'savings_percent': round((savings / current_cost * 100), 1) if current_cost > 0 else 0,
                                'performance_improvement': '10-30%',
                                'confidence': 'high',
                                'scenario': 'ec2_instance_old_generation',
                                'tags': tags
                            }

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="ec2_instance",
                                    resource_id=instance_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=round(savings, 2),
                                    resource_metadata=metadata,
                                )
                            )

        except ClientError as e:
            print(f"Error scanning old generation instances in {region}: {e}")

        return orphans

    def _recommend_smaller_instance(self, current_type: str, avg_cpu: float, max_cpu: float) -> str:
        """Helper method to recommend smaller instance type based on CPU usage."""
        parts = current_type.split('.')
        if len(parts) != 2:
            return current_type

        family, size = parts[0], parts[1]
        sizes = ['large', 'xlarge', '2xlarge', '4xlarge', '8xlarge', '12xlarge', '16xlarge', '24xlarge']

        try:
            current_index = sizes.index(size)
        except ValueError:
            return current_type

        # Recommend downsize based on CPU
        if avg_cpu < 15 and max_cpu < 40 and current_index >= 2:
            new_index = max(current_index - 2, 0)
        elif avg_cpu < 25 and max_cpu < 60 and current_index >= 1:
            new_index = current_index - 1
        else:
            return current_type

        return f"{family}.{sizes[new_index]}"

    async def scan_burstable_credit_waste(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for T2/T3/T4 instances with CPU credit waste (SCENARIO 4).

        Detects burstable instances with unused credits or Unlimited charges.
        """
        orphans: list[OrphanResourceData] = []
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_burstable_waste = rules.get("detect_burstable_waste", True)
        credit_threshold = rules.get("burstable_credit_threshold", 0.9)
        lookback_days = rules.get("burstable_lookback_days", 30)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_burstable_waste:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2, \
                     self.session.client("cloudwatch", region_name=region) as cloudwatch:
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
                )

                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=lookback_days)

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_type = instance['InstanceType']
                        if not (instance_type.startswith('t2.') or instance_type.startswith('t3.') or instance_type.startswith('t4g.')):
                            continue

                        instance_id = instance['InstanceId']
                        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        name = tags.get('Name', 'Unnamed')

                        # Check CPU credit balance
                        credit_metrics = await cloudwatch.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUCreditBalance',
                            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=['Average', 'Maximum']
                        )

                        if credit_metrics['Datapoints']:
                            avg_credits = sum(dp['Average'] for dp in credit_metrics['Datapoints']) / len(credit_metrics['Datapoints'])
                            max_credits_map = {'t3.nano': 144, 't3.micro': 288, 't3.small': 576, 't3.medium': 576,
                                             't3.large': 864, 't3.xlarge': 2880, 't3.2xlarge': 5760}
                            max_credits = max_credits_map.get(instance_type, 1000)

                            if avg_credits > (max_credits * credit_threshold):
                                current_cost = self._estimate_ec2_instance_cost(instance_type)
                                # Recommend M5 equivalent
                                size = instance_type.split('.')[1]
                                recommended_type = f"m5.{size}" if size in ['large', 'xlarge', '2xlarge'] else "m5.large"
                                recommended_cost = self._estimate_ec2_instance_cost(recommended_type)
                                savings = current_cost - recommended_cost

                                orphans.append(OrphanResourceData(
                                    resource_type="ec2_instance",
                                    resource_id=instance_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=round(savings, 2),
                                    resource_metadata={
                                        'instance_type': instance_type,
                                        'avg_cpu_credits': round(avg_credits, 0),
                                        'max_credits': max_credits,
                                        'credit_utilization': round((avg_credits / max_credits * 100), 1),
                                        'recommended_type': recommended_type,
                                        'monthly_savings': round(savings, 2),
                                        'confidence': 'high',
                                        'scenario': 'ec2_instance_burstable_credit_waste',
                                        'tags': tags
                                    }
                                ))

        except ClientError as e:
            print(f"Error scanning burstable credit waste in {region}: {e}")

        return orphans

    async def scan_dev_test_24_7_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for dev/test instances running 24/7 (SCENARIO 5).

        Detects non-production instances that should be scheduled.
        """
        orphans: list[OrphanResourceData] = []
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_dev_test = rules.get("detect_dev_test_24_7", True)
        env_tags = rules.get("nonprod_env_tags", ["Environment", "Env", "Stage"])
        env_values = rules.get("nonprod_env_values", ["dev", "development", "test", "testing", "stage", "staging", "qa", "sandbox"])
        min_age_days = rules.get("nonprod_min_age_days", 7)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_dev_test:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
                )

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        launch_time = instance['LaunchTime']
                        age_days = (datetime.now(timezone.utc) - launch_time).days

                        if age_days < min_age_days:
                            continue

                        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        name = tags.get('Name', 'Unnamed')

                        # Check if non-prod environment
                        is_nonprod = False
                        env_value = None
                        for tag_key in env_tags:
                            if tag_key in tags:
                                tag_value = tags[tag_key].lower()
                                if tag_value in env_values:
                                    is_nonprod = True
                                    env_value = tag_value
                                    break

                        if is_nonprod:
                            monthly_cost = self._estimate_ec2_instance_cost(instance_type)
                            # Savings assuming 67% reduction (business hours only)
                            savings = monthly_cost * 0.67

                            orphans.append(OrphanResourceData(
                                resource_type="ec2_instance",
                                resource_id=instance_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=round(savings, 2),
                                resource_metadata={
                                    'instance_type': instance_type,
                                    'environment': env_value,
                                    'is_nonprod': True,
                                    'age_days': age_days,
                                    'current_monthly_cost': monthly_cost,
                                    'potential_savings': round(savings, 2),
                                    'recommendation': 'Schedule on/off during business hours (9AM-6PM weekdays)',
                                    'confidence': 'high',
                                    'scenario': 'ec2_instance_dev_running_24_7',
                                    'tags': tags
                                }
                            ))

        except ClientError as e:
            print(f"Error scanning dev/test 24/7 instances in {region}: {e}")

        return orphans

    async def scan_untagged_ec2_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for untagged EC2 instances (SCENARIO 6).

        Detects instances without any tags.
        """
        orphans: list[OrphanResourceData] = []
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_untagged = rules.get("detect_untagged", True)
        min_age_days = rules.get("untagged_min_age_days", 30)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_untagged:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
                )

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        launch_time = instance['LaunchTime']
                        age_days = (datetime.now(timezone.utc) - launch_time).days
                        tags = instance.get('Tags', [])

                        if not tags and age_days >= min_age_days:
                            state = instance['State']['Name']
                            monthly_cost = self._estimate_ec2_instance_cost(instance_type) if state == 'running' else 0

                            orphans.append(OrphanResourceData(
                                resource_type="ec2_instance",
                                resource_id=instance_id,
                                resource_name=instance_id,
                                region=region,
                                estimated_monthly_cost=round(monthly_cost, 2),
                                resource_metadata={
                                    'instance_type': instance_type,
                                    'state': state,
                                    'age_days': age_days,
                                    'has_tags': False,
                                    'recommendation': 'Add cost allocation tags or review for deletion',
                                    'confidence': 'high',
                                    'scenario': 'ec2_instance_untagged'
                                }
                            ))

        except ClientError as e:
            print(f"Error scanning untagged EC2 instances in {region}: {e}")

        return orphans

    async def scan_right_sizing_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Advanced right-sizing opportunities (SCENARIO 8).

        Detects instances that can be downsized based on comprehensive metrics.
        """
        orphans: list[OrphanResourceData] = []
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_right_sizing = rules.get("detect_right_sizing", True)
        cpu_threshold = rules.get("right_sizing_cpu_threshold", 40.0)
        max_cpu_threshold = rules.get("right_sizing_max_cpu_threshold", 75.0)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_right_sizing:
            return orphans

        # Note: This is a simplified version. Full implementation would analyze CPU, RAM, Network, Disk I/O
        # For MVP, we focus on CPU-based right-sizing
        return await self.scan_oversized_instances(region, detection_rules)

    async def scan_spot_eligible_workloads(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Spot-eligible workloads (SCENARIO 9).

        Detects stable workloads suitable for Spot instances (70-90% savings).
        """
        orphans: list[OrphanResourceData] = []
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_spot = rules.get("detect_spot_eligible", True)
        cpu_variance_threshold = rules.get("spot_cpu_variance_threshold", 20.0)
        min_uptime_days = rules.get("spot_min_uptime_days", 7)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_spot:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2, \
                     self.session.client("cloudwatch", region_name=region) as cloudwatch:
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']},
                            {'Name': 'instance-lifecycle', 'Values': ['on-demand']}]  # Only On-Demand
                )

                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=14)

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        launch_time = instance['LaunchTime']
                        age_days = (datetime.now(timezone.utc) - launch_time).days

                        if age_days < min_uptime_days:
                            continue

                        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        name = tags.get('Name', 'Unnamed')

                        # Get CPU metrics to check stability
                        cpu_metrics = await cloudwatch.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUUtilization',
                            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,
                            Statistics=['Average']
                        )

                        if cpu_metrics['Datapoints'] and len(cpu_metrics['Datapoints']) > 20:
                            cpu_values = [dp['Average'] for dp in cpu_metrics['Datapoints']]
                            avg_cpu = sum(cpu_values) / len(cpu_values)
                            variance = sum((x - avg_cpu) ** 2 for x in cpu_values) / len(cpu_values)
                            std_dev = variance ** 0.5

                            # Low variance = stable workload = Spot-eligible
                            if std_dev < cpu_variance_threshold:
                                current_cost = self._estimate_ec2_instance_cost(instance_type)
                                spot_cost = current_cost * 0.3  # Spot typically 70% cheaper
                                savings = current_cost - spot_cost

                                orphans.append(OrphanResourceData(
                                    resource_type="ec2_instance",
                                    resource_id=instance_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=round(savings, 2),
                                    resource_metadata={
                                        'instance_type': instance_type,
                                        'avg_cpu': round(avg_cpu, 1),
                                        'cpu_variance': round(variance, 1),
                                        'cpu_std_dev': round(std_dev, 1),
                                        'workload_stability': 'high' if std_dev < 10 else 'medium',
                                        'current_monthly_cost': current_cost,
                                        'spot_monthly_cost': round(spot_cost, 2),
                                        'monthly_savings': round(savings, 2),
                                        'savings_percent': 70,
                                        'recommendation': 'Migrate to Spot instances',
                                        'confidence': 'high',
                                        'scenario': 'ec2_instance_spot_opportunity',
                                        'tags': tags
                                    }
                                ))

        except ClientError as e:
            print(f"Error scanning Spot-eligible workloads in {region}: {e}")

        return orphans

    async def scan_scheduled_unused_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for instances only used during business hours (SCENARIO 10).

        Detects instances running 24/7 but only utilized during business hours.
        """
        orphans: list[OrphanResourceData] = []
        from app.models.detection_rule import DEFAULT_DETECTION_RULES

        rules = detection_rules or DEFAULT_DETECTION_RULES.get("ec2_instance", {})
        detect_scheduled = rules.get("detect_scheduled_unused", True)
        business_start = rules.get("business_hours_start", 9)
        business_end = rules.get("business_hours_end", 18)
        cpu_threshold = rules.get("scheduled_cpu_threshold", 10.0)
        enabled = rules.get("enabled", True)

        if not enabled or not detect_scheduled:
            return orphans

        try:
            async with self.session.client("ec2", region_name=region) as ec2, \
                     self.session.client("cloudwatch", region_name=region) as cloudwatch:
                response = await ec2.describe_instances(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
                )

                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=14)

                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        name = tags.get('Name', 'Unnamed')

                        # Get hourly CPU metrics
                        cpu_metrics = await cloudwatch.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUUtilization',
                            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,
                            Statistics=['Average']
                        )

                        if cpu_metrics['Datapoints'] and len(cpu_metrics['Datapoints']) > 50:
                            # Separate business vs non-business hours
                            business_hours_cpu = []
                            non_business_hours_cpu = []

                            for dp in cpu_metrics['Datapoints']:
                                hour = dp['Timestamp'].hour
                                weekday = dp['Timestamp'].weekday()

                                # Business hours: 9 AM - 6 PM, Monday-Friday
                                if business_start <= hour < business_end and weekday < 5:
                                    business_hours_cpu.append(dp['Average'])
                                else:
                                    non_business_hours_cpu.append(dp['Average'])

                            if business_hours_cpu and non_business_hours_cpu:
                                avg_business = sum(business_hours_cpu) / len(business_hours_cpu)
                                avg_non_business = sum(non_business_hours_cpu) / len(non_business_hours_cpu)

                                # Flag if non-business hours CPU is very low
                                if avg_non_business < cpu_threshold and avg_business > (cpu_threshold * 2):
                                    current_cost = self._estimate_ec2_instance_cost(instance_type)
                                    # Savings assuming 67% reduction (running only 45h/week vs 168h/week)
                                    savings = current_cost * 0.73

                                    orphans.append(OrphanResourceData(
                                        resource_type="ec2_instance",
                                        resource_id=instance_id,
                                        resource_name=name,
                                        region=region,
                                        estimated_monthly_cost=round(savings, 2),
                                        resource_metadata={
                                            'instance_type': instance_type,
                                            'avg_cpu_business_hours': round(avg_business, 1),
                                            'avg_cpu_non_business': round(avg_non_business, 1),
                                            'current_monthly_cost': current_cost,
                                            'scheduled_monthly_cost': round(current_cost * 0.27, 2),
                                            'monthly_savings': round(savings, 2),
                                            'recommendation': f'Schedule on/off: {business_start}AM-{business_end}PM weekdays only',
                                            'confidence': 'high',
                                            'scenario': 'ec2_instance_scheduled_unused',
                                            'tags': tags
                                        }
                                    ))

        except ClientError as e:
            print(f"Error scanning scheduled unused instances in {region}: {e}")

        return orphans

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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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

    async def scan_stopped_databases(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for RDS instances with comprehensive orphan detection.

        Detection scenarios:
        1. Stopped long-term - RDS stopped > min_stopped_days
        2. Idle running - Running with 0 database connections
        3. Zero I/O - Running with 0 read/write operations
        4. Never connected - Created but never connected since creation
        5. No backups - Automated backups disabled (BackupRetentionPeriod = 0)

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of stopped/idle RDS instance resources
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("rds_instance", {})

        # Check if detection is enabled
        if not detection_rules.get("enabled", True):
            return orphans

        # Load configuration
        min_stopped_days = detection_rules.get("min_stopped_days", 7)
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 14)
        critical_age_days = detection_rules.get("critical_age_days", 30)
        detect_idle_running = detection_rules.get("detect_idle_running", True)
        min_idle_days = detection_rules.get("min_idle_days", 7)
        idle_confidence_threshold_days = detection_rules.get("idle_confidence_threshold_days", 14)
        detect_zero_io = detection_rules.get("detect_zero_io", True)
        min_zero_io_days = detection_rules.get("min_zero_io_days", 7)
        detect_never_connected = detection_rules.get("detect_never_connected", True)
        never_connected_min_age_days = detection_rules.get("never_connected_min_age_days", 7)
        detect_no_backups = detection_rules.get("detect_no_backups", True)
        no_backups_min_age_days = detection_rules.get("no_backups_min_age_days", 30)

        try:
            async with self.session.client("rds", region_name=region) as rds, self.session.client(
                "cloudwatch", region_name=region
            ) as cloudwatch:
                response = await rds.describe_db_instances()

                for db in response.get("DBInstances", []):
                    db_id = db["DBInstanceIdentifier"]
                    status = db["DBInstanceStatus"]
                    db_class = db["DBInstanceClass"]
                    engine = db["Engine"]
                    storage_gb = db["AllocatedStorage"]
                    storage_type = db.get("StorageType", "gp2")
                    multi_az = db.get("MultiAZ", False)
                    backup_retention_period = db.get("BackupRetentionPeriod", 0)
                    created_time = db.get("InstanceCreateTime")

                    # Calculate age
                    now = datetime.now(timezone.utc)
                    age_days = (now - created_time).days if created_time else 0

                    # Calculate monthly cost
                    # Storage cost
                    storage_cost_per_gb = self.PRICING.get(f"rds_storage_{storage_type}_per_gb", 0.115)
                    storage_cost = storage_gb * storage_cost_per_gb

                    # Compute cost (only when running)
                    compute_cost = 0.0
                    if status == "available":
                        # Try to map db_class to pricing key
                        # Format: db.t3.micro -> rds_db_t3_micro
                        db_class_key = f"rds_{db_class.replace('.', '_')}"
                        compute_cost = self.PRICING.get(db_class_key, 0.0)

                        # If not in pricing dict, estimate based on common patterns
                        if compute_cost == 0.0:
                            if "t3.micro" in db_class:
                                compute_cost = self.PRICING["rds_db_t3_micro"]
                            elif "t3.small" in db_class:
                                compute_cost = self.PRICING["rds_db_t3_small"]
                            elif "t3.medium" in db_class:
                                compute_cost = self.PRICING["rds_db_t3_medium"]
                            elif "t3.large" in db_class:
                                compute_cost = self.PRICING["rds_db_t3_large"]
                            elif "t4g.micro" in db_class:
                                compute_cost = self.PRICING["rds_db_t4g_micro"]
                            elif "t4g.small" in db_class:
                                compute_cost = self.PRICING["rds_db_t4g_small"]
                            elif "m5.large" in db_class:
                                compute_cost = self.PRICING["rds_db_m5_large"]
                            elif "m5.xlarge" in db_class:
                                compute_cost = self.PRICING["rds_db_m5_xlarge"]
                            elif "m5.2xlarge" in db_class:
                                compute_cost = self.PRICING["rds_db_m5_2xlarge"]
                            else:
                                # Fallback: assume t3.small equivalent
                                compute_cost = self.PRICING["rds_db_t3_small"]

                        # Multi-AZ doubles the compute cost
                        if multi_az:
                            compute_cost *= 2

                    # Total cost
                    if status == "stopped":
                        monthly_cost = storage_cost  # Only storage when stopped
                    else:
                        monthly_cost = compute_cost + storage_cost

                    # Initialize detection variables
                    is_orphaned = False
                    orphan_type = None
                    orphan_reasons = []
                    confidence_level = "low"

                    # CloudWatch metrics (only for running instances)
                    avg_connections = 0
                    avg_read_iops = 0
                    avg_write_iops = 0

                    if status == "available" and (detect_idle_running or detect_zero_io or detect_never_connected):
                        # Get CloudWatch metrics for last 30 days
                        end_time = now
                        start_time = now - timedelta(days=30)

                        # DatabaseConnections metric
                        try:
                            connections_response = await cloudwatch.get_metric_statistics(
                                Namespace="AWS/RDS",
                                MetricName="DatabaseConnections",
                                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=86400,  # 1 day
                                Statistics=["Average"],
                            )
                            datapoints = connections_response.get("Datapoints", [])
                            if datapoints:
                                avg_connections = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                        except Exception as e:
                            print(f"Warning: Could not get DatabaseConnections for {db_id}: {e}")

                        # ReadIOPS metric
                        try:
                            read_iops_response = await cloudwatch.get_metric_statistics(
                                Namespace="AWS/RDS",
                                MetricName="ReadIOPS",
                                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=86400,
                                Statistics=["Average"],
                            )
                            datapoints = read_iops_response.get("Datapoints", [])
                            if datapoints:
                                avg_read_iops = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                        except Exception as e:
                            print(f"Warning: Could not get ReadIOPS for {db_id}: {e}")

                        # WriteIOPS metric
                        try:
                            write_iops_response = await cloudwatch.get_metric_statistics(
                                Namespace="AWS/RDS",
                                MetricName="WriteIOPS",
                                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=86400,
                                Statistics=["Average"],
                            )
                            datapoints = write_iops_response.get("Datapoints", [])
                            if datapoints:
                                avg_write_iops = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                        except Exception as e:
                            print(f"Warning: Could not get WriteIOPS for {db_id}: {e}")

                    # Scenario #1: Stopped long-term
                    if status == "stopped":
                        if age_days >= min_stopped_days:
                            is_orphaned = True
                            orphan_type = "stopped"
                            orphan_reasons.append(f"Database stopped for {age_days} days")

                            if age_days >= critical_age_days:
                                confidence_level = "critical"
                                orphan_reasons.append(f"CRITICAL: Stopped for {age_days}+ days (threshold: {critical_age_days})")
                            elif age_days >= confidence_threshold_days:
                                confidence_level = "high"
                                orphan_reasons.append(f"Stopped longer than {confidence_threshold_days} days")
                            else:
                                confidence_level = "medium"

                    # Scenario #4: Never connected (check first as it's a special case of idle)
                    elif detect_never_connected and status == "available" and age_days >= never_connected_min_age_days:
                        if avg_connections == 0:
                            is_orphaned = True
                            orphan_type = "never_connected"
                            orphan_reasons.append(f"Created {age_days} days ago but never connected")
                            orphan_reasons.append("0 database connections since creation")
                            confidence_level = "high" if age_days >= 14 else "medium"

                    # Scenario #2: Idle running (0 connections, but exclude never_connected)
                    elif detect_idle_running and status == "available" and orphan_type != "never_connected":
                        if avg_connections == 0 and age_days >= min_idle_days:
                            is_orphaned = True
                            orphan_type = "idle_running"
                            orphan_reasons.append(f"Running with 0 connections for {age_days}+ days")
                            orphan_reasons.append("Paying full compute cost for unused database")

                            if age_days >= idle_confidence_threshold_days:
                                confidence_level = "high"
                            else:
                                confidence_level = "medium"

                    # Scenario #3: Zero I/O (no read/write operations)
                    elif detect_zero_io and status == "available" and orphan_type is None:
                        if avg_read_iops == 0 and avg_write_iops == 0 and age_days >= min_zero_io_days:
                            is_orphaned = True
                            orphan_type = "zero_io"
                            orphan_reasons.append(f"No read/write operations in 30 days")
                            orphan_reasons.append(f"ReadIOPS: {avg_read_iops:.2f}, WriteIOPS: {avg_write_iops:.2f}")
                            confidence_level = "medium"

                    # Scenario #5: No backups (can combine with other scenarios)
                    if detect_no_backups and backup_retention_period == 0 and age_days >= no_backups_min_age_days:
                        if not is_orphaned:
                            is_orphaned = True
                            orphan_type = "no_backups"
                            confidence_level = "medium"
                        orphan_reasons.append("No automated backups configured (BackupRetentionPeriod = 0)")
                        orphan_reasons.append("Indicates abandoned or non-production database")

                    # Add to orphans list if detected
                    if is_orphaned:
                        # Calculate wasted amount (how much already spent)
                        wasted_amount = round(monthly_cost * (age_days / 30), 2) if age_days > 0 else 0

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
                                    "storage_type": storage_type,
                                    "multi_az": multi_az,
                                    "backup_retention_period": backup_retention_period,
                                    "age_days": age_days,
                                    "orphan_type": orphan_type,
                                    "orphan_reason": " | ".join(orphan_reasons),
                                    "orphan_reasons": orphan_reasons,
                                    "confidence_level": confidence_level,
                                    "compute_cost_monthly": round(compute_cost, 2),
                                    "storage_cost_monthly": round(storage_cost, 2),
                                    "cloudwatch_stats": {
                                        "avg_connections": round(avg_connections, 2),
                                        "avg_read_iops": round(avg_read_iops, 2),
                                        "avg_write_iops": round(avg_write_iops, 2),
                                    },
                                    "wasted_amount": wasted_amount,
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning RDS instances in {region}: {e}")

        return orphans

    async def scan_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for NAT gateways with no outbound traffic or misconfigured routing.

        Detection scenarios (Phase 1 - MVP: 7/10):
        1. No route table references (orphaned)
        2. Zero traffic (BytesOutToDestination = 0)
        3. Route tables not associated with any subnet
        4. VPC without Internet Gateway (broken config)
        5. NAT Gateway in public subnet (misconfigured)
        6. Redundant NAT Gateways in same AZ (unnecessary HA cost)
        7. Low traffic < 10 GB/month (NAT Instance alternative)

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
        max_bytes_30d = detection_rules.get("max_bytes_30d", 1_000_000)  # Scenario 2: zero traffic
        low_traffic_threshold_gb = detection_rules.get("low_traffic_threshold_gb", 10.0)  # Scenario 7: low traffic
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 30)
        critical_age_days = detection_rules.get("critical_age_days", 90)
        detect_no_routes = detection_rules.get("detect_no_routes", True)
        detect_no_igw = detection_rules.get("detect_no_igw", True)
        detect_public_subnet = detection_rules.get("detect_public_subnet", True)
        detect_redundant_same_az = detection_rules.get("detect_redundant_same_az", True)

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

                # Get all subnets to determine AZs and public/private status
                subnets_response = await ec2.describe_subnets()
                subnets_by_id = {}
                for subnet in subnets_response.get("Subnets", []):
                    subnets_by_id[subnet["SubnetId"]] = subnet

                # Build VPC+AZ grouping for redundancy detection (Scenario 6)
                nat_gw_by_vpc_az: dict[str, list[dict]] = {}
                for nat_gw in nat_response.get("NatGateways", []):
                    subnet_id = nat_gw.get("SubnetId")
                    vpc_id = nat_gw.get("VpcId")
                    if subnet_id in subnets_by_id:
                        az = subnets_by_id[subnet_id]["AvailabilityZone"]
                        key = f"{vpc_id}_{az}"
                        if key not in nat_gw_by_vpc_az:
                            nat_gw_by_vpc_az[key] = []
                        nat_gw_by_vpc_az[key].append(nat_gw)

                async with self.session.client("cloudwatch", region_name=region) as cw:
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=30)

                    for nat_gw in nat_response.get("NatGateways", []):
                        nat_gw_id = nat_gw["NatGatewayId"]
                        vpc_id = nat_gw.get("VpcId", "Unknown")
                        subnet_id = nat_gw.get("SubnetId", "Unknown")
                        created_at = nat_gw["CreateTime"]
                        age_days = (end_time - created_at).days

                        # Skip if NAT Gateway is too young
                        if age_days < min_age_days:
                            continue

                        # Get AZ and subnet info
                        availability_zone = "Unknown"
                        if subnet_id in subnets_by_id:
                            availability_zone = subnets_by_id[subnet_id]["AvailabilityZone"]

                        # Analyze routing configuration
                        route_tables_with_nat = []
                        associated_subnets_count = 0
                        nat_gw_subnet_is_public = False

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

                            # Scenario 5: Check if NAT GW is in public subnet
                            # A subnet is public if its route table has a route to an IGW
                            if detect_public_subnet:
                                # Check if this route table is associated with the NAT GW's subnet
                                for association in rt.get("Associations", []):
                                    if association.get("SubnetId") == subnet_id:
                                        # Check if route table has IGW route
                                        for route in rt.get("Routes", []):
                                            if route.get("GatewayId", "").startswith("igw-"):
                                                nat_gw_subnet_is_public = True
                                                break

                        has_routes = len(route_tables_with_nat) > 0
                        has_associated_subnets = associated_subnets_count > 0
                        vpc_has_igw = vpc_id in vpcs_with_igw

                        # Scenario 6: Check for redundancy in same AZ
                        is_redundant_same_az = False
                        redundant_nat_gw_count = 0
                        redundant_nat_gw_ids = []
                        if detect_redundant_same_az:
                            vpc_az_key = f"{vpc_id}_{availability_zone}"
                            if vpc_az_key in nat_gw_by_vpc_az and len(nat_gw_by_vpc_az[vpc_az_key]) > 1:
                                is_redundant_same_az = True
                                redundant_nat_gw_count = len(nat_gw_by_vpc_az[vpc_az_key])
                                redundant_nat_gw_ids = [gw["NatGatewayId"] for gw in nat_gw_by_vpc_az[vpc_az_key]]

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
                        total_gb = total_bytes / (1024 ** 3)

                        # Determine if orphaned based on multiple criteria
                        is_orphaned = False
                        orphan_reasons = []
                        orphan_type = None
                        scenario_id = None

                        # Scenario 1: No route tables reference this NAT Gateway
                        if detect_no_routes and not has_routes:
                            is_orphaned = True
                            orphan_type = "no_routes"
                            scenario_id = "nat_gateway_no_route_table"
                            orphan_reasons.append("Not referenced in any route table")

                        # Scenario 3: Has routes but none are associated with subnets
                        elif has_routes and not has_associated_subnets:
                            is_orphaned = True
                            orphan_type = "routes_not_associated"
                            scenario_id = "nat_gateway_routes_not_associated"
                            orphan_reasons.append(
                                f"Referenced in {len(route_tables_with_nat)} route table(s) but none associated with subnets"
                            )

                        # Scenario 4: VPC has no Internet Gateway (broken config)
                        if detect_no_igw and not vpc_has_igw:
                            is_orphaned = True
                            if not orphan_type:
                                orphan_type = "no_igw"
                                scenario_id = "nat_gateway_no_igw"
                            orphan_reasons.append(
                                "VPC has no Internet Gateway (NAT Gateway cannot route to internet)"
                            )

                        # Scenario 5: NAT Gateway in public subnet
                        if detect_public_subnet and nat_gw_subnet_is_public:
                            is_orphaned = True
                            if not orphan_type:
                                orphan_type = "public_subnet"
                                scenario_id = "nat_gateway_in_public_subnet"
                            orphan_reasons.append(
                                "NAT Gateway in public subnet (subnet has route to IGW - misconfigured)"
                            )

                        # Scenario 6: Redundant NAT Gateway in same AZ
                        if detect_redundant_same_az and is_redundant_same_az:
                            is_orphaned = True
                            if not orphan_type:
                                orphan_type = "redundant_same_az"
                                scenario_id = "nat_gateway_redundant_same_az"
                            orphan_reasons.append(
                                f"{redundant_nat_gw_count} NAT Gateways in same VPC+AZ (no HA benefit, only 1 needed)"
                            )

                        # Scenario 2: Zero traffic
                        if total_bytes < max_bytes_30d:
                            if not is_orphaned:
                                orphan_type = "zero_traffic"
                                scenario_id = "nat_gateway_zero_traffic"
                            orphan_reasons.append(
                                f"Only {(total_bytes / 1024):.2f} KB traffic in 30 days (zero usage)"
                            )
                            is_orphaned = True

                        # Scenario 7: Low traffic (< 10 GB/month default)
                        elif total_gb < low_traffic_threshold_gb:
                            if not is_orphaned:
                                orphan_type = "low_traffic"
                                scenario_id = "nat_gateway_low_traffic"
                            orphan_reasons.append(
                                f"Only {total_gb:.2f} GB traffic in 30 days (< {low_traffic_threshold_gb} GB threshold - NAT Instance more cost-effective)"
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
                                    "subnet_id": subnet_id,
                                    "availability_zone": availability_zone,
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "bytes_out_30d": int(total_bytes),
                                    "traffic_gb_30d": round(total_gb, 2),
                                    "confidence": confidence,
                                    "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                    "orphan_reason": orphan_reason,
                                    "orphan_type": orphan_type,
                                    "scenario_id": scenario_id,
                                    # Enhanced metadata
                                    "has_routes": has_routes,
                                    "route_tables_count": len(route_tables_with_nat),
                                    "associated_subnets_count": associated_subnets_count,
                                    "vpc_has_igw": vpc_has_igw,
                                    "nat_gw_subnet_is_public": nat_gw_subnet_is_public,
                                    "is_redundant_same_az": is_redundant_same_az,
                                    "redundant_nat_gw_count": redundant_nat_gw_count,
                                    "redundant_nat_gw_ids": redundant_nat_gw_ids if is_redundant_same_az else [],
                                    "orphan_reasons": orphan_reasons,
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning unused NAT gateways in {region}: {e}")

        return orphans

    async def scan_nat_gateway_vpc_endpoint_candidates(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for NAT Gateways that could benefit from VPC Endpoints (Scenario 8).

        Simplified MVP version without VPC Flow Logs:
        - Detects NAT GW in VPCs without S3/DynamoDB VPC Endpoints
        - Recommends VPC Endpoints (free) to eliminate data processing costs
        - Flags candidates with traffic <50 GB/month (high ROI)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of NAT gateways that could benefit from VPC Endpoints
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("nat_gateway", {})

        # Check if detection is enabled
        if not detection_rules.get("detect_vpc_endpoint_candidates", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 7)
        vpc_endpoint_traffic_threshold_gb = detection_rules.get("vpc_endpoint_traffic_threshold_gb", 50.0)
        detect_missing_s3_endpoint = detection_rules.get("detect_missing_s3_endpoint", True)
        detect_missing_dynamodb_endpoint = detection_rules.get("detect_missing_dynamodb_endpoint", True)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all NAT Gateways
                nat_response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                # Get all VPC Endpoints to check which VPCs already have them
                vpc_endpoints_response = await ec2.describe_vpc_endpoints()
                vpcs_with_s3_endpoint = set()
                vpcs_with_dynamodb_endpoint = set()

                for endpoint in vpc_endpoints_response.get("VpcEndpoints", []):
                    service_name = endpoint.get("ServiceName", "")
                    vpc_id = endpoint.get("VpcId")

                    if f"com.amazonaws.{region}.s3" in service_name:
                        vpcs_with_s3_endpoint.add(vpc_id)
                    elif f"com.amazonaws.{region}.dynamodb" in service_name:
                        vpcs_with_dynamodb_endpoint.add(vpc_id)

                async with self.session.client("cloudwatch", region_name=region) as cw:
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=30)

                    for nat_gw in nat_response.get("NatGateways", []):
                        nat_gw_id = nat_gw["NatGatewayId"]
                        vpc_id = nat_gw.get("VpcId", "Unknown")
                        created_at = nat_gw["CreateTime"]
                        age_days = (end_time - created_at).days

                        # Skip if too young
                        if age_days < min_age_days:
                            continue

                        # Query CloudWatch for traffic
                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/NATGateway",
                            MetricName="BytesOutToDestination",
                            Dimensions=[{"Name": "NatGatewayId", "Value": nat_gw_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=["Sum"],
                        )

                        total_bytes = sum(dp["Sum"] for dp in metrics_response.get("Datapoints", []))
                        total_gb = total_bytes / (1024 ** 3)

                        # Only flag if traffic is low enough for VPC Endpoints to be beneficial
                        if total_gb > vpc_endpoint_traffic_threshold_gb:
                            continue

                        # Check for missing VPC Endpoints
                        missing_endpoints = []
                        if detect_missing_s3_endpoint and vpc_id not in vpcs_with_s3_endpoint:
                            missing_endpoints.append("S3")
                        if detect_missing_dynamodb_endpoint and vpc_id not in vpcs_with_dynamodb_endpoint:
                            missing_endpoints.append("DynamoDB")

                        # Skip if no missing endpoints
                        if not missing_endpoints:
                            continue

                        # Calculate potential savings
                        # VPC Endpoints are free, so savings = data processing cost
                        # Conservative estimate: assume 20-50% of traffic could use VPC Endpoints
                        estimated_vpc_endpoint_traffic_percent = 30.0  # Conservative estimate
                        data_processing_cost = total_gb * 0.045  # NAT GW data processing
                        potential_monthly_savings = data_processing_cost * (estimated_vpc_endpoint_traffic_percent / 100)

                        # Extract name from tags
                        name = None
                        for tag in nat_gw.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        orphan_reason = f"VPC missing {' and '.join(missing_endpoints)} VPC Endpoint(s) - could eliminate data processing costs"

                        orphans.append(
                            OrphanResourceData(
                                resource_type="nat_gateway",
                                resource_id=nat_gw_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=potential_monthly_savings,
                                resource_metadata={
                                    "vpc_id": vpc_id,
                                    "subnet_id": nat_gw.get("SubnetId", "Unknown"),
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "traffic_gb_30d": round(total_gb, 2),
                                    "confidence_level": "medium",
                                    "orphan_reason": orphan_reason,
                                    "orphan_type": "vpc_endpoint_candidate",
                                    "scenario_id": "nat_gateway_s3_dynamodb_vpc_endpoints",
                                    # VPC Endpoint metadata
                                    "missing_vpc_endpoints": missing_endpoints,
                                    "has_s3_vpc_endpoint": vpc_id in vpcs_with_s3_endpoint,
                                    "has_dynamodb_vpc_endpoint": vpc_id in vpcs_with_dynamodb_endpoint,
                                    "data_processing_cost_30d": round(data_processing_cost, 2),
                                    "estimated_savings_potential": round(potential_monthly_savings, 2),
                                    "recommendation": f"Create FREE VPC Endpoint(s) for {', '.join(missing_endpoints)} to eliminate data processing costs. VPC Endpoints are free and could save ~${potential_monthly_savings:.2f}/month (conservative estimate).",
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning NAT Gateway VPC Endpoint candidates in {region}: {e}")

        return orphans

    async def scan_nat_gateway_dev_test_unused_hours(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for dev/test NAT Gateways with traffic only during business hours (Scenario 9).

        Analyzes hourly traffic patterns to detect NAT GW that could be scheduled:
        - Checks for Environment=dev/test/staging tags
        - Analyzes CloudWatch hourly metrics over 7 days
        - Calculates % of traffic during business hours (8AM-6PM Mon-Fri)
        - Flags if >90% traffic during business hours (scheduling opportunity)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of dev/test NAT gateways with business-hours-only traffic
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("nat_gateway", {})

        # Check if detection is enabled
        if not detection_rules.get("detect_dev_test_unused_hours", True):
            return orphans

        min_age_days = detection_rules.get("min_age_days", 7)
        business_hours_start = detection_rules.get("business_hours_start", 8)
        business_hours_end = detection_rules.get("business_hours_end", 18)
        business_days = detection_rules.get("business_days", [0, 1, 2, 3, 4])  # Mon-Fri
        business_hours_traffic_threshold = detection_rules.get("business_hours_traffic_threshold", 90.0)
        dev_test_pattern_lookback_days = detection_rules.get("dev_test_pattern_lookback_days", 7)
        nonprod_env_tags = detection_rules.get("nonprod_env_tags", ["Environment", "Env", "Stage"])
        nonprod_env_values = detection_rules.get("nonprod_env_values", ["dev", "development", "test", "testing", "staging", "qa"])

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all NAT Gateways
                nat_response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                async with self.session.client("cloudwatch", region_name=region) as cw:
                    end_time = datetime.now(timezone.utc)
                    start_time = end_time - timedelta(days=dev_test_pattern_lookback_days)

                    for nat_gw in nat_response.get("NatGateways", []):
                        nat_gw_id = nat_gw["NatGatewayId"]
                        vpc_id = nat_gw.get("VpcId", "Unknown")
                        created_at = nat_gw["CreateTime"]
                        age_days = (end_time - created_at).days

                        # Skip if too young
                        if age_days < min_age_days:
                            continue

                        # Check if this is a dev/test environment
                        tags = {tag["Key"]: tag["Value"] for tag in nat_gw.get("Tags", [])}
                        is_nonprod = False
                        environment_value = None

                        for tag_key in nonprod_env_tags:
                            if tag_key in tags:
                                env_value = tags[tag_key].lower()
                                if env_value in [v.lower() for v in nonprod_env_values]:
                                    is_nonprod = True
                                    environment_value = env_value
                                    break

                        # Skip if not non-prod
                        if not is_nonprod:
                            continue

                        # Get hourly metrics (Period=3600 seconds = 1 hour)
                        metrics_response = await cw.get_metric_statistics(
                            Namespace="AWS/NATGateway",
                            MetricName="BytesOutToDestination",
                            Dimensions=[{"Name": "NatGatewayId", "Value": nat_gw_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,  # 1 hour periods
                            Statistics=["Sum"],
                        )

                        # Group traffic by hour of day and day of week
                        from collections import defaultdict
                        traffic_by_hour = defaultdict(list)
                        business_hours_traffic = 0
                        total_traffic = 0

                        for dp in metrics_response.get("Datapoints", []):
                            timestamp = dp["Timestamp"]
                            bytes_value = dp["Sum"]
                            total_traffic += bytes_value

                            hour = timestamp.hour
                            day_of_week = timestamp.weekday()  # 0=Monday, 6=Sunday

                            traffic_by_hour[hour].append(bytes_value)

                            # Check if this is business hours
                            if day_of_week in business_days and business_hours_start <= hour < business_hours_end:
                                business_hours_traffic += bytes_value

                        # Skip if no traffic
                        if total_traffic == 0:
                            continue

                        # Calculate business hours percentage
                        business_hours_percent = (business_hours_traffic / total_traffic) * 100

                        # Skip if not concentrated in business hours
                        if business_hours_percent < business_hours_traffic_threshold:
                            continue

                        # Calculate potential savings
                        # NAT GW charged 24/7 ($32.40/month)
                        # Business hours only: 50 hours/week = ~30% of time
                        monthly_cost_current = self.PRICING["nat_gateway"]
                        business_hours_per_week = (business_hours_end - business_hours_start) * len(business_days)
                        hours_per_week = 168
                        business_hours_ratio = business_hours_per_week / hours_per_week
                        monthly_cost_if_scheduled = monthly_cost_current * business_hours_ratio
                        monthly_savings = monthly_cost_current - monthly_cost_if_scheduled

                        # Extract name from tags
                        name = tags.get("Name", None)

                        orphan_reason = f"Dev/Test NAT Gateway with {business_hours_percent:.1f}% traffic during business hours - scheduling opportunity"

                        orphans.append(
                            OrphanResourceData(
                                resource_type="nat_gateway",
                                resource_id=nat_gw_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=monthly_savings,
                                resource_metadata={
                                    "vpc_id": vpc_id,
                                    "subnet_id": nat_gw.get("SubnetId", "Unknown"),
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "environment": environment_value,
                                    "confidence_level": "medium",
                                    "orphan_reason": orphan_reason,
                                    "orphan_type": "dev_test_unused_hours",
                                    "scenario_id": "nat_gateway_dev_test_unused_hours",
                                    # Business hours pattern metadata
                                    "business_hours_percent": round(business_hours_percent, 1),
                                    "total_traffic_7d_gb": round(total_traffic / (1024 ** 3), 2),
                                    "business_hours_traffic_gb": round(business_hours_traffic / (1024 ** 3), 2),
                                    "business_hours_definition": f"{business_hours_start}h-{business_hours_end}h Mon-Fri",
                                    "monthly_cost_current": round(monthly_cost_current, 2),
                                    "monthly_savings_if_scheduled": round(monthly_savings, 2),
                                    "annual_savings": round(monthly_savings * 12, 2),
                                    "recommendation": f"Dev/Test NAT Gateway with {business_hours_percent:.1f}% traffic during business hours. Options: 1) Delete/recreate via Lambda (save ${monthly_savings:.2f}/month), 2) Migrate to NAT Instance (can be stopped), 3) Accept 24/7 cost. Annual savings potential: ${monthly_savings * 12:.2f}/year.",
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning NAT Gateway dev/test unused hours in {region}: {e}")

        return orphans

    async def scan_nat_gateway_obsolete_migration(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for obsolete NAT Gateways after architecture migration (Scenario 10).

        Detects NAT GW with dramatic traffic drop (>90%) over 90 days:
        - Compares baseline traffic (J-90 to J-60) vs current (J-7 to J-0)
        - Flags NAT GW with >90% traffic drop
        - Indicates likely obsolescence due to migration to serverless, containers, or VPC Endpoints

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of NAT gateways likely obsolete after migration
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("nat_gateway", {})

        # Check if detection is enabled
        if not detection_rules.get("detect_obsolete_migration", True):
            return orphans

        migration_min_age_days = detection_rules.get("migration_min_age_days", 90)
        traffic_drop_threshold_percent = detection_rules.get("traffic_drop_threshold_percent", 90.0)

        try:
            async with self.session.client("ec2", region_name=region) as ec2:
                # Get all NAT Gateways
                nat_response = await ec2.describe_nat_gateways(
                    Filters=[{"Name": "state", "Values": ["available"]}]
                )

                async with self.session.client("cloudwatch", region_name=region) as cw:
                    now = datetime.now(timezone.utc)

                    for nat_gw in nat_response.get("NatGateways", []):
                        nat_gw_id = nat_gw["NatGatewayId"]
                        vpc_id = nat_gw.get("VpcId", "Unknown")
                        created_at = nat_gw["CreateTime"]
                        age_days = (now - created_at).days

                        # Skip if not old enough
                        if age_days < migration_min_age_days:
                            continue

                        # Define 4 comparison periods
                        periods = {
                            "baseline_90_60d": (now - timedelta(days=90), now - timedelta(days=60)),
                            "period_60_30d": (now - timedelta(days=60), now - timedelta(days=30)),
                            "period_30_7d": (now - timedelta(days=30), now - timedelta(days=7)),
                            "current_7d": (now - timedelta(days=7), now),
                        }

                        traffic_by_period = {}

                        # Query CloudWatch for each period
                        for period_name, (start, end) in periods.items():
                            period_seconds = int((end - start).total_seconds())

                            metrics_response = await cw.get_metric_statistics(
                                Namespace="AWS/NATGateway",
                                MetricName="BytesOutToDestination",
                                Dimensions=[{"Name": "NatGatewayId", "Value": nat_gw_id}],
                                StartTime=start,
                                EndTime=end,
                                Period=period_seconds,  # Single period covering entire range
                                Statistics=["Sum"],
                            )

                            total_bytes = sum(dp["Sum"] for dp in metrics_response.get("Datapoints", []))
                            traffic_by_period[period_name] = total_bytes

                        baseline = traffic_by_period["baseline_90_60d"]
                        current = traffic_by_period["current_7d"]

                        # Skip if baseline is zero (can't calculate drop %)
                        if baseline == 0:
                            continue

                        # Normalize to same time period (30 days for baseline, 7 days for current)
                        # Multiply current by (30/7) to extrapolate to 30-day equivalent
                        current_30d_equivalent = current * (30 / 7)

                        # Calculate traffic drop percentage
                        drop_percent = ((baseline - current_30d_equivalent) / baseline) * 100

                        # Skip if drop is not significant
                        if drop_percent < traffic_drop_threshold_percent:
                            continue

                        # Calculate savings
                        monthly_cost = self.PRICING["nat_gateway"]

                        # Extract name from tags
                        name = None
                        for tag in nat_gw.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        baseline_gb = baseline / (1024 ** 3)
                        current_gb = current / (1024 ** 3)
                        current_30d_gb = current_30d_equivalent / (1024 ** 3)

                        orphan_reason = f"Traffic dropped {drop_percent:.1f}% in 90 days (from {baseline_gb:.2f} GB to {current_30d_gb:.2f} GB/month) - likely obsolete after migration"

                        orphans.append(
                            OrphanResourceData(
                                resource_type="nat_gateway",
                                resource_id=nat_gw_id,
                                resource_name=name,
                                region=region,
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "vpc_id": vpc_id,
                                    "subnet_id": nat_gw.get("SubnetId", "Unknown"),
                                    "created_at": created_at.isoformat(),
                                    "age_days": age_days,
                                    "confidence_level": "high",
                                    "orphan_reason": orphan_reason,
                                    "orphan_type": "obsolete_migration",
                                    "scenario_id": "nat_gateway_obsolete_migration",
                                    # Traffic trend metadata
                                    "baseline_traffic_gb_30d": round(baseline_gb, 2),
                                    "period_60_30d_gb": round(traffic_by_period["period_60_30d"] / (1024 ** 3), 2),
                                    "period_30_7d_gb": round(traffic_by_period["period_30_7d"] / (1024 ** 3), 2),
                                    "current_traffic_gb_7d": round(current_gb, 2),
                                    "current_traffic_gb_30d_projected": round(current_30d_gb, 2),
                                    "traffic_drop_percent": round(drop_percent, 1),
                                    "monthly_savings": round(monthly_cost, 2),
                                    "annual_savings": round(monthly_cost * 12, 2),
                                    "recommendation": f"Traffic dropped {drop_percent:.1f}% in 90 days (from {baseline_gb:.2f} GB to {current_30d_gb:.2f} GB/month). NAT Gateway likely obsolete after architecture migration (serverless, containers, or VPC Endpoints). Delete to save ${monthly_cost:.2f}/month (${monthly_cost * 12:.2f}/year).",
                                },
                            )
                        )

        except ClientError as e:
            print(f"Error scanning NAT Gateway obsolete migration in {region}: {e}")

        return orphans

    async def scan_unused_fsx_file_systems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for unused FSx file systems using CloudWatch metrics and advanced detection.

        Detects 8 scenarios (by priority):
        1. Completely inactive (0 read/write transfers for 30+ days)
        2. Over-provisioned storage (<10% storage used)
        3. Over-provisioned throughput (<10% throughput utilized)
        4. Excessive backup retention (orphaned backups)
        5. Unused file shares (Windows: 0 SMB connections for 7+ days)
        6. Low IOPS utilization (<10% IOPS used)
        7. Multi-AZ overkill (Multi-AZ in dev/test environments)
        8. Wrong storage type (SSD for archive workloads)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned FSx file systems
        """
        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 30) if detection_rules else 30

        # Scenario 1: Completely inactive
        detect_inactive = detection_rules.get("detect_inactive", True) if detection_rules else True
        inactive_lookback_days = detection_rules.get("inactive_lookback_days", 30) if detection_rules else 30

        # Scenario 2: Over-provisioned storage
        detect_over_provisioned_storage = detection_rules.get("detect_over_provisioned_storage", True) if detection_rules else True
        storage_usage_threshold = detection_rules.get("storage_usage_threshold_percent", 10.0) if detection_rules else 10.0
        storage_lookback_days = detection_rules.get("storage_lookback_days", 7) if detection_rules else 7

        # Scenario 3: Over-provisioned throughput
        detect_over_provisioned_throughput = detection_rules.get("detect_over_provisioned_throughput", True) if detection_rules else True
        throughput_utilization_threshold = detection_rules.get("throughput_utilization_threshold_percent", 10.0) if detection_rules else 10.0
        throughput_lookback_days = detection_rules.get("throughput_lookback_days", 7) if detection_rules else 7

        # Scenario 4: Excessive backups
        detect_excessive_backups = detection_rules.get("detect_excessive_backups", True) if detection_rules else True
        max_backup_retention_days = detection_rules.get("max_backup_retention_days", 30) if detection_rules else 30
        detect_orphaned_backups = detection_rules.get("detect_orphaned_backups", True) if detection_rules else True

        # Scenario 5: Unused file shares (Windows)
        detect_unused_file_shares = detection_rules.get("detect_unused_file_shares", True) if detection_rules else True
        min_zero_connections_days = detection_rules.get("min_zero_connections_days", 7) if detection_rules else 7

        # Scenario 6: Low IOPS utilization
        detect_low_iops_utilization = detection_rules.get("detect_low_iops_utilization", True) if detection_rules else True
        iops_utilization_threshold = detection_rules.get("iops_utilization_threshold_percent", 10.0) if detection_rules else 10.0
        iops_lookback_days = detection_rules.get("iops_lookback_days", 7) if detection_rules else 7

        # Scenario 7: Multi-AZ overkill
        detect_multi_az_overkill = detection_rules.get("detect_multi_az_overkill", True) if detection_rules else True
        multi_az_tag_key = detection_rules.get("multi_az_tag_key", "Environment") if detection_rules else "Environment"
        multi_az_tag_values = detection_rules.get("multi_az_tag_values", ["dev", "test", "development", "testing"]) if detection_rules else ["dev", "test", "development", "testing"]

        # Scenario 8: Wrong storage type
        detect_ssd_for_archive = detection_rules.get("detect_ssd_for_archive", True) if detection_rules else True
        archive_throughput_threshold = detection_rules.get("archive_throughput_threshold_mbps", 8.0) if detection_rules else 8.0

        try:
            async with self.session.client("fsx", region_name=region) as fsx:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    # Describe all file systems
                    response = await fsx.describe_file_systems()

                    for fs in response.get("FileSystems", []):
                        fs_id = fs["FileSystemId"]
                        fs_type = fs["FileSystemType"]  # LUSTRE, WINDOWS, ONTAP, OPENZFS
                        created_at = fs["CreationTime"]
                        age_days = (datetime.now(timezone.utc) - created_at).days

                        if age_days < min_age_days:
                            continue

                        # Extract common metadata
                        storage_capacity = fs["StorageCapacity"]  # in GB
                        deployment_type = fs.get("WindowsConfiguration", {}).get("DeploymentType") if fs_type == "WINDOWS" else None
                        is_multi_az = deployment_type == "MULTI_AZ_1" if deployment_type else False

                        # Extract tags
                        tags = {tag["Key"]: tag["Value"] for tag in fs.get("Tags", [])}
                        name = tags.get("Name")
                        environment_tag = tags.get(multi_az_tag_key, "").lower()

                        # Storage type (Windows only: SSD or HDD)
                        storage_type = None
                        if fs_type == "WINDOWS":
                            storage_type = fs.get("WindowsConfiguration", {}).get("StorageType", "SSD")

                        # Throughput capacity (Windows/ONTAP only)
                        throughput_capacity = None
                        if fs_type == "WINDOWS":
                            throughput_capacity = fs.get("WindowsConfiguration", {}).get("ThroughputCapacity")
                        elif fs_type == "ONTAP":
                            throughput_capacity = fs.get("OntapConfiguration", {}).get("ThroughputCapacity")

                        # ========================================
                        # PRIORITY 1: Completely Inactive
                        # ========================================
                        if detect_inactive:
                            now = datetime.now(timezone.utc)
                            start_time = now - timedelta(days=inactive_lookback_days)

                            # Check both read and write metrics
                            read_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="DataReadBytes",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=86400,  # 1 day
                                Statistics=["Sum"],
                            )

                            write_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="DataWriteBytes",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=86400,
                                Statistics=["Sum"],
                            )

                            total_read_bytes = sum(dp["Sum"] for dp in read_response.get("Datapoints", []))
                            total_write_bytes = sum(dp["Sum"] for dp in write_response.get("Datapoints", []))

                            if total_read_bytes == 0 and total_write_bytes == 0:
                                orphan_type = "inactive"
                                confidence = "critical" if age_days >= confidence_threshold_days else "high"

                                # Calculate cost
                                pricing_key = f"fsx_{fs_type.lower()}_per_gb"
                                monthly_cost = storage_capacity * self.PRICING.get(pricing_key, 0.14)

                                # Add throughput cost for Windows/ONTAP
                                if throughput_capacity and fs_type in ["WINDOWS", "ONTAP"]:
                                    monthly_cost += throughput_capacity * self.PRICING["fsx_throughput_per_mbps"]

                                # Multi-AZ doubles cost
                                if is_multi_az:
                                    monthly_cost *= 2

                                reason = f"No read/write activity detected over {inactive_lookback_days} days (file system age: {age_days} days)"

                                orphans.append(
                                    OrphanResourceData(
                                        resource_type="fsx_file_system",
                                        resource_id=fs_id,
                                        resource_name=name,
                                        region=region,
                                        estimated_monthly_cost=monthly_cost,
                                        resource_metadata={
                                            "file_system_type": fs_type,
                                            "orphan_type": orphan_type,
                                            "storage_capacity_gb": storage_capacity,
                                            "deployment_type": deployment_type,
                                            "is_multi_az": is_multi_az,
                                            "storage_type": storage_type,
                                            "throughput_capacity_mbps": throughput_capacity,
                                            "lifecycle_status": fs.get("Lifecycle", "Unknown"),
                                            "created_at": created_at.isoformat(),
                                            "age_days": age_days,
                                            "confidence": confidence,
                                            "orphan_reason": reason,
                                            "total_read_bytes": int(total_read_bytes),
                                            "total_write_bytes": int(total_write_bytes),
                                            "lookback_days": inactive_lookback_days,
                                        },
                                    )
                                )
                                continue  # Move to next file system (priority detection)

                        # ========================================
                        # PRIORITY 2: Over-Provisioned Storage
                        # ========================================
                        if detect_over_provisioned_storage:
                            now = datetime.now(timezone.utc)
                            start_time = now - timedelta(days=storage_lookback_days)

                            # Query StorageUsed metric
                            storage_used_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="StorageUsed",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=86400,
                                Statistics=["Average"],
                            )

                            datapoints = storage_used_response.get("Datapoints", [])
                            if datapoints:
                                # Get average storage used (in bytes, convert to GB)
                                avg_storage_used_bytes = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                                avg_storage_used_gb = avg_storage_used_bytes / (1024**3)
                                usage_percent = (avg_storage_used_gb / storage_capacity) * 100 if storage_capacity > 0 else 0

                                if usage_percent < storage_usage_threshold:
                                    orphan_type = "over_provisioned_storage"
                                    confidence = "high" if age_days >= confidence_threshold_days else "medium"

                                    # Calculate wasted storage cost
                                    wasted_storage_gb = storage_capacity - avg_storage_used_gb
                                    pricing_key = f"fsx_{fs_type.lower()}_per_gb"
                                    wasted_cost = wasted_storage_gb * self.PRICING.get(pricing_key, 0.14)

                                    # Multi-AZ doubles cost
                                    if is_multi_az:
                                        wasted_cost *= 2

                                    reason = f"Storage over-provisioned: {storage_capacity} GB provisioned but only {avg_storage_used_gb:.1f} GB used ({usage_percent:.1f}% utilization) - {wasted_storage_gb:.1f} GB wasted"

                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fsx_file_system",
                                            resource_id=fs_id,
                                            resource_name=name,
                                            region=region,
                                            estimated_monthly_cost=wasted_cost,
                                            resource_metadata={
                                                "file_system_type": fs_type,
                                                "orphan_type": orphan_type,
                                                "storage_capacity_gb": storage_capacity,
                                                "storage_used_gb": round(avg_storage_used_gb, 2),
                                                "storage_utilization_percent": round(usage_percent, 2),
                                                "wasted_storage_gb": round(wasted_storage_gb, 2),
                                                "deployment_type": deployment_type,
                                                "is_multi_az": is_multi_az,
                                                "age_days": age_days,
                                                "confidence": confidence,
                                                "orphan_reason": reason,
                                                "lookback_days": storage_lookback_days,
                                            },
                                        )
                                    )
                                    continue

                        # ========================================
                        # PRIORITY 3: Over-Provisioned Throughput
                        # ========================================
                        if detect_over_provisioned_throughput and throughput_capacity and fs_type in ["WINDOWS", "ONTAP"]:
                            now = datetime.now(timezone.utc)
                            start_time = now - timedelta(days=throughput_lookback_days)

                            # Query ThroughputUtilization metric (percentage)
                            throughput_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="ThroughputUtilization",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=3600,  # 1 hour
                                Statistics=["Average"],
                            )

                            datapoints = throughput_response.get("Datapoints", [])
                            if datapoints:
                                avg_throughput_utilization = sum(dp["Average"] for dp in datapoints) / len(datapoints)

                                if avg_throughput_utilization < throughput_utilization_threshold:
                                    orphan_type = "over_provisioned_throughput"
                                    confidence = "medium" if age_days >= confidence_threshold_days else "low"

                                    # Calculate wasted throughput cost
                                    wasted_cost = throughput_capacity * self.PRICING["fsx_throughput_per_mbps"] * (1 - avg_throughput_utilization / 100)

                                    # Multi-AZ doubles cost
                                    if is_multi_az:
                                        wasted_cost *= 2

                                    reason = f"Throughput over-provisioned: {throughput_capacity} MB/s provisioned but only {avg_throughput_utilization:.1f}% utilized (avg over {throughput_lookback_days} days)"

                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fsx_file_system",
                                            resource_id=fs_id,
                                            resource_name=name,
                                            region=region,
                                            estimated_monthly_cost=wasted_cost,
                                            resource_metadata={
                                                "file_system_type": fs_type,
                                                "orphan_type": orphan_type,
                                                "throughput_capacity_mbps": throughput_capacity,
                                                "throughput_utilization_percent": round(avg_throughput_utilization, 2),
                                                "deployment_type": deployment_type,
                                                "is_multi_az": is_multi_az,
                                                "age_days": age_days,
                                                "confidence": confidence,
                                                "orphan_reason": reason,
                                                "lookback_days": throughput_lookback_days,
                                            },
                                        )
                                    )
                                    continue

                        # ========================================
                        # PRIORITY 4: Excessive Backup Retention
                        # ========================================
                        if detect_excessive_backups or detect_orphaned_backups:
                            try:
                                backups_response = await fsx.describe_backups(
                                    Filters=[{"Name": "file-system-id", "Values": [fs_id]}]
                                )

                                backups = backups_response.get("Backups", [])
                                old_backups = []
                                orphaned_backups = []
                                total_backup_size_gb = 0

                                for backup in backups:
                                    backup_age_days = (datetime.now(timezone.utc) - backup["CreationTime"]).days
                                    backup_size_gb = backup.get("Volume", {}).get("VolumeSize", 0) if "Volume" in backup else 0
                                    total_backup_size_gb += backup_size_gb

                                    # Detect excessive retention
                                    if detect_excessive_backups and backup_age_days > max_backup_retention_days:
                                        old_backups.append({"id": backup["BackupId"], "age_days": backup_age_days, "size_gb": backup_size_gb})

                                    # Detect orphaned backups (source file system deleted)
                                    if detect_orphaned_backups and backup.get("Lifecycle") == "DELETED":
                                        orphaned_backups.append({"id": backup["BackupId"], "age_days": backup_age_days, "size_gb": backup_size_gb})

                                if old_backups or orphaned_backups:
                                    orphan_type = "excessive_backups" if old_backups else "orphaned_backups"
                                    confidence = "medium" if old_backups else "high"

                                    # Calculate backup costs
                                    wasted_backup_cost = total_backup_size_gb * self.PRICING["fsx_backup_per_gb"]

                                    if old_backups:
                                        reason = f"{len(old_backups)} backups older than {max_backup_retention_days} days (total {total_backup_size_gb:.1f} GB) - excessive retention"
                                    else:
                                        reason = f"{len(orphaned_backups)} orphaned backups (source file system deleted) - {total_backup_size_gb:.1f} GB wasted"

                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fsx_file_system",
                                            resource_id=fs_id,
                                            resource_name=name,
                                            region=region,
                                            estimated_monthly_cost=wasted_backup_cost,
                                            resource_metadata={
                                                "file_system_type": fs_type,
                                                "orphan_type": orphan_type,
                                                "backup_count": len(backups),
                                                "old_backup_count": len(old_backups),
                                                "orphaned_backup_count": len(orphaned_backups),
                                                "total_backup_size_gb": round(total_backup_size_gb, 2),
                                                "max_backup_age_days": max(b["age_days"] for b in old_backups) if old_backups else 0,
                                                "age_days": age_days,
                                                "confidence": confidence,
                                                "orphan_reason": reason,
                                            },
                                        )
                                    )
                                    continue
                            except ClientError:
                                pass  # Backups API not available for this file system

                        # ========================================
                        # PRIORITY 5: Unused File Shares (Windows)
                        # ========================================
                        if detect_unused_file_shares and fs_type == "WINDOWS":
                            now = datetime.now(timezone.utc)
                            start_time = now - timedelta(days=min_zero_connections_days)

                            # Query ClientConnections metric
                            connections_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="ClientConnections",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=3600,  # 1 hour
                                Statistics=["Average"],
                            )

                            datapoints = connections_response.get("Datapoints", [])
                            if datapoints:
                                max_connections = max(dp["Average"] for dp in datapoints)

                                if max_connections == 0:
                                    orphan_type = "unused_file_shares"
                                    confidence = "high" if age_days >= confidence_threshold_days else "medium"

                                    # Calculate full cost (no SMB connections = completely unused)
                                    monthly_cost = storage_capacity * self.PRICING["fsx_windows_per_gb"]
                                    if throughput_capacity:
                                        monthly_cost += throughput_capacity * self.PRICING["fsx_throughput_per_mbps"]
                                    if is_multi_az:
                                        monthly_cost *= 2

                                    reason = f"No SMB client connections detected over {min_zero_connections_days} days - file shares unused"

                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fsx_file_system",
                                            resource_id=fs_id,
                                            resource_name=name,
                                            region=region,
                                            estimated_monthly_cost=monthly_cost,
                                            resource_metadata={
                                                "file_system_type": fs_type,
                                                "orphan_type": orphan_type,
                                                "storage_capacity_gb": storage_capacity,
                                                "max_client_connections": 0,
                                                "deployment_type": deployment_type,
                                                "is_multi_az": is_multi_az,
                                                "age_days": age_days,
                                                "confidence": confidence,
                                                "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                                "orphan_reason": reason,
                                                "lookback_days": min_zero_connections_days,
                                            },
                                        )
                                    )
                                    continue

                        # ========================================
                        # PRIORITY 6: Low IOPS Utilization
                        # ========================================
                        if detect_low_iops_utilization and fs_type in ["WINDOWS", "ONTAP"]:
                            now = datetime.now(timezone.utc)
                            start_time = now - timedelta(days=iops_lookback_days)

                            # Query DiskIopsUtilization metric (percentage)
                            iops_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="DiskIopsUtilization",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=3600,
                                Statistics=["Average"],
                            )

                            datapoints = iops_response.get("Datapoints", [])
                            if datapoints:
                                avg_iops_utilization = sum(dp["Average"] for dp in datapoints) / len(datapoints)

                                if avg_iops_utilization < iops_utilization_threshold:
                                    orphan_type = "low_iops_utilization"
                                    confidence = "low"  # Low confidence (IOPS may spike)

                                    # Estimate potential savings (not precise without provisioned IOPS data)
                                    monthly_cost = storage_capacity * self.PRICING.get(f"fsx_{fs_type.lower()}_per_gb", 0.14) * 0.3  # 30% waste estimate
                                    if is_multi_az:
                                        monthly_cost *= 2

                                    reason = f"Low IOPS utilization: {avg_iops_utilization:.1f}% average over {iops_lookback_days} days - over-provisioned IOPS"

                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fsx_file_system",
                                            resource_id=fs_id,
                                            resource_name=name,
                                            region=region,
                                            estimated_monthly_cost=monthly_cost,
                                            resource_metadata={
                                                "file_system_type": fs_type,
                                                "orphan_type": orphan_type,
                                                "iops_utilization_percent": round(avg_iops_utilization, 2),
                                                "deployment_type": deployment_type,
                                                "is_multi_az": is_multi_az,
                                                "age_days": age_days,
                                                "confidence": confidence,
                                                "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                                "orphan_reason": reason,
                                                "lookback_days": iops_lookback_days,
                                            },
                                        )
                                    )
                                    continue

                        # ========================================
                        # PRIORITY 7: Multi-AZ Overkill
                        # ========================================
                        if detect_multi_az_overkill and is_multi_az and environment_tag in multi_az_tag_values:
                            orphan_type = "multi_az_overkill"
                            confidence = "medium"

                            # Calculate cost difference (Multi-AZ = 2× Single-AZ)
                            pricing_key = f"fsx_{fs_type.lower()}_per_gb"
                            single_az_cost = storage_capacity * self.PRICING.get(pricing_key, 0.14)
                            if throughput_capacity and fs_type in ["WINDOWS", "ONTAP"]:
                                single_az_cost += throughput_capacity * self.PRICING["fsx_throughput_per_mbps"]

                            wasted_cost = single_az_cost  # Wasted = difference between Multi-AZ and Single-AZ

                            reason = f"Multi-AZ deployment in {environment_tag} environment (tag: {multi_az_tag_key}={environment_tag}) - Single-AZ sufficient for non-production"

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="fsx_file_system",
                                    resource_id=fs_id,
                                    resource_name=name,
                                    region=region,
                                    estimated_monthly_cost=wasted_cost,
                                    resource_metadata={
                                        "file_system_type": fs_type,
                                        "orphan_type": orphan_type,
                                        "storage_capacity_gb": storage_capacity,
                                        "deployment_type": deployment_type,
                                        "is_multi_az": is_multi_az,
                                        "environment_tag": environment_tag,
                                        "age_days": age_days,
                                        "confidence": confidence,
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                        "orphan_reason": reason,
                                    },
                                )
                            )
                            continue

                        # ========================================
                        # PRIORITY 8: Wrong Storage Type (SSD for Archive)
                        # ========================================
                        if detect_ssd_for_archive and fs_type == "WINDOWS" and storage_type == "SSD":
                            now = datetime.now(timezone.utc)
                            start_time = now - timedelta(days=7)

                            # Calculate average throughput (read + write)
                            read_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="DataReadBytes",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=86400,
                                Statistics=["Average"],
                            )

                            write_response = await cw.get_metric_statistics(
                                Namespace="AWS/FSx",
                                MetricName="DataWriteBytes",
                                Dimensions=[{"Name": "FileSystemId", "Value": fs_id}],
                                StartTime=start_time,
                                EndTime=now,
                                Period=86400,
                                Statistics=["Average"],
                            )

                            read_datapoints = read_response.get("Datapoints", [])
                            write_datapoints = write_response.get("Datapoints", [])

                            if read_datapoints or write_datapoints:
                                avg_read_mbps = (sum(dp["Average"] for dp in read_datapoints) / len(read_datapoints) / 1_000_000) if read_datapoints else 0
                                avg_write_mbps = (sum(dp["Average"] for dp in write_datapoints) / len(write_datapoints) / 1_000_000) if write_datapoints else 0
                                avg_total_mbps = avg_read_mbps + avg_write_mbps

                                if avg_total_mbps < archive_throughput_threshold:
                                    orphan_type = "wrong_storage_type"
                                    confidence = "low"  # Low confidence (workload may change)

                                    # Calculate savings: SSD → HDD (90% cheaper)
                                    ssd_cost = storage_capacity * self.PRICING["fsx_windows_per_gb"]
                                    hdd_cost = storage_capacity * self.PRICING["fsx_windows_hdd_per_gb"]
                                    wasted_cost = ssd_cost - hdd_cost

                                    if is_multi_az:
                                        wasted_cost *= 2

                                    reason = f"SSD storage type for archive workload: avg {avg_total_mbps:.2f} MB/s throughput (< {archive_throughput_threshold} MB/s) - HDD recommended (90% cheaper)"

                                    orphans.append(
                                        OrphanResourceData(
                                            resource_type="fsx_file_system",
                                            resource_id=fs_id,
                                            resource_name=name,
                                            region=region,
                                            estimated_monthly_cost=wasted_cost,
                                            resource_metadata={
                                                "file_system_type": fs_type,
                                                "orphan_type": orphan_type,
                                                "storage_type": storage_type,
                                                "storage_capacity_gb": storage_capacity,
                                                "avg_throughput_mbps": round(avg_total_mbps, 2),
                                                "recommended_storage_type": "HDD",
                                                "potential_savings_percent": 90,
                                                "deployment_type": deployment_type,
                                                "is_multi_az": is_multi_az,
                                                "age_days": age_days,
                                                "confidence": confidence,
                                                "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                                "orphan_reason": reason,
                                            },
                                        )
                                    )
                                    continue

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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
        Scan for idle/orphaned EKS clusters with comprehensive detection scenarios.

        Scenarios:
        1. No worker nodes - Cluster with 0 nodes (paying control plane only)
        2. All nodes unhealthy - All nodes in degraded/failed state
        3. Low CPU utilization - All nodes with <5% CPU average
        4. Fargate no profiles - Fargate-only cluster with no profiles configured
        5. Outdated K8s version - Very old Kubernetes version (abandoned)

        Args:
            region: AWS region to scan
            detection_rules: Optional user-defined detection rules

        Returns:
            List of orphaned EKS cluster resources
        """
        orphans: list[OrphanResourceData] = []

        # Use provided rules or defaults
        if detection_rules is None:
            from app.models.detection_rule import DEFAULT_DETECTION_RULES

            detection_rules = DEFAULT_DETECTION_RULES.get("eks_cluster", {})

        # Check if detection is enabled
        if not detection_rules.get("enabled", True):
            return orphans

        # Load configuration
        min_age_days = detection_rules.get("min_age_days", 3)
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 7)
        critical_age_days = detection_rules.get("critical_age_days", 30)
        detect_no_nodes = detection_rules.get("detect_no_nodes", True)
        detect_unhealthy_nodes = detection_rules.get("detect_unhealthy_nodes", True)
        min_unhealthy_days = detection_rules.get("min_unhealthy_days", 7)
        detect_low_utilization = detection_rules.get("detect_low_utilization", True)
        cpu_threshold_percent = detection_rules.get("cpu_threshold_percent", 5.0)
        min_idle_days = detection_rules.get("min_idle_days", 7)
        idle_lookback_days = detection_rules.get("idle_lookback_days", 7)
        detect_fargate_no_profiles = detection_rules.get(
            "detect_fargate_no_profiles", True
        )
        detect_outdated_version = detection_rules.get("detect_outdated_version", True)
        min_supported_minor_versions = detection_rules.get(
            "min_supported_minor_versions", 3
        )

        # AWS supports last 3-4 minor versions (adjust as AWS updates support)
        # As of 2025, latest is 1.28, so minimum supported would be 1.25
        LATEST_K8S_VERSION = "1.28"

        try:
            async with self.session.client("eks", region_name=region) as eks:
                async with self.session.client("ec2", region_name=region) as ec2:
                    async with self.session.client(
                        "cloudwatch", region_name=region
                    ) as cloudwatch:
                        response = await eks.list_clusters()

                        for cluster_name in response.get("clusters", []):
                            cluster_info = await eks.describe_cluster(name=cluster_name)
                            cluster = cluster_info["cluster"]

                            # Basic metadata
                            created_at = cluster["createdAt"]
                            age_days = (datetime.now(timezone.utc) - created_at).days
                            k8s_version = cluster.get("version", "Unknown")
                            cluster_status = cluster.get("status", "Unknown")

                            # Skip if too young
                            if age_days < min_age_days:
                                continue

                            # Get node groups
                            nodegroups_response = await eks.list_nodegroups(
                                clusterName=cluster_name
                            )
                            nodegroups = nodegroups_response.get("nodegroups", [])

                            # Get Fargate profiles (graceful failure if permission denied)
                            fargate_profiles = []
                            try:
                                fargate_response = await eks.list_fargate_profiles(
                                    clusterName=cluster_name
                                )
                                fargate_profiles = fargate_response.get(
                                    "fargateProfileNames", []
                                )
                            except ClientError as fargate_error:
                                # Silently continue if Fargate permissions are missing
                                # This allows detection to work even without Fargate access
                                if fargate_error.response.get("Error", {}).get(
                                    "Code"
                                ) != "AccessDeniedException":
                                    # Log only non-permission errors
                                    print(
                                        f"Error listing Fargate profiles for {cluster_name}: {fargate_error}"
                                    )

                            # Collect node information
                            total_nodes = 0
                            unhealthy_nodes = 0
                            node_instance_ids = []
                            node_details = []

                            for ng_name in nodegroups:
                                ng_info = await eks.describe_nodegroup(
                                    clusterName=cluster_name, nodegroupName=ng_name
                                )
                                ng = ng_info["nodegroup"]

                                desired_size = (
                                    ng.get("scalingConfig", {}).get("desiredSize", 0)
                                )
                                total_nodes += desired_size

                                # Check health
                                ng_status = ng.get("status", "UNKNOWN")
                                ng_health = ng.get("health", {})
                                health_issues = ng_health.get("issues", [])

                                if (
                                    ng_status
                                    not in ["ACTIVE", "CREATING", "UPDATING"]
                                    or health_issues
                                ):
                                    unhealthy_nodes += desired_size

                                node_details.append(
                                    {
                                        "name": ng_name,
                                        "status": ng_status,
                                        "desired_size": desired_size,
                                        "instance_type": ng.get("instanceTypes", [
                                            "unknown"
                                        ])[0],
                                        "health_issues": len(health_issues),
                                    }
                                )

                            # Try to find EC2 instances by EKS cluster tag for CPU metrics
                            try:
                                instances_response = await ec2.describe_instances(
                                    Filters=[
                                        {
                                            "Name": "tag:eks:cluster-name",
                                            "Values": [cluster_name],
                                        },
                                        {
                                            "Name": "instance-state-name",
                                            "Values": ["running"],
                                        },
                                    ]
                                )
                                for reservation in instances_response.get(
                                    "Reservations", []
                                ):
                                    for instance in reservation.get("Instances", []):
                                        node_instance_ids.append(instance["InstanceId"])
                            except Exception:
                                pass

                            # Detection logic
                            is_orphaned = False
                            orphan_type = None
                            orphan_reasons = []
                            confidence_level = "medium"

                            # Scenario #1: No worker nodes
                            if (
                                detect_no_nodes
                                and total_nodes == 0
                                and len(fargate_profiles) == 0
                            ):
                                is_orphaned = True
                                orphan_type = "no_worker_nodes"
                                orphan_reasons.append(
                                    f"No worker nodes and no Fargate profiles (age: {age_days} days)"
                                )
                                orphan_reasons.append(
                                    "Paying $73/month for unused control plane"
                                )

                                if age_days >= critical_age_days:
                                    confidence_level = "critical"
                                    orphan_reasons.append(
                                        f"CRITICAL: Unused for {age_days}+ days"
                                    )
                                elif age_days >= confidence_threshold_days:
                                    confidence_level = "high"
                                else:
                                    confidence_level = "medium"

                            # Scenario #4: Fargate no profiles
                            elif (
                                detect_fargate_no_profiles
                                and total_nodes == 0
                                and len(nodegroups) == 0
                                and len(fargate_profiles) == 0
                            ):
                                is_orphaned = True
                                orphan_type = "fargate_no_profiles"
                                orphan_reasons.append(
                                    "Fargate-configured but no profiles created"
                                )
                                orphan_reasons.append(
                                    "Cannot deploy pods without Fargate profiles or node groups"
                                )
                                confidence_level = (
                                    "high"
                                    if age_days >= confidence_threshold_days
                                    else "medium"
                                )

                            # Scenario #2: All nodes unhealthy
                            elif (
                                detect_unhealthy_nodes
                                and total_nodes > 0
                                and unhealthy_nodes == total_nodes
                                and age_days >= min_unhealthy_days
                            ):
                                is_orphaned = True
                                orphan_type = "all_nodes_unhealthy"
                                orphan_reasons.append(
                                    f"All {total_nodes} nodes are unhealthy/degraded"
                                )
                                orphan_reasons.append("Cluster unable to run workloads")
                                confidence_level = (
                                    "high"
                                    if age_days >= confidence_threshold_days
                                    else "medium"
                                )

                            # Scenario #3: Low CPU utilization on all nodes
                            elif (
                                detect_low_utilization
                                and total_nodes > 0
                                and len(node_instance_ids) > 0
                                and age_days >= min_idle_days
                            ):
                                # Check CloudWatch CPU for nodes
                                low_cpu_nodes = 0
                                total_checked_nodes = 0
                                avg_cpu_overall = 0.0

                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=idle_lookback_days)

                                # Limit to 10 instances to avoid API throttling
                                for instance_id in node_instance_ids[:10]:
                                    try:
                                        cpu_response = (
                                            await cloudwatch.get_metric_statistics(
                                                Namespace="AWS/EC2",
                                                MetricName="CPUUtilization",
                                                Dimensions=[
                                                    {
                                                        "Name": "InstanceId",
                                                        "Value": instance_id,
                                                    }
                                                ],
                                                StartTime=start_time,
                                                EndTime=now,
                                                Period=86400,  # 1 day
                                                Statistics=["Average"],
                                            )
                                        )
                                        datapoints = cpu_response.get("Datapoints", [])
                                        if datapoints:
                                            avg_cpu = sum(
                                                dp["Average"] for dp in datapoints
                                            ) / len(datapoints)
                                            avg_cpu_overall += avg_cpu
                                            total_checked_nodes += 1
                                            if avg_cpu < cpu_threshold_percent:
                                                low_cpu_nodes += 1
                                    except Exception:
                                        pass

                                if total_checked_nodes > 0:
                                    avg_cpu_overall /= total_checked_nodes

                                    # If all checked nodes have low CPU
                                    if (
                                        low_cpu_nodes == total_checked_nodes
                                        and avg_cpu_overall < cpu_threshold_percent
                                    ):
                                        is_orphaned = True
                                        orphan_type = "low_utilization"
                                        orphan_reasons.append(
                                            f"All nodes have <{cpu_threshold_percent}% CPU utilization (avg: {avg_cpu_overall:.2f}%)"
                                        )
                                        orphan_reasons.append(
                                            "Over-provisioned or abandoned cluster"
                                        )
                                        confidence_level = (
                                            "high"
                                            if age_days >= critical_age_days
                                            else "medium"
                                        )

                            # Scenario #5: Outdated Kubernetes version
                            if detect_outdated_version and k8s_version != "Unknown":
                                try:
                                    latest_major, latest_minor = map(
                                        int, LATEST_K8S_VERSION.split(".")[:2]
                                    )
                                    current_major, current_minor = map(
                                        int, k8s_version.split(".")[:2]
                                    )

                                    version_diff = (
                                        latest_major - current_major
                                    ) * 100 + (latest_minor - current_minor)

                                    if version_diff >= min_supported_minor_versions:
                                        if not is_orphaned:
                                            is_orphaned = True
                                            orphan_type = "outdated_version"
                                            confidence_level = "medium"

                                        orphan_reasons.append(
                                            f"Kubernetes version {k8s_version} is {version_diff} versions behind latest ({LATEST_K8S_VERSION})"
                                        )
                                        orphan_reasons.append(
                                            "Likely abandoned cluster (security risk)"
                                        )
                                except Exception:
                                    pass

                            if is_orphaned:
                                # Calculate costs
                                control_plane_cost = self.PRICING["eks_control_plane"]
                                node_cost = 0.0

                                for node in node_details:
                                    instance_type = node["instance_type"]
                                    desired_size = node["desired_size"]

                                    # Map instance type to pricing
                                    instance_type_lower = instance_type.lower()
                                    price_key = (
                                        f"eks_{instance_type_lower.replace('.', '_')}"
                                    )

                                    if price_key in self.PRICING:
                                        node_cost += (
                                            self.PRICING[price_key] * desired_size
                                        )
                                    elif "t3.small" in instance_type_lower:
                                        node_cost += (
                                            self.PRICING["eks_t3_small"] * desired_size
                                        )
                                    elif "t3.medium" in instance_type_lower:
                                        node_cost += (
                                            self.PRICING["eks_t3_medium"] * desired_size
                                        )
                                    elif "t3.large" in instance_type_lower:
                                        node_cost += (
                                            self.PRICING["eks_t3_large"] * desired_size
                                        )
                                    elif "m5.large" in instance_type_lower:
                                        node_cost += (
                                            self.PRICING["eks_m5_large"] * desired_size
                                        )
                                    else:
                                        # Default fallback to t3.medium
                                        node_cost += (
                                            self.PRICING["eks_t3_medium"] * desired_size
                                        )

                                total_cost = control_plane_cost + node_cost

                                orphans.append(
                                    OrphanResourceData(
                                        resource_type="eks_cluster",
                                        resource_id=cluster_name,
                                        resource_name=cluster_name,
                                        region=region,
                                        estimated_monthly_cost=round(total_cost, 2),
                                        resource_metadata={
                                            "version": k8s_version,
                                            "status": cluster_status,
                                            "nodegroup_count": len(nodegroups),
                                            "total_nodes": total_nodes,
                                            "unhealthy_nodes": unhealthy_nodes,
                                            "fargate_profile_count": len(
                                                fargate_profiles
                                            ),
                                            "node_details": node_details,
                                            "created_at": created_at.isoformat(),
                                            "age_days": age_days,
                                            "orphan_type": orphan_type,
                                            "orphan_reason": " | ".join(orphan_reasons),
                                            "orphan_reasons": orphan_reasons,
                                            "confidence_level": confidence_level,
                                            "control_plane_cost_monthly": round(
                                                control_plane_cost, 2
                                            ),
                                            "node_cost_monthly": round(node_cost, 2),
                                            "wasted_amount": round(total_cost, 2),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
        Scan for idle/orphaned ElastiCache clusters (Redis + Memcached).

        Detects 4 scenarios (by priority):
        1. Zero cache hits (no activity)
        2. Low hit rate (< 50% hits, cache inefficient)
        3. No connections (nobody connects)
        4. Over-provisioned memory (< 20% memory used)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned ElastiCache clusters
        """
        orphans = []

        # Extract detection rules (with defaults)
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 7) if detection_rules else 7

        # PRIORITY 1: Zero cache hits
        detect_zero_cache_hits = detection_rules.get("detect_zero_cache_hits", True) if detection_rules else True
        zero_hits_lookback_days = detection_rules.get("zero_hits_lookback_days", 7) if detection_rules else 7

        # PRIORITY 2: Low hit rate
        detect_low_hit_rate = detection_rules.get("detect_low_hit_rate", True) if detection_rules else True
        hit_rate_threshold = detection_rules.get("hit_rate_threshold", 50.0) if detection_rules else 50.0
        critical_hit_rate = detection_rules.get("critical_hit_rate", 10.0) if detection_rules else 10.0
        hit_rate_lookback_days = detection_rules.get("hit_rate_lookback_days", 7) if detection_rules else 7

        # PRIORITY 3: No connections
        detect_no_connections = detection_rules.get("detect_no_connections", True) if detection_rules else True
        no_connections_lookback_days = detection_rules.get("no_connections_lookback_days", 7) if detection_rules else 7

        # PRIORITY 4: Over-provisioned memory
        detect_over_provisioned_memory = detection_rules.get("detect_over_provisioned_memory", True) if detection_rules else True
        memory_usage_threshold = detection_rules.get("memory_usage_threshold", 20.0) if detection_rules else 20.0
        memory_lookback_days = detection_rules.get("memory_lookback_days", 7) if detection_rules else 7

        print(f"🗄️ [DEBUG] scan_idle_elasticache_clusters called for region: {region}")

        try:
            async with self.session.client("elasticache", region_name=region) as elasticache:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    # List all ElastiCache clusters (Redis + Memcached)
                    response = await elasticache.describe_cache_clusters()
                    clusters = response.get("CacheClusters", [])

                    print(f"🗄️ [DEBUG] Found {len(clusters)} ElastiCache clusters in {region}")

                    for cluster in clusters:
                        cluster_id = cluster["CacheClusterId"]
                        cluster_status = cluster.get("CacheClusterStatus", "unknown")

                        # Skip non-available clusters
                        if cluster_status != "available":
                            print(f"🗄️ [DEBUG] Skipping {cluster_id}: status={cluster_status} (not available)")
                            continue

                        created_at = cluster.get("CacheClusterCreateTime")
                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        # Skip very young clusters
                        if age_days < min_age_days:
                            print(f"🗄️ [DEBUG] Skipping {cluster_id}: too young ({age_days} < {min_age_days} days)")
                            continue

                        # Extract cluster metadata
                        node_type = cluster.get("CacheNodeType", "cache.m5.large")
                        num_nodes = cluster.get("NumCacheNodes", 1)
                        engine = cluster.get("Engine", "Unknown")
                        engine_version = cluster.get("EngineVersion", "Unknown")

                        print(f"🗄️ [DEBUG] Analyzing cluster: {cluster_id} (age={age_days} days, engine={engine}, nodes={num_nodes}x{node_type})")

                        # Variables for detection
                        orphan_type = None
                        orphan_reason = None
                        confidence = "medium"
                        monthly_cost = 0.0

                        # Additional metadata
                        cache_hits = 0
                        cache_misses = 0
                        hit_rate = None
                        connections = None
                        memory_usage_percent = None

                        # PRIORITY 1: Check zero cache hits
                        if orphan_type is None and detect_zero_cache_hits:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=zero_hits_lookback_days)

                                hits_response = await cw.get_metric_statistics(
                                    Namespace="AWS/ElastiCache",
                                    MetricName="CacheHits",
                                    Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,  # 1 hour
                                    Statistics=["Sum"],
                                )

                                datapoints = hits_response.get("Datapoints", [])
                                cache_hits = sum(dp["Sum"] for dp in datapoints)

                                if cache_hits == 0:
                                    orphan_type = "zero_cache_hits"
                                    orphan_reason = f"No cache hits for {zero_hits_lookback_days} days - cluster not used"
                                    confidence = "critical" if age_days >= confidence_threshold_days else "high"
                                    print(f"🗄️ [DEBUG] ✅ {cluster_id} detected as ORPHAN: type={orphan_type}, confidence={confidence}")

                            except ClientError as e:
                                print(f"Warning: Could not check cache hits for {cluster_id}: {e}")

                        # PRIORITY 2: Check low hit rate
                        if orphan_type is None and detect_low_hit_rate:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=hit_rate_lookback_days)

                                # Get CacheHits if not already retrieved
                                if cache_hits == 0:  # Not retrieved in PRIORITY 1
                                    hits_response = await cw.get_metric_statistics(
                                        Namespace="AWS/ElastiCache",
                                        MetricName="CacheHits",
                                        Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
                                        StartTime=start_time,
                                        EndTime=now,
                                        Period=3600,
                                        Statistics=["Sum"],
                                    )
                                    cache_hits = sum(dp["Sum"] for dp in hits_response.get("Datapoints", []))

                                # Get CacheMisses
                                misses_response = await cw.get_metric_statistics(
                                    Namespace="AWS/ElastiCache",
                                    MetricName="CacheMisses",
                                    Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,
                                    Statistics=["Sum"],
                                )
                                cache_misses = sum(dp["Sum"] for dp in misses_response.get("Datapoints", []))

                                # Calculate hit rate
                                total_requests = cache_hits + cache_misses
                                if total_requests > 0:
                                    hit_rate = (cache_hits / total_requests) * 100

                                    if hit_rate < hit_rate_threshold:
                                        orphan_type = "low_hit_rate"
                                        if hit_rate < critical_hit_rate:
                                            orphan_reason = f"Very low hit rate ({hit_rate:.1f}%) - cache almost useless"
                                            confidence = "critical"
                                        else:
                                            orphan_reason = f"Low hit rate ({hit_rate:.1f}%) - cache inefficient (threshold: {hit_rate_threshold}%)"
                                            confidence = "high" if age_days >= confidence_threshold_days else "medium"

                                        print(f"🗄️ [DEBUG] ✅ {cluster_id} detected as ORPHAN: type={orphan_type}, hit_rate={hit_rate:.1f}%, confidence={confidence}")

                            except ClientError as e:
                                print(f"Warning: Could not check hit rate for {cluster_id}: {e}")

                        # PRIORITY 3: Check no connections
                        if orphan_type is None and detect_no_connections:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=no_connections_lookback_days)

                                conn_response = await cw.get_metric_statistics(
                                    Namespace="AWS/ElastiCache",
                                    MetricName="CurrConnections",
                                    Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,
                                    Statistics=["Average"],
                                )

                                datapoints = conn_response.get("Datapoints", [])
                                if len(datapoints) > 0:
                                    avg_connections = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                                    connections = int(avg_connections)

                                    if connections == 0:
                                        orphan_type = "no_connections"
                                        orphan_reason = f"No active connections for {no_connections_lookback_days} days - nobody uses this cluster"
                                        confidence = "critical" if age_days >= confidence_threshold_days else "high"
                                        print(f"🗄️ [DEBUG] ✅ {cluster_id} detected as ORPHAN: type={orphan_type}, confidence={confidence}")

                            except ClientError as e:
                                print(f"Warning: Could not check connections for {cluster_id}: {e}")

                        # PRIORITY 4: Check over-provisioned memory
                        if orphan_type is None and detect_over_provisioned_memory:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=memory_lookback_days)

                                memory_response = await cw.get_metric_statistics(
                                    Namespace="AWS/ElastiCache",
                                    MetricName="DatabaseMemoryUsagePercentage",
                                    Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,
                                    Statistics=["Average"],
                                )

                                datapoints = memory_response.get("Datapoints", [])
                                if len(datapoints) > 0:
                                    avg_memory = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                                    memory_usage_percent = avg_memory

                                    if memory_usage_percent < memory_usage_threshold:
                                        # Also check evictions (should be 0 if over-provisioned)
                                        evictions_response = await cw.get_metric_statistics(
                                            Namespace="AWS/ElastiCache",
                                            MetricName="Evictions",
                                            Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
                                            StartTime=start_time,
                                            EndTime=now,
                                            Period=3600,
                                            Statistics=["Sum"],
                                        )

                                        evictions = sum(dp["Sum"] for dp in evictions_response.get("Datapoints", []))

                                        if evictions == 0:
                                            orphan_type = "over_provisioned_memory"
                                            orphan_reason = f"Memory usage only {memory_usage_percent:.1f}% (threshold: {memory_usage_threshold}%) with 0 evictions - cluster too large"
                                            confidence = "medium"
                                            print(f"🗄️ [DEBUG] ✅ {cluster_id} detected as ORPHAN: type={orphan_type}, memory={memory_usage_percent:.1f}%, confidence={confidence}")

                            except ClientError as e:
                                print(f"Warning: Could not check memory usage for {cluster_id}: {e}")

                        # If detected as orphan, calculate cost and add to list
                        if orphan_type:
                            # Calculate cost based on node type
                            cost_per_node = self._get_elasticache_node_cost(node_type)
                            monthly_cost = cost_per_node * num_nodes

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="elasticache_cluster",
                                    resource_id=cluster_id,
                                    resource_name=cluster_id,
                                    region=region,
                                    estimated_monthly_cost=round(monthly_cost, 2),
                                    resource_metadata={
                                        "cluster_id": cluster_id,
                                        "node_type": node_type,
                                        "num_nodes": num_nodes,
                                        "engine": engine,
                                        "engine_version": engine_version,
                                        "status": cluster_status,
                                        "age_days": age_days,
                                        "created_at": created_at.isoformat() if created_at else None,
                                        "orphan_type": orphan_type,
                                        "orphan_reason": orphan_reason,
                                        "confidence": confidence,
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                        # Metrics
                                        "cache_hits_7d": int(cache_hits) if cache_hits > 0 else 0,
                                        "cache_misses_7d": int(cache_misses) if cache_misses > 0 else 0,
                                        "hit_rate": round(hit_rate, 1) if hit_rate is not None else None,
                                        "avg_connections": connections,
                                        "memory_usage_percent": round(memory_usage_percent, 1) if memory_usage_percent is not None else None,
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning ElastiCache clusters in {region}: {e}")

        print(f"🗄️ [DEBUG] scan_idle_elasticache_clusters completed for {region}: Found {len(orphans)} orphan clusters")
        return orphans

    def _get_elasticache_node_cost(self, node_type: str) -> float:
        """
        Get monthly cost for an ElastiCache node type.

        Args:
            node_type: Node type (e.g., 'cache.t3.micro', 'cache.m5.large')

        Returns:
            Monthly cost in USD
        """
        # Map node type to pricing key
        node_type_lower = node_type.lower().replace("cache.", "elasticache_")

        # Try exact match
        if node_type_lower in self.PRICING:
            return self.PRICING[node_type_lower] * 730

        # Try prefix matching (e.g., cache.m5.large → elasticache_m5_large)
        for key, price in self.PRICING.items():
            if key.startswith("elasticache_") and node_type_lower.endswith(key.replace("elasticache_", "")):
                return price * 730

        # Default fallback based on node family
        if "t3" in node_type or "t4g" in node_type:
            return self.PRICING.get("elasticache_t3_micro", 0.017) * 730  # ~$12/month
        elif "m5" in node_type or "m6g" in node_type:
            return self.PRICING.get("elasticache_m5_large", 0.126) * 730  # ~$90/month
        elif "r5" in node_type or "r6g" in node_type:
            return self.PRICING.get("elasticache_r5_large", 0.188) * 730  # ~$135/month
        else:
            return 90.00  # Default $90/month

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
                                        "confidence_level": self._calculate_confidence_level(30, detection_rules),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
        Scan for idle/orphaned Kinesis streams using CloudWatch metrics.

        Detects 6 scenarios (by priority):
        1. Completely inactive (0 writes + 0 reads)
        2. Written but never read (writes > 0, reads = 0)
        3. Under-utilized (< 1% capacity used)
        4. Excessive retention (long retention + real-time reads)
        5. Unused Enhanced Fan-Out (registered consumers not used)
        6. Over-provisioned (too many shards vs actual usage)

        Args:
            region: AWS region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphaned Kinesis streams
        """
        orphans = []

        # Extract detection rules (with defaults)
        min_age_days = detection_rules.get("min_age_days", 3) if detection_rules else 3
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 7) if detection_rules else 7

        # Scenario 1: Inactive
        detect_inactive = detection_rules.get("detect_inactive", True) if detection_rules else True
        inactive_lookback_days = detection_rules.get("inactive_lookback_days", 7) if detection_rules else 7

        # Scenario 2: Written but not read
        detect_written_not_read = detection_rules.get("detect_written_not_read", True) if detection_rules else True
        written_not_read_lookback_days = detection_rules.get("written_not_read_lookback_days", 7) if detection_rules else 7

        # Scenario 3: Under-utilized
        detect_underutilized = detection_rules.get("detect_underutilized", True) if detection_rules else True
        utilization_threshold_percent = detection_rules.get("utilization_threshold_percent", 1.0) if detection_rules else 1.0
        underutilized_lookback_days = detection_rules.get("underutilized_lookback_days", 7) if detection_rules else 7

        # Scenario 4: Excessive retention
        detect_excessive_retention = detection_rules.get("detect_excessive_retention", True) if detection_rules else True
        max_iterator_age_ms = detection_rules.get("max_iterator_age_ms", 60000) if detection_rules else 60000  # 1 minute

        # Scenario 5: Unused Enhanced Fan-Out
        detect_unused_enhanced_fanout = detection_rules.get("detect_unused_enhanced_fanout", True) if detection_rules else True

        # Scenario 6: Over-provisioned
        detect_overprovisioned = detection_rules.get("detect_overprovisioned", True) if detection_rules else True
        overprovisioning_ratio = detection_rules.get("overprovisioning_ratio", 10.0) if detection_rules else 10.0

        print(f"🌊 [DEBUG] scan_idle_kinesis_streams called for region: {region}")

        try:
            async with self.session.client("kinesis", region_name=region) as kinesis:
                async with self.session.client("cloudwatch", region_name=region) as cw:
                    response = await kinesis.list_streams()
                    stream_names = response.get("StreamNames", [])

                    print(f"🌊 [DEBUG] Found {len(stream_names)} Kinesis streams in {region}")

                    for stream_name in stream_names:
                        # Get stream details
                        stream_info = await kinesis.describe_stream(StreamName=stream_name)
                        stream = stream_info["StreamDescription"]

                        created_at = stream.get("StreamCreationTimestamp")
                        if not created_at:
                            continue

                        age_days = (datetime.now(timezone.utc) - created_at).days

                        # Skip very young streams
                        if age_days < min_age_days:
                            print(f"🌊 [DEBUG] Skipping {stream_name}: too young ({age_days} < {min_age_days} days)")
                            continue

                        # Extract stream metadata
                        shard_count = len(stream.get("Shards", []))
                        stream_status = stream.get("StreamStatus", "UNKNOWN")
                        retention_hours = stream.get("RetentionPeriodHours", 24)
                        stream_arn = stream.get("StreamARN", "")

                        print(f"🌊 [DEBUG] Analyzing stream: {stream_name} (age={age_days} days, shards={shard_count}, retention={retention_hours}h)")

                        # Variables for detection
                        orphan_type = None
                        orphan_reason = None
                        confidence = "medium"
                        monthly_cost = 0.0

                        # Metrics storage
                        incoming_records = 0
                        incoming_bytes = 0
                        outgoing_records = 0
                        iterator_age_avg_ms = 0
                        enhanced_fanout_consumers = []

                        # PRIORITY 1: Check if completely inactive (0 writes, 0 reads)
                        if orphan_type is None and detect_inactive:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=inactive_lookback_days)

                                # Get IncomingRecords
                                incoming_response = await cw.get_metric_statistics(
                                    Namespace="AWS/Kinesis",
                                    MetricName="IncomingRecords",
                                    Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,  # 1 hour
                                    Statistics=["Sum"],
                                )
                                incoming_records = sum(dp["Sum"] for dp in incoming_response.get("Datapoints", []))

                                # Get GetRecords.Records (outgoing/read records)
                                outgoing_response = await cw.get_metric_statistics(
                                    Namespace="AWS/Kinesis",
                                    MetricName="GetRecords.Records",
                                    Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,
                                    Statistics=["Sum"],
                                )
                                outgoing_records = sum(dp["Sum"] for dp in outgoing_response.get("Datapoints", []))

                                if incoming_records == 0 and outgoing_records == 0:
                                    orphan_type = "inactive"
                                    orphan_reason = f"No incoming or outgoing records for {inactive_lookback_days} days - completely unused"
                                    confidence = "critical" if age_days >= confidence_threshold_days else "high"
                                    monthly_cost = self.PRICING["kinesis_shard"] * shard_count
                                    print(f"🌊 [DEBUG] ✅ {stream_name} detected as ORPHAN: type={orphan_type}, confidence={confidence}")

                            except ClientError as e:
                                print(f"Warning: Could not check inactive metrics for {stream_name}: {e}")

                        # PRIORITY 2: Check if written but never read
                        if orphan_type is None and detect_written_not_read:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=written_not_read_lookback_days)

                                # Get IncomingRecords if not already retrieved
                                if incoming_records == 0:
                                    incoming_response = await cw.get_metric_statistics(
                                        Namespace="AWS/Kinesis",
                                        MetricName="IncomingRecords",
                                        Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                        StartTime=start_time,
                                        EndTime=now,
                                        Period=3600,
                                        Statistics=["Sum"],
                                    )
                                    incoming_records = sum(dp["Sum"] for dp in incoming_response.get("Datapoints", []))

                                # Get GetRecords.Records if not already retrieved
                                if outgoing_records == 0:
                                    outgoing_response = await cw.get_metric_statistics(
                                        Namespace="AWS/Kinesis",
                                        MetricName="GetRecords.Records",
                                        Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                        StartTime=start_time,
                                        EndTime=now,
                                        Period=3600,
                                        Statistics=["Sum"],
                                    )
                                    outgoing_records = sum(dp["Sum"] for dp in outgoing_response.get("Datapoints", []))

                                if incoming_records > 0 and outgoing_records == 0:
                                    orphan_type = "written_not_read"
                                    orphan_reason = f"Data written ({int(incoming_records)} records) but never read for {written_not_read_lookback_days} days - no consumers"
                                    confidence = "high" if age_days >= confidence_threshold_days else "medium"
                                    monthly_cost = self.PRICING["kinesis_shard"] * shard_count
                                    print(f"🌊 [DEBUG] ✅ {stream_name} detected as ORPHAN: type={orphan_type}, confidence={confidence}")

                            except ClientError as e:
                                print(f"Warning: Could not check written_not_read metrics for {stream_name}: {e}")

                        # PRIORITY 3: Check if under-utilized (< 1% capacity)
                        if orphan_type is None and detect_underutilized:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=underutilized_lookback_days)

                                # Get IncomingBytes
                                bytes_response = await cw.get_metric_statistics(
                                    Namespace="AWS/Kinesis",
                                    MetricName="IncomingBytes",
                                    Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                    StartTime=start_time,
                                    EndTime=now,
                                    Period=3600,
                                    Statistics=["Sum"],
                                )
                                incoming_bytes = sum(dp["Sum"] for dp in bytes_response.get("Datapoints", []))

                                # Calculate capacity: 1 shard = 1 MB/s = 86.4 GB/day
                                capacity_bytes_per_period = shard_count * 86.4 * 1024 * 1024 * 1024 * underutilized_lookback_days
                                utilization_percent = (incoming_bytes / capacity_bytes_per_period * 100) if capacity_bytes_per_period > 0 else 0

                                if utilization_percent < utilization_threshold_percent:
                                    orphan_type = "underutilized"
                                    orphan_reason = f"Stream under-utilized: {utilization_percent:.2f}% capacity used ({shard_count} shards) - {incoming_bytes / (1024**3):.2f} GB over {underutilized_lookback_days} days"
                                    confidence = "medium" if age_days >= confidence_threshold_days else "low"
                                    monthly_cost = self.PRICING["kinesis_shard"] * shard_count * 0.8  # 80% waste estimate
                                    print(f"🌊 [DEBUG] ✅ {stream_name} detected as ORPHAN: type={orphan_type}, confidence={confidence}, utilization={utilization_percent:.2f}%")

                            except ClientError as e:
                                print(f"Warning: Could not check underutilized metrics for {stream_name}: {e}")

                        # PRIORITY 4: Check excessive retention
                        if orphan_type is None and detect_excessive_retention:
                            try:
                                if retention_hours > 24:
                                    now = datetime.now(timezone.utc)
                                    start_time = now - timedelta(days=7)

                                    # Get GetRecords.IteratorAgeMilliseconds (how old records are when read)
                                    iterator_response = await cw.get_metric_statistics(
                                        Namespace="AWS/Kinesis",
                                        MetricName="GetRecords.IteratorAgeMilliseconds",
                                        Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                        StartTime=start_time,
                                        EndTime=now,
                                        Period=3600,
                                        Statistics=["Average"],
                                    )
                                    datapoints = iterator_response.get("Datapoints", [])
                                    if datapoints:
                                        iterator_age_avg_ms = sum(dp["Average"] for dp in datapoints) / len(datapoints)

                                        # If records are read very quickly (< 1 minute), long retention is wasteful
                                        if iterator_age_avg_ms < max_iterator_age_ms:
                                            # Calculate retention cost (approximate)
                                            retention_cost_per_gb = self.PRICING["kinesis_retention_extended_per_gb"] if retention_hours <= 168 else self.PRICING["kinesis_retention_long_per_gb"]
                                            # Rough estimate: assume 1 GB per shard per day
                                            estimated_gb = shard_count * (retention_hours / 24)
                                            retention_cost = estimated_gb * retention_cost_per_gb

                                            orphan_type = "excessive_retention"
                                            orphan_reason = f"Retention set to {retention_hours}h but data read in real-time (avg {iterator_age_avg_ms/1000:.1f}s) - excessive retention cost"
                                            confidence = "low"
                                            monthly_cost = retention_cost
                                            print(f"🌊 [DEBUG] ✅ {stream_name} detected as ORPHAN: type={orphan_type}, confidence={confidence}, retention={retention_hours}h")

                            except ClientError as e:
                                print(f"Warning: Could not check excessive_retention metrics for {stream_name}: {e}")

                        # PRIORITY 5: Check unused Enhanced Fan-Out
                        if orphan_type is None and detect_unused_enhanced_fanout:
                            try:
                                # List registered consumers
                                consumers_response = await kinesis.list_stream_consumers(StreamARN=stream_arn)
                                consumers = consumers_response.get("Consumers", [])

                                if consumers:
                                    # Check if any consumer is actually using Enhanced Fan-Out
                                    # If consumers registered but no SubscribeToShard activity, it's wasteful
                                    now = datetime.now(timezone.utc)
                                    start_time = now - timedelta(days=7)

                                    # Note: Enhanced Fan-Out metrics are under consumer-specific dimensions
                                    # For simplicity, we detect registered consumers as potential waste
                                    # In production, you'd check SubscribeToShard.* metrics per consumer

                                    consumer_count = len(consumers)
                                    enhanced_fanout_cost = self.PRICING["kinesis_enhanced_fanout_per_consumer"] * consumer_count * shard_count

                                    orphan_type = "unused_enhanced_fanout"
                                    orphan_reason = f"{consumer_count} Enhanced Fan-Out consumers registered - verify if actively used"
                                    confidence = "medium"
                                    monthly_cost = enhanced_fanout_cost
                                    enhanced_fanout_consumers = [c["ConsumerName"] for c in consumers]
                                    print(f"🌊 [DEBUG] ✅ {stream_name} detected as ORPHAN: type={orphan_type}, confidence={confidence}, consumers={consumer_count}")

                            except ClientError as e:
                                print(f"Warning: Could not check Enhanced Fan-Out for {stream_name}: {e}")

                        # PRIORITY 6: Check over-provisioning
                        if orphan_type is None and detect_overprovisioned:
                            try:
                                now = datetime.now(timezone.utc)
                                start_time = now - timedelta(days=7)

                                # Get IncomingBytes if not already retrieved
                                if incoming_bytes == 0:
                                    bytes_response = await cw.get_metric_statistics(
                                        Namespace="AWS/Kinesis",
                                        MetricName="IncomingBytes",
                                        Dimensions=[{"Name": "StreamName", "Value": stream_name}],
                                        StartTime=start_time,
                                        EndTime=now,
                                        Period=3600,
                                        Statistics=["Sum"],
                                    )
                                    incoming_bytes = sum(dp["Sum"] for dp in bytes_response.get("Datapoints", []))

                                # Calculate actual throughput vs capacity
                                capacity_bytes_per_day = shard_count * 86.4 * 1024 * 1024 * 1024  # 1 MB/s per shard
                                actual_bytes_per_day = incoming_bytes / 7  # Average over 7 days
                                capacity_ratio = (capacity_bytes_per_day / actual_bytes_per_day) if actual_bytes_per_day > 0 else float('inf')

                                if capacity_ratio > overprovisioning_ratio:
                                    orphan_type = "overprovisioned"
                                    orphan_reason = f"{shard_count} shards provisioned but only using {actual_bytes_per_day / (1024**3):.2f} GB/day ({capacity_ratio:.1f}x over-provisioned)"
                                    confidence = "low"
                                    monthly_cost = self.PRICING["kinesis_shard"] * shard_count * 0.7  # 70% waste estimate
                                    print(f"🌊 [DEBUG] ✅ {stream_name} detected as ORPHAN: type={orphan_type}, confidence={confidence}, ratio={capacity_ratio:.1f}x")

                            except ClientError as e:
                                print(f"Warning: Could not check overprovisioned metrics for {stream_name}: {e}")

                        # If any scenario detected, add to orphans
                        if orphan_type is not None:
                            orphans.append(
                                OrphanResourceData(
                                    resource_type="kinesis_stream",
                                    resource_id=stream_name,
                                    resource_name=stream_name,
                                    region=region,
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "shard_count": shard_count,
                                        "status": stream_status,
                                        "retention_hours": retention_hours,
                                        "created_at": created_at.isoformat(),
                                        "age_days": age_days,
                                        "orphan_type": orphan_type,
                                        "confidence": confidence,
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                        "orphan_reason": orphan_reason,
                                        "incoming_records": int(incoming_records),
                                        "outgoing_records": int(outgoing_records),
                                        "incoming_bytes": int(incoming_bytes),
                                        "iterator_age_avg_ms": int(iterator_age_avg_ms),
                                        "enhanced_fanout_consumers": enhanced_fanout_consumers,
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
                                    "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
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
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                        "orphan_reason": reason,
                                        "avg_connections_7d": round(avg_connections, 2),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning DocumentDB clusters in {region}: {e}")

        return orphans

    async def scan_idle_s3_buckets(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle S3 buckets (global resources).

        Note: S3 buckets are global, so this should be called once per account, not per region.

        Detection scenarios:
        1. Empty bucket (0 objects, age > 90 days)
        2. All objects very old (all objects LastModified > 365 days)
        3. Incomplete multipart uploads (> 30 days old)
        4. No lifecycle policy + old objects (objects > 180 days, no lifecycle)

        Args:
            detection_rules: Optional detection configuration

        Returns:
            List of idle S3 buckets
        """
        print("🗄️ [DEBUG] scan_idle_s3_buckets called")
        orphans = []

        # Default detection rules
        min_bucket_age_days = detection_rules.get("min_bucket_age_days", 90) if detection_rules else 90
        detect_empty = detection_rules.get("detect_empty", True) if detection_rules else True
        detect_old_objects = detection_rules.get("detect_old_objects", True) if detection_rules else True
        object_age_threshold_days = detection_rules.get("object_age_threshold_days", 365) if detection_rules else 365
        detect_multipart_uploads = detection_rules.get("detect_multipart_uploads", True) if detection_rules else True
        multipart_age_days = detection_rules.get("multipart_age_days", 30) if detection_rules else 30
        detect_no_lifecycle = detection_rules.get("detect_no_lifecycle", True) if detection_rules else True
        lifecycle_age_threshold_days = detection_rules.get("lifecycle_age_threshold_days", 180) if detection_rules else 180

        try:
            async with self.session.client("s3") as s3:
                # List all buckets (global)
                response = await s3.list_buckets()
                buckets = response.get("Buckets", [])
                print(f"🗄️ [DEBUG] Found {len(buckets)} S3 buckets in account")

                for bucket_info in buckets:
                    bucket_name = bucket_info["Name"]
                    bucket_creation_date = bucket_info.get("CreationDate")

                    print(f"🗄️ [DEBUG] Analyzing bucket: {bucket_name}")

                    if not bucket_creation_date:
                        print(f"🗄️ [DEBUG] Skipping {bucket_name}: no creation date")
                        continue

                    # Calculate bucket age
                    bucket_age_days = (datetime.now(timezone.utc) - bucket_creation_date).days
                    print(f"🗄️ [DEBUG] Bucket {bucket_name}: age={bucket_age_days} days, min_required={min_bucket_age_days} days")

                    # Skip young buckets
                    if bucket_age_days < min_bucket_age_days:
                        print(f"🗄️ [DEBUG] Skipping {bucket_name}: too young ({bucket_age_days} < {min_bucket_age_days} days)")
                        continue

                    try:
                        # Get bucket location (region)
                        location_response = await s3.get_bucket_location(Bucket=bucket_name)
                        bucket_region = location_response.get("LocationConstraint") or "us-east-1"

                        # List objects (limit to first 1000 to avoid timeout)
                        objects_response = await s3.list_objects_v2(
                            Bucket=bucket_name,
                            MaxKeys=1000
                        )

                        object_count = objects_response.get("KeyCount", 0)
                        objects = objects_response.get("Contents", [])

                        # Calculate bucket size (GB) and storage class distribution
                        total_size_bytes = 0
                        storage_classes = {}
                        oldest_object_date = None
                        newest_object_date = None

                        for obj in objects:
                            total_size_bytes += obj.get("Size", 0)
                            storage_class = obj.get("StorageClass", "STANDARD")
                            storage_classes[storage_class] = storage_classes.get(storage_class, 0) + obj.get("Size", 0)

                            # Track oldest and newest objects
                            last_modified = obj.get("LastModified")
                            if last_modified:
                                if not oldest_object_date or last_modified < oldest_object_date:
                                    oldest_object_date = last_modified
                                if not newest_object_date or last_modified > newest_object_date:
                                    newest_object_date = last_modified

                        bucket_size_gb = total_size_bytes / (1024 ** 3)

                        # Scenario detection
                        orphan_type = None
                        orphan_reason = None
                        confidence = "medium"
                        monthly_cost = 0.0

                        # PRIORITY 1: Incomplete multipart uploads (HIGHEST PRIORITY - hidden costs)
                        # Check this FIRST because a bucket can be empty AND have multipart uploads
                        if detect_multipart_uploads:
                            try:
                                multipart_response = await s3.list_multipart_uploads(Bucket=bucket_name)
                                multipart_uploads = multipart_response.get("Uploads", [])

                                old_multiparts = []
                                multipart_size_bytes = 0

                                for upload in multipart_uploads:
                                    initiated = upload.get("Initiated")
                                    if initiated:
                                        days_since_upload = (datetime.now(timezone.utc) - initiated).days
                                        if days_since_upload >= multipart_age_days:
                                            old_multiparts.append(upload)
                                            # Estimate size (multipart uploads can be large, estimate 100MB each)
                                            multipart_size_bytes += 100 * 1024 * 1024

                                if old_multiparts:
                                    orphan_type = "multipart_uploads"
                                    orphan_reason = f"{len(old_multiparts)} incomplete multipart uploads (>{multipart_age_days} days old)"
                                    confidence = "high" if len(old_multiparts) > 5 else "medium"

                                    # Add multipart cost to existing storage
                                    multipart_size_gb = multipart_size_bytes / (1024 ** 3)
                                    total_storage_gb = bucket_size_gb + multipart_size_gb
                                    monthly_cost = total_storage_gb * self.PRICING.get("s3_standard_per_gb", 0.023)

                            except ClientError as e:
                                # Some buckets may not allow listing multipart uploads
                                if "AccessDenied" not in str(e):
                                    print(f"Warning: Could not list multipart uploads for {bucket_name}: {e}")

                        # PRIORITY 2: No lifecycle policy + old objects (optimization opportunity)
                        if orphan_type is None and detect_no_lifecycle and object_count > 0 and oldest_object_date:
                            try:
                                # Check if bucket has a lifecycle configuration
                                await s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
                                has_lifecycle = True
                            except ClientError as e:
                                if "NoSuchLifecycleConfiguration" in str(e):
                                    has_lifecycle = False
                                else:
                                    has_lifecycle = False  # Treat errors as no lifecycle

                            if not has_lifecycle:
                                days_since_oldest = (datetime.now(timezone.utc) - oldest_object_date).days
                                if days_since_oldest >= lifecycle_age_threshold_days:
                                    orphan_type = "no_lifecycle"
                                    orphan_reason = f"No lifecycle policy, objects are {days_since_oldest}+ days old ({object_count} objects, {bucket_size_gb:.2f} GB)"
                                    confidence = "medium"

                                    # Calculate cost
                                    dominant_class = max(storage_classes.items(), key=lambda x: x[1])[0] if storage_classes else "STANDARD"
                                    if "STANDARD_IA" in dominant_class:
                                        monthly_cost = bucket_size_gb * self.PRICING.get("s3_standard_ia_per_gb", 0.0125)
                                    else:
                                        monthly_cost = bucket_size_gb * self.PRICING.get("s3_standard_per_gb", 0.023)

                        # PRIORITY 3: All objects very old (fallback)
                        if orphan_type is None and detect_old_objects and object_count > 0 and oldest_object_date and newest_object_date:
                            days_since_newest = (datetime.now(timezone.utc) - newest_object_date).days
                            if days_since_newest >= object_age_threshold_days:
                                orphan_type = "old_objects"
                                orphan_reason = f"All {object_count} objects are {days_since_newest}+ days old (no recent activity)"
                                confidence = "high" if days_since_newest >= 730 else "medium"  # 2 years = high confidence

                                # Calculate cost based on dominant storage class
                                dominant_class = max(storage_classes.items(), key=lambda x: x[1])[0] if storage_classes else "STANDARD"
                                if "GLACIER" in dominant_class or "DEEP_ARCHIVE" in dominant_class:
                                    monthly_cost = bucket_size_gb * self.PRICING.get("s3_glacier_per_gb", 0.004)
                                elif "INTELLIGENT_TIERING" in dominant_class or "STANDARD_IA" in dominant_class:
                                    monthly_cost = bucket_size_gb * self.PRICING.get("s3_standard_ia_per_gb", 0.0125)
                                else:
                                    monthly_cost = bucket_size_gb * self.PRICING.get("s3_standard_per_gb", 0.023)

                        # PRIORITY 4: Empty bucket (last resort - lowest priority)
                        if orphan_type is None and detect_empty and object_count == 0:
                            orphan_type = "empty"
                            orphan_reason = f"Bucket is empty ({bucket_age_days} days old)"
                            confidence = "high" if bucket_age_days >= 180 else "medium"
                            # Empty buckets still cost $0 for storage, but minimal cost for having the bucket
                            monthly_cost = 0.0

                        # Add to orphans if detected
                        if orphan_type:
                            print(f"🗄️ [DEBUG] ✅ Bucket {bucket_name} detected as ORPHAN: type={orphan_type}, reason={orphan_reason}")
                            orphans.append(
                                OrphanResourceData(
                                    resource_type="s3_bucket",
                                    resource_id=bucket_name,
                                    resource_name=bucket_name,
                                    region=bucket_region,
                                    estimated_monthly_cost=round(monthly_cost, 2),
                                    resource_metadata={
                                        "bucket_region": bucket_region,
                                        "object_count": object_count,
                                        "bucket_size_gb": round(bucket_size_gb, 2),
                                        "creation_date": bucket_creation_date.isoformat(),
                                        "bucket_age_days": bucket_age_days,
                                        "oldest_object_days": (datetime.now(timezone.utc) - oldest_object_date).days if oldest_object_date else None,
                                        "newest_object_days": (datetime.now(timezone.utc) - newest_object_date).days if newest_object_date else None,
                                        "storage_classes": {k: round(v / (1024 ** 3), 2) for k, v in storage_classes.items()},
                                        "orphan_type": orphan_type,
                                        "orphan_reason": orphan_reason,
                                        "confidence": confidence,
                                        "confidence_level": self._calculate_confidence_level(bucket_age_days, detection_rules),
                                    },
                                )
                            )

                    except ClientError as e:
                        # Handle bucket-specific errors (e.g., access denied, bucket in different region)
                        error_code = e.response.get("Error", {}).get("Code", "Unknown")
                        if error_code not in ["AccessDenied", "NoSuchBucket"]:
                            print(f"Error scanning S3 bucket {bucket_name}: {e}")

        except ClientError as e:
            print(f"Error listing S3 buckets: {e}")

        print(f"🗄️ [DEBUG] scan_idle_s3_buckets completed: Found {len(orphans)} idle S3 buckets")
        return orphans

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
            region: AWS region to scan
            detection_rules: Custom detection rules configuration

        Returns:
            List of orphaned Lambda functions
        """
        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 60) if detection_rules else 60
        critical_age_days = detection_rules.get("critical_age_days", 180) if detection_rules else 180

        # Provisioned concurrency rules
        detect_unused_provisioned = detection_rules.get("detect_unused_provisioned_concurrency", True) if detection_rules else True
        provisioned_min_age_days = detection_rules.get("provisioned_min_age_days", 30) if detection_rules else 30
        provisioned_critical_days = detection_rules.get("provisioned_critical_days", 90) if detection_rules else 90
        provisioned_utilization_threshold = detection_rules.get("provisioned_utilization_threshold", 1.0) if detection_rules else 1.0

        # Never invoked rules
        detect_never_invoked = detection_rules.get("detect_never_invoked", True) if detection_rules else True
        never_invoked_min_age_days = detection_rules.get("never_invoked_min_age_days", 30) if detection_rules else 30
        never_invoked_confidence_days = detection_rules.get("never_invoked_confidence_days", 60) if detection_rules else 60

        # Zero invocations rules
        detect_zero_invocations = detection_rules.get("detect_zero_invocations", True) if detection_rules else True
        zero_invocations_lookback_days = detection_rules.get("zero_invocations_lookback_days", 90) if detection_rules else 90
        zero_invocations_confidence_days = detection_rules.get("zero_invocations_confidence_days", 180) if detection_rules else 180

        # Failure detection rules
        detect_all_failures = detection_rules.get("detect_all_failures", True) if detection_rules else True
        failure_rate_threshold = detection_rules.get("failure_rate_threshold", 95.0) if detection_rules else 95.0
        min_invocations_for_failure_check = detection_rules.get("min_invocations_for_failure_check", 10) if detection_rules else 10
        failure_lookback_days = detection_rules.get("failure_lookback_days", 30) if detection_rules else 30

        print(f"⚡ [DEBUG] scan_idle_lambda_functions called for region: {region}")

        try:
            async with self.session.client("lambda", region_name=region) as lambda_client:
                async with self.session.client("cloudwatch", region_name=region) as cloudwatch_client:
                    # List all Lambda functions
                    paginator = lambda_client.get_paginator("list_functions")
                    async for page in paginator.paginate():
                        for function in page.get("Functions", []):
                            function_name = function.get("FunctionName")
                            function_arn = function.get("FunctionArn")
                            memory_size_mb = function.get("MemorySize", 128)
                            memory_size_gb = memory_size_mb / 1024
                            last_modified = function.get("LastModified")  # ISO 8601 string

                            # Parse creation date
                            try:
                                creation_date = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
                                age_days = (datetime.now(timezone.utc) - creation_date).days
                            except Exception:
                                age_days = 0

                            print(f"⚡ [DEBUG] Analyzing Lambda: {function_name} (age={age_days} days, memory={memory_size_mb}MB)")

                            # Skip very young functions
                            if age_days < min_age_days:
                                print(f"⚡ [DEBUG] Skipping {function_name}: too young ({age_days} < {min_age_days} days)")
                                continue

                            orphan_type = None
                            orphan_reason = None
                            confidence = "medium"
                            monthly_cost = 0.0

                            # PRIORITY 1: Check provisioned concurrency (VERY EXPENSIVE)
                            if detect_unused_provisioned:
                                try:
                                    provisioned_configs = await lambda_client.list_provisioned_concurrency_configs(
                                        FunctionName=function_name
                                    )
                                    for config in provisioned_configs.get("ProvisionedConcurrencyConfigs", []):
                                        allocated_concurrency = config.get("AllocatedProvisionedConcurrentExecutions", 0)
                                        if allocated_concurrency > 0:
                                            # Check CloudWatch: ProvisionedConcurrencyInvocations
                                            end_time = datetime.now(timezone.utc)
                                            start_time = end_time - timedelta(days=provisioned_min_age_days)

                                            metrics_response = await cloudwatch_client.get_metric_statistics(
                                                Namespace="AWS/Lambda",
                                                MetricName="ProvisionedConcurrencyInvocations",
                                                Dimensions=[
                                                    {"Name": "FunctionName", "Value": function_name},
                                                    {"Name": "Resource", "Value": f"{function_name}:{config.get('FunctionVersion', '$LATEST')}"},
                                                ],
                                                StartTime=start_time,
                                                EndTime=end_time,
                                                Period=86400,  # 1 day
                                                Statistics=["Sum"],
                                            )

                                            provisioned_invocations = sum(
                                                dp.get("Sum", 0) for dp in metrics_response.get("Datapoints", [])
                                            )

                                            # Check total invocations for comparison
                                            total_metrics = await cloudwatch_client.get_metric_statistics(
                                                Namespace="AWS/Lambda",
                                                MetricName="Invocations",
                                                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                                                StartTime=start_time,
                                                EndTime=end_time,
                                                Period=86400,
                                                Statistics=["Sum"],
                                            )

                                            total_invocations = sum(
                                                dp.get("Sum", 0) for dp in total_metrics.get("Datapoints", [])
                                            )

                                            utilization_pct = (
                                                (provisioned_invocations / total_invocations * 100)
                                                if total_invocations > 0
                                                else 0.0
                                            )

                                            if utilization_pct < provisioned_utilization_threshold:
                                                orphan_type = "unused_provisioned_concurrency"
                                                orphan_reason = f"Provisioned concurrency ({allocated_concurrency} units) unused: {utilization_pct:.1f}% utilization over {provisioned_min_age_days} days"
                                                confidence = "critical" if provisioned_min_age_days >= provisioned_critical_days else "high"

                                                # Calculate cost: provisioned concurrency is charged 24/7
                                                seconds_per_month = 30 * 24 * 60 * 60
                                                monthly_cost = (
                                                    allocated_concurrency
                                                    * memory_size_gb
                                                    * seconds_per_month
                                                    * self.PRICING.get("lambda_provisioned_concurrency_gb_second", 0.0000041667)
                                                )
                                                print(
                                                    f"⚡ [DEBUG] ✅ {function_name} detected as ORPHAN: type={orphan_type}, utilization={utilization_pct:.1f}%, cost=${monthly_cost:.2f}/month"
                                                )
                                                break  # Don't check other scenarios if provisioned concurrency detected

                                except ClientError as e:
                                    # No provisioned concurrency configured or access denied
                                    if "ResourceNotFoundException" not in str(e):
                                        print(f"Warning: Could not check provisioned concurrency for {function_name}: {e}")

                            # PRIORITY 2: Check if never invoked
                            if orphan_type is None and detect_never_invoked:
                                try:
                                    end_time = datetime.now(timezone.utc)
                                    start_time = creation_date  # Check since creation

                                    metrics_response = await cloudwatch_client.get_metric_statistics(
                                        Namespace="AWS/Lambda",
                                        MetricName="Invocations",
                                        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=86400,  # 1 day
                                        Statistics=["Sum"],
                                    )

                                    total_invocations = sum(dp.get("Sum", 0) for dp in metrics_response.get("Datapoints", []))

                                    if total_invocations == 0 and age_days >= never_invoked_min_age_days:
                                        orphan_type = "never_invoked"
                                        orphan_reason = f"Never invoked since creation ({age_days} days ago)"
                                        confidence = "critical" if age_days >= critical_age_days else (
                                            "high" if age_days >= never_invoked_confidence_days else "medium"
                                        )
                                        # Cost: minimal (just storage, no compute)
                                        monthly_cost = 0.5  # Estimate: minimal storage cost
                                        print(f"⚡ [DEBUG] ✅ {function_name} detected as ORPHAN: type={orphan_type}, age={age_days} days")

                                except ClientError as e:
                                    print(f"Warning: Could not check invocations for {function_name}: {e}")

                            # PRIORITY 3: Check zero invocations (last X days)
                            if orphan_type is None and detect_zero_invocations:
                                try:
                                    end_time = datetime.now(timezone.utc)
                                    start_time = end_time - timedelta(days=zero_invocations_lookback_days)

                                    metrics_response = await cloudwatch_client.get_metric_statistics(
                                        Namespace="AWS/Lambda",
                                        MetricName="Invocations",
                                        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=["Sum"],
                                    )

                                    recent_invocations = sum(dp.get("Sum", 0) for dp in metrics_response.get("Datapoints", []))

                                    if recent_invocations == 0:
                                        orphan_type = "zero_invocations"
                                        orphan_reason = f"No invocations in last {zero_invocations_lookback_days} days"
                                        confidence = "high" if age_days >= zero_invocations_confidence_days else "medium"
                                        monthly_cost = 0.5  # Estimate
                                        print(f"⚡ [DEBUG] ✅ {function_name} detected as ORPHAN: type={orphan_type}, lookback={zero_invocations_lookback_days} days")

                                except ClientError as e:
                                    print(f"Warning: Could not check recent invocations for {function_name}: {e}")

                            # PRIORITY 4: Check 100% failures (dead function)
                            if orphan_type is None and detect_all_failures:
                                try:
                                    end_time = datetime.now(timezone.utc)
                                    start_time = end_time - timedelta(days=failure_lookback_days)

                                    # Get invocations
                                    invocations_response = await cloudwatch_client.get_metric_statistics(
                                        Namespace="AWS/Lambda",
                                        MetricName="Invocations",
                                        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=["Sum"],
                                    )

                                    total_invocations = sum(dp.get("Sum", 0) for dp in invocations_response.get("Datapoints", []))

                                    # Get errors
                                    errors_response = await cloudwatch_client.get_metric_statistics(
                                        Namespace="AWS/Lambda",
                                        MetricName="Errors",
                                        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=["Sum"],
                                    )

                                    total_errors = sum(dp.get("Sum", 0) for dp in errors_response.get("Datapoints", []))

                                    if total_invocations >= min_invocations_for_failure_check:
                                        failure_rate = (total_errors / total_invocations) * 100 if total_invocations > 0 else 0

                                        if failure_rate >= failure_rate_threshold:
                                            orphan_type = "all_failures"
                                            orphan_reason = f"{failure_rate:.1f}% failure rate ({int(total_errors)}/{int(total_invocations)} errors) over {failure_lookback_days} days"
                                            confidence = "high"
                                            # Cost: charged even for failures
                                            monthly_cost = 1.0  # Estimate
                                            print(f"⚡ [DEBUG] ✅ {function_name} detected as ORPHAN: type={orphan_type}, failure_rate={failure_rate:.1f}%")

                                except ClientError as e:
                                    print(f"Warning: Could not check failures for {function_name}: {e}")

                            # Add to orphans if detected
                            if orphan_type:
                                orphans.append(
                                    OrphanResourceData(
                                        resource_type="lambda_function",
                                        resource_id=function_arn,
                                        resource_name=function_name,
                                        region=region,
                                        estimated_monthly_cost=round(monthly_cost, 2),
                                        resource_metadata={
                                            "function_arn": function_arn,
                                            "memory_size_mb": memory_size_mb,
                                            "runtime": function.get("Runtime"),
                                            "age_days": age_days,
                                            "last_modified": last_modified,
                                            "orphan_type": orphan_type,
                                            "orphan_reason": orphan_reason,
                                            "confidence": confidence,
                                            "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                        },
                                    )
                                )

        except ClientError as e:
            print(f"Error scanning Lambda functions in {region}: {e}")

        print(f"⚡ [DEBUG] scan_idle_lambda_functions completed for {region}: Found {len(orphans)} idle functions")
        return orphans

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
            region: AWS region to scan
            detection_rules: Custom detection rules configuration

        Returns:
            List of orphaned DynamoDB tables
        """
        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7
        confidence_threshold_days = detection_rules.get("confidence_threshold_days", 30) if detection_rules else 30
        critical_age_days = detection_rules.get("critical_age_days", 90) if detection_rules else 90

        # PRIORITY 1: Over-provisioned capacity
        detect_over_provisioned = detection_rules.get("detect_over_provisioned", True) if detection_rules else True
        provisioned_utilization_threshold = detection_rules.get("provisioned_utilization_threshold", 10.0) if detection_rules else 10.0
        provisioned_lookback_days = detection_rules.get("provisioned_lookback_days", 7) if detection_rules else 7

        # PRIORITY 2: Unused GSI
        detect_unused_gsi = detection_rules.get("detect_unused_gsi", True) if detection_rules else True
        gsi_lookback_days = detection_rules.get("gsi_lookback_days", 14) if detection_rules else 14

        # PRIORITY 3: Never used (Provisioned)
        detect_never_used_provisioned = detection_rules.get("detect_never_used_provisioned", True) if detection_rules else True
        never_used_min_age_days = detection_rules.get("never_used_min_age_days", 30) if detection_rules else 30

        # PRIORITY 4: Never used (On-Demand)
        detect_never_used_ondemand = detection_rules.get("detect_never_used_ondemand", True) if detection_rules else True
        ondemand_lookback_days = detection_rules.get("ondemand_lookback_days", 60) if detection_rules else 60

        # PRIORITY 5: Empty tables
        detect_empty_tables = detection_rules.get("detect_empty_tables", True) if detection_rules else True
        empty_table_min_age_days = detection_rules.get("empty_table_min_age_days", 90) if detection_rules else 90

        print(f"🗃️ [DEBUG] scan_idle_dynamodb_tables called for region: {region}")

        try:
            async with self.session.client("dynamodb", region_name=region) as dynamodb_client:
                async with self.session.client("cloudwatch", region_name=region) as cloudwatch_client:
                    # List all DynamoDB tables
                    paginator = dynamodb_client.get_paginator("list_tables")
                    all_table_names = []
                    async for page in paginator.paginate():
                        all_table_names.extend(page.get("TableNames", []))

                    print(f"🗃️ [DEBUG] Found {len(all_table_names)} DynamoDB tables in {region}")

                    for table_name in all_table_names:
                        # Get table details
                        table_response = await dynamodb_client.describe_table(TableName=table_name)
                        table = table_response.get("Table", {})

                        # Extract table metadata
                        table_arn = table.get("TableArn")
                        table_status = table.get("TableStatus")
                        creation_date = table.get("CreationDateTime")
                        item_count = table.get("ItemCount", 0)
                        table_size_bytes = table.get("TableSizeBytes", 0)
                        table_size_gb = table_size_bytes / (1024 ** 3) if table_size_bytes > 0 else 0

                        # Billing mode
                        billing_mode_summary = table.get("BillingModeSummary", {})
                        billing_mode = billing_mode_summary.get("BillingMode", "PROVISIONED")

                        # Provisioned throughput (if applicable)
                        provisioned_throughput = table.get("ProvisionedThroughput", {})
                        provisioned_read_capacity = provisioned_throughput.get("ReadCapacityUnits", 0)
                        provisioned_write_capacity = provisioned_throughput.get("WriteCapacityUnits", 0)

                        # Global Secondary Indexes
                        global_secondary_indexes = table.get("GlobalSecondaryIndexes", [])

                        # Calculate age
                        try:
                            age_days = (datetime.now(timezone.utc) - creation_date).days
                        except Exception:
                            age_days = 0

                        print(f"🗃️ [DEBUG] Analyzing table: {table_name} (age={age_days} days, billing={billing_mode}, items={item_count}, size={table_size_gb:.2f}GB)")

                        # Skip very young tables
                        if age_days < min_age_days:
                            print(f"🗃️ [DEBUG] Skipping {table_name}: too young ({age_days} < {min_age_days} days)")
                            continue

                        # Skip non-ACTIVE tables
                        if table_status != "ACTIVE":
                            print(f"🗃️ [DEBUG] Skipping {table_name}: status={table_status} (not ACTIVE)")
                            continue

                        orphan_type = None
                        orphan_reason = None
                        confidence = "medium"
                        monthly_cost = 0.0

                        # PRIORITY 1: Check over-provisioned capacity (PROVISIONED mode only)
                        if detect_over_provisioned and billing_mode == "PROVISIONED" and (provisioned_read_capacity > 0 or provisioned_write_capacity > 0):
                            try:
                                end_time = datetime.now(timezone.utc)
                                start_time = end_time - timedelta(days=provisioned_lookback_days)

                                # Get consumed read capacity
                                read_metrics = await cloudwatch_client.get_metric_statistics(
                                    Namespace="AWS/DynamoDB",
                                    MetricName="ConsumedReadCapacityUnits",
                                    Dimensions=[{"Name": "TableName", "Value": table_name}],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,  # 1 day
                                    Statistics=["Sum"],
                                )

                                # Get consumed write capacity
                                write_metrics = await cloudwatch_client.get_metric_statistics(
                                    Namespace="AWS/DynamoDB",
                                    MetricName="ConsumedWriteCapacityUnits",
                                    Dimensions=[{"Name": "TableName", "Value": table_name}],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=["Sum"],
                                )

                                read_datapoints = read_metrics.get("Datapoints", [])
                                write_datapoints = write_metrics.get("Datapoints", [])

                                total_consumed_read = sum(dp.get("Sum", 0) for dp in read_datapoints)
                                total_consumed_write = sum(dp.get("Sum", 0) for dp in write_datapoints)

                                # Calculate utilization %
                                # Provisioned capacity is per second, so over lookback days:
                                total_provisioned_read = provisioned_read_capacity * provisioned_lookback_days * 86400
                                total_provisioned_write = provisioned_write_capacity * provisioned_lookback_days * 86400

                                read_utilization = (total_consumed_read / total_provisioned_read * 100) if total_provisioned_read > 0 else 0
                                write_utilization = (total_consumed_write / total_provisioned_write * 100) if total_provisioned_write > 0 else 0
                                avg_utilization = (read_utilization + write_utilization) / 2

                                if avg_utilization < provisioned_utilization_threshold:
                                    orphan_type = "over_provisioned"
                                    orphan_reason = f"Over-provisioned capacity: {avg_utilization:.1f}% avg utilization (Read: {read_utilization:.1f}%, Write: {write_utilization:.1f}%) over {provisioned_lookback_days} days"
                                    confidence = "critical" if avg_utilization < 5.0 else "high"

                                    # Calculate cost: provisioned capacity charged 24/7
                                    monthly_cost = (
                                        (provisioned_read_capacity * self.PRICING["dynamodb_rcu_per_hour"] * 730) +
                                        (provisioned_write_capacity * self.PRICING["dynamodb_wcu_per_hour"] * 730) +
                                        (table_size_gb * self.PRICING["dynamodb_storage_per_gb"])
                                    )
                                    print(f"🗃️ [DEBUG] ✅ {table_name} detected as ORPHAN: type={orphan_type}, utilization={avg_utilization:.1f}%, cost=${monthly_cost:.2f}/month")

                            except ClientError as e:
                                print(f"Warning: Could not check capacity utilization for {table_name}: {e}")

                        # PRIORITY 2: Check unused Global Secondary Indexes
                        if orphan_type is None and detect_unused_gsi and len(global_secondary_indexes) > 0:
                            for gsi in global_secondary_indexes:
                                gsi_name = gsi.get("IndexName")
                                gsi_status = gsi.get("IndexStatus")

                                if gsi_status != "ACTIVE":
                                    continue

                                try:
                                    end_time = datetime.now(timezone.utc)
                                    start_time = end_time - timedelta(days=gsi_lookback_days)

                                    # Check GSI consumed capacity
                                    gsi_read_metrics = await cloudwatch_client.get_metric_statistics(
                                        Namespace="AWS/DynamoDB",
                                        MetricName="ConsumedReadCapacityUnits",
                                        Dimensions=[
                                            {"Name": "TableName", "Value": table_name},
                                            {"Name": "GlobalSecondaryIndexName", "Value": gsi_name},
                                        ],
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=["Sum"],
                                    )

                                    gsi_read_datapoints = gsi_read_metrics.get("Datapoints", [])
                                    gsi_total_read = sum(dp.get("Sum", 0) for dp in gsi_read_datapoints)

                                    if gsi_total_read == 0:
                                        orphan_type = "unused_gsi"
                                        orphan_reason = f"Unused Global Secondary Index '{gsi_name}' - never queried in {gsi_lookback_days} days (doubles table cost)"
                                        confidence = "high" if age_days >= confidence_threshold_days else "medium"

                                        # GSI cost = same as table cost (provisioned or on-demand)
                                        gsi_provisioned = gsi.get("ProvisionedThroughput", {})
                                        gsi_rcu = gsi_provisioned.get("ReadCapacityUnits", 0)
                                        gsi_wcu = gsi_provisioned.get("WriteCapacityUnits", 0)

                                        if billing_mode == "PROVISIONED":
                                            monthly_cost = (
                                                (gsi_rcu * self.PRICING["dynamodb_rcu_per_hour"] * 730) +
                                                (gsi_wcu * self.PRICING["dynamodb_wcu_per_hour"] * 730) +
                                                (table_size_gb * self.PRICING["dynamodb_storage_per_gb"])  # Storage duplicated
                                            )
                                        else:
                                            # On-demand: minimal cost if no usage
                                            monthly_cost = table_size_gb * self.PRICING["dynamodb_storage_per_gb"]

                                        print(f"🗃️ [DEBUG] ✅ {table_name} detected as ORPHAN: type={orphan_type}, GSI={gsi_name}, cost=${monthly_cost:.2f}/month")
                                        break  # Don't check other GSIs

                                except ClientError as e:
                                    print(f"Warning: Could not check GSI {gsi_name} for {table_name}: {e}")

                        # PRIORITY 3: Never used (Provisioned mode)
                        if orphan_type is None and detect_never_used_provisioned and billing_mode == "PROVISIONED":
                            try:
                                end_time = datetime.now(timezone.utc)
                                start_time = creation_date  # Check since creation

                                # Check if ever used
                                read_metrics = await cloudwatch_client.get_metric_statistics(
                                    Namespace="AWS/DynamoDB",
                                    MetricName="ConsumedReadCapacityUnits",
                                    Dimensions=[{"Name": "TableName", "Value": table_name}],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=["Sum"],
                                )

                                write_metrics = await cloudwatch_client.get_metric_statistics(
                                    Namespace="AWS/DynamoDB",
                                    MetricName="ConsumedWriteCapacityUnits",
                                    Dimensions=[{"Name": "TableName", "Value": table_name}],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=["Sum"],
                                )

                                total_reads = sum(dp.get("Sum", 0) for dp in read_metrics.get("Datapoints", []))
                                total_writes = sum(dp.get("Sum", 0) for dp in write_metrics.get("Datapoints", []))

                                if total_reads == 0 and total_writes == 0 and age_days >= never_used_min_age_days:
                                    orphan_type = "never_used_provisioned"
                                    orphan_reason = f"Never used since creation ({age_days} days ago) - paying for provisioned capacity with 0 usage"
                                    confidence = "critical" if age_days >= critical_age_days else ("high" if age_days >= confidence_threshold_days else "medium")

                                    # Cost: full provisioned cost + storage
                                    monthly_cost = (
                                        (provisioned_read_capacity * self.PRICING["dynamodb_rcu_per_hour"] * 730) +
                                        (provisioned_write_capacity * self.PRICING["dynamodb_wcu_per_hour"] * 730) +
                                        (table_size_gb * self.PRICING["dynamodb_storage_per_gb"])
                                    )
                                    print(f"🗃️ [DEBUG] ✅ {table_name} detected as ORPHAN: type={orphan_type}, age={age_days} days, cost=${monthly_cost:.2f}/month")

                            except ClientError as e:
                                print(f"Warning: Could not check usage for {table_name}: {e}")

                        # PRIORITY 4: Never used (On-Demand mode)
                        if orphan_type is None and detect_never_used_ondemand and billing_mode == "PAY_PER_REQUEST":
                            try:
                                end_time = datetime.now(timezone.utc)
                                start_time = end_time - timedelta(days=ondemand_lookback_days)

                                # Check recent usage
                                read_metrics = await cloudwatch_client.get_metric_statistics(
                                    Namespace="AWS/DynamoDB",
                                    MetricName="ConsumedReadCapacityUnits",
                                    Dimensions=[{"Name": "TableName", "Value": table_name}],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=["Sum"],
                                )

                                write_metrics = await cloudwatch_client.get_metric_statistics(
                                    Namespace="AWS/DynamoDB",
                                    MetricName="ConsumedWriteCapacityUnits",
                                    Dimensions=[{"Name": "TableName", "Value": table_name}],
                                    StartTime=start_time,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=["Sum"],
                                )

                                recent_reads = sum(dp.get("Sum", 0) for dp in read_metrics.get("Datapoints", []))
                                recent_writes = sum(dp.get("Sum", 0) for dp in write_metrics.get("Datapoints", []))

                                if recent_reads == 0 and recent_writes == 0:
                                    orphan_type = "never_used_ondemand"
                                    orphan_reason = f"On-Demand table with no usage in last {ondemand_lookback_days} days (only storage cost)"
                                    confidence = "high" if age_days >= confidence_threshold_days else "medium"

                                    # Cost: storage only (no requests)
                                    monthly_cost = table_size_gb * self.PRICING["dynamodb_storage_per_gb"]
                                    print(f"🗃️ [DEBUG] ✅ {table_name} detected as ORPHAN: type={orphan_type}, lookback={ondemand_lookback_days} days, cost=${monthly_cost:.2f}/month")

                            except ClientError as e:
                                print(f"Warning: Could not check on-demand usage for {table_name}: {e}")

                        # PRIORITY 5: Empty tables
                        if orphan_type is None and detect_empty_tables and item_count == 0 and age_days >= empty_table_min_age_days:
                            orphan_type = "empty_table"
                            orphan_reason = f"Table is empty (0 items) since creation {age_days} days ago"
                            confidence = "high" if age_days >= critical_age_days else "medium"

                            # Cost depends on billing mode
                            if billing_mode == "PROVISIONED":
                                monthly_cost = (
                                    (provisioned_read_capacity * self.PRICING["dynamodb_rcu_per_hour"] * 730) +
                                    (provisioned_write_capacity * self.PRICING["dynamodb_wcu_per_hour"] * 730)
                                )
                            else:
                                monthly_cost = 0.5  # Minimal cost for empty on-demand table

                            print(f"🗃️ [DEBUG] ✅ {table_name} detected as ORPHAN: type={orphan_type}, age={age_days} days, cost=${monthly_cost:.2f}/month")

                        # Add to orphans if detected
                        if orphan_type:
                            orphans.append(
                                OrphanResourceData(
                                    resource_type="dynamodb_table",
                                    resource_id=table_arn,
                                    resource_name=table_name,
                                    region=region,
                                    estimated_monthly_cost=round(monthly_cost, 2),
                                    resource_metadata={
                                        "table_arn": table_arn,
                                        "billing_mode": billing_mode,
                                        "item_count": item_count,
                                        "table_size_gb": round(table_size_gb, 2),
                                        "provisioned_read_capacity": provisioned_read_capacity,
                                        "provisioned_write_capacity": provisioned_write_capacity,
                                        "global_secondary_indexes_count": len(global_secondary_indexes),
                                        "age_days": age_days,
                                        "created_at": creation_date.isoformat() if creation_date else None,
                                        "orphan_type": orphan_type,
                                        "orphan_reason": orphan_reason,
                                        "confidence": confidence,
                                        "confidence_level": self._calculate_confidence_level(age_days, detection_rules),
                                    },
                                )
                            )

        except ClientError as e:
            print(f"Error scanning DynamoDB tables in {region}: {e}")

        print(f"🗃️ [DEBUG] scan_idle_dynamodb_tables completed for {region}: Found {len(orphans)} idle tables")
        return orphans
