"""Pydantic v2 schemas for the audit module."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Audit Log Schemas
# ============================================================================


class AuditLogBase(BaseModel):
    """Base schema for audit log entries."""

    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(default=None, description="ID of affected resource")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    correlation_id: Optional[str] = Field(default=None, description="Request correlation ID")
    status: str = Field(default="success", description="success or failure")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class AuditLogCreate(AuditLogBase):
    """Schema for creating an audit log entry."""

    company_id: Optional[int] = Field(default=None, description="Tenant company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    user_id: Optional[int] = Field(default=None, description="User who performed action")


class AuditLogResponse(AuditLogBase):
    """Schema for audit log response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Audit log ID")
    company_id: Optional[int] = Field(default=None, description="Tenant company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    user_id: Optional[int] = Field(default=None, description="User who performed action")
    created_at: datetime = Field(..., description="Timestamp of the action")


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: List[AuditLogResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Records per page")


class AuditLogFilter(BaseModel):
    """Filters for querying audit logs."""

    action: Optional[str] = Field(default=None, description="Filter by action type")
    resource_type: Optional[str] = Field(default=None, description="Filter by resource type")
    resource_id: Optional[str] = Field(default=None, description="Filter by resource ID")
    user_id: Optional[int] = Field(default=None, description="Filter by user")
    status: Optional[str] = Field(default=None, description="Filter by status")
    date_from: Optional[datetime] = Field(default=None, description="Start date")
    date_to: Optional[datetime] = Field(default=None, description="End date")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ============================================================================
# Security Event Schemas
# ============================================================================


class SecurityEventBase(BaseModel):
    """Base schema for security events."""

    event_type: str = Field(..., description="Type of security event")
    severity: str = Field(..., description="low, medium, high, or critical")
    description: str = Field(..., description="Human-readable description")
    source_ip: Optional[str] = Field(default=None, description="Source IP address")
    user_id: Optional[int] = Field(default=None, description="Associated user")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class SecurityEventCreate(SecurityEventBase):
    """Schema for creating a security event."""

    company_id: Optional[int] = Field(default=None, description="Tenant company ID")


class SecurityEventResponse(SecurityEventBase):
    """Schema for security event response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Event ID")
    company_id: Optional[int] = Field(default=None, description="Tenant company ID")
    resolved: bool = Field(default=False, description="Whether the event is resolved")
    resolved_by: Optional[int] = Field(default=None, description="User who resolved")
    resolved_at: Optional[datetime] = Field(default=None, description="Resolution timestamp")
    created_at: datetime = Field(..., description="Event timestamp")


class SecurityEventListResponse(BaseModel):
    """Paginated list of security events."""

    items: List[SecurityEventResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Records per page")


class SecurityEventFilter(BaseModel):
    """Filters for querying security events."""

    event_type: Optional[str] = Field(default=None, description="Filter by event type")
    severity: Optional[str] = Field(default=None, description="Filter by severity")
    resolved: Optional[bool] = Field(default=None, description="Filter by resolution status")
    user_id: Optional[int] = Field(default=None, description="Filter by user")
    date_from: Optional[datetime] = Field(default=None, description="Start date")
    date_to: Optional[datetime] = Field(default=None, description="End date")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class SecurityEventResolve(BaseModel):
    """Schema for resolving a security event."""

    resolution_note: Optional[str] = Field(default=None, description="Optional resolution note")


# ============================================================================
# Login Attempt Schemas
# ============================================================================


class LoginAttemptBase(BaseModel):
    """Base schema for login attempts."""

    email: str = Field(..., description="Email used for login")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    status: str = Field(..., description="success, failed, or blocked")
    failure_reason: Optional[str] = Field(default=None, description="Reason for failure")


class LoginAttemptCreate(LoginAttemptBase):
    """Schema for creating a login attempt record."""

    company_id: Optional[int] = Field(default=None, description="Tenant company ID")


class LoginAttemptResponse(LoginAttemptBase):
    """Schema for login attempt response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Attempt ID")
    company_id: Optional[int] = Field(default=None, description="Tenant company ID")
    created_at: datetime = Field(..., description="Attempt timestamp")


class LoginAttemptListResponse(BaseModel):
    """Paginated list of login attempts."""

    items: List[LoginAttemptResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Records per page")


class LoginAttemptFilter(BaseModel):
    """Filters for querying login attempts."""

    email: Optional[str] = Field(default=None, description="Filter by email")
    ip_address: Optional[str] = Field(default=None, description="Filter by IP")
    status: Optional[str] = Field(default=None, description="Filter by status")
    date_from: Optional[datetime] = Field(default=None, description="Start date")
    date_to: Optional[datetime] = Field(default=None, description="End date")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ============================================================================
# API Key Schemas
# ============================================================================


class APIKeyBase(BaseModel):
    """Base schema for API keys."""

    name: str = Field(..., min_length=1, max_length=255, description="Key name/label")
    scopes: List[str] = Field(default_factory=list, description="List of permission scopes")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration date")
    is_active: bool = Field(default=True, description="Whether the key is active")


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=255, description="Key name/label")
    scopes: List[str] = Field(default_factory=list, description="List of permission scopes")
    expires_days: Optional[int] = Field(default=365, ge=1, le=1095, description="Days until expiry")


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    scopes: Optional[List[str]] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class APIKeyResponse(APIKeyBase):
    """Schema for API key response (without key_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Key ID")
    company_id: int = Field(..., description="Tenant company ID")
    user_id: int = Field(..., description="Key owner user ID")
    last_used_at: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class APIKeyWithPlainKey(BaseModel):
    """Schema returned once when a new API key is created.

    Contains the plain API key that the user must save immediately.
    """

    id: int = Field(..., description="Key ID")
    name: str = Field(..., description="Key name")
    plain_key: str = Field(..., description="The API key (shown once only)")
    scopes: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(..., description="Creation timestamp")


class APIKeyListResponse(BaseModel):
    """Paginated list of API keys."""

    items: List[APIKeyResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Records per page")


class APIKeyValidateRequest(BaseModel):
    """Schema for validating an API key."""

    api_key: str = Field(..., description="The API key to validate")
    required_scope: Optional[str] = Field(default=None, description="Required scope")


class APIKeyValidationResult(BaseModel):
    """Result of API key validation."""

    valid: bool = Field(..., description="Whether the key is valid")
    company_id: Optional[int] = Field(default=None)
    user_id: Optional[int] = Field(default=None)
    scopes: List[str] = Field(default_factory=list)
    message: Optional[str] = Field(default=None)


# ============================================================================
# Data Access Log Schemas
# ============================================================================


class DataAccessLogBase(BaseModel):
    """Base schema for data access logs."""

    table_name: str = Field(..., description="Database table accessed")
    record_id: str = Field(..., description="ID of accessed record")
    action: str = Field(..., description="read, create, update, or delete")
    accessed_fields: Optional[List[str]] = Field(default=None, description="Fields that were accessed")
    reason: Optional[str] = Field(default=None, description="Business reason for access")


class DataAccessLogCreate(DataAccessLogBase):
    """Schema for creating a data access log."""

    company_id: int = Field(..., description="Tenant company ID")
    user_id: Optional[int] = Field(default=None, description="User who accessed data")


class DataAccessLogResponse(DataAccessLogBase):
    """Schema for data access log response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Log ID")
    company_id: int = Field(..., description="Tenant company ID")
    user_id: Optional[int] = Field(default=None, description="User who accessed data")
    created_at: datetime = Field(..., description="Access timestamp")


class DataAccessLogListResponse(BaseModel):
    """Paginated list of data access logs."""

    items: List[DataAccessLogResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching records")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Records per page")


class DataAccessLogFilter(BaseModel):
    """Filters for querying data access logs."""

    table_name: Optional[str] = Field(default=None, description="Filter by table")
    record_id: Optional[str] = Field(default=None, description="Filter by record ID")
    action: Optional[str] = Field(default=None, description="Filter by action")
    user_id: Optional[int] = Field(default=None, description="Filter by user")
    date_from: Optional[datetime] = Field(default=None, description="Start date")
    date_to: Optional[datetime] = Field(default=None, description="End date")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ============================================================================
# Audit Statistics Schemas
# ============================================================================


class AuditStatsResponse(BaseModel):
    """Summary statistics for the audit dashboard."""

    total_audit_logs: int = Field(..., description="Total audit log entries")
    total_security_events: int = Field(..., description="Total security events")
    open_security_events: int = Field(..., description="Unresolved security events")
    critical_events: int = Field(..., description="Critical severity events")
    high_events: int = Field(..., description="High severity events")
    total_login_attempts_24h: int = Field(..., description="Login attempts in last 24h")
    failed_login_attempts_24h: int = Field(..., description="Failed logins in last 24h")
    active_api_keys: int = Field(..., description="Number of active API keys")
    data_access_logs_24h: int = Field(..., description="Data access logs in last 24h")
    top_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Most frequent actions")
    top_security_events: List[Dict[str, Any]] = Field(default_factory=list, description="Most frequent event types")
    events_by_severity: Dict[str, int] = Field(default_factory=dict, description="Events grouped by severity")
    recent_events: List[SecurityEventResponse] = Field(default_factory=list, description="Most recent events")


class ExportFormat(str, Enum):
    """Supported export formats for audit trail."""

    CSV = "csv"
    JSON = "json"
