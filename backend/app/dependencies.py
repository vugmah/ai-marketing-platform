"""FastAPI dependencies for database, Redis, auth, and RBAC."""

from typing import List, Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.utils import verify_token
from app.database import get_db as db_session
from app.exceptions import AuthenticationError, AuthorizationError
from app.redis_client import get_redis_client

security = HTTPBearer(auto_error=False)


async def get_db():
    """Database session dependency."""
    async for session in db_session():
        yield session


async def get_redis_dep():
    """Redis client dependency."""
    redis = await get_redis_client()
    yield redis


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and verify the current user from JWT token + database.

    Priority:
    1. Authorization header (Bearer token)
    2. request.state.user (set by AuthMiddleware)

    Args:
        authorization: Authorization header with Bearer token.
        db: Async database session.

    Returns:
        Authenticated User model instance from database.

    Raises:
        AuthenticationError: If token is missing, invalid, revoked, or user not found.
    """
    # Check if middleware already set the user
    if authorization is None:
        raise AuthenticationError(detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise AuthenticationError(detail="Bearer token required")

    token = authorization.replace("Bearer ", "")

    try:
        payload = verify_token(token)
    except ValueError as exc:
        raise AuthenticationError(detail=str(exc)) from exc

    # Check if token is revoked in Redis (by full token)
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{token}")
    if revoked:
        raise AuthenticationError(detail="Token has been revoked")

    # Check if token is revoked by JTI
    jti = payload.get("jti")
    if jti:
        jti_revoked = await redis.get(f"revoked:jti:{jti}")
        if jti_revoked:
            raise AuthenticationError(detail="Token has been revoked")

    # Check if all user tokens are revoked (global user revocation)
    user_id = payload.get("sub")
    iat = payload.get("iat")
    if user_id and iat:
        from app.auth.service import _is_user_revoked
        user_revoked = await _is_user_revoked(user_id, iat)
        if user_revoked:
            raise AuthenticationError(
                detail="All sessions have been invalidated. Please log in again."
            )

    if not user_id:
        raise AuthenticationError(detail="Invalid token payload")

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError(detail="User not found")

    if not user.is_active:
        raise AuthenticationError(detail="User account is deactivated")

    return user


def require_role(allowed_roles: List[str]):
    """Dependency factory that checks if the current user has one of the required roles.

    Uses role hierarchy: higher-level roles implicitly include lower-level permissions.
    For example, a 'super_admin' passes a check for ['company_admin'].

    Args:
        allowed_roles: List of allowed role names.

    Returns:
        Dependency function that validates user role.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(["company_admin"]))):
            ...
    """
    # Role hierarchy for inheritance
    ROLE_HIERARCHY = {
        "super_admin": 6,
        "company_admin": 5,
        "branch_manager": 4,
        "marketing_manager": 3,
        "support_agent": 2,
        "analyst": 1,
    }

    # Minimum required level
    min_required_level = min(
        ROLE_HIERARCHY.get(role, 0) for role in allowed_roles
    )

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        if user_level < min_required_level:
            raise AuthorizationError(
                detail=f"Access denied. Required role level: {min_required_level} "
                f"(one of: {', '.join(allowed_roles)}). Your role: {user.role} (level {user_level})."
            )
        return user

    return role_checker


def require_roles_exact(allowed_roles: List[str]):
    """Dependency factory that checks for exact role match (no inheritance).

    Args:
        allowed_roles: List of exactly allowed role names.

    Returns:
        Dependency function that validates user role exactly.
    """

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise AuthorizationError(
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}. "
                f"Your role: {user.role}."
            )
        return user

    return role_checker


async def get_optional_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Extract user from token if present, but don't require authentication.

    Args:
        authorization: Optional Authorization header.
        db: Async database session.

    Returns:
        User instance if authenticated, None otherwise.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        return await get_current_user(authorization, db)
    except Exception:
        return None


async def require_company_access(
    user: User = Depends(get_current_user),
) -> User:
    """Ensure the user has a company assigned (not a super_admin without company).

    Args:
        user: Current authenticated user.

    Returns:
        User if they have company access.

    Raises:
        AuthorizationError: If user has no company assignment.
    """
    if user.role == "super_admin":
        return user  # Super admins can access everything

    if user.company_id is None:
        raise AuthorizationError(
            detail="No company assigned. Please contact your administrator."
        )

    return user


async def get_company_id(
    user: User = Depends(require_company_access),
) -> str:
    """Extract company_id from authenticated user."""
    return str(user.company_id)


async def get_optional_company_id(
    user: Optional[User] = Depends(get_optional_user),
) -> Optional[str]:
    """Optionally extract company_id from user (if authenticated)."""
    if user is None or user.company_id is None:
        return None
    return str(user.company_id)
