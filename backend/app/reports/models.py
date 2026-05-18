"""
Export job database model.

Tracks async report generation jobs with status, file paths, errors,
and metadata for multi-tenant PDF/DOCX/XLSX/CSV/JSON exports.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ExportJob(Base):
    """
    Async report export job tracking model.

    Stores job metadata, status transitions, generated file paths,
    and error details for all export operations in the system.
    """

    __tablename__ = "export_jobs"
    __table_args__ = {
        "schema": None,
        "comment": "Async report export job queue tracking",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_export_jobs_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_export_jobs_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Job specification
    job_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="analytics, campaign, social, erp, billing, followers, custom",
    )
    format = Column(
        String(10),
        nullable=False,
        index=True,
        comment="pdf, docx, xlsx, csv, json",
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, processing, completed, failed, cancelled",
    )

    # File info
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_name = Column(String(255), nullable=True)

    # Error tracking
    error_message = Column(String(1000), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Report config
    report_title = Column(String(255), nullable=True)
    report_params = Column(JSON, nullable=True, default=dict)
    template_config = Column(JSON, nullable=True)

    # Tracking
    created_by = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_export_jobs_created_by",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company", foreign_keys=[company_id], lazy="selectin")
    branch = relationship("Branch", foreign_keys=[branch_id], lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ExportJob(id={self.id}, company_id={self.company_id}, "
            f"type='{self.job_type}', format='{self.format}', "
            f"status='{self.status}')>"
        )

    @property
    def is_terminal(self) -> bool:
        """Check if the job has reached a terminal state."""
        return self.status in ("completed", "failed", "cancelled")

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        if self.started_at and self.status == "processing":
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None

    @property
    def file_size_human(self) -> Optional[str]:
        """Return human-readable file size."""
        if self.file_size is None:
            return None
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
