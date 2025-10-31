"""Cloud accounts API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.crud import cloud_account as cloud_account_crud
from app.models.user import User
from app.schemas.cloud_account import (
    AWSCredentials,
    AzureCredentials,
    GCPCredentials,
    CloudAccount,
    CloudAccountCreate,
    CloudAccountUpdate,
)
from app.services.aws_validator import AWSValidationError, validate_aws_credentials
from app.services.azure_validator import AzureValidationError, validate_azure_credentials

router = APIRouter()


@router.post("/", response_model=CloudAccount, status_code=status.HTTP_201_CREATED)
async def create_cloud_account(
    account_in: CloudAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CloudAccount:
    """
    Create a new cloud account connection.

    This endpoint:
    1. Validates the provided credentials
    2. Encrypts the credentials before storage
    3. Creates the cloud account record

    Args:
        account_in: Cloud account creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created cloud account (without credentials)

    Raises:
        HTTPException: If validation fails or account creation fails
    """
    # Validate credentials before storing
    if account_in.provider == "aws":
        if not account_in.aws_access_key_id or not account_in.aws_secret_access_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AWS Access Key ID and Secret Access Key are required for AWS accounts",
            )

        # Validate AWS credentials
        try:
            credentials = AWSCredentials(
                access_key_id=account_in.aws_access_key_id,
                secret_access_key=account_in.aws_secret_access_key,
                region=account_in.regions[0] if account_in.regions else "us-east-1",
            )
            account_info = await validate_aws_credentials(credentials)

            # Optionally update account_identifier with actual AWS account ID
            if not account_in.account_identifier:
                account_in.account_identifier = account_info["account_id"]

        except AWSValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AWS credentials validation failed: {str(e)}",
            )

    elif account_in.provider == "azure":
        if (
            not account_in.azure_tenant_id
            or not account_in.azure_client_id
            or not account_in.azure_client_secret
            or not account_in.azure_subscription_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Azure Tenant ID, Client ID, Client Secret, and Subscription ID are required for Azure accounts",
            )

        # Validate Azure credentials
        try:
            credentials = AzureCredentials(
                tenant_id=account_in.azure_tenant_id,
                client_id=account_in.azure_client_id,
                client_secret=account_in.azure_client_secret,
                subscription_id=account_in.azure_subscription_id,
            )
            subscription_info = await validate_azure_credentials(credentials)

            # Optionally update account_identifier with subscription ID
            if not account_in.account_identifier:
                account_in.account_identifier = subscription_info["subscription_id"]

        except AzureValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Azure credentials validation failed: {str(e)}",
            )

    elif account_in.provider == "gcp":
        if not account_in.gcp_project_id or not account_in.gcp_service_account_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GCP Project ID and Service Account JSON are required for GCP accounts",
            )

        # For MVP, we skip validation and directly create the account
        # GCP validation will be implemented in Phase 2
        if not account_in.account_identifier:
            account_in.account_identifier = account_in.gcp_project_id

    # Create cloud account with encrypted credentials
    try:
        cloud_account = await cloud_account_crud.create_cloud_account(
            db=db,
            user_id=current_user.id,
            account_in=account_in,
        )
        return cloud_account

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/validate-credentials", response_model=dict)
async def validate_credentials_before_creation(
    credentials_data: CloudAccountCreate,
) -> dict:
    """
    Validate cloud provider credentials without creating an account.

    This endpoint allows users to test their credentials before account creation,
    providing immediate feedback on whether the credentials are valid.

    Args:
        credentials_data: Cloud account credentials to validate

    Returns:
        Dict with validation result including provider info

    Raises:
        HTTPException: If validation fails or required fields are missing
    """
    if credentials_data.provider == "aws":
        if not credentials_data.aws_access_key_id or not credentials_data.aws_secret_access_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AWS Access Key ID and Secret Access Key are required",
            )

        credentials = AWSCredentials(
            access_key_id=credentials_data.aws_access_key_id,
            secret_access_key=credentials_data.aws_secret_access_key,
            region=credentials_data.regions[0] if credentials_data.regions else "us-east-1",
        )

        try:
            account_info = await validate_aws_credentials(credentials)
            return {
                "valid": True,
                "provider": "aws",
                "account_id": account_info["account_id"],
                "message": f"✅ AWS credentials are valid! Account ID: {account_info['account_id']}",
            }
        except AWSValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"❌ AWS validation failed: {str(e)}",
            )

    elif credentials_data.provider == "azure":
        if not all([
            credentials_data.azure_tenant_id,
            credentials_data.azure_client_id,
            credentials_data.azure_client_secret,
            credentials_data.azure_subscription_id,
        ]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Azure Tenant ID, Client ID, Client Secret, and Subscription ID are required",
            )

        credentials = AzureCredentials(
            tenant_id=credentials_data.azure_tenant_id,
            client_id=credentials_data.azure_client_id,
            client_secret=credentials_data.azure_client_secret,
            subscription_id=credentials_data.azure_subscription_id,
        )

        try:
            subscription_info = await validate_azure_credentials(credentials)
            return {
                "valid": True,
                "provider": "azure",
                "subscription_id": subscription_info["subscription_id"],
                "subscription_name": subscription_info.get("subscription_name", "N/A"),
                "message": f"✅ Azure credentials are valid! Subscription: {subscription_info.get('subscription_name', subscription_info['subscription_id'])}",
            }
        except AzureValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"❌ Azure validation failed: {str(e)}",
            )

    elif credentials_data.provider == "gcp":
        if not credentials_data.gcp_project_id or not credentials_data.gcp_service_account_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GCP Project ID and Service Account JSON are required",
            )

        # For MVP, we skip actual validation and return success
        # GCP validation will be implemented in Phase 2
        try:
            import json
            json_data = json.loads(credentials_data.gcp_service_account_json)
            project_id = json_data.get("project_id", credentials_data.gcp_project_id)

            return {
                "valid": True,
                "provider": "gcp",
                "project_id": project_id,
                "message": f"✅ GCP credentials format is valid! Project ID: {project_id}",
            }
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"❌ Invalid JSON format for Service Account: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"❌ GCP validation failed: {str(e)}",
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {credentials_data.provider}",
        )


@router.get("/", response_model=list[CloudAccount])
async def list_cloud_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 100,
) -> list[CloudAccount]:
    """
    List all cloud accounts for the current user.

    Args:
        db: Database session
        current_user: Current authenticated user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of cloud accounts (without credentials)
    """
    accounts = await cloud_account_crud.get_cloud_accounts_by_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return accounts


@router.get("/{account_id}", response_model=CloudAccount)
async def get_cloud_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CloudAccount:
    """
    Get a specific cloud account by ID.

    Args:
        account_id: Cloud account UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Cloud account (without credentials)

    Raises:
        HTTPException: If account not found
    """
    account = await cloud_account_crud.get_cloud_account_by_id(
        db=db,
        account_id=account_id,
        user_id=current_user.id,
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud account not found",
        )

    return account


@router.patch("/{account_id}", response_model=CloudAccount)
async def update_cloud_account(
    account_id: uuid.UUID,
    account_in: CloudAccountUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CloudAccount:
    """
    Update a cloud account.

    Note: If updating AWS credentials, both access_key_id and secret_access_key
    must be provided together.

    Args:
        account_id: Cloud account UUID
        account_in: Cloud account update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated cloud account (without credentials)

    Raises:
        HTTPException: If account not found or validation fails
    """
    # Get existing account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db=db,
        account_id=account_id,
        user_id=current_user.id,
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud account not found",
        )

    # If updating AWS credentials, validate them
    if account_in.aws_access_key_id and account_in.aws_secret_access_key:
        try:
            credentials = AWSCredentials(
                access_key_id=account_in.aws_access_key_id,
                secret_access_key=account_in.aws_secret_access_key,
                region=account.regions[0] if account.regions else "us-east-1",
            )
            await validate_aws_credentials(credentials)

        except AWSValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AWS credentials validation failed: {str(e)}",
            )

    # If updating Azure credentials, validate them
    if (
        account_in.azure_tenant_id
        and account_in.azure_client_id
        and account_in.azure_client_secret
        and account_in.azure_subscription_id
    ):
        try:
            credentials = AzureCredentials(
                tenant_id=account_in.azure_tenant_id,
                client_id=account_in.azure_client_id,
                client_secret=account_in.azure_client_secret,
                subscription_id=account_in.azure_subscription_id,
            )
            await validate_azure_credentials(credentials)

        except AzureValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Azure credentials validation failed: {str(e)}",
            )

    # Update account
    updated_account = await cloud_account_crud.update_cloud_account(
        db=db,
        db_account=account,
        account_in=account_in,
    )

    return updated_account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Delete a cloud account.

    Args:
        account_id: Cloud account UUID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If account not found
    """
    # Get existing account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db=db,
        account_id=account_id,
        user_id=current_user.id,
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud account not found",
        )

    # Delete account
    await cloud_account_crud.delete_cloud_account(db=db, db_account=account)


