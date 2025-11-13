"""Application Configuration using Pydantic Settings."""

import os
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from pydantic import EmailStr, PostgresDsn, RedisDsn, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_file() -> str:
    """
    Determine which .env file to load based on APP_ENV.

    Returns:
        Path to the .env file to load
    """
    app_env = os.getenv("APP_ENV", "development")
    base_dir = Path(__file__).parent.parent.parent  # backend/

    if app_env == "test":
        env_file = base_dir / ".env.test"
        if env_file.exists():
            return str(env_file)

    if app_env == "production":
        env_file = base_dir / ".env.production"
        if env_file.exists():
            return str(env_file)

    # Default to .env
    return str(base_dir / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "CutCosts"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"

    # Security
    ENCRYPTION_KEY: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_REMEMBER_ME_EXPIRE_DAYS: int = 30

    # Database
    # Note: Using str instead of PostgresDsn to support SQLite for testing
    DATABASE_URL: str

    # Redis
    REDIS_URL: RedisDsn

    # Celery
    CELERY_BROKER_URL: RedisDsn
    CELERY_RESULT_BACKEND: RedisDsn

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_MAX_AGE: int = 600  # Preflight cache duration in seconds

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = ""  # Changed from EmailStr to str to accept empty values
    EMAILS_FROM_NAME: str = "CutCosts"

    # Email verification
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 168  # 7 days
    UNVERIFIED_ACCOUNT_CLEANUP_DAYS: int = 14  # Auto-delete after 14 days
    FRONTEND_URL: str = "http://localhost:3000"

    # AWS (Optional - for testing)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "eu-west-1"

    # AWS SES (Optional - for cold email monitoring)
    AWS_SES_REGION: str = "eu-north-1"
    AWS_SES_ACCESS_KEY_ID: str = ""  # Optional, uses AWS_ACCESS_KEY_ID if empty
    AWS_SES_SECRET_ACCESS_KEY: str = ""  # Optional, uses AWS_SECRET_ACCESS_KEY if empty

    # AI Assistant (Anthropic)
    ANTHROPIC_API_KEY: str = ""
    CHAT_MAX_MESSAGES_PER_USER_PER_DAY: int = 50
    CHAT_CONTEXT_MAX_RESOURCES: int = 20
    CHAT_MODEL: str = "claude-haiku-4-5-20250818"

    # Error Tracking (Sentry)
    SENTRY_DSN: str = ""  # Sentry Data Source Name (URL from sentry.io dashboard)
    SENTRY_ENVIRONMENT: str = "development"  # development, staging, production
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1  # 10% of transactions for performance monitoring
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1  # 10% of transactions for profiling

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_LOGIN: str = "5/minute"  # Login attempts (brute-force protection)
    RATE_LIMIT_AUTH_REGISTER: str = "3/minute"  # Registration (spam prevention)
    RATE_LIMIT_AUTH_REFRESH: str = "10/minute"  # Token refresh
    RATE_LIMIT_SCANS: str = "10/minute"  # Cloud scans (resource-intensive)
    RATE_LIMIT_ADMIN: str = "50/minute"  # Admin endpoints
    RATE_LIMIT_API_DEFAULT: str = "100/minute"  # Default for all API endpoints

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | List[str]) -> List[str]:
        """Parse allowed origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def validate_cors_origins(cls, origins: List[str], info) -> List[str]:
        """
        Validate CORS origins for security.

        Security rules:
        1. No wildcards ("*", "http://*", etc.)
        2. Valid URL format (scheme://host[:port])
        3. In production: HTTPS only (except localhost/127.0.0.1)
        4. No empty or whitespace-only origins

        Args:
            origins: List of origin URLs to validate
            info: ValidationInfo containing other field values

        Returns:
            Validated list of origins

        Raises:
            ValueError: If any origin violates security rules
        """
        if not origins:
            raise ValueError("ALLOWED_ORIGINS cannot be empty. At least one origin must be specified.")

        # Get APP_ENV from the validation context
        app_env = info.data.get("APP_ENV", "development")
        is_production = app_env == "production"

        validated_origins = []

        for origin in origins:
            origin = origin.strip()

            # Rule 1: No empty origins
            if not origin:
                raise ValueError("CORS origin cannot be empty or whitespace-only")

            # Rule 2: No wildcards
            if "*" in origin:
                raise ValueError(
                    f"CORS origin '{origin}' contains wildcard '*'. "
                    "Wildcards are not allowed for security reasons. "
                    "Specify exact domains instead."
                )

            # Rule 3: Valid URL format
            try:
                parsed = urlparse(origin)
            except Exception as e:
                raise ValueError(f"CORS origin '{origin}' is not a valid URL: {e}")

            if not parsed.scheme:
                raise ValueError(
                    f"CORS origin '{origin}' must include scheme (http:// or https://). "
                    f"Example: https://cloudwaste.com"
                )

            if not parsed.netloc:
                raise ValueError(
                    f"CORS origin '{origin}' must include hostname. "
                    f"Example: https://cloudwaste.com"
                )

            # Rule 4: Production must use HTTPS (except localhost)
            if is_production:
                is_localhost = parsed.netloc.startswith("localhost") or parsed.netloc.startswith("127.0.0.1")

                if parsed.scheme != "https" and not is_localhost:
                    raise ValueError(
                        f"CORS origin '{origin}' must use HTTPS in production. "
                        f"HTTP is only allowed for localhost/127.0.0.1. "
                        f"Change to: https://{parsed.netloc}"
                    )

            validated_origins.append(origin)

        return validated_origins


# Create global settings instance
settings = Settings()  # type: ignore
