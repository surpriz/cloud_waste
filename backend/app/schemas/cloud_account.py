"""CloudAccount Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# AWS credentials schema (not stored directly, used for encryption)
class AWSCredentials(BaseModel):
    """AWS credentials schema."""

    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=16, max_length=128)
    region: str = Field(default="us-east-1", pattern="^[a-z]{2}-[a-z]+-[0-9]{1}$")


# Azure credentials schema (not stored directly, used for encryption)
class AzureCredentials(BaseModel):
    """Azure credentials schema."""

    tenant_id: str = Field(..., min_length=36, max_length=36, description="Azure AD Tenant ID (GUID)")
    client_id: str = Field(..., min_length=36, max_length=36, description="Azure Service Principal Application/Client ID (GUID)")
    client_secret: str = Field(..., min_length=1, max_length=256, description="Azure Service Principal Client Secret")
    subscription_id: str = Field(..., min_length=36, max_length=36, description="Azure Subscription ID (GUID)")


# GCP credentials schema (not stored directly, used for encryption)
class GCPCredentials(BaseModel):
    """GCP credentials schema."""

    project_id: str = Field(..., min_length=6, max_length=30, description="GCP Project ID")
    service_account_json: str = Field(..., description="GCP Service Account JSON key (as string)")


# Base schema
class CloudAccountBase(BaseModel):
    """Base cloud account schema."""

    provider: str = Field(..., pattern="^(aws|azure|gcp)$")
    account_name: str = Field(..., min_length=1, max_length=255)
    account_identifier: str = Field(..., min_length=1, max_length=255)
    regions: list[str] | None = Field(
        default=None,
        description="List of regions to scan (e.g., ['eu-west-1', 'us-east-1'])",
    )
    resource_groups: list[str] | None = Field(
        default=None,
        description="List of Azure resource groups to scan (e.g., ['rg-prod', 'rg-dev']). If None, all resource groups will be scanned.",
    )
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


# Schema for creating cloud account
class CloudAccountCreate(CloudAccountBase):
    """Schema for creating a cloud account."""

    # AWS credentials (will be encrypted before storage)
    aws_access_key_id: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="AWS Access Key ID (required for AWS)",
    )
    aws_secret_access_key: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="AWS Secret Access Key (required for AWS)",
    )

    # Azure credentials (will be encrypted before storage)
    azure_tenant_id: str | None = Field(
        default=None,
        min_length=36,
        max_length=36,
        description="Azure AD Tenant ID (required for Azure)",
    )
    azure_client_id: str | None = Field(
        default=None,
        min_length=36,
        max_length=36,
        description="Azure Service Principal Client ID (required for Azure)",
    )
    azure_client_secret: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Azure Service Principal Client Secret (required for Azure)",
    )
    azure_subscription_id: str | None = Field(
        default=None,
        min_length=36,
        max_length=36,
        description="Azure Subscription ID (required for Azure)",
    )

    # GCP credentials (will be encrypted before storage)
    gcp_project_id: str | None = Field(
        default=None,
        min_length=6,
        max_length=30,
        description="GCP Project ID (required for GCP)",
    )
    gcp_service_account_json: str | None = Field(
        default=None,
        description="GCP Service Account JSON key (required for GCP)",
    )


# Schema for updating cloud account
class CloudAccountUpdate(BaseModel):
    """Schema for updating a cloud account."""

    account_name: str | None = Field(default=None, min_length=1, max_length=255)
    regions: list[str] | None = None
    resource_groups: list[str] | None = None
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    # Allow updating AWS credentials
    aws_access_key_id: str | None = Field(default=None, min_length=16, max_length=128)
    aws_secret_access_key: str | None = Field(default=None, min_length=16, max_length=128)

    # Allow updating Azure credentials
    azure_tenant_id: str | None = Field(default=None, min_length=36, max_length=36)
    azure_client_id: str | None = Field(default=None, min_length=36, max_length=36)
    azure_client_secret: str | None = Field(default=None, min_length=1, max_length=256)
    azure_subscription_id: str | None = Field(default=None, min_length=36, max_length=36)

    # Allow updating GCP credentials
    gcp_project_id: str | None = Field(default=None, min_length=6, max_length=30)
    gcp_service_account_json: str | None = None

    # Scheduled scan settings
    scheduled_scan_enabled: bool | None = None
    scheduled_scan_frequency: str | None = Field(
        default=None, pattern="^(daily|weekly|monthly)$"
    )
    scheduled_scan_hour: int | None = Field(default=None, ge=0, le=23)
    scheduled_scan_day_of_week: int | None = Field(default=None, ge=0, le=6)
    scheduled_scan_day_of_month: int | None = Field(default=None, ge=1, le=31)


# Schema returned by API
class CloudAccount(CloudAccountBase):
    """Cloud account schema for API responses."""

    id: uuid.UUID
    user_id: uuid.UUID
    last_scan_at: datetime | None = None
    scheduled_scan_enabled: bool
    scheduled_scan_frequency: str
    scheduled_scan_hour: int
    scheduled_scan_day_of_week: int | None = None
    scheduled_scan_day_of_month: int | None = None
    created_at: datetime
    updated_at: datetime

    # Do NOT expose encrypted credentials
    model_config = {"from_attributes": True}


# Schema with decrypted credentials (internal use only, never returned by API)
class CloudAccountWithCredentials(CloudAccount):
    """Cloud account with decrypted credentials (internal use only)."""

    aws_credentials: AWSCredentials | None = None
    azure_credentials: AzureCredentials | None = None
    gcp_credentials: GCPCredentials | None = None
