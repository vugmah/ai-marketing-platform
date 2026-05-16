"""Audit and security API router.

Provides endpoints for:
- Audit log querying and export
- Security event management
- Login attempt tracking
- API key CRUD and rotation
- Data access logging
- Audit statistics
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import (
    APIKeyCreate,
    APIKeyListResponse,
    APIKeyResponse,
    APIKeyUpdate,
    APIKeyValidationResult,
    APIKeyValidateRequest,
    APIKeyWithPlainKey,
    AuditLogFilter,
    AuditLogListResponse,
    AuditStatsResponse,
    DataAccessLogFilter,
    DataAccessLogListResponse,
    ExportFormat,
    LoginAttemptFilter,
    LoginAttemptListResponse,
    SecurityEventFilter,
    SecurityEventListResponse,
    SecurityEventResolve,
)
from app.audit.service import (
    APIKeyService,
    AuditLogService,
    DataAccessLogger,
    LoginAttemptService,
    SecurityMonitoringService,
)
from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, require_role

router = APIRouter()


# ============================================================================
# Helpers
# ============================================================================

def _get_company_id_from_user(user: User) -> Optional[int]:
    """Extract company_id from user, handling None."""
    return getattr(user, "company_id", None)


def _get_user_id(user: User) -> int:
    """Extract user_id from user."""
    return getattr(user, "id", None)


# ============================================================================
# Audit Logs
# ============================================================================


@router.get(
    "/logs",
    response_model=Dict[str, Any],
    summary="List audit logs",
    description="Query audit logs with filters and pagination.",
)
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status (success/failure)"),
    date_from: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[datetime] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> Dict[str, Any]:
    """List audit logs with filtering and pagination.

    Returns paginated audit log entries sorted by newest first.
    Admins can view logs for their company; super_admin can view all.
    """
    filters = AuditLogFilter(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    service = AuditLogService(db)
    result = await service.query(filters)

    # Convert items to response schema
    from app.audit.schemas import AuditLogResponse
    items = []
    for item in result["items"]:
        items.append(AuditLogResponse.model_validate(item))

    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.get(
    "/logs/export",
    response_class=PlainTextResponse,
    summary="Export audit trail",
    description="Export audit logs in CSV or JSON format.",
)
async def export_audit_logs(
    fmt: ExportFormat = Query(ExportFormat.CSV, description="Export format"),
    action: Optional[str] = Query(None, description="Filter by action"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> str:
    """Export audit logs in CSV or JSON format.

    Supports CSV and JSON export formats for compliance reporting.
    """
    filters = AuditLogFilter(
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )

    service = AuditLogService(db)
    return await service.export(filters, fmt)


# ============================================================================
# Security Events
# ============================================================================


@router.get(
    "/security-events",
    response_model=Dict[str, Any],
    summary="List security events",
    description="Query security events with filters.",
)
async def list_security_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    user_id: Optional[int] = Query(None, description="Filter by user"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> Dict[str, Any]:
    """List security events with filtering and pagination."""
    filters = SecurityEventFilter(
        event_type=event_type,
        severity=severity,
        resolved=resolved,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    service = SecurityMonitoringService(db)
    result = await service.query(filters)

    from app.audit.schemas import SecurityEventResponse
    items = []
    for item in result["items"]:
        items.append(SecurityEventResponse.model_validate(item))

    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.post(
    "/security-events/{event_id}/resolve",
    response_model=Optional[Dict[str, Any]],
    summary="Resolve security event",
    description="Mark a security event as resolved with optional note.",
)
async def resolve_security_event(
    event_id: int,
    data: SecurityEventResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> Optional[Dict[str, Any]]:
    """Resolve a security event by ID."""
    service = SecurityMonitoringService(db)
    event = await service.resolve_event(event_id, data, _get_user_id(current_user))

    if event is None:
        return None

    from app.audit.schemas import SecurityEventResponse
    return SecurityEventResponse.model_validate(event).model_dump()


# ============================================================================
# Login Attempts
# ============================================================================


@router.get(
    "/login-attempts",
    response_model=Dict[str, Any],
    summary="List login attempts",
    description="Query login attempts with filters.",
)
async def list_login_attempts(
    email: Optional[str] = Query(None, description="Filter by email"),
    ip_address: Optional[str] = Query(None, description="Filter by IP"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> Dict[str, Any]:
    """List login attempts with filtering."""
    filters = LoginAttemptFilter(
        email=email,
        ip_address=ip_address,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    service = LoginAttemptService(db)
    result = await service.query(filters)

    from app.audit.schemas import LoginAttemptResponse
    items = []
    for item in result["items"]:
        items.append(LoginAttemptResponse.model_validate(item))

    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


# ============================================================================
# API Keys
# ============================================================================


@router.get(
    "/api-keys",
    response_model=Dict[str, Any],
    summary="List API keys",
    description="List all API keys for the current company.",
)
async def list_api_keys(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> Dict[str, Any]:
    """List API keys for the current user's company."""
    company_id = _get_company_id_from_user(current_user)
    if company_id is None:
        return {"items": [], "total": 0, "page": 1, "page_size": page_size}

    service = APIKeyService(db)
    result = await service.list_keys(company_id, page, page_size)

    from app.audit.schemas import APIKeyResponse
    items = []
    for item in result["items"]:
        items.append(APIKeyResponse.model_validate(item))

    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.post(
    "/api-keys",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new scoped API key. The key is only shown once.",
)
async def create_api_key(
    data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> Dict[str, Any]:
    """Create a new API key.

    Returns the API key metadata and the plain key (shown once only).
    Store the plain_key securely - it cannot be retrieved later.
    """
    company_id = _get_company_id_from_user(current_user)
    if company_id is None:
        raise Exception("Company ID required")

    service = APIKeyService(db)
    result = await service.create(data, company_id, _get_user_id(current_user))

    from app.audit.schemas import APIKeyResponse
    key = result["key"]

    return {
        "id": key.id,
        "name": key.name,
        "plain_key": result["plain_key"],  # Shown once only!
        "scopes": key.scopes,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "created_at": key.created_at.isoformat() if key.created_at else None,
    }


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
    description="Revoke (deactivate) an API key.",
)
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> None:
    """Revoke an API key by ID."""
    company_id = _get_company_id_from_user(current_user)
    if company_id is None:
        raise Exception("Company ID required")

    service = APIKeyService(db)
    success = await service.revoke(key_id, company_id)
    if not success:
        raise Exception("API key not found")


