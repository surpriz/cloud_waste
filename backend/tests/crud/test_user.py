"""Tests for User CRUD operations."""

from datetime import datetime, timedelta
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class TestUserCRUD:
    """Test CRUD operations for User model."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a new user."""
        user_data = UserCreate(
            email="newuser@example.com",
            password="SecurePass123!",
            full_name="New User",
        )

        user = await user_crud.create_user(db_session, user_data)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.hashed_password != "SecurePass123!"  # Password should be hashed
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.email_verified is False

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session: AsyncSession, test_user: User):
        """Test retrieving a user by ID."""
        retrieved_user = await user_crud.get_user_by_id(db_session, test_user.id)

        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id
        assert retrieved_user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, db_session: AsyncSession):
        """Test retrieving a non-existent user by ID returns None."""
        non_existent_id = uuid.uuid4()
        retrieved_user = await user_crud.get_user_by_id(db_session, non_existent_id)

        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, db_session: AsyncSession, test_user: User):
        """Test retrieving a user by email."""
        retrieved_user = await user_crud.get_user_by_email(db_session, test_user.email)

        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id
        assert retrieved_user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, db_session: AsyncSession):
        """Test retrieving a non-existent user by email returns None."""
        retrieved_user = await user_crud.get_user_by_email(
            db_session, "nonexistent@example.com"
        )

        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_update_user_basic_fields(self, db_session: AsyncSession, test_user: User):
        """Test updating basic user fields."""
        update_data = UserUpdate(
            full_name="Updated Name",
            is_active=False,
        )

        updated_user = await user_crud.update_user(db_session, test_user, update_data)

        assert updated_user.full_name == "Updated Name"
        assert updated_user.is_active is False
        assert updated_user.email == test_user.email  # Email unchanged

    @pytest.mark.asyncio
    async def test_update_user_password(self, db_session: AsyncSession, test_user: User):
        """Test updating user password."""
        original_password_hash = test_user.hashed_password

        update_data = UserUpdate(password="NewPassword123!")
        updated_user = await user_crud.update_user(db_session, test_user, update_data)

        # Password hash should have changed
        assert updated_user.hashed_password != original_password_hash
        # Should be able to authenticate with new password
        from app.core.security import verify_password
        assert verify_password("NewPassword123!", updated_user.hashed_password)

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, db_session: AsyncSession, test_user: User):
        """Test successful user authentication."""
        # test_user was created with password "Test123!@#"
        authenticated_user = await user_crud.authenticate_user(
            db_session, test_user.email, "Test123!@#"
        )

        assert authenticated_user is not None
        assert authenticated_user.id == test_user.id

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test authentication with wrong password returns None."""
        authenticated_user = await user_crud.authenticate_user(
            db_session, test_user.email, "WrongPassword123!"
        )

        assert authenticated_user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent_email(self, db_session: AsyncSession):
        """Test authentication with non-existent email returns None."""
        authenticated_user = await user_crud.authenticate_user(
            db_session, "nonexistent@example.com", "password123"
        )

        assert authenticated_user is None

    @pytest.mark.asyncio
    async def test_is_user_active(self, test_user: User):
        """Test checking if user is active."""
        assert await user_crud.is_user_active(test_user) is True

        test_user.is_active = False
        assert await user_crud.is_user_active(test_user) is False

    @pytest.mark.asyncio
    async def test_is_user_superuser(self, test_user: User, test_superuser: User):
        """Test checking if user is superuser."""
        assert await user_crud.is_user_superuser(test_user) is False
        assert await user_crud.is_user_superuser(test_superuser) is True

    @pytest.mark.asyncio
    async def test_get_all_users(self, db_session: AsyncSession, test_user: User):
        """Test retrieving all users."""
        # Create additional users
        user2 = UserCreate(
            email="user2@example.com",
            password="Pass123!",
            full_name="User Two",
        )
        user3 = UserCreate(
            email="user3@example.com",
            password="Pass123!",
            full_name="User Three",
        )
        await user_crud.create_user(db_session, user2)
        await user_crud.create_user(db_session, user3)

        users = await user_crud.get_all_users(db_session, skip=0, limit=10)

        assert len(users) >= 3  # At least test_user + 2 new users

    @pytest.mark.asyncio
    async def test_get_all_users_pagination(self, db_session: AsyncSession):
        """Test pagination of get_all_users."""
        # Create multiple users
        for i in range(5):
            user_data = UserCreate(
                email=f"user{i}@example.com",
                password="Pass123!",
                full_name=f"User {i}",
            )
            await user_crud.create_user(db_session, user_data)

        # Get first 2 users
        first_page = await user_crud.get_all_users(db_session, skip=0, limit=2)
        assert len(first_page) == 2

        # Get next 2 users
        second_page = await user_crud.get_all_users(db_session, skip=2, limit=2)
        assert len(second_page) == 2

        # Users should be different
        first_ids = {u.id for u in first_page}
        second_ids = {u.id for u in second_page}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_count_users(self, db_session: AsyncSession, test_user: User):
        """Test counting total number of users."""
        initial_count = await user_crud.count_users(db_session)

        # Create new user
        user_data = UserCreate(
            email="newcount@example.com",
            password="Pass123!",
            full_name="New Count User",
        )
        await user_crud.create_user(db_session, user_data)

        new_count = await user_crud.count_users(db_session)
        assert new_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_count_active_users(self, db_session: AsyncSession, test_user: User):
        """Test counting active users."""
        initial_active_count = await user_crud.count_active_users(db_session)

        # Create inactive user
        inactive_user_data = UserCreate(
            email="inactive@example.com",
            password="Pass123!",
            full_name="Inactive User",
        )
        inactive_user = await user_crud.create_user(db_session, inactive_user_data)
        inactive_user.is_active = False
        db_session.add(inactive_user)
        await db_session.commit()

        # Create active user
        active_user_data = UserCreate(
            email="active@example.com",
            password="Pass123!",
            full_name="Active User",
        )
        await user_crud.create_user(db_session, active_user_data)

        new_active_count = await user_crud.count_active_users(db_session)
        # Should increase by 1 (only the active user)
        assert new_active_count == initial_active_count + 1

    @pytest.mark.asyncio
    async def test_count_superusers(self, db_session: AsyncSession, test_superuser: User):
        """Test counting superusers."""
        initial_superuser_count = await user_crud.count_superusers(db_session)

        # Create regular user (not superuser)
        regular_user_data = UserCreate(
            email="regular@example.com",
            password="Pass123!",
            full_name="Regular User",
        )
        await user_crud.create_user(db_session, regular_user_data)

        new_superuser_count = await user_crud.count_superusers(db_session)
        # Should remain the same (regular user is not superuser)
        assert new_superuser_count == initial_superuser_count

    @pytest.mark.asyncio
    async def test_delete_user(self, db_session: AsyncSession):
        """Test deleting a user."""
        # Create user to delete
        user_data = UserCreate(
            email="todelete@example.com",
            password="Pass123!",
            full_name="To Delete",
        )
        user = await user_crud.create_user(db_session, user_data)
        user_id = user.id

        # Delete user
        await user_crud.delete_user(db_session, user)

        # Verify user is deleted
        deleted_user = await user_crud.get_user_by_id(db_session, user_id)
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_generate_verification_token(self):
        """Test generating a verification token."""
        token = user_crud.generate_verification_token()

        assert isinstance(token, str)
        assert len(token) > 0

        # Generate another token and ensure it's different
        token2 = user_crud.generate_verification_token()
        assert token != token2

    @pytest.mark.asyncio
    async def test_set_verification_token(self, db_session: AsyncSession, test_user: User):
        """Test setting verification token for user."""
        token = await user_crud.set_verification_token(db_session, test_user)

        assert isinstance(token, str)
        assert test_user.email_verification_token == token
        assert test_user.verification_token_expires_at is not None
        assert test_user.verification_token_expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_get_user_by_verification_token_valid(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test retrieving user by valid verification token."""
        token = await user_crud.set_verification_token(db_session, test_user)

        retrieved_user = await user_crud.get_user_by_verification_token(db_session, token)

        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id

    @pytest.mark.asyncio
    async def test_get_user_by_verification_token_expired(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test retrieving user by expired verification token returns None."""
        token = await user_crud.set_verification_token(db_session, test_user)

        # Manually expire the token
        test_user.verification_token_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.add(test_user)
        await db_session.commit()

        retrieved_user = await user_crud.get_user_by_verification_token(db_session, token)

        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_get_user_by_verification_token_invalid(self, db_session: AsyncSession):
        """Test retrieving user by invalid verification token returns None."""
        retrieved_user = await user_crud.get_user_by_verification_token(
            db_session, "invalid-token-12345"
        )

        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_verify_user_email(self, db_session: AsyncSession, test_user: User):
        """Test verifying user email."""
        # Set verification token first
        await user_crud.set_verification_token(db_session, test_user)

        # Verify email
        verified_user = await user_crud.verify_user_email(db_session, test_user)

        assert verified_user.email_verified is True
        assert verified_user.email_verification_token is None
        assert verified_user.verification_token_expires_at is None

    @pytest.mark.asyncio
    async def test_get_unverified_users_older_than(self, db_session: AsyncSession):
        """Test retrieving unverified users older than specified days."""
        # Create old unverified user
        old_user_data = UserCreate(
            email="oldunverified@example.com",
            password="Pass123!",
            full_name="Old Unverified",
        )
        old_user = await user_crud.create_user(db_session, old_user_data)

        # Manually set created_at to 15 days ago
        old_user.created_at = datetime.utcnow() - timedelta(days=15)
        db_session.add(old_user)
        await db_session.commit()

        # Create recent unverified user
        recent_user_data = UserCreate(
            email="recentunverified@example.com",
            password="Pass123!",
            full_name="Recent Unverified",
        )
        await user_crud.create_user(db_session, recent_user_data)

        # Get unverified users older than 14 days
        old_unverified_users = await user_crud.get_unverified_users_older_than(
            db_session, days=14
        )

        # Should include old_user but not recent_user
        old_user_emails = [u.email for u in old_unverified_users]
        assert "oldunverified@example.com" in old_user_emails
        assert "recentunverified@example.com" not in old_user_emails

    @pytest.mark.asyncio
    async def test_get_unverified_users_excludes_verified(self, db_session: AsyncSession):
        """Test that get_unverified_users_older_than excludes verified users."""
        # Create old verified user
        verified_user_data = UserCreate(
            email="oldverified@example.com",
            password="Pass123!",
            full_name="Old Verified",
        )
        verified_user = await user_crud.create_user(db_session, verified_user_data)
        verified_user.created_at = datetime.utcnow() - timedelta(days=20)
        verified_user.email_verified = True
        db_session.add(verified_user)
        await db_session.commit()

        # Get unverified users older than 15 days
        old_unverified_users = await user_crud.get_unverified_users_older_than(
            db_session, days=15
        )

        # Should not include verified user
        old_user_emails = [u.email for u in old_unverified_users]
        assert "oldverified@example.com" not in old_user_emails
