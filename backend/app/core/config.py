"""Application Configuration using Pydantic Settings."""

from typing import List

from pydantic import EmailStr, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "CloudWaste"
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

    # Database
    DATABASE_URL: PostgresDsn

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

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str = "CloudWaste"

    # AWS (Optional - for testing)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "eu-west-1"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | List[str]) -> List[str]:
        """Parse allowed origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# Create global settings instance
settings = Settings()  # type: ignore
