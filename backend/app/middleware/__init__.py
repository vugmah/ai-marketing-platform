"""Application middleware package.

Middleware stack order (outermost first):
    1. AuditMiddleware         - Log all requests/responses
    2. SecurityHeadersMiddleware - Add security headers
    3. CacheControlMiddleware  - Prevent caching of sensitive data
    4. RateLimitMiddleware     - Enforce rate limits
    5. AuthMiddleware          - Validate JWT tokens
    6. TenantMiddleware        - Extract and validate tenant
    7. RBACMiddleware          - Enforce role-based access

This ordering ensures:
- All requests are logged (even those that fail rate limiting)
- Security headers are present on all responses
- Rate limits apply before auth (prevents auth endpoint abuse)
- Auth runs before tenant/rbac (need to know who you are before what you can do)
"""

from app.middleware.audit import AuditMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.cors import setup_cors
from app.middleware.rbac import RBACMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import CacheControlMiddleware, SecurityHeadersMiddleware
from app.middleware.tenant import TenantMiddleware

__all__ = [
    "AuditMiddleware",
    "AuthMiddleware",
    "CacheControlMiddleware",
    "RateLimitMiddleware",
    "RBACMiddleware",
    "SecurityHeadersMiddleware",
    "setup_cors",
    "TenantMiddleware",
]


def setup_middleware(app) -> None:
    """Register all middleware with the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    # CORS is added via setup_cors() in app creation

    # Security headers (first - applies to all responses)
    app.add_middleware(SecurityHeadersMiddleware)

    # Cache control
    app.add_middleware(CacheControlMiddleware)

    # Audit logging (captures all requests)
    app.add_middleware(AuditMiddleware)

    # Rate limiting (before auth to protect auth endpoints)
    app.add_middleware(RateLimitMiddleware)

    # Authentication
    app.add_middleware(AuthMiddleware)

    # Tenant isolation
    app.add_middleware(TenantMiddleware)

    # RBAC (after auth - needs user info)
    app.add_middleware(RBACMiddleware)
