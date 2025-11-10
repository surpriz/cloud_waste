"""Tests for cloud accounts API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import cloud_account as cloud_account_crud
from app.models.user import User
from app.schemas.cloud_account import CloudAccountCreate


class TestAccountsAPI:
    """Test cloud accounts API endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.accounts.validate_aws_credentials")
    async def test_create_aws_account_success(
        self,
        mock_validate,
        authenticated_async_client: AsyncClient,
        test_user: User,
    ):
        """Test creating an AWS cloud account with valid credentials."""
        # Mock successful AWS validation
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }

        account_data = {
            "provider": "aws",
            "account_name": "Test AWS Account",
            "account_identifier": "123456789012",
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "regions": ["us-east-1", "eu-west-1"],
        }

        response = await authenticated_async_client.post(
            "/api/v1/accounts/", json=account_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "aws"
        assert data["account_name"] == "Test AWS Account"
        assert data["account_identifier"] == "123456789012"
        assert data["regions"] == ["us-east-1", "eu-west-1"]
        # Credentials should not be returned
        assert "aws_access_key_id" not in data
        assert "credentials_encrypted" not in data

    @pytest.mark.asyncio
    async def test_create_account_missing_aws_credentials(
        self, authenticated_async_client: AsyncClient
    ):
        """Test creating AWS account without credentials returns 400."""
        account_data = {
            "provider": "aws",
            "account_name": "Test AWS",
            "account_identifier": "123456789012",
            # Missing AWS credentials
        }

        response = await authenticated_async_client.post(
            "/api/v1/accounts/", json=account_data
        )

        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.api.v1.accounts.validate_aws_credentials")
    async def test_create_account_invalid_aws_credentials(
        self, mock_validate, authenticated_async_client: AsyncClient
    ):
        """Test creating AWS account with invalid credentials returns 400."""
        # Mock AWS validation failure
        from app.services.aws_validator import AWSValidationError

        mock_validate.side_effect = AWSValidationError("Invalid credentials")

        account_data = {
            "provider": "aws",
            "account_name": "Test AWS",
            "account_identifier": "123456789012",
            "aws_access_key_id": "AKIAINVALIDKEY123",
            "aws_secret_access_key": "invalidSecret123456789012345678901234",
        }

        response = await authenticated_async_client.post(
            "/api/v1/accounts/", json=account_data
        )

        assert response.status_code == 400
        assert "validation failed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_cloud_accounts(
        self,
        authenticated_async_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing user's cloud accounts."""
        # Create test accounts
        for i in range(3):
            account_data = CloudAccountCreate(
                provider="aws",
                account_name=f"Account {i}",
                account_identifier=f"12345678901{i}",
                aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
                aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            )
            await cloud_account_crud.create_cloud_account(
                db_session, test_user.id, account_data
            )

        response = await authenticated_async_client.get("/api/v1/accounts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Verify no credentials in response
        for account in data:
            assert "credentials_encrypted" not in account
            assert "aws_access_key_id" not in account

    @pytest.mark.asyncio
    async def test_get_cloud_account_by_id(
        self,
        authenticated_async_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting a specific cloud account."""
        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        response = await authenticated_async_client.get(
            f"/api/v1/accounts/{account.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(account.id)
        assert data["account_name"] == "Test Account"

    @pytest.mark.asyncio
    async def test_get_account_not_found(
        self, authenticated_async_client: AsyncClient
    ):
        """Test getting non-existent account returns 404."""
        import uuid

        fake_id = str(uuid.uuid4())
        response = await authenticated_async_client.get(f"/api/v1/accounts/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.v1.accounts.validate_aws_credentials")
    async def test_update_cloud_account(
        self,
        mock_validate,
        authenticated_async_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test updating cloud account."""
        # Mock AWS validation
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }

        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Original Name",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Update account
        update_data = {
            "account_name": "Updated Name",
            "description": "Updated description",
        }
        response = await authenticated_async_client.patch(
            f"/api/v1/accounts/{account.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["account_name"] == "Updated Name"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_cloud_account(
        self,
        authenticated_async_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test deleting cloud account."""
        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="To Delete",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Delete account
        response = await authenticated_async_client.delete(
            f"/api/v1/accounts/{account.id}"
        )

        assert response.status_code == 204  # No Content

        # Verify account is deleted
        get_response = await authenticated_async_client.get(
            f"/api/v1/accounts/{account.id}"
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, async_client: AsyncClient):
        """Test accessing accounts endpoints without authentication."""
        response = await async_client.get("/api/v1/accounts/")

        assert response.status_code == 403  # Forbidden without auth
