"""Tests for Scan CRUD operations."""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import scan as scan_crud
from app.crud import cloud_account as cloud_account_crud
from app.models.user import User
from app.models.scan import ScanStatus, ScanType
from app.schemas.scan import ScanCreate, ScanUpdate
from app.schemas.cloud_account import CloudAccountCreate


class TestScanCRUD:
    """Test CRUD operations for Scan model."""

    @pytest.mark.asyncio
    async def test_create_manual_scan(self, db_session: AsyncSession, test_user: User):
        """Test creating a manual scan job."""
        # Create cloud account first
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Create scan
        scan_data = ScanCreate(
            cloud_account_id=account.id,
            scan_type=ScanType.MANUAL,
        )
        scan = await scan_crud.create_scan(db_session, scan_data)

        assert scan.id is not None
        assert scan.cloud_account_id == account.id
        assert scan.scan_type == ScanType.MANUAL.value
        assert scan.status == ScanStatus.PENDING.value
        assert scan.total_resources_scanned == 0
        assert scan.orphan_resources_found == 0
        assert scan.estimated_monthly_waste == 0.0
        assert scan.started_at is None
        assert scan.completed_at is None

    @pytest.mark.asyncio
    async def test_create_scheduled_scan(self, db_session: AsyncSession, test_user: User):
        """Test creating a scheduled scan job."""
        # Create cloud account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS Account",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Create scheduled scan
        scan_data = ScanCreate(
            cloud_account_id=account.id,
            scan_type=ScanType.SCHEDULED,
        )
        scan = await scan_crud.create_scan(db_session, scan_data)

        assert scan.scan_type == ScanType.SCHEDULED.value
        assert scan.status == ScanStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_scan_by_id(self, db_session: AsyncSession, test_user: User):
        """Test retrieving a scan by ID."""
        # Create account and scan
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        scan_data = ScanCreate(cloud_account_id=account.id)
        scan = await scan_crud.create_scan(db_session, scan_data)

        # Retrieve scan
        retrieved = await scan_crud.get_scan_by_id(db_session, scan.id)

        assert retrieved is not None
        assert retrieved.id == scan.id
        assert retrieved.cloud_account_id == account.id

    @pytest.mark.asyncio
    async def test_get_scan_by_id_not_found(self, db_session: AsyncSession):
        """Test retrieving a non-existent scan returns None."""
        non_existent_id = uuid.uuid4()
        retrieved = await scan_crud.get_scan_by_id(db_session, non_existent_id)

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_scans_by_account(self, db_session: AsyncSession, test_user: User):
        """Test retrieving all scans for a cloud account."""
        # Create cloud account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Create multiple scans
        for i in range(3):
            scan_data = ScanCreate(cloud_account_id=account.id)
            await scan_crud.create_scan(db_session, scan_data)

        # Retrieve scans
        scans = await scan_crud.get_scans_by_account(db_session, account.id)

        assert len(scans) == 3
        # All scans should belong to the same account
        for scan in scans:
            assert scan.cloud_account_id == account.id

    @pytest.mark.asyncio
    async def test_get_scans_by_account_pagination(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test pagination of scans for a cloud account."""
        # Create cloud account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Create 5 scans
        for i in range(5):
            scan_data = ScanCreate(cloud_account_id=account.id)
            await scan_crud.create_scan(db_session, scan_data)

        # Get first page (2 scans)
        first_page = await scan_crud.get_scans_by_account(
            db_session, account.id, skip=0, limit=2
        )
        assert len(first_page) == 2

        # Get second page (2 scans)
        second_page = await scan_crud.get_scans_by_account(
            db_session, account.id, skip=2, limit=2
        )
        assert len(second_page) == 2

        # Verify scans are different
        first_ids = {s.id for s in first_page}
        second_ids = {s.id for s in second_page}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_get_scans_by_user(self, db_session: AsyncSession, test_user: User):
        """Test retrieving all scans for a user's cloud accounts."""
        # Create two cloud accounts
        account1_data = CloudAccountCreate(
            provider="aws",
            account_name="Account 1",
            account_identifier="111111111111",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE1",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE1",
        )
        account1 = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account1_data
        )

        account2_data = CloudAccountCreate(
            provider="aws",
            account_name="Account 2",
            account_identifier="222222222222",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE2",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE2",
        )
        account2 = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account2_data
        )

        # Create scans for both accounts
        scan1_data = ScanCreate(cloud_account_id=account1.id)
        await scan_crud.create_scan(db_session, scan1_data)

        scan2_data = ScanCreate(cloud_account_id=account2.id)
        await scan_crud.create_scan(db_session, scan2_data)

        # Retrieve all scans for user
        scans = await scan_crud.get_scans_by_user(db_session, test_user.id)

        assert len(scans) == 2
        scan_account_ids = {s.cloud_account_id for s in scans}
        assert account1.id in scan_account_ids
        assert account2.id in scan_account_ids

    @pytest.mark.asyncio
    async def test_update_scan(self, db_session: AsyncSession, test_user: User):
        """Test updating a scan."""
        # Create account and scan
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        scan_data = ScanCreate(cloud_account_id=account.id)
        scan = await scan_crud.create_scan(db_session, scan_data)

        # Update scan
        now = datetime.utcnow()
        update_data = ScanUpdate(
            status=ScanStatus.COMPLETED,
            total_resources_scanned=150,
            orphan_resources_found=25,
            estimated_monthly_waste=450.50,
            started_at=now - timedelta(minutes=10),
            completed_at=now,
        )
        updated = await scan_crud.update_scan(db_session, scan.id, update_data)

        assert updated is not None
        assert updated.status == ScanStatus.COMPLETED.value
        assert updated.total_resources_scanned == 150
        assert updated.orphan_resources_found == 25
        assert updated.estimated_monthly_waste == 450.50
        assert updated.started_at is not None
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_scan_not_found(self, db_session: AsyncSession):
        """Test updating a non-existent scan returns None."""
        non_existent_id = uuid.uuid4()
        update_data = ScanUpdate(status=ScanStatus.COMPLETED)

        updated = await scan_crud.update_scan(db_session, non_existent_id, update_data)

        assert updated is None

    @pytest.mark.asyncio
    async def test_delete_scan(self, db_session: AsyncSession, test_user: User):
        """Test deleting a scan."""
        # Create account and scan
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        scan_data = ScanCreate(cloud_account_id=account.id)
        scan = await scan_crud.create_scan(db_session, scan_data)
        scan_id = scan.id

        # Delete scan
        result = await scan_crud.delete_scan(db_session, scan_id)
        assert result is True

        # Verify scan is deleted
        deleted = await scan_crud.get_scan_by_id(db_session, scan_id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_scan_not_found(self, db_session: AsyncSession):
        """Test deleting a non-existent scan returns False."""
        non_existent_id = uuid.uuid4()
        result = await scan_crud.delete_scan(db_session, non_existent_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_scan_statistics(self, db_session: AsyncSession, test_user: User):
        """Test getting scan statistics."""
        # Create cloud account
        account_data = CloudAccountCreate(
            provider="aws",
            account_name="Test AWS",
            account_identifier="123456789012",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )
        account = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account_data
        )

        # Create scans with different statuses
        # Completed scan 1
        scan1 = await scan_crud.create_scan(
            db_session, ScanCreate(cloud_account_id=account.id)
        )
        await scan_crud.update_scan(
            db_session,
            scan1.id,
            ScanUpdate(
                status=ScanStatus.COMPLETED,
                orphan_resources_found=10,
                estimated_monthly_waste=100.0,
                completed_at=datetime.utcnow(),
            ),
        )

        # Completed scan 2
        scan2 = await scan_crud.create_scan(
            db_session, ScanCreate(cloud_account_id=account.id)
        )
        await scan_crud.update_scan(
            db_session,
            scan2.id,
            ScanUpdate(
                status=ScanStatus.COMPLETED,
                orphan_resources_found=15,
                estimated_monthly_waste=200.50,
                completed_at=datetime.utcnow(),
            ),
        )

        # Failed scan
        scan3 = await scan_crud.create_scan(
            db_session, ScanCreate(cloud_account_id=account.id)
        )
        await scan_crud.update_scan(
            db_session,
            scan3.id,
            ScanUpdate(
                status=ScanStatus.FAILED,
                error_message="Connection error",
            ),
        )

        # Pending scan
        await scan_crud.create_scan(
            db_session, ScanCreate(cloud_account_id=account.id)
        )

        # Get statistics
        stats = await scan_crud.get_scan_statistics(db_session)

        assert stats["total_scans"] == 4
        assert stats["completed_scans"] == 2
        assert stats["failed_scans"] == 1
        assert stats["total_orphan_resources"] == 25  # 10 + 15
        assert stats["total_monthly_waste"] == 300.50  # 100.0 + 200.50
        assert stats["last_scan_at"] is not None

    @pytest.mark.asyncio
    async def test_get_scan_statistics_by_account(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test getting scan statistics filtered by cloud account."""
        # Create two cloud accounts
        account1_data = CloudAccountCreate(
            provider="aws",
            account_name="Account 1",
            account_identifier="111111111111",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE1",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE1",
        )
        account1 = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account1_data
        )

        account2_data = CloudAccountCreate(
            provider="aws",
            account_name="Account 2",
            account_identifier="222222222222",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE2",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE2",
        )
        account2 = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account2_data
        )

        # Create scans for account1
        scan1 = await scan_crud.create_scan(
            db_session, ScanCreate(cloud_account_id=account1.id)
        )
        await scan_crud.update_scan(
            db_session,
            scan1.id,
            ScanUpdate(
                status=ScanStatus.COMPLETED,
                orphan_resources_found=5,
                estimated_monthly_waste=50.0,
                completed_at=datetime.utcnow(),
            ),
        )

        # Create scans for account2
        scan2 = await scan_crud.create_scan(
            db_session, ScanCreate(cloud_account_id=account2.id)
        )
        await scan_crud.update_scan(
            db_session,
            scan2.id,
            ScanUpdate(
                status=ScanStatus.COMPLETED,
                orphan_resources_found=20,
                estimated_monthly_waste=300.0,
                completed_at=datetime.utcnow(),
            ),
        )

        # Get statistics for account1 only
        stats = await scan_crud.get_scan_statistics(db_session, account1.id)

        assert stats["total_scans"] == 1
        assert stats["completed_scans"] == 1
        assert stats["total_orphan_resources"] == 5
        assert stats["total_monthly_waste"] == 50.0

    @pytest.mark.asyncio
    async def test_delete_all_scans_by_user(
        self, db_session: AsyncSession, test_user: User, test_superuser: User
    ):
        """Test deleting all scans for a user's cloud accounts."""
        # Create account for test_user
        account1_data = CloudAccountCreate(
            provider="aws",
            account_name="User1 Account",
            account_identifier="111111111111",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE1",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE1",
        )
        account1 = await cloud_account_crud.create_cloud_account(
            db_session, test_user.id, account1_data
        )

        # Create account for test_superuser
        account2_data = CloudAccountCreate(
            provider="aws",
            account_name="User2 Account",
            account_identifier="222222222222",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE2",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE2",
        )
        account2 = await cloud_account_crud.create_cloud_account(
            db_session, test_superuser.id, account2_data
        )

        # Create scans for both users
        await scan_crud.create_scan(db_session, ScanCreate(cloud_account_id=account1.id))
        await scan_crud.create_scan(db_session, ScanCreate(cloud_account_id=account1.id))
        await scan_crud.create_scan(db_session, ScanCreate(cloud_account_id=account2.id))

        # Delete all scans for test_user
        deleted_count = await scan_crud.delete_all_scans_by_user(
            db_session, test_user.id
        )

        assert deleted_count == 2

        # Verify only test_user's scans are deleted
        user1_scans = await scan_crud.get_scans_by_user(db_session, test_user.id)
        user2_scans = await scan_crud.get_scans_by_user(db_session, test_superuser.id)

        assert len(user1_scans) == 0
        assert len(user2_scans) == 1
