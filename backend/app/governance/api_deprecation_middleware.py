"""API Deprecation middleware - adds Sunset/Deprecation headers.

Note: Full DB-backed deprecation checks deferred to Phase 1 (Observability).
Current implementation adds static version headers. Cache-based deprecation
lookup will be added when Redis integration is fully wired.
"""

import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class APIDeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware that adds API version and deprecation headers.

    Phase 1 enhancement: Add Redis-backed endpoint status lookup
    to inject Deprecation/Sunset headers for deprecated endpoints.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "[DEPRECATION_MW] Inner exception for %s %s",
                request.method, request.url.path
            )
            raise

        path = request.url.path
        method = request.method

        # Skip non-API and health paths
        if not path.startswith("/api/") or path.startswith("/api/v2/health"):
            return response

        # Add version and timing headers
        latency = (time.time() - start_time) * 1000
        response.headers["X-API-Version"] = "v2"
        response.headers["X-Response-Time-Ms"] = str(round(latency, 2))

        return response
