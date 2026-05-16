"""Pydantic schemas for realtime WebSocket messages.

Defines all inbound/outbound message types for the WebSocket gateway,
including subscription control, heartbeat, and typed event payloads.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WSMessageType(str, Enum):
    """Inbound message types from client → server."""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    ACK = "ack"


class WSOutboundType(str, Enum):
    """Outbound message types from server → client."""

    # System
    WELCOME = "welcome"
    PONG = "pong"
    ERROR = "error"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"

    # Business events
    NOTIFICATION = "notification"
    DASHBOARD_UPDATE = "dashboard_update"
    SUPPORT_MESSAGE = "support_message"
    ALERT = "alert"
    EVENT = "event"


class SubscriptionChannel(str, Enum):
    """Available subscription channels for scoped realtime updates."""

    NOTIFICATIONS = "notifications"
    DASHBOARD = "dashboard"
    SUPPORT_INBOX = "support_inbox"
    ALERTS = "alerts"
    EVENTS = "events"
    ALL = "all"


# ---------------------------------------------------------------------------
# Inbound (Client → Server)
# ---------------------------------------------------------------------------


class SubscribeMessage(BaseModel):
    """Client subscription request."""

    type: str = Field(default=WSMessageType.SUBSCRIBE)
    channel: SubscriptionChannel = Field(
        ..., description="Channel to subscribe to"
    )
    branch_id: Optional[int] = Field(
        default=None, description="Optional branch-scoped filter"
    )


class UnsubscribeMessage(BaseModel):
    """Client unsubscription request."""

    type: str = Field(default=WSMessageType.UNSUBSCRIBE)
    channel: SubscriptionChannel = Field(
        ..., description="Channel to unsubscribe from"
    )


class PingMessage(BaseModel):
    """Client heartbeat ping."""

    type: str = Field(default=WSMessageType.PING)
    timestamp: Optional[float] = Field(
        default=None, description="Client timestamp for latency calc"
    )


class AckMessage(BaseModel):
    """Client acknowledgment for reliable delivery."""

    type: str = Field(default=WSMessageType.ACK)
    message_id: str = Field(..., description="ID of the acknowledged message")


# ---------------------------------------------------------------------------
# Outbound (Server → Client)
# ---------------------------------------------------------------------------


class WelcomePayload(BaseModel):
    """Sent immediately after successful WebSocket connection + auth."""

    connection_id: str
    user_id: int
    company_id: Optional[int] = None
    subscribed_channels: List[str] = Field(default_factory=list)
    server_time: float
    message: str = "Connected to realtime gateway"


class PongPayload(BaseModel):
    """Server heartbeat response."""

    server_time: float
    client_time: Optional[float] = None


class ErrorPayload(BaseModel):
    """Server error response."""

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SubscribedPayload(BaseModel):
    """Subscription confirmation."""

    channel: str
    branch_id: Optional[int] = None
    message: str


class UnsubscribedPayload(BaseModel):
    """Unsubscription confirmation."""

    channel: str
    message: str


class NotificationPayload(BaseModel):
    """Realtime notification pushed to client."""

    id: str
    type: str
    title: str
    message: str
    is_read: bool = False
    created_at: str
    metadata: Optional[Dict[str, Any]] = None


class DashboardKPIPayload(BaseModel):
    """Live dashboard KPI update."""

    metric_name: str
    metric_value: float
    previous_value: Optional[float] = None
    change_percent: Optional[float] = None
    branch_id: Optional[int] = None
    timestamp: str

    @model_validator(mode="after")
    def compute_change_percent(self) -> "DashboardKPIPayload":
        """Auto-compute change_percent when previous_value is set."""
        if self.previous_value is not None and self.previous_value != 0:
            self.change_percent = round(
                ((self.metric_value - self.previous_value) / abs(self.previous_value)) * 100,
                2,
            )
        return self


class DashboardUpdatePayload(BaseModel):
    """Batch dashboard update with multiple KPIs."""

    kpis: List[DashboardKPIPayload]
    branch_id: Optional[int] = None
    timestamp: str


class SupportMessagePayload(BaseModel):
    """New support message pushed to inbox subscribers."""

    ticket_id: str
    message_id: str
    sender_type: str  # "user" | "agent" | "ai"
    sender_name: str
    content: str
    timestamp: str
    branch_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class AlertPayload(BaseModel):
    """Realtime threshold alert."""

    alert_id: str
    severity: str  # "critical" | "warning" | "info"
    alert_type: str  # e.g. "threshold_exceeded", "inventory_low"
    title: str
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    branch_id: Optional[int] = None
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class EventPayload(BaseModel):
    """Generic event forwarded from the event bus."""

    event_name: str
    payload: Dict[str, Any]
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    source_module: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: str


# ---------------------------------------------------------------------------
# Unified outbound envelope
# ---------------------------------------------------------------------------


class WSOutboundMessage(BaseModel):
    """Every outbound message is wrapped in a typed envelope.

    This provides a uniform protocol so clients can switch on `msg_type`
    and parse `payload` accordingly.
    """

    msg_type: WSOutboundType
    message_id: str
    timestamp: float
    payload: Dict[str, Any] = Field(default_factory=dict)
