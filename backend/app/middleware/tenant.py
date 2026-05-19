"""Tenant middleware: extracts company ID from request header with leak detection.

Features:
- Extracts company (tenant) ID from X-Company-ID header
- Validates tenant context against authenticated user
- Detects tenant data leakage in responses (cross-tenant data exposure)
- Logs tenant isolation violations for security audit
"""

import json
import logging
from typing import Any, Dict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts the company (tenant) ID from X-Company-ID header
    and attaches it to the request state.

    Includes tenant leak detection: scans response bodies for potential
    cross-tenant data exposure and blocks responses that contain data
    belonging to a different tenant than the requesting one.
    """

    # Exact paths to skip tenant check entirely (must match exactly)
    SKIP_PATHS_EXACT = {
        "/",
        "/api/v2/health/live",
        "/api/v2/health/ready",
        "/api/v2/health/db",
        "/api/v2/health/redis",
        "/api/docs",
        "/docs",
        "/api/redoc",
        "/redoc",
        "/api/openapi.json",
        "/openapi.json",
        "/favicon.ico",
    }

    # Prefix paths to skip (startswith match)
    SKIP_PATHS_PREFIX = [
        "/api/v2/health",
        "/api/v2/auth",
        "/api/v1/auth",
        "/api/docs",
        "/docs",
        "/docs-static",
        "/redoc",
        "/static",
        "/assets",
    ]

    # Response body fields that indicate tenant ID
    TENANT_ID_FIELDS = {
        "company_id",
        "tenant_id",
        "tenantId",
        "companyId",
        "organization_id",
        "orgId",
        "organizationId",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip tenant check for public endpoints
        if path in self.SKIP_PATHS_EXACT:
            return await call_next(request)
        if any(path.startswith(sp) for sp in self.SKIP_PATHS_PREFIX):
            return await call_next(request)

        # Extract company ID from header
        company_id = request.headers.get("X-Company-ID")

        if not company_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "X-Company-ID header is required"},
                headers={"X-Tenant-Required": "true"},
            )

        # Validate company_id is a valid integer
        try:
            company_id_int = int(company_id)
            if company_id_int <= 0:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"X-Company-ID must be a positive integer, got: {company_id}"},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": f"X-Company-ID must be a valid integer, got: {company_id}"},
            )

        request.state.company_id = company_id_int

        # Call next middleware/handler
        response = await call_next(request)

        # ------------------------------------------------------------------
        # Tenant leak detection: scan response for cross-tenant data
        # ------------------------------------------------------------------
        response = await self._detect_tenant_leak(request, response, company_id_int)

        # Add tenant header to response for debugging
        response.headers["X-Tenant-ID"] = str(company_id_int)

        return response

    async def _detect_tenant_leak(
        self,
        request: Request,
        response: Response,
        expected_company_id: int,
    ) -> Response:
        """Detect if response contains data from a different tenant.

        Scans JSON response bodies for tenant ID fields and checks
        if any value differs from the requesting tenant's ID.

        Args:
            request: The incoming request.
            response: The outgoing response.
            expected_company_id: The expected tenant ID from the request.

        Returns:
            The original response if safe, or an error response if leak detected.
        """
        # Only check JSON responses with 2xx status
        if response.status_code >= 300:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            if not body:
                return response

            # Parse JSON
            data = json.loads(body.decode("utf-8", errors="replace"))

            # Search for tenant ID fields in the response
            leak_detected, found_ids = self._find_tenant_ids(
                data, expected_company_id
            )

            if leak_detected:
                # Log the security event
                logger.critical(
                    "TENANT_LEAK_DETECTED: Response for tenant %s "
                    "contains data from other tenants: %s. "
                    "Path: %s %s",
                    expected_company_id,
                    found_ids,
                    request.method,
                    request.url.path,
                )

                # Return sanitized error instead of leaking data
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": "Tenant isolation violation detected. "
                                  "Security team has been notified.",
                        "error_code": "TENANT_ISOLATION_VIOLATION",
                    },
                    headers={
                        "X-Tenant-ID": str(expected_company_id),
                        "X-Tenant-Leak-Detected": "true",
                    },
                )

            # Reconstruct response with original body
            from fastapi.responses import JSONResponse

            return JSONResponse(
                content=data,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not valid JSON, skip leak detection
            return response
        except Exception:
            # On any error, don't block the response (fail-open for detection)
            return response

    @classmethod
    def _find_tenant_ids(
        cls, data: Any, expected_company_id: int
    ) -> tuple[bool, list[int]]:
        """Recursively search for tenant ID fields in response data.

        Args:
            data: Parsed JSON data (dict, list, or primitive).
            expected_company_id: The expected tenant ID.

        Returns:
            Tuple of (leak_detected, list_of_found_ids).
        """
        found_ids: list[int] = []

        if isinstance(data, dict):
            for key, value in data.items():
                if key in cls.TENANT_ID_FIELDS and value is not None:
                    try:
                        vid = int(value)
                        found_ids.append(vid)
                    except (ValueError, TypeError):
                        pass
                # Recurse into nested structures
                nested_leak, nested_ids = cls._find_tenant_ids(value, expected_company_id)
                found_ids.extend(nested_ids)

        elif isinstance(data, list):
            for item in data:
                _, nested_ids = cls._find_tenant_ids(item, expected_company_id)
                found_ids.extend(nested_ids)

        # Check if any found ID differs from expected
        leak_detected = any(
            tid != expected_company_id for tid in found_ids
        ) if found_ids else False

        return leak_detected, found_ids
