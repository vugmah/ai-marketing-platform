"""Audit and security monitoring services.

Services:
- AuditLogService: Log and query audit trail
- SecurityMonitoringService: Detect anomalies and manage events
- LoginAttemptService: Track logins, detect brute force
- APIKeyService: CRUD and validate API keys
- DataAccessLogger: Compliance data access logging
- TenantLeakDetectionService: Detect cross-tenant data leaks
"""

import asyncio
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import and_, or_, text

from app.audit.constants import (
    BRUTE_FORCE_ACCOUNT_LOCKOUT_THRESHOLD,
    BRUTE_FORCE_BLOCK_DURATION_SECONDS,
    BRUTE_FORCE_MAX_ATTEMPTS,
    BRUTE_FORCE_WINDOW_SECONDS,
    DATA_EXFILTRATION_RECORD_THRESHOLD,
    DATA_EXFILTRATION_SIZE_THRESHOLD_MB,
    OFF_HOURS_END,
    OFF_HOURS_START,
    RAPID_REQUEST_THRESHOLD,
    SecurityEventType,
    SeverityLevel,
)
from app.audit.models import (
    APIKey,
    AuditAction,
    AuditLog,
    DataAccessAction,
    DataAccessLog,
    LoginAttempt,
    LoginStatus,
    ResourceType,
    SecurityEvent,
)
from app.audit.schemas import (
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyValidationResult,
    AuditLogCreate,
    AuditLogFilter,
    AuditStatsResponse,
    DataAccessLogCreate,
    DataAccessLogFilter,
    ExportFormat,
    LoginAttemptFilter,
    SecurityEventCreate,
    SecurityEventFilter,
    SecurityEventResolve,
)
from app.audit.security_utils import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
)
from app.redis_client import get_redis_client


# ============================================================================
# AuditLogService
# ============================================================================


class AuditLogService:
    """Service for managing audit log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: AuditAction,
        resource_type: ResourceType,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Create a new audit log entry.

        Args:
            action: The action performed.
            resource_type: The type of resource affected.
            company_id: Tenant company ID.
            branch_id: Branch ID.
            user_id: User who performed the action.
            resource_id: ID of the affected resource.
            details: Additional JSON-serializable context.
            ip_address: Client IP address.
            user_agent: Client user agent string.
            session_id: Session identifier.
            correlation_id: Request correlation ID.
            status: "success" or "failure".
            error_message: Error message if status is "failure".

        Returns:
            The created AuditLog instance.
        """
        entry = AuditLog(
            company_id=company_id,
            branch_id=branch_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            correlation_id=correlation_id,
            status=status,
            error_message=error_message,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_ms: Optional[float] = None,
        correlation_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log an API request as an audit entry.

        Args:
            method: HTTP method.
            path: Request path.
            status_code: HTTP response status.
            company_id: Tenant company ID.
            branch_id: Branch ID.
            user_id: User who made the request.
            ip_address: Client IP.
            user_agent: Client user agent.
            duration_ms: Request duration in milliseconds.
            correlation_id: Request correlation ID.
            error_message: Error if request failed.

        Returns:
            The created AuditLog instance.
        """
        details = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }

        # Determine action from HTTP method
        action_map = {
            "POST": AuditAction.CREATE,
            "GET": AuditAction.READ,
            "PUT": AuditAction.UPDATE,
            "PATCH": AuditAction.UPDATE,
            "DELETE": AuditAction.DELETE,
        }
        action = action_map.get(method, AuditAction.API_CALL)

        status = "success" if status_code < 400 else "failure"

        return await self.log(
            action=action,
            resource_type=ResourceType.API_KEY,
            company_id=company_id,
            branch_id=branch_id,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            status=status,
            error_message=error_message,
        )

    async def query(self, filters: AuditLogFilter) -> Dict[str, Any]:
        """Query audit logs with filters.

        Args:
            filters: AuditLogFilter with pagination and filtering.

        Returns:
            Dict with items (list), total, page, page_size.
        """
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at))

        if filters.action:
            stmt = stmt.where(AuditLog.action == filters.action)
        if filters.resource_type:
            stmt = stmt.where(AuditLog.resource_type == filters.resource_type)
        if filters.resource_id:
            stmt = stmt.where(AuditLog.resource_id == filters.resource_id)
        if filters.user_id:
            stmt = stmt.where(AuditLog.user_id == filters.user_id)
        if filters.status:
            stmt = stmt.where(AuditLog.status == filters.status)
        if filters.date_from:
            stmt = stmt.where(AuditLog.created_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(AuditLog.created_at <= filters.date_to)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Paginate
        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.offset(offset).limit(filters.page_size)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": list(items),
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        }

    async def export(
        self,
        filters: AuditLogFilter,
        fmt: ExportFormat = ExportFormat.JSON,
    ) -> str:
        """Export audit logs in CSV or JSON format.

        Args:
            filters: Filters for the export query.
            fmt: Export format (csv or json).

        Returns:
            The exported data as a string.
        """
        # Remove pagination for export
        filters.page = 1
        filters.page_size = 10000

        result = await self.query(filters)
        items = result["items"]

        if fmt == ExportFormat.CSV:
            return self._export_csv(items)
        else:
            return self._export_json(items)

    def _export_csv(self, items: List[AuditLog]) -> str:
        """Export audit logs as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "id", "created_at", "company_id", "branch_id", "user_id",
            "action", "resource_type", "resource_id", "status",
            "ip_address", "correlation_id", "details",
        ])

        for item in items:
            writer.writerow([
                item.id,
                item.created_at.isoformat() if item.created_at else "",
                item.company_id or "",
                item.branch_id or "",
                item.user_id or "",
                item.action.value if item.action else "",
                item.resource_type.value if item.resource_type else "",
                item.resource_id or "",
                item.status,
                item.ip_address or "",
                item.correlation_id or "",
                json.dumps(item.details) if item.details else "",
            ])

        return output.getvalue()

    def _export_json(self, items: List[AuditLog]) -> str:
        """Export audit logs as JSON."""
        data = []
        for item in items:
            data.append({
                "id": item.id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "company_id": item.company_id,
                "branch_id": item.branch_id,
                "user_id": item.user_id,
                "action": item.action.value if item.action else None,
                "resource_type": item.resource_type.value if item.resource_type else None,
                "resource_id": item.resource_id,
                "status": item.status,
                "ip_address": item.ip_address,
                "user_agent": item.user_agent,
                "session_id": item.session_id,
                "correlation_id": item.correlation_id,
                "details": item.details,
                "error_message": item.error_message,
            })
        return json.dumps(data, indent=2, default=str)


