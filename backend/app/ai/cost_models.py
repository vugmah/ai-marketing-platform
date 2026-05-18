"""AI Cost Governance models."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class AITokenUsage(Base):
    """Per-request AI token usage tracking."""
    __tablename__ = "ai_token_usage"
    __table_args__ = (
        Index("ix_atu_company", "company_id"),
        Index("ix_atu_branch", "branch_id"),
        Index("ix_atu_model", "model_name"),
        Index("ix_atu_date", "created_at"),
        {"schema": None, "comment": "AI token usage per request"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(100), nullable=False, index=True)
    model_name = Column(String(50), nullable=False)  # gpt-4o, gpt-4o-mini, etc.
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Numeric(10, 6), nullable=False, default=0.0)
    request_type = Column(String(50), nullable=False, default="chat")
    priority = Column(String(20), nullable=False, default="normal")  # low, normal, high, critical
    cached = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AIBudget(Base):
    """AI budget per company/branch."""
    __tablename__ = "ai_budgets"
    __table_args__ = (
        Index("ix_ab_company", "company_id"),
        Index("ix_ab_branch", "branch_id"),
        {"schema": None, "comment": "AI budgets per company and branch"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    period = Column(String(20), nullable=False, default="monthly")  # daily, weekly, monthly
    budget_usd = Column(Numeric(12, 4), nullable=False, default=100.0)
    spent_usd = Column(Numeric(12, 4), nullable=False, default=0.0)
    alert_threshold_pct = Column(Numeric(5, 2), nullable=False, default=80.0)
    hard_limit_usd = Column(Numeric(12, 4), nullable=False, default=200.0)
    model_tier = Column(String(20), nullable=False, default="balanced")  # cheap, balanced, premium
    fallback_model = Column(String(50), nullable=True, default="gpt-4o-mini")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AIModelPricing(Base):
    """AI model pricing reference."""
    __tablename__ = "ai_model_pricing"
    __table_args__ = (
        Index("ix_amp_model", "model_name"),
        {"schema": None, "comment": "AI model pricing per 1K tokens"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(50), nullable=False, unique=True)
    input_cost_per_1k = Column(Numeric(10, 6), nullable=False)
    output_cost_per_1k = Column(Numeric(10, 6), nullable=False)
    provider = Column(String(50), nullable=False)
    context_window = Column(Integer, nullable=False)
    quality_tier = Column(String(20), nullable=False)  # cheap, balanced, premium
    active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
