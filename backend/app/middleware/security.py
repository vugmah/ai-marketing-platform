"""Security headers middleware.

Adds comprehensive security headers to every HTTP response:
- X-Frame-Options: Clickjacking protection
- Strict-Transport-Security (HSTS): Force HTTPS
- Content-Security-Policy (CSP): XSS and data injection protection
- X-Content-Type-Options: MIME sniffing prevention
- Referrer-Policy: Control referrer information leakage
- Permissions-Policy: Restrict browser feature access
- X-Permitted-Cross-Domain-Policies: Flash/PDF policy restriction
- Cross-Origin-Opener-Policy: Cross-origin window isolation
- Cross-Origin-Resource-Policy: Resource sharing control
- Cross-Origin-Embedder-Policy: Embedding control

SECURITY NOTE:
    These headers are defense-in-depth measures. They complement but do not
    replace proper input validation, output encoding, and authentication.
"""

import logging
import os
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

logger = logging.getLogger(__name__)


# Security header values
_X_FRAME_OPTIONS = "DENY"
_X_CONTENT_TYPE_OPTIONS = "nosniff"
_REFERRER_POLICY = "strict-origin-when-cross-origin"
_X_PERMITTED_CROSS_DOMAIN_POLICIES = "none"
_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
_CROSS_ORIGIN_RESOURCE_POLICY = "same-origin"
_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"

# CSP Directives
_CSP_DIRECTIVES = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
    "img-src 'self' data: https: blob:; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self' https://api.stripe.com https://*.railway.app https://*.up.railway.app; "
    "media-src 'self' blob: https:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "upgrade-insecure-requests;"
)

# HSTS max age (1 year = 31536000 seconds)
_HSTS_MAX_AGE = 31536000
_HSTS_INCLUDE_SUBDOMAINS = True
_HSTS_PRELOAD = True

# Permissions Policy
_PERMISSIONS_POLICY = (
    "accelerometer=(), "
    "ambient-light-sensor=(), "
    "autoplay=(), "
    "battery=(), "
    "camera=(), "
    "display-capture=(), "
    "document-domain=(), "
    "encrypted-media=(), "
    "fullscreen=(), "
    "gamepad=(), "
    "geolocation=(), "
    "gyroscope=(), "
    "magnetometer=(), "
    "microphone=(), "
    "midi=(), "
    "payment=(), "
    "picture-in-picture=(), "
    "publickey-credentials-get=(), "
    "screen-wake-lock=(), "
    "serial=(), "
    "speaker-selection=(), "
    "usb=(), "
    "web-share=(), "
    "xr-spatial-tracking=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to every HTTP response.

    Implements OWASP-recommended security headers for API defense-in-depth.
    Should be placed early in the middleware stack to ensure all responses
    (including error responses) get the headers.
    """

    # Paths that skip security headers (API docs, health checks)
    SKIP_PATHS = [
        "/api/health",
    ]

    def __init__(self, app, *, report_only: bool = False):
        """Initialize the security headers middleware.

        Args:
            app: The ASGI application.
            report_only: If True, CSP is sent as Content-Security-Policy-Report-Only.
        """
        super().__init__(app)
        self.report_only = report_only
        self._is_production = os.environ.get("ENVIRONMENT", "development").lower() in (
            "production",
            "staging",
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Check if we should skip headers for this path
        skip_headers = any(path.startswith(sp) for sp in self.SKIP_PATHS)

        response = await call_next(request)

        if skip_headers:
            return response

        # Apply security headers
        self._apply_security_headers(response)

        return response

    def _apply_security_headers(self, response: Response) -> None:
        """Add all security headers to the response.

        Args:
            response: The outgoing HTTP response.
        """
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = _X_FRAME_OPTIONS

        # Force HTTPS (only in production)
        if self._is_production:
            hsts_value = f"max-age={_HSTS_MAX_AGE}"
            if _HSTS_INCLUDE_SUBDOMAINS:
                hsts_value += "; includeSubDomains"
            if _HSTS_PRELOAD:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Content Security Policy
        if self.report_only:
            response.headers["Content-Security-Policy-Report-Only"] = _CSP_DIRECTIVES
        else:
            response.headers["Content-Security-Policy"] = _CSP_DIRECTIVES

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = _X_CONTENT_TYPE_OPTIONS

        # Referrer policy
        response.headers["Referrer-Policy"] = _REFERRER_POLICY

        # Permissions policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY

        # Cross-domain policy restriction
        response.headers["X-Permitted-Cross-Domain-Policies"] = _X_PERMITTED_CROSS_DOMAIN_POLICIES

        # Cross-origin policies
        response.headers["Cross-Origin-Opener-Policy"] = _CROSS_ORIGIN_OPENER_POLICY
        response.headers["Cross-Origin-Resource-Policy"] = _CROSS_ORIGIN_RESOURCE_POLICY
        response.headers["Cross-Origin-Embedder-Policy"] = _CROSS_ORIGIN_EMBEDDER_POLICY

        # Remove potentially dangerous headers
        # These can leak server implementation details
        headers_to_remove = [
            "Server",
            "X-Powered-By",
            "X-AspNet-Version",
            "X-AspNetMvc-Version",
        ]
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Middleware that adds cache-control headers for sensitive endpoints.

    Prevents caching of authenticated responses and sensitive data.
    """

    # Paths that should never be cached (auth, user data, etc.)
    NO_CACHE_PATHS = [
        "/api/v2/auth",
        "/api/v2/users",
        "/api/v2/audit",
        "/api/v2/billing",
        "/api/v2/admin",
    ]

    # Safe-to-cache paths (public assets, health)
    CACHEABLE_PATHS = [
        "/api/health",
        "/static",
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        method = request.method

        response = await call_next(request)

        # Skip if headers already set by handler
        if "Cache-Control" in response.headers:
            return response

        # Never cache non-GET requests
        if method != "GET":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        # Check if path is in no-cache list
        if any(path.startswith(p) for p in self.NO_CACHE_PATHS):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        # Check if path is cacheable
        if any(path.startswith(p) for p in self.CACHEABLE_PATHS):
            # Allow short caching for health checks
            response.headers["Cache-Control"] = "public, max-age=60"
            return response

        # Default: no cache for authenticated API responses
        auth_header = request.headers.get("Authorization", "")
        if auth_header:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        # Default for unauthenticated GET: allow short caching
        response.headers["Cache-Control"] = "public, max-age=300"

        return response
