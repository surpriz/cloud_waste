"""CRUD operations for User model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
