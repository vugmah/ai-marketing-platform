"""Constants for the Event Bus & Automation module.

Defines all system and business event types, retry policies,
and category-specific configuration used across the events module.
"""

from enum import Enum
from typing import Dict, List

# ---------------------------------------------------------------------------
# Event Categories
# ---------------------------------------------------------------------------


class EventCategory(str, Enum):
    """Event classification categories."""

    SYSTEM = "system"
    BUSINESS = "business"
    INTEGRATION = "integration"


# ---------------------------------------------------------------------------
# Event Log Status
# ---------------------------------------------------------------------------


class EventLogStatus(str, Enum):
    """Lifecycle statuses for event log entries."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Handler Status
# ---------------------------------------------------------------------------


class HandlerStatus(str, Enum):
    """Execution statuses for event handlers."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Handler Types
# ---------------------------------------------------------------------------


class HandlerType(str, Enum):
    """Supported event handler types."""

    WEBHOOK = "webhook"
    FUNCTION = "function"
    NOTIFICATION = "notification"


# ---------------------------------------------------------------------------
# Dead Letter Resolution Status
# ---------------------------------------------------------------------------


class ResolutionStatus(str, Enum):
    """Resolution states for dead letter events."""

    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IGNORED = "ignored"


# ---------------------------------------------------------------------------
# Automation Execution Status
# ---------------------------------------------------------------------------


class AutomationExecutionStatus(str, Enum):
    """Execution statuses for automation rule runs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Retry Policy Types
# ---------------------------------------------------------------------------


class RetryPolicyType(str, Enum):
    """Retry backoff strategies."""

    IMMEDIATE = "immediate"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


# ---------------------------------------------------------------------------
# System Event Types
# ---------------------------------------------------------------------------

SYSTEM_EVENT_TYPES: List[str] = [
    # Auth events
    "user_registered",
    "user_login",
    "user_logout",
    # Company events
    "company_created",
    "company_updated",
    # Branch events
    "branch_created",
    "branch_updated",
    # ERP sync events
    "erp_sync_started",
    "erp_sync_completed",
    "erp_sync_failed",
    # Order & inventory events
    "order_created",
    "review_received",
    # Campaign events
    "campaign_created",
    "campaign_updated",
    # Payment events
    "inventory_low",
    "payment_received",
    "subscription_changed",
    # AI & content events
    "ai_request_completed",
    # Social & media events
    "social_post_published",
    "media_uploaded",
]

# ---------------------------------------------------------------------------
# Business Event Types
# ---------------------------------------------------------------------------

BUSINESS_EVENT_TYPES: List[str] = [
    "content_generated",
    "suggestion_applied",
    "recommendation_dismissed",
    "report_generated",
]

# ---------------------------------------------------------------------------
# All Event Types (combined)
# ---------------------------------------------------------------------------

ALL_EVENT_TYPES: List[str] = SYSTEM_EVENT_TYPES + BUSINESS_EVENT_TYPES

# ---------------------------------------------------------------------------
# Retry Policies Configuration
# ---------------------------------------------------------------------------

RETRY_POLICIES: Dict[str, Dict[str, int]] = {
    RetryPolicyType.IMMEDIATE: {
        "max_retries": 3,
        "delay_seconds": 1,
        "multiplier": 1,
    },
    RetryPolicyType.LINEAR: {
        "max_retries": 5,
        "delay_seconds": 5,
        "multiplier": 1,
    },
    RetryPolicyType.EXPONENTIAL: {
        "max_retries": 5,
        "delay_seconds": 2,
        "multiplier": 2,
    },
}

# ---------------------------------------------------------------------------
# Category-specific Max Retry Counts
# ---------------------------------------------------------------------------

CATEGORY_MAX_RETRIES: Dict[str, int] = {
    EventCategory.SYSTEM: 5,
    EventCategory.BUSINESS: 3,
    EventCategory.INTEGRATION: 7,
}

# ---------------------------------------------------------------------------
# Default Retry Policy per Category
# ---------------------------------------------------------------------------

DEFAULT_RETRY_POLICY: Dict[str, str] = {
    EventCategory.SYSTEM: RetryPolicyType.EXPONENTIAL,
    EventCategory.BUSINESS: RetryPolicyType.LINEAR,
    EventCategory.INTEGRATION: RetryPolicyType.EXPONENTIAL,
}

# ---------------------------------------------------------------------------
# Redis Channel Prefix
# ---------------------------------------------------------------------------

REDIS_CHANNEL_PREFIX = "events:channel"
EVENT_BUS_CONSUMER_GROUP = "event_bus:consumers"

# ---------------------------------------------------------------------------
# Webhook Defaults
# ---------------------------------------------------------------------------

WEBHOOK_DEFAULT_TIMEOUT_SECONDS = 30
WEBHOOK_MAX_RETRIES = 5
WEBHOOK_SIGNATURE_HEADER = "X-Event-Signature"
WEBHOOK_VERSION_HEADER = "X-Event-Version"
WEBHOOK_VERSION = "v2"

# ---------------------------------------------------------------------------
# Event Batching
# ---------------------------------------------------------------------------

EVENT_BATCH_SIZE = 100
EVENT_BATCH_FLUSH_INTERVAL_SECONDS = 5

# ---------------------------------------------------------------------------
# Automation
# ---------------------------------------------------------------------------

AUTOMATION_MAX_ACTIONS_PER_EXECUTION = 10
AUTOMATION_MAX_CONDITION_DEPTH = 5
