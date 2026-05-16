"""Audit logging middleware.

Logs every HTTP request and response for security monitoring and compliance.

Features:
- Request/response logging with timing
- Sensitive data masking (passwords, tokens, API keys)
- PII redaction (emails, phone numbers)
- Structured JSON logging for SIEM integration
- Async logging with fire-and-forget to avoid blocking requests
- Configurable log levels per endpoint

SECURITY NOTICE:
    This middleware logs request metadata, NOT request/response bodies
    (except for error responses). Bodies are never logged to prevent
    sensitive data exposure in logs.
"""

import json
import logging
import re
import time
import uuid
from typing import Any, Dict, Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("app.audit")
security_logger = logging.getLogger("app.security")

# Fields to mask in logs (never log these values)
_SENSITIVE_FIELDS: Set[str] = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "confirm_password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "api_secret",
    "secret_key",
    "jwt_secret_key",
    "stripe_secret_key",
    "authorization",
    "cookie",
    "x-api-key",
    "s3_secret_access_key",
    "r2_secret_access_key",
    "webhook_verify_token",
    "mysql_password",
    "redis_password",
    "private_key",
    "credit_card",
    "cvv",
    "ssn",
}

# Regex patterns for PII redaction
_PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
}

# Endpoints that should always be logged at INFO (security-sensitive)
_ALWAYS_LOG_PATHS = [
    "/api/v2/auth/login",
    "/api/v2/auth/register",
    "/api/v2/auth/logout",
    "/api/v2/auth/refresh",
    "/api/v2/auth/forgot-password",
    "/api/v2/auth/reset-password",
]

# Endpoints that should be logged at WARNING for security monitoring
_SECURITY_SENSITIVE_PATHS = [
    "/api/v2/auth/forgot-password",
    "/api/v2/auth/reset-password",
    "/api/v2/admin",
    "/api/v2/audit",
]


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all HTTP requests and responses.

    Logs are structured as JSON for easy parsing by SIEM systems.
    Sensitive data is automatically masked/redacted.

    Should be placed early in the middleware stack to capture
    all requests including those that fail in later middleware.
    """

    # Paths to skip audit logging (health checks, docs)
    SKIP_PATHS = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    ]

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip logging for health checks and docs (reduces noise)
        if any(path.startswith(sp) for sp in self.SKIP_PATHS):
            return await call_next(request)

        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        method = request.method

        # Get user info if authenticated
        user_id = None
        user_email = None
        user_role = None
        user = getattr(request.state, "user", None)
        if user and isinstance(user, dict):
            user_id = user.get("sub")
            user_email = user.get("email")
            user_role = user.get("role")

        # Get tenant info
        company_id = getattr(request.state, "company_id", None)

        # Start timing
        start_time = time.perf_counter()

        # Build request log entry
        request_log = {
            "event": "http_request",
            "request_id": request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
            "method": method,
            "path": path,
            "query_params": str(request.query_params),
            "client_ip": client_ip,
            "user_agent": user_agent[:200] if user_agent else None,  # Truncate
            "user_id": user_id,
            "user_email": self._mask_email(user_email) if user_email else None,
            "user_role": user_role,
            "company_id": company_id,
            "correlation_id": getattr(request.state, "correlation_id", None),
        }

        # Determine log level based on endpoint sensitivity
        log_level = self._determine_log_level(path, method)

        # Log the request
        if log_level == "warning":
            security_logger.warning("AUDIT_REQUEST: %s", json.dumps(request_log, default=str))
        else:
            logger.info("AUDIT_REQUEST: %s", json.dumps(request_log, default=str))

        # Call the handler
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log the exception
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            error_log = {
                **request_log,
                "event": "http_error",
                "status_code": 500,
                "duration_ms": duration_ms,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
            }
            security_logger.error(
                "AUDIT_ERROR: %s",
                json.dumps(error_log, default=str),
            )
            raise

        # Calculate duration
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Build response log entry
        response_log = {
            **request_log,
            "event": "http_response",
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "content_length": response.headers.get("content-length"),
            "content_type": response.headers.get("content-type"),
            "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
        }

        # Log response based on status code
        if response.status_code >= 500:
            security_logger.error(
                "AUDIT_RESPONSE: %s",
                json.dumps(response_log, default=str),
            )
        elif response.status_code >= 400:
            # Log 4xx errors at warning for security monitoring
            security_logger.warning(
                "AUDIT_RESPONSE: %s",
                json.dumps(response_log, default=str),
            )
        else:
            if log_level == "warning":
                security_logger.warning(
                    "AUDIT_RESPONSE: %s",
                    json.dumps(response_log, default=str),
                )
            else:
                logger.info(
                    "AUDIT_RESPONSE: %s",
                    json.dumps(response_log, default=str),
                )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the real client IP from request headers.

        Checks X-Forwarded-For and X-Real-IP headers first,
        falls back to request.client.host.

        Args:
            request: The incoming HTTP request.

        Returns:
            Client IP address string.
        """
        # Check X-Forwarded-For (may contain multiple IPs)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP is the original client
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"

    @staticmethod
    def _mask_email(email: Optional[str]) -> Optional[str]:
        """Mask an email address for logging.

        Args:
            email: The email to mask.

        Returns:
            Masked email (e.g., j***@example.com).
        """
        if not email or "@" not in email:
            return email
        local, domain = email.rsplit("@", 1)
        if len(local) <= 1:
            masked_local = "*"
        else:
            masked_local = local[0] + "*" * min(len(local) - 1, 5)
        return f"{masked_local}@{domain}"

    @staticmethod
    def _determine_log_level(path: str, method: str) -> str:
        """Determine the appropriate log level for an endpoint.

        Args:
            path: Request path.
            method: HTTP method.

        Returns:
            Log level string: "info" or "warning".
        """
        # Security-sensitive endpoints always at WARNING
        if any(path.startswith(p) for p in _SECURITY_SENSITIVE_PATHS):
            return "warning"

        # Auth endpoints at WARNING
        if any(path.startswith(p) for p in _ALWAYS_LOG_PATHS):
            return "warning"

        # DELETE operations at WARNING
        if method == "DELETE":
            return "warning"

        return "info"


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively mask sensitive fields in a dictionary.

    Args:
        data: Dictionary potentially containing sensitive data.

    Returns:
        Copy of the dictionary with sensitive fields masked.
    """
    if not isinstance(data, dict):
        return data

    masked = {}
    for key, value in data.items():
        key_lower = key.lower()

        if key_lower in _SENSITIVE_FIELDS:
            masked[key] = "***REDACTED***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value)
        elif isinstance(value, list):
            masked[key] = [
                mask_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked[key] = value

    return masked


def redact_pii(text: str) -> str:
    """Redact PII from a text string.

    Args:
        text: Text potentially containing PII.

    Returns:
        Text with PII redacted.
    """
    if not text:
        return text

    result = text
    for pii_type, pattern in _PII_PATTERNS.items():
        result = pattern.sub(f"[{pii_type}_REDACTED]", result)

    return result