# ============================================================================
# SecurityMonitoringService
# ============================================================================


class SecurityMonitoringService:
    """Service for security event detection and management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, data: SecurityEventCreate) -> SecurityEvent:
        """Create a new security event.

        Args:
            data: Security event data.

        Returns:
            The created SecurityEvent.
        """
        event = SecurityEvent(
            company_id=data.company_id,
            event_type=data.event_type,
            severity=data.severity,
            description=data.description,
            source_ip=data.source_ip,
            user_id=data.user_id,
            details=data.details,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def query(self, filters: SecurityEventFilter) -> Dict[str, Any]:
        """Query security events with filters.

        Args:
            filters: SecurityEventFilter with pagination and filtering.

        Returns:
            Dict with items, total, page, page_size.
        """
        stmt = select(SecurityEvent).order_by(desc(SecurityEvent.created_at))

        if filters.event_type:
            stmt = stmt.where(SecurityEvent.event_type == filters.event_type)
        if filters.severity:
            stmt = stmt.where(SecurityEvent.severity == filters.severity)
        if filters.resolved is not None:
            stmt = stmt.where(SecurityEvent.resolved == filters.resolved)
        if filters.user_id:
            stmt = stmt.where(SecurityEvent.user_id == filters.user_id)
        if filters.date_from:
            stmt = stmt.where(SecurityEvent.created_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(SecurityEvent.created_at <= filters.date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.offset(offset).limit(filters.page_size)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": list(items),
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        }

    async def resolve_event(
        self,
        event_id: int,
        data: SecurityEventResolve,
        resolved_by: int,
    ) -> Optional[SecurityEvent]:
        """Mark a security event as resolved.

        Args:
            event_id: The event ID.
            data: Resolution data.
            resolved_by: User ID who resolved.

        Returns:
            The updated SecurityEvent, or None if not found.
        """
        stmt = select(SecurityEvent).where(SecurityEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            return None

        event.resolved = True
        event.resolved_by = resolved_by
        event.resolved_at = datetime.now(timezone.utc)

        if data.resolution_note:
            if event.details is None:
                event.details = {}
            event.details["resolution_note"] = data.resolution_note

        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def detect_rapid_requests(
        self,
        ip_address: str,
        user_id: Optional[int] = None,
    ) -> Optional[SecurityEventCreate]:
        """Detect rapid request patterns from an IP.

        Args:
            ip_address: Client IP.
            user_id: Optional user ID.

        Returns:
            SecurityEventCreate if anomaly detected, None otherwise.
        """
        redis = await get_redis_client()
        window, max_requests = RAPID_REQUEST_THRESHOLD

        key = f"req_rate:{ip_address}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window)

        if count > max_requests:
            return SecurityEventCreate(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                severity=SeverityLevel.HIGH,
                description=f"Rapid requests detected from {ip_address}: {count} requests in {window}s",
                source_ip=ip_address,
                user_id=user_id,
                details={"request_count": count, "window_seconds": window},
            )

        return None

    async def detect_off_hours_access(
        self,
        ip_address: str,
        user_id: int,
        company_timezone: str = "Asia/Baku",
    ) -> Optional[SecurityEventCreate]:
        """Detect access outside business hours.

        Args:
            ip_address: Client IP.
            user_id: User ID.
            company_timezone: Company's timezone string.

        Returns:
            SecurityEventCreate if off-hours access detected.
        """
        try:
            import pytz
            tz = pytz.timezone(company_timezone)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now(timezone.utc)

        hour = now.hour
        if hour >= OFF_HOURS_START or hour < OFF_HOURS_END:
            return SecurityEventCreate(
                event_type=SecurityEventType.OFF_HOURS_ACCESS,
                severity=SeverityLevel.LOW,
                description=f"Off-hours access at {hour}:00 from {ip_address}",
                source_ip=ip_address,
                user_id=user_id,
                details={"hour": hour, "timezone": company_timezone},
            )

        return None

    async def detect_data_exfiltration(
        self,
        user_id: int,
        company_id: int,
        record_count: int,
        data_size_mb: float,
        ip_address: Optional[str] = None,
    ) -> Optional[SecurityEventCreate]:
        """Detect potential data exfiltration via large exports.

        Args:
            user_id: User performing the export.
            company_id: Tenant company ID.
            record_count: Number of records exported.
            data_size_mb: Size of exported data in MB.
            ip_address: Client IP.

        Returns:
            SecurityEventCreate if exfiltration suspected.
        """
        if record_count > DATA_EXFILTRATION_RECORD_THRESHOLD:
            return SecurityEventCreate(
                event_type=SecurityEventType.DATA_EXFILTRATION,
                severity=SeverityLevel.HIGH if record_count > 5000 else SeverityLevel.MEDIUM,
                description=f"Large data export: {record_count} records ({data_size_mb:.1f} MB)",
                source_ip=ip_address,
                user_id=user_id,
                company_id=company_id,
                details={
                    "record_count": record_count,
                    "data_size_mb": data_size_mb,
                    "threshold": DATA_EXFILTRATION_RECORD_THRESHOLD,
                },
            )

        if data_size_mb > DATA_EXFILTRATION_SIZE_THRESHOLD_MB:
            return SecurityEventCreate(
                event_type=SecurityEventType.DATA_EXFILTRATION,
                severity=SeverityLevel.HIGH,
                description=f"Large data export: {record_count} records ({data_size_mb:.1f} MB)",
                source_ip=ip_address,
                user_id=user_id,
                company_id=company_id,
                details={
                    "record_count": record_count,
                    "data_size_mb": data_size_mb,
                    "threshold": DATA_EXFILTRATION_SIZE_THRESHOLD_MB,
                },
            )

        return None

    async def get_recent_events(
        self, limit: int = 10, company_id: Optional[int] = None
    ) -> List[SecurityEvent]:
        """Get recent security events.

        Args:
            limit: Maximum number of events.
            company_id: Optional company filter.

        Returns:
            List of recent SecurityEvents.
        """
        stmt = select(SecurityEvent).order_by(desc(SecurityEvent.created_at)).limit(limit)
        if company_id:
            stmt = stmt.where(SecurityEvent.company_id == company_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ============================================================================
# LoginAttemptService
# ============================================================================


class LoginAttemptService:
    """Service for tracking login attempts and detecting brute force."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_attempt(
        self,
        email: str,
        ip_address: str,
        status: LoginStatus,
        company_id: Optional[int] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> LoginAttempt:
        """Record a login attempt.

        Args:
            email: Email used for login.
            ip_address: Client IP.
            status: Login result status.
            company_id: Tenant company ID.
            user_agent: Client user agent.
            failure_reason: Reason for failure.

        Returns:
            The created LoginAttempt.
        """
        attempt = LoginAttempt(
            company_id=company_id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            failure_reason=failure_reason,
        )
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt

    async def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if an IP is temporarily blocked due to failed logins.

        Args:
            ip_address: The IP to check.

        Returns:
            True if the IP is blocked.
        """
        redis = await get_redis_client()
        blocked = await redis.get(f"login_block:{ip_address}")
        return blocked is not None

    async def is_account_locked(self, email: str) -> bool:
        """Check if an account is locked due to too many failed attempts.

        Args:
            email: The email to check.

        Returns:
            True if the account is locked.
        """
        redis = await get_redis_client()
        locked = await redis.get(f"account_lock:{email}")
        return locked is not None

    async def check_brute_force(
        self,
        email: str,
        ip_address: str,
    ) -> Dict[str, Any]:
        """Check for brute force patterns and apply blocks if needed.

        Args:
            email: Login email.
            ip_address: Client IP.

        Returns:
            Dict with is_blocked, block_reason, and should_log_event.
        """
        result = {
            "is_blocked": False,
            "block_reason": None,
            "should_log_event": False,
        }

        # Check existing blocks
        if await self.is_ip_blocked(ip_address):
            result["is_blocked"] = True
            result["block_reason"] = "IP temporarily blocked"
            return result

        if await self.is_account_locked(email):
            result["is_blocked"] = True
            result["block_reason"] = "Account temporarily locked"
            return result

        # Count recent failed attempts for this IP
        redis = await get_redis_client()
        ip_key = f"login_fail_ip:{ip_address}"
        ip_fails = await redis.incr(ip_key)
        if ip_fails == 1:
            await redis.expire(ip_key, BRUTE_FORCE_WINDOW_SECONDS)

        # Count recent failed attempts for this email
        email_key = f"login_fail_email:{email}"
        email_fails = await redis.incr(email_key)
        if email_fails == 1:
            await redis.expire(email_key, BRUTE_FORCE_WINDOW_SECONDS)

        # Block IP if too many failures
        if ip_fails >= BRUTE_FORCE_MAX_ATTEMPTS:
            await redis.set(
                f"login_block:{ip_address}",
                "brute_force",
                ex=BRUTE_FORCE_BLOCK_DURATION_SECONDS,
            )
            result["is_blocked"] = True
            result["block_reason"] = f"Too many failed attempts from this IP ({ip_fails})"
            result["should_log_event"] = True

        # Lock account if too many failures
        if email_fails >= BRUTE_FORCE_ACCOUNT_LOCKOUT_THRESHOLD:
            await redis.set(
                f"account_lock:{email}",
                "too_many_failures",
                ex=BRUTE_FORCE_BLOCK_DURATION_SECONDS,
            )
            result["is_blocked"] = True
            result["block_reason"] = f"Account locked after {email_fails} failed attempts"
            result["should_log_event"] = True

        return result

    async def reset_failures(self, email: str, ip_address: str) -> None:
        """Reset failure counters after successful login.

        Args:
            email: The successfully logged in email.
            ip_address: The client IP.
        """
        redis = await get_redis_client()
        await redis.delete(f"login_fail_ip:{ip_address}")
        await redis.delete(f"login_fail_email:{email}")
        # Also clear any blocks
        await redis.delete(f"login_block:{ip_address}")
        await redis.delete(f"account_lock:{email}")

    async def query(self, filters: LoginAttemptFilter) -> Dict[str, Any]:
        """Query login attempts with filters.

        Args:
            filters: LoginAttemptFilter.

        Returns:
            Dict with items, total, page, page_size.
        """
        stmt = select(LoginAttempt).order_by(desc(LoginAttempt.created_at))

        if filters.email:
            stmt = stmt.where(LoginAttempt.email == filters.email)
        if filters.ip_address:
            stmt = stmt.where(LoginAttempt.ip_address == filters.ip_address)
        if filters.status:
            stmt = stmt.where(LoginAttempt.status == filters.status)
        if filters.date_from:
            stmt = stmt.where(LoginAttempt.created_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(LoginAttempt.created_at <= filters.date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.offset(offset).limit(filters.page_size)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": list(items),
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        }


# ============================================================================
# APIKeyService
# ============================================================================


class APIKeyService:
    """Service for managing scoped API keys."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, data: APIKeyCreate, company_id: int, user_id: int
    ) -> Dict[str, Any]:
        """Create a new API key.

        Args:
            data: API key creation data.
            company_id: Tenant company ID.
            user_id: Owner user ID.

        Returns:
            Dict with the APIKeyResponse and the plain_key (shown once).
        """
        plain_key = generate_api_key()
        key_hash = hash_api_key(plain_key)

        expires_at = None
        if data.expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)

        api_key = APIKey(
            company_id=company_id,
            user_id=user_id,
            name=data.name,
            key_hash=key_hash,
            scopes=data.scopes,
            expires_at=expires_at,
            is_active=True,
        )

        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        return {"key": api_key, "plain_key": plain_key}

    async def get_by_id(self, key_id: int, company_id: int) -> Optional[APIKey]:
        """Get an API key by ID scoped to a company.

        Args:
            key_id: The API key ID.
            company_id: Tenant company ID.

        Returns:
            The APIKey or None.
        """
        stmt = select(APIKey).where(
            and_(APIKey.id == key_id, APIKey.company_id == company_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_keys(
        self,
        company_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """List API keys for a company.

        Args:
            company_id: Tenant company ID.
            page: Page number.
            page_size: Records per page.

        Returns:
            Dict with items, total, page, page_size.
        """
        stmt = (
            select(APIKey)
            .where(APIKey.company_id == company_id)
            .order_by(desc(APIKey.created_at))
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": list(items),
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update(
        self, key_id: int, company_id: int, data: APIKeyUpdate
    ) -> Optional[APIKey]:
        """Update an API key.

        Args:
            key_id: The API key ID.
            company_id: Tenant company ID.
            data: Update data.

        Returns:
            The updated APIKey or None.
        """
        api_key = await self.get_by_id(key_id, company_id)
        if api_key is None:
            return None

        if data.name is not None:
            api_key.name = data.name
        if data.scopes is not None:
            api_key.scopes = data.scopes
        if data.is_active is not None:
            api_key.is_active = data.is_active

        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

    async def revoke(self, key_id: int, company_id: int) -> bool:
        """Revoke (soft-delete) an API key.

        Args:
            key_id: The API key ID.
            company_id: Tenant company ID.

        Returns:
            True if revoked, False if not found.
        """
        api_key = await self.get_by_id(key_id, company_id)
        if api_key is None:
            return False

        api_key.is_active = False
        await self.db.commit()
        return True

    async def rotate(self, key_id: int, company_id: int) -> Optional[Dict[str, Any]]:
        """Rotate an API key (revoke old, create new).

        Args:
            key_id: The API key ID to rotate.
            company_id: Tenant company ID.

        Returns:
            Dict with new key and plain_key, or None if not found.
        """
        old_key = await self.get_by_id(key_id, company_id)
        if old_key is None:
            return None

        # Generate new key with same settings
        from app.audit.schemas import APIKeyCreate

        create_data = APIKeyCreate(
            name=old_key.name,
            scopes=old_key.scopes,
            expires_days=365 if old_key.expires_at else None,
        )

        result = await self.create(create_data, company_id, old_key.user_id)

        # Revoke old key
        old_key.is_active = False
        await self.db.commit()

        return result

    async def validate_key(
        self, plain_key: str, required_scope: Optional[str] = None
    ) -> APIKeyValidationResult:
        """Validate an API key and check optional scope.

        Args:
            plain_key: The plain API key.
            required_scope: Optional required scope.

        Returns:
            APIKeyValidationResult with validation outcome.
        """
        key_hash = hash_api_key(plain_key)

        stmt = select(APIKey).where(
            and_(APIKey.key_hash == key_hash, APIKey.is_active == True)
        )
        result = await self.db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if api_key is None:
            return APIKeyValidationResult(valid=False, message="Invalid API key")

        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return APIKeyValidationResult(valid=False, message="API key has expired")

        # Check scope
        scopes = api_key.scopes or []
        if required_scope and required_scope not in scopes:
            if "admin" not in scopes:
                return APIKeyValidationResult(
                    valid=False,
                    message=f"Insufficient scope: {required_scope} required",
                    scopes=scopes,
                )

        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await self.db.commit()

        return APIKeyValidationResult(
            valid=True,
            company_id=api_key.company_id,
            user_id=api_key.user_id,
            scopes=scopes,
            message="Valid",
        )

    async def record_usage(self, key_id: int) -> None:
        """Record API key usage (update last_used_at).

        Args:
            key_id: The API key ID.
        """
        stmt = (
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.commit()


# ============================================================================
# DataAccessLogger
# ============================================================================


class DataAccessLogger:
    """Service for logging data access for GDPR/KVKK compliance."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_access(
        self,
        table_name: str,
        record_id: str,
        action: DataAccessAction,
        company_id: int,
        user_id: Optional[int] = None,
        accessed_fields: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ) -> DataAccessLog:
        """Log a data access event.

        Args:
            table_name: Database table accessed.
            record_id: ID of the accessed record.
            action: Type of access (read/create/update/delete).
            company_id: Tenant company ID.
            user_id: User who accessed the data.
            accessed_fields: Fields that were accessed.
            reason: Business reason.

        Returns:
            The created DataAccessLog.
        """
        log_entry = DataAccessLog(
            company_id=company_id,
            user_id=user_id,
            table_name=table_name,
            record_id=str(record_id),
            action=action,
            accessed_fields=accessed_fields,
            reason=reason,
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry

    async def log_read(
        self,
        table_name: str,
        record_id: str,
        company_id: int,
        user_id: Optional[int] = None,
        accessed_fields: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ) -> DataAccessLog:
        """Convenience method to log a read access."""
        return await self.log_access(
            table_name=table_name,
            record_id=record_id,
            action=DataAccessAction.READ,
            company_id=company_id,
            user_id=user_id,
            accessed_fields=accessed_fields,
            reason=reason,
        )

    async def log_create(
        self,
        table_name: str,
        record_id: str,
        company_id: int,
        user_id: Optional[int] = None,
        accessed_fields: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ) -> DataAccessLog:
        """Convenience method to log a create access."""
        return await self.log_access(
            table_name=table_name,
            record_id=record_id,
            action=DataAccessAction.CREATE,
            company_id=company_id,
            user_id=user_id,
            accessed_fields=accessed_fields,
            reason=reason,
        )

    async def log_update(
        self,
        table_name: str,
        record_id: str,
        company_id: int,
        user_id: Optional[int] = None,
        accessed_fields: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ) -> DataAccessLog:
        """Convenience method to log an update access."""
        return await self.log_access(
            table_name=table_name,
            record_id=record_id,
            action=DataAccessAction.UPDATE,
            company_id=company_id,
            user_id=user_id,
            accessed_fields=accessed_fields,
            reason=reason,
        )

    async def log_delete(
        self,
        table_name: str,
        record_id: str,
        company_id: int,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> DataAccessLog:
        """Convenience method to log a delete access."""
        return await self.log_access(
            table_name=table_name,
            record_id=record_id,
            action=DataAccessAction.DELETE,
            company_id=company_id,
            user_id=user_id,
            reason=reason,
        )

    async def query(self, filters: DataAccessLogFilter) -> Dict[str, Any]:
        """Query data access logs with filters.

        Args:
            filters: DataAccessLogFilter.

        Returns:
            Dict with items, total, page, page_size.
        """
        stmt = select(DataAccessLog).order_by(desc(DataAccessLog.created_at))

        if filters.table_name:
            stmt = stmt.where(DataAccessLog.table_name == filters.table_name)
        if filters.record_id:
            stmt = stmt.where(DataAccessLog.record_id == filters.record_id)
        if filters.action:
            stmt = stmt.where(DataAccessLog.action == filters.action)
        if filters.user_id:
            stmt = stmt.where(DataAccessLog.user_id == filters.user_id)
        if filters.date_from:
            stmt = stmt.where(DataAccessLog.created_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(DataAccessLog.created_at <= filters.date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.offset(offset).limit(filters.page_size)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return {
            "items": list(items),
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        }

    async def get_data_subject_access_log(
        self, company_id: int, record_ids: List[str], table_name: str
    ) -> List[DataAccessLog]:
        """Get all access logs for a data subject (GDPR/KVKK request).

        Args:
            company_id: Tenant company ID.
            record_ids: List of record IDs belonging to the data subject.
            table_name: The table containing the data.

        Returns:
            List of DataAccessLogs for the subject's records.
        """
        stmt = (
            select(DataAccessLog)
            .where(
                and_(
                    DataAccessLog.company_id == company_id,
                    DataAccessLog.table_name == table_name,
                    DataAccessLog.record_id.in_(record_ids),
                )
            )
            .order_by(desc(DataAccessLog.created_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ============================================================================
# TenantLeakDetectionService
# ============================================================================


class TenantLeakDetectionService:
    """Service for detecting cross-tenant data leaks in responses."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_response(
        self,
        response_body: Any,
        expected_company_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Scan a response body for potential tenant data leakage.

        Checks if any nested company_id or tenant_id fields contain
        a value different from the requesting user's company_id.

        Args:
            response_body: The response body (dict, list, or other).
            expected_company_id: The expected company_id.

        Returns:
            Dict with leak findings, or None if no leak detected.
        """
        leaks: List[Dict[str, Any]] = []
        self._scan_value(response_body, "", expected_company_id, leaks)

        if leaks:
            # Log the leak detection
            await self._log_tenant_leak(expected_company_id, leaks)
            return {
                "leak_detected": True,
                "findings": leaks,
            }

        return None

    def _scan_value(
        self,
        value: Any,
        path: str,
        expected_company_id: int,
        leaks: List[Dict[str, Any]],
    ) -> None:
        """Recursively scan a value for tenant leaks.

        Args:
            value: Current value to scan.
            path: JSON path to current value.
            expected_company_id: Expected company_id.
            leaks: Accumulated leak findings.
        """
        if isinstance(value, dict):
            for key, val in value.items():
                current_path = f"{path}.{key}" if path else key

                # Check if this key is a tenant identifier
                if key.lower() in ("company_id", "tenant_id", "organization_id"):
                    if isinstance(val, (int, str)):
                        try:
                            found_id = int(val)
                            if found_id != expected_company_id:
                                leaks.append({
                                    "path": current_path,
                                    "key": key,
                                    "expected": expected_company_id,
                                    "found": found_id,
                                })
                        except (ValueError, TypeError):
                            pass

                self._scan_value(val, current_path, expected_company_id, leaks)

        elif isinstance(value, list):
            for i, item in enumerate(value):
                current_path = f"{path}[{i}]"
                self._scan_value(item, current_path, expected_company_id, leaks)

    async def _log_tenant_leak(
        self, company_id: int, leaks: List[Dict[str, Any]]
    ) -> None:
        """Log a tenant leak as a security event.

        Args:
            company_id: The affected company.
            leaks: List of leak findings.
        """
        security_service = SecurityMonitoringService(self.db)
        await security_service.create_event(
            SecurityEventCreate(
                company_id=company_id,
                event_type=SecurityEventType.TENANT_LEAK,
                severity=SeverityLevel.CRITICAL,
                description=f"Cross-tenant data leak detected: {len(leaks)} fields",
                details={"leaks": leaks},
            )
        )

    async def validate_query_tenant(
        self,
        stmt: Any,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Any:
        """Add tenant filters to an existing SQLAlchemy query.

        Ensures the query only returns data for the requesting tenant.

        Args:
            stmt: The SQLAlchemy select statement.
            company_id: The tenant company ID.
            branch_id: Optional branch ID for additional filtering.

        Returns:
            The modified statement with tenant filters applied.
        """
        from sqlalchemy import inspect

        # Get the table from the statement
        table = stmt.froms[0] if hasattr(stmt, "froms") and stmt.froms else None

        if table is not None:
            # Check if table has company_id column
            mapper = inspect(table)
            columns = {col.name for col in mapper.columns} if hasattr(mapper, "columns") else set()

            if "company_id" in columns:
                stmt = stmt.where(table.c.company_id == company_id)

            if branch_id is not None and "branch_id" in columns:
                stmt = stmt.where(table.c.branch_id == branch_id)

        return stmt
