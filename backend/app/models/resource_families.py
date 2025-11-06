"""Resource families mappings for Basic/Expert mode in detection rules."""

from typing import Dict, List

# AWS Resource Families (Big 4 with granular scenarios)
RESOURCE_FAMILIES: Dict[str, List[str]] = {
    # EBS Volumes (10 scenarios)
    "ebs_volume": [
        "ebs_volume_unattached",
        "ebs_volume_on_stopped_instance",
        "ebs_volume_gp2_migration",
        "ebs_volume_unnecessary_io2",
        "ebs_volume_overprovisioned_iops",
        "ebs_volume_overprovisioned_throughput",
        "ebs_volume_idle",
        "ebs_volume_low_iops_usage",
        "ebs_volume_low_throughput_usage",
        "ebs_volume_type_downgrade",
    ],
    # Elastic IPs (10 scenarios)
    "elastic_ip": [
        "elastic_ip_unassociated",
        "elastic_ip_on_stopped_instance",
        "elastic_ip_multiple_per_instance",
        "elastic_ip_on_detached_eni",
        "elastic_ip_never_used",
        "elastic_ip_on_unused_nat_gateway",
        "elastic_ip_idle",
        "elastic_ip_low_traffic",
        "elastic_ip_unused_nat_gateway",
        "elastic_ip_on_failed_instance",
    ],
    # EBS Snapshots (10 scenarios)
    "ebs_snapshot": [
        "ebs_snapshot_orphaned",
        "ebs_snapshot_redundant",
        "ebs_snapshot_unused_ami",
        "ebs_snapshot_old_unused",
        "ebs_snapshot_from_deleted_instance",
        "ebs_snapshot_incomplete_failed",
        "ebs_snapshot_untagged",
        "ebs_snapshot_excessive_retention",
        "ebs_snapshot_duplicate",
        "ebs_snapshot_never_restored",
    ],
    # EC2 Instances (10 scenarios)
    "ec2_instance": [
        "ec2_instance_stopped",
        "ec2_instance_idle_running",
        "ec2_instance_oversized",
        "ec2_instance_old_generation",
        "ec2_instance_burstable_credit_waste",
        "ec2_instance_dev_test_24_7",
        "ec2_instance_untagged",
        "ec2_instance_right_sizing_opportunity",
        "ec2_instance_spot_eligible",
        "ec2_instance_scheduled_unused",
    ],
    # Other AWS resources (grouped but already have single types)
    "load_balancer": ["load_balancer"],
    "rds_instance": ["rds_instance"],
    "fsx_file_system": ["fsx_file_system"],
    "neptune_cluster": ["neptune_cluster"],
    "msk_cluster": ["msk_cluster"],
    "eks_cluster": ["eks_cluster"],
    "sagemaker_endpoint": ["sagemaker_endpoint"],
    "redshift_cluster": ["redshift_cluster"],
    "elasticache_cluster": ["elasticache_cluster"],
    "vpn_connection": ["vpn_connection"],
    "transit_gateway_attachment": ["transit_gateway_attachment"],
    "opensearch_domain": ["opensearch_domain"],
    "global_accelerator": ["global_accelerator"],
    "kinesis_stream": ["kinesis_stream"],
    "vpc_endpoint": ["vpc_endpoint"],
    "documentdb_cluster": ["documentdb_cluster"],
    "s3_bucket": ["s3_bucket"],
    "lambda_function": ["lambda_function"],
    "dynamodb_table": ["dynamodb_table"],
}

