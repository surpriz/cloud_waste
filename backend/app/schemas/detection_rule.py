"""DetectionRule Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetectionRuleBase(BaseModel):
    """Base detection rule schema."""

    resource_type: str = Field(
        ...,
        pattern="^(ebs_volume|elastic_ip|ebs_snapshot|ec2_instance|load_balancer|rds_instance|fsx_file_system|neptune_cluster|msk_cluster|eks_cluster|sagemaker_endpoint|redshift_cluster|elasticache_cluster|vpn_connection|transit_gateway_attachment|opensearch_domain|global_accelerator|kinesis_stream|vpc_endpoint|documentdb_cluster|s3_bucket|lambda_function|dynamodb_table|managed_disk_unattached|managed_disk_on_stopped_vm|disk_snapshot_orphaned|disk_snapshot_redundant|disk_snapshot_very_old|disk_snapshot_premium_source|disk_snapshot_large_unused|disk_snapshot_full_instead_incremental|disk_snapshot_excessive_retention|disk_snapshot_manual_without_policy|disk_snapshot_never_restored|disk_snapshot_frequent_creation|managed_disk_unnecessary_zrs|managed_disk_unnecessary_cmk|managed_disk_idle|managed_disk_unused_bursting|managed_disk_overprovisioned|managed_disk_underutilized_hdd|public_ip_unassociated|public_ip_on_stopped_resource|public_ip_dynamic_unassociated|public_ip_unnecessary_standard_sku|public_ip_unnecessary_zone_redundancy|public_ip_ddos_protection_unused|public_ip_on_nic_without_vm|public_ip_reserved_but_unused|public_ip_no_traffic|public_ip_very_low_traffic|virtual_machine_deallocated|virtual_machine_stopped_not_deallocated|virtual_machine_never_started|virtual_machine_oversized_premium|virtual_machine_untagged_orphan|virtual_machine_idle|virtual_machine_old_generation|virtual_machine_spot_convertible|virtual_machine_underutilized|virtual_machine_memory_overprovisioned|azure_aks_cluster|nat_gateway_no_subnet|nat_gateway_never_used|nat_gateway_no_public_ip|nat_gateway_single_vm|nat_gateway_redundant|nat_gateway_dev_test_always_on|nat_gateway_unnecessary_zones|nat_gateway_no_traffic|nat_gateway_very_low_traffic|nat_gateway_private_link_alternative|load_balancer_no_backend_instances|load_balancer_all_backends_unhealthy|load_balancer_no_inbound_rules|load_balancer_basic_sku_retired|application_gateway_no_backend_targets|application_gateway_stopped|load_balancer_never_used|load_balancer_no_traffic|application_gateway_no_requests|application_gateway_underutilized)$",
    )
    rules: dict[str, Any] = Field(
        ...,
        description="Custom detection rules (e.g., {'enabled': true, 'min_age_days': 14})",
    )


class DetectionRuleCreate(DetectionRuleBase):
    """Schema for creating a detection rule."""

    pass


class DetectionRuleUpdate(BaseModel):
    """Schema for updating a detection rule."""

    rules: dict[str, Any] | None = None


class DetectionRule(DetectionRuleBase):
    """Detection rule schema for API responses."""

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DetectionRuleWithDefaults(BaseModel):
    """Detection rule with default values shown."""

    resource_type: str
    current_rules: dict[str, Any]
    default_rules: dict[str, Any]
    description: str
