"""Pytest configuration and fixtures for CloudWaste tests."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.user import User

# Use SQLite in-memory database for tests (faster and no setup needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def engine():
    """Create async engine for tests with SQLite in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,  # StaticPool for in-memory SQLite
        connect_args={"check_same_thread": False},  # Required for SQLite
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        # Rollback to clean up any changes (but allows commits during test)
        await session.rollback()


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    """Create a test client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for authentication tests."""
    from app.core.security import get_password_hash

    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("Test123!@#"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        email_verified=True,  # Pre-verified for tests
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_superuser(db_session: AsyncSession) -> User:
    """Create a test superuser for admin tests."""
    from app.core.security import get_password_hash

    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("Admin123!@#"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client: TestClient, test_user: User) -> TestClient:
    """Create a test client with JWT authentication."""
    from app.core.security import create_access_token
    from datetime import timedelta

    access_token = create_access_token(
        data={"sub": str(test_user.id)},
        expires_delta=timedelta(minutes=30),
    )
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    return client


@pytest.fixture
async def authenticated_async_client(
    async_client: AsyncClient, test_user: User
) -> AsyncClient:
    """Create an async test client with JWT authentication."""
    from app.core.security import create_access_token
    from datetime import timedelta

    access_token = create_access_token(
        data={"sub": str(test_user.id)},
        expires_delta=timedelta(minutes=30),
    )
    async_client.headers.update({"Authorization": f"Bearer {access_token}"})
    return async_client


@pytest.fixture
def mock_aws_credentials() -> dict:
    """Mock AWS credentials for testing."""
    return {
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1",
    }


@pytest.fixture
def mock_azure_credentials() -> dict:
    """Mock Azure credentials for testing."""
    return {
        "tenant_id": "12345678-1234-1234-1234-123456789abc",
        "client_id": "87654321-4321-4321-4321-abc987654321",
        "client_secret": "mock-azure-client-secret-for-testing",
        "subscription_id": "abcdef12-3456-7890-abcd-ef1234567890",
    }


@pytest.fixture
def mock_gcp_credentials() -> dict:
    """Mock GCP credentials for testing."""
    return {
        "project_id": "cloudwaste-test-project",
        "private_key_id": "1234567890abcdef1234567890abcdef12345678",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
        "client_email": "test@cloudwaste-test-project.iam.gserviceaccount.com",
        "client_id": "123456789012345678901",
    }
