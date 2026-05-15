"""Tenant middleware: extracts company ID from request header."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.exceptions import TenantError


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts the company (tenant) ID from the X-Company-ID header
    and attaches it to the request state.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip tenant check for health endpoints and auth endpoints
        path = request.url.path
        if path.startswith("/api/health") or path in ["/api/docs", "/api/redoc", "/api/openapi.json"]:
            return await call_next(request)

        company_id = request.headers.get("X-Company-ID")
        if not company_id:
            # Allow auth endpoints to pass without company ID
            if path.startswith("/api/v2/auth"):
                request.state.company_id = None
                return await call_next(request)
            raise TenantError(detail="X-Company-ID header is required")

        request.state.company_id = company_id
        response = await call_next(request)
        return response