# Azure Resource Families (logically grouped)
AZURE_RESOURCE_FAMILIES: Dict[str, List[str]] = {
    "managed_disk": [
        "managed_disk_unattached",
        "managed_disk_on_stopped_vm",
        "managed_disk_unnecessary_zrs",
        "managed_disk_unnecessary_cmk",
        "managed_disk_idle",
        "managed_disk_unused_bursting",
        "managed_disk_overprovisioned",
        "managed_disk_underutilized_hdd",
    ],
    "disk_snapshot": [
        "disk_snapshot_orphaned",
        "disk_snapshot_redundant",
        "disk_snapshot_very_old",
        "disk_snapshot_premium_source",
        "disk_snapshot_large_unused",
        "disk_snapshot_full_instead_incremental",
        "disk_snapshot_excessive_retention",
        "disk_snapshot_manual_without_policy",
        "disk_snapshot_never_restored",
        "disk_snapshot_frequent_creation",
    ],
    "public_ip": [
        "public_ip_unassociated",
        "public_ip_on_stopped_resource",
        "public_ip_dynamic_unassociated",
        "public_ip_unnecessary_standard_sku",
        "public_ip_unnecessary_zone_redundancy",
        "public_ip_ddos_protection_unused",
        "public_ip_on_nic_without_vm",
        "public_ip_reserved_but_unused",
        "public_ip_no_traffic",
        "public_ip_very_low_traffic",
    ],
    "virtual_machine": [
        "virtual_machine_deallocated",
        "virtual_machine_stopped_not_deallocated",
        "virtual_machine_never_started",
        "virtual_machine_oversized_premium",
        "virtual_machine_untagged_orphan",
        "virtual_machine_idle",
        "virtual_machine_old_generation",
        "virtual_machine_spot_convertible",
        "virtual_machine_underutilized",
        "virtual_machine_memory_overprovisioned",
    ],
    # Azure - NAT Gateway scenarios
    "nat_gateway": [
        "nat_gateway_no_subnet",
        "nat_gateway_never_used",
        "nat_gateway_no_public_ip",
        "nat_gateway_single_vm",
        "nat_gateway_redundant",
        "nat_gateway_dev_test_always_on",
        "nat_gateway_unnecessary_zones",
        "nat_gateway_no_traffic",
        "nat_gateway_very_low_traffic",
        "nat_gateway_private_link_alternative",
    ],
    # Other Azure resources (each as its own family)
    "azure_aks_cluster": ["azure_aks_cluster"],
    # ... Add more as needed
}

# GCP Resource Families (logically grouped - 12 major services with ~152 scenarios)
GCP_RESOURCE_FAMILIES: Dict[str, List[str]] = {
    # Compute Engine Instances
    "compute_instance": [
        "compute_instance_stopped",
        "compute_instance_idle",
        "compute_instance_overprovisioned",
        "compute_instance_old_generation",
        "compute_instance_no_spot",
        "compute_instance_untagged",
        "compute_instance_memory_waste",
        "compute_instance_rightsizing",
        "compute_instance_burstable_waste",
    ],
    # Persistent Disks
    "persistent_disk": [
        "persistent_disk_unattached",
        "persistent_disk_attached_stopped",
        "persistent_disk_never_used",
        "persistent_disk_orphan_snapshots",
        "persistent_disk_oversized",
        "persistent_disk_underutilized",
        "persistent_disk_overprovisioned_type",
        "persistent_disk_old_type",
        "persistent_disk_readonly",
        "persistent_disk_untagged",
    ],
    # Cloud SQL
    "cloud_sql": [
        "cloud_sql_stopped",
        "cloud_sql_idle",
        "cloud_sql_overprovisioned",
        "cloud_sql_storage_overprovisioned",
        "cloud_sql_unnecessary_ha",
        "cloud_sql_old_machine_type",
        "cloud_sql_unused_replicas",
        "cloud_sql_zero_io",
        "cloud_sql_untagged",
        "cloud_sql_alternative_cost_per_gb",
    ],
    # GKE Clusters
    "gke_cluster": [
        "gke_cluster_empty",
        "gke_cluster_no_workloads",
        "gke_cluster_no_autoscaling",
        "gke_cluster_nodes_inactive",
        "gke_cluster_nodes_underutilized",
        "gke_cluster_nodepool_overprovisioned",
        "gke_cluster_pods_overrequested",
        "gke_cluster_old_machine_type",
        "gke_cluster_untagged",
    ],
    # Dataflow Jobs
    "dataflow": [
        "dataflow_streaming_job_idle",
        "dataflow_job_low_cpu_utilization",
        "dataflow_job_low_throughput",
        "dataflow_job_oversized_workers",
        "dataflow_oversized_disk",
        "dataflow_no_max_workers",
        "dataflow_batch_without_flexrs",
        "dataflow_streaming_without_engine",
        "dataflow_streaming_high_backlog",
        "dataflow_job_failed_with_resources",
    ],
    # Dataproc Clusters
    "dataproc_cluster": [
        "dataproc_cluster_stopped",
        "dataproc_cluster_idle",
        "dataproc_cluster_low_cpu_utilization",
        "dataproc_cluster_low_memory_utilization",
        "dataproc_cluster_no_autoscaling",
        "dataproc_cluster_oversized_workers",
        "dataproc_cluster_unnecessary_ssd",
        "dataproc_cluster_underutilized_hdfs",
        "dataproc_cluster_no_scheduled_delete",
        "dataproc_cluster_single_node_prod",
    ],
    # BigQuery
    "bigquery": [
        "bigquery_unused_materialized_views",
        "bigquery_never_queried_tables",
        "bigquery_empty_datasets",
        "bigquery_unpartitioned_large_tables",
        "bigquery_unclustered_large_tables",
        "bigquery_no_expiration",
        "bigquery_active_storage_waste",
        "bigquery_expensive_queries",
        "bigquery_ondemand_vs_flatrate",
        "bigquery_untagged_datasets",
    ],
    # Memorystore Redis
    "memorystore_redis": [
        "memorystore_redis_idle",
        "memorystore_redis_overprovisioned",
        "memorystore_redis_low_hit_rate",
        "memorystore_redis_wrong_tier",
        "memorystore_redis_wrong_size",
        "memorystore_redis_wrong_eviction",
        "memorystore_redis_cross_zone_traffic",
        "memorystore_redis_high_connection_churn",
        "memorystore_redis_no_cud",
        "memorystore_redis_untagged",
    ],
    # Cloud Functions
    "gcp_cloud_function": [
        "gcp_cloud_function_never_invoked",
        "gcp_cloud_function_memory_overprovisioning",
        "gcp_cloud_function_excessive_timeout",
        "gcp_cloud_function_excessive_concurrency",
        "gcp_cloud_function_excessive_max_instances",
        "gcp_cloud_function_idle_min_instances",
        "gcp_cloud_function_duplicate",
        "gcp_cloud_function_cold_start_over_optimization",
        "gcp_cloud_function_untagged",
    ],
    # Cloud Run
    "gcp_cloud_run": [
        "gcp_cloud_run_never_used",
        "gcp_cloud_run_overprovisioned",
        "gcp_cloud_run_excessive_min_instances",
        "gcp_cloud_run_excessive_max_instances",
        "gcp_cloud_run_idle_min_instances",
        "gcp_cloud_run_nonprod_min_instances",
        "gcp_cloud_run_cpu_always_allocated",
        "gcp_cloud_run_low_concurrency",
        "gcp_cloud_run_multi_region_redundant",
        "gcp_cloud_run_untagged",
    ],
    # Vertex AI
    "vertex_ai": [
        "vertex_ai_idle_endpoints",
        "vertex_ai_zero_predictions",
        "vertex_ai_overprovisioned_machines",
        "vertex_ai_unused_traffic_split",
        "vertex_ai_old_model_versions",
        "vertex_ai_gpu_waste",
        "vertex_ai_failed_training_jobs",
        "vertex_ai_unused_feature_store",
        "vertex_ai_untagged_endpoints",
    ],
    # AI Platform Notebooks
    "notebook_instance": [
        "notebook_instance_stopped",
        "notebook_instance_idle_no_shutdown",
        "notebook_instance_running_no_activity",
        "notebook_instance_oversized_machine_type",
        "notebook_instance_oversized_disk",
        "notebook_instance_low_cpu_utilization",
        "notebook_instance_low_memory_utilization",
        "notebook_instance_low_gpu_utilization",
        "notebook_instance_gpu_attached_unused",
        "notebook_instance_unnecessary_gpu_in_dev",
    ],
}

