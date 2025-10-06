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

    # Future: Azure and GCP credentials
    # azure_credentials: dict | None = None
    # gcp_credentials: dict | None = None


# Schema for updating cloud account
class CloudAccountUpdate(BaseModel):
    """Schema for updating a cloud account."""

    account_name: str | None = Field(default=None, min_length=1, max_length=255)
    regions: list[str] | None = None
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    # Allow updating credentials
    aws_access_key_id: str | None = Field(default=None, min_length=16, max_length=128)
    aws_secret_access_key: str | None = Field(default=None, min_length=16, max_length=128)

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
    # azure_credentials: dict | None = None
    # gcp_credentials: dict | None = None
