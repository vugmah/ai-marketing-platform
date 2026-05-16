"""Auth role definitions

Provides UserRole enum for role-based access control.
"""
from enum import Enum


class UserRole(str, Enum):
    """User roles."""
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


def has_role(user, role: UserRole) -> bool:
    """Check if user has a specific role."""
    if hasattr(user, 'role'):
        return user.role == role.value
    return False
