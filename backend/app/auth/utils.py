"""Authentication utilities: JWT tokens, password hashing, and refresh token rotation."""

import secrets
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
        "jti": secrets.token_hex(16),  # Unique token ID for revocation tracking
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
        "jti": secrets.token_hex(16),  # Unique token ID for rotation tracking
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


# ============================================================================
# Refresh Token Rotation
# ============================================================================


_ROTATED_TOKEN_PREFIX = "rotated:"
_TOKEN_FAMILY_PREFIX = "token_family:"


def rotate_refresh_token(
    old_refresh_token: str,
    token_payload: Dict,
    old_jti: Optional[str] = None,
) -> str:
    """Generate a new refresh token and mark the old one as rotated.

    Refresh token rotation ensures that each refresh token can only be used once.
    When a refresh token is used, it is immediately invalidated and a new one
    is issued. This prevents token replay attacks.

    Token family tracking links all refresh tokens in a chain, so if a rotated
    token is used again, the entire family can be revoked (detect token theft).

    Args:
        old_refresh_token: The refresh token being consumed.
        token_payload: The payload data for the new token (must include 'sub').
        old_jti: The JTI of the old token (for family tracking).

    Returns:
        A new refresh token string.

    Raises:
        ValueError: If the token payload does not contain a subject ('sub').
    """
    if "sub" not in token_payload:
        raise ValueError("Token payload must include 'sub' (user ID)")

    # Generate new token family ID if not present
    token_family = token_payload.get("token_family") or secrets.token_hex(8)

    # Create new refresh token with rotation metadata
    new_payload = {
        "sub": token_payload["sub"],
        "email": token_payload.get("email"),
        "role": token_payload.get("role"),
        "company_id": token_payload.get("company_id"),
        "branch_id": token_payload.get("branch_id"),
    }

    now = datetime.now(timezone.utc)
    new_payload.update({
        "iat": now,
        "type": "refresh",
        "jti": secrets.token_hex(16),  # Fresh unique token ID
        "rotated_from": old_jti or "unknown",
        "token_family": token_family,
        "rotation_count": token_payload.get("rotation_count", 0) + 1,
    })

    new_token = create_refresh_token(new_payload)
    return new_token


async def mark_token_rotated(
    token_jti: str,
    token_family: Optional[str] = None,
    expire_seconds: Optional[int] = None,
) -> None:
    """Mark a refresh token as rotated (used) in Redis.

    Prevents the same refresh token from being used twice.
    Also tracks token families for theft detection.

    Args:
        token_jti: The JTI of the token that was rotated.
        token_family: Optional token family ID for chain tracking.
        expire_seconds: How long to keep the rotation record.
    """
    from app.redis_client import get_redis_client

    if expire_seconds is None:
        expire_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400

    try:
        redis = await get_redis_client()

        # Mark individual token as rotated
        await redis.setex(
            f"{_ROTATED_TOKEN_PREFIX}{token_jti}",
            expire_seconds,
            "1",
        )

        # Track in token family for theft detection
        if token_family:
            await redis.sadd(
                f"{_TOKEN_FAMILY_PREFIX}{token_family}",
                token_jti,
            )
            await redis.expire(
                f"{_TOKEN_FAMILY_PREFIX}{token_family}",
                expire_seconds,
            )

    except Exception:
        # If Redis is down, we can't track rotation - but we still issue
        # the new token. The old token will expire naturally.
        pass


async def is_token_rotated(token_jti: str) -> bool:
    """Check if a refresh token has already been rotated.

    Args:
        token_jti: The JTI of the token to check.

    Returns:
        True if the token has already been used (rotated).
    """
    from app.redis_client import get_redis_client

    try:
        redis = await get_redis_client()
        rotated = await redis.get(f"{_ROTATED_TOKEN_PREFIX}{token_jti}")
        return rotated is not None
    except Exception:
        # If Redis is down, we can't check - assume not rotated
        # This is a security trade-off for availability
        return False


async def revoke_token_family(token_family: str) -> None:
    """Revoke all tokens in a token family (theft detection response).

    When a rotated token is used again (indicating token theft),
    revoke the entire token family to force re-authentication.

    Args:
        token_family: The token family ID to revoke.
    """
    from app.redis_client import get_redis_client

    try:
        redis = await get_redis_client()

        # Get all JTIs in the family
        jtis = await redis.smembers(f"{_TOKEN_FAMILY_PREFIX}{token_family}")

        # Revoke each JTI
        pipe = redis.pipeline()
        for jti in jtis:
            jti_str = jti.decode() if isinstance(jti, bytes) else jti
            pipe.setex(
                f"revoked:jti:{jti_str}",
                settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                "family_revoked",
            )
            pipe.setex(
                f"{_ROTATED_TOKEN_PREFIX}{jti_str}",
                settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                "family_revoked",
            )
        await pipe.execute()

        # Clean up the family set
        await redis.delete(f"{_TOKEN_FAMILY_PREFIX}{token_family}")

    except Exception:
        pass


# ============================================================================
# Token fingerprinting (bind token to client for additional security)
# ============================================================================


def generate_token_fingerprint(request_info: Dict) -> str:
    """Generate a client fingerprint for token binding.

    Binds the token to a specific client fingerprint (user-agent + IP hash).
    If the fingerprint changes significantly, the token may be stolen.

    Args:
        request_info: Dict with 'user_agent' and 'ip' keys.

    Returns:
        A short fingerprint hash.
    """
    import hashlib

    user_agent = request_info.get("user_agent", "")
    ip = request_info.get("ip", "")
    # Use first 16 chars of user-agent and first 2 octets of IP
    # This allows for minor changes (browser updates) but catches major changes
    ua_snippet = user_agent[:32].lower() if user_agent else ""
    ip_parts = ip.split(".")
    ip_prefix = ".".join(ip_parts[:2]) if "." in ip else ip[:8]

    fingerprint_data = f"{ua_snippet}:{ip_prefix}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


def verify_token_fingerprint(token_payload: Dict, request_info: Dict) -> bool:
    """Verify that a token's fingerprint matches the current request.

    Args:
        token_payload: The decoded JWT payload.
        request_info: Dict with 'user_agent' and 'ip' keys.

    Returns:
        True if the fingerprint matches or no fingerprint was set.
    """
    stored_fp = token_payload.get("fp")
    if not stored_fp:
        return True  # No fingerprint = no binding (backward compatible)

    current_fp = generate_token_fingerprint(request_info)
    return stored_fp == current_fp
