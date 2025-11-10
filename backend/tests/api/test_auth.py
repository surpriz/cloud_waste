"""Tests for authentication API endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import UserCreate


class TestAuthAPI:
    """Test authentication API endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.auth.email_service.send_verification_email", return_value=True)
    async def test_register_success(
        self, mock_send_email, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["email_verified"] is False
        assert "hashed_password" not in data

        # Verify email service was called
        mock_send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, async_client: AsyncClient, test_user: User
    ):
        """Test registration with duplicate email returns 400."""
        user_data = {
            "email": test_user.email,
            "password": "SecurePass123!",
            "full_name": "Duplicate User",
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_success(
        self, async_client: AsyncClient, test_user: User
    ):
        """Test successful login with valid credentials."""
        form_data = {
            "username": test_user.email,
            "password": "Test123!@#",  # Password from conftest.py
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=form_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_remember_me(
        self, async_client: AsyncClient, test_user: User
    ):
        """Test login with remember_me flag."""
        form_data = {
            "username": test_user.email,
            "password": "Test123!@#",
            "remember_me": "true",
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=form_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Refresh token should have longer expiration (checked in JWT decode)

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, async_client: AsyncClient, test_user: User
    ):
        """Test login with wrong password returns 401."""
        form_data = {
            "username": test_user.email,
            "password": "WrongPassword123!",
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=form_data,
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_unverified_email(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test login with unverified email returns 403."""
        # Create unverified user
        user_data = UserCreate(
            email="unverified@example.com",
            password="Test123!@#",
            full_name="Unverified User",
        )
        user = await user_crud.create_user(db_session, user_data)
        # user.email_verified is False by default

        form_data = {
            "username": user.email,
            "password": "Test123!@#",
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=form_data,
        )

        assert response.status_code == 403
        assert "not verified" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self, async_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test login with inactive user returns 403."""
        # Deactivate user
        test_user.is_active = False
        db_session.add(test_user)
        await db_session.commit()

        form_data = {
            "username": test_user.email,
            "password": "Test123!@#",
        }

        response = await async_client.post(
            "/api/v1/auth/login",
            data=form_data,
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, async_client: AsyncClient, test_user: User
    ):
        """Test refreshing access token with valid refresh token."""
        # First login to get tokens
        form_data = {
            "username": test_user.email,
            "password": "Test123!@#",
        }
        login_response = await async_client.post("/api/v1/auth/login", data=form_data)
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        refresh_data = {"refresh_token": refresh_token}
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, async_client: AsyncClient):
        """Test refreshing with invalid token returns 401."""
        refresh_data = {"refresh_token": "invalid.token.here"}

        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_current_user(
        self, authenticated_async_client: AsyncClient, test_user: User
    ):
        """Test getting current user information."""
        response = await authenticated_async_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, async_client: AsyncClient):
        """Test getting current user without authentication returns 403."""
        response = await async_client.get("/api/v1/auth/me")

        assert response.status_code == 403

    @pytest.mark.asyncio
    @patch("app.api.v1.auth.email_service.send_welcome_email", return_value=True)
    async def test_verify_email_success(
        self, mock_send_welcome, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test successful email verification."""
        # Create user and set verification token
        user_data = UserCreate(
            email="verify@example.com",
            password="Test123!@#",
            full_name="Verify User",
        )
        user = await user_crud.create_user(db_session, user_data)
        verification_token = await user_crud.set_verification_token(db_session, user)

        # Verify email
        response = await async_client.get(
            f"/api/v1/auth/verify-email/{verification_token}"
        )

        assert response.status_code == 200
        assert "verified successfully" in response.json()["message"].lower()

        # Verify user is now verified in database
        await db_session.refresh(user)
        assert user.email_verified is True

        # Verify welcome email was sent
        mock_send_welcome.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, async_client: AsyncClient):
        """Test email verification with invalid token returns 400."""
        response = await async_client.get(
            "/api/v1/auth/verify-email/invalid-token-12345"
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.api.v1.auth.email_service.send_verification_email", return_value=True)
    async def test_resend_verification_success(
        self, mock_send_email, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test resending verification email."""
        # Create unverified user
        user_data = UserCreate(
            email="resend@example.com",
            password="Test123!@#",
            full_name="Resend User",
        )
        user = await user_crud.create_user(db_session, user_data)

        # Resend verification
        form_data = {"email": user.email}
        response = await async_client.post(
            "/api/v1/auth/resend-verification",
            data=form_data,
        )

        assert response.status_code == 200
        assert "sent successfully" in response.json()["message"].lower()

        # Verify email service was called
        mock_send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_resend_verification_already_verified(
        self, async_client: AsyncClient, test_user: User
    ):
        """Test resending verification to already verified user returns 400."""
        # test_user is already verified
        form_data = {"email": test_user.email}

        response = await async_client.post(
            "/api/v1/auth/resend-verification",
            data=form_data,
        )

        assert response.status_code == 400
        assert "already verified" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_current_user(
        self, authenticated_async_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test updating current user information."""
        update_data = {
            "full_name": "Updated Name",
            "email_scan_notifications": False,
        }

        response = await authenticated_async_client.patch(
            "/api/v1/auth/me", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["email_scan_notifications"] is False

    @pytest.mark.asyncio
    async def test_update_current_user_duplicate_email(
        self,
        authenticated_async_client: AsyncClient,
        test_user: User,
        test_superuser: User,
    ):
        """Test updating email to already taken email returns 400."""
        update_data = {
            "email": test_superuser.email,  # Try to use superuser's email
        }

        response = await authenticated_async_client.patch(
            "/api/v1/auth/me", json=update_data
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
