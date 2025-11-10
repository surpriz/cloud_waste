"""Authentication endpoints."""

from datetime import timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.rate_limit import auth_login_limit, auth_refresh_limit, auth_register_limit, limiter
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import User as UserSchema
from app.schemas.user import UserCreate, UserUpdate
from app.services import email_service

router = APIRouter()
logger = structlog.get_logger()


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
@auth_register_limit
async def register(
    request: Request,
    response: Response,
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new user and send verification email.

    Args:
        user_in: User registration data
        db: Database session

    Returns:
        Created user (email_verified=False)

    Raises:
        HTTPException: If email already registered
    """
    # Check if user already exists
    user = await user_crud.get_user_by_email(db, user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user (email_verified defaults to False)
    user = await user_crud.create_user(db, user_in)

    # Generate verification token
    verification_token = await user_crud.set_verification_token(db, user)

    # Send verification email (async but don't wait)
    email_sent = email_service.send_verification_email(
        email=user.email,
        full_name=user.full_name or "User",
        verification_token=verification_token,
    )

    if not email_sent:
        logger.warning(
            "auth.verification_email_failed",
            user_id=str(user.id),
            email=user.email,
        )

    logger.info(
        "auth.user_registered",
        user_id=str(user.id),
        email=user.email,
        email_sent=email_sent,
    )

    return user


@router.post("/login", response_model=Token)
@auth_login_limit
async def login(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    remember_me: Annotated[bool, Form()] = False,
) -> dict[str, str]:
    """
    OAuth2 compatible token login.

    Args:
        db: Database session
        form_data: OAuth2 form with username (email) and password
        remember_me: If True, refresh token expires after 30 days instead of 7

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are incorrect
    """
    user = await user_crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not await user_crud.is_user_active(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Check if email is verified
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email and click the verification link.",
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # Create refresh token with appropriate expiration
    if remember_me:
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_REMEMBER_ME_EXPIRE_DAYS)
    else:
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=refresh_token_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
@auth_refresh_limit
async def refresh_token(
    request: Request,
    response: Response,
    refresh_request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """
    Refresh access token using refresh token.

    Args:
        refresh_request: Refresh token request
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    payload = decode_token(refresh_request.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user exists
    import uuid

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    user = await user_crud.get_user_by_id(db, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not await user_crud.is_user_active(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Create new tokens
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserSchema)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user
    """
    return current_user


@router.get("/verify-email/{token}")
async def verify_email(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """
    Verify user email with token.

    Args:
        token: Email verification token
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or expired
    """
    # Get user by verification token
    user = await user_crud.get_user_by_verification_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Verify email
    await user_crud.verify_user_email(db, user)

    # Send welcome email
    email_sent = email_service.send_welcome_email(
        email=user.email,
        full_name=user.full_name or "User",
    )

    logger.info(
        "auth.email_verified",
        user_id=str(user.id),
        email=user.email,
        welcome_email_sent=email_sent,
    )

    return {
        "message": "Email verified successfully. You can now login.",
    }


@router.post("/resend-verification")
@auth_register_limit  # Same limit as register to prevent email spam
async def resend_verification_email(
    request: Request,
    response: Response,
    email: Annotated[str, Form()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """
    Resend verification email to user.

    Args:
        email: User email address
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If user not found or already verified
    """
    # Get user by email
    user = await user_crud.get_user_by_email(db, email)
    if not user:
        # Don't reveal that user doesn't exist for security
        return {
            "message": "If the email exists and is not verified, a new verification email has been sent.",
        }

    # Check if already verified
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    # Generate new verification token
    verification_token = await user_crud.set_verification_token(db, user)

    # Send verification email
    email_sent = email_service.send_verification_email(
        email=user.email,
        full_name=user.full_name or "User",
        verification_token=verification_token,
    )

    if not email_sent:
        logger.error(
            "auth.resend_verification_failed",
            user_id=str(user.id),
            email=user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email",
        )

    logger.info(
        "auth.verification_email_resent",
        user_id=str(user.id),
        email=user.email,
    )

    return {
        "message": "Verification email sent successfully",
    }


@router.patch("/me", response_model=UserSchema)
async def update_current_user(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Update current user information and preferences.

    Args:
        user_update: User update data (email, password, full_name, email_scan_notifications)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user

    Raises:
        HTTPException: If email is already taken by another user
    """
    # Check if email is being changed and is already taken
    if user_update.email and user_update.email != current_user.email:
        existing_user = await user_crud.get_user_by_email(db, user_update.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Update user
    updated_user = await user_crud.update_user(db, current_user, user_update)

    logger.info(
        "auth.user_updated",
        user_id=str(updated_user.id),
        email=updated_user.email,
        email_scan_notifications=updated_user.email_scan_notifications,
    )

    return updated_user
