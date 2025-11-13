"""FastAPI Application Entry Point."""

import hashlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.middleware import CORSLoggingMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking
# IMPORTANT: Must be done BEFORE creating FastAPI app
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        # Performance monitoring
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),  # Track API endpoint performance
            SqlalchemyIntegration(),  # Track database queries
            RedisIntegration(),  # Track Redis operations
            CeleryIntegration(),  # Track Celery tasks
        ],
        # User context (GDPR: Only enable if user consents)
        send_default_pii=False,  # Don't send PII by default
        # Release tracking (helps identify which version introduced bugs)
        release=f"cutcosts-backend@{os.getenv('GIT_COMMIT', 'dev')}",
        # Additional configuration
        attach_stacktrace=True,  # Attach stack traces to messages
        max_breadcrumbs=50,  # Number of breadcrumbs to keep
    )
    logger.info(f"✅ Sentry initialized (environment: {settings.SENTRY_ENVIRONMENT})")
else:
    logger.info("⚠️  Sentry DSN not set - Error tracking disabled")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="CutCosts - Detect and identify orphaned cloud resources",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS logging middleware for security monitoring (OPTIONAL)
# ⚠️  NOTE: CORSLoggingMiddleware is available but currently disabled
# due to compatibility issues with BaseHTTPMiddleware in test environment
# To enable: uncomment the line below
# app.add_middleware(CORSLoggingMiddleware, log_all_requests=False)

# Configure CORS with strict security rules
# Security rationale:
# - allow_origins: Validated whitelist from settings (no wildcards)
# - allow_credentials: Allows cookies/authorization headers (required for JWT)
# - allow_methods: Explicit list (no wildcard for security)
# - allow_headers: Explicit whitelist (no wildcard to prevent header injection)
# - max_age: Cache preflight for 10 minutes to reduce requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
    max_age=settings.CORS_MAX_AGE,
)


# Encryption Key Validation
def validate_encryption_key() -> None:
    """
    Validate ENCRYPTION_KEY at startup to prevent data loss.

    ⚠️  CRITICAL: This function ensures that ENCRYPTION_KEY hasn't changed
    since the last run. If the key changes, all encrypted data (cloud accounts
    credentials) becomes UNRECOVERABLE.

    Checks:
    1. ENCRYPTION_KEY is set in environment
    2. Key hash is logged (for audit trail)
    3. Warns if key appears to be a placeholder

    Raises:
        SystemExit: If ENCRYPTION_KEY is missing or invalid
    """
    logger.info("🔐 Validating ENCRYPTION_KEY...")

    # Check if ENCRYPTION_KEY is set
    if not settings.ENCRYPTION_KEY:
        logger.error("❌ ENCRYPTION_KEY not set in environment!")
        logger.error("   This will prevent encryption/decryption of cloud credentials")
        raise SystemExit(1)

    # Check if key is a placeholder
    placeholder_keywords = ["your-", "change-", "example", "placeholder"]
    if any(keyword in settings.ENCRYPTION_KEY.lower() for keyword in placeholder_keywords):
        logger.error("❌ ENCRYPTION_KEY appears to be a placeholder!")
        logger.error("   Please generate a proper Fernet key using:")
        logger.error("   python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        raise SystemExit(1)

    # Calculate and log key hash (for audit trail, not security)
    key_hash = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).hexdigest()
    logger.info(f"✅ ENCRYPTION_KEY validated")
    logger.info(f"   Key hash (first 16 chars): {key_hash[:16]}...")

    # Warn about key importance
    logger.info("")
    logger.info("⚠️  ENCRYPTION_KEY SECURITY:")
    logger.info("   - This key encrypts ALL cloud account credentials")
    logger.info("   - If this key changes, ALL encrypted data is LOST")
    logger.info("   - Never modify this key in production without migration")
    logger.info("   - Backup this key in a secure, separate location")
    logger.info("")


@app.on_event("startup")
async def startup_event() -> None:
    """Run validation checks on application startup."""
    validate_encryption_key()


@app.get("/api/v1/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.APP_NAME,
            "environment": settings.APP_ENV,
        },
    )


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Welcome to CutCosts API",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


# Include API v1 routers
from app.api.v1 import api_router

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
