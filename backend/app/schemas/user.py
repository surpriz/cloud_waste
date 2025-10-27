"""User Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# Shared properties
class UserBase(BaseModel):
    """Base user schema with common attributes."""

    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    email_verified: bool = False


# Properties to receive via API on creation
class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str | None = None


# Properties to receive via API on update
class UserUpdate(BaseModel):
    """Schema for user update."""

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=100)
    full_name: str | None = None
    is_active: bool | None = None


# Properties to receive via API on admin update
class UserAdminUpdate(BaseModel):
    """Schema for admin user update (can modify is_superuser)."""

    is_active: bool | None = None
    is_superuser: bool | None = None


# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    """User schema with database fields."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Additional properties to return via API
class User(UserInDBBase):
    """User schema for API responses."""

    pass


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    """User schema with hashed password (internal use only)."""

    hashed_password: str
