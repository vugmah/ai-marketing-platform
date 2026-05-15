"""Authentication service layer with real async database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import TokenResponse, UserRegister, UserResponse
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.config import settings
from app.database import get_db_context
from app.exceptions import AlreadyExistsError, AuthenticationError, NotFoundError
from app.redis_client import get_redis_client


def _user_to_response(user: User) -> UserResponse:
    """Convert User model instance to UserResponse schema."""
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        company_id=user.company_id,
        branch_id=user.branch_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def register_user(data: UserRegister) -> UserResponse:
    """Register a new user with real database operations.

    Args:
        data: User registration data.

    Returns:
        Created user response.

    Raises:
        AlreadyExistsError: If a user with the same email already exists.
    """
    email = data.email.lower().strip()

    async with get_db_context() as db:
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            raise AlreadyExistsError(
                detail=f"User with email '{email}' already exists"
            )

        # Create new user
        user = User(
            email=email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role="user",
            company_id=None,
            branch_id=None,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return _user_to_response(user)


async def login_user(email: str, password: str) -> TokenResponse:
    """Authenticate a user against the database and return tokens.

    Args:
        email: User email address.
        password: Plain text password.

    Returns:
        Token response with access and refresh tokens.

    Raises:
        AuthenticationError: If credentials are invalid.
    """
    email = email.lower().strip()

    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationError(detail="Invalid email or password")

        if not verify_password(password, user.password_hash):
            raise AuthenticationError(detail="Invalid email or password")

        if not user.is_active:
            raise AuthenticationError(detail="Account is deactivated")

        token_payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
        }

        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )


async def get_current_user(token: str) -> UserResponse:
    """Get the current user from an access token via database lookup.

    Args:
        token: JWT access token.

    Returns:
        Current user response.

    Raises:
        AuthenticationError: If the token is invalid, revoked, or user not found.
    """
    try:
        payload = verify_token(token)
    except ValueError as exc:
        raise AuthenticationError(detail=str(exc)) from exc

    # Check if token is revoked in Redis
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{token}")
    if revoked:
        raise AuthenticationError(detail="Token has been revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(detail="Invalid token payload")

    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundError(detail="User not found")

        if not user.is_active:
            raise AuthenticationError(detail="Account is deactivated")

        return _user_to_response(user)


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    """Refresh the access token using a refresh token.

    Args:
        refresh_token: JWT refresh token.

    Returns:
        New token response with fresh access and refresh tokens.

    Raises:
        AuthenticationError: If the refresh token is invalid or revoked.
    """
    try:
        payload = verify_token(refresh_token)
    except ValueError as exc:
        raise AuthenticationError(detail=f"Invalid refresh token: {exc}") from exc

    # Check if refresh token is revoked in Redis
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{refresh_token}")
    if revoked:
        raise AuthenticationError(detail="Refresh token has been revoked")

    # Check token type
    token_type = payload.get("type")
    if token_type != "refresh":
        raise AuthenticationError(detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(detail="Invalid token payload")

    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise NotFoundError(detail="User not found")

        if not user.is_active:
            raise AuthenticationError(detail="Account is deactivated")

        token_payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
        }

        new_access_token = create_access_token(token_payload)
        new_refresh_token = create_refresh_token(token_payload)

        # Revoke the old refresh token in Redis
        await redis.setex(
            f"revoked:{refresh_token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "1",
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )


async def logout_user(
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> None:
    """Logout a user by revoking their tokens in Redis.

    Args:
        access_token: Optional access token to revoke.
        refresh_token: Optional refresh token to revoke.
    """
    redis = await get_redis_client()

    if access_token:
        await redis.setex(
            f"revoked:{access_token}",
            settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            "1",
        )

    if refresh_token:
        await redis.setex(
            f"revoked:{refresh_token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "1",
        )
