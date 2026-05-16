"""Support Operator Workspace models."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index, Enum
from sqlalchemy.sql import func

from app.database import Base


class SupportTicketOperator(Base):
    """Support tickets with operator assignment."""
    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_st_company", "company_id"),
        Index("ix_st_operator", "assigned_operator_id"),
        Index("ix_st_status", "status"),
        Index("ix_st_priority", "priority"),
        Index("ix_st_sla", "sla_deadline"),
        {"schema": "public", "comment": "Support tickets with operator workspace"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    assigned_operator_id = Column(Integer, nullable=True, index=True)
    supervisor_id = Column(Integer, nullable=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")  # open, assigned, waiting, resolved, closed, escalated
    priority = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    channel = Column(String(30), nullable=False, default="chat")  # chat, email, phone, whatsapp, instagram
    sla_deadline = Column(DateTime, nullable=True)
    first_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    escalation_reason = Column(Text, nullable=True)
    ai_suggested_reply = Column(Text, nullable=True)
    ai_suggestion_used = Column(Boolean, nullable=False, default=False)
    tags = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class OperatorWorkload(Base):
    """Operator workload tracking."""
    __tablename__ = "operator_workloads"
    __table_args__ = (
        Index("ix_ow_operator", "operator_id"),
        {"schema": "public", "comment": "Operator workload and availability"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(Integer, nullable=False, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    active_tickets = Column(Integer, nullable=False, default=0)
    max_capacity = Column(Integer, nullable=False, default=10)
    status = Column(String(20), nullable=False, default="online")  # online, away, offline, busy
    avg_response_time_sec = Column(Integer, nullable=True)
    satisfaction_score = Column(Numeric(3, 2), nullable=True)
    last_assigned_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SupportEscalationRule(Base):
    """Escalation rules for support."""
    __tablename__ = "support_escalation_rules"
    __table_args__ = (
        Index("ix_ser_company", "company_id"),
        {"schema": "public", "comment": "Support escalation rules"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    trigger_condition = Column(String(50), nullable=False)  # sla_breach, priority, manual, ai_confidence
    trigger_value = Column(String(200), nullable=True)
    action = Column(String(50), nullable=False)  # reassign, notify, escalate, auto_close
    target_operator_id = Column(Integer, nullable=True)
    target_supervisor_id = Column(Integer, nullable=True)
    notification_channels = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SupportAnalyticsDaily(Base):
    """Daily support analytics."""
    __tablename__ = "support_analytics_daily"
    __table_args__ = (
        Index("ix_sad_company_date", "company_id", "date"),
        {"schema": "public", "comment": "Daily support analytics"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    date = Column(String(10), nullable=False)
    total_tickets = Column(Integer, nullable=False, default=0)
    resolved_tickets = Column(Integer, nullable=False, default=0)
    avg_resolution_time_min = Column(Integer, nullable=True)
    sla_breach_count = Column(Integer, nullable=False, default=0)
    avg_satisfaction = Column(Numeric(3, 2), nullable=True)
    ai_handled_count = Column(Integer, nullable=False, default=0)
    escalated_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
