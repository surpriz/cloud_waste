"""Rate limiting configuration using SlowAPI and Redis."""

from typing import Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def get_user_identifier(request: Request) -> str:
    """
    Get rate limit identifier from request.

    Priority order:
    1. User ID from JWT token (if authenticated)
    2. IP address (for non-authenticated requests)

    Args:
        request: FastAPI request object

    Returns:
        Unique identifier string for rate limiting
    """
    # Try to get user from request state (set by auth dependency)
    if hasattr(request.state, "user") and request.state.user:
        user_id = getattr(request.state.user, "id", None)
        if user_id:
            return f"user:{user_id}"

    # Fallback to IP address
    return f"ip:{get_remote_address(request)}"


# Initialize SlowAPI limiter with Redis backend
limiter = Limiter(
    key_func=get_user_identifier,
    storage_uri=str(settings.REDIS_URL),
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[settings.RATE_LIMIT_API_DEFAULT],
    headers_enabled=True,  # Add X-RateLimit-* headers to responses
)


def rate_limit_by_ip(limit: str) -> Callable:
    """
    Decorator for rate limiting by IP address only.

    Useful for public endpoints (login, register) where user is not authenticated.

    Args:
        limit: Rate limit string (e.g., "5/minute", "100/hour")

    Returns:
        Rate limit decorator

    Example:
        @rate_limit_by_ip("5/minute")
        async def login(...)
    """
    def _get_ip(request: Request) -> str:
        return f"ip:{get_remote_address(request)}"

    return limiter.limit(limit, key_func=_get_ip)


# Pre-configured rate limit decorators for common use cases
# These can be applied directly to endpoints

# Authentication endpoints (most critical - prevent brute-force)
auth_login_limit = limiter.limit(settings.RATE_LIMIT_AUTH_LOGIN)
auth_register_limit = limiter.limit(settings.RATE_LIMIT_AUTH_REGISTER)
auth_refresh_limit = limiter.limit(settings.RATE_LIMIT_AUTH_REFRESH)

# Scan endpoints (resource-intensive operations)
scan_limit = limiter.limit(settings.RATE_LIMIT_SCANS)

# Admin endpoints
admin_limit = limiter.limit(settings.RATE_LIMIT_ADMIN)

# General API endpoints (default)
api_default_limit = limiter.limit(settings.RATE_LIMIT_API_DEFAULT)
