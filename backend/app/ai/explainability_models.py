"""AI Explainability models - Phase 4."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class AIRecommendationExplanation(Base):
    """AI recommendation explanations with source attribution."""
    __tablename__ = "ai_recommendation_explanations"
    __table_args__ = (
        Index("ix_are_rec", "recommendation_id"),
        Index("ix_are_company", "company_id"),
        {"schema": "public", "comment": "AI recommendation explainability"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=True, index=True)
    recommendation_id = Column(Integer, nullable=False, index=True)
    recommendation_type = Column(String(50), nullable=False)  # campaign, audience, budget, content, timing
    title = Column(String(500), nullable=False)
    explanation = Column(Text, nullable=False)
    reasoning_steps = Column(JSON, nullable=False, default=list)
    source_data = Column(JSON, nullable=False, default=dict)
    confidence_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    confidence_reason = Column(Text, nullable=True)
    data_sources = Column(JSON, nullable=False, default=list)
    key_factors = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AIScoringFactor(Base):
    """Individual scoring factors for AI recommendations."""
    __tablename__ = "ai_scoring_factors"
    __table_args__ = (
        Index("ix_asf_rec", "recommendation_id"),
        {"schema": "public", "comment": "AI scoring factors breakdown"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(Integer, ForeignKey("public.ai_recommendation_explanations.id"), nullable=False)
    factor_name = Column(String(200), nullable=False)
    factor_category = Column(String(50), nullable=False)  # engagement, reach, cost, timing, audience
    weight = Column(Numeric(5, 4), nullable=False, default=0.0)
    score = Column(Numeric(5, 4), nullable=False, default=0.0)
    weighted_score = Column(Numeric(5, 4), nullable=False, default=0.0)
    data_source = Column(String(200), nullable=True)
    raw_value = Column(String(500), nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
