"""Security audit middleware.

Provides:
- AuditMiddleware: Auto-log all API requests/responses
- SecurityHeadersMiddleware: Add security headers
- SuspiciousActivityMiddleware: Detect unusual patterns
- TenantLeakMiddleware: Verify responses only contain tenant data
"""

import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.audit.constants import (
    BRUTE_FORCE_BLOCK_DURATION_SECONDS,
    BRUTE_FORCE_MAX_ATTEMPTS,
    BRUTE_FORCE_WINDOW_SECONDS,
    OFF_HOURS_END,
    OFF_HOURS_START,
    RAPID_REQUEST_THRESHOLD,
    SecurityEventType,
    SECURITY_HEADERS,
    SeverityLevel,
    TENANT_LEAK_FIELD_PATTERNS,
    TENANT_LEAK_MAX_SAMPLE_SIZE,
    TOKEN_REUSE_WINDOW_SECONDS,
)
from app.audit.models import AuditAction, ResourceType, SecurityEvent, LoginStatus
from app.audit.schemas import SecurityEventCreate
from app.audit.service import (
    AuditLogService,
    LoginAttemptService,
    SecurityMonitoringService,
)
from app.database import get_db_context
from app.redis_client import get_redis_client


# ============================================================================
# AuditMiddleware
# ============================================================================


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that automatically logs all API requests and responses.

    Creates an audit log entry for every request with timing,
    status code, user context, and correlation ID.
    """

    # Paths to skip auditing
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

        # Skip health checks and docs
        if any(path.startswith(sp) for sp in self.SKIP_PATHS):
            return await call_next(request)

        # Generate or use existing correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = secrets.token_hex(16)
        request.state.correlation_id = correlation_id

        # Record start time
        start_time = time.perf_counter()

        # Extract request info
        method = request.method
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        user_id = self._get_user_id(request)
        company_id = self._get_company_id(request)
        branch_id = self._get_branch_id(request)

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # Log the request asynchronously (fire and forget to not block)
        try:
            status_code = response.status_code
            asyncio = __import__("asyncio")
            asyncio.create_task(
                self._log_request(
                    method=method,
                    path=path,
                    status_code=status_code,
                    company_id=company_id,
                    branch_id=branch_id,
                    user_id=user_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                )
            )
        except Exception:
            pass

        return response

    async def _log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        company_id: Optional[int],
        branch_id: Optional[int],
        user_id: Optional[int],
        ip_address: str,
        user_agent: Optional[str],
        duration_ms: float,
        correlation_id: str,
    ) -> None:
        """Log a request to the audit trail."""
        try:
            async with get_db_context() as db:
                service = AuditLogService(db)
                await service.log_api_request(
                    method=method,
                    path=path,
                    status_code=status_code,
                    company_id=company_id,
                    branch_id=branch_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                )
        except Exception:
            pass

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract real client IP from request headers."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _get_user_id(request: Request) -> Optional[int]:
        """Extract user ID from request state."""
        user = getattr(request.state, "user", None)
        if user is None:
            return None
        if isinstance(user, dict):
            sub = user.get("sub")
            if sub:
                try:
                    return int(sub)
                except (ValueError, TypeError):
                    pass
        return None

    @staticmethod
    def _get_company_id(request: Request) -> Optional[int]:
        """Extract company ID from request state."""
        cid = getattr(request.state, "company_id", None)
        if cid is not None:
            try:
                return int(cid)
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _get_branch_id(request: Request) -> Optional[int]:
        """Extract branch ID from request state."""
        bid = getattr(request.state, "branch_id", None)
        if bid is not None:
            try:
                return int(bid)
            except (ValueError, TypeError):
                pass
        return None


# ============================================================================
# SecurityHeadersMiddleware
# ============================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds comprehensive security headers to all responses.

    Implements OWASP recommended security headers including:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    - Cross-Origin headers
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Add all security headers
        for header_name, header_value in SECURITY_HEADERS.items():
            if header_name not in response.headers:
                response.headers[header_name] = header_value

        # Add dynamic headers
        response.headers["X-Request-ID"] = getattr(
            request.state, "correlation_id", secrets.token_hex(8)
        )

        return response


# ============================================================================
# SuspiciousActivityMiddleware
# ============================================================================


class SuspiciousActivityMiddleware(BaseHTTPMiddleware):
    """Middleware that detects suspicious activity patterns.

    Monitors for:
    - Rapid requests (rate-based anomaly)
    - Burst requests (short-term spikes)
    - Off-hours access
    - Token reuse (same token used rapidly)
    - Unusual user agents
    """

    # Paths to skip monitoring
    SKIP_PATHS = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    ]

    # Suspicious user agent patterns
    SUSPICIOUS_UA_PATTERNS = [
        "sqlmap", "nikto", "nmap", "masscan", "zgrab",
        "gobuster", "dirbuster", "wfuzz", "burp", "metasploit",
        "nessus", "openvas", "acunetix", "netsparker",
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip monitoring for health/docs
        if any(path.startswith(sp) for sp in self.SKIP_PATHS):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)
        user_agent = request.headers.get("User-Agent", "")
        auth_header = request.headers.get("Authorization", "")

        # Run checks
        await self._check_rapid_requests(request, client_ip, user_id)
        await self._check_burst_requests(request, client_ip, user_id)
        await self._check_token_reuse(request, auth_header, user_id)
        await self._check_suspicious_user_agent(request, user_agent, client_ip, user_id)
        await self._check_off_hours_access(request, client_ip, user_id)

        response = await call_next(request)
        return response

    async def _check_rapid_requests(
        self, request: Request, ip: str, user_id: Optional[int]
    ) -> None:
        """Check for rapid requests from the same IP."""
        try:
            redis = await get_redis_client()
            window, max_requests = RAPID_REQUEST_THRESHOLD
            key = f"rapid_req:{ip}"

            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window)

            if count > max_requests:
                # Create security event
                asyncio = __import__("asyncio")
                asyncio.create_task(
                    self._log_security_event(
                        event_type=SecurityEventType.UNUSUAL_ACTIVITY,
                        severity=SeverityLevel.HIGH,
                        description=f"Rapid requests from {ip}: {count} in {window}s",
                        source_ip=ip,
                        user_id=user_id,
                        details={"request_count": count, "window": window},
                    )
                )
        except Exception:
            pass

    async def _check_burst_requests(
        self, request: Request, ip: str, user_id: Optional[int]
    ) -> None:
        """Check for burst requests (very short-term spikes)."""
        try:
            redis = await get_redis_client()
            from app.audit.constants import BURST_REQUEST_THRESHOLD
            window, max_requests = BURST_REQUEST_THRESHOLD
            key = f"burst_req:{ip}"

            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window)

            if count > max_requests:
                asyncio = __import__("asyncio")
                asyncio.create_task(
                    self._log_security_event(
                        event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                        severity=SeverityLevel.MEDIUM,
                        description=f"Burst requests from {ip}: {count} in {window}s",
                        source_ip=ip,
                        user_id=user_id,
                        details={"request_count": count, "window": window},
                    )
                )
        except Exception:
            pass

    async def _check_token_reuse(
        self, request: Request, auth_header: str, user_id: Optional[int]
    ) -> None:
        """Check if the same token is being reused rapidly (possible replay)."""
        if not auth_header or not auth_header.startswith("Bearer "):
            return

        token = auth_header.replace("Bearer ", "")
        token_prefix = token[:32]  # Use prefix for tracking

        try:
            redis = await get_redis_client()
            key = f"token_use:{token_prefix}"

            # Check if this token was used recently
            last_used = await redis.get(key)
            if last_used is not None:
                asyncio = __import__("asyncio")
                asyncio.create_task(
                    self._log_security_event(
                        event_type=SecurityEventType.TOKEN_REUSE,
                        severity=SeverityLevel.HIGH,
                        description="Potential token replay detected",
                        source_ip=self._get_client_ip(request),
                        user_id=user_id,
                        details={"token_prefix": token_prefix},
                    )
                )

            await redis.set(key, "1", ex=TOKEN_REUSE_WINDOW_SECONDS)
        except Exception:
            pass

    async def _check_suspicious_user_agent(
        self,
        request: Request,
        user_agent: str,
        ip: str,
        user_id: Optional[int],
    ) -> None:
        """Check for known malicious user agents."""
        if not user_agent:
            return

        ua_lower = user_agent.lower()
        for pattern in self.SUSPICIOUS_UA_PATTERNS:
            if pattern in ua_lower:
                asyncio = __import__("asyncio")
                asyncio.create_task(
                    self._log_security_event(
                        event_type=SecurityEventType.UNUSUAL_ACTIVITY,
                        severity=SeverityLevel.MEDIUM,
                        description=f"Suspicious user agent detected: {pattern}",
                        source_ip=ip,
                        user_id=user_id,
                        details={
                            "user_agent": user_agent,
                            "detected_pattern": pattern,
                        },
                    )
                )
                break

    async def _check_off_hours_access(
        self, request: Request, ip: str, user_id: Optional[int]
    ) -> None:
        """Check for access outside business hours."""
        try:
            now = datetime.now(timezone.utc)
            hour = now.hour

            if hour >= OFF_HOURS_START or hour < OFF_HOURS_END:
                # Only flag if user is authenticated
                if user_id is not None:
                    redis = await get_redis_client()
                    key = f"off_hours:{user_id}"

                    # Rate limit: only flag once per hour per user
                    flagged = await redis.get(key)
                    if flagged is None:
                        await redis.set(key, "1", ex=3600)

                        asyncio = __import__("asyncio")
                        asyncio.create_task(
                            self._log_security_event(
                                event_type=SecurityEventType.OFF_HOURS_ACCESS,
                                severity=SeverityLevel.LOW,
                                description=f"Off-hours access at {hour}:00 UTC",
                                source_ip=ip,
                                user_id=user_id,
                                details={"hour": hour},
                            )
                        )
        except Exception:
            pass

    async def _log_security_event(
        self,
        event_type: SecurityEventType,
        severity: SeverityLevel,
        description: str,
        source_ip: Optional[str] = None,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Fire-and-forget security event logging."""
        try:
            async with get_db_context() as db:
                service = SecurityMonitoringService(db)
                await service.create_event(
                    SecurityEventCreate(
                        event_type=event_type,
                        severity=severity,
                        description=description,
                        source_ip=source_ip,
                        user_id=user_id,
                        details=details,
                    )
                )
        except Exception:
            pass

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract real client IP from request headers."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _get_user_id(request: Request) -> Optional[int]:
        """Extract user ID from request state."""
        user = getattr(request.state, "user", None)
        if user is None:
            return None
        if isinstance(user, dict):
            sub = user.get("sub")
            if sub:
                try:
                    return int(sub)
                except (ValueError, TypeError):
                    pass
        return None


