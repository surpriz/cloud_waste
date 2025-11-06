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

# Inverse mapping: resource_type -> family
RESOURCE_TYPE_TO_FAMILY: Dict[str, str] = {}
for family, types in RESOURCE_FAMILIES.items():
    for resource_type in types:
        RESOURCE_TYPE_TO_FAMILY[resource_type] = family

for family, types in AZURE_RESOURCE_FAMILIES.items():
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
