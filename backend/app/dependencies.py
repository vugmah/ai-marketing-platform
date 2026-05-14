"""FastAPI dependencies for database, Redis, auth, and RBAC."""

from typing import List

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.auth.schemas import JWTPayload, UserResponse
from app.auth.utils import verify_token
from app.database import get_db as db_session
from app.exceptions import AuthenticationError, AuthorizationError
from app.redis_client import get_redis

security = HTTPBearer(auto_error=False)


async def get_db():
    """Database session dependency."""
    async for session in db_session():
        yield session


async def get_redis_dep():
    """Redis client dependency."""
    async for redis in get_redis():
        yield redis


async def get_current_user(request: Request) -> UserResponse:
    """Extract and verify the current user from JWT token.

    Priority:
    1. Authorization header (Bearer token)
    2. request.state.user (set by AuthMiddleware)
    """
    # Check if middleware already set the user
    user = getattr(request.state, "user", None)
    if user is not None:
        if isinstance(user, UserResponse):
            return user
        if isinstance(user, dict):
            return UserResponse(**user)

    # Fall back to Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError(detail="Missing or invalid authorization header")

    token = auth_header.replace("Bearer ", "")
    payload = verify_token(token)

    return UserResponse(
        id=payload.get("sub", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "user"),
        company_id=payload.get("company_id"),
        branch_id=payload.get("branch_id"),
    )


def require_role(roles: List[str]):
    """Dependency factory that checks if the current user has one of the required roles.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user=Depends(require_role(["admin"]))):
            ...
    """

    async def role_checker(request: Request) -> UserResponse:
        user = await get_current_user(request)

        if user.role not in roles:
            raise AuthorizationError(
                detail=f"Access denied. Required roles: {', '.join(roles)}"
            )

        return user

    return role_checker
