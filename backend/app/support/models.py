"""SQLAlchemy models for the AI Customer Support module."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SupportTicket(Base):
    """Customer support tickets from multiple channels."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    branch_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True,
        index=True,
    )
    customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True,
        comment="External customer ID from the source channel",
    )
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    source: Mapped[str] = mapped_column(
        Enum("whatsapp", "telegram", "instagram", "facebook", "email", "web", name="ticket_source"),
        nullable=False,
        index=True,
    )
    source_conversation_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True,
        comment="Conversation/thread ID from the source channel (e.g., WhatsApp chat ID)",
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[str] = mapped_column(
        Enum("open", "pending", "resolved", "closed", name="ticket_status"),
        nullable=False,
        default="open",
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "urgent", name="ticket_priority"),
        nullable=False,
        default="medium",
        index=True,
    )
    assigned_to: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    ai_handled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    category: Mapped[Optional[str]] = mapped_column(
        Enum("billing", "technical", "sales", "general", name="ticket_category"),
        nullable=True,
        index=True,
    )
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now(),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    messages: Mapped[list["SupportMessage"]] = relationship(
        "SupportMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportMessage.created_at",
        lazy="selectin",
    )


class SupportMessage(Base):
    """Individual messages within a support ticket conversation."""

    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(
        Enum("customer", "agent", "ai", "system", name="message_sender_type"),
        nullable=False,
    )
    sender_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="User ID if sender is an agent; null for customer/AI",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    sentiment: Mapped[Optional[str]] = mapped_column(
        Enum("positive", "negative", "neutral", name="message_sentiment"),
        nullable=True,
    )
    internal_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # Relationships
    ticket: Mapped["SupportTicket"] = relationship(
        "SupportTicket", back_populates="messages",
    )


class KnowledgeBaseArticle(Base):
    """Knowledge base articles for RAG-powered support."""

    __tablename__ = "knowledge_base_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    vector_embedding: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="JSON vector embedding for similarity search (pgvector-compatible)",
    )
    source: Mapped[str] = mapped_column(
        Enum("manual", "ai_generated", name="kb_article_source"),
        nullable=False,
        default="manual",
    )
    status: Mapped[str] = mapped_column(
        Enum("draft", "published", "archived", name="kb_article_status"),
        nullable=False,
        default="draft",
        index=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now(),
    )


class KnowledgeBaseCategory(Base):
    """Hierarchical categories for knowledge base articles."""

    __tablename__ = "knowledge_base_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("knowledge_base_categories.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # Self-referential relationship for hierarchy
    children: Mapped[list["KnowledgeBaseCategory"]] = relationship(
        "KnowledgeBaseCategory",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    parent: Mapped[Optional["KnowledgeBaseCategory"]] = relationship(
        "KnowledgeBaseCategory",
        back_populates="children",
        remote_side=[id],
    )


class SupportMacro(Base):
    """Reusable response templates (macros) with variable substitution."""

    __tablename__ = "support_macros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    shortcut: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="e.g., '/refund' - typed to expand the macro",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="Variable definitions for substitution, e.g., {'customer_name': 'string', 'order_id': 'string'}",
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now(),
    )


class EscalationRule(Base):
    """Rules for automatically escalating tickets based on conditions."""

    __tablename__ = "escalation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    conditions: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="Dict of conditions, e.g., {'priority': 'urgent', 'sentiment': 'negative', 'wait_time_minutes': 30}",
    )
    actions: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="Dict of actions, e.g., {'assign_to': 5, 'notify': ['email'], 'set_priority': 'urgent'}",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now(),
    )


class AIReplyAuditLog(Base):
    """Audit trail for every AI-generated reply before it is sent."""

    __tablename__ = "ai_reply_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # AI urettigi ham cevap
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    # Filtrelenmis / temizlenmis cevap
    filtered_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Confidence skoru
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Kullanilan KB makale ID'leri
    kb_articles_used: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    # Relevance skorlari
    relevance_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Onay durumu
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | approved | rejected | auto_sent | filtered",
    )
    # Onay / red eden kullanici
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Filtreleme sonuclari
    forbidden_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    forbidden_keywords_found: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    forbidden_patterns_found: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    # Sentiment analizi
    detected_sentiment: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="positive | negative | neutral",
    )

    # Human takeover onerildi mi
    suggested_human_takeover: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Kac token kullanildi
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), index=True,
    )


class SupportAnalytics(Base):
    """Daily aggregated support analytics per company."""

    __tablename__ = "support_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True,
        comment="The date this analytics row represents (aggregated daily)",
    )
    total_tickets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_tickets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_response_time: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Average first response time in minutes",
    )
    avg_resolution_time: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Average resolution time in minutes",
    )
    ai_resolution_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Percentage of tickets resolved by AI (0.0-1.0)",
    )
    customer_satisfaction: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="Average customer satisfaction score (1.0-5.0)",
    )
    tickets_by_source: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="e.g., {'whatsapp': 10, 'email': 5, 'web': 3}",
    )
    tickets_by_category: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="e.g., {'billing': 8, 'technical': 6, 'sales': 4}",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
