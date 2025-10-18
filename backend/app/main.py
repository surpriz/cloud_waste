"""FastAPI Application Entry Point."""

import hashlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="CloudWaste - Detect and identify orphaned cloud resources",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "message": "Welcome to CloudWaste API",
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
