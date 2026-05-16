"""Analytics models for pre-computed snapshot storage.

Provides a single table for caching expensive analytics aggregations
as materialized snapshots, enabling fast retrieval for frequently
accessed analytics queries.

Note: Most analytics are computed in real-time via service.py
aggregation functions. This model serves as an optional cache layer
for pre-computed report snapshots.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AnalyticsSnapshot(Base):
    """
    Pre-computed analytics snapshot for a company/branch/report combination.

    Stores serialized aggregation results for expensive queries that can be
    refreshed periodically via background tasks. Primary real-time analytics
    are served directly from service.py aggregation functions.
    """

    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "branch_id",
            "report_type",
            "snapshot_date",
            name="uq_analytics_snapshots_company_branch_report_date",
        ),
        {
            "schema": "public",
            "comment": "Pre-computed analytics snapshots for fast retrieval",
        },
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant isolation
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_analytics_snapshots_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_analytics_snapshots_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Snapshot metadata
    report_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of report (overview, conversions, campaigns, branches_kpi, erp, ai_insights, growth)",
    )
    snapshot_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="The date this snapshot represents",
    )
    date_range_start = Column(Date, nullable=True)
    date_range_end = Column(Date, nullable=True)

    # Serialized result data
    result_data = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Serialized aggregation result",
    )

    # Performance metadata
    computation_time_ms = Column(
        Integer,
        nullable=True,
        comment="Time taken to compute this snapshot in milliseconds",
    )
    record_count = Column(
        Integer,
        nullable=True,
        default=0,
        comment="Number of source records aggregated",
    )

    # Status
    is_stale = Column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="0=fresh, 1=stale (needs refresh)",
    )

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AnalyticsSnapshot(id={self.id}, "
            f"report_type='{self.report_type}', "
            f"company_id={self.company_id}, "
            f"snapshot_date={self.snapshot_date}, "
            f"is_stale={self.is_stale})>"
        )
