"""Tests for rate limiting functionality."""

import time
from typing import Dict

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings


def parse_rate_limit(limit_str: str) -> tuple[int, int]:
    """
    Parse rate limit string like "5/minute" into (count, seconds).

    Args:
        limit_str: Rate limit string (e.g., "5/minute", "100/hour")

    Returns:
        Tuple of (max_requests, time_window_seconds)
    """
    count, period = limit_str.split("/")
    count = int(count)

    period_map = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }

    seconds = period_map.get(period, 60)  # Default to minute
    return count, seconds


class TestAuthRateLimiting:
    """Test rate limiting for authentication endpoints."""

    def test_login_rate_limit(self, client: TestClient) -> None:
        """
        Test that login endpoint is rate limited.

        Should allow 5 requests per minute, then reject with 429.
        """
        max_requests, _ = parse_rate_limit(settings.RATE_LIMIT_AUTH_LOGIN)

        # Make requests up to the limit
        for i in range(max_requests):
            response = client.post(
                "/api/v1/auth/login",
                data={
                    "username": f"test{i}@example.com",
                    "password": "wrongpassword",
                },
            )
            # Should fail with 401 (wrong credentials) or 403 (inactive user)
            # but NOT with 429 (rate limit)
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ], f"Request {i+1}/{max_requests} failed with unexpected status"

        # Next request should be rate limited
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_register_rate_limit(self, client: TestClient) -> None:
        """
        Test that register endpoint is rate limited.

        Should allow 3 requests per minute, then reject with 429.
        """
        max_requests, _ = parse_rate_limit(settings.RATE_LIMIT_AUTH_REGISTER)

        # Make requests up to the limit
        for i in range(max_requests):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"newuser{i}_{int(time.time())}@example.com",
                    "password": "SecurePassword123!",
                    "full_name": f"Test User {i}",
                },
            )
            # Should succeed (201) or fail with 400 (email exists)
            # but NOT with 429 (rate limit)
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
            ], f"Request {i+1}/{max_requests} failed with unexpected status"

        # Next request should be rate limited
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"newuser_ratelimited_{int(time.time())}@example.com",
                "password": "SecurePassword123!",
                "full_name": "Rate Limited User",
            },
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "X-RateLimit-Limit" in response.headers

    def test_refresh_rate_limit(self, client: TestClient) -> None:
        """
        Test that token refresh endpoint is rate limited.

        Should allow 10 requests per minute, then reject with 429.
        """
        max_requests, _ = parse_rate_limit(settings.RATE_LIMIT_AUTH_REFRESH)

        # Make requests up to the limit
        for i in range(max_requests):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "invalid_token_for_testing"},
            )
            # Should fail with 401 (invalid token)
            # but NOT with 429 (rate limit)
            assert (
                response.status_code == status.HTTP_401_UNAUTHORIZED
            ), f"Request {i+1}/{max_requests} failed with unexpected status"

        # Next request should be rate limited
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token_for_testing"},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "X-RateLimit-Limit" in response.headers


class TestScanRateLimiting:
    """Test rate limiting for scan endpoints."""

    def test_create_scan_rate_limit_unauthenticated(self, client: TestClient) -> None:
        """
        Test that scan creation endpoint is rate limited even without authentication.

        Should reject with 401 (Unauthorized) first, but still count towards rate limit.
        """
        max_requests, _ = parse_rate_limit(settings.RATE_LIMIT_SCANS)

        # Make requests up to the limit (will fail with 401 but count towards limit)
        for i in range(max_requests):
            response = client.post(
                "/api/v1/scans/",
                json={
                    "cloud_account_id": "00000000-0000-0000-0000-000000000000",
                    "scan_type": "full",
                },
            )
            # Should fail with 401 (not authenticated)
            # but NOT with 429 (rate limit)
            assert (
                response.status_code == status.HTTP_401_UNAUTHORIZED
            ), f"Request {i+1}/{max_requests} failed with unexpected status"

        # Next request should be rate limited
        response = client.post(
            "/api/v1/scans/",
            json={
                "cloud_account_id": "00000000-0000-0000-0000-000000000000",
                "scan_type": "full",
            },
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "X-RateLimit-Limit" in response.headers


class TestRateLimitHeaders:
    """Test that rate limit headers are properly included in responses."""

    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        """Test that rate limit headers are included in successful responses."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpassword",
            },
        )

        # Check that rate limit headers are present
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        # Validate header values
        limit = int(response.headers["X-RateLimit-Limit"])
        remaining = int(response.headers["X-RateLimit-Remaining"])
        reset = int(response.headers["X-RateLimit-Reset"])

        assert limit > 0, "Rate limit should be positive"
        assert remaining >= 0, "Remaining should be non-negative"
        assert reset > 0, "Reset timestamp should be positive"


class TestRateLimitConfiguration:
    """Test that rate limiting can be configured via settings."""

    def test_rate_limit_enabled_setting(self) -> None:
        """Test that rate limiting can be disabled via settings."""
        # This test verifies the configuration is loaded correctly
        assert isinstance(settings.RATE_LIMIT_ENABLED, bool)
        assert isinstance(settings.RATE_LIMIT_AUTH_LOGIN, str)
        assert isinstance(settings.RATE_LIMIT_AUTH_REGISTER, str)
        assert isinstance(settings.RATE_LIMIT_SCANS, str)
        assert isinstance(settings.RATE_LIMIT_API_DEFAULT, str)

    def test_rate_limit_format(self) -> None:
        """Test that rate limit strings are in correct format."""
        limits_to_test = [
            settings.RATE_LIMIT_AUTH_LOGIN,
            settings.RATE_LIMIT_AUTH_REGISTER,
            settings.RATE_LIMIT_AUTH_REFRESH,
            settings.RATE_LIMIT_SCANS,
            settings.RATE_LIMIT_ADMIN,
            settings.RATE_LIMIT_API_DEFAULT,
        ]

        for limit_str in limits_to_test:
            # Check format: "number/period"
            assert "/" in limit_str, f"Invalid rate limit format: {limit_str}"
            count, period = limit_str.split("/")

            # Validate count is a positive integer
            assert count.isdigit(), f"Invalid count in rate limit: {limit_str}"
            assert int(count) > 0, f"Count must be positive: {limit_str}"

            # Validate period is valid
            valid_periods = ["second", "minute", "hour", "day"]
            assert period in valid_periods, f"Invalid period in rate limit: {limit_str}"
