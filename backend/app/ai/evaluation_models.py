"""AI Evaluation & Quality Framework models - Phase 2."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class AIHallucinationScore(Base):
    """AI hallucination detection scores."""
    __tablename__ = "ai_hallucination_scores"
    __table_args__ = (
        Index("ix_ahs_conversation", "conversation_id"),
        Index("ix_ahs_company", "company_id"),
        {"schema": "public", "comment": "AI hallucination scoring per response"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    response_id = Column(Integer, nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    hallucination_score = Column(Numeric(5, 4), nullable=False, default=0.0)  # 0-1, higher = more hallucinated
    factual_score = Column(Numeric(5, 4), nullable=False, default=0.0)  # 0-1, higher = more factual
    source_verification_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    detected_claims = Column(JSON, nullable=False, default=list)
    verified_claims = Column(JSON, nullable=False, default=list)
    unverified_claims = Column(JSON, nullable=False, default=list)
    flagged = Column(Boolean, nullable=False, default=False)
    reviewed_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AIRecommendationQuality(Base):
    """AI recommendation quality tracking."""
    __tablename__ = "ai_recommendation_quality"
    __table_args__ = (
        Index("ix_arq_rec", "recommendation_id"),
        Index("ix_arq_company", "company_id"),
        {"schema": "public", "comment": "AI recommendation quality metrics"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    recommendation_id = Column(Integer, nullable=False, index=True)
    recommendation_type = Column(String(50), nullable=False)
    user_feedback = Column(String(20), nullable=True)  # helpful, unhelpful, neutral
    helpfulness_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    accuracy_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    actionability_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    overall_quality_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    user_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AIPromptPerformance(Base):
    """Prompt performance analytics."""
    __tablename__ = "ai_prompt_performance"
    __table_args__ = (
        Index("ix_app_prompt", "prompt_template_key"),
        Index("ix_app_company", "company_id"),
        {"schema": "public", "comment": "Prompt performance analytics"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    prompt_template_key = Column(String(100), nullable=False)
    model_name = Column(String(50), nullable=False)
    total_requests = Column(Integer, nullable=False, default=0)
    avg_response_quality = Column(Numeric(5, 4), nullable=False, default=0.0)
    avg_latency_ms = Column(Numeric(10, 2), nullable=False, default=0.0)
    avg_token_count = Column(Integer, nullable=False, default=0)
    avg_cost_usd = Column(Numeric(10, 6), nullable=False, default=0.0)
    user_satisfaction_rate = Column(Numeric(5, 4), nullable=False, default=0.0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AIConfidenceAnalytics(Base):
    """AI confidence score tracking over time."""
    __tablename__ = "ai_confidence_analytics"
    __table_args__ = (
        Index("ix_aca_company", "company_id"),
        Index("ix_aca_date", "date"),
        {"schema": "public", "comment": "AI confidence analytics daily"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    date = Column(String(10), nullable=False)
    avg_confidence = Column(Numeric(5, 4), nullable=False, default=0.0)
    high_confidence_pct = Column(Numeric(5, 2), nullable=False, default=0.0)
    low_confidence_pct = Column(Numeric(5, 2), nullable=False, default=0.0)
    escalated_count = Column(Integer, nullable=False, default=0)
    unsafe_blocked_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
