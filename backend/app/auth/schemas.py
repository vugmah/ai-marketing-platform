"""Authentication and user Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import validate_email, validate_password


class JWTPayload(BaseModel):
    """JWT token payload structure."""

    sub: str = Field(..., description="User ID (subject)")
    email: str = Field(..., description="User email address")
    role: str = Field(default="user", description="User role")
    company_id: Optional[str] = Field(default=None, description="Company/Tenant ID")
    branch_id: Optional[str] = Field(default=None, description="Branch ID")
    exp: Optional[datetime] = Field(default=None, description="Expiration time")
    iat: Optional[datetime] = Field(default=None, description="Issued at time")
    type: str = Field(default="access", description="Token type: access or refresh")


class UserRegister(BaseModel):
    """User registration request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    company_name: Optional[str] = Field(default=None, max_length=200, description="Company name")
    phone: Optional[str] = Field(default=None, max_length=20, description="Phone number")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        return validate_email(value)


class UserLogin(BaseModel):
    """User login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        return validate_email(value)


class PasswordReset(BaseModel):
    """Password reset request schema."""

    email: EmailStr = Field(..., description="User email address")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        return validate_email(value)


class PasswordChange(BaseModel):
    """Password change request schema (authenticated user)."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password(value)


# Alias for backward compatibility (media/router.py uses TokenData)
TokenData = JWTPayload


class TokenResponse(BaseModel):
    """Token response schema for login and refresh."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    refresh_expires_in: int = Field(default=604800, description="Refresh token expiry in seconds")


class UserResponse(BaseModel):
    """User response schema (public user data)."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    role: str = Field(default="user", description="User role")
    company_id: Optional[str] = Field(default=None, description="Company ID")
    branch_id: Optional[str] = Field(default=None, description="Branch ID")
    is_active: bool = Field(default=True, description="Whether the user is active")
    created_at: Optional[datetime] = Field(default=None, description="Account creation time")

    class Config:
        from_attributes = True


class LogoutRequest(BaseModel):
    """Logout request schema."""

    refresh_token: Optional[str] = Field(default=None, description="Refresh token to revoke")