@router.post(
    "/api-keys/{key_id}/rotate",
    response_model=Dict[str, Any],
    summary="Rotate API key",
    description="Rotate an API key (revoke old, create new with same settings).",
)
async def rotate_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> Dict[str, Any]:
    """Rotate an API key.

    Revokes the old key and creates a new one with the same settings.
    Returns the new key (shown once only).
    """
    company_id = _get_company_id_from_user(current_user)
    if company_id is None:
        raise Exception("Company ID required")

    service = APIKeyService(db)
    result = await service.rotate(key_id, company_id)

    if result is None:
        raise Exception("API key not found")

    key = result["key"]
    return {
        "id": key.id,
        "name": key.name,
        "plain_key": result["plain_key"],  # Shown once only!
        "scopes": key.scopes,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "created_at": key.created_at.isoformat() if key.created_at else None,
    }


@router.post(
    "/api-keys/validate",
    response_model=APIKeyValidationResult,
    summary="Validate API key",
    description="Validate an API key and check optional scope.",
)
async def validate_api_key(
    data: APIKeyValidateRequest,
    db: AsyncSession = Depends(get_db),
) -> APIKeyValidationResult:
    """Validate an API key.

    Checks if the key exists, is active, not expired, and optionally
    has the required scope.
    """
    service = APIKeyService(db)
    return await service.validate_key(data.api_key, data.required_scope)


# ============================================================================
# Data Access Logs
# ============================================================================


