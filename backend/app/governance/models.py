"""Data Governance models for GDPR/KVKK compliance tracking.

Tables:
- gdpr_export_requests: Tracks data export requests (Article 20)
- gdpr_deletion_requests: Tracks data deletion requests (Article 17)
- retention_policy_runs: Logs retention policy execution history
"""

import enum
from datetime import datetime

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
)

from app.database import Base


class GDPRRequestStatus(str, enum.Enum):
    """Status of a GDPR/KVKK request."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class GDPRRequestType(str, enum.Enum):
    """Type of GDPR/KVKK data subject request."""

    EXPORT = "export"
    DELETION = "deletion"
    RECTIFICATION = "rectification"
    RESTRICTION = "restriction"


class GDPRExportRequest(Base):
    """Tracks GDPR/KVKK data export requests (Right to Data Portability).

    Records who requested the export, what data scope was requested,
    and the status of the export process.
    """

    __tablename__ = "gdpr_export_requests"
    __table_args__ = {
        "schema": "public",
        "comment": "GDPR/KVKK data export request tracking",
    }

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Admin who initiated the export (null if self-service)",
    )

    request_type = Column(
        Enum(GDPRRequestType, name="gdprrequesttype", create_type=True),
        default=GDPRRequestType.EXPORT,
        nullable=False,
    )
    status = Column(
        Enum(GDPRRequestStatus, name="gdprrequeststatus", create_type=True),
        default=GDPRRequestStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Data scope: which tables/modules to include
    data_scope = Column(
        JSON,
        nullable=False,
        default=lambda: ["all"],
        comment="List of data scopes: all, user, company, branch, ai, ads, etc.",
    )

    # Export file metadata
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    record_count = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Expiration: export files are retained for 30 days
    expires_at = Column(DateTime, nullable=False)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<GDPRExportRequest(id={self.id}, user_id={self.user_id}, "
            f"status='{self.status}', scope={self.data_scope})>"
        )


class GDPRDeletionRequest(Base):
    """Tracks GDPR/KVKK data deletion requests (Right to be Forgotten).

    Records deletion requests with verification status, affected tables,
    and execution logs for audit purposes.
    """

    __tablename__ = "gdpr_deletion_requests"
    __table_args__ = {
        "schema": "public",
        "comment": "GDPR/KVKK data deletion request tracking",
    }

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    request_type = Column(
        Enum(GDPRRequestType, name="gdprrequesttype_deletion", create_type=True),
        default=GDPRRequestType.DELETION,
        nullable=False,
    )
    status = Column(
        Enum(GDPRRequestStatus, name="gdprrequeststatus_deletion", create_type=True),
        default=GDPRRequestStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Verification: double-opt-in for deletion
    verification_token = Column(String(255), nullable=True, index=True)
    verified_at = Column(DateTime, nullable=True)

    # What was deleted
    affected_tables = Column(JSON, nullable=True)
    records_deleted = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<GDPRDeletionRequest(id={self.id}, user_id={self.user_id}, "
            f"status='{self.status}', records_deleted={self.records_deleted})>"
        )


class RetentionPolicyRun(Base):
    """Logs each execution of the retention policy cleanup job.

    Provides audit trail for data retention compliance by recording
    which policy was run, how many records were affected, and any errors.
    """

    __tablename__ = "retention_policy_runs"
    __table_args__ = {
        "schema": "public",
        "comment": "Retention policy execution audit log",
    }

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    policy_name = Column(String(128), nullable=False, index=True)
    table_name = Column(String(128), nullable=False, index=True)
    retention_days = Column(Integer, nullable=False)

    records_affected = Column(Integer, nullable=False, default=0)
    execution_time_ms = Column(Integer, nullable=True)

    status = Column(
        Enum("success", "failed", "partial", name="retentionrunstatus", create_type=True),
        nullable=False,
        index=True,
    )
    error_message = Column(Text, nullable=True)

    # Snapshot of cutoff date used
    cutoff_date = Column(DateTime, nullable=False)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<RetentionPolicyRun(id={self.id}, policy='{self.policy_name}', "
            f"table='{self.table_name}', affected={self.records_affected}, "
            f"status='{self.status}')>"
        )