@router.post("/{account_id}/validate", response_model=dict)
async def validate_cloud_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """
    Validate cloud account credentials and permissions.

    This endpoint re-validates the stored credentials and checks
    for required read permissions.

    Args:
        account_id: Cloud account UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Validation result with account info and permissions

    Raises:
        HTTPException: If account not found or validation fails
    """
    # Get existing account
    account = await cloud_account_crud.get_cloud_account_by_id(
        db=db,
        account_id=account_id,
        user_id=current_user.id,
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud account not found",
        )

    # Get decrypted credentials (internal use only)
    account_with_creds = await cloud_account_crud.get_decrypted_credentials(account)

    if account.provider == "aws" and account_with_creds.aws_credentials:
        try:
            # Validate credentials
            account_info = await validate_aws_credentials(account_with_creds.aws_credentials)

            # Check permissions
            from app.services.aws_validator import check_aws_read_permissions

            permissions = await check_aws_read_permissions(account_with_creds.aws_credentials)

            return {
                "status": "valid",
                "provider": "aws",
                "account_info": account_info,
                "permissions": permissions,
            }

        except AWSValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {str(e)}",
            )

    elif account.provider == "azure" and account_with_creds.azure_credentials:
        try:
            # Validate credentials
            subscription_info = await validate_azure_credentials(account_with_creds.azure_credentials)

            # Check permissions
            from app.services.azure_validator import check_azure_read_permissions

            permissions = await check_azure_read_permissions(account_with_creds.azure_credentials)

            return {
                "status": "valid",
                "provider": "azure",
                "subscription_info": subscription_info,
                "permissions": permissions,
            }

        except AzureValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {str(e)}",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Provider {account.provider} is not yet supported for validation",
    )
