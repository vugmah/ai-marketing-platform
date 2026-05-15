"""Authentication API router."""

from fastapi import APIRouter, Depends, Header, Request, status

from app.auth.schemas import (
    LogoutRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.auth.service import (
    get_current_user as svc_get_current_user,
    login_user,
    logout_user,
    refresh_access_token,
    register_user,
)
from app.exceptions import AuthenticationError, ValidationError

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(data: UserRegister) -> UserResponse:
    """Register a new user account.

    Creates a new user with the provided email, password, and profile info.
    Returns the created user data.
    """
    return await register_user(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and get tokens",
)
async def login(data: UserLogin) -> TokenResponse:
    """Authenticate with email and password.

    Returns access and refresh tokens upon successful authentication.
    """
    return await login_user(data.email, data.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
async def refresh(request: Request) -> TokenResponse:
    """Refresh the access token using a refresh token.

    The refresh token should be sent in the Authorization header
    as a Bearer token.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError(detail="Refresh token required in Authorization header")

    refresh_token = auth_header.replace("Bearer ", "")
    return await refresh_access_token(refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke tokens",
)
async def logout(
    request: Request,
    logout_data: LogoutRequest | None = None,
) -> None:
    """Logout the current user and revoke tokens.

    Revokes both the access token and optional refresh token.
    """
    auth_header = request.headers.get("Authorization", "")
    access_token = None
    if auth_header and auth_header.startswith("Bearer "):
        access_token = auth_header.replace("Bearer ", "")

    refresh_token = logout_data.refresh_token if logout_data else None

    await logout_user(access_token=access_token, refresh_token=refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def me(request: Request) -> UserResponse:
    """Get the current authenticated user's profile.

    Requires a valid access token in the Authorization header.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError(detail="Access token required")

    access_token = auth_header.replace("Bearer ", "")
    return await svc_get_current_user(access_token)
