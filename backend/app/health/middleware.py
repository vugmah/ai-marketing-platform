"""Monitoring middleware for the AI Marketing Platform.

Provides ``MetricsMiddleware`` for collecting Prometheus metrics and
``LoggingMiddleware`` for structured JSON request logging.

Usage in main.py:
    from app.health.middleware import MetricsMiddleware, LoggingMiddleware

    app.add_middleware(MetricsMiddleware)
    app.add_middleware(LoggingMiddleware)

Both middlewares are async and compatible with FastAPI's middleware stack.
"""

import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.health.logging_config import get_logger
from app.health.metrics import record_error, record_request

logger = get_logger("aimp.http")

# ---------------------------------------------------------------------------
# Metrics Middleware
# ---------------------------------------------------------------------------


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics for every HTTP request.

    Records:
    - ``aimp_http_requests_total`` -- counter with method, endpoint, status labels
    - ``aimp_http_request_duration_seconds`` -- histogram with method, endpoint labels
    - ``aimp_http_active_connections`` -- gauge of concurrent connections

    Place this middleware early in the stack to capture all requests.
    """

    # Paths to skip for metrics (static assets, health probes, metrics itself)
    SKIP_PATHS = {
        "/api/health",
        "/api/health/db",
        "/api/health/redis",
        "/api/v2/health",
        "/api/v2/health/live",
        "/api/v2/health/ready",
        "/api/v2/health/metrics",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/favicon.ico",
    }

    # Skip path prefixes
    SKIP_PREFIXES = (
        "/static/",
        "/docs/",
        "/_next/",
    )

    @staticmethod
    def _should_skip(path: str) -> bool:
        """Determine if a request path should not be recorded.

        Args:
            path: Request URL path.

        Returns:
            True if the path should be skipped.
        """
        if path in MetricsMiddleware.SKIP_PATHS:
            return True
        if path.startswith(MetricsMiddleware.SKIP_PREFIXES):
            return True
        return False

    @staticmethod
    def _normalize_endpoint(path: str) -> str:
        """Normalize a path by replacing path parameters with placeholders.

        Replaces UUIDs and numeric segments with ``{id}`` placeholders
        to keep cardinality bounded.

        Args:
            path: Raw request URL path.

        Returns:
            Normalized path suitable for use as a Prometheus label.
        """
        import re

        parts = path.split("/")
        normalized: list[str] = []

        for part in parts:
            if not part:
                normalized.append(part)
            elif re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", part, re.I):
                normalized.append("{uuid}")
            elif part.isdigit():
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process a request through the middleware.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in the chain.

        Returns:
            HTTP response from downstream handlers.
        """
        from app.health.metrics import active_connections

        path = request.url.path
        method = request.method

        # Skip metrics for excluded paths
        if self._should_skip(path):
            return await call_next(request)

        endpoint = self._normalize_endpoint(path)
        start = time.perf_counter()
        active_connections.inc()

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 500:
                record_error(error_type="http_5xx")
            return response
        except Exception:
            status_code = 500
            record_error(error_type="http_exception")
            raise
        finally:
            duration = time.perf_counter() - start
            active_connections.dec()
            record_request(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration,
            )


