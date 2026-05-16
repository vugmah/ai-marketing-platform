"""Pydantic v2 schemas for the Event Bus & Automation module.

Provides request and response models for all CRUD operations across:
- Event definitions
- Event subscriptions
- Event log
- Dead letter events
- Automation rules
- Automation executions
- Event statistics
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared Schemas
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel):
    """Paginated list response wrapper."""

    model_config = ConfigDict(from_attributes=True)

    total: int = Field(..., description="Total number of matching records")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    items: List[Any] = Field(default_factory=list)


class EventStatsResponse(BaseModel):
    """Event statistics summary response."""

    model_config = ConfigDict(from_attributes=True)

    total_events: int = Field(..., description="Total events in the selected period")
    total_by_status: Dict[str, int] = Field(default_factory=dict)
    total_by_event_name: Dict[str, int] = Field(default_factory=dict)
    total_failed: int = Field(0)
    total_dead_letter: int = Field(0)
    total_automation_rules_triggered: int = Field(0)
    total_webhooks_delivered: int = Field(0)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# ---------------------------------------------------------------------------
# EventDefinition Schemas
# ---------------------------------------------------------------------------


class EventDefinitionBase(BaseModel):
    """Base fields for event definitions."""

    event_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    payload_schema: Optional[Dict[str, Any]] = None
    category: str = Field(default="system")
    is_system: bool = Field(default=False)


class EventDefinitionCreate(EventDefinitionBase):
    """Schema for creating an event definition."""

    company_id: Optional[int] = None


class EventDefinitionUpdate(BaseModel):
    """Schema for updating an event definition."""

    event_name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = None
    payload_schema: Optional[Dict[str, Any]] = None
    category: Optional[str] = None


class EventDefinitionResponse(EventDefinitionBase):
    """Schema for event definition responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: Optional[int] = None
    created_at: datetime


class EventDefinitionListResponse(PaginatedResponse):
    """Schema for listing event definitions."""

    items: List[EventDefinitionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# EventSubscription Schemas
# ---------------------------------------------------------------------------


class EventSubscriptionBase(BaseModel):
    """Base fields for event subscriptions."""

    event_name: str = Field(..., min_length=1, max_length=128)
    handler_type: str = Field(...)
    handler_config: Dict[str, Any] = Field(default_factory=dict)
    filter_conditions: Optional[Dict[str, Any]] = None
    is_active: bool = Field(default=True)
    retry_policy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "exponential",
            "max_retries": 5,
            "delay_seconds": 2,
        }
    )


class EventSubscriptionCreate(EventSubscriptionBase):
    """Schema for creating an event subscription."""

    company_id: int


class EventSubscriptionUpdate(BaseModel):
    """Schema for updating an event subscription."""

    event_name: Optional[str] = Field(default=None, max_length=128)
    handler_type: Optional[str] = None
    handler_config: Optional[Dict[str, Any]] = None
    filter_conditions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    retry_policy: Optional[Dict[str, Any]] = None


class EventSubscriptionResponse(EventSubscriptionBase):
    """Schema for event subscription responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime


class EventSubscriptionListResponse(PaginatedResponse):
    """Schema for listing event subscriptions."""

    items: List[EventSubscriptionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# EventLog Schemas
# ---------------------------------------------------------------------------


class EventHandlerResponse(BaseModel):
    """Schema for event handler execution responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    handler_type: str
    handler_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    retry_count: int = 0


class EventLogBase(BaseModel):
    """Base fields for event log entries."""

    event_name: str = Field(..., min_length=1, max_length=128)
    payload: Dict[str, Any] = Field(default_factory=dict)
    source_module: Optional[str] = Field(default=None, max_length=64)
    source_user_id: Optional[int] = None
    correlation_id: Optional[str] = Field(default=None, max_length=64)


class EventLogCreate(EventLogBase):
    """Schema for creating an event log entry."""

    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    status: Optional[str] = "pending"


class EventLogUpdate(BaseModel):
    """Schema for updating an event log entry."""

    status: Optional[str] = None
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None


