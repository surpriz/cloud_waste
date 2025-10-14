"""CRUD operations for CloudAccount model."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import credential_encryption
from app.models.cloud_account import CloudAccount
from app.schemas.cloud_account import (
    AWSCredentials,
    AzureCredentials,
    CloudAccountCreate,
    CloudAccountUpdate,
    CloudAccountWithCredentials,
)


async def get_cloud_account_by_id(
    db: AsyncSession,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CloudAccount | None:
    """
    Get cloud account by ID for a specific user.

    Args:
        db: Database session
        account_id: Cloud account UUID
        user_id: User UUID (for security check)

    Returns:
        CloudAccount object or None if not found
    """
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id,
            CloudAccount.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_cloud_accounts_by_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[CloudAccount]:
    """
    Get all cloud accounts for a user.

    Args:
        db: Database session
        user_id: User UUID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of CloudAccount objects
    """
    result = await db.execute(
        select(CloudAccount)
        .where(CloudAccount.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .order_by(CloudAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def create_cloud_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_in: CloudAccountCreate,
) -> CloudAccount:
    """
    Create new cloud account with encrypted credentials.

    Args:
        db: Database session
        user_id: User UUID
        account_in: Cloud account creation schema

    Returns:
        Created CloudAccount object

    Raises:
        ValueError: If required credentials are missing for the provider
    """
    # Prepare credentials for encryption based on provider
    credentials_dict = {}

    if account_in.provider == "aws":
        if not account_in.aws_access_key_id or not account_in.aws_secret_access_key:
            raise ValueError("AWS credentials (access_key_id and secret_access_key) are required")

        credentials_dict = {
            "access_key_id": account_in.aws_access_key_id,
            "secret_access_key": account_in.aws_secret_access_key,
        }
    elif account_in.provider == "azure":
        if (
            not account_in.azure_tenant_id
            or not account_in.azure_client_id
            or not account_in.azure_client_secret
            or not account_in.azure_subscription_id
        ):
            raise ValueError(
                "Azure credentials (tenant_id, client_id, client_secret, subscription_id) are required"
            )

        credentials_dict = {
            "tenant_id": account_in.azure_tenant_id,
            "client_id": account_in.azure_client_id,
            "client_secret": account_in.azure_client_secret,
            "subscription_id": account_in.azure_subscription_id,
        }
    # Future providers: gcp
    # elif account_in.provider == "gcp":
    #     ...

    # Encrypt credentials
    credentials_json = json.dumps(credentials_dict)
    encrypted_credentials = credential_encryption.encrypt(credentials_json)

    # Create cloud account
    db_account = CloudAccount(
        user_id=user_id,
        provider=account_in.provider,
        account_name=account_in.account_name,
        account_identifier=account_in.account_identifier,
        credentials_encrypted=encrypted_credentials,
        regions=account_in.regions,
        resource_groups=account_in.resource_groups,
        description=account_in.description,
        is_active=account_in.is_active,
    )

    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    return db_account


async def update_cloud_account(
    db: AsyncSession,
    db_account: CloudAccount,
    account_in: CloudAccountUpdate,
) -> CloudAccount:
    """
    Update existing cloud account.

    Args:
        db: Database session
        db_account: Existing CloudAccount object
        account_in: Cloud account update schema

    Returns:
        Updated CloudAccount object
    """
    update_data = account_in.model_dump(exclude_unset=True)

    # Handle AWS credentials update if provided
    if "aws_access_key_id" in update_data and "aws_secret_access_key" in update_data:
        credentials_dict = {
            "access_key_id": update_data.pop("aws_access_key_id"),
            "secret_access_key": update_data.pop("aws_secret_access_key"),
        }
        credentials_json = json.dumps(credentials_dict)
        encrypted_credentials = credential_encryption.encrypt(credentials_json)
        update_data["credentials_encrypted"] = encrypted_credentials
    else:
        # Remove individual AWS credential fields if only one was provided
        update_data.pop("aws_access_key_id", None)
        update_data.pop("aws_secret_access_key", None)

    # Handle Azure credentials update if all four fields provided
    if (
        "azure_tenant_id" in update_data
        and "azure_client_id" in update_data
        and "azure_client_secret" in update_data
        and "azure_subscription_id" in update_data
    ):
        credentials_dict = {
            "tenant_id": update_data.pop("azure_tenant_id"),
            "client_id": update_data.pop("azure_client_id"),
            "client_secret": update_data.pop("azure_client_secret"),
            "subscription_id": update_data.pop("azure_subscription_id"),
        }
        credentials_json = json.dumps(credentials_dict)
        encrypted_credentials = credential_encryption.encrypt(credentials_json)
        update_data["credentials_encrypted"] = encrypted_credentials
    else:
        # Remove individual Azure credential fields if not all provided
        update_data.pop("azure_tenant_id", None)
        update_data.pop("azure_client_id", None)
        update_data.pop("azure_client_secret", None)
        update_data.pop("azure_subscription_id", None)

    # Update fields
    for field, value in update_data.items():
        setattr(db_account, field, value)

    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    return db_account


async def delete_cloud_account(
    db: AsyncSession,
    db_account: CloudAccount,
) -> bool:
    """
    Delete cloud account.

    Args:
        db: Database session
        db_account: CloudAccount object to delete

    Returns:
        True if deleted successfully
    """
    await db.delete(db_account)
    await db.commit()
    return True


async def get_decrypted_credentials(
    db_account: CloudAccount,
) -> CloudAccountWithCredentials:
    """
    Get cloud account with decrypted credentials.

    SECURITY WARNING: This function returns decrypted credentials.
    Use only for internal operations (AWS API calls, validation).
    NEVER return this to API responses.

    Args:
        db_account: CloudAccount object

    Returns:
        CloudAccountWithCredentials with decrypted credentials
    """
    # Decrypt credentials
    decrypted_json = credential_encryption.decrypt(db_account.credentials_encrypted)
    credentials_dict = json.loads(decrypted_json)

    # Parse based on provider
    aws_credentials = None
    azure_credentials = None

    if db_account.provider == "aws":
        aws_credentials = AWSCredentials(
            access_key_id=credentials_dict["access_key_id"],
            secret_access_key=credentials_dict["secret_access_key"],
            region=db_account.regions[0] if db_account.regions else "us-east-1",
        )
    elif db_account.provider == "azure":
        azure_credentials = AzureCredentials(
            tenant_id=credentials_dict["tenant_id"],
            client_id=credentials_dict["client_id"],
            client_secret=credentials_dict["client_secret"],
            subscription_id=credentials_dict["subscription_id"],
        )

    # Create response with decrypted credentials
    return CloudAccountWithCredentials(
        id=db_account.id,
        user_id=db_account.user_id,
        provider=db_account.provider,
        account_name=db_account.account_name,
        account_identifier=db_account.account_identifier,
        regions=db_account.regions,
        description=db_account.description,
        is_active=db_account.is_active,
        last_scan_at=db_account.last_scan_at,
        scheduled_scan_enabled=db_account.scheduled_scan_enabled,
        scheduled_scan_frequency=db_account.scheduled_scan_frequency,
        scheduled_scan_hour=db_account.scheduled_scan_hour,
        scheduled_scan_day_of_week=db_account.scheduled_scan_day_of_week,
        scheduled_scan_day_of_month=db_account.scheduled_scan_day_of_month,
        created_at=db_account.created_at,
        updated_at=db_account.updated_at,
        aws_credentials=aws_credentials,
        azure_credentials=azure_credentials,
    )
