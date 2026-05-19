"""Role-Based Access Control (RBAC) middleware.

Enforces role-based access control with a hierarchical role system.
Higher-level roles inherit permissions from lower-level roles.

Role Hierarchy (highest to lowest):
    super_admin     - Full system access
    company_admin   - Company-level management
    branch_manager  - Branch-level management
    marketing_manager - Marketing operations
    support_agent   - Customer support
    analyst         - Read-only analytics
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.exceptions import AuthorizationError

# Role hierarchy: higher number = more permissions
# Each role inherits permissions from all roles below it
ROLE_HIERARCHY = {
    "super_admin": 6,
    "company_admin": 5,
    "branch_manager": 4,
    "marketing_manager": 3,
    "support_agent": 2,
    "analyst": 1,
}

# Role groups for easier permission assignment
ROLE_GROUPS = {
    "admin": ["super_admin", "company_admin"],
    "manager": ["super_admin", "company_admin", "branch_manager", "marketing_manager"],
    "all_staff": ["super_admin", "company_admin", "branch_manager", "marketing_manager", "support_agent", "analyst"],
    "write_access": ["super_admin", "company_admin", "branch_manager", "marketing_manager"],
    "read_access": ["super_admin", "company_admin", "branch_manager", "marketing_manager", "support_agent", "analyst"],
}

# Protected path patterns with minimum required role level
PROTECTED_PATHS: dict = {
    # Admin-only endpoints
    "/api/v2/companies": "admin",
    "/api/v2/audit/security-events": "admin",
    "/api/v2/audit/api-keys": "admin",
    "/api/v2/billing": "admin",
    # Manager-level endpoints
    "/api/v2/branches": "manager",
    "/api/v2/dashboard": "manager",
    "/api/v2/analytics": "read_access",
    "/api/v2/erp": "manager",
    "/api/v2/erp/sync": "manager",
    # Marketing operations
    "/api/v2/campaigns": "write_access",
    "/api/v2/audience": "write_access",
    "/api/v2/ads": "write_access",
    "/api/v2/social": "write_access",
    "/api/v2/social/publish": "manager",
    # AI endpoints - restricted to managers and above
    "/api/v2/ai": "manager",
    "/api/v2/ai/generate": "manager",
    # Media/Creative Studio
    "/api/v2/media": "write_access",
    "/api/v2/media/upload": "write_access",
    # Support - any staff
    "/api/v2/support": "all_staff",
    # Notifications - any authenticated user
    "/api/v2/notifications": "all_staff",
}

# HTTP method to required permission level mapping
METHOD_PERMISSIONS = {
    "GET": "read_access",
    "HEAD": "read_access",
    "OPTIONS": "read_access",
    "POST": "write_access",
    "PUT": "write_access",
    "PATCH": "write_access",
    "DELETE": "admin",
}


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces role-based access control.

    Checks if the authenticated user has the required role for the requested path.
    Should be placed AFTER AuthMiddleware in the middleware stack.

    Supports:
    - Path-based role requirements
    - HTTP method-based permission escalation
    - Hierarchical role inheritance
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        user = getattr(request.state, "user", None)
        path = request.url.path
        method = request.method

        # Skip RBAC for public paths
        public_paths = [
            "/api/health",
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
            "/api/v2/auth/register",
            "/api/v2/auth/login",
            "/api/v2/auth/refresh",
            "/api/v2/auth/forgot-password",
            "/api/v2/auth/reset-password",
            "/api/v2/auth/logout",
        ]

        if any(path.startswith(pp) for pp in public_paths):
            return await call_next(request)

        # If no user is authenticated, let the endpoint handle it
        if user is None:
            return await call_next(request)

        # Check protected paths
        for path_prefix, required_role_or_group in PROTECTED_PATHS.items():
            if path.startswith(path_prefix):
                user_role = user.get("role", "analyst") if isinstance(user, dict) else getattr(user, "role", "analyst")
                user_level = ROLE_HIERARCHY.get(str(user_role).lower(), 0)

                # Resolve role group to minimum level
                min_level = self._resolve_role_requirement(
                    required_role_or_group, method
                )

                if user_level < min_level:
                    raise AuthorizationError(
                        detail=(
                            f"Access denied. Required role level: {min_level} "
                            f"({required_role_or_group}). Your role: {user_role} (level {user_level})."
                        )
                    )

        response = await call_next(request)
        return response

    @staticmethod
    def _resolve_role_requirement(
        requirement: str, method: str = "GET"
    ) -> int:
        """Resolve a role requirement (group or individual role) to a minimum level.

        Args:
            requirement: Role name or group name.
            method: HTTP method for method-based escalation.

        Returns:
            Minimum role level required.
        """
        # Check if it's a group
        if requirement in ROLE_GROUPS:
            group_roles = ROLE_GROUPS[requirement]
            min_level = min(ROLE_HIERARCHY.get(r, 0) for r in group_roles)
        else:
            min_level = ROLE_HIERARCHY.get(requirement, 0)

        # Method-based escalation: DELETE requires admin level
        if method == "DELETE":
            min_level = max(min_level, ROLE_HIERARCHY.get("company_admin", 5))

        return min_level


def has_role(user_role: str, required_role_or_group: str) -> bool:
    """Check if a user role meets the requirement.

    Args:
        user_role: The user's role.
        required_role_or_group: Required role name or group name.

    Returns:
        True if the user has the required role or higher.
    """
    user_level = ROLE_HIERARCHY.get(str(user_role).lower(), 0)

    if required_role_or_group in ROLE_GROUPS:
        group_roles = ROLE_GROUPS[required_role_or_group]
        min_level = min(ROLE_HIERARCHY.get(r, 0) for r in group_roles)
    else:
        min_level = ROLE_HIERARCHY.get(required_role_or_group, 0)

    return user_level >= min_level


def require_min_role(user_role: str, min_role: str) -> bool:
    """Check if user role is at least the minimum required role.

    Args:
        user_role: The user's role.
        min_role: Minimum required role in the hierarchy.

    Returns:
        True if user meets the minimum role requirement.
    """
    user_level = ROLE_HIERARCHY.get(str(user_role).lower(), 0)
    min_level = ROLE_HIERARCHY.get(str(min_role).lower(), 0)
    return user_level >= min_level
