"""Auth dependencies for governance and protected routes.

Re-exports from app.auth.service for backward compatibility.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.service import get_current_user as _get_current_user

security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user from Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await _get_current_user(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed_roles: str):
    """Dependency factory to require specific user roles.
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin", "superadmin"))])
    """
    async def role_checker(user=Depends(get_current_user)):
        user_role = getattr(user, "role", None) or getattr(user, "user_type", None)
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {allowed_roles}",
            )
        return user
    return role_checker
