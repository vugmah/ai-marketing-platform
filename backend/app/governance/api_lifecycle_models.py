"""API Lifecycle & Versioning models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class APIVersionPolicy(Base):
    """API version policy configuration per company."""
    __tablename__ = "api_version_policies"
    __table_args__ = (
        Index("ix_avp_company", "company_id"),
        {"schema": "public", "comment": "API version policy per company"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    current_version = Column(String(10), nullable=False, default="v2")
    min_supported_version = Column(String(10), nullable=False, default="v2")
    deprecation_notice_days = Column(Integer, nullable=False, default=90)
    breaking_change_notification = Column(Boolean, nullable=False, default=True)
    auto_add_headers = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class APIEndpointLifecycle(Base):
    """Lifecycle tracking for individual API endpoints."""
    __tablename__ = "api_endpoint_lifecycles"
    __table_args__ = (
        Index("ix_ael_endpoint", "method", "path"),
        Index("ix_ael_status", "lifecycle_status"),
        Index("ix_ael_company", "company_id"),
        {"schema": "public", "comment": "API endpoint lifecycle metadata"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=True, index=True)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    path = Column(String(500), nullable=False)
    version = Column(String(10), nullable=False, default="v2")
    lifecycle_status = Column(String(20), nullable=False, default="stable")  # stable, deprecated, experimental, sunset
    introduced_at = Column(DateTime, nullable=False, server_default=func.now())
    deprecated_at = Column(DateTime, nullable=True)
    sunset_at = Column(DateTime, nullable=True)
    removal_version = Column(String(10), nullable=True)
    alternative_endpoint = Column(String(500), nullable=True)
    breaking_changes = Column(JSON, nullable=False, default=list)
    migration_guide = Column(Text, nullable=True)
    notification_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class APIChangelogEntry(Base):
    """API changelog entries."""
    __tablename__ = "api_changelog"
    __table_args__ = (
        Index("ix_acl_version", "version"),
        Index("ix_acl_company", "company_id"),
        {"schema": "public", "comment": "API changelog entries"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=True, index=True)
    version = Column(String(10), nullable=False)
    change_type = Column(String(20), nullable=False)  # added, changed, deprecated, removed, fixed
    endpoint = Column(String(500), nullable=True)
    description = Column(Text, nullable=False)
    migration_required = Column(Boolean, nullable=False, default=False)
    migration_steps = Column(Text, nullable=True)
    announced_at = Column(DateTime, server_default=func.now(), nullable=False)
    effective_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class APIContractSnapshot(Base):
    """API contract snapshots for drift detection."""
    __tablename__ = "api_contract_snapshots"
    __table_args__ = (
        Index("ix_acs_endpoint", "endpoint_id"),
        {"schema": "public", "comment": "API contract snapshots for drift detection"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_id = Column(Integer, ForeignKey("public.api_endpoint_lifecycles.id"), nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    request_schema = Column(JSON, nullable=True)
    response_schema = Column(JSON, nullable=True)
    query_params = Column(JSON, nullable=True)
    headers = Column(JSON, nullable=True)
    snapshot_at = Column(DateTime, server_default=func.now(), nullable=False)