@router.get(
    "/data-access",
    response_model=Dict[str, Any],
    summary="List data access logs",
    description="Query data access logs for GDPR/KVKK compliance.",
)
async def list_data_access_logs(
    table_name: Optional[str] = Query(None, description="Filter by table"),
    record_id: Optional[str] = Query(None, description="Filter by record ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    user_id: Optional[int] = Query(None, description="Filter by user"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> Dict[str, Any]:
    """List data access logs for compliance auditing."""
    filters = DataAccessLogFilter(
        table_name=table_name,
        record_id=record_id,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    service = DataAccessLogger(db)
    result = await service.query(filters)

    from app.audit.schemas import DataAccessLogResponse
    items = []
    for item in result["items"]:
        items.append(DataAccessLogResponse.model_validate(item))

    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


# ============================================================================
# Audit Statistics
# ============================================================================


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    summary="Audit statistics",
    description="Get summary statistics for the audit dashboard.",
)
async def get_audit_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> Dict[str, Any]:
    """Get audit statistics for the dashboard.

    Returns counts of audit logs, security events, login attempts,
    API keys, and data access logs.
    """
    from sqlalchemy import desc, func, select

    company_id = _get_company_id_from_user(current_user)

    # Audit log count
    from app.audit.models import AuditLog
    stmt = select(func.count()).select_from(AuditLog)
    if company_id:
        stmt = stmt.where(AuditLog.company_id == company_id)
    result = await db.execute(stmt)
    total_audit_logs = result.scalar() or 0

    # Security event counts
    from app.audit.models import SecurityEvent
    stmt = select(func.count()).select_from(SecurityEvent)
    if company_id:
        stmt = stmt.where(SecurityEvent.company_id == company_id)
    result = await db.execute(stmt)
    total_security_events = result.scalar() or 0

    # Open events
    stmt = select(func.count()).select_from(SecurityEvent).where(SecurityEvent.resolved == False)
    if company_id:
        stmt = stmt.where(SecurityEvent.company_id == company_id)
    result = await db.execute(stmt)
    open_events = result.scalar() or 0

    # By severity
    stmt = (
        select(SecurityEvent.severity, func.count())
        .group_by(SecurityEvent.severity)
    )
    if company_id:
        stmt = stmt.where(SecurityEvent.company_id == company_id)
    result = await db.execute(stmt)
    severity_counts = {row[0]: row[1] for row in result.all()}

    # Login attempts last 24h
    from app.audit.models import LoginAttempt
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = select(func.count()).select_from(LoginAttempt).where(LoginAttempt.created_at >= last_24h)
    if company_id:
        stmt = stmt.where(LoginAttempt.company_id == company_id)
    result = await db.execute(stmt)
    total_login_24h = result.scalar() or 0

    # Failed logins last 24h
    from app.audit.models import LoginAttempt
    stmt = (
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.created_at >= last_24h)
        .where(LoginAttempt.status == "failed")
    )
    if company_id:
        stmt = stmt.where(LoginAttempt.company_id == company_id)
    result = await db.execute(stmt)
    failed_login_24h = result.scalar() or 0

    # Active API keys
    from app.audit.models import APIKey
    stmt = select(func.count()).select_from(APIKey).where(APIKey.is_active == True)
    if company_id:
        stmt = stmt.where(APIKey.company_id == company_id)
    result = await db.execute(stmt)
    active_api_keys = result.scalar() or 0

    # Data access logs 24h
    from app.audit.models import DataAccessLog
    stmt = select(func.count()).select_from(DataAccessLog).where(DataAccessLog.created_at >= last_24h)
    if company_id:
        stmt = stmt.where(DataAccessLog.company_id == company_id)
    result = await db.execute(stmt)
    data_access_24h = result.scalar() or 0

    # Recent events
    stmt = select(SecurityEvent).order_by(desc(SecurityEvent.created_at)).limit(5)
    if company_id:
        stmt = stmt.where(SecurityEvent.company_id == company_id)
    result = await db.execute(stmt)
    recent_events_raw = result.scalars().all()

    from app.audit.schemas import SecurityEventResponse
    recent_events = [SecurityEventResponse.model_validate(e) for e in recent_events_raw]

    return {
        "total_audit_logs": total_audit_logs,
        "total_security_events": total_security_events,
        "open_security_events": open_events,
        "critical_events": severity_counts.get("critical", 0),
        "high_events": severity_counts.get("high", 0),
        "total_login_attempts_24h": total_login_24h,
        "failed_login_attempts_24h": failed_login_24h,
        "active_api_keys": active_api_keys,
        "data_access_logs_24h": data_access_24h,
        "events_by_severity": severity_counts,
        "recent_events": [e.model_dump() for e in recent_events],
    }
