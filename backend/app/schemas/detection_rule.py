"""DetectionRule Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetectionRuleBase(BaseModel):
    """Base detection rule schema."""

    resource_type: str = Field(
        ...,
        pattern="^(ebs_volume|elastic_ip|ebs_snapshot|ec2_instance|nat_gateway|load_balancer|rds_instance|fsx_file_system|neptune_cluster|msk_cluster|eks_cluster|sagemaker_endpoint|redshift_cluster|elasticache_cluster|vpn_connection|transit_gateway_attachment|opensearch_domain|global_accelerator|kinesis_stream|vpc_endpoint|documentdb_cluster|s3_bucket|lambda_function|dynamodb_table|managed_disk_unattached|managed_disk_on_stopped_vm|disk_snapshot_orphaned|disk_snapshot_redundant|managed_disk_unnecessary_zrs|managed_disk_unnecessary_cmk|managed_disk_idle|managed_disk_unused_bursting|managed_disk_overprovisioned|managed_disk_underutilized_hdd|public_ip_unassociated|virtual_machine_deallocated|azure_aks_cluster)$",
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
