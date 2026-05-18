"""Multi-Tenant Resource Governance models - Phase 3."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class TenantResourceQuota(Base):
    """Per-tenant resource quotas."""
    __tablename__ = "tenant_resource_quotas"
    __table_args__ = (
        Index("ix_trq_company", "company_id", unique=True),
        {"schema": None, "comment": "Per-tenant resource quotas"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    max_ai_tokens_per_hour = Column(Integer, nullable=False, default=100000)
    max_ai_tokens_per_day = Column(Integer, nullable=False, default=1000000)
    max_queue_jobs_per_hour = Column(Integer, nullable=False, default=10000)
    max_redis_memory_mb = Column(Integer, nullable=False, default=512)
    max_celery_workers = Column(Integer, nullable=False, default=5)
    max_webhook_calls_per_min = Column(Integer, nullable=False, default=60)
    max_storage_mb = Column(Integer, nullable=False, default=10240)
    max_branches = Column(Integer, nullable=False, default=10)
    max_users = Column(Integer, nullable=False, default=50)
    throttling_enabled = Column(Boolean, nullable=False, default=True)
    noisy_neighbor_protection = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TenantResourceUsage(Base):
    """Per-tenant real-time resource usage."""
    __tablename__ = "tenant_resource_usage"
    __table_args__ = (
        Index("ix_tru_company_time", "company_id", "measured_at"),
        {"schema": None, "comment": "Tenant resource usage snapshots"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    ai_tokens_used_hour = Column(Integer, nullable=False, default=0)
    ai_tokens_used_day = Column(Integer, nullable=False, default=0)
    queue_jobs_processed_hour = Column(Integer, nullable=False, default=0)
    redis_memory_used_mb = Column(Integer, nullable=False, default=0)
    active_celery_workers = Column(Integer, nullable=False, default=0)
    webhook_calls_min = Column(Integer, nullable=False, default=0)
    storage_used_mb = Column(Integer, nullable=False, default=0)
    throttled_events_count = Column(Integer, nullable=False, default=0)
    quota_violations = Column(Integer, nullable=False, default=0)
    measured_at = Column(DateTime, server_default=func.now(), nullable=False)


class BranchResourceQuota(Base):
    """Per-branch resource quotas."""
    __tablename__ = "branch_resource_quotas"
    __table_args__ = (
        Index("ix_brq_branch", "branch_id", unique=True),
        {"schema": None, "comment": "Per-branch resource quotas"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False, index=True)
    max_ai_tokens_per_hour = Column(Integer, nullable=False, default=10000)
    max_concurrent_jobs = Column(Integer, nullable=False, default=5)
    max_webhook_calls_per_min = Column(Integer, nullable=False, default=10)
    priority_weight = Column(Integer, nullable=False, default=1)
    worker_queue_prefix = Column(String(50), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
