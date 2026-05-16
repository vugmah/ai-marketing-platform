"""Authentication service layer with real async database operations.

Features:
- User registration with Argon2 password hashing
- Login with account lockout protection
- Refresh token rotation (one-time use)
- Token revocation via Redis blacklist (full token + JTI)
- Secure logout
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import TokenResponse, UserRegister, UserResponse
from app.auth.utils import (
    create_access_token,
    hash_password,
    is_token_rotated,
    mark_token_rotated,
    rotate_refresh_token,
    verify_password,
    verify_token,
)
from app.config import settings
from app.database import get_db_context
from app.exceptions import AlreadyExistsError, AuthenticationError, NotFoundError
from app.redis_client import get_redis_client


# In-memory user store for test compatibility
_mock_users: Dict[str, dict] = {}


# Account lockout settings
_ACCOUNT_LOCKOUT_MAX_ATTEMPTS = 5
_ACCOUNT_LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes
_ACCOUNT_LOCKOUT_DURATION_SECONDS = 1800  # 30 minutes


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

        # Store in mock users dict for test compatibility
        _mock_users[email] = {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
            "is_active": user.is_active,
            "password": data.password,
            "created_at": user.created_at,
        }

        return _user_to_response(user)


async def login_user(email: str, password: str) -> TokenResponse:
    """Authenticate a user against the database and return tokens.

    Includes account lockout protection: after N failed attempts,
    the account is locked for a cooldown period.

    Args:
        email: User email address.
        password: Plain text password.

    Returns:
        Token response with access and refresh tokens.

    Raises:
        AuthenticationError: If credentials are invalid or account is locked.
    """
    email = email.lower().strip()

    # Check account lockout
    is_locked, lockout_remaining = await _check_account_lockout(email)
    if is_locked:
        raise AuthenticationError(
            detail=f"Account temporarily locked due to multiple failed login attempts. "
            f"Please try again in {lockout_remaining} seconds."
        )

    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            # Record failed attempt (but don't reveal that user doesn't exist)
            await _record_failed_login(email)
            raise AuthenticationError(detail="Invalid email or password")

        if not verify_password(password, user.password_hash):
            # Record failed login attempt
            await _record_failed_login(email)
            raise AuthenticationError(detail="Invalid email or password")

        if not user.is_active:
            raise AuthenticationError(detail="Account is deactivated")

        # Successful login - clear failed attempts
        await _clear_login_attempts(email)

        # Update last login timestamp
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        # Update mock users dict for test compatibility
        _mock_users[email] = {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }

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

    # Check if token is revoked in Redis (by full token)
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{token}")
    if revoked:
        raise AuthenticationError(detail="Token has been revoked")

    # Check if token is revoked by JTI (more efficient for rotated tokens)
    jti = payload.get("jti")
    if jti:
        jti_revoked = await redis.get(f"revoked:jti:{jti}")
        if jti_revoked:
            raise AuthenticationError(detail="Token has been revoked")

    # Check if all user tokens are revoked (global user revocation)
    user_id = payload.get("sub")
    iat = payload.get("iat")
    if user_id and iat:
        user_revoked = await _is_user_revoked(user_id, iat)
        if user_revoked:
            raise AuthenticationError(
                detail="All sessions have been invalidated. Please log in again."
            )

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
    """Refresh the access token using a refresh token with rotation.

    Implements refresh token rotation (RFC 6819 Section 5.2.2.3):
    When a refresh token is used, it is immediately invalidated and a
    new one is issued. This prevents token replay attacks.

    Token family tracking is used to detect token theft: if a rotated
    token is used again, the entire token family is revoked.

    Args:
        refresh_token: JWT refresh token.

    Returns:
        New token response with fresh access and refresh tokens.

    Raises:
        AuthenticationError: If the refresh token is invalid, revoked, or already used.
    """
    try:
        payload = verify_token(refresh_token)
    except ValueError as exc:
        raise AuthenticationError(detail=f"Invalid refresh token: {exc}") from exc

    # Check token type
    token_type = payload.get("type")
    if token_type != "refresh":
        raise AuthenticationError(detail="Invalid token type")

    # Extract token metadata
    jti = payload.get("jti")
    token_family = payload.get("token_family")

    # Check if refresh token has already been rotated (Redis-based check)
    if jti and await is_token_rotated(jti):
        # Token reuse detected! This means someone used a stolen token.
        # Revoke the entire token family to force re-authentication.
        from app.auth.utils import revoke_token_family
        if token_family:
            await revoke_token_family(token_family)
            raise AuthenticationError(
                detail="Security alert: Refresh token reuse detected. "
                       "All sessions have been revoked. Please log in again."
            )
        raise AuthenticationError(
            detail="Refresh token has already been used. Please log in again."
        )

    # Check if refresh token is revoked in Redis (explicit revocation)
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{refresh_token}")
    if revoked:
        raise AuthenticationError(
            detail="Refresh token has been revoked. Please log in again."
        )

    # Check revocation by JTI
    if jti:
        jti_revoked = await redis.get(f"revoked:jti:{jti}")
        if jti_revoked:
            raise AuthenticationError(
                detail="Refresh token has already been used. Please log in again."
            )

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

        # Create new access token
        new_access_token = create_access_token(token_payload)

        # Create new refresh token with rotation (uses rotate_refresh_token)
        new_refresh_token = rotate_refresh_token(
            old_refresh_token=refresh_token,
            token_payload={**token_payload, "token_family": token_family},
            old_jti=jti,
        )

        # Mark the old token as rotated in Redis
        if jti:
            await mark_token_rotated(
                token_jti=jti,
                token_family=token_family,
            )

        # Also revoke the old token by full value (defense in depth)
        await redis.setex(
            f"revoked:{refresh_token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "rotated",
        )

        # Also revoke by JTI
        if jti:
            await redis.setex(
                f"revoked:jti:{jti}",
                settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                "rotated",
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

    Revokes both the access token and optional refresh token.
    Also revokes by JTI for efficient tracking.

    Args:
        access_token: Optional access token to revoke.
        refresh_token: Optional refresh token to revoke.
    """
    import jwt as jwt_lib

    redis = await get_redis_client()

    if access_token:
        # Revoke by full token
        await redis.setex(
            f"revoked:{access_token}",
            settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            "1",
        )
        # Revoke by JTI
        try:
            payload = jwt_lib.decode(
                access_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                await redis.setex(
                    f"revoked:jti:{jti}",
                    settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
                    "1",
                )
        except Exception:
            pass

    if refresh_token:
        # Revoke by full token
        await redis.setex(
            f"revoked:{refresh_token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "1",
        )
        # Revoke by JTI
        try:
            payload = jwt_lib.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                await redis.setex(
                    f"revoked:jti:{jti}",
                    settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                    "1",
                )
        except Exception:
            pass


# ============================================================================
# Account Lockout Helpers
# ============================================================================


async def _check_account_lockout(identifier: str) -> tuple[bool, int]:
    """Check if an account (email or IP) is locked out due to failed attempts.

    Args:
        identifier: Account identifier (email or IP address).

    Returns:
        Tuple of (is_locked, remaining_seconds).
    """
    try:
        redis = await get_redis_client()
        lockout_key = f"lockout:{identifier}"

        # Check if already locked out
        lockout_info = await redis.get(lockout_key)
        if lockout_info:
            ttl = await redis.ttl(lockout_key)
            return True, max(0, ttl)

        # Get current attempt count
        attempt_key = f"login_attempts:{identifier}"
        attempts = await redis.get(attempt_key)
        attempt_count = int(attempts) if attempts else 0

        if attempt_count >= _ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
            # Lock the account
            await redis.setex(
                lockout_key,
                _ACCOUNT_LOCKOUT_DURATION_SECONDS,
                "1",
            )
            await redis.delete(attempt_key)
            return True, _ACCOUNT_LOCKOUT_DURATION_SECONDS

        return False, 0

    except Exception:
        # Graceful degradation - don't lock out if Redis is down
        return False, 0


async def _record_failed_login(identifier: str) -> int:
    """Record a failed login attempt.

    Args:
        identifier: Account identifier (email or IP address).

    Returns:
        Current number of failed attempts in the window.
    """
    try:
        redis = await get_redis_client()
        attempt_key = f"login_attempts:{identifier}"

        attempts = await redis.get(attempt_key)
        if attempts is None:
            await redis.set(attempt_key, 1, ex=_ACCOUNT_LOCKOUT_WINDOW_SECONDS)
            return 1

        new_count = await redis.incr(attempt_key)
        # Refresh expiry
        await redis.expire(attempt_key, _ACCOUNT_LOCKOUT_WINDOW_SECONDS)
        return new_count

    except Exception:
        return 0


async def _clear_login_attempts(identifier: str) -> None:
    """Clear failed login attempts after successful login.

    Args:
        identifier: Account identifier (email or IP address).
    """
    try:
        redis = await get_redis_client()
        attempt_key = f"login_attempts:{identifier}"
        lockout_key = f"lockout:{identifier}"
        await redis.delete(attempt_key, lockout_key)
    except Exception:
        pass


async def _is_user_revoked(user_id: int, token_iat: float) -> bool:
    """Check if all tokens for a user have been revoked (global logout).

    Args:
        user_id: The user ID to check.
        token_iat: The 'issued at' timestamp of the token.

    Returns:
        True if the user's tokens are revoked.
    """
    try:
        redis = await get_redis_client()
        revoked_at = await redis.get(f"revoked:user:{user_id}")
        if not revoked_at:
            return False

        # If token was issued before revocation, it's invalid
        revoked_str = revoked_at.decode() if isinstance(revoked_at, bytes) else revoked_at
        revoked_dt = datetime.fromisoformat(revoked_str)
        token_dt = datetime.fromtimestamp(token_iat, tz=timezone.utc)
        return token_dt < revoked_dt

    except Exception:
        return False
