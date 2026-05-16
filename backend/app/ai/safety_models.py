"""AI Fact Validation & Safety models."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class AIFactCheckLog(Base):
    """AI fact validation results log."""
    __tablename__ = "ai_fact_check_logs"
    __table_args__ = (
        Index("ix_afcl_conversation", "conversation_id"),
        Index("ix_afcl_status", "verification_status"),
        {"schema": "public", "comment": "AI fact validation results"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    ai_response_id = Column(Integer, nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(50), nullable=False)  # price, inventory, campaign, reservation, general
    verification_status = Column(String(20), nullable=False, default="pending")  # pending, verified, failed, uncertain
    erp_check_result = Column(JSON, nullable=True)
    menu_check_result = Column(JSON, nullable=True)
    confidence_score = Column(Numeric(4, 3), nullable=False, default=0.0)
    requires_approval = Column(Boolean, nullable=False, default=False)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    blocking_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AICriticalActionPolicy(Base):
    """Policy for which AI actions require validation/approval."""
    __tablename__ = "ai_critical_action_policies"
    __table_args__ = (
        Index("ix_acap_company", "company_id"),
        {"schema": "public", "comment": "AI critical action policies per company"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # price_quote, inventory_check, campaign_create, reservation, order
    requires_erp_verification = Column(Boolean, nullable=False, default=True)
    requires_human_approval = Column(Boolean, nullable=False, default=False)
    min_confidence_threshold = Column(Numeric(4, 3), nullable=False, default=0.85)
    auto_block_if_unverified = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
