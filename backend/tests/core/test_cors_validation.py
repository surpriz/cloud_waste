"""Unit tests for CORS origin validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestCORSOriginValidation:
    """Test suite for CORS origin validation in Settings."""

    def test_valid_origins_development(self):
        """Test that valid HTTP origins are accepted in development."""
        settings = Settings(
            APP_ENV="development",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            REDIS_URL="redis://localhost:6379/0",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            CELERY_RESULT_BACKEND="redis://localhost:6379/0",
            SECRET_KEY="test-secret",
            ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
            JWT_SECRET_KEY="test-jwt-secret",
            ALLOWED_ORIGINS=[
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "https://cloudwaste.com",
            ],
        )

        assert len(settings.ALLOWED_ORIGINS) == 3
        assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
        assert "https://cloudwaste.com" in settings.ALLOWED_ORIGINS

    def test_valid_origins_production_https_only(self):
        """Test that only HTTPS origins are accepted in production (except localhost)."""
        settings = Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            REDIS_URL="redis://localhost:6379/0",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            CELERY_RESULT_BACKEND="redis://localhost:6379/0",
            SECRET_KEY="test-secret",
            ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
            JWT_SECRET_KEY="test-jwt-secret",
            ALLOWED_ORIGINS=[
                "https://cloudwaste.com",
                "https://www.cloudwaste.com",
                "https://api.cloudwaste.com",
                "http://localhost:3000",  # Allowed in production
                "http://127.0.0.1:3000",  # Allowed in production
            ],
        )

        assert len(settings.ALLOWED_ORIGINS) == 5
        assert all("https://" in origin or "localhost" in origin or "127.0.0.1" in origin for origin in settings.ALLOWED_ORIGINS)

    def test_reject_wildcard_asterisk(self):
        """Test that wildcard '*' is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="development",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=["*"],
            )

        error_str = str(exc_info.value)
        assert "wildcard" in error_str.lower()
        assert "*" in error_str

    def test_reject_wildcard_in_domain(self):
        """Test that wildcards in domains are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="development",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=["http://*.cloudwaste.com"],
            )

        error_str = str(exc_info.value)
        assert "wildcard" in error_str.lower()

    def test_reject_http_in_production_non_localhost(self):
        """Test that HTTP (non-localhost) origins are rejected in production."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="production",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=["http://cloudwaste.com"],  # HTTP in production
            )

        error_str = str(exc_info.value)
        assert "https" in error_str.lower()
        assert "production" in error_str.lower()

    def test_reject_origin_without_scheme(self):
        """Test that origins without scheme (http:// or https://) are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="development",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=["cloudwaste.com"],  # Missing scheme
            )

        error_str = str(exc_info.value)
        assert "scheme" in error_str.lower()

    def test_reject_origin_without_hostname(self):
        """Test that origins without hostname are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="development",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=["http://"],  # No hostname
            )

        error_str = str(exc_info.value)
        assert "hostname" in error_str.lower()

    def test_reject_empty_origin(self):
        """Test that empty origins are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="development",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=[""],
            )

        error_str = str(exc_info.value)
        assert "empty" in error_str.lower() or "cannot be empty" in error_str.lower()

    def test_reject_empty_origins_list(self):
        """Test that empty ALLOWED_ORIGINS list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                APP_ENV="development",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
                REDIS_URL="redis://localhost:6379/0",
                CELERY_BROKER_URL="redis://localhost:6379/0",
                CELERY_RESULT_BACKEND="redis://localhost:6379/0",
                SECRET_KEY="test-secret",
                ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
                JWT_SECRET_KEY="test-jwt-secret",
                ALLOWED_ORIGINS=[],
            )

        error_str = str(exc_info.value)
        assert "empty" in error_str.lower() or "cannot be empty" in error_str.lower()

    def test_parse_comma_separated_origins(self):
        """Test that comma-separated string of origins is correctly parsed."""
        settings = Settings(
            APP_ENV="development",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            REDIS_URL="redis://localhost:6379/0",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            CELERY_RESULT_BACKEND="redis://localhost:6379/0",
            SECRET_KEY="test-secret",
            ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
            JWT_SECRET_KEY="test-jwt-secret",
            ALLOWED_ORIGINS="http://localhost:3000,https://cloudwaste.com,http://127.0.0.1:3000",
        )

        assert len(settings.ALLOWED_ORIGINS) == 3
        assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
        assert "https://cloudwaste.com" in settings.ALLOWED_ORIGINS
        assert "http://127.0.0.1:3000" in settings.ALLOWED_ORIGINS

    def test_origins_with_port_numbers(self):
        """Test that origins with explicit port numbers are accepted."""
        settings = Settings(
            APP_ENV="development",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            REDIS_URL="redis://localhost:6379/0",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            CELERY_RESULT_BACKEND="redis://localhost:6379/0",
            SECRET_KEY="test-secret",
            ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
            JWT_SECRET_KEY="test-jwt-secret",
            ALLOWED_ORIGINS=[
                "http://localhost:3000",
                "https://cloudwaste.com:8443",
                "http://192.168.1.100:3001",
            ],
        )

        assert len(settings.ALLOWED_ORIGINS) == 3
        assert "https://cloudwaste.com:8443" in settings.ALLOWED_ORIGINS

    def test_localhost_http_allowed_in_production(self):
        """Test that localhost HTTP is allowed even in production."""
        settings = Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            REDIS_URL="redis://localhost:6379/0",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            CELERY_RESULT_BACKEND="redis://localhost:6379/0",
            SECRET_KEY="test-secret",
            ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
            JWT_SECRET_KEY="test-jwt-secret",
            ALLOWED_ORIGINS=[
                "http://localhost:3000",
                "http://localhost:8080",
                "http://127.0.0.1:3000",
            ],
        )

        assert len(settings.ALLOWED_ORIGINS) == 3
        assert all("localhost" in origin or "127.0.0.1" in origin for origin in settings.ALLOWED_ORIGINS)

    def test_trim_whitespace_from_origins(self):
        """Test that whitespace is trimmed from origins."""
        settings = Settings(
            APP_ENV="development",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            REDIS_URL="redis://localhost:6379/0",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            CELERY_RESULT_BACKEND="redis://localhost:6379/0",
            SECRET_KEY="test-secret",
            ENCRYPTION_KEY="test-encryption-key-32-bytes-long",
            JWT_SECRET_KEY="test-jwt-secret",
            ALLOWED_ORIGINS="  http://localhost:3000  ,  https://cloudwaste.com  ",
        )

        assert len(settings.ALLOWED_ORIGINS) == 2
        assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
        assert "https://cloudwaste.com" in settings.ALLOWED_ORIGINS
        # Ensure no leading/trailing spaces
        assert not any(origin.startswith(" ") or origin.endswith(" ") for origin in settings.ALLOWED_ORIGINS)
