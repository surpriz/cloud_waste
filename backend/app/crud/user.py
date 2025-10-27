"""CRUD operations for User model."""

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Get user by ID.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        User object or None if not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Get user by email address.

    Args:
        db: Database session
        email: User email

    Returns:
        User object or None if not found
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    Create new user.

    Args:
        db: Database session
        user_in: User creation schema

    Returns:
        Created user object
    """
    db_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_user(
    db: AsyncSession,
    db_user: User,
    user_in: UserUpdate,
) -> User:
    """
    Update existing user.

    Args:
        db: Database session
        db_user: Existing user object
        user_in: User update schema

    Returns:
        Updated user object
    """
    update_data = user_in.model_dump(exclude_unset=True)

    # Hash password if it's being updated
    if "password" in update_data:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """
    Authenticate user with email and password.

    Args:
        db: Database session
        email: User email
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def is_user_active(user: User) -> bool:
    """
    Check if user is active.

    Args:
        user: User object

    Returns:
        True if user is active, False otherwise
    """
    return user.is_active


async def is_user_superuser(user: User) -> bool:
    """
    Check if user is superuser.

    Args:
        user: User object

    Returns:
        True if user is superuser, False otherwise
    """
    return user.is_superuser


async def get_all_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    """
    Get all users (admin only).

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of user objects
    """
    result = await db.execute(
        select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    return list(result.scalars().all())


async def count_users(db: AsyncSession) -> int:
    """
    Count total number of users.

    Args:
        db: Database session

    Returns:
        Total number of users
    """
    from sqlalchemy import func
    result = await db.execute(select(func.count(User.id)))
    return result.scalar_one()


async def count_active_users(db: AsyncSession) -> int:
    """
    Count number of active users.

    Args:
        db: Database session

    Returns:
        Number of active users
    """
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    return result.scalar_one()


async def count_superusers(db: AsyncSession) -> int:
    """
    Count number of superusers.

    Args:
        db: Database session

    Returns:
        Number of superusers
    """
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(User.id)).where(User.is_superuser == True)
    )
    return result.scalar_one()


async def delete_user(db: AsyncSession, db_user: User) -> None:
    """
    Delete user permanently.

    This will CASCADE delete all associated data:
    - Cloud accounts
    - Scans
    - Orphan resources
    - Chat conversations

    Args:
        db: Database session
        db_user: User object to delete
    """
    await db.delete(db_user)
    await db.commit()


def generate_verification_token() -> str:
    """
    Generate a secure random token for email verification.

    Returns:
        URL-safe random token
    """
    return secrets.token_urlsafe(32)


async def set_verification_token(db: AsyncSession, db_user: User) -> str:
    """
    Set verification token for user.

    Args:
        db: Database session
        db_user: User object

    Returns:
        Generated verification token
    """
    token = generate_verification_token()
    expires_at = datetime.utcnow() + timedelta(
        hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
    )

    db_user.email_verification_token = token
    db_user.verification_token_expires_at = expires_at

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return token


async def get_user_by_verification_token(
    db: AsyncSession,
    token: str,
) -> User | None:
    """
    Get user by verification token.

    Args:
        db: Database session
        token: Verification token

    Returns:
        User object or None if not found or expired
    """
    result = await db.execute(
        select(User).where(
            User.email_verification_token == token,
            User.verification_token_expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def verify_user_email(db: AsyncSession, db_user: User) -> User:
    """
    Mark user email as verified.

    Args:
        db: Database session
        db_user: User object

    Returns:
        Updated user object
    """
    db_user.email_verified = True
    db_user.email_verification_token = None
    db_user.verification_token_expires_at = None

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user


async def get_unverified_users_older_than(
    db: AsyncSession,
    days: int,
) -> list[User]:
    """
    Get users whose email is not verified and account is older than specified days.

    Args:
        db: Database session
        days: Number of days

    Returns:
        List of unverified users
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(User).where(
            User.email_verified == False,  # noqa: E712
            User.created_at < cutoff_date,
        )
    )
    return list(result.scalars().all())
