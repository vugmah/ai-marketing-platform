"""Incident Management & Recovery models - Phase 5."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class OperationalIncident(Base):
    """Incident tracking."""
    __tablename__ = "operational_incidents"
    __table_args__ = (
        Index("ix_oi_status", "status"),
        Index("ix_oi_severity", "severity"),
        Index("ix_oi_company", "company_id"),
        Index("ix_oi_type", "incident_type"),
        {"comment": "Operational incident tracking"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=True, index=True)
    incident_type = Column(String(50), nullable=False)  # queue_failure, api_outage, ai_outage, db_issue, webhook_failure
    severity = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    affected_services = Column(JSON, nullable=False, default=list)
    affected_company_ids = Column(JSON, nullable=False, default=list)
    root_cause = Column(Text, nullable=True)
    impact_summary = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="open")  # open, investigating, mitigating, resolved, closed
    detected_at = Column(DateTime, server_default=func.now(), nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    assigned_to = Column(Integer, nullable=True)
    playbook_used = Column(String(200), nullable=True)
    auto_recovery_triggered = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class IncidentTimelineEvent(Base):
    """Incident timeline events."""
    __tablename__ = "incident_timeline_events"
    __table_args__ = (
        Index("ix_ite_incident", "incident_id"),
        Index("ix_ite_time", "created_at"),
        {"comment": "Incident timeline events"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("operational_incidents.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # detection, acknowledgment, action, mitigation, resolution
    description = Column(Text, nullable=False)
    performed_by = Column(Integer, nullable=True)
    config_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AutoRecoveryPlaybook(Base):
    """Auto-recovery playbooks."""
    __tablename__ = "auto_recovery_playbooks"
    __table_args__ = (
        Index("ix_arb_type", "incident_type"),
        {"comment": "Auto-recovery playbooks"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_type = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    trigger_condition = Column(String(500), nullable=False)
    actions = Column(JSON, nullable=False, default=list)
    max_auto_attempts = Column(Integer, nullable=False, default=3)
    cooldown_sec = Column(Integer, nullable=False, default=300)
    notify_channels = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
