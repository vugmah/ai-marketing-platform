"""Role-Based Access Control (RBAC) middleware."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.exceptions import AuthorizationError

# Define role hierarchy and protected paths
ROLE_HIERARCHY = {
    "superadmin": 4,
    "admin": 3,
    "manager": 2,
    "user": 1,
}

# Protected path patterns with minimum required role level
PROTECTED_PATHS: dict = {
    # "path_prefix": min_role_level
}


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces role-based access control.

    Checks if the authenticated user has the required role for the requested path.
    Should be placed AFTER AuthMiddleware in the middleware stack.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        user = getattr(request.state, "user", None)
        path = request.url.path

        # Skip RBAC for public paths
        public_paths = [
            "/api/health",
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
            "/api/v2/auth/register",
            "/api/v2/auth/login",
            "/api/v2/auth/refresh",
        ]

        if any(path.startswith(pp) for pp in public_paths):
            return await call_next(request)

        # If no user is authenticated, let the endpoint handle it
        if user is None:
            return await call_next(request)

        # Check protected paths
        for path_prefix, min_level in PROTECTED_PATHS.items():
            if path.startswith(path_prefix):
                user_role = user.get("role", "user") if isinstance(user, dict) else getattr(user, "role", "user")
                user_level = ROLE_HIERARCHY.get(user_role, 0)
                if user_level < min_level:
                    raise AuthorizationError(
                        detail=f"Access denied. Required role level: {min_level}"
                    )

        response = await call_next(request)
        return response
