"""Rate limiting middleware using Redis."""

import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.exceptions import AppException
from app.redis_client import get_redis_client

# Endpoint-specific rate limits: (max_requests, window_seconds)
DEFAULT_LIMIT = (100, 60)  # 100 requests per minute
ENDPOINT_LIMITS = {
    "/api/v2/auth/login": (10, 60),       # 10 login attempts per minute
    "/api/v2/auth/register": (5, 60),     # 5 registrations per minute
    "/api/v2/auth/refresh": (20, 60),     # 20 token refreshes per minute
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits per client IP and endpoint."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for health checks and docs
        path = request.url.path
        if path.startswith("/api/health") or path in [
            "/api/docs", "/api/redoc", "/api/openapi.json"
        ]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        limit_key = f"rate_limit:{client_ip}:{path}"

        max_requests, window = self._get_limit(path)

        try:
            redis = await get_redis_client()

            current_count = await redis.get(limit_key)
            if current_count is None:
                await redis.set(limit_key, 1, ex=window)
                current_count = 1
            elif int(current_count) >= max_requests:
                retry_after = await redis.ttl(limit_key)
                raise AppException(
                    detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    status_code=429,
                )
            else:
                await redis.incr(limit_key)

        except AppException:
            raise
        except Exception:
            # If Redis is unavailable, allow the request through
            pass

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract the real client IP from request headers."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    def _get_limit(self, path: str):
        """Get the rate limit for a given path."""
        for endpoint_pattern, limit in ENDPOINT_LIMITS.items():
            if path.startswith(endpoint_pattern):
                return limit
        return DEFAULT_LIMIT