class EventLogResponse(EventLogBase):
    """Schema for event log responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    status: str
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    handlers: List[EventHandlerResponse] = Field(default_factory=list)


class EventLogListResponse(PaginatedResponse):
    """Schema for listing event log entries."""

    items: List[EventLogResponse] = Field(default_factory=list)


class EventRetryRequest(BaseModel):
    """Schema for retrying a failed event."""

    force_immediate: bool = Field(
        default=False,
        description="If True, retry immediately without waiting",
    )


class EventRetryResponse(BaseModel):
    """Schema for event retry responses."""

    success: bool
    message: str
    event_log_id: int


# ---------------------------------------------------------------------------
# DeadLetterEvent Schemas
# ---------------------------------------------------------------------------


class DeadLetterEventBase(BaseModel):
    """Base fields for dead letter events."""

    failure_reason: str
    last_error: Optional[str] = None
    original_payload: Dict[str, Any] = Field(default_factory=dict)
    resolution_status: str = Field(default="unresolved")


class DeadLetterEventCreate(DeadLetterEventBase):
    """Schema for creating a dead letter event."""

    event_log_id: int
    resolved_by: Optional[int] = None


class DeadLetterEventResponse(DeadLetterEventBase):
    """Schema for dead letter event responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_log_id: int
    retry_exhausted_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    created_at: datetime
    event_log: Optional[EventLogResponse] = None


class DeadLetterEventListResponse(PaginatedResponse):
    """Schema for listing dead letter events."""

    items: List[DeadLetterEventResponse] = Field(default_factory=list)


class DeadLetterResolveRequest(BaseModel):
    """Schema for resolving a dead letter event."""

    resolution: str = Field(..., description="Resolution action: resolved or ignored")
    note: Optional[str] = None


class DeadLetterResolveResponse(BaseModel):
    """Schema for dead letter resolution responses."""

    success: bool
    message: str
    dead_letter_id: int
    resolution_status: str


class DeadLetterRetryResponse(BaseModel):
    """Schema for dead letter retry responses."""

    success: bool
    message: str
    dead_letter_id: int
    new_event_log_id: Optional[int] = None


# ---------------------------------------------------------------------------
# AutomationRule Schemas
# ---------------------------------------------------------------------------


class AutomationRuleBase(BaseModel):
    """Base fields for automation rules."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_event: str = Field(..., min_length=1, max_length=128)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    is_active: bool = Field(default=True)


class AutomationRuleCreate(AutomationRuleBase):
    """Schema for creating an automation rule."""

    company_id: int
    branch_id: Optional[int] = None


class AutomationRuleUpdate(BaseModel):
    """Schema for updating an automation rule."""

    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    trigger_event: Optional[str] = Field(default=None, max_length=128)
    conditions: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


class AutomationRuleResponse(AutomationRuleBase):
    """Schema for automation rule responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    created_at: datetime
    updated_at: datetime


class AutomationRuleListResponse(PaginatedResponse):
    """Schema for listing automation rules."""

    items: List[AutomationRuleResponse] = Field(default_factory=list)


class AutomationRuleToggleResponse(BaseModel):
    """Schema for toggling an automation rule."""

    success: bool
    rule_id: int
    is_active: bool
    message: str


# ---------------------------------------------------------------------------
# AutomationExecution Schemas
# ---------------------------------------------------------------------------


class AutomationExecutionBase(BaseModel):
    """Base fields for automation executions."""

    status: str = Field(default="pending")
    actions_executed: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None


class AutomationExecutionCreate(AutomationExecutionBase):
    """Schema for creating an automation execution record."""

    rule_id: int
    trigger_event_id: Optional[int] = None


class AutomationExecutionResponse(AutomationExecutionBase):
    """Schema for automation execution responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    trigger_event_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class AutomationExecutionListResponse(PaginatedResponse):
    """Schema for listing automation executions."""

    items: List[AutomationExecutionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Webhook Delivery Schemas
# ---------------------------------------------------------------------------


class WebhookDeliveryRequest(BaseModel):
    """Schema for requesting a webhook delivery."""

    url: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    headers: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = 30
    signature_secret: Optional[str] = None


class WebhookDeliveryResponse(BaseModel):
    """Schema for webhook delivery responses."""

    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    delivery_time_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Event Publish Schemas
# ---------------------------------------------------------------------------


class EventPublishRequest(BaseModel):
    """Schema for publishing an event to the event bus."""

    event_name: str = Field(..., min_length=1, max_length=128)
    payload: Dict[str, Any] = Field(default_factory=dict)
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    source_module: Optional[str] = Field(default=None, max_length=64)
    correlation_id: Optional[str] = None


class EventPublishResponse(BaseModel):
    """Schema for event publish responses."""

    success: bool
    event_log_id: Optional[int] = None
    correlation_id: str
    message: str