# ============================================================================
# TenantLeakMiddleware
# ============================================================================


class TenantLeakMiddleware(BaseHTTPMiddleware):
    """Middleware that verifies all response data belongs to the requesting tenant.

    Scans JSON responses for any company_id or tenant_id fields that
    contain a value different from the requesting user's company_id.
    Logs violations as critical security events.
    """

    # Paths to skip
    SKIP_PATHS = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    ]

    # Paths that don't need tenant checking
    PUBLIC_PATHS = [
        "/api/v2/auth/register",
        "/api/v2/auth/login",
        "/api/v2/auth/refresh",
    ]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip for docs, health, and public endpoints
        if any(path.startswith(sp) for sp in self.SKIP_PATHS):
            return await call_next(request)
        if any(path.startswith(pp) for pp in self.PUBLIC_PATHS):
            return await call_next(request)

        response = await call_next(request)

        # Only check JSON responses with authenticated users
        if response.headers.get("content-type", "").startswith("application/json"):
            company_id = self._get_company_id(request)
            if company_id is not None:
                try:
                    body = await self._get_response_body(response)
                    if body:
                        leaks = self._scan_for_tenant_leaks(body, company_id)
                        if leaks:
                            await self._log_tenant_leak(company_id, leaks, path)
                            # Optionally strip leaked data from response
                            # response = self._sanitize_response(response, leaks)
                except Exception:
                    pass

        return response

    async def _get_response_body(self, response: Response) -> Optional[Any]:
        """Extract JSON body from response."""
        try:
            # For starlette responses, we can read the body
            if hasattr(response, "body"):
                body_bytes = response.body
            else:
                # Try to read from response iterator
                body_chunks = []
                async for chunk in response.body_iterator:
                    body_chunks.append(chunk)
                body_bytes = b"".join(body_chunks)
                # Restore the iterator for downstream
                response.body_iterator = iter(body_chunks)

            if body_bytes:
                return json.loads(body_bytes.decode("utf-8"))
        except Exception:
            pass
        return None

    def _scan_for_tenant_leaks(
        self, body: Any, expected_company_id: int
    ) -> List[Dict[str, Any]]:
        """Scan response body for tenant data leakage.

        Args:
            body: Parsed JSON body.
            expected_company_id: Expected company_id.

        Returns:
            List of leak findings.
        """
        leaks: List[Dict[str, Any]] = []
        self._scan_value(body, "", expected_company_id, leaks)
        return leaks

    def _scan_value(
        self,
        value: Any,
        path: str,
        expected_company_id: int,
        leaks: List[Dict[str, Any]],
        depth: int = 0,
    ) -> None:
        """Recursively scan a value for tenant leaks.

        Args:
            value: Current value to scan.
            path: JSON path.
            expected_company_id: Expected company_id.
            leaks: Accumulated findings.
            depth: Current recursion depth.
        """
        if depth > 10:  # Prevent excessive recursion
            return

        if isinstance(value, dict):
            for key, val in value.items():
                current_path = f"{path}.{key}" if path else key

                if key.lower() in TENANT_LEAK_FIELD_PATTERNS:
                    if isinstance(val, (int, str)):
                        try:
                            found_id = int(val)
                            if found_id != expected_company_id and found_id > 0:
                                leaks.append({
                                    "path": current_path,
                                    "key": key,
                                    "expected": expected_company_id,
                                    "found": found_id,
                                })
                        except (ValueError, TypeError):
                            pass

                self._scan_value(val, current_path, expected_company_id, leaks, depth + 1)

        elif isinstance(value, list):
            for i, item in enumerate(value):
                if i >= TENANT_LEAK_MAX_SAMPLE_SIZE:
                    break
                current_path = f"{path}[{i}]"
                self._scan_value(item, current_path, expected_company_id, leaks, depth + 1)

    async def _log_tenant_leak(
        self,
        company_id: int,
        leaks: List[Dict[str, Any]],
        path: str,
    ) -> None:
        """Log a tenant leak detection event."""
        try:
            async with get_db_context() as db:
                service = SecurityMonitoringService(db)
                await service.create_event(
                    SecurityEventCreate(
                        company_id=company_id,
                        event_type=SecurityEventType.TENANT_LEAK,
                        severity=SeverityLevel.CRITICAL,
                        description=f"Cross-tenant data leak in response for {path}: {len(leaks)} fields",
                        details={
                            "endpoint": path,
                            "leaks": leaks,
                        },
                    )
                )
        except Exception:
            pass

    @staticmethod
    def _get_company_id(request: Request) -> Optional[int]:
        """Extract company ID from request state."""
        cid = getattr(request.state, "company_id", None)
        if cid is not None:
            try:
                return int(cid)
            except (ValueError, TypeError):
                pass
        return None
