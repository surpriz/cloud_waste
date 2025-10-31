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
        # SCENARIO 1: Unattached volumes
        "min_age_days": 7,  # Ignore volumes created in last 7 days
        "confidence_threshold_days": 30,  # High confidence after 30 days
        "detect_attached_unused": True,  # Also detect attached volumes with no I/O activity
        "min_idle_days_attached": 30,  # Min days of no I/O for attached volumes

        # SCENARIO 2: Volumes on stopped instances
        "min_stopped_days": 30,  # Instance must be stopped for 30+ days

        # SCENARIO 3: gp2 → gp3 migration recommendation
        "min_size_gb": 100,  # Minimum volume size for migration recommendation (small volumes = marginal savings)

        # SCENARIO 4: Unnecessary io2 volumes
        "compliance_tags": [
            "compliance", "hipaa", "pci-dss", "sox", "gdpr", "iso27001",
            "critical", "production-critical", "high-availability"
        ],  # Tags that justify io2 durability (99.999%)

        # SCENARIO 5: Overprovisioned IOPS
        "iops_overprovisioning_factor": 2.0,  # Flag if provisioned IOPS > baseline × 2

        # SCENARIO 6: Overprovisioned throughput
        "baseline_throughput_mbps": 125,  # gp3 baseline throughput (free)
        "high_throughput_workload_tags": [
            "database", "analytics", "bigdata", "ml", "etl", "data-warehouse"
        ],  # Workloads that justify high throughput

        # SCENARIO 7: Idle volumes (CloudWatch - already partially implemented)
        "min_idle_days": 60,  # Observation period for idle detection
        "max_ops_threshold": 0.1,  # ops/sec - consider idle if < 0.1 ops/sec

        # SCENARIO 8: Low IOPS usage
        "max_iops_utilization_percent": 30,  # Flag if IOPS utilization < 30%
        "safety_buffer_factor": 1.5,  # Recommended IOPS = avg × 1.5 (safety margin)
        "min_observation_days": 30,  # CloudWatch observation period

        # SCENARIO 9: Low throughput usage
        "max_throughput_utilization_percent": 30,  # Flag if throughput utilization < 30%

        # SCENARIO 10: Volume type downgrade opportunities
        "min_savings_percent": 20,  # Only recommend downgrade if savings ≥ 20%
        "safety_margin_iops": 1.5,  # Ensure downgraded type can handle avg_iops × 1.5

        "description": "EBS volumes - 10 waste scenarios: unattached, stopped instances, gp2→gp3 migration, unnecessary io2, overprovisioned IOPS/throughput, idle, low IOPS/throughput usage, type downgrade opportunities",
    },
    "elastic_ip": {
        "enabled": True,

        # SCENARIO 1: Unassociated Elastic IPs
        "min_age_days": 3,  # Ignore IPs allocated in last 3 days
        "confidence_threshold_days": 7,  # High confidence after 7 days

        # SCENARIO 2: EIPs on stopped EC2 instances
        "min_stopped_days": 30,  # Instance must be stopped for 30+ days

        # SCENARIO 3: Multiple EIPs per instance
        "max_eips_per_instance": 1,  # Flag instances with more than 1 EIP
        "allow_multiple_eips_tags": [
            "multi-nic", "ha", "high-availability", "active-active",
            "failover", "floating-ip"
        ],  # Tags that justify multiple EIPs

        # SCENARIO 4: EIPs on detached ENIs
        "detached_eni_min_days": 7,  # ENI must be detached for 7+ days

        # SCENARIO 5: Never-used EIPs
        "min_never_used_days": 7,  # EIP never attached since allocation for 7+ days

        # SCENARIO 6: EIPs on unused NAT Gateways
        "nat_gateway_min_idle_days": 30,  # NAT Gateway must be idle for 30+ days
        "nat_gateway_traffic_threshold_gb": 0.1,  # < 0.1 GB/month = unused

        # SCENARIO 7: Idle EIPs (CloudWatch)
        "min_idle_days": 30,  # Active resource must be idle for 30+ days
        "idle_network_threshold_bytes": 1_000_000,  # < 1MB in lookback = idle
        "min_observation_days": 30,  # CloudWatch observation period

        # SCENARIO 8: Low-traffic EIPs
        "low_traffic_threshold_gb": 1.0,  # < 1 GB/month for 30 days

        # SCENARIO 9: EIPs on unused NAT Gateways (advanced CloudWatch)
        "nat_gateway_zero_connections_days": 30,  # NAT with zero connections for 30+ days

        # SCENARIO 10: EIPs on failed instances
        "max_status_check_failures": 7,  # Consecutive days of status check failures
        "min_failed_days": 7,  # Instance failing for 7+ days

        "description": "Elastic IP addresses - 10 waste scenarios: unassociated, stopped instances, multiple EIPs per instance, detached ENIs, never-used, unused NAT Gateways, idle resources, low traffic, zero NAT connections, failed instances",
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
        # Scenario 3: Old unused snapshots
        "detect_old_unused": True,  # Detect very old snapshots without compliance tags
        "old_unused_age_days": 365,  # Snapshots >365 days without compliance tags
        "compliance_tags": ["Backup", "Compliance", "Governance", "Retention", "Legal"],  # Tags indicating intentional retention
        # Scenario 4: Snapshots from deleted instances
        "detect_deleted_instance_snapshots": True,  # Detect snapshots with instance IDs in description where instance no longer exists
        # Scenario 5: Incomplete/failed snapshots
        "detect_incomplete_failed": True,  # Detect snapshots in error or pending state
        "max_pending_days": 7,  # Maximum days a snapshot can be in pending state
        # Scenario 6: Untagged snapshots
        "detect_untagged": True,  # Detect snapshots with no tags (likely abandoned)
        "min_untagged_age_days": 30,  # Snapshots must be >30 days old to be flagged as untagged
        # Scenario 8: Excessive retention in non-prod
        "detect_excessive_retention": True,  # Detect snapshots retained too long in non-prod environments
        "nonprod_max_days": 90,  # Max retention for dev/test/staging environments
        "nonprod_env_tags": ["Environment", "Env", "Stage"],  # Tags that indicate environment
        "nonprod_env_values": ["dev", "development", "test", "testing", "stage", "staging", "qa"],  # Values indicating non-prod
        # Scenario 9: Duplicate snapshots
        "detect_duplicates": True,  # Detect duplicate snapshots (same volume + size within short time window)
        "duplicate_window_hours": 1,  # Time window to detect duplicates (snapshots of same volume within N hours)
        "confidence_threshold_days": 180,
        "description": "EBS Snapshots - 10 waste scenarios: orphaned volumes, redundant backups, old unused, deleted instances, incomplete/failed, untagged, never restored (CloudTrail), excessive retention, duplicates, unused AMIs",
    },
    "ec2_instance": {
        "enabled": True,
        # Scenario 1: Stopped instances
        "min_stopped_days": 30,  # Stopped for > 30 days
        "confidence_threshold_days": 60,
        # Scenario 7: Idle running instances detection
        "detect_idle_running": True,  # Also detect running instances with low utilization
        "cpu_threshold_percent": 5.0,  # Average CPU < 5% = idle
        "network_threshold_bytes": 1_000_000,  # < 1MB network traffic in lookback period = idle
        "min_idle_days": 7,  # Running instances must be idle for at least 7 days to be detected
        "idle_confidence_threshold_days": 30,  # High confidence after 30 days idle
        # Scenario 2: Over-provisioned instances
        "detect_oversized": True,  # Detect over-provisioned instances
        "oversized_cpu_threshold": 30.0,  # Average CPU <30% = over-provisioned
        "oversized_lookback_days": 30,  # Analyze last 30 days
        "oversized_min_instance_size": "xlarge",  # Only check xlarge+ instances
        # Scenario 3: Old generation instances
        "detect_old_generation": True,  # Detect obsolete instance types
        "old_generations": ["t2", "m4", "c4", "r4", "i3", "x1", "p2", "g3"],  # Obsolete families
        "generation_mapping": {
            "t2": "t3", "m4": "m5", "c4": "c5", "r4": "r5",
            "i3": "i3en", "x1": "x2idn", "p2": "p3", "g3": "g4dn"
        },  # Old → New mapping
        # Scenario 4: Burstable credit waste (T2/T3/T4)
        "detect_burstable_waste": True,  # Detect T2/T3/T4 credit waste
        "burstable_credit_threshold": 0.9,  # Credit balance >90% of max = waste
        "burstable_lookback_days": 30,  # Analyze last 30 days
        "detect_unlimited_charges": True,  # Detect Unlimited mode charges
        # Scenario 5: Dev/Test running 24/7
        "detect_dev_test_24_7": True,  # Detect non-prod running 24/7
        "nonprod_env_tags": ["Environment", "Env", "Stage"],  # Tags indicating environment
        "nonprod_env_values": ["dev", "development", "test", "testing", "stage", "staging", "qa", "sandbox"],  # Non-prod values
        "nonprod_min_age_days": 7,  # Running for >7 days
        # Scenario 6: Untagged instances
        "detect_untagged": True,  # Detect instances without tags
        "untagged_min_age_days": 30,  # >30 days old
        # Scenario 8: Right-sizing opportunities (advanced)
        "detect_right_sizing": True,  # Advanced right-sizing analysis
        "right_sizing_cpu_threshold": 40.0,  # CPU <40% = potential right-sizing
        "right_sizing_max_cpu_threshold": 75.0,  # Max CPU must be <75% to recommend downsize
        "right_sizing_lookback_days": 30,  # Analyze last 30 days
        # Scenario 9: Spot-eligible workloads
        "detect_spot_eligible": True,  # Detect Spot-compatible workloads
        "spot_cpu_variance_threshold": 20.0,  # CPU variance <20% = stable workload
        "spot_min_uptime_days": 7,  # Running for >7 days
        "spot_excluded_types": ["database", "cache", "queue"],  # Exclude critical workloads
        # Scenario 10: Scheduled unused (business hours only)
        "detect_scheduled_unused": True,  # Detect usage only during business hours
        "business_hours_start": 9,  # 9 AM
        "business_hours_end": 18,  # 6 PM
        "business_days": [0, 1, 2, 3, 4],  # Monday-Friday (0=Monday)
        "scheduled_cpu_threshold": 10.0,  # CPU <10% outside business hours
        "scheduled_lookback_days": 14,  # Analyze last 14 days
        "description": "EC2 Instances - 10 waste scenarios: stopped >30d, oversized, old generation, burstable credit waste, dev/test 24/7, untagged, idle, right-sizing, Spot-eligible, scheduled unused",
    },
    # Azure NAT Gateway - 10 Waste Detection Scenarios
    "nat_gateway_no_subnet": {
        "enabled": True,
        "min_age_days": 7,
        "description": "Azure NAT Gateways without any subnets attached ($32.40/month waste)",
    },
    "nat_gateway_never_used": {
        "enabled": True,
        "min_age_days": 7,
        "description": "Azure NAT Gateways with subnets but no VMs using them ($32.40/month waste)",
    },
    "nat_gateway_no_public_ip": {
        "enabled": True,
        "min_age_days": 3,
        "description": "Azure NAT Gateways without Public IP addresses attached ($32.40/month waste)",
    },
    "nat_gateway_single_vm": {
        "enabled": True,
        "min_age_days": 14,
        "description": "Azure NAT Gateways used by only a single VM - Standard Public IP more cost-effective ($28.75/month savings)",
    },
    "nat_gateway_redundant": {
        "enabled": True,
        "min_age_days": 14,
        "description": "Multiple NAT Gateways in same VNet - typically only one needed ($32.40/month per redundant gateway)",
    },
    "nat_gateway_dev_test_always_on": {
        "enabled": True,
        "min_age_days": 7,
        "business_hours_per_week": 40,  # 8 hours/day × 5 days/week
        "description": "Dev/Test NAT Gateways running 24/7 instead of business hours only ($24.70/month savings)",
    },
    "nat_gateway_unnecessary_zones": {
        "enabled": True,
        "min_age_days": 14,
        "description": "Multi-zone NAT Gateways when VMs use single zone ($0.50/month savings)",
    },
    "nat_gateway_no_traffic": {
        "enabled": True,
        "min_age_days": 7,
        "monitoring_days": 30,
        "description": "NAT Gateways with zero traffic over 30 days (Azure Monitor metrics) ($32.40/month waste)",
    },
    "nat_gateway_very_low_traffic": {
        "enabled": True,
        "min_age_days": 14,
        "monitoring_days": 30,
        "max_gb_per_month": 10,  # < 10 GB/month = use Public IP instead
        "description": "NAT Gateways with very low traffic (<10 GB/month) - Standard Public IP more cost-effective ($28-29/month savings)",
    },
    "nat_gateway_private_link_alternative": {
        "enabled": True,
        "min_age_days": 30,
        "description": "NAT Gateways for Azure services traffic - Private Link/Service Endpoints eliminate need ($32.40/month savings)",
    },
    # AWS NAT Gateway - 10 Waste Detection Scenarios (Phase 1: 7 scenarios, Phase 2: 3 scenarios)
    "nat_gateway": {
        "enabled": True,
        "min_age_days": 7,  # Minimum age before flagging (avoid false positives during setup)
        "confidence_threshold_days": 30,  # High confidence after 30 days
        "critical_age_days": 90,  # Critical alert after 90 days unused

        # Scenario 1: No route tables reference
        "detect_no_routes": True,  # Detect NAT GW not referenced in any route table

        # Scenario 2 & 7: Traffic-based detection
        "max_bytes_30d": 1_000_000,  # < 1 MB = zero traffic (Scenario 2)
        "low_traffic_threshold_gb": 10.0,  # < 10 GB/month = low traffic (Scenario 7)

        # Scenario 3: Routes not associated with subnets
        "detect_unassociated_routes": True,  # Route tables without subnet associations

        # Scenario 4: VPC without Internet Gateway
        "detect_no_igw": True,  # NAT GW in VPC without IGW (broken config)

        # Scenario 5: NAT Gateway in public subnet (Phase 1 - NEW)
        "detect_public_subnet": True,  # NAT GW in subnet with route to IGW

        # Scenario 6: Redundant NAT Gateways in same AZ (Phase 1 - NEW)
        "detect_redundant_same_az": True,  # Multiple NAT GW in same VPC+AZ

        # Scenario 8: VPC Endpoint candidates (simplified MVP version without VPC Flow Logs)
        "detect_vpc_endpoint_candidates": True,  # Recommend VPC Endpoints for S3/DynamoDB
        "vpc_endpoint_traffic_threshold_gb": 50.0,  # Only recommend if traffic <50 GB (low enough for savings)
        "detect_missing_s3_endpoint": True,  # Flag if S3 VPC Endpoint missing
        "detect_missing_dynamodb_endpoint": True,  # Flag if DynamoDB VPC Endpoint missing

        # Scenario 9: Dev/Test unused hours (CloudWatch hourly pattern)
        "detect_dev_test_unused_hours": True,  # Analyze hourly traffic patterns for dev/test NAT GW
        "business_hours_start": 8,  # 8 AM
        "business_hours_end": 18,  # 6 PM
        "business_days": [0, 1, 2, 3, 4],  # Monday-Friday (0=Monday)
        "business_hours_traffic_threshold": 90.0,  # >90% traffic during business hours = scheduling candidate
        "dev_test_pattern_lookback_days": 7,  # Analyze last 7 days of hourly patterns
        "nonprod_env_tags": ["Environment", "Env", "Stage"],  # Tags to check
        "nonprod_env_values": ["dev", "development", "test", "testing", "staging", "qa"],  # Non-prod values

        # Scenario 10: Obsolete after migration (CloudWatch trend analysis)
        "detect_obsolete_migration": True,  # Detect NAT GW with traffic drop >90%
        "traffic_drop_threshold_percent": 90.0,  # >90% traffic drop = likely obsolete
        "migration_baseline_days": 90,  # Compare J-90 to J-60 (baseline) vs J-7 to J-0 (current)
        "migration_min_age_days": 90,  # Only analyze NAT GW older than 90 days

        "description": "AWS NAT Gateways - 10 waste scenarios (100% coverage): no routes, zero traffic, unassociated routes, no IGW, public subnet, redundant same AZ, low traffic, VPC Endpoint candidates, dev/test business hours, obsolete after migration",
    },
    # Azure Load Balancer & Application Gateway - 10 Waste Detection Scenarios
    "load_balancer_no_backend_instances": {
        "enabled": True,
        "min_age_days": 7,
        "description": "Azure Load Balancers with no backend instances ($18.25/month Standard waste)",
    },
    "load_balancer_all_backends_unhealthy": {
        "enabled": True,
        "min_age_days": 7,
        "min_unhealthy_days": 14,
        "description": "Azure Load Balancers with 100% unhealthy backends ($18.25/month waste + service unavailable)",
    },
    "load_balancer_no_inbound_rules": {
        "enabled": True,
        "min_age_days": 14,
        "description": "Azure Load Balancers without load balancing or NAT rules ($18.25/month waste)",
    },
    "load_balancer_basic_sku_retired": {
        "enabled": True,
        "description": "Azure Load Balancers using retired Basic SKU - CRITICAL migration required (service interruption risk)",
    },
    "application_gateway_no_backend_targets": {
        "enabled": True,
        "min_age_days": 7,
        "description": "Azure Application Gateways with no backend targets ($262-323/month waste)",
    },
    "application_gateway_stopped": {
        "enabled": True,
        "min_stopped_days": 30,
        "description": "Azure Application Gateways in stopped state - cleanup recommended (no current cost)",
    },
    "load_balancer_never_used": {
        "enabled": True,
        "min_age_days": 30,
        "description": "Azure Load Balancers created but never used ($18.25/month waste)",
    },
    "load_balancer_no_traffic": {
        "enabled": True,
        "min_no_traffic_days": 30,
        "max_bytes_threshold": 1048576,  # 1 MB
        "max_packets_threshold": 1000,
        "description": "Azure Load Balancers with zero traffic over 30 days (Azure Monitor metrics) ($18.25/month waste)",
    },
    "application_gateway_no_requests": {
        "enabled": True,
        "min_no_requests_days": 30,
        "max_requests_threshold": 100,
        "description": "Azure Application Gateways with zero HTTP requests over 30 days (Azure Monitor) ($262-323/month waste)",
    },
    "application_gateway_underutilized": {
        "enabled": True,
        "min_underutilized_days": 30,
        "max_utilization_percent": 5.0,
        "min_requests_per_day": 1000,
        "description": "Azure Application Gateways severely underutilized (<5% capacity) - downgrade recommended ($200-260/month savings)",
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
    "disk_snapshot_very_old": {
        "enabled": True,
        "max_age_threshold": 365,
        "min_age_days": 365,
        "exclude_tags": ["keep", "permanent", "archive", "compliance", "DR"],
        "confidence_critical_days": 730,  # 2 years
        "confidence_high_days": 365,
        "confidence_medium_days": 180,
        "description": "Very old snapshots (>1 year) with accumulated costs",
    },
    "disk_snapshot_premium_source": {
        "enabled": True,
        "min_snapshot_size_gb": 1000,
        "min_age_days": 30,
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Large snapshots from Premium SSD disks (>1 TB generating high costs)",
    },
    "disk_snapshot_large_unused": {
        "enabled": True,
        "large_snapshot_threshold": 1000,
        "min_age_days": 90,
        "confidence_critical_days": 180,
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Large snapshots (>1 TB) never restored (HIGH VALUE waste)",
    },
    "disk_snapshot_full_instead_incremental": {
        "enabled": True,
        "min_snapshots_for_incremental": 2,
        "min_age_days": 30,
        "assumed_change_rate": 0.10,
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Full snapshots instead of incremental (50-90% cost savings - HIGHEST ROI)",
    },
    "disk_snapshot_excessive_retention": {
        "enabled": True,
        "max_snapshots_threshold": 50,
        "recommended_max_snapshots": 30,
        "min_age_days": 7,
        "confidence_critical_days": 180,
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Excessive snapshot retention (>50 snapshots per disk - approaching Azure 500 limit)",
    },
    "disk_snapshot_manual_without_policy": {
        "enabled": True,
        "max_manual_snapshots": 10,
        "min_age_days": 30,
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Manual snapshots without rotation policy (risk of infinite accumulation)",
    },
    "disk_snapshot_never_restored": {
        "enabled": True,
        "min_never_restored_days": 90,
        "exclude_tags": ["DR", "disaster-recovery", "archive", "compliance"],
        "confidence_high_days": 180,
        "confidence_medium_days": 90,
        "description": "Snapshots never restored since 90+ days",
    },
    "disk_snapshot_frequent_creation": {
        "enabled": True,
        "max_frequency_days": 1.0,
        "observation_period_days": 30,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Too frequent snapshot creation (>1/day - switch to weekly for 86% savings)",
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
        "confidence_critical_days": 90,
        "confidence_high_days": 30,
        "confidence_medium_days": 7,
        "description": "Azure VMs deallocated for extended periods",
    },
    "virtual_machine_stopped_not_deallocated": {
        "enabled": True,
        "min_stopped_days": 7,  # CRITICAL - detect quickly to prevent waste
        "confidence_threshold_days": 14,
        "confidence_critical_days": 30,
        "confidence_high_days": 14,
        "confidence_medium_days": 7,
        "description": "Azure VMs stopped but NOT deallocated (paying full price while stopped) - CRITICAL waste scenario",
    },
    "virtual_machine_never_started": {
        "enabled": True,
        "min_age_days": 7,  # VMs never started after 7 days
        "confidence_threshold_days": 30,
        "confidence_critical_days": 60,
        "confidence_high_days": 30,
        "confidence_medium_days": 7,
        "description": "Azure VMs created but never started - likely test or failed deployments",
    },
    "virtual_machine_oversized_premium": {
        "enabled": True,
        "min_age_days": 30,  # Ignore recently created VMs
        "non_prod_environments": ["dev", "test", "staging", "qa", "development"],
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure VMs using Premium SSD in non-production environments - Standard SSD recommended",
    },
    "virtual_machine_untagged_orphan": {
        "enabled": True,
        "min_age_days": 30,  # Ignore recently created VMs
        "required_tags": ["owner", "project", "cost_center", "environment"],
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure VMs missing required governance tags - potentially orphaned resources",
    },
    "virtual_machine_idle": {
        "enabled": True,
        "min_idle_days": 7,  # Observation period in days
        "max_cpu_percent": 5.0,  # Azure Advisor standard: <5% CPU = idle
        "max_network_mb_per_day": 7.0,  # Azure Advisor standard: <7MB/day network traffic = idle
        "confidence_threshold_days": 14,
        "confidence_critical_days": 30,
        "confidence_high_days": 14,
        "confidence_medium_days": 7,
        "description": "Azure VMs running but completely idle (low CPU + low network) - Requires Azure Monitor",
    },
    "virtual_machine_old_generation": {
        "enabled": True,
        "min_age_days": 60,  # Only flag stable VMs (2 months old)
        "old_generations": ["v1", "v2", "_v3"],  # SKU generations to flag for upgrade
        "savings_percent": 25.0,  # Estimated savings from migrating to v4/v5
        "confidence_threshold_days": 90,
        "confidence_critical_days": 180,
        "confidence_high_days": 90,
        "confidence_medium_days": 60,
        "description": "Azure VMs using old generation SKUs (v1/v2/v3) - migrate to v4/v5 for better price-performance",
    },
    "virtual_machine_spot_convertible": {
        "enabled": True,
        "min_age_days": 30,  # Only flag stable VMs (1 month old)
        "spot_eligible_tags": ["batch", "dev", "test", "staging", "ci", "cd", "analytics", "non-critical", "development", "qa"],
        "spot_discount_percent": 75.0,  # Average Spot discount (60-90%)
        "exclude_ha_vms": True,  # Exclude high-availability production VMs
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure VMs eligible for Spot pricing (60-90% savings) - interruptible workloads (dev/test/batch)",
    },
    "virtual_machine_underutilized": {
        "enabled": True,
        "min_observation_days": 30,  # Observation period for CPU analysis
        "max_avg_cpu_percent": 20.0,  # Sustained low average CPU usage
        "max_p95_cpu_percent": 40.0,  # Even peak (p95) CPU is low
        "confidence_threshold_days": 30,
        "confidence_critical_days": 60,
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure VMs consistently underutilized (rightsizing opportunity) - Requires Azure Monitor",
    },
    "virtual_machine_memory_overprovisioned": {
        "enabled": True,
        "min_observation_days": 30,  # Observation period for memory analysis
        "max_memory_percent": 30.0,  # Low memory usage threshold
        "memory_optimized_series": ["E", "M", "G"],  # Memory-optimized series to check
        "confidence_threshold_days": 30,
        "confidence_critical_days": 60,
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure memory-optimized VMs (E-series) with low memory usage - Requires Azure Monitor Agent",
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
    # ===================================
    # AZURE DATABASES (15 Scenarios)
    # ===================================
    # Azure SQL Database - 4 Scenarios
    "sql_database_stopped": {
        "enabled": True,
        "min_age_days": 30,  # Paused for > 30 days
        "confidence_threshold_days": 60,
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 60,  # High confidence after 60 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "exclude_system_databases": True,  # Exclude master, tempdb, model, msdb
        "description": "Azure SQL Databases paused for extended periods ($147-15,699/month waste)",
    },
    "sql_database_idle_connections": {
        "enabled": True,
        "min_age_days": 30,  # Zero connections for > 30 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_connections_threshold": 0,  # 0 connections = idle
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure SQL Databases online but with zero connections over 30 days (Azure Monitor metrics) ($147-15,699/month waste)",
    },
    "sql_database_over_provisioned_dtu": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_dtu_utilization_percent": 30.0,  # < 30% DTU utilization = over-provisioned
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure SQL Databases with DTU utilization <30% over 30 days - downgrade recommended ($118-456/month savings)",
    },
    "sql_database_serverless_not_pausing": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "min_pause_events": 0,  # 0 auto-pause events = never pausing
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure SQL Serverless databases that never auto-pause - constant billing without idle periods ($286/month waste)",
    },
    # Azure Cosmos DB - 3 Scenarios
    "cosmosdb_over_provisioned_ru": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_ru_utilization_percent": 30.0,  # < 30% RU utilization = over-provisioned
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure Cosmos DB with Request Units (RU) utilization <30% over 30 days - downscale recommended ($409/month savings)",
    },
    "cosmosdb_idle_containers": {
        "enabled": True,
        "min_age_days": 30,  # Zero requests for > 30 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_requests_threshold": 0,  # 0 requests = idle
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure Cosmos DB containers with zero requests over 30 days (Azure Monitor metrics) ($36/month per container)",
    },
    "cosmosdb_hot_partitions_idle_others": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "hot_partition_threshold_percent": 80.0,  # > 80% RU on single partition = hot
        "idle_partitions_threshold": 2,  # ≥ 2 idle partitions = inefficient partition key
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure Cosmos DB with hot partitions (poor partition key design) - most RU unused ($409/month savings)",
    },
    # Azure PostgreSQL/MySQL - 4 Scenarios
    "postgres_mysql_stopped": {
        "enabled": True,
        "min_stopped_days": 7,  # Stopped for > 7 days
        "confidence_critical_days": 30,
        "confidence_high_days": 14,
        "confidence_medium_days": 7,
        "description": "Azure Database for PostgreSQL/MySQL stopped for extended periods ($15-22/month waste)",
    },
    "postgres_mysql_idle_connections": {
        "enabled": True,
        "min_age_days": 14,  # Zero connections for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_connections_threshold": 0,  # 0 connections = idle
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure PostgreSQL/MySQL with zero connections over 30 days (Azure Monitor metrics) ($150-600/month waste)",
    },
    "postgres_mysql_over_provisioned_vcores": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_cpu_utilization_percent": 20.0,  # < 20% CPU = over-provisioned
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure PostgreSQL/MySQL with vCore utilization <20% over 30 days - downgrade recommended ($300/month savings)",
    },
    "postgres_mysql_burstable_always_bursting": {
        "enabled": True,
        "min_age_days": 7,  # Stable for > 7 days
        "monitoring_days": 14,  # Azure Monitor lookback period
        "burst_usage_threshold_percent": 90.0,  # > 90% time bursting = undersized
        "confidence_high_days": 14,
        "confidence_medium_days": 7,
        "description": "Azure PostgreSQL/MySQL Burstable tier constantly bursting (>90% time) - performance issue + potential throttling",
    },
    # Azure Synapse Analytics - 2 Scenarios
    "synapse_sql_pool_paused": {
        "enabled": True,
        "min_paused_days": 30,  # Paused for > 30 days
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure Synapse SQL pools paused for extended periods - cleanup recommended ($246-983/month waste)",
    },
    "synapse_sql_pool_idle_queries": {
        "enabled": True,
        "min_age_days": 30,  # Zero queries for > 30 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_queries_threshold": 0,  # 0 queries = idle
        "confidence_critical_days": 90,  # CRITICAL - very expensive idle resource
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure Synapse SQL pools with zero queries over 30 days - CRITICAL waste ($4,503-9,006/month)",
    },
    # Azure Cache for Redis - 2 Scenarios
    "redis_idle_cache": {
        "enabled": True,
        "min_age_days": 14,  # Zero connections for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_connections_threshold": 0,  # 0 connections = idle
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Azure Cache for Redis with zero connections over 30 days (Azure Monitor metrics) ($104-1,664/month waste)",
    },
    "redis_over_sized_tier": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_memory_utilization_percent": 30.0,  # < 30% memory used = over-sized
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Azure Cache for Redis with memory utilization <30% over 30 days - downgrade tier recommended ($312-3,976/month savings)",
    },
    # ===================================
    # AZURE STORAGE ACCOUNTS (8 Scenarios Implemented)
    # ===================================
    "storage_account_never_used": {
        "enabled": True,
        "min_age_days": 30,  # Never used for > 30 days
        "confidence_critical_days": 90,
        "confidence_high_days": 30,
        "confidence_medium_days": 7,
        "description": "Azure Storage Accounts never used (no containers created) - management overhead only ($0.43/month waste)",
    },
    "storage_account_empty": {
        "enabled": True,
        "min_age_days": 7,  # Minimum age before flagging
        "min_empty_days": 30,  # Empty for > 30 days
        "confidence_high_days": 30,
        "confidence_medium_days": 7,
        "description": "Azure Storage Accounts with empty containers (no data stored for 30+ days) - transaction overhead ($0.07/month waste)",
    },
    "storage_no_lifecycle_policy": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "min_size_threshold": 100,  # Only check if >= 100 GB
        "confidence_critical_days": 90,
        "confidence_high_days": 30,
        "description": "Azure Storage Accounts in Hot tier WITHOUT lifecycle management policy - CRITICAL ($82.80/TB/month potential savings - 46%)",
    },
    "storage_unnecessary_grs": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "confidence_high_days": 30,
        "description": "Azure Storage Accounts with GRS/RAGRS/GZRS in dev/test environments - LRS sufficient ($18/TB/month savings - 50%)",
    },
    "soft_deleted_blobs_accumulated": {
        "enabled": True,
        "max_retention_days": 30,  # Maximum recommended retention
        "min_deleted_size_gb": 10,  # Minimum size to flag
        "description": "Soft-deleted blobs with retention period >30 days - billed at same rate as active data ($13.77/account/month potential savings - 90%)",
    },
    "blobs_hot_tier_unused": {
        "enabled": True,
        "min_unused_days_cool": 30,  # Not accessed for 30+ days → Cool tier
        "min_unused_days_archive": 90,  # Not accessed for 90+ days → Archive tier
        "min_blob_size_gb": 0.1,  # Minimum blob size to consider
        "description": "Blobs in Hot tier not accessed for 30+ days - should be Cool/Archive ($84.96/TB/month savings - 94.5%)",
    },
    "storage_account_no_transactions": {
        "enabled": True,
        "min_no_transactions_days": 90,  # Zero transactions for 90 days
        "max_transactions_threshold": 100,  # Max transactions to consider "no activity"
        "confidence_critical_days": 90,
        "description": "Azure Storage Accounts with zero transactions over 90 days (Azure Monitor metrics) - consider archiving or deleting",
    },
    "blob_old_versions_accumulated": {
        "enabled": True,
        "min_age_days": 30,  # Minimum age before flagging
        "max_versions_per_blob": 5,  # Maximum recommended versions to keep
        "min_blob_size_gb": 1,  # Minimum blob size to consider
        "description": "Blob versioning with excessive versions (>5 per blob) - each version costs full blob price ($186.48/account/month potential savings - 86%)",
    },
    # ===================================
    # AZURE FUNCTIONS (10 Scenarios - 100% Coverage)
    # ===================================
    "functions_never_invoked": {
        "enabled": True,
        "min_age_days": 30,  # Minimum age before flagging
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 60,  # High confidence after 60 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Azure Function App never invoked since creation (Premium: $388-1,553/month, Consumption: $0 idle)",
    },
    "functions_premium_plan_idle": {
        "enabled": True,
        "low_invocation_threshold": 100,  # <100 invocations/month
        "monitoring_period_days": 30,  # Monitor last 30 days
        "confidence_critical_days": 30,  # Critical if <50 invocations
        "confidence_high_days": 30,  # High if <100 invocations
        "confidence_medium_days": 30,  # Medium if <500 invocations
        "description": "Premium Function App with very low invocations (<100/month) - migrate to Consumption ($388/month P0 savings, 50% frequency)",
    },
    "functions_consumption_over_allocated_memory": {
        "enabled": False,  # Requires Application Insights memory metrics
        "memory_utilization_threshold": 50,  # <50% memory used
        "monitoring_period_days": 30,
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Consumption Function with over-allocated memory (>50% unused) - reduce memory allocation ($2-20/month savings)",
    },
    "functions_always_on_consumption": {
        "enabled": True,
        "min_age_days": 7,  # Minimum age before flagging
        "description": "Always On configured on Consumption plan (invalid config - no cost impact but cleanup recommended)",
    },
    "functions_premium_plan_oversized": {
        "enabled": True,
        "cpu_threshold": 20,  # <20% CPU utilization
        "monitoring_period_days": 30,
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Premium Function App oversized (EP2/EP3 with low CPU) - downgrade to EP1 ($388-1,165/month P0 savings, 20% frequency)",
    },
    "functions_dev_test_premium": {
        "enabled": True,
        "min_age_days": 30,  # Minimum age before flagging
        "dev_test_tags": ["dev", "test", "development", "testing", "staging"],  # Environment tags
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 60,  # High confidence after 60 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Premium Function App in dev/test environment - migrate to Consumption ($388/month P0 savings, 25% frequency)",
    },
    "functions_multiple_plans_same_app": {
        "enabled": True,
        "min_age_days": 30,  # Minimum age before flagging
        "max_plans_per_app": 1,  # Maximum recommended plans per application
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Multiple App Service Plans for same application - consolidate into single plan ($388-776/month P1 savings, 10% frequency)",
    },
    "functions_low_invocation_rate_premium": {
        "enabled": True,
        "low_invocation_threshold": 1000,  # <1000 invocations/month
        "monitoring_period_days": 30,
        "confidence_critical_days": 30,  # Critical if <500 invocations
        "confidence_high_days": 30,  # High if <1000 invocations
        "confidence_medium_days": 30,  # Medium if <5000 invocations
        "description": "Premium Function App with low invocation rate (<1000/month) via Application Insights ($388/month P0 savings, 40% frequency)",
    },
    "functions_high_error_rate": {
        "enabled": True,
        "high_error_rate_threshold": 50,  # >50% error rate
        "monitoring_period_days": 30,
        "confidence_critical_days": 30,  # Critical if >70% errors
        "confidence_high_days": 30,  # High if >50% errors
        "description": "Function App with high error rate (>50%) via Application Insights - fix errors to reduce waste ($0.26-233/month P2 savings)",
    },
    "functions_long_execution_time": {
        "enabled": True,
        "long_execution_threshold": 5,  # >5 minutes average execution
        "monitoring_period_days": 30,
        "confidence_critical_days": 30,  # Critical if >10 min
        "confidence_high_days": 30,  # High if >5 min
        "confidence_medium_days": 30,  # Medium if >3 min
        "description": "Function App with long execution time (>5 min avg) via Application Insights - optimize code ($72/month P1 savings, 15% frequency)",
    },
    # ===================================
    # AZURE COSMOS DB TABLE API (12 Scenarios - 100% Coverage)
    # ===================================
    # P0 Scenarios - Critical ROI ($31,177/year)
    "cosmosdb_table_api_low_traffic": {
        "enabled": True,
        "min_age_days": 30,  # Minimum age before flagging
        "max_requests_per_sec_threshold": 100,  # <100 req/sec = migrate to Azure Table Storage
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 60,  # High confidence after 60 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Cosmos DB Table API with low traffic (<100 req/sec) - migrate to Azure Table Storage ($291.60/account/month savings - 90%)",
    },
    "cosmosdb_table_over_provisioned_ru": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "over_provisioned_threshold": 30,  # <30% RU utilization = over-provisioned
        "recommended_buffer": 1.3,  # 30% buffer above peak usage
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Cosmos DB Table API with RU utilization <30% over 30 days - reduce RU/s ($227-682/month savings - 70%)",
    },
    "cosmosdb_table_high_storage_low_throughput": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "min_storage_gb_threshold": 500,  # >500 GB storage
        "max_ru_utilization_threshold": 20,  # <20% RU utilization
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API with high storage (>500GB) + low RU (<20%) - migrate to Azure Table Storage ($850/month savings)",
    },
    "cosmosdb_table_idle": {
        "enabled": True,
        "min_age_days": 30,  # Zero requests for > 30 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "max_requests_threshold": 100,  # <100 total requests = idle
        "confidence_critical_days": 90,  # CRITICAL - very expensive idle resource
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API idle (0 requests over 30 days) - CRITICAL waste ($324/month per account)",
    },
    "cosmosdb_table_autoscale_not_scaling_down": {
        "enabled": True,
        "min_age_days": 14,  # Stable for > 14 days
        "monitoring_days": 30,  # Azure Monitor lookback period
        "autoscale_stuck_threshold": 95,  # >95% time at max RU/s
        "confidence_high_days": 30,
        "confidence_medium_days": 14,
        "description": "Cosmos DB Table API autoscale stuck at max (>95% time) - switch to manual provisioned ($129/month savings - 33%)",
    },
    # P1 Scenarios - High ROI ($15,912/year)
    "cosmosdb_table_unnecessary_multi_region": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "min_regions": 2,  # Flag if >= 2 regions
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API multi-region in dev/test - use single-region ($324/month per extra region - 50%)",
    },
    "cosmosdb_table_continuous_backup_unused": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "lookback_days": 90,  # Check restore history over 90 days
        "compliance_tags": ["compliance", "hipaa", "pci", "sox", "gdpr", "regulated"],
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API continuous backup without compliance tags - switch to periodic ($156/TB/month savings - 44%)",
    },
    "cosmosdb_table_empty_tables": {
        "enabled": True,
        "min_age_days": 30,  # Empty for > 30 days
        "min_provisioned_ru": 400,  # Minimum RU/s per table
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API with empty tables provisioned - delete empty tables ($25.92/table/month waste)",
    },
    "cosmosdb_table_throttled_need_autoscale": {
        "enabled": True,
        "min_age_days": 7,  # Stable for > 7 days
        "monitoring_days": 14,  # Azure Monitor lookback period
        "throttling_threshold": 5,  # >5% throttling rate
        "confidence_high_days": 14,
        "confidence_medium_days": 7,
        "description": "Cosmos DB Table API manual provisioned with throttling (>5%) - enable autoscale to prevent errors",
    },
    # P2 Scenarios - Medium ROI ($3,448/year)
    "cosmosdb_table_never_used": {
        "enabled": True,
        "min_age_days": 30,  # Never used for > 30 days
        "confidence_critical_days": 90,
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API never used (0 tables created) - cleanup recommended ($324/month waste)",
    },
    "cosmosdb_table_unnecessary_zone_redundancy": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "confidence_high_days": 60,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API zone-redundant in dev/test - disable zone redundancy ($37/month savings - 15%)",
    },
    "cosmosdb_table_analytical_storage_never_used": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "lookback_days": 90,  # Check analytical query history over 90 days
        "confidence_high_days": 90,
        "confidence_medium_days": 30,
        "description": "Cosmos DB Table API analytical storage never used - disable analytical store ($30/TB/month savings)",
    },
    # ===================================
    # AZURE CONTAINER APPS (16 Scenarios - 100% Coverage)
    # ===================================
    # Phase 1 - Detection Simple (10 scenarios)
    "container_app_stopped": {
        "enabled": True,
        "min_stopped_days": 30,  # Stopped (min/max replicas = 0) for > 30 days
        "min_age_days": 7,  # Don't alert on newly created apps
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 60,  # High confidence after 60 days
        "confidence_medium_days": 30,  # Medium confidence after 30 days
        "description": "Container Apps stopped (minReplicas=0, maxReplicas=0) since >30 days - Dedicated plan pays full cost ($146/month D4)",
    },
    "container_app_zero_replicas": {
        "enabled": True,
        "min_zero_replica_days": 30,  # Zero replicas in production for > 30 days
        "exclude_dev_environments": True,  # dev/test scale-to-zero is legitimate
        "dev_environments": ["dev", "test", "development", "testing", "staging", "qa"],
        "confidence_high_days": 30,
        "description": "Container Apps with 0 replicas in production environment - Dedicated environment charged even with 0 replicas ($146/month D4)",
    },
    "container_app_unnecessary_premium_tier": {
        "enabled": True,
        "max_utilization_threshold": 50,  # <50% profile utilization = waste
        "min_observation_days": 30,  # Monitor utilization for 30 days
        "confidence_critical_days": 60,  # Critical if <25% utilization
        "confidence_high_days": 30,  # High if <50% utilization
        "description": "Dedicated Workload Profiles (D4/D8/D16/D32) with <50% utilization - migrate to Consumption plan ($67-1,089/month savings)",
    },
    "container_app_dev_zone_redundancy": {
        "enabled": True,
        "min_age_days": 30,  # Stable for > 30 days
        "dev_environments": ["dev", "test", "development", "testing", "staging", "qa", "nonprod"],
        "confidence_high_days": 30,
        "description": "Zone-redundant environments in dev/test - disable zone redundancy ($19.71/month savings - 25%)",
    },
    "container_app_no_ingress_configured": {
        "enabled": True,
        "min_age_days": 60,  # Allow time for configuration
        "allow_internal_only": False,  # Alert even on internal-only ingress
        "confidence_medium_days": 60,
        "description": "Container Apps without ingress configured - consider Azure Functions or Container Instances Jobs ($78.83/month savings)",
    },
    "container_app_empty_environment": {
        "enabled": True,
        "min_empty_days": 30,  # Environment empty for > 30 days
        "exclude_newly_created": True,  # Grace period for new environments
        "grace_period_days": 7,
        "confidence_critical_days": 60,  # Critical after 60 days
        "confidence_medium_days": 30,
        "description": "Managed Environments with 0 Container Apps - Dedicated profiles charged even when empty ($146/month D4)",
    },
    "container_app_unused_revision": {
        "enabled": True,
        "max_inactive_revisions": 5,  # Keep max 5 inactive revisions
        "min_revision_age_days": 90,  # Revisions older than 90 days
        "confidence_low_days": 90,
        "description": "Container Apps with >5 inactive revisions (>90 days old) - cleanup recommended for hygiene (minimal cost impact)",
    },
    "container_app_overprovisioned_cpu_memory": {
        "enabled": True,
        "min_overprovisioning_threshold": 3,  # Allocation 3x+ actual usage
        "min_observation_days": 30,  # Requires Azure Monitor metrics
        "confidence_high_days": 30,  # With metrics
        "confidence_medium_days": 30,  # Without metrics (heuristics)
        "description": "Container Apps with CPU/memory allocation 3x+ actual usage - rightsizing recommended ($118.24/month savings)",
    },
    "container_app_custom_domain_unused": {
        "enabled": True,
        "min_observation_days": 60,  # Monitor HTTP requests for 60 days
        "max_requests_threshold": 10,  # <10 total requests = unused
        "confidence_high_days": 60,
        "description": "Custom domains configured with 0 HTTP requests over 60 days - remove unused custom domain (cleanup + certificate costs)",
    },
    "container_app_secrets_unused": {
        "enabled": True,
        "min_age_days": 60,  # Secrets unreferenced for > 60 days
        "confidence_medium_days": 60,
        "description": "Secrets defined but not referenced by containers or Dapr - security hygiene (no direct cost)",
    },
    # Phase 2 - Azure Monitor Métriques (6 scenarios)
    "container_app_low_cpu_utilization": {
        "enabled": True,
        "max_cpu_utilization_percent": 15,  # CPU <15% = over-provisioned
        "min_observation_days": 30,  # Azure Monitor lookback period
        "recommended_buffer": 1.3,  # 30% buffer above peak usage
        "confidence_critical_days": 30,  # Critical if <10%
        "confidence_high_days": 30,  # High if <15%
        "confidence_medium_days": 30,  # Medium if <20%
        "description": "Container Apps with CPU utilization <15% over 30 days - downsize recommended ($94.60/month savings - 75%)",
    },
    "container_app_low_memory_utilization": {
        "enabled": True,
        "max_memory_utilization_percent": 20,  # Memory <20% = over-provisioned
        "min_observation_days": 30,  # Azure Monitor lookback period
        "confidence_critical_days": 30,  # Critical if <15%
        "confidence_high_days": 30,  # High if <20%
        "confidence_medium_days": 30,  # Medium if <30%
        "description": "Container Apps with memory utilization <20% over 30 days - downsize recommended ($23.64/month savings - 75%)",
    },
    "container_app_zero_http_requests": {
        "enabled": True,
        "min_observation_days": 60,  # Monitor HTTP requests for 60 days
        "max_requests_threshold": 100,  # <100 total requests = unused
        "confidence_critical_days": 90,  # Critical after 90 days
        "confidence_high_days": 60,
        "description": "Container Apps with 0 HTTP requests over 60 days - stop app or investigate backend usage ($78.83/month waste - 100%)",
    },
    "container_app_high_replica_low_traffic": {
        "enabled": True,
        "min_avg_replicas": 5,  # Alert if average replicas >= 5
        "max_requests_per_replica_per_sec": 10,  # <10 req/sec per replica = over-scaled
        "min_observation_days": 30,  # Azure Monitor lookback period
        "confidence_high_days": 30,  # High if <5 req/sec/replica
        "confidence_medium_days": 30,  # Medium if <10 req/sec/replica
        "description": "Container Apps with >5 replicas + <10 req/sec per replica - reduce maxReplicas ($276.32/month savings - 70%)",
    },
    "container_app_autoscaling_not_triggering": {
        "enabled": True,
        "min_observation_days": 30,  # Monitor replica variance for 30 days
        "min_scale_events": 5,  # Expected minimum scale events
        "max_stddev_threshold": 0.5,  # Low variance = autoscale not working
        "confidence_medium_days": 30,
        "description": "Autoscale configured but replicas never change (stddev <0.5) - fix autoscale rules or switch to manual (waste capacity or underprovisioned)",
    },
    "container_app_cold_start_issues": {
        "enabled": True,
        "max_avg_cold_start_ms": 10000,  # >10 seconds average cold start
        "min_cold_start_count": 50,  # At least 50 cold starts in period
        "min_observation_days": 30,  # Azure Monitor lookback period
        "confidence_high_days": 30,
        "description": "Container Apps with minReplicas=0 + cold starts >10 sec - set minReplicas=1 for better UX (trade-off: +$39.42/month vs cold start elimination)",
    },
    # ===== Azure Virtual Desktop (18 scenarios - 100% coverage) =====
    # Phase 1 - Detection Simple (12 scenarios)
    "avd_host_pool_empty": {
        "enabled": True,
        "min_empty_days": 30,
        "min_age_days": 7,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Host pools empty (0 session hosts) since >30 days - minimal infrastructure cost but wasteful ($0-146/month depending on environment)",
    },
    "avd_session_host_stopped": {
        "enabled": True,
        "min_stopped_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "Session hosts deallocated >30 days - still paying for disks ($32/month per host: $12.29 OS disk + FSLogix)",
    },
    "avd_session_host_never_used": {
        "enabled": True,
        "min_age_days": 30,
        "confidence_high_days": 30,
        "description": "Session hosts created >30 days ago but never had user sessions - 100% waste ($140-180/month per host)",
    },
    "avd_host_pool_no_autoscale": {
        "enabled": True,
        "min_hosts_for_autoscale": 5,
        "min_savings_threshold": 100,  # Only alert if potential savings ≥$100/month
        "exclude_environments": ["prod", "production"],
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Pooled host pools without autoscale (always-on) - waste 60-70% ($933/month for 10 hosts vs $308 with autoscale)",
    },
    "avd_host_pool_over_provisioned": {
        "enabled": True,
        "max_utilization_threshold": 30,  # <30% utilization = over-provisioned
        "recommended_buffer": 1.3,  # 30% headroom above average
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "Host pools with <30% capacity utilization - reduce session hosts ($840/month savings for 10→4 hosts)",
    },
    "avd_application_group_empty": {
        "enabled": True,
        "min_age_days": 30,
        "confidence_medium_days": 30,
        "description": "RemoteApp application groups with 0 applications configured - no direct cost but complexity waste",
    },
    "avd_workspace_empty": {
        "enabled": True,
        "min_age_days": 30,
        "confidence_high_days": 30,
        "description": "Workspaces with no application groups attached - hygiene issue",
    },
    "avd_premium_disk_in_dev": {
        "enabled": True,
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "min_age_days": 30,
        "confidence_high_days": 30,
        "description": "Session hosts with Premium SSD in dev/test environments - migrate to StandardSSD ($10.11/month savings per host)",
    },
    "avd_unnecessary_availability_zones": {
        "enabled": True,
        "dev_environments": ["dev", "test", "staging", "qa"],
        "min_age_days": 30,
        "confidence_high_days": 30,
        "description": "Session hosts deployed across multiple zones in dev/test - zone redundancy adds ~25% overhead ($350/month for 10 hosts)",
    },
    "avd_personal_desktop_never_used": {
        "enabled": True,
        "min_unused_days": 60,
        "confidence_high_days": 60,
        "description": "Personal desktops assigned but never/rarely used (60+ days) - 100% waste ($140-180/month per desktop)",
    },
    "avd_fslogix_oversized": {
        "enabled": True,
        "max_utilization_threshold": 50,
        "premium_min_iops": 3000,  # If avg IOPS <3000, Premium not needed
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Azure Files Premium for FSLogix with low utilization (<50%) or low IOPS - migrate to Standard ($143/month savings per 1TB)",
    },
    "avd_session_host_old_vm_generation": {
        "enabled": True,
        "max_generation_allowed": 3,  # Alert if VM generation ≤v3
        "min_age_days": 60,
        "confidence_medium_days": 60,
        "description": "Session hosts using old VM generations (v3 vs v5) - upgrade for 20% cost savings + 20% performance gain ($28/month per host)",
    },
    # Phase 2 - Azure Monitor Metrics (6 scenarios)
    "avd_low_cpu_utilization": {
        "enabled": True,
        "max_cpu_utilization_percent": 15,
        "min_observation_days": 30,
        "recommended_buffer": 1.3,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "Session hosts with <15% avg CPU utilization - downsize VM ($70/month savings: D4s_v4→D2s_v4)",
    },
    "avd_low_memory_utilization": {
        "enabled": True,
        "max_available_memory_threshold": 80,  # >80% available = <20% used
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "description": "Session hosts with low memory usage (<20%) - migrate E-series→D-series ($40/month savings: E4s_v4→D4s_v4)",
    },
    "avd_zero_user_sessions": {
        "enabled": True,
        "min_observation_days": 60,
        "max_sessions_threshold": 0,
        "confidence_critical_days": 60,
        "description": "Host pools with 0 user sessions for 60+ days - delete entire pool (100% waste: $700/month for 5 hosts)",
    },
    "avd_high_host_count_low_users": {
        "enabled": True,
        "min_avg_hosts": 5,
        "max_utilization_threshold": 20,  # Severe over-provisioning
        "recommended_buffer": 1.3,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "description": "Many session hosts but few concurrent users (<20% capacity) - reduce hosts ($1,960/month savings: 20→6 hosts)",
    },
    "avd_disconnected_sessions_waste": {
        "enabled": True,
        "min_disconnected_threshold": 5,  # Avg disconnected sessions
        "recommended_max_timeout": 14400,  # 4 hours in seconds
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "description": "High disconnected sessions without timeout config - configure timeout to reclaim capacity ($140-280/month potential savings)",
    },
    "avd_peak_hours_mismatch": {
        "enabled": True,
        "min_mismatch_hours": 2,  # Alert if ≥2h schedule mismatch
        "peak_threshold_percent": 70,  # % of max to consider as peak
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "description": "Autoscale peak hours don't match actual usage patterns - adjust schedule ($2,301/month waste: 4h/day mismatch × 10 hosts)",
    },
    # ===== Azure HDInsight Spark Cluster (18 scenarios - 100% coverage) =====
    # Phase 1 - Detection Simple (10 scenarios)
    "hdinsight_spark_cluster_stopped": {
        "enabled": True,
        "min_stopped_days": 7,
        "confidence_medium_days": 7,
        "confidence_high_days": 30,
        "description": "Spark cluster stopped >7 days - still paying storage costs (~$840/month for small cluster)",
    },
    "hdinsight_spark_cluster_never_used": {
        "enabled": True,
        "min_age_days": 14,
        "confidence_high_days": 14,
        "description": "Spark cluster never executed any jobs since creation (14+ days) - 100% waste ($8,400/month typical cluster)",
    },
    "hdinsight_spark_premium_storage_dev": {
        "enabled": True,
        "dev_environments": ["dev", "test", "staging", "qa", "development", "nonprod"],
        "min_age_days": 7,
        "confidence_high_days": 7,
        "description": "Premium storage in dev/test environments - migrate to Standard ($800/month savings per cluster)",
    },
    "hdinsight_spark_no_autoscale": {
        "enabled": True,
        "min_worker_nodes": 5,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "No autoscale configured with >= 5 worker nodes - waste 40-60% during low-load periods ($5,600/month for 24/7 cluster)",
    },
    "hdinsight_spark_outdated_version": {
        "enabled": True,
        "min_supported_versions": ["3.2", "3.3"],  # Spark versions
        "confidence_critical_days": 90,
        "description": "Outdated Spark version (security risk + no support) - upgrade to 3.3+ or migrate to Synapse/Databricks",
    },
    "hdinsight_spark_external_metastore_unused": {
        "enabled": True,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "description": "External metastore (SQL DB) configured but never accessed - $73/month wasted on S0 tier",
    },
    "hdinsight_spark_empty_cluster": {
        "enabled": True,
        "min_age_days": 14,
        "max_data_processed_gb": 1,
        "confidence_high_days": 14,
        "description": "Cluster processes <1GB data in 14+ days - delete or migrate to serverless ($8,400/month waste)",
    },
    "hdinsight_spark_oversized_head_nodes": {
        "enabled": True,
        "max_recommended_head_node_size": "Standard_D4_v2",
        "confidence_medium_days": 30,
        "description": "Head nodes oversized (>D4_v2) - downsize head nodes ($200/month savings per node)",
    },
    "hdinsight_spark_unnecessary_edge_node": {
        "enabled": True,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "description": "Edge node provisioned but never used - remove edge node ($490/month savings for D13_v2)",
    },
    "hdinsight_spark_undersized_disks": {
        "enabled": True,
        "min_disk_size_gb": 256,
        "confidence_medium_days": 30,
        "description": "Worker node disks <256GB causing spill-to-disk issues - increase disk size or optimize jobs (performance issue)",
    },
    # Phase 2 - Azure Monitor + Ambari API Metrics (8 scenarios)
    "hdinsight_spark_low_cpu_utilization": {
        "enabled": True,
        "max_cpu_utilization_percent": 20,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "Worker nodes with <20% avg CPU utilization - downsize worker nodes ($2,800/month savings: 10 workers → 6 workers)",
    },
    "hdinsight_spark_zero_jobs_metrics": {
        "enabled": True,
        "min_observation_days": 30,
        "confidence_critical_days": 30,
        "description": "0 Spark jobs submitted in 30+ days (Ambari metrics) - delete cluster ($8,400/month waste)",
    },
    "hdinsight_spark_idle_business_hours": {
        "enabled": True,
        "business_hours_start": 9,
        "business_hours_end": 17,
        "max_cpu_threshold_percent": 10,
        "min_observation_days": 14,
        "confidence_high_days": 14,
        "description": "Cluster idle (<10% CPU) during business hours (9-5) - investigate usage patterns or delete ($8,400/month waste)",
    },
    "hdinsight_spark_high_yarn_memory_waste": {
        "enabled": True,
        "max_memory_utilization_percent": 40,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "description": "YARN containers using <40% allocated memory - reduce executor memory config ($3,360/month savings: 10 workers → 6 workers)",
    },
    "hdinsight_spark_excessive_shuffle_data": {
        "enabled": True,
        "max_shuffle_data_ratio": 5.0,  # Shuffle data / Input data ratio
        "min_observation_days": 14,
        "confidence_medium_days": 14,
        "description": "Jobs with shuffle data >5x input data - optimize partition strategy (performance + cost issue)",
    },
    "hdinsight_spark_autoscale_not_working": {
        "enabled": True,
        "max_worker_node_variance": 1,  # Worker count stddev
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "description": "Autoscale configured but worker count never changes (variance <1) - fix autoscale rules or disable",
    },
    "hdinsight_spark_low_memory_utilization": {
        "enabled": True,
        "max_memory_utilization_percent": 25,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "description": "Worker nodes with <25% memory utilization - downsize to memory-optimized series ($1,200/month savings)",
    },
    "hdinsight_spark_high_job_failure_rate": {
        "enabled": True,
        "max_job_failure_rate_percent": 25,
        "min_jobs_count": 20,
        "min_observation_days": 14,
        "confidence_high_days": 14,
        "description": "Job failure rate >25% - investigate job errors or cluster misconfig (waste compute + developer time)",
    },
    # ===== Azure Machine Learning Compute Instance (18 scenarios - 100% coverage) =====
    # Phase 1 - Detection Simple (10 scenarios)
    "ml_compute_instance_no_auto_shutdown": {
        "enabled": True,
        "min_age_days": 7,
        "assumed_usage_hours_per_day": 8,
        "confidence_medium_days": 7,
        "confidence_high_days": 30,
        "description": "Compute instance running 24/7 without auto-shutdown or schedule - waste 67% if used 8h/day ($112/month for Standard_DS3_v2)",
    },
    "ml_compute_instance_gpu_for_cpu_workload": {
        "enabled": True,
        "min_age_days": 14,
        "max_gpu_utilization_percent": 5,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "GPU instance (NC/ND series) with 0% GPU usage - switch to CPU instance to save 60-80% ($514/month waste for NC6)",
    },
    "ml_compute_instance_stopped_30_days": {
        "enabled": True,
        "min_stopped_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 90,
        "confidence_critical_days": 180,
        "description": "Compute instance stopped >30 days - still paying storage costs ($22/month) - consider deletion",
    },
    "ml_compute_instance_over_provisioned": {
        "enabled": True,
        "min_age_days": 14,
        "max_cpu_utilization_percent": 30,
        "max_memory_utilization_percent": 40,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "Over-provisioned instance (<30% CPU, <40% RAM) - downsize to save 40-60% ($75/month for DS12_v2 → DS3_v2)",
    },
    "ml_compute_instance_never_accessed": {
        "enabled": True,
        "min_age_days": 60,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "Compute instance created but never accessed (0 activity in 60+ days) - 100% waste ($143/month for DS3_v2)",
    },
    "ml_compute_instance_multiple_per_user": {
        "enabled": True,
        "min_instances_per_user": 2,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "User has multiple compute instances (duplication) - consolidate to 1 instance to save 50% ($286/month for 2× DS3_v2)",
    },
    "ml_compute_instance_premium_ssd_unnecessary": {
        "enabled": True,
        "min_age_days": 14,
        "max_disk_iops_utilization_percent": 30,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "Premium SSD when Standard SSD sufficient (<30% IOPS usage) - save 60% on storage ($120/month for 1TB Premium)",
    },
    "ml_compute_instance_no_idle_shutdown": {
        "enabled": True,
        "min_age_days": 7,
        "has_schedule_shutdown": True,
        "confidence_medium_days": 7,
        "confidence_high_days": 21,
        "description": "Schedule shutdown configured but no idle shutdown - waste during work hours when inactive ($67/month for 4h/day idle)",
    },
    "ml_compute_instance_dev_high_performance_sku": {
        "enabled": True,
        "exclude_environments": ["prod", "production"],
        "min_vcpu_count": 16,
        "confidence_medium_days": 7,
        "confidence_high_days": 30,
        "description": "Dev/test environment using high-performance SKU (>=16 vCPU) - overkill for development ($500/month for E16s_v3)",
    },
    "ml_compute_instance_old_sdk_deprecated_image": {
        "enabled": True,
        "min_image_age_days": 365,
        "confidence_medium_days": 180,
        "confidence_high_days": 365,
        "description": "Compute instance using old SDK version or deprecated image (>1 year old) - security risk + missing features",
    },
    # Phase 2 - Detection avec métriques Azure Monitor + Azure ML API (8 scenarios)
    "ml_compute_instance_low_cpu_utilization": {
        "enabled": True,
        "max_avg_cpu_percent": 10,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "CPU utilization <10% avg over 30 days - instance oversized or underused ($107/month waste for 75% reduction)",
    },
    "ml_compute_instance_low_gpu_utilization": {
        "enabled": True,
        "max_avg_gpu_percent": 15,
        "min_observation_days": 14,
        "confidence_high_days": 14,
        "confidence_critical_days": 30,
        "description": "GPU utilization <15% for GPU instance - switch to CPU instance to save 60-80% ($500/month for NC6)",
    },
    "ml_compute_instance_idle_business_hours": {
        "enabled": True,
        "business_hours_start": 9,
        "business_hours_end": 17,
        "max_cpu_percent_business_hours": 5,
        "min_observation_days": 14,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "Instance idle during business hours (9 AM - 5 PM <5% CPU) - enable auto-shutdown to save 50% ($54/month)",
    },
    "ml_compute_instance_no_jupyter_activity": {
        "enabled": True,
        "min_days_no_notebook_activity": 30,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "No Jupyter notebook activity (0 kernels, 0 notebook opens) for 30+ days - 100% waste ($143/month)",
    },
    "ml_compute_instance_no_training_jobs": {
        "enabled": True,
        "min_days_no_training_jobs": 30,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "No training jobs submitted (via Azure ML SDK) for 30+ days - instance unused ($143/month waste)",
    },
    "ml_compute_instance_low_memory_utilization": {
        "enabled": True,
        "max_avg_memory_percent": 25,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Memory utilization <25% avg over 30 days - downsize to save 50% ($71/month for E8s_v3 → E4s_v3)",
    },
    "ml_compute_instance_network_idle": {
        "enabled": True,
        "max_network_bytes_per_day": 1048576,  # 1 MB/day
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "Network idle (< 1 MB/day in+out) for 30+ days - instance not doing anything ($143/month waste)",
    },
    "ml_compute_instance_disk_io_near_zero": {
        "enabled": True,
        "max_disk_iops_per_day": 100,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "Disk I/O near zero (<100 IOPS/day) for 30+ days - instance idle or not used ($143/month waste)",
    },
    # ===== Azure App Service (Web Apps) (18 scenarios - 100% coverage) =====
    # Phase 1 - Detection Simple (10 scenarios)
    "app_service_plan_empty": {
        "enabled": True,
        "min_empty_days": 7,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "App Service Plan with 0 apps deployed >7 days - 100% waste ($70-876/month depending on SKU)",
    },
    "app_service_premium_in_dev": {
        "enabled": True,
        "exclude_environments": ["prod", "production"],
        "premium_tiers": ["Premium", "PremiumV2", "PremiumV3", "Isolated"],
        "confidence_high_days": 7,
        "description": "Premium tier (P1v2+) in dev/test - downgrade to Basic/Standard to save 62% ($91/month P1v2→B2)",
    },
    "app_service_no_auto_scale": {
        "enabled": True,
        "min_instances_for_autoscale": 2,
        "min_age_days": 14,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "No auto-scale configured with fixed >=2 instances - waste 50% during low-load ($140/month for S2)",
    },
    "app_service_always_on_low_traffic": {
        "enabled": True,
        "max_requests_per_day": 100,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Always On enabled for low-traffic apps (<100 req/day) - 10-15% overhead waste ($7/month for S1)",
    },
    "app_service_unused_deployment_slots": {
        "enabled": True,
        "min_days_no_traffic": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Deployment slots with 0 traffic >30 days - each slot = additional instance cost ($146/month per P1v2 slot)",
    },
    "app_service_over_provisioned_plan": {
        "enabled": True,
        "max_cpu_utilization_percent": 30,
        "max_memory_utilization_percent": 40,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Over-provisioned plan (<30% CPU <40% RAM) - downsize to save 50% ($70/month S2→S1)",
    },
    "app_service_stopped_apps_paid_plan": {
        "enabled": True,
        "min_stopped_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "Stopped apps on paid plans >30 days - still paying plan cost ($70/month for S1)",
    },
    "app_service_multiple_plans_consolidation": {
        "enabled": True,
        "min_plans_for_consolidation": 2,
        "max_apps_per_plan_threshold": 5,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "Multiple plans with <5 apps each - consolidate to save 33% ($70/month - 3× S1 → 1× S2)",
    },
    "app_service_vnet_integration_unused": {
        "enabled": True,
        "min_days_no_vnet_traffic": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "VNet integration configured but unused (0 traffic to VNet) - $0.15/GB wasted",
    },
    "app_service_old_runtime_version": {
        "enabled": True,
        "min_runtime_age_months": 12,
        "confidence_medium_days": 180,
        "confidence_high_days": 365,
        "description": "Old runtime version (>1 year old) - security risk + missing features (update to latest LTS)",
    },
    # Phase 2 - Detection avec métriques Azure Monitor (8 scenarios)
    "app_service_low_cpu_utilization": {
        "enabled": True,
        "max_avg_cpu_percent": 10,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "CPU utilization <10% avg over 30 days - downsize plan to save 50% ($52/month S2→S1)",
    },
    "app_service_low_memory_utilization": {
        "enabled": True,
        "max_avg_memory_percent": 30,
        "min_observation_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Memory utilization <30% avg over 30 days - downsize to save 40% ($42/month S2→B3)",
    },
    "app_service_low_request_count": {
        "enabled": True,
        "max_requests_per_day": 100,
        "min_observation_days": 30,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "Low request count (<100 req/day) for 30+ days - consider serverless ($70/month S1 waste)",
    },
    "app_service_no_traffic_business_hours": {
        "enabled": True,
        "business_hours_start": 9,
        "business_hours_end": 17,
        "max_requests_business_hours": 10,
        "min_observation_days": 14,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "description": "No traffic during business hours (9-5 PM <10 req) - enable auto-shutdown to save 40% ($28/month)",
    },
    "app_service_high_http_error_rate": {
        "enabled": True,
        "max_error_rate_percent": 50,
        "min_requests_count": 100,
        "min_observation_days": 7,
        "confidence_high_days": 7,
        "description": "HTTP error rate >50% - app misconfigured or broken (waste compute + investigate issues)",
    },
    "app_service_slow_response_time": {
        "enabled": True,
        "max_avg_response_time_seconds": 10,
        "min_observation_days": 7,
        "confidence_medium_days": 7,
        "confidence_high_days": 14,
        "description": "Slow response time (>10s avg) - performance issue or wrong SKU (investigate + optimize)",
    },
    "app_service_auto_scale_never_triggers": {
        "enabled": True,
        "min_days_with_autoscale": 30,
        "max_scale_events": 0,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "Auto-scale configured but never triggered (0 scale events) - fixed instances waste ($140/month for 2× S1)",
    },
    "app_service_cold_start_excessive": {
        "enabled": True,
        "max_cold_start_time_seconds": 30,
        "min_observation_days": 7,
        "confidence_medium_days": 7,
        "confidence_high_days": 14,
        "description": "Cold start time >30s - Always On disabled or wrong SKU (poor user experience + performance issue)",
    },
    # ===== Azure Networking (ExpressRoute, VPN, NICs) (8 scenarios - 100% coverage) =====
    # ExpressRoute Circuit (4 scenarios)
    "expressroute_circuit_not_provisioned": {
        "enabled": True,
        "min_not_provisioned_days": 30,
        "confidence_medium_days": 7,
        "confidence_high_days": 30,
        "confidence_critical_days": 90,
        "description": "ExpressRoute circuit Not Provisioned >30 days - paying $950-6,400/month for unusable circuit (100% waste)",
    },
    "expressroute_circuit_no_connection": {
        "enabled": True,
        "min_no_connection_days": 30,
        "min_age_days": 7,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "ExpressRoute circuit provisioned but no VNet Gateway connection >30 days - 100% waste ($950-6,400/month)",
    },
    "expressroute_gateway_orphaned": {
        "enabled": True,
        "min_age_days": 14,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "ExpressRoute Gateway with NO circuit attached - 100% waste ($139-1,367/month depending on SKU)",
    },
    "expressroute_circuit_underutilized": {
        "enabled": True,
        "max_utilization_threshold": 10.0,
        "min_underutilized_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "description": "ExpressRoute circuit bandwidth <10% utilized - downgrade to save 80% ($760/month 1Gbps→200Mbps)",
    },
    # VPN Gateway (3 scenarios)
    "vpn_gateway_disconnected": {
        "enabled": True,
        "min_disconnected_days": 30,
        "min_age_days": 7,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "VPN Gateway disconnected (all connections down) >30 days - waste ($142-730/month depending on SKU)",
    },
    "vpn_gateway_basic_sku_deprecated": {
        "enabled": True,
        "min_age_days": 1,
        "confidence_high_days": 1,
        "confidence_critical_days": 7,
        "description": "VPN Gateway Basic SKU deprecated - security risk + support ending (upgrade to VpnGw1 required)",
    },
    "vpn_gateway_no_connections": {
        "enabled": True,
        "min_age_days": 14,
        "confidence_medium_days": 14,
        "confidence_high_days": 30,
        "confidence_critical_days": 60,
        "description": "VPN Gateway with 0 connections >14 days - 100% waste ($142-730/month depending on SKU)",
    },
    # Network Interfaces (1 scenario)
    "network_interface_orphaned": {
        "enabled": True,
        "min_age_days": 30,
        "confidence_medium_days": 30,
        "confidence_high_days": 60,
        "confidence_critical_days": 90,
        "description": "Network Interface (NIC) not attached to VM >30 days - small waste but governance issue ($4.32/month per NIC)",
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
