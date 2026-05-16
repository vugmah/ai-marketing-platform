"""Internal Admin & Ops Console models - Phase 3."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class SystemStatusSnapshot(Base):
    """Realtime system status snapshots."""
    __tablename__ = "system_status_snapshots"
    __table_args__ = (
        Index("ix_sss_time", "snapshot_at"),
        {"schema": "public", "comment": "System status snapshots"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    overall_health = Column(String(20), nullable=False, default="healthy")
    db_status = Column(String(20), nullable=False, default="ok")
    redis_status = Column(String(20), nullable=False, default="ok")
    queue_status = Column(String(20), nullable=False, default="ok")
    ai_provider_status = Column(String(20), nullable=False, default="ok")
    active_connections = Column(Integer, nullable=False, default=0)
    requests_per_min = Column(Integer, nullable=False, default=0)
    error_rate_pct = Column(Numeric(5, 2), nullable=False, default=0)
    ai_requests_per_min = Column(Integer, nullable=False, default=0)
    ai_cost_per_hour_usd = Column(Numeric(10, 4), nullable=False, default=0)
    snapshot_at = Column(DateTime, server_default=func.now(), nullable=False)


class FailedJobRecovery(Base):
    """Failed job recovery tracking."""
    __tablename__ = "failed_job_recoveries"
    __table_args__ = (
        Index("ix_fjr_job", "job_type", "job_id"),
        Index("ix_fjr_status", "status"),
        {"schema": "public", "comment": "Failed job recovery"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False)  # webhook, ai_request, sync, export
    job_id = Column(String(200), nullable=False)
    company_id = Column(Integer, nullable=True, index=True)
    error_message = Column(Text, nullable=False)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    status = Column(String(20), nullable=False, default="pending")  # pending, retried, recovered, failed
    recovered_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ModerationQueueItem(Base):
    """AI moderation queue."""
    __tablename__ = "moderation_queue"
    __table_args__ = (
        Index("ix_mq_status", "status"),
        Index("ix_mq_company", "company_id"),
        Index("ix_mq_created", "created_at"),
        {"schema": "public", "comment": "AI content moderation queue"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    content_type = Column(String(50), nullable=False)  # ai_response, user_prompt, campaign_text
    content = Column(Text, nullable=False)
    flagged_reason = Column(String(200), nullable=False)
    severity = Column(String(20), nullable=False, default="medium")  # low, medium, high, critical
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected, escalated
    reviewed_by = Column(Integer, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AuditExplorerQuery(Base):
    """Saved audit explorer queries for ops team."""
    __tablename__ = "audit_explorer_queries"
    __table_args__ = (
        Index("ix_aeq_created_by", "created_by"),
        {"schema": "public", "comment": "Saved audit explorer queries"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    query_type = Column(String(50), nullable=False)  # tenant, queue, ai, security, api
    filters = Column(JSON, nullable=False, default=dict)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
