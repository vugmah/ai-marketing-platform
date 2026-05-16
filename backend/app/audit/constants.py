"""Security audit constants: event types, severity levels, thresholds, headers."""

from enum import Enum


class AuditAction(str, Enum):
    """Standard audit actions for CRUD operations."""

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


class ResourceType(str, Enum):
    """Resource types that can be audited."""

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


class SecurityEventType(str, Enum):
    """Types of security events that can be triggered."""

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


class SeverityLevel(str, Enum):
    """Severity levels for security events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LoginStatus(str, Enum):
    """Possible statuses for login attempts."""

    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    MFA_REQUIRED = "mfa_required"


class APIKeyScope(str, Enum):
    """Valid scopes for API keys."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_WRITE = "analytics:write"
    CAMPAIGNS_READ = "campaigns:read"
    CAMPAIGNS_WRITE = "campaigns:write"
    CAMPAIGNS_DELETE = "campaigns:delete"
    AUDIENCE_READ = "audience:read"
    AUDIENCE_WRITE = "audience:write"
    AUDIENCE_IMPORT = "audience:import"
    AUDIENCE_EXPORT = "audience:export"
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# Security Headers (recommended production values)
# ---------------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: https: blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https: wss:; "
        "media-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "accelerometer=(), "
        "camera=(), "
        "geolocation=(), "
        "gyroscope=(), "
        "magnetometer=(), "
        "microphone=(), "
        "payment=(), "
        "usb=()"
    ),
    "X-Permitted-Cross-Domain-Policies": "none",
    "X-Download-Options": "noopen",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}

# ---------------------------------------------------------------------------
# Suspicious Activity Thresholds
# ---------------------------------------------------------------------------

# Request rate thresholds per time window (window_seconds, max_requests)
RAPID_REQUEST_THRESHOLD = (60, 120)       # 120 requests per minute
BURST_REQUEST_THRESHOLD = (10, 30)         # 30 requests per 10 seconds

# Off-hours: outside 06:00-22:00 in company's timezone
OFF_HOURS_START = 22
OFF_HOURS_END = 6

# Failed login thresholds for brute force detection
BRUTE_FORCE_WINDOW_SECONDS = 300           # 5 minute window
BRUTE_FORCE_MAX_ATTEMPTS = 5               # 5 failed attempts
BRUTE_FORCE_BLOCK_DURATION_SECONDS = 1800  # 30 minute block
BRUTE_FORCE_ACCOUNT_LOCKOUT_THRESHOLD = 10  # Lock account after 10 failures

# Geo anomaly: detect logins from new countries within short time windows
GEO_ANOMALY_WINDOW_HOURS = 1
GEO_ANOMALY_MAX_COUNTRIES = 2

# Data exfiltration thresholds
DATA_EXFILTRATION_RECORD_THRESHOLD = 1000   # Flag exports > 1000 records
DATA_EXFILTRATION_SIZE_THRESHOLD_MB = 50    # Flag exports > 50 MB

# Tenant leak detection
TENANT_LEAK_MAX_SAMPLE_SIZE = 100           # Check up to 100 items in response
TENANT_LEAK_FIELD_PATTERNS = [              # JSON keys that might contain tenant IDs
    "company_id",
    "tenant_id",
    "organization_id",
    "branch_id",
]

# Token reuse detection
TOKEN_REUSE_WINDOW_SECONDS = 10             # Same token used within 10 seconds

# Secret scanning patterns (basic detection for common leaks)
SECRET_PATTERNS = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret_key": r"[0-9a-zA-Z/+]{40}",
    "github_token": r"gh[pousr]_[A-Za-z0-9_]{36,}",
    "slack_token": r"xox[baprs]-[0-9a-zA-Z-]+",
    "generic_api_key": r"[aA][pP][iI][-_]?[kK][eE][yY][\s]*[:=][\s]*['\"][a-zA-Z0-9]{16,}['\"]",
    "private_key": r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "jwt_token": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
    "password_in_url": r"[a-zA-Z0-9]+://[^:]+:[^@]+@",
}

# Upload validation limits
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024     # 10 MB
ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".json", ".png", ".jpg", ".jpeg", ".pdf", ".txt"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "image/png",
    "image/jpeg",
    "application/pdf",
    "text/plain",
}
