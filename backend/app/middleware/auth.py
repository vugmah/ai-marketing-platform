"""Authentication middleware: validates JWT tokens from Authorization header.

Provides:
- JWT token validation from Authorization header
- Revoked token checking via Redis blacklist
- Token payload attachment to request state
- Graceful handling for public paths (no auth required)
- Correlation ID propagation
"""

import secrets
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth.utils import verify_token
from app.redis_client import get_redis_client


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates JWT tokens and attaches user info to request state.

    Checks:
    1. Authorization header presence and format
    2. JWT signature validity and expiry
    3. Token revocation status (Redis blacklist)
    4. Token type validation (access tokens only for API requests)

    Note: This middleware runs before route handlers. The actual user lookup
    should be done in the route-level dependency (get_current_user).
    This middleware only verifies the token signature and attaches the payload.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/v2/auth/register",
        "/api/v2/auth/login",
        "/api/v2/auth/forgot-password",
        "/api/v2/auth/reset-password",
    ]

    # Paths that allow both authenticated and unauthenticated access
    OPTIONAL_AUTH_PATHS = [
        "/api/v2/auth/refresh",
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        auth_header = request.headers.get("Authorization", "")

        # Generate correlation ID if not present
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = secrets.token_hex(16)
        request.state.correlation_id = correlation_id

        # Skip auth for public paths
        if any(path.startswith(pp) for pp in self.PUBLIC_PATHS):
            request.state.user = None
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")

            # Basic token format validation
            if not self._is_valid_token_format(token):
                request.state.user = None
                if not any(path.startswith(pp) for pp in self.OPTIONAL_AUTH_PATHS):
                    response = await call_next(request)
                    response.headers["X-Correlation-ID"] = correlation_id
                    return response

            try:
                # Verify JWT signature and expiry
                payload = verify_token(token)

                # Check token type - only accept access tokens for API requests
                token_type = payload.get("type", "access")
                if token_type != "access":
                    # Refresh tokens should not be used for API access
                    request.state.user = None
                    response = await call_next(request)
                    response.headers["X-Correlation-ID"] = correlation_id
                    return response

                # Check if token is revoked in Redis (blacklist check)
                is_revoked = await self._is_token_revoked(token)
                if is_revoked:
                    request.state.user = None
                    response = await call_next(request)
                    response.headers["X-Correlation-ID"] = correlation_id
                    return response

                # Valid token - attach user payload to request state
                request.state.user = payload

            except Exception:
                # Token invalid or expired - let the route handler deal with it
                request.state.user = None
        else:
            request.state.user = None

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @staticmethod
    def _is_valid_token_format(token: str) -> bool:
        """Validate basic JWT token format.

        A valid JWT has 3 parts separated by dots:
        header.payload.signature

        Args:
            token: The token string to validate.

        Returns:
            True if the token has valid JWT format.
        """
        if not token or not isinstance(token, str):
            return False
        parts = token.split(".")
        return len(parts) == 3 and all(len(part) > 0 for part in parts)

    @staticmethod
    async def _is_token_revoked(token: str) -> bool:
        """Check if a token has been revoked (blacklisted).

        Queries Redis for the revoked token entry.

        Args:
            token: The JWT token string.

        Returns:
            True if the token is revoked, False otherwise.
        """
        try:
            redis = await get_redis_client()

            # Check full token revocation
            revoked = await redis.get(f"revoked:{token}")
            if revoked:
                return True

            # Check by JTI (token ID) if present in payload
            # This is more efficient for rotated tokens
            import jwt
            from app.config import settings
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                jti_revoked = await redis.get(f"revoked:jti:{jti}")
                if jti_revoked:
                    return True

            return False

        except Exception:
            # If Redis is unavailable, assume token is NOT revoked
            # (graceful degradation - route-level auth will catch issues)
            return False


# ============================================================================
# Authentication helper functions
# ============================================================================


async def revoke_token(token: str, expiry_seconds: int = 86400) -> None:
    """Revoke a token by adding it to the Redis blacklist.

    Args:
        token: The JWT token to revoke.
        expiry_seconds: How long to keep the revocation entry.
    """
    try:
        redis = await get_redis_client()

        # Revoke by full token
        await redis.setex(f"revoked:{token}", expiry_seconds, "1")

        # Also revoke by JTI for efficient lookup
        import jwt
        from app.config import settings
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                await redis.setex(f"revoked:jti:{jti}", expiry_seconds, "1")
        except Exception:
            pass  # Token might be malformed

    except Exception:
        pass  # Graceful degradation


async def revoke_all_user_tokens(user_id: int) -> None:
    """Revoke all tokens for a user (e.g., after password change or security incident).

    Sets a global revocation flag that invalidates all tokens for this user.

    Args:
        user_id: The user ID whose tokens should be revoked.
    """
    try:
        redis = await get_redis_client()
        # Set a global revocation marker for this user
        # All tokens for this user issued before this timestamp are invalid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await redis.setex(
            f"revoked:user:{user_id}",
            86400 * 7,  # 7 days
            now,
        )
    except Exception:
        pass  # Graceful degradation


async def is_user_revoked(user_id: int, token_iat: Optional[float] = None) -> bool:
    """Check if all tokens for a user have been revoked.

    Args:
        user_id: The user ID to check.
        token_iat: The 'issued at' timestamp of the token.

    Returns:
        True if the user's tokens are revoked.
    """
    try:
        redis = await get_redis_client()
        revoked_at = await redis.get(f"revoked:user:{user_id}")
        if not revoked_at:
            return False

        # If token was issued before revocation, it's invalid
        if token_iat:
            from datetime import datetime, timezone
            revoked_dt = datetime.fromisoformat(revoked_at.decode())
            token_dt = datetime.fromtimestamp(token_iat, tz=timezone.utc)
            return token_dt < revoked_dt

        return True

    except Exception:
        return False
