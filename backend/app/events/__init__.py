"""Event Bus & Automation module for the AI Marketing Platform.

This module provides a complete event-driven architecture including:
- Redis pub/sub based event bus for async event propagation
- Event logging, subscriptions, and handler management
- Dead letter queue for failed events with retry and resolution workflows
- Automation rules engine for trigger-based workflows
- Webhook delivery with signature verification and retry logic
"""

from app.events.bus import EventBus, EventBusMiddleware, get_event_bus
from app.events.constants import (
    BUSINESS_EVENT_TYPES,
    RETRY_POLICIES,
    SYSTEM_EVENT_TYPES,
)
from app.events.models import (
    AutomationExecution,
    AutomationRule,
    DeadLetterEvent,
    EventDefinition,
    EventHandler,
    EventLog,
    EventSubscription,
)
from app.events.service import (
    AutomationRuleService,
    DeadLetterService,
    EventHandlerService,
    EventLogService,
    EventSubscriptionService,
    WebhookDeliveryService,
)

__all__ = [
    # Bus
    "EventBus",
    "EventBusMiddleware",
    "get_event_bus",
    # Constants
    "SYSTEM_EVENT_TYPES",
    "BUSINESS_EVENT_TYPES",
    "RETRY_POLICIES",
    # Models
    "EventDefinition",
    "EventSubscription",
    "EventLog",
    "EventHandler",
    "DeadLetterEvent",
    "AutomationRule",
    "AutomationExecution",
    # Services
    "EventLogService",
    "EventSubscriptionService",
    "EventHandlerService",
    "DeadLetterService",
    "AutomationRuleService",
    "WebhookDeliveryService",
]

# Import Celery tasks for autodiscovery
from app.events import tasks as events_tasks