# ---------------------------------------------------------------------------
# Logging Middleware
# ---------------------------------------------------------------------------


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured JSON logging for every HTTP request.

    Logs each request with correlation ID, user info, timing, and
    response status.  Redacts sensitive fields (passwords, tokens).

    Place this middleware after auth middleware so request.state.user
    is available.
    """

    # Headers to redact (values replaced with "***")
    SENSITIVE_HEADERS = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "proxy-authorization",
    }

    # Query parameters to redact
    SENSITIVE_PARAMS = {
        "password",
        "token",
        "api_key",
        "apikey",
        "secret",
        "access_token",
        "refresh_token",
        "jwt",
    }

    # Paths to skip for logging (reduce noise)
    SKIP_LOG_PATHS = {
        "/api/health",
        "/api/v2/health/live",
        "/api/v2/health/metrics",
        "/favicon.ico",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    }

    def _redact_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Return headers with sensitive values redacted.

        Args:
            headers: Original request headers.

        Returns:
            Headers dictionary with sensitive values replaced.
        """
        result: Dict[str, str] = {}
        for key, value in headers.items():
            if key.lower() in self.SENSITIVE_HEADERS:
                result[key] = "***"
            else:
                result[key] = value
        return result

    def _redact_query_params(self, query_string: str) -> str:
        """Redact sensitive values from query string.

        Args:
            query_string: Raw query string.

        Returns:
            Query string with sensitive values replaced.
        """
        if not query_string:
            return query_string

        parts = query_string.split("&")
        redacted: list[str] = []
        for part in parts:
            if "=" in part:
                key, _, value = part.partition("=")
                if key.lower() in self.SENSITIVE_PARAMS:
                    redacted.append(f"{key}=***")
                else:
                    redacted.append(part)
            else:
                redacted.append(part)
        return "&".join(redacted)

    def _extract_user_info(self, request: Request) -> Dict[str, Any]:
        """Extract user information from request state if available.

        Args:
            request: FastAPI request object.

        Returns:
            Dictionary with user_id and company_id, or None values.
        """
        user_id: Optional[str] = None
        company_id: Optional[str] = None

        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            if isinstance(user, dict):
                user_id = user.get("id") or user.get("sub")
                company_id = user.get("company_id")
            else:
                user_id = getattr(user, "id", None)
                company_id = getattr(user, "company_id", None)

        return {
            "user_id": str(user_id) if user_id else None,
            "company_id": str(company_id) if company_id else None,
        }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process a request through the logging middleware.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in the chain.

        Returns:
            HTTP response from downstream handlers.
        """
        # Generate or propagate correlation ID
        correlation_id = request.headers.get("x-correlation-id", "")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        path = request.url.path
        should_log = path not in self.SKIP_LOG_PATHS

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Inject correlation ID into response headers
            response.headers["x-correlation-id"] = correlation_id

            if should_log:
                duration = time.perf_counter() - start
                user_info = self._extract_user_info(request)

                log_data: Dict[str, Any] = {
                    "event": "http_request",
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": path,
                    "query": self._redact_query_params(str(request.url.query)),
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 3),
                    "user_id": user_info["user_id"],
                    "company_id": user_info["company_id"],
                    "client_ip": self._get_client_ip(request),
                    "user_agent": request.headers.get("user-agent", ""),
                    "content_length": response.headers.get("content-length", 0),
                }

                if status_code >= 500:
                    logger.error(log_data)
                elif status_code >= 400:
                    logger.warning(log_data)
                else:
                    logger.info(log_data)

            return response

        except Exception as exc:
            logger.exception("[HEALTH_MW] Inner exception for %s %s", request.method, path)
            if should_log:
                duration = time.perf_counter() - start
                user_info = self._extract_user_info(request)

                log_data = {
                    "event": "http_request_error",
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": path,
                    "query": self._redact_query_params(str(request.url.query)),
                    "error": f"{type(exc).__name__}: {str(exc)}",
                    "duration_ms": round(duration * 1000, 3),
                    "user_id": user_info["user_id"],
                    "company_id": user_info["company_id"],
                    "client_ip": self._get_client_ip(request),
                }
                logger.error(log_data)
            raise

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the real client IP from request headers.

        Checks X-Forwarded-For and X-Real-IP headers first for proxied
        requests, falls back to the direct client IP.

        Args:
            request: FastAPI request object.

        Returns:
            Client IP address string.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # X-Forwarded-For can contain multiple IPs; use the first one
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Error tracking context manager
# ---------------------------------------------------------------------------


class ErrorTracker:
    """Context manager for tracking errors in background tasks.

    Usage:
        async with ErrorTracker("db_migration"):
            await run_migration()
    """

    def __init__(self, error_type: str, context: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.context = context or {}
        self.logger = get_logger("aimp.errors")

    async def __aenter__(self) -> "ErrorTracker":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None:
            record_error(error_type=self.error_type)
            self.logger.error({
                "event": "background_error",
                "error_type": self.error_type,
                "error": f"{exc_type.__name__}: {str(exc_val)}",
                **self.context,
            })
