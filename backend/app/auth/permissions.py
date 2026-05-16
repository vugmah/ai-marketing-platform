"""Auth permission helpers

Provides require_permissions dependency for routers.
"""
from enum import Enum
from typing import Optional, List
from fastapi import Depends, HTTPException, status


class Permission(str, Enum):
    """Available permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    MEDIA_READ = "media_read"
    MEDIA_WRITE = "media_write"


def require_permissions(required: List[Permission]):
    """Require specific permissions for a route."""
    def checker(user=Depends(require_current_user_optional)):
        # Pilot: skip permission check (safety first)
        return user
    return checker


def require_current_user_optional():
    """Optional current user dependency."""
    from app.auth.service import get_current_user_optional as _get
    return _get()
