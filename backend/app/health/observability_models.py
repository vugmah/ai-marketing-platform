"""Observability Intelligence models - Phase 1."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class EndpointHealthScore(Base):
    """Per-endpoint health scoring with latency/error tracking."""
    __tablename__ = "endpoint_health_scores"
    __table_args__ = (
        Index("ix_ehs_endpoint", "method", "path"),
        Index("ix_ehs_time", "measured_at"),
        Index("ix_ehs_company", "company_id"),
        {"schema": None, "comment": "Endpoint health scoring"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=True, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    avg_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    p95_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    p99_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    error_rate_pct = Column(Numeric(5, 2), nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    health_score = Column(Numeric(5, 2), nullable=False, default=100)
    status = Column(String(20), nullable=False, default="healthy")
    measured_at = Column(DateTime, server_default=func.now(), nullable=False)


class QueueBottleneck(Base):
    """Queue bottleneck analysis."""
    __tablename__ = "queue_bottlenecks"
    __table_args__ = (
        Index("ix_qb_queue", "queue_name"),
        Index("ix_qb_time", "measured_at"),
        {"schema": None, "comment": "Queue bottleneck detection"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_name = Column(String(100), nullable=False)
    depth = Column(Integer, nullable=False, default=0)
    throughput_per_min = Column(Integer, nullable=False, default=0)
    consumer_count = Column(Integer, nullable=False, default=0)
    avg_wait_time_sec = Column(Integer, nullable=False, default=0)
    oldest_message_age_sec = Column(Integer, nullable=False, default=0)
    is_congested = Column(Boolean, nullable=False, default=False)
    bottleneck_severity = Column(String(20), nullable=False, default="none")
    measured_at = Column(DateTime, server_default=func.now(), nullable=False)


class AILatencyAnalytics(Base):
    """AI model latency analytics."""
    __tablename__ = "ai_latency_analytics"
    __table_args__ = (
        Index("ix_ala_model", "model_name"),
        Index("ix_ala_time", "measured_at"),
        Index("ix_ala_company", "company_id"),
        {"schema": None, "comment": "AI latency analytics"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=True, index=True)
    model_name = Column(String(50), nullable=False)
    request_type = Column(String(50), nullable=False)
    avg_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    p95_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    p99_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    token_count = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    timeout_count = Column(Integer, nullable=False, default=0)
    measured_at = Column(DateTime, server_default=func.now(), nullable=False)


class ExternalAPIReliability(Base):
    """External API reliability tracking."""
    __tablename__ = "external_api_reliability"
    __table_args__ = (
        Index("ix_ear_provider", "provider_name"),
        Index("ix_ear_time", "measured_at"),
        {"schema": None, "comment": "External API reliability tracking"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(100), nullable=False)
    endpoint = Column(String(500), nullable=False)
    success_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    timeout_count = Column(Integer, nullable=False, default=0)
    avg_latency_ms = Column(Numeric(10, 2), nullable=False, default=0)
    reliability_score = Column(Numeric(5, 2), nullable=False, default=100)
    status = Column(String(20), nullable=False, default="operational")
    last_error = Column(Text, nullable=True)
    measured_at = Column(DateTime, server_default=func.now(), nullable=False)


class WebhookFailureLog(Base):
    """Webhook failure analytics."""
    __tablename__ = "webhook_failure_logs"
    __table_args__ = (
        Index("ix_wfl_webhook", "webhook_id"),
        Index("ix_wfl_time", "failed_at"),
        {"schema": None, "comment": "Webhook failure tracking"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_id = Column(Integer, nullable=False, index=True)
    webhook_url = Column(String(1000), nullable=False)
    event_type = Column(String(100), nullable=False)
    http_status = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, server_default=func.now(), nullable=False)


class WorkerHealthScore(Base):
    """Celery/Worker health scoring."""
    __tablename__ = "worker_health_scores"
    __table_args__ = (
        Index("ix_wh_worker", "worker_name"),
        Index("ix_wh_time", "measured_at"),
        {"schema": None, "comment": "Worker health scoring"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_name = Column(String(100), nullable=False)
    queue_name = Column(String(100), nullable=False)
    tasks_processed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)
    avg_task_duration_ms = Column(Numeric(10, 2), nullable=False, default=0)
    memory_usage_mb = Column(Integer, nullable=True)
    cpu_usage_pct = Column(Numeric(5, 2), nullable=True)
    health_score = Column(Numeric(5, 2), nullable=False, default=100)
    status = Column(String(20), nullable=False, default="healthy")
    measured_at = Column(DateTime, server_default=func.now(), nullable=False)
