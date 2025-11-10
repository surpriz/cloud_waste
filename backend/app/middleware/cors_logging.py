"""CORS Logging Middleware for security monitoring."""

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class CORSLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log CORS requests for security monitoring.

    This middleware logs:
    - All cross-origin requests (Origin header present)
    - CORS preflight OPTIONS requests
    - Origin domain and requested path
    - Response status code

    Usage:
        app.add_middleware(CORSLoggingMiddleware)

    Security Benefits:
    - Detect unauthorized cross-origin access attempts
    - Monitor which origins are making requests
    - Audit trail for CORS-related issues
    - Alert on suspicious patterns

    Logging format:
    - Uses structlog for structured JSON logging
    - Includes: origin, method, path, status_code, is_preflight
    """

    def __init__(self, app: ASGIApp, log_all_requests: bool = False):
        """
        Initialize CORS logging middleware.

        Args:
            app: ASGI application
            log_all_requests: If True, log all requests (not just cross-origin).
                             Default False to reduce log volume.
        """
        super().__init__(app)
        self.log_all_requests = log_all_requests

    async def dispatch(self, request: Request, call_next):
        """
        Process request and log CORS information.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Get origin header (present in cross-origin requests)
        origin = request.headers.get("Origin")

        # Check if this is a CORS preflight request
        is_preflight = request.method == "OPTIONS" and origin is not None

        # Log cross-origin requests or all requests if configured
        if origin or self.log_all_requests:
            # Process request and get response
            response: Response = await call_next(request)

            # Prepare log context
            log_context = {
                "event": "cors.request",
                "method": request.method,
                "path": request.url.path,
                "origin": origin or "same-origin",
                "is_preflight": is_preflight,
                "status_code": response.status_code,
                "user_agent": request.headers.get("User-Agent", "unknown"),
            }

            # Log level based on response status
            if response.status_code >= 400:
                # Log errors/rejections at warning level
                if response.status_code == 403:
                    logger.warning(
                        "cors.request_forbidden",
                        **log_context,
                        reason="Origin likely not in ALLOWED_ORIGINS whitelist",
                    )
                else:
                    logger.warning("cors.request_failed", **log_context)
            else:
                # Log successful requests at info level
                if is_preflight:
                    logger.info("cors.preflight_success", **log_context)
                else:
                    logger.debug("cors.request_success", **log_context)

            return response
        else:
            # Not a cross-origin request, pass through without logging
            return await call_next(request)