# Inverse mapping: resource_type -> family
RESOURCE_TYPE_TO_FAMILY: Dict[str, str] = {}
for family, types in RESOURCE_FAMILIES.items():
    for resource_type in types:
        RESOURCE_TYPE_TO_FAMILY[resource_type] = family

for family, types in AZURE_RESOURCE_FAMILIES.items():
    for resource_type in types:
        RESOURCE_TYPE_TO_FAMILY[resource_type] = family

for family, types in GCP_RESOURCE_FAMILIES.items():
    for resource_type in types:
        RESOURCE_TYPE_TO_FAMILY[resource_type] = family


def get_resource_family(resource_type: str) -> str:
    """Get the family name for a given resource_type."""
    return RESOURCE_TYPE_TO_FAMILY.get(resource_type, resource_type)


def get_family_scenarios(family: str) -> List[str]:
    """Get all scenario resource_types for a given family."""
    if family in RESOURCE_FAMILIES:
        return RESOURCE_FAMILIES[family]
    elif family in AZURE_RESOURCE_FAMILIES:
        return AZURE_RESOURCE_FAMILIES[family]
    elif family in GCP_RESOURCE_FAMILIES:
        return GCP_RESOURCE_FAMILIES[family]
    else:
        return [family]  # Single-scenario family


def extract_common_params(rules_dict: Dict[str, any]) -> Dict[str, any]:
    """
    Extract common parameters from a rule dictionary.

    Common params are typically: enabled, min_age_days, confidence_threshold_days, etc.
    """
    common_keys = [
        "enabled",
        "min_age_days",
        "confidence_threshold_days",
        "min_stopped_days",
        "description",
    ]

    return {key: rules_dict.get(key) for key in common_keys if key in rules_dict}
