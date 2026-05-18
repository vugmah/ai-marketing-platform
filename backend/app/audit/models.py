"""Security audit and compliance models.

Tables:
- audit_logs: Comprehensive audit trail for all CRUD and API operations
- security_events: Detected security anomalies and alerts
- login_attempts: Login success/failure tracking for brute-force detection
- api_keys: Scoped API keys for service-to-service authentication
- data_access_logs: GDPR/KVKK compliance data access records
"""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.database import Base


class AuditAction(str, enum.Enum):
    """Standard audit actions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    API_CALL = "api_call"
    PERMISSION_DENIED = "permission_denied"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    ROLE_CHANGED = "role_changed"
    SETTINGS_CHANGED = "settings_changed"


class ResourceType(str, enum.Enum):
    """Resource types for audit entries."""

    USER = "user"
    COMPANY = "company"
    BRANCH = "branch"
    CAMPAIGN = "campaign"
    AUDIENCE = "audience"
    TEMPLATE = "template"
    ANALYTICS = "analytics"
    INTEGRATION = "integration"
    API_KEY = "api_key"
    SETTINGS = "settings"
    AUTH = "auth"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    NOTIFICATION = "notification"


class SecurityEventType(str, enum.Enum):
    """Security event types."""

    SUSPICIOUS_LOGIN = "suspicious_login"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PERMISSION_DENIED = "permission_denied"
    DATA_EXFILTRATION = "data_exfiltration"
    UNUSUAL_ACTIVITY = "unusual_activity"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    OFF_HOURS_ACCESS = "off_hours_access"
    GEO_ANOMALY = "geo_anomaly"
    TOKEN_REUSE = "token_reuse"
    ACCOUNT_LOCKOUT = "account_lockout"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    TENANT_LEAK = "tenant_leak"
    SECRET_LEAK = "secret_leak"
    XSS_ATTEMPT = "xss_attempt"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"


class SeverityLevel(str, enum.Enum):
    """Severity levels for security events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LoginStatus(str, enum.Enum):
    """Login attempt status."""

    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


class DataAccessAction(str, enum.Enum):
    """Data access actions for compliance logging."""

    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class AuditLog(Base):
    """Comprehensive audit trail for all system operations.

    Tracks every API call and CRUD operation with full context for
    forensic analysis and compliance reporting.
    """

    __tablename__ = "audit_logs"
    __table_args__ = {"schema": None, "comment": "Audit trail for all operations"}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("public.branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action = Column(
        Enum(AuditAction, name="auditaction", create_type=True),
        nullable=False,
        index=True,
    )
    resource_type = Column(
        Enum(ResourceType, name="resourcetype_audit", create_type=True),
        nullable=False,
        index=True,
    )
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)

    # Request context
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)

    # Outcome
    status = Column(String(20), nullable=False, default="success")
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"resource='{self.resource_type}', user={self.user_id}, "
            f"status='{self.status}')>"
        )


class SecurityEvent(Base):
    """Detected security events and anomalies.

    Captures suspicious activities detected by middleware and services
    for security operations review.
    """

    __tablename__ = "security_events"
    __table_args__ = {"schema": None, "comment": "Security events and alerts"}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    event_type = Column(
        Enum(SecurityEventType, name="securityeventtype", create_type=True),
        nullable=False,
        index=True,
    )
    severity = Column(
        Enum(SeverityLevel, name="severitylevel", create_type=True),
        nullable=False,
        index=True,
    )
    description = Column(Text, nullable=False)
    source_ip = Column(String(45), nullable=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details = Column(JSON, nullable=True)

    # Resolution tracking
    resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_by = Column(Integer, ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<SecurityEvent(id={self.id}, type='{self.event_type}', "
            f"severity='{self.severity}', resolved={self.resolved})>"
        )


class LoginAttempt(Base):
    """Individual login attempts for brute-force detection.

    Tracks every login attempt with full context to enable
    pattern analysis and automatic blocking.
    """

    __tablename__ = "login_attempts"
    __table_args__ = {"schema": None, "comment": "Login attempts tracking"}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    email = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(String(500), nullable=True)

    status = Column(
        Enum(LoginStatus, name="loginstatus", create_type=True),
        nullable=False,
        index=True,
    )
    failure_reason = Column(String(255), nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<LoginAttempt(id={self.id}, email='{self.email}', "
            f"status='{self.status}', ip='{self.ip_address}')>"
        )


class APIKey(Base):
    """Scoped API keys for service-to-service authentication.

    API keys are hashed before storage and can be scoped to
    specific resources with expiration dates.
    """

    __tablename__ = "api_keys"
    __table_args__ = {"schema": None, "comment": "Scoped API keys"}

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False)
    scopes = Column(JSON, nullable=False, default=list)

    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<APIKey(id={self.id}, name='{self.name}', "
            f"company={self.company_id}, active={self.is_active})>"
        )


class DataAccessLog(Base):
    """Data access logs for GDPR/KVKK compliance.

    Records every read/create/update/delete operation on sensitive data
    with field-level granularity for data subject access requests.
    """

    __tablename__ = "data_access_logs"
    __table_args__ = {"schema": None, "comment": "Data access logs for compliance"}

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    table_name = Column(String(128), nullable=False, index=True)
    record_id = Column(String(255), nullable=False, index=True)
    action = Column(
        Enum(DataAccessAction, name="dataaccessaction", create_type=True),
        nullable=False,
        index=True,
    )
    accessed_fields = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<DataAccessLog(id={self.id}, table='{self.table_name}', "
            f"record={self.record_id}, action='{self.action}')>"
        )
