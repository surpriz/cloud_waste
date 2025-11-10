"""Tests for CloudAccount CRUD operations."""

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import cloud_account as cloud_account_crud
from app.core.security import credential_encryption
from app.models.user import User
from app.models.cloud_account import CloudAccount
from app.schemas.cloud_account import CloudAccountCreate, CloudAccountUpdate


class TestCloudAccountCRUD:
    """Test CRUD operations for CloudAccount model."""

    @pytest.mark.asyncio
    async def test_create_aws_cloud_account(self, db_session: AsyncSession, test_user: User):
        """Test creating an AWS cloud account with encrypted credentials."""
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            regions=["us-east-1", "eu-west-1"],
            description="Test AWS account",
        )

        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        assert account.id is not None
        assert account.user_id == test_user.id
        assert account.provider == "aws"
        assert account.account_name == "Test AWS Account"
        assert account.account_identifier == "123456789012"
        assert account.regions == ["us-east-1", "eu-west-1"]
        assert account.credentials_encrypted is not None
        assert account.is_active is True

        # Verify credentials are encrypted (not plain text)
        assert b"AKIAIOSFODNN7EXAMPLE" not in account.credentials_encrypted

    @pytest.mark.asyncio
    async def test_create_azure_cloud_account(self, db_session: AsyncSession, test_user: User):
        """Test creating an Azure cloud account."""
        account_data = CloudAccountCreate(
            provider="azure",
            account_name="Test Azure Account",
            account_identifier="azure-sub-123",
            azure_tenant_id="12345678-1234-1234-1234-123456789abc",
            azure_client_id="87654321-4321-4321-4321-abc987654321",
            azure_client_secret="secret-123-very-long-secret-key",
            azure_subscription_id="abcdef12-3456-7890-abcd-ef1234567890",
            description="Test Azure account",
        )

        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        assert account.id is not None
        assert account.provider == "azure"
        assert account.account_name == "Test Azure Account"
        # Credentials should be encrypted
        assert b"tenant-123" not in account.credentials_encrypted

    @pytest.mark.asyncio
    async def test_create_aws_account_missing_credentials(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test creating AWS account without required credentials raises error."""
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS Account",
            account_identifier="123456789012",
            # Missing credentials
        )

        with pytest.raises(ValueError, match="AWS credentials .* are required"):
            await cloud_account_crud.create_cloud_account(
                db_session, test_user.id, account_data
            )

    @pytest.mark.asyncio
    async def test_create_azure_account_missing_credentials(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test creating Azure account without all required credentials raises error."""
        account_data = CloudAccountCreate(
            provider="azure",
            account_name="Test Azure Account",
            account_identifier="azure-sub-123",
            azure_tenant_id="12345678-1234-1234-1234-123456789abc",
            # Missing other credentials
        )

        with pytest.raises(ValueError, match="Azure credentials .* are required"):
            await cloud_account_crud.create_cloud_account(
                db_session, test_user.id, account_data
            )

    @pytest.mark.asyncio
    async def test_get_cloud_account_by_id(self, db_session: AsyncSession, test_user: User):
        """Test retrieving a cloud account by ID."""
        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            regions=["us-east-1"],
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Retrieve account
        retrieved = await cloud_account_crud.get_cloud_account_by_id(
            db_session, account.id, test_user.id
        )

        assert retrieved is not None
        assert retrieved.id == account.id
        assert retrieved.account_name == "Test Account"

    @pytest.mark.asyncio
    async def test_get_cloud_account_wrong_user(self, db_session: AsyncSession, test_user: User):
        """Test that user can't access another user's cloud account."""
        # Create account for test_user
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

        # Try to retrieve with different user_id
        wrong_user_id = uuid.uuid4()
        retrieved = await cloud_account_crud.get_cloud_account_by_id(
            db_session, account.id, wrong_user_id
        )

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_cloud_accounts_by_user(self, db_session: AsyncSession, test_user: User):
        """Test retrieving all cloud accounts for a user."""
        # Create multiple accounts
        for i in range(3):
            account_data = CloudAccountCreate(
                provider="aws",
                account_name=f"Account {i}",
                account_identifier=f"12345678901{i}",
                aws_access_key_id=f"AKIAIOSFODNN7EXAMPLE{i}",
                aws_secret_access_key=f"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE{i}",
            )
            await cloud_account_crud.create_cloud_account(
                db_session, test_user.id, account_data
            )

        # Retrieve all accounts
        accounts = await cloud_account_crud.get_cloud_accounts_by_user(
            db_session, test_user.id
        )

        assert len(accounts) == 3
        account_names = [acc.account_name for acc in accounts]
        assert "Account 0" in account_names
        assert "Account 1" in account_names
        assert "Account 2" in account_names

    @pytest.mark.asyncio
    async def test_get_cloud_accounts_pagination(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test pagination of cloud accounts."""
        # Create 5 accounts
        for i in range(5):
            account_data = CloudAccountCreate(
                provider="aws",
                account_name=f"Account {i}",
                account_identifier=f"12345678901{i}",
                aws_access_key_id=f"AKIAIOSFODNN7EXAMPLE{i}",
                aws_secret_access_key=f"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE{i}",
            )
            await cloud_account_crud.create_cloud_account(
                db_session, test_user.id, account_data
            )

        # Get first 2 accounts
        first_page = await cloud_account_crud.get_cloud_accounts_by_user(
            db_session, test_user.id, skip=0, limit=2
        )
        assert len(first_page) == 2

        # Get next 2 accounts
        second_page = await cloud_account_crud.get_cloud_accounts_by_user(
            db_session, test_user.id, skip=2, limit=2
        )
        assert len(second_page) == 2

        # Verify accounts are different
        first_ids = {acc.id for acc in first_page}
        second_ids = {acc.id for acc in second_page}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_update_cloud_account_basic_fields(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test updating basic fields of a cloud account."""
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
        update_data = CloudAccountUpdate(
            account_name="Updated Name",
            description="Updated description",
            is_active=False,
        )
        updated = await cloud_account_crud.update_cloud_account(
            db_session, account, update_data
        )

        assert updated.account_name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_update_aws_credentials(self, db_session: AsyncSession, test_user: User):
        """Test updating AWS credentials (should re-encrypt)."""
        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAOLDKEYEXAMPLE",
            aws_secret_access_key="oldSecretKeyExample123456789",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )
        original_encrypted = account.credentials_encrypted

        # Update credentials
        update_data = CloudAccountUpdate(
            aws_access_key_id="AKIANEWKEYEXAMPLE",
            aws_secret_access_key="newSecretKeyExample123456789",
        )
        updated = await cloud_account_crud.update_cloud_account(
            db_session, account, update_data
        )

        # Credentials should be re-encrypted
        assert updated.credentials_encrypted != original_encrypted

        # Verify new credentials can be decrypted
        decrypted_json = credential_encryption.decrypt(updated.credentials_encrypted)
        creds = json.loads(decrypted_json)
        assert creds["access_key_id"] == "AKIANEWKEYEXAMPLE"
        assert creds["secret_access_key"] == "newSecretKeyExample123456789"

    @pytest.mark.asyncio
    async def test_delete_cloud_account(self, db_session: AsyncSession, test_user: User):
        """Test deleting a cloud account."""
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
        account_id = account.id

        # Delete account
        result = await cloud_account_crud.delete_cloud_account(db_session, account)
        assert result is True

        # Verify account is deleted
        deleted = await cloud_account_crud.get_cloud_account_by_id(
            db_session, account_id, test_user.id
        )
        assert deleted is None

    @pytest.mark.asyncio
    async def test_get_decrypted_aws_credentials(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test getting decrypted AWS credentials."""
        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            regions=["us-east-1", "eu-west-1"],
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Get decrypted credentials
        account_with_creds = await cloud_account_crud.get_decrypted_credentials(account)

        assert account_with_creds.aws_credentials is not None
        assert account_with_creds.aws_credentials.access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert (
            account_with_creds.aws_credentials.secret_access_key
            == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )
        assert account_with_creds.aws_credentials.region == "us-east-1"

    @pytest.mark.asyncio
    async def test_get_decrypted_azure_credentials(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test getting decrypted Azure credentials."""
        # Create account
        account_data = CloudAccountCreate(
            provider="azure",
            account_name="Test Azure",
            account_identifier="azure-sub-123",
            azure_tenant_id="12345678-1234-1234-1234-123456789abc",
            azure_client_id="87654321-4321-4321-4321-abc987654321",
            azure_client_secret="azure-secret-123-very-long-key",
            azure_subscription_id="abcdef12-3456-7890-abcd-ef1234567890",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Get decrypted credentials
        account_with_creds = await cloud_account_crud.get_decrypted_credentials(account)

        assert account_with_creds.azure_credentials is not None
        assert account_with_creds.azure_credentials.tenant_id == "12345678-1234-1234-1234-123456789abc"
        assert account_with_creds.azure_credentials.client_id == "87654321-4321-4321-4321-abc987654321"
        assert account_with_creds.azure_credentials.client_secret == "azure-secret-123-very-long-key"
        assert account_with_creds.azure_credentials.subscription_id == "abcdef12-3456-7890-abcd-ef1234567890"

    @pytest.mark.asyncio
    async def test_credentials_encryption_roundtrip(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test that credentials encryption/decryption works correctly."""
        original_access_key = "AKIAIOSFODNN7EXAMPLE"
        original_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

        # Create account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test Account",
            account_identifier="123456789012",
            aws_access_key_id=original_access_key,
            aws_secret_access_key=original_secret_key,
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Decrypt and verify
        decrypted_json = credential_encryption.decrypt(account.credentials_encrypted)
        creds = json.loads(decrypted_json)

        assert creds["access_key_id"] == original_access_key
        assert creds["secret_access_key"] == original_secret_key

    @pytest.mark.asyncio
    async def test_multiple_users_separate_accounts(
        self, db_session: AsyncSession, test_user: User, test_superuser: User
    ):
        """Test that multiple users have separate cloud accounts."""
        # Create account for test_user
        account_data1 = CloudAccountCreate(
            provider="aws",
            account_name="User1 Account",
            account_identifier="111111111111",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE1",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE1",
        )
        await cloud_account_crud.create_cloud_account(db_session, test_user.id, account_data1)

        # Create account for test_superuser
        account_data2 = CloudAccountCreate(
            provider="aws",
            account_name="User2 Account",
            account_identifier="222222222222",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE2",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE2",
        )
        await cloud_account_crud.create_cloud_account(
            db_session, test_superuser.id, account_data2
        )

        # Verify each user sees only their accounts
        user1_accounts = await cloud_account_crud.get_cloud_accounts_by_user(
            db_session, test_user.id
        )
        user2_accounts = await cloud_account_crud.get_cloud_accounts_by_user(
            db_session, test_superuser.id
        )

        assert len(user1_accounts) == 1
        assert user1_accounts[0].account_name == "User1 Account"

        assert len(user2_accounts) == 1
        assert user2_accounts[0].account_name == "User2 Account"
