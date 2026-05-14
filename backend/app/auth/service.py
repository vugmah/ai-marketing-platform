"""Authentication service layer with mock implementations.

Note: These are mock implementations. In production, replace with real
database operations using the User model and proper async queries.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.auth.schemas import TokenResponse, UserRegister, UserResponse
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.config import settings
from app.exceptions import AlreadyExistsError, AuthenticationError, NotFoundError

# In-memory mock user store for demonstration
# Key: email, Value: dict with user data
_mock_users: Dict[str, Dict] = {}

# Revoked token store (for logout)
_revoked_tokens: set = set()


def _generate_user_id() -> str:
    """Generate a unique user ID."""
    return str(uuid.uuid4())


def _user_to_response(user_data: Dict) -> UserResponse:
    """Convert stored user dict to UserResponse schema."""
    return UserResponse(
        id=user_data["id"],
        email=user_data["email"],
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        role=user_data.get("role", "user"),
        company_id=user_data.get("company_id"),
        branch_id=user_data.get("branch_id"),
        is_active=user_data.get("is_active", True),
        created_at=user_data.get("created_at"),
    )


async def register_user(data: UserRegister) -> UserResponse:
    """Register a new user (mock implementation).

    Args:
        data: User registration data.

    Returns:
        Created user response.

    Raises:
        AlreadyExistsError: If a user with the same email already exists.
    """
    email = data.email.lower().strip()

    if email in _mock_users:
        raise AlreadyExistsError(detail=f"User with email '{email}' already exists")

    user_id = _generate_user_id()
    now = datetime.now(timezone.utc)

    user_data = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(data.password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": "user",
        "company_id": None,
        "branch_id": None,
        "is_active": True,
        "created_at": now,
    }

    _mock_users[email] = user_data

    return _user_to_response(user_data)


async def login_user(email: str, password: str) -> TokenResponse:
    """Authenticate a user and return tokens (mock implementation).

    Args:
        email: User email address.
        password: Plain text password.

    Returns:
        Token response with access and refresh tokens.

    Raises:
        AuthenticationError: If credentials are invalid.
    """
    email = email.lower().strip()
    user_data = _mock_users.get(email)

    if user_data is None:
        # For demo, auto-create user if not exists (remove in production)
        raise AuthenticationError(detail="Invalid email or password")

    if not verify_password(password, user_data["password_hash"]):
        raise AuthenticationError(detail="Invalid email or password")

    if not user_data.get("is_active", True):
        raise AuthenticationError(detail="Account is deactivated")

    token_payload = {
        "sub": user_data["id"],
        "email": user_data["email"],
        "role": user_data.get("role", "user"),
        "company_id": user_data.get("company_id"),
        "branch_id": user_data.get("branch_id"),
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
    """Get the current user from an access token.

    Args:
        token: JWT access token.

    Returns:
        Current user response.

    Raises:
        AuthenticationError: If the token is invalid or user not found.
    """
    try:
        payload = verify_token(token)
    except ValueError as exc:
        raise AuthenticationError(detail=str(exc)) from exc

    if token in _revoked_tokens:
        raise AuthenticationError(detail="Token has been revoked")

    user_id = payload.get("sub")
    email = payload.get("email", "").lower()

    # Find user by email (mock lookup)
    user_data = _mock_users.get(email)
    if user_data is None or user_data["id"] != user_id:
        raise NotFoundError(detail="User not found")

    return _user_to_response(user_data)


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    """Refresh the access token using a refresh token.

    Args:
        refresh_token: JWT refresh token.

    Returns:
        New token response with fresh access and refresh tokens.

    Raises:
        AuthenticationError: If the refresh token is invalid.
    """
    try:
        payload = verify_token(refresh_token)
    except ValueError as exc:
        raise AuthenticationError(detail=f"Invalid refresh token: {exc}") from exc

    if refresh_token in _revoked_tokens:
        raise AuthenticationError(detail="Refresh token has been revoked")

    # Check token type
    token_type = payload.get("type")
    if token_type != "refresh":
        raise AuthenticationError(detail="Invalid token type")

    email = payload.get("email", "").lower()
    user_data = _mock_users.get(email)
    if user_data is None:
        raise NotFoundError(detail="User not found")

    token_payload = {
        "sub": user_data["id"],
        "email": user_data["email"],
        "role": user_data.get("role", "user"),
        "company_id": user_data.get("company_id"),
        "branch_id": user_data.get("branch_id"),
    }

    new_access_token = create_access_token(token_payload)
    new_refresh_token = create_refresh_token(token_payload)

    # Revoke the old refresh token
    _revoked_tokens.add(refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


async def logout_user(access_token: Optional[str] = None, refresh_token: Optional[str] = None) -> None:
    """Logout a user by revoking their tokens.

    Args:
        access_token: Optional access token to revoke.
        refresh_token: Optional refresh token to revoke.
    """
    if access_token:
        _revoked_tokens.add(access_token)
    if refresh_token:
        _revoked_tokens.add(refresh_token)
