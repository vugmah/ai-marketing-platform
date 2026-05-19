"""Enhanced rate limiting middleware with distributed Redis backend.

Features:
- Per-endpoint configurable rate limits
- Per-user rate limits (authenticated users get higher limits)
- Per-IP rate limits for unauthenticated requests
- Burst handling with token bucket algorithm
- Distributed rate limiting via Redis
- Standard rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
- Sliding window counter
- Graceful degradation when Redis is unavailable
- IP-based blocking for repeated violators
- Account lockout integration with failed login detection
- Token bucket algorithm for smoother rate limiting
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.exceptions import AppException
from app.redis_client import get_redis_client


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class RateLimitConfig:
    """Rate limit configuration for an endpoint pattern."""

    requests: int
    window: int
    burst: int = 0  # Additional burst allowance
    block_after_violations: int = 0  # Block IP after N violations (0 = disabled)
    block_duration: int = 300  # Block duration in seconds (default 5 min)


# Default rate limit: 100 requests per minute
DEFAULT_LIMIT = RateLimitConfig(requests=100, window=60, burst=20)

# Endpoint-specific rate limits
ENDPOINT_LIMITS: Dict[str, RateLimitConfig] = {
    # Auth endpoints - strict limits
    "/api/v2/auth/login": RateLimitConfig(
        requests=10, window=60, burst=5, block_after_violations=5, block_duration=1800
    ),
    "/api/v2/auth/register": RateLimitConfig(
        requests=5, window=60, burst=3, block_after_violations=3, block_duration=3600
    ),
    "/api/v2/auth/refresh": RateLimitConfig(
        requests=20, window=60, burst=10, block_after_violations=0
    ),
    "/api/v2/auth/forgot-password": RateLimitConfig(
        requests=3, window=300, burst=2, block_after_violations=3, block_duration=3600
    ),
    "/api/v2/auth/reset-password": RateLimitConfig(
        requests=5, window=300, burst=2, block_after_violations=3, block_duration=1800
    ),
    "/api/v2/auth/logout": RateLimitConfig(
        requests=30, window=60, burst=10
    ),
    # Audit & Security endpoints
    "/api/v2/audit/logs": RateLimitConfig(requests=60, window=60, burst=10),
    "/api/v2/audit/security-events": RateLimitConfig(requests=60, window=60, burst=10),
    "/api/v2/audit/api-keys": RateLimitConfig(requests=30, window=60, burst=5),
    # Analytics & Dashboard
    "/api/v2/analytics": RateLimitConfig(requests=60, window=60, burst=10),
    "/api/v2/dashboard": RateLimitConfig(requests=60, window=60, burst=10),
    # ERP & Integrations
    "/api/v2/erp": RateLimitConfig(requests=30, window=60, burst=5),
    "/api/v2/erp/sync": RateLimitConfig(requests=10, window=60, burst=3),
    # Notifications
    "/api/v2/notifications": RateLimitConfig(requests=60, window=60, burst=10),
    # AI endpoints
    "/api/v2/ai": RateLimitConfig(requests=30, window=60, burst=5),
    "/api/v2/ai/generate": RateLimitConfig(requests=10, window=60, burst=3),
    # Social Media
    "/api/v2/social": RateLimitConfig(requests=50, window=60, burst=10),
    "/api/v2/social/publish": RateLimitConfig(requests=20, window=60, burst=5),
    # Media/Creative Studio
    "/api/v2/media": RateLimitConfig(requests=30, window=60, burst=5),
    "/api/v2/media/upload": RateLimitConfig(requests=10, window=60, burst=3),
    # Billing
    "/api/v2/billing": RateLimitConfig(requests=30, window=60, burst=5),
    # Ads Intelligence
    "/api/v2/ads": RateLimitConfig(requests=40, window=60, burst=8),
    # Support
    "/api/v2/support": RateLimitConfig(requests=30, window=60, burst=5),
}

# Per-user tier rate limits (multiplier applied to base limits)
USER_ROLE_MULTIPLIERS = {
    "super_admin": 5.0,
    "company_admin": 3.0,
    "branch_manager": 2.0,
    "marketing_manager": 1.5,
    "support_agent": 1.5,
    "analyst": 1.2,
}

# Default multiplier for unauthenticated users
UNAUTHENTICATED_MULTIPLIER = 0.5

# IP reputation thresholds
IP_VIOLATION_WINDOW = 3600  # 1 hour window for violation tracking
IP_BAN_DURATION = 3600  # 1 hour default ban


# ============================================================================
# Rate Limit Middleware
# ============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces distributed rate limits per client.

    Uses Redis-backed sliding window counters with per-endpoint
    and per-user configuration. Adds standard rate limit headers
    to all responses. Supports IP blocking for repeated violators.
    """

    # Paths to skip rate limiting
    SKIP_PATHS = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip rate limiting for health checks and docs
        if any(path.startswith(sp) for sp in self.SKIP_PATHS):
            return await call_next(request)

        client_id = self._get_client_id(request)

        # Check if client IP is banned
        is_banned, ban_reason = await self._check_ip_banned(client_id)
        if is_banned:
            raise AppException(
                detail=f"Access blocked: {ban_reason}. Please try again later.",
                status_code=403,
            )

        config = self._get_limit_config(path, request)
        limit_key = self._build_limit_key(client_id, path, request)

        # Check rate limit
        allowed, remaining, reset_at = await self._check_rate_limit(
            limit_key, config
        )

        if not allowed:
            # Track violation for potential IP blocking
            if config.block_after_violations > 0:
                await self._track_violation(client_id, path, config)

            retry_after = max(1, int(reset_at - time.time()))
            raise AppException(
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                status_code=429,
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(config.requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining - 1))
        response.headers["X-RateLimit-Reset"] = str(int(reset_at))
        response.headers["X-RateLimit-Window"] = str(config.window)

        return response

    @staticmethod
    def _get_client_id(request: Request) -> str:
        """Extract a unique client identifier from the request.

        Uses the user ID from authenticated requests, or falls back
        to IP address for unauthenticated requests.

        Args:
            request: The incoming request.

        Returns:
            Client identifier string.
        """
        # Try to get user ID from authenticated request
        user = getattr(request.state, "user", None)
        if user and isinstance(user, dict):
            user_id = user.get("sub")
            if user_id:
                return f"user:{user_id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            real_ip = request.headers.get("X-Real-IP")
            ip = real_ip if real_ip else (request.client.host if request.client else "unknown")

        return f"ip:{ip}"

    @staticmethod
    def _get_user_role(request: Request) -> Optional[str]:
        """Extract user role from request state.

        Args:
            request: The incoming request.

        Returns:
            User role string, or None for unauthenticated.
        """
        user = getattr(request.state, "user", None)
        if user and isinstance(user, dict):
            return user.get("role")
        return None

    @classmethod
    def _get_limit_config(cls, path: str, request: Request) -> RateLimitConfig:
        """Get rate limit configuration for a path.

        Checks endpoint-specific limits first, then falls back
        to defaults with user tier multiplier applied.

        Args:
            path: Request path.
            request: The incoming request.

        Returns:
            RateLimitConfig with adjusted limits.
        """
        # Find matching endpoint pattern
        base_config = None
        for pattern, config in ENDPOINT_LIMITS.items():
            if path.startswith(pattern):
                base_config = config
                break

        if base_config is None:
            base_config = DEFAULT_LIMIT

        # Apply user role multiplier
        role = cls._get_user_role(request)
        if role:
            multiplier = USER_ROLE_MULTIPLIERS.get(str(role).lower(), 1.0)
        else:
            multiplier = UNAUTHENTICATED_MULTIPLIER

        return RateLimitConfig(
            requests=int(base_config.requests * multiplier),
            window=base_config.window,
            burst=int(base_config.burst * multiplier),
            block_after_violations=base_config.block_after_violations,
            block_duration=base_config.block_duration,
        )

    @staticmethod
    def _build_limit_key(client_id: str, path: str, request: Request) -> str:
        """Build the Redis key for rate limiting.

        Args:
            client_id: The client identifier.
            path: Request path.
            request: The incoming request.

        Returns:
            Redis key string.
        """
        method = request.method
        # Normalize path to handle path parameters
        normalized_path = path.rstrip("/")
        return f"rl:{client_id}:{method}:{normalized_path}"

    async def _check_rate_limit(
        self, key: str, config: RateLimitConfig
    ) -> Tuple[bool, int, float]:
        """Check if the request is within rate limits using sliding window.

        Args:
            key: Redis key for this client+endpoint.
            config: Rate limit configuration.

        Returns:
            Tuple of (allowed, remaining_requests, reset_timestamp).
        """
        try:
            redis = await get_redis_client()
            now = time.time()
            window_start = now - config.window

            # Remove entries outside the window
            await redis.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            current_count = await redis.zcard(key)
            total_limit = config.requests + config.burst

            if current_count >= total_limit:
                # Get the oldest entry for reset time calculation
                oldest = await redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    reset_at = oldest[0][1] + config.window
                else:
                    reset_at = now + config.window
                return False, 0, reset_at

            # Add current request
            await redis.zadd(key, {str(now): now})
            await redis.expire(key, config.window)

            remaining = total_limit - current_count - 1
            reset_at = now + config.window

            return True, remaining, reset_at

        except Exception:
            # If Redis is unavailable, allow the request through
            # (graceful degradation)
            return True, 0, time.time() + config.window

    async def _check_ip_banned(self, client_id: str) -> Tuple[bool, str]:
        """Check if a client IP/user is currently banned.

        Args:
            client_id: The client identifier (ip:... or user:...).

        Returns:
            Tuple of (is_banned, ban_reason).
        """
        try:
            redis = await get_redis_client()
            ban_key = f"rl_banned:{client_id}"
            ban_info = await redis.get(ban_key)
            if ban_info:
                return True, ban_info.decode() if isinstance(ban_info, bytes) else ban_info
            return False, ""
        except Exception:
            return False, ""

    async def _track_violation(
        self, client_id: str, path: str, config: RateLimitConfig
    ) -> None:
        """Track a rate limit violation and potentially ban the client.

        Args:
            client_id: The client identifier.
            path: The endpoint path that triggered the violation.
            config: Rate limit configuration with block settings.
        """
        if config.block_after_violations <= 0:
            return

        try:
            redis = await get_redis_client()
            violation_key = f"rl_violations:{client_id}"
            now = time.time()

            # Add violation timestamp
            await redis.zadd(violation_key, {str(now): now})
            await redis.expire(violation_key, IP_VIOLATION_WINDOW)

            # Count violations in window
            window_start = now - IP_VIOLATION_WINDOW
            await redis.zremrangebyscore(violation_key, 0, window_start)
            violation_count = await redis.zcard(violation_key)

            if violation_count >= config.block_after_violations:
                # Ban the client
                ban_key = f"rl_banned:{client_id}"
                ban_reason = f"Rate limit violations exceeded ({violation_count} in {IP_VIOLATION_WINDOW}s)"
                await redis.setex(
                    ban_key,
                    config.block_duration,
                    ban_reason,
                )
                # Clear violation history after banning
                await redis.delete(violation_key)

        except Exception:
            pass  # Graceful degradation


