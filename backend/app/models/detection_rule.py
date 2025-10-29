"""DetectionRule database model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


# Default detection rules (best practices)
DEFAULT_DETECTION_RULES = {
    "ebs_volume": {
        "enabled": True,
        "min_age_days": 7,  # Ignore volumes created in last 7 days
        "confidence_threshold_days": 30,  # High confidence after 30 days
        "detect_attached_unused": True,  # Also detect attached volumes with no I/O activity
        "min_idle_days_attached": 30,  # Min days of no I/O for attached volumes
        "description": "Unattached EBS volumes and attached volumes with no I/O activity",
    },
    "elastic_ip": {
        "enabled": True,
        "min_age_days": 3,  # Ignore IPs allocated in last 3 days
        "confidence_threshold_days": 7,
        "description": "Unassociated Elastic IP addresses",
    },
    "ebs_snapshot": {
        "enabled": True,
        "min_age_days": 90,  # Snapshots older than 90 days
        "require_orphaned_volume": True,  # Volume must be deleted
        "detect_idle_volume_snapshots": True,  # Also detect snapshots of idle/orphaned volumes
        "detect_redundant_snapshots": True,  # Detect redundant snapshots (too many per volume)
        "max_snapshots_per_volume": 7,  # Keep only N most recent snapshots per volume
        "detect_unused_ami_snapshots": True,  # Detect snapshots of unused AMIs
        "min_ami_unused_days": 180,  # AMI unused for 180+ days
        "confidence_threshold_days": 180,
        "description": "Orphaned, redundant, and unused AMI snapshots",
    },
    "ec2_instance": {
        "enabled": True,
        "min_stopped_days": 30,  # Stopped for > 30 days
        "confidence_threshold_days": 60,
        # Idle running instances detection
        "detect_idle_running": True,  # Also detect running instances with low utilization
        "cpu_threshold_percent": 5.0,  # Average CPU < 5% = idle
        "network_threshold_bytes": 1_000_000,  # < 1MB network traffic in lookback period = idle
        "min_idle_days": 7,  # Running instances must be idle for at least 7 days to be detected
        "idle_confidence_threshold_days": 30,  # High confidence after 30 days idle
        "description": "EC2 instances stopped for extended periods or running with very low utilization",
    },
    "nat_gateway": {
        "enabled": True,
        "max_bytes_30d": 1_000_000,  # < 1MB traffic in 30 days
        "min_age_days": 7,
        "confidence_threshold_days": 30,
        "critical_age_days": 90,  # Critical alert after 90 days unused
        "detect_no_routes": True,  # Detect NAT GW not referenced in route tables
        "detect_no_igw": True,  # Detect NAT GW in VPC without Internet Gateway
        "description": "NAT Gateways with no traffic, no routing, or misconfigured",
    },
    "load_balancer": {
        "enabled": True,
        "require_zero_healthy_targets": True,
        "min_age_days": 7,
        "confidence_threshold_days": 30,
        "critical_age_days": 90,  # Critical alert after 90 days with no backends
        "detect_no_listeners": True,  # Detect LB without listeners
        "detect_zero_requests": True,  # Detect LB with no requests (CloudWatch)
        "min_requests_30d": 100,  # Minimum requests in 30 days (ALB/CLB)
        "detect_no_target_groups": True,  # Detect LB without any target groups
        "detect_never_used": True,  # Detect LB never used since creation
        "never_used_min_age_days": 30,  # Min age to consider "never used"
        "detect_unhealthy_long_term": True,  # Detect LB with all unhealthy targets >90d
        "unhealthy_long_term_days": 90,  # Days to consider long-term unhealthy
        "detect_sg_blocks_traffic": True,  # Detect LB with SG blocking all traffic
        "description": "Load balancers with no healthy backends, no listeners, no traffic, no target groups, security group issues, or never used",
    },
    "rds_instance": {
        "enabled": True,
        "min_stopped_days": 7,  # RDS auto-starts after 7 days
        "confidence_threshold_days": 14,
        "critical_age_days": 30,  # Critical after 30+ days stopped
        # Idle running instances detection
        "detect_idle_running": True,  # Detect running instances with 0 connections
        "min_idle_days": 7,  # Running with 0 connections for 7+ days
        "idle_confidence_threshold_days": 14,  # High confidence after 14 days
        # Zero I/O detection
        "detect_zero_io": True,  # Detect instances with no read/write operations
        "min_zero_io_days": 7,  # No I/O for 7+ days
        # Never connected detection
        "detect_never_connected": True,  # Detect instances never connected since creation
        "never_connected_min_age_days": 7,  # Min age to consider "never connected"
        # No backups detection
        "detect_no_backups": True,  # Detect instances without automated backups
        "no_backups_min_age_days": 30,  # Min age for no-backup detection
        "description": "RDS instances stopped long-term, idle running (0 connections), zero I/O, never connected, or without backups",
    },
    # TOP 15 high-cost idle resources
    "fsx_file_system": {
        "enabled": True,
        "min_age_days": 3,  # Ignore file systems created in last 3 days
        "confidence_threshold_days": 30,  # High confidence after 30 days
        # Scenario 1: Completely inactive (0 read/write transfers)
        "detect_inactive": True,
        "inactive_lookback_days": 30,  # Check last 30 days for activity
        # Scenario 2: Over-provisioned storage (<10% storage used)
        "detect_over_provisioned_storage": True,
        "storage_usage_threshold_percent": 10.0,  # < 10% storage used = over-provisioned
        "storage_lookback_days": 7,  # Check last 7 days of storage metrics
        # Scenario 3: Over-provisioned throughput (<10% throughput utilized)
        "detect_over_provisioned_throughput": True,
        "throughput_utilization_threshold_percent": 10.0,  # < 10% throughput = over-provisioned
        "throughput_lookback_days": 7,  # Check last 7 days of throughput metrics
        # Scenario 4: Excessive backup retention (orphaned backups)
        "detect_excessive_backups": True,
        "max_backup_retention_days": 30,  # Backups > 30 days = excessive
        "detect_orphaned_backups": True,  # Detect backups with deleted source file system
        # Scenario 5: Unused file shares (Windows: 0 SMB connections)
        "detect_unused_file_shares": True,  # FSx Windows only
        "min_zero_connections_days": 7,  # 0 SMB connections for 7+ days
        # Scenario 6: Low IOPS utilization (<10% IOPS used)
        "detect_low_iops_utilization": True,  # Windows/ONTAP only
        "iops_utilization_threshold_percent": 10.0,  # < 10% IOPS utilized
        "iops_lookback_days": 7,  # Check last 7 days
        # Scenario 7: Multi-AZ overkill (Multi-AZ in dev/test environments)
        "detect_multi_az_overkill": True,  # Detect Multi-AZ when Single-AZ sufficient
        "multi_az_tag_key": "Environment",  # Tag key to check (e.g., "dev", "test")
        "multi_az_tag_values": ["dev", "test", "development", "testing"],  # Tag values indicating non-prod
        # Scenario 8: Wrong storage type (SSD for archive workloads)
        "detect_ssd_for_archive": True,  # Windows only (HDD available)
        "archive_throughput_threshold_mbps": 8.0,  # < 8 MB/s avg throughput = archive workload
        "description": "FSx file systems: inactive, over-provisioned storage/throughput, excessive backups, unused file shares (Windows), low IOPS, Multi-AZ overkill, wrong storage type",
    },
    "neptune_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Neptune clusters with no active connections",
    },
    "msk_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "MSK clusters with no data traffic",
    },
    "eks_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "critical_age_days": 30,  # Critical after 30+ days unused
        # No worker nodes detection
        "detect_no_nodes": True,  # Detect clusters with 0 nodes
        # Unhealthy nodes detection
        "detect_unhealthy_nodes": True,  # Detect clusters with all nodes unhealthy
        "min_unhealthy_days": 7,  # Nodes unhealthy for 7+ days
        # Low utilization detection
        "detect_low_utilization": True,  # Detect clusters with low CPU on all nodes
        "cpu_threshold_percent": 5.0,  # Average CPU < 5% = idle
        "min_idle_days": 7,  # Low utilization for 7+ days
        "idle_lookback_days": 7,  # CloudWatch lookback period
        # Fargate detection
        "detect_fargate_no_profiles": True,  # Detect Fargate-only clusters with no profiles
        # Version detection
        "detect_outdated_version": True,  # Detect outdated Kubernetes versions
        "min_supported_minor_versions": 3,  # Min 3 versions behind latest (e.g., 1.25 if latest is 1.28)
        "description": "EKS clusters: no nodes, unhealthy nodes, low CPU utilization, Fargate misconfigured, or outdated K8s version",
    },
    "sagemaker_endpoint": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "SageMaker endpoints with no invocations",
    },
    "redshift_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Redshift clusters with no database connections",
    },
    "elasticache_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        # PRIORITY 1: Zero cache hits
        "detect_zero_cache_hits": True,
        "zero_hits_lookback_days": 7,
        # PRIORITY 2: Low hit rate
        "detect_low_hit_rate": True,
        "hit_rate_threshold": 50.0,  # < 50% = inefficient cache
        "critical_hit_rate": 10.0,  # < 10% = useless cache
        "hit_rate_lookback_days": 7,
        # PRIORITY 3: No connections
        "detect_no_connections": True,
        "no_connections_lookback_days": 7,
        # PRIORITY 4: Over-provisioned memory
        "detect_over_provisioned_memory": True,
        "memory_usage_threshold": 20.0,  # < 20% memory used = over-provisioned
        "memory_lookback_days": 7,
        "description": "ElastiCache clusters: zero cache hits, low hit rate, no connections, or over-provisioned memory",
    },
    "vpn_connection": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 30,
        "description": "VPN connections with no data transfer",
    },
    "transit_gateway_attachment": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 30,
        "description": "Transit Gateway attachments with no traffic",
    },
    "opensearch_domain": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "OpenSearch domains with no search requests",
    },
    "global_accelerator": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Global Accelerators with no endpoints",
    },
    "kinesis_stream": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        # Scenario 1: Completely inactive (0 writes, 0 reads)
        "detect_inactive": True,
        "inactive_lookback_days": 7,
        # Scenario 2: Written but never read
        "detect_written_not_read": True,
        "written_not_read_lookback_days": 7,
        # Scenario 3: Under-utilized (< 1% capacity)
        "detect_underutilized": True,
        "utilization_threshold_percent": 1.0,
        "underutilized_lookback_days": 7,
        # Scenario 4: Excessive retention
        "detect_excessive_retention": True,
        "max_iterator_age_ms": 60000,  # 1 minute
        # Scenario 5: Unused Enhanced Fan-Out
        "detect_unused_enhanced_fanout": True,
        # Scenario 6: Over-provisioned shards
        "detect_overprovisioned": True,
        "overprovisioning_ratio": 10.0,
        "description": "Kinesis streams: inactive, under-utilized, excessive retention, or orphaned consumers",
    },
    "vpc_endpoint": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "VPC endpoints with no network interfaces",
    },
    "documentdb_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "DocumentDB clusters with no database connections",
    },
    "s3_bucket": {
        "enabled": True,
        "min_bucket_age_days": 1,  # TEMPORAIRE: Minimum bucket age before flagging (ORIGINAL: 90)
        "confidence_threshold_days": 180,
        # Empty bucket detection
        "detect_empty": True,  # Detect buckets with 0 objects
        # Old objects detection
        "detect_old_objects": True,  # Detect buckets where ALL objects are very old
        "object_age_threshold_days": 1,  # TEMPORAIRE: All objects > 1 days old (ORIGINAL: 365)
        # Incomplete multipart uploads detection
        "detect_multipart_uploads": True,  # Detect incomplete multipart uploads
        "multipart_age_days": 1,  # TEMPORAIRE: Incomplete uploads > 1 days old (ORIGINAL: 30)
        # No lifecycle policy detection
        "detect_no_lifecycle": True,  # Detect buckets without lifecycle policies + old objects
        "lifecycle_age_threshold_days": 1,  # TEMPORAIRE: Buckets with objects > 1 days + no lifecycle (ORIGINAL: 180)
        "description": "S3 buckets: empty, old objects, incomplete multipart uploads, no lifecycle policy",
    },
    "lambda_function": {
        "enabled": True,
        "min_age_days": 30,  # Minimum age before flagging as orphan
        "confidence_threshold_days": 60,  # High confidence after 60 days
        "critical_age_days": 180,  # Critical alert after 180 days
        # Provisioned concurrency detection (HIGHEST PRIORITY - very expensive)
        "detect_unused_provisioned_concurrency": True,  # Detect provisioned concurrency with 0 usage
        "provisioned_min_age_days": 30,  # Min days with provisioned concurrency unused
        "provisioned_critical_days": 90,  # Critical after 90 days unused
        "provisioned_utilization_threshold": 1.0,  # < 1% utilization = unused (0.01 = 1%)
        # Never invoked detection
        "detect_never_invoked": True,  # Detect functions never invoked since creation
        "never_invoked_min_age_days": 30,  # Min age to consider "never invoked"
        "never_invoked_confidence_days": 60,  # High confidence after 60 days
        # Zero invocations detection
        "detect_zero_invocations": True,  # Detect functions with 0 invocations in lookback period
        "zero_invocations_lookback_days": 90,  # Check last 90 days
        "zero_invocations_confidence_days": 180,  # High confidence after 180 days
        # Failed invocations detection (100% errors = dead function)
        "detect_all_failures": True,  # Detect functions with 100% error rate
        "failure_rate_threshold": 95.0,  # > 95% errors = dead function
        "min_invocations_for_failure_check": 10,  # Minimum invocations to avoid false positives
        "failure_lookback_days": 30,  # Check last 30 days
        "description": "Lambda functions: unused provisioned concurrency, never invoked, zero invocations, or 100% failures",
    },
    "dynamodb_table": {
        "enabled": True,
        "min_age_days": 7,  # Ignore tables created in last 7 days
        "confidence_threshold_days": 30,  # High confidence after 30 days
        "critical_age_days": 90,  # Critical alert after 90 days
        # PRIORITY 1: Over-provisioned capacity (VERY EXPENSIVE)
        "detect_over_provisioned": True,  # Detect tables with unused provisioned capacity
        "provisioned_utilization_threshold": 10.0,  # < 10% utilization = waste
        "provisioned_lookback_days": 7,  # Check last 7 days of usage
        # PRIORITY 2: Unused Global Secondary Indexes
        "detect_unused_gsi": True,  # Detect GSI never queried
        "gsi_lookback_days": 14,  # GSI unused for 14+ days
        # PRIORITY 3: Never used tables (Provisioned mode)
        "detect_never_used_provisioned": True,  # Detect provisioned tables with 0 usage
        "never_used_min_age_days": 30,  # Min age to consider "never used"
        # PRIORITY 4: Never used tables (On-Demand mode)
        "detect_never_used_ondemand": True,  # Detect on-demand tables with 0 usage
        "ondemand_lookback_days": 60,  # Check last 60 days
        # PRIORITY 5: Empty tables
        "detect_empty_tables": True,  # Detect tables with 0 items
        "empty_table_min_age_days": 90,  # Empty for 90+ days
        "description": "DynamoDB tables: over-provisioned capacity, unused GSI, never used (provisioned/on-demand), or empty tables",
    },
    # ===================================
    # AZURE RESOURCES (Managed by Azure)
    # ===================================
    "managed_disk_unattached": {
        "enabled": True,
        "min_age_days": 7,  # Ignore disks created in last 7 days
        "confidence_threshold_days": 30,  # High confidence after 30 days
        "description": "Unattached Azure Managed Disks (Standard HDD/SSD, Premium SSD, Ultra SSD)",
    },
    "public_ip_unassociated": {
        "enabled": True,
        "min_age_days": 3,  # Ignore IPs allocated in last 3 days
        "confidence_threshold_days": 7,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Unassociated Azure Public IP addresses (not attached to any resource)",
    },
    "public_ip_on_stopped_resource": {
        "enabled": True,
        "min_stopped_days": 30,  # Resource stopped/deallocated for > 30 days
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Public IP addresses attached to stopped/deallocated resources (VMs, Load Balancers with no backends)",
    },
    "public_ip_dynamic_unassociated": {
        "enabled": True,
        "min_age_days": 3,  # Ignore IPs allocated in last 3 days
        "confidence_critical_days": 30,  # Critical after 30 days (anomaly - should be auto-deallocated)
        "confidence_high_days": 14,  # High confidence after 14 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Dynamic Public IPs stuck in provisioned state (anomaly - should be auto-deallocated when unassociated)",
    },
    "public_ip_unnecessary_standard_sku": {
        "enabled": True,
        "min_age_days": 7,  # Ignore IPs allocated in last 7 days
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Standard SKU Public IPs used in dev/test environments (Basic SKU would suffice until Sept 2025 retirement)",
    },
    "public_ip_unnecessary_zone_redundancy": {
        "enabled": True,
        "min_age_days": 7,  # Ignore IPs allocated in last 7 days
        "min_zones": 3,  # Flag IPs with 3+ zones
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Zone-redundant Public IPs (3+ zones) without high-availability requirements (saves $0.65/month per IP)",
    },
    "public_ip_ddos_protection_unused": {
        "enabled": True,
        "lookback_days": 90,  # Check DDoS attack history over last 90 days
        "confidence_critical_days": 180,  # Critical after 180 days (HIGH VALUE - $2,944/month + $30/IP)
        "confidence_high_days": 90,  # High confidence after 90 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "DDoS Protection Standard that has never been triggered (HIGH VALUE: $2,944/month subscription + $30/IP)",
    },
    "public_ip_on_nic_without_vm": {
        "enabled": True,
        "min_age_days": 7,  # Ignore NICs created in last 7 days
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Public IPs attached to orphaned Network Interfaces (NICs without VMs)",
    },
    "public_ip_reserved_but_unused": {
        "enabled": True,
        "min_age_days": 3,  # Ignore IPs allocated in last 3 days
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Reserved Public IPs that have never been assigned an actual IP address (misconfigured)",
    },
    "public_ip_no_traffic": {
        "enabled": True,
        "lookback_days": 30,  # Check traffic over last 30 days
        "confidence_critical_days": 90,  # Critical after 90 days of zero traffic
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Public IPs with zero network traffic (ByteCount=0, PacketCount=0) over lookback period",
    },
    "public_ip_very_low_traffic": {
        "enabled": True,
        "lookback_days": 30,  # Check traffic over last 30 days
        "traffic_threshold_gb": 1.0,  # Flag IPs with <1 GB/month traffic
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Public IPs with very low network traffic (<1 GB/month) suggesting over-provisioning",
    },
    "disk_snapshot_orphaned": {
        "enabled": True,
        "min_age_days": 90,  # Snapshots older than 90 days
        "confidence_threshold_days": 180,
        "confidence_critical_days": 180,  # Critical after 180 days
        "confidence_high_days": 90,  # High confidence after 90 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Orphaned Azure Disk Snapshots (source disk deleted)",
    },
    "managed_disk_on_stopped_vm": {
        "enabled": True,
        "min_stopped_days": 30,  # VM deallocated for > 30 days
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Managed Disks (OS + Data) attached to VMs deallocated for extended periods",
    },
    "disk_snapshot_redundant": {
        "enabled": True,
        "min_age_days": 90,  # Snapshots older than 90 days
        "max_snapshots_per_disk": 3,  # Keep only N most recent snapshots per source disk
        "confidence_threshold_days": 180,
        "confidence_critical_days": 180,  # Critical after 180 days
        "confidence_high_days": 90,  # High confidence after 90 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Redundant Disk Snapshots (>3 snapshots for same source disk)",
    },
    "managed_disk_unnecessary_zrs": {
        "enabled": True,
        "min_age_days": 30,  # Ignore disks created in last 30 days
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Zone-Redundant Storage (ZRS) disks in dev/test environments (unnecessary redundancy)",
    },
    "managed_disk_unnecessary_cmk": {
        "enabled": True,
        "min_age_days": 30,  # Ignore disks created in last 30 days
        "compliance_tags": ["compliance", "hipaa", "pci", "sox", "gdpr", "regulated", "Compliance", "HIPAA", "PCI", "SOX", "GDPR"],
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Customer-Managed Key (CMK) encryption without compliance requirements (~8% cost overhead)",
    },
    "managed_disk_idle": {
        "enabled": True,
        "min_idle_days": 60,  # Observation period (Azure Monitor metrics)
        "max_iops_threshold": 0.1,  # Average IOPS < 0.1 = idle
        "confidence_threshold_days": 90,
        "confidence_critical_days": 120,  # Critical after 120 days idle
        "confidence_high_days": 60,  # High confidence after 60 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Attached disks with zero I/O activity (0 read/write IOPS over observation period) - Requires Azure Monitor",
    },
    "managed_disk_unused_bursting": {
        "enabled": True,
        "min_observation_days": 30,  # Azure Monitor lookback period
        "max_burst_usage_percent": 0.01,  # < 0.01% burst credits used = unused
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Premium SSD disks with bursting enabled but never used (~15% cost overhead) - Requires Azure Monitor",
    },
    "managed_disk_overprovisioned": {
        "enabled": True,
        "min_observation_days": 30,  # Azure Monitor lookback period
        "max_utilization_percent": 30,  # < 30% IOPS/Bandwidth utilization = over-provisioned
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Premium SSD disks over-provisioned (performance tier too high for actual usage) - Requires Azure Monitor",
    },
    "managed_disk_underutilized_hdd": {
        "enabled": True,
        "min_observation_days": 30,  # Azure Monitor lookback period
        "max_iops_threshold": 100,  # Average IOPS < 100 for HDD = under-utilized
        "min_disk_size_gb": 256,  # Minimum size to consider as \"large\" HDD
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        "description": "Large Standard HDD disks under-utilized (should migrate to smaller Standard SSD) - Requires Azure Monitor",
    },
    "virtual_machine_deallocated": {
        "enabled": True,
        "min_stopped_days": 30,  # Deallocated for > 30 days
        "confidence_threshold_days": 60,
        "description": "Azure VMs deallocated for extended periods",
    },
    "azure_aks_cluster": {
        "enabled": True,
        "min_age_days": 7,  # Ignore clusters created in last 7 days
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 30,  # High confidence after 30 days
        "confidence_medium_days": 7,  # Medium confidence after 7 days
        # Scenario detection flags
        "detect_stopped": True,  # Cluster stopped but not deleted
        "detect_zero_nodes": True,  # Cluster with 0 nodes
        "detect_no_user_pods": True,  # No user pods (only kube-system)
        "detect_autoscaler_not_enabled": True,  # No autoscaling configured
        "detect_oversized_vms": True,  # VMs too large for workload
        "detect_orphaned_pvs": True,  # Orphaned PersistentVolumes
        "detect_unused_load_balancers": True,  # LoadBalancer services with 0 backends
        "detect_low_cpu": True,  # CPU <20% over 30 days
        "detect_low_memory": True,  # Memory <30% over 30 days
        "detect_dev_test_always_on": True,  # Dev/test clusters running 24/7
        # Thresholds
        "cpu_threshold": 20,  # CPU < 20% = low utilization
        "memory_threshold": 30,  # Memory < 30% = low utilization
        "monitoring_period_days": 30,  # Azure Monitor lookback period
        "description": "Azure Kubernetes Service (AKS) clusters: stopped, zero nodes, no user pods, no autoscaler, oversized VMs, orphaned PVs, unused LBs, low CPU/memory, or dev/test always on",
    },
}


class DetectionRule(Base):
    """User-specific detection rule configuration."""

    __tablename__ = "detection_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'ebs_volume', 'elastic_ip', 'ebs_snapshot', etc.

    # Custom rules (JSONB for flexibility)
    # Example: {"enabled": true, "min_age_days": 14, "confidence_threshold_days": 45}
    rules: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="detection_rules")  # type: ignore

    def __repr__(self) -> str:
        """String representation."""
        return f"<DetectionRule {self.resource_type} for user {self.user_id}>"
