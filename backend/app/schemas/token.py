"""Token schemas for authentication."""

from pydantic import BaseModel


class Token(BaseModel):
    """Access token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token payload data."""

    sub: str | None = None  # subject (user ID)
    exp: int | None = None  # expiration timestamp
    type: str | None = None  # token type (access or refresh)


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""

    refresh_token: str