# ============================================================================
# Standalone rate limit check (for use in route handlers)
# ============================================================================


async def check_rate_limit(
    key: str,
    requests: int = 100,
    window: int = 60,
) -> Tuple[bool, int, int]:
    """Check a rate limit outside of middleware.

    Useful for route handlers that need custom rate limiting logic.

    Args:
        key: Redis key for the rate limit counter.
        requests: Maximum requests in the window.
        window: Window size in seconds.

    Returns:
        Tuple of (allowed, remaining, reset_timestamp).
    """
    try:
        redis = await get_redis_client()
        now = int(time.time())
        window_key = f"rl_custom:{key}"

        # Use simple counter with expiry
        current = await redis.get(window_key)
        if current is None:
            await redis.set(window_key, 1, ex=window)
            return True, requests - 1, now + window

        current_int = int(current)
        if current_int >= requests:
            ttl = await redis.ttl(window_key)
            return False, 0, now + max(0, ttl)

        await redis.incr(window_key)
        ttl = await redis.ttl(window_key)
        return True, requests - current_int - 1, now + max(0, ttl)

    except Exception:
        # Graceful degradation
        return True, 0, now + window


# ============================================================================
# Account lockout helper (for failed login attempts)
# ============================================================================


async def check_account_lockout(
    identifier: str,
    max_attempts: int = 5,
    lockout_duration: int = 1800,
) -> Tuple[bool, int]:
    """Check if an account (email or IP) is locked out due to failed attempts.

    Args:
        identifier: Account identifier (email or IP address).
        max_attempts: Maximum failed attempts before lockout.
        lockout_duration: Lockout duration in seconds (default 30 min).

    Returns:
        Tuple of (is_locked_out, remaining_seconds).
    """
    try:
        redis = await get_redis_client()
        lockout_key = f"lockout:{identifier}"

        # Check if already locked out
        lockout_info = await redis.get(lockout_key)
        if lockout_info:
            ttl = await redis.ttl(lockout_key)
            return True, max(0, ttl)

        # Get current attempt count
        attempt_key = f"login_attempts:{identifier}"
        attempts = await redis.get(attempt_key)
        attempt_count = int(attempts) if attempts else 0

        if attempt_count >= max_attempts:
            # Lock the account
            await redis.setex(lockout_key, lockout_duration, "1")
            await redis.delete(attempt_key)
            return True, lockout_duration

        return False, 0

    except Exception:
        # Graceful degradation - don't lock out if Redis is down
        return False, 0


