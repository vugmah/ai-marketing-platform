"""Release & Rollout Management models - Phase 2."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class FeatureFlag(Base):
    """Feature flags for staged rollout."""
    __tablename__ = "feature_flags"
    __table_args__ = (
        Index("ix_ff_key", "flag_key"),
        Index("ix_ff_company", "company_id"),
        {"comment": "Feature flags for tenant-based rollout", "extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    flag_key = Column(String(100), nullable=False)
    flag_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    rollout_pct = Column(Numeric(5, 2), nullable=False, default=0)
    target_branches = Column(JSON, nullable=False, default=list)
    target_roles = Column(JSON, nullable=False, default=list)
    dependencies = Column(JSON, nullable=False, default=list)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class RolloutCohort(Base):
    """Beta cohort management."""
    __tablename__ = "rollout_cohorts"
    __table_args__ = (
        Index("ix_rc_name", "name"),
        Index("ix_rc_company", "company_id"),
        {"extend_existing": True, "comment": "Beta rollout cohorts"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    cohort_type = Column(String(20), nullable=False, default="beta")  # beta, canary, ab
    description = Column(Text, nullable=True)
    branch_ids = Column(JSON, nullable=False, default=list)
    user_ids = Column(JSON, nullable=False, default=list)
    percentage = Column(Numeric(5, 2), nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ReleaseNote(Base):
    """Release notes."""
    __tablename__ = "release_notes"
    __table_args__ = (
        Index("ix_rn_version", "version"),
        Index("ix_rn_company", "company_id"),
        {"extend_existing": True, "comment": "Release notes per version"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=True, index=True)
    version = Column(String(20), nullable=False)
    change_type = Column(String(20), nullable=False)  # feature, fix, improvement, breaking
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    affected_modules = Column(JSON, nullable=False, default=list)
    migration_required = Column(Boolean, nullable=False, default=False)
    published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class RolloutEvent(Base):
    """Rollout event tracking."""
    __tablename__ = "rollout_events"
    __table_args__ = (
        Index("ix_re_flag", "flag_id"),
        Index("ix_re_time", "created_at"),
        {"extend_existing": True, "comment": "Rollout event log"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    flag_id = Column(Integer, ForeignKey("feature_flags.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # enable, disable, pct_change, rollback
    old_value = Column(String(200), nullable=True)
    new_value = Column(String(200), nullable=True)
    performed_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
