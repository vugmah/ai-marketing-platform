"""ERP integration constants.

Defines entity types, sync intervals, conflict resolution strategies,
retry configuration, and other shared constants for the ERP module.
"""

from enum import Enum
from typing import Dict, List


# ---------------------------------------------------------------------------
# Entity types supported for sync
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    """Entity types that can be synchronized from an ERP system."""

    PRODUCTS = "products"
    INVENTORY = "inventory"
    SALES_ORDERS = "sales_orders"
    CUSTOMERS = "customers"
    INVOICES = "invoices"
    PAYMENTS = "payments"
    ALL = "all"


# All entity types except "all" (the aggregate)
INDIVIDUAL_ENTITY_TYPES: List[str] = [
    EntityType.PRODUCTS.value,
    EntityType.INVENTORY.value,
    EntityType.SALES_ORDERS.value,
    EntityType.CUSTOMERS.value,
    EntityType.INVOICES.value,
    EntityType.PAYMENTS.value,
]


# ---------------------------------------------------------------------------
# Sync intervals (in minutes)
# ---------------------------------------------------------------------------

class SyncInterval(int, Enum):
    """Predefined sync intervals in minutes."""

    REALTIME = 1
    FAST = 5
    NORMAL = 15
    STANDARD = 60
    SLOW = 360
    DAILY = 1440


# Human-readable interval labels
SYNC_INTERVAL_LABELS: Dict[int, str] = {
    SyncInterval.REALTIME: "Real-time (1 min)",
    SyncInterval.FAST: "Fast (5 min)",
    SyncInterval.NORMAL: "Normal (15 min)",
    SyncInterval.STANDARD: "Standard (1 hour)",
    SyncInterval.SLOW: "Slow (6 hours)",
    SyncInterval.DAILY: "Daily (24 hours)",
}


# ---------------------------------------------------------------------------
# Conflict resolution strategies
# ---------------------------------------------------------------------------

class ConflictStrategy(str, Enum):
    """Strategies for resolving sync conflicts."""

    LAST_WRITE_WINS = "last_write_wins"          # Latest timestamp wins
    ERP_WINS = "erp_wins"                        # ERP data always wins
    LOCAL_WINS = "local_wins"                    # Local data always wins
    MERGE = "merge"                              # Merge non-null fields
    MANUAL_REVIEW = "manual_review"              # Flag for manual review


DEFAULT_CONFLICT_STRATEGY = ConflictStrategy.LAST_WRITE_WINS


# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

class RetryConfig:
    """Retry configuration for sync operations."""

    MAX_RETRIES: int = 3
    BASE_DELAY: float = 1.0                       # seconds
    MAX_DELAY: float = 60.0                       # seconds
    EXPONENTIAL_BASE: float = 2.0
    # Delay per attempt: min(BASE_DELAY * EXPONENTIAL_BASE ^ attempt, MAX_DELAY)

    # Per-entity retry overrides
    ENTITY_MAX_RETRIES: Dict[str, int] = {
        "products": 3,
        "inventory": 3,
        "sales_orders": 5,
        "customers": 3,
        "invoices": 5,
        "payments": 3,
    }


# ---------------------------------------------------------------------------
# Sync job defaults
# ---------------------------------------------------------------------------

class SyncJobDefaults:
    """Default values for sync jobs."""

    AUTO_SYNC_INTERVAL_MINUTES: int = 60
    MAX_PAGE_SIZE: int = 1000
    DEFAULT_PAGE_SIZE: int = 100
    MAX_PAGES: int = 100                           # Safety guard
    SYNC_TIMEOUT_SECONDS: int = 3600               # 1 hour


# ---------------------------------------------------------------------------
# Sync status values
# ---------------------------------------------------------------------------

class SyncStatus(str, Enum):
    """High-level sync status values."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    NEVER = "never"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Sync job status
# ---------------------------------------------------------------------------

class SyncJobStatus(str, Enum):
    """Lifecycle status of a sync job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Sync job type
# ---------------------------------------------------------------------------

class SyncJobType(str, Enum):
    """How a sync job was triggered."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"


# ---------------------------------------------------------------------------
# Log level
# ---------------------------------------------------------------------------

class LogLevel(str, Enum):
    """Severity level for sync log entries."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


# ---------------------------------------------------------------------------
# Provider types
# ---------------------------------------------------------------------------

class ProviderType(str, Enum):
    """Supported ERP/external system providers."""

    CUSTOM = "custom"
    ODOO = "odoo"
    SAP = "sap"
    NETSUITE = "netsuite"
    DYNAMICS = "dynamics"
    LOGO = "logo"
    MIKRO = "mikro"
    PARASUT = "parasut"
    ONE_C = "1c"


# List of all provider types
ALL_PROVIDER_TYPES: List[str] = [p.value for p in ProviderType]


# ---------------------------------------------------------------------------
# Webhook event prefixes
# ---------------------------------------------------------------------------

WEBHOOK_EVENT_PREFIXES: List[str] = [
    "product", "inventory", "sales_order", "customer",
    "invoice", "payment",
]


# ---------------------------------------------------------------------------
# Encryption settings
# ---------------------------------------------------------------------------

class EncryptionConfig:
    """Configuration for credential encryption."""

    # Fields that should be encrypted at rest
    ENCRYPTED_FIELDS: List[str] = [
        "api_key",
        "api_secret",
        "oauth_token",
        "oauth_refresh_token",
        "webhook_secret",
    ]

    # Fields that should never be returned in API responses
    SENSITIVE_FIELDS: List[str] = [
        "api_key",
        "api_secret",
        "oauth_token",
        "oauth_token_secret",
        "webhook_secret",
    ]
