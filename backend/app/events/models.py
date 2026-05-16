"""Database models for the Event Bus & Automation module.

Defines seven core tables that power the event-driven architecture:
- event_definitions: Registry of all event types and their schemas
- event_subscriptions: Subscriptions linking events to handlers
- event_log: Immutable log of all events published to the bus
- event_handlers: Individual handler execution records
- dead_letter_events: Failed events moved after retry exhaustion
- automation_rules: Condition-action rules for workflow automation
- automation_executions: Execution audit trail for automation rules
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# EventDefinition
# ---------------------------------------------------------------------------


class EventDefinition(Base):
    """Registry of all event types supported by the platform.

    Each event definition describes the event name, its JSON payload schema,
    and its category (system, business, or integration). System events are
    pre-seeded and cannot be deleted.
    """

    __tablename__ = "event_definitions"
    __table_args__ = {"schema": "public", "comment": "Registry of event types and schemas"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_event_definitions_company_id",
        ),
        nullable=True,
        index=True,
        comment="Null means global/system event definition",
    )
    event_name = Column(
        String(128),
        nullable=False,
        index=True,
        comment="Unique event identifier (e.g. order_created)",
    )
    description = Column(Text, nullable=True)
    payload_schema = Column(
        JSON,
        nullable=True,
        comment="JSON Schema describing the expected payload shape",
    )
    category = Column(
        Enum("system", "business", "integration", name="eventcategory_enum"),
        nullable=False,
        default="system",
        index=True,
    )
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="True for platform-level events that cannot be deleted",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    company = relationship("Company", backref="event_definitions")

    def __repr__(self) -> str:
        return f"<EventDefinition(id={self.id}, event_name='{self.event_name}', category='{self.category}')>"


# ---------------------------------------------------------------------------
# EventSubscription
# ---------------------------------------------------------------------------


class EventSubscription(Base):
    """Subscription records that map event names to handler configurations.

    When an event is published, the event bus queries active subscriptions
    matching the event name and executes each configured handler. Filters
    can be applied so that only payloads matching certain conditions trigger
    the handler.
    """

    __tablename__ = "event_subscriptions"
    __table_args__ = {
        "schema": "public",
        "comment": "Subscriptions linking events to handler configurations",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_event_subscriptions_company_id",
        ),
        nullable=False,
        index=True,
    )
    event_name = Column(
        String(128),
        nullable=False,
        index=True,
        comment="Event name to subscribe to (supports * wildcard)",
    )
    handler_type = Column(
        Enum("webhook", "function", "notification", name="handler_type_enum"),
        nullable=False,
        comment="Type of handler to invoke",
    )
    handler_config = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Handler-specific configuration (URL, function path, etc.)",
    )
    filter_conditions = Column(
        JSON,
        nullable=True,
        comment="Optional JSON filter on payload fields",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    retry_policy = Column(
        JSON,
        nullable=False,
        default=lambda: {"type": "exponential", "max_retries": 5, "delay_seconds": 2},
        comment="Retry configuration for this subscription",
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    company = relationship("Company", backref="event_subscriptions")

    def __repr__(self) -> str:
        return (
            f"<EventSubscription(id={self.id}, event_name='{self.event_name}', "
            f"handler_type='{self.handler_type}', is_active={self.is_active})>"
        )


# ---------------------------------------------------------------------------
# EventLog
# ---------------------------------------------------------------------------


class EventLog(Base):
    """Immutable audit log of every event published to the event bus.

    Each row represents a single event occurrence with its full payload,
    processing status, correlation ID for distributed tracing, and retry
    tracking. This table is the source of truth for event history.
    """

    __tablename__ = "event_log"
    __table_args__ = {
        "schema": "public",
        "comment": "Immutable log of all published events",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_event_log_company_id",
        ),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_event_log_branch_id",
        ),
        nullable=True,
        index=True,
    )
    event_name = Column(
        String(128),
        nullable=False,
        index=True,
    )
    payload = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Full event payload as JSON",
    )
    source_module = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Module that published the event (e.g. erp, ai, social)",
    )
    source_user_id = Column(
        Integer,
        ForeignKey(
            "public.users.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_event_log_source_user_id",
        ),
        nullable=True,
    )
    correlation_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="UUID for tracing related events across services",
    )
    status = Column(
        Enum(
            "pending", "processing", "completed", "failed",
            name="eventlog_status_enum",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    processed_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp when event finished processing",
    )
    error_message = Column(Text, nullable=True)
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    company = relationship("Company", backref="event_logs")
    branch = relationship("Branch", backref="event_logs")
    source_user = relationship("User", backref="published_events")
    handlers = relationship(
        "EventHandler",
        back_populates="event_log",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    dead_letter = relationship(
        "DeadLetterEvent",
        back_populates="event_log",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<EventLog(id={self.id}, event_name='{self.event_name}', "
            f"status='{self.status}', retry_count={self.retry_count})>"
        )


# ---------------------------------------------------------------------------
# EventHandler
# ---------------------------------------------------------------------------


class EventHandler(Base):
    """Execution record for an individual handler invoked for an event.

    Each EventLog can spawn multiple EventHandler rows (one per subscription
    match). This table tracks the lifecycle of each handler execution from
    pending through running to completed or failed.
    """

    __tablename__ = "event_handlers"
    __table_args__ = {
        "schema": "public",
        "comment": "Individual handler execution records",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_log_id = Column(
        Integer,
        ForeignKey(
            "public.event_log.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_event_handlers_event_log_id",
        ),
        nullable=False,
        index=True,
    )
    handler_type = Column(
        Enum("webhook", "function", "notification", name="handler_type_exec_enum"),
        nullable=False,
    )
    handler_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable handler identifier",
    )
    status = Column(
        Enum(
            "pending", "running", "completed", "failed",
            name="handler_status_enum",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    output = Column(
        JSON,
        nullable=True,
        comment="Handler output/response stored as JSON",
    )
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    event_log = relationship("EventLog", back_populates="handlers")

    def __repr__(self) -> str:
        return (
            f"<EventHandler(id={self.id}, handler_name='{self.handler_name}', "
            f"status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# DeadLetterEvent
# ---------------------------------------------------------------------------


class DeadLetterEvent(Base):
    """Dead letter queue for events that failed after all retries.

    When an event handler exhausts its retry policy, the event is moved to
    this table for manual inspection, resolution, or reprocessing. Each row
    preserves the original payload and error context for debugging.
    """

    __tablename__ = "dead_letter_events"
    __table_args__ = {
        "schema": "public",
        "comment": "Dead letter queue for failed events",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_log_id = Column(
        Integer,
        ForeignKey(
            "public.event_log.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_dead_letter_events_event_log_id",
        ),
        nullable=True,  # Can be null for Celery task failures not linked to an event
        index=True,
        unique=True,
    )
    failure_reason = Column(
        Text,
        nullable=False,
        comment="Summary of why the event failed",
    )
    last_error = Column(
        Text,
        nullable=True,
        comment="Last error message or stack trace",
    )
    retry_exhausted_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    original_payload = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Snapshot of the original event payload",
    )
    resolution_status = Column(
        Enum(
            "unresolved", "resolved", "ignored",
            name="resolution_status_enum",
        ),
        nullable=False,
        default="unresolved",
        index=True,
    )
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(
        Integer,
        ForeignKey(
            "public.users.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_dead_letter_events_resolved_by",
        ),
        nullable=True,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    event_log = relationship("EventLog", back_populates="dead_letter")
    resolver = relationship("User", backref="resolved_dead_letters")

    def __repr__(self) -> str:
        return (
            f"<DeadLetterEvent(id={self.id}, event_log_id={self.event_log_id}, "
            f"resolution_status='{self.resolution_status}')>"
        )


# ---------------------------------------------------------------------------
# AutomationRule
# ---------------------------------------------------------------------------


class AutomationRule(Base):
    """User-defined rules that trigger actions when events match conditions.

    Each rule binds to a trigger_event. When an event of that type is
    published, the conditions JSON is evaluated against the payload. If all
    conditions pass, the actions JSON describes what to execute (e.g. send
    notification, call webhook, publish another event).
    """

    __tablename__ = "automation_rules"
    __table_args__ = {
        "schema": "public",
        "comment": "Automation rules: trigger-event -> conditions -> actions",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_automation_rules_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_automation_rules_branch_id",
        ),
        nullable=True,
        index=True,
        comment="Optional: scope rule to a specific branch",
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    trigger_event = Column(
        String(128),
        nullable=False,
        index=True,
        comment="Event name that triggers this rule",
    )
    conditions = Column(
        JSON,
        nullable=False,
        default=list,
        comment="List of condition objects evaluated against payload",
    )
    actions = Column(
        JSON,
        nullable=False,
        default=list,
        comment="List of action objects to execute when conditions match",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    last_triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    company = relationship("Company", backref="automation_rules")
    branch = relationship("Branch", backref="automation_rules")
    executions = relationship(
        "AutomationExecution",
        back_populates="rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AutomationRule(id={self.id}, name='{self.name}', "
            f"trigger_event='{self.trigger_event}', is_active={self.is_active})>"
        )


# ---------------------------------------------------------------------------
# AutomationExecution
# ---------------------------------------------------------------------------


class AutomationExecution(Base):
    """Audit trail for each time an automation rule is evaluated.

    Records when a rule was triggered, whether it completed successfully,
    which actions were executed, and any error that occurred.
    """

    __tablename__ = "automation_executions"
    __table_args__ = {
        "schema": "public",
        "comment": "Execution audit trail for automation rules",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rule_id = Column(
        Integer,
        ForeignKey(
            "public.automation_rules.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_automation_executions_rule_id",
        ),
        nullable=False,
        index=True,
    )
    trigger_event_id = Column(
        Integer,
        ForeignKey(
            "public.event_log.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_automation_executions_trigger_event_id",
        ),
        nullable=True,
        index=True,
        comment="FK to the event_log entry that triggered this execution",
    )
    status = Column(
        Enum(
            "pending", "running", "completed", "failed",
            name="automation_execution_status_enum",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    actions_executed = Column(
        JSON,
        nullable=True,
        comment="Snapshot of actions that were executed and their results",
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    rule = relationship("AutomationRule", back_populates="executions")
    trigger_event = relationship("EventLog", backref="automation_executions")

    def __repr__(self) -> str:
        return (
            f"<AutomationExecution(id={self.id}, rule_id={self.rule_id}, "
            f"status='{self.status}')>"
        )
