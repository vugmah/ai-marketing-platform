"""Authentication utilities: JWT tokens and password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt
from passlib.context import CryptContext

from app.config import settings

# Password hashing context with Argon2
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data (must include 'sub' for user ID).
        expires_delta: Optional custom expiry duration.

    Returns:
        Encoded JWT access token string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
    })

    token = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


def create_refresh_token(data: Dict) -> str:
    """Create a JWT refresh token.

    Args:
        data: Payload data (must include 'sub' for user ID).

    Returns:
        Encoded JWT refresh token string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
    })

    token = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token


def verify_token(token: str) -> Dict:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token string to verify.

    Returns:
        Decoded token payload as dictionary.

    Raises:
        ValueError: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def hash_password(password: str) -> str:
    """Hash a password using Argon2.

    Args:
        password: Plain text password.

    Returns:
        Argon2 hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its Argon2 hash.

    Args:
        password: Plain text password to verify.
        hashed: Stored Argon2 hash.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def decode_token_without_verification(token: str) -> Dict:
    """Decode a JWT token without verifying the signature or expiry.

    Useful for extracting data from an expired token (e.g., for refresh).

    Args:
        token: The JWT token string.

    Returns:
        Decoded token payload as dictionary.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": False, "verify_signature": True},
    )
