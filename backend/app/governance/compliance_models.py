"""Enterprise Compliance Layer models - Phase 4."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class AuditRetentionPolicy(Base):
    """Audit retention governance policies."""
    __tablename__ = "audit_retention_policies"
    __table_args__ = (
        Index("ix_arp_company", "company_id"),
        {"schema": None, "comment": "Audit data retention policies"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    data_category = Column(String(50), nullable=False)  # audit_logs, chat_history, analytics, erp_data
    retention_days = Column(Integer, nullable=False, default=365)
    auto_archive = Column(Boolean, nullable=False, default=True)
    auto_delete_after_retention = Column(Boolean, nullable=False, default=False)
    archive_storage_class = Column(String(20), nullable=False, default="standard")
    legal_hold = Column(Boolean, nullable=False, default=False)
    legal_hold_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class DataLineageRecord(Base):
    """Data lineage tracking."""
    __tablename__ = "data_lineage_records"
    __table_args__ = (
        Index("ix_dlr_source", "source_table", "source_id"),
        Index("ix_dlr_target", "target_table", "target_id"),
        {"schema": None, "comment": "Data lineage tracking"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    operation = Column(String(50), nullable=False)  # create, update, delete, sync, export, ai_generate
    source_table = Column(String(100), nullable=True)
    source_id = Column(Integer, nullable=True)
    target_table = Column(String(100), nullable=True)
    target_id = Column(Integer, nullable=True)
    transformation_description = Column(Text, nullable=True)
    performed_by = Column(Integer, nullable=True)
    performed_by_type = Column(String(20), nullable=False, default="user")  # user, system, ai, webhook
    config_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PIIDataClassification(Base):
    """PII data classification records."""
    __tablename__ = "pii_data_classifications"
    __table_args__ = (
        Index("ix_pdc_table_record", "table_name", "record_id"),
        Index("ix_pdc_company", "company_id"),
        {"schema": None, "comment": "PII data classification"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=False)
    pii_type = Column(String(50), nullable=False)  # email, phone, name, address, tax_id
    classification_level = Column(String(20), nullable=False, default="standard")  # standard, sensitive, restricted
    anonymized = Column(Boolean, nullable=False, default=False)
    anonymized_at = Column(DateTime, nullable=True)
    detected_by = Column(String(20), nullable=False, default="auto")  # auto, manual, audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ComplianceReport(Base):
    """Generated compliance reports."""
    __tablename__ = "compliance_reports"
    __table_args__ = (
        Index("ix_cr_company", "company_id"),
        Index("ix_cr_date", "report_date"),
        {"schema": None, "comment": "Compliance reports"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    report_type = Column(String(50), nullable=False)  # gdpr, kvkk, audit, data_protection, access_log
    report_date = Column(String(10), nullable=False)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)
    data_points = Column(JSON, nullable=False, default=dict)
    issues_found = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="generated")  # generated, reviewed, submitted
    generated_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AdminActionLog(Base):
    """Immutable admin action tracking."""
    __tablename__ = "admin_action_logs"
    __table_args__ = (
        Index("ix_aal_admin", "admin_id"),
        Index("ix_aal_company", "company_id"),
        Index("ix_aal_time", "created_at"),
        {"schema": None, "comment": "Immutable admin action audit trail"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    admin_id = Column(Integer, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # create, update, delete, export, config_change, permission_change
    target_table = Column(String(100), nullable=True)
    target_id = Column(Integer, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