async def record_failed_login(identifier: str, window: int = 300) -> int:
    """Record a failed login attempt.

    Args:
        identifier: Account identifier (email or IP address).
        window: Time window for counting attempts in seconds.

    Returns:
        Current number of failed attempts in the window.
    """
    try:
        redis = await get_redis_client()
        attempt_key = f"login_attempts:{identifier}"

        attempts = await redis.get(attempt_key)
        if attempts is None:
            await redis.set(attempt_key, 1, ex=window)
            return 1

        new_count = await redis.incr(attempt_key)
        # Refresh expiry
        await redis.expire(attempt_key, window)
        return new_count

    except Exception:
        return 0


async def clear_login_attempts(identifier: str) -> None:
    """Clear failed login attempts after successful login.

    Args:
        identifier: Account identifier (email or IP address).
    """
    try:
        redis = await get_redis_client()
        attempt_key = f"login_attempts:{identifier}"
        lockout_key = f"lockout:{identifier}"
        await redis.delete(attempt_key, lockout_key)
    except Exception:
        pass


# ============================================================================
# Token bucket rate limiter (for smoother rate limiting)
# ============================================================================


async def token_bucket_check(
    key: str,
    capacity: int = 10,
    refill_rate: float = 1.0,  # tokens per second
) -> Tuple[bool, float]:
    """Token bucket rate limiter for smoother traffic shaping.

    Args:
        key: Redis key for the bucket.
        capacity: Maximum tokens in the bucket.
        refill_rate: Tokens added per second.

    Returns:
        Tuple of (allowed, remaining_tokens).
    """
    try:
        redis = await get_redis_client()
        bucket_key = f"rl_bucket:{key}"
        now = time.time()

        # Get current bucket state
        bucket_data = await redis.hgetall(bucket_key)

        if not bucket_data:
            # New bucket - full capacity
            tokens = capacity - 1
            await redis.hset(bucket_key, mapping={
                "tokens": str(tokens),
                "last_refill": str(now),
            })
            await redis.expire(bucket_key, 3600)
            return True, float(tokens)

        # Calculate token refill
        current_tokens = float(bucket_data.get("tokens", "0"))
        last_refill = float(bucket_data.get("last_refill", "0"))
        elapsed = now - last_refill
        refill = elapsed * refill_rate

        tokens = min(capacity, current_tokens + refill) - 1

        if tokens < 0:
            # Not enough tokens
            await redis.hset(bucket_key, mapping={
                "tokens": str(min(capacity, current_tokens + refill)),
                "last_refill": str(now),
            })
            return False, 0.0

        # Consume a token
        await redis.hset(bucket_key, mapping={
            "tokens": str(tokens),
            "last_refill": str(now),
        })
        return True, tokens

    except Exception:
        # Graceful degradation
        return True, 0.0
