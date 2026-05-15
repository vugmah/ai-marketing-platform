"""FastAPI dependencies for database, Redis, auth, and RBAC."""

from typing import List

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

    # Check if token is revoked in Redis
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{token}")
    if revoked:
        raise AuthenticationError(detail="Token has been revoked")

    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError(detail="User not found")

    if not user.is_active:
        raise AuthenticationError(detail="User account is deactivated")

    return user


def require_role(allowed_roles: List[str]):
    """Dependency factory that checks if the current user has one of the required roles.

    Args:
        allowed_roles: List of allowed role names.

    Returns:
        Dependency function that validates user role.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(["admin"]))):
            ...
    """

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise AuthorizationError(
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return user

    return role_checker
