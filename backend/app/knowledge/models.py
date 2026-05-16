"""Knowledge Ingestion - Database Models.

Modeller:
    - KnowledgeBase: Sirket/sube bazli knowledge base kayitlari
    - KnowledgeChunk: Semantic chunk'lar
    - KnowledgeEmbedding: Vector embedding kayitlari
    - BrandProfile: Marka profili (tone, colors, values)
    - VisualAsset: Gorsel varliklar ve analizleri
    - CampaignInsight: Kampanya analizleri ve ogrenilenler
    - IngestionJob: Async ingestion isleri
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT, MEDIUMTEXT
from sqlalchemy.orm import relationship

from app.database import Base


# =============================================================================
# Enums (mapped as String columns for DB portability)
# =============================================================================

class IngestionSource(str, PyEnum):
    """Bilgi kaynak tipleri."""

    WEBSITE = "website"
    PDF = "pdf"
    DOCX = "docx"
    OCR = "ocr"
    SOCIAL_MEDIA = "social_media"
    MANUAL = "manual"
    CAMPAIGN = "campaign"
    VISUAL = "visual"


class IngestionStatus(str, PyEnum):
    """Ingestion is durumlari."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ChunkType(str, PyEnum):
    """Chunk tipi."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    BRAND_STATEMENT = "brand_statement"
    CAMPAIGN_DATA = "campaign_data"
    VISUAL_DESCRIPTION = "visual_description"


class BrandAttributeType(str, PyEnum):
    """Brand attribute kategorileri."""

    TONE = "tone"
    COLOR = "color"
    VALUE = "value"
    MISSION = "mission"
    VISION = "vision"
    SLOGAN = "slogan"
    PERSONALITY = "personality"
    TARGET_AUDIENCE = "target_audience"


# =============================================================================
# Association Tables
# =============================================================================

knowledge_base_tags = Table(
    "knowledge_base_tags",
    Base.metadata,
    Column("knowledge_base_id", Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True),
    Column("tag", String(64), primary_key=True),
)


# =============================================================================
# Models
# =============================================================================

class KnowledgeBase(Base):
    """Sirket veya sube bazli knowledge base kaydi.

    Her sirket/sube icin ayrı knowledge base olusturulur.
    Web sitesi, PDF, DOCX, gorsel vb. tum icerikler burada toplanir.
    """

    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    # Kaynak bilgileri
    source_type = Column(String(32), nullable=False, default=IngestionSource.WEBSITE)
    source_url = Column(String(2048), nullable=True)
    source_title = Column(String(512), nullable=True)
    source_description = Column(Text, nullable=True)

    # Icerik
    raw_content = Column(LONGTEXT, nullable=True)
    raw_content_hash = Column(String(64), nullable=True, index=True)
    content_metadata = Column(JSON, nullable=True, default=dict)

    # Durum
    status = Column(String(32), nullable=False, default=IngestionStatus.PENDING)
    chunk_count = Column(Integer, default=0)
    embedding_count = Column(Integer, default=0)

    # Islem bilgileri
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Iliskiler
    chunks = relationship("KnowledgeChunk", back_populates="knowledge_base", cascade="all, delete-orphan", lazy="selectin")
    embeddings = relationship("KnowledgeEmbedding", back_populates="knowledge_base", cascade="all, delete-orphan", lazy="selectin")
    ingestion_jobs = relationship("IngestionJob", back_populates="knowledge_base")

    # Index
    __table_args__ = (
        Index("ix_kb_company_branch", "company_id", "branch_id"),
        Index("ix_kb_status", "status"),
        Index("ix_kb_source_type", "source_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "source_description": self.source_description,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "embedding_count": self.embedding_count,
            "content_metadata": self.content_metadata or {},
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "error_message": self.error_message,
        }


class KnowledgeChunk(Base):
    """Semantic chunk'lar - anlamli metin parcalari.

    Metin semantic chunking ile anlamli parcalara bolunur.
    Her chunk bir vector embedding'e sahiptir.
    """

    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    # Chunk icerigi
    chunk_type = Column(String(32), nullable=False, default=ChunkType.PARAGRAPH)
    content = Column(MEDIUMTEXT, nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)

    # Chunk metadata
    sequence = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)

    # Semantic bilgiler
    semantic_tags = Column(JSON, nullable=True, default=list)
    keywords = Column(JSON, nullable=True, default=list)
    entities = Column(JSON, nullable=True, default=list)

    # Kaynak bilgisi
    source_section = Column(String(256), nullable=True)
    source_heading = Column(String(256), nullable=True)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Iliskiler
    knowledge_base = relationship("KnowledgeBase", back_populates="chunks")
    embedding = relationship("KnowledgeEmbedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan")

    # Index
    __table_args__ = (
        Index("ix_chunk_kb_seq", "knowledge_base_id", "sequence"),
        Index("ix_chunk_company_type", "company_id", "chunk_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "chunk_type": self.chunk_type,
            "content": self.content,
            "sequence": self.sequence,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "semantic_tags": self.semantic_tags or [],
            "keywords": self.keywords or [],
            "entities": self.entities or [],
            "source_section": self.source_section,
            "source_heading": self.source_heading,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeEmbedding(Base):
    """Vector embedding kayitlari.

    Her chunk icin bir embedding vectoru uretilir.
    Vector similarity search icin kullanilir.
    """

    __tablename__ = "knowledge_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Embedding model bilgisi
    embedding_model = Column(String(128), nullable=False, default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_version = Column(String(32), nullable=False, default="1.0")
    embedding_dimension = Column(Integer, nullable=False, default=384)

    # Vector - JSON formatinda saklanir (vector DB migration icin hazirlik)
    vector_json = Column(JSON, nullable=False)

    # Metadata
    similarity_score = Column(Float, nullable=True)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Iliskiler
    knowledge_base = relationship("KnowledgeBase", back_populates="embeddings")
    chunk = relationship("KnowledgeChunk", back_populates="embedding")

    # Index
    __table_args__ = (
        Index("ix_emb_company_model", "company_id", "embedding_model"),
        Index("ix_emb_kb_id", "knowledge_base_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "chunk_id": self.chunk_id,
            "company_id": self.company_id,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BrandProfile(Base):
    """Marka profili - marka tonu, renkleri, degerleri.

    AI'in markayi tanima ve dogru tonda icerik uretmesi icin
    ogrenilen marka profili bilgileri.
    """

    __tablename__ = "brand_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    # Attribute kategorisi
    attribute_type = Column(String(32), nullable=False)
    attribute_key = Column(String(128), nullable=False)
    attribute_value = Column(Text, nullable=False)

    # Guven skoru (0-1)
    confidence_score = Column(Float, default=0.5)

    # Kaynak
    source = Column(String(256), nullable=True)
    source_count = Column(Integer, default=1)

    # Metadata
    extra_data = Column(JSON, nullable=True, default=dict)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Index
    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "attribute_type", "attribute_key", name="uq_brand_attr"),
        Index("ix_brand_company_type", "company_id", "attribute_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "attribute_type": self.attribute_type,
            "attribute_key": self.attribute_key,
            "attribute_value": self.attribute_value,
            "confidence_score": self.confidence_score,
            "source": self.source,
            "source_count": self.source_count,
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class VisualAsset(Base):
    """Gorsel varliklar ve analiz sonuclari.

    Marka gorsel kimligini ogrenmek icin kullanilan
    gorseller ve AI analiz sonuclari.
    """

    __tablename__ = "visual_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)

    # Gorsel bilgileri
    image_url = Column(String(2048), nullable=False)
    image_hash = Column(String(64), nullable=True, index=True)
    image_type = Column(String(64), nullable=True)
    source_url = Column(String(2048), nullable=True)

    # Analiz sonuclari
    description = Column(Text, nullable=True)
    dominant_colors = Column(JSON, nullable=True, default=list)
    detected_objects = Column(JSON, nullable=True, default=list)
    detected_text = Column(Text, nullable=True)
    brand_elements = Column(JSON, nullable=True, default=list)
    composition_analysis = Column(JSON, nullable=True, default=dict)
    style_tags = Column(JSON, nullable=True, default=list)

    # Brand iliskisi
    is_brand_asset = Column(Integer, default=0)
    brand_relevance_score = Column(Float, default=0.0)

    # Metadata
    extra_data = Column(JSON, nullable=True, default=dict)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    analyzed_at = Column(DateTime, nullable=True)

    # Index
    __table_args__ = (
        Index("ix_visual_company_brand", "company_id", "is_brand_asset"),
        Index("ix_visual_kb", "knowledge_base_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "knowledge_base_id": self.knowledge_base_id,
            "image_url": self.image_url,
            "image_type": self.image_type,
            "source_url": self.source_url,
            "description": self.description,
            "dominant_colors": self.dominant_colors or [],
            "detected_objects": self.detected_objects or [],
            "detected_text": self.detected_text,
            "brand_elements": self.brand_elements or [],
            "composition_analysis": self.composition_analysis or {},
            "style_tags": self.style_tags or [],
            "is_brand_asset": bool(self.is_brand_asset),
            "brand_relevance_score": self.brand_relevance_score,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CampaignInsight(Base):
    """Kampanya analizleri ve ogrenilen basari faktorleri.

    Gecmis kampanyalar analiz edilerek basari faktorleri cikarilir.
    AI gelecek kampanyalar icin ogrenilen bu bilgileri kullanir.
    """

    __tablename__ = "campaign_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)

    # Kampanya bilgileri
    campaign_name = Column(String(256), nullable=False)
    campaign_type = Column(String(64), nullable=True)
    platform = Column(String(64), nullable=True)

    # Metrikler
    reach = Column(Integer, nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    conversions = Column(Integer, nullable=True)
    spend = Column(Float, nullable=True)
    revenue = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)
    ctr = Column(Float, nullable=True)
    roas = Column(Float, nullable=True)
    cpa = Column(Float, nullable=True)

    # AI analiz sonuclari
    success_factors = Column(JSON, nullable=True, default=list)
    failure_factors = Column(JSON, nullable=True, default=list)
    audience_insights = Column(JSON, nullable=True, default=dict)
    content_analysis = Column(JSON, nullable=True, default=dict)
    timing_insights = Column(JSON, nullable=True, default=dict)
    creative_analysis = Column(JSON, nullable=True, default=dict)
    ai_summary = Column(Text, nullable=True)

    # Ogrenilen stratejiler
    recommended_strategies = Column(JSON, nullable=True, default=list)
    similar_campaigns = Column(JSON, nullable=True, default=list)

    # Metadata
    campaign_dates = Column(JSON, nullable=True, default=dict)
    extra_data = Column(JSON, nullable=True, default=dict)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Index
    __table_args__ = (
        Index("ix_campaign_company_type", "company_id", "campaign_type"),
        Index("ix_campaign_platform", "platform"),
        Index("ix_campaign_kb", "knowledge_base_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "campaign_name": self.campaign_name,
            "campaign_type": self.campaign_type,
            "platform": self.platform,
            "reach": self.reach,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": self.spend,
            "revenue": self.revenue,
            "engagement_rate": self.engagement_rate,
            "ctr": self.ctr,
            "roas": self.roas,
            "cpa": self.cpa,
            "success_factors": self.success_factors or [],
            "failure_factors": self.failure_factors or [],
            "audience_insights": self.audience_insights or {},
            "content_analysis": self.content_analysis or {},
            "timing_insights": self.timing_insights or {},
            "creative_analysis": self.creative_analysis or {},
            "ai_summary": self.ai_summary,
            "recommended_strategies": self.recommended_strategies or [],
            "campaign_dates": self.campaign_dates or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class IngestionJob(Base):
    """Async ingestion is kayitlari.

    Celery task ile yonetilen ingestion islerinin durumunu takip eder.
    """

    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    # Celery task
    celery_task_id = Column(String(128), nullable=True, index=True)

    # Is tipi
    job_type = Column(String(64), nullable=False)
    source_info = Column(JSON, nullable=True, default=dict)

    # Durum
    status = Column(String(32), nullable=False, default=IngestionStatus.PENDING)
    progress_percent = Column(Integer, default=0)

    # Loglar
    logs = Column(JSON, nullable=True, default=list)
    error_details = Column(JSON, nullable=True, default=dict)

    # Zaman damgalari
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Iliskiler
    knowledge_base = relationship("KnowledgeBase", back_populates="ingestion_jobs")

    # Index
    __table_args__ = (
        Index("ix_job_status_type", "status", "job_type"),
        Index("ix_job_company", "company_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "celery_task_id": self.celery_task_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "source_info": self.source_info or {},
            "logs": self.logs or [],
            "error_details": self.error_details or {},
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BrandColor(Base):
    """Marka renkleri - hex kodlari ve kullanim alanlari.

    Gorsel analiz ve manuel giris ile ogrenilen marka renk paleti.
    """

    __tablename__ = "brand_colors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    # Renk bilgisi
    hex_code = Column(String(7), nullable=False)
    color_name = Column(String(64), nullable=True)
    color_role = Column(String(32), nullable=True)

    # Kullanim alani
    usage_area = Column(String(128), nullable=True)
    usage_frequency = Column(Float, default=0.0)

    # Metadata
    confidence = Column(Float, default=0.5)
    source = Column(String(256), nullable=True)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Index
    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "hex_code", "usage_area", name="uq_brand_color"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "hex_code": self.hex_code,
            "color_name": self.color_name,
            "color_role": self.color_role,
            "usage_area": self.usage_area,
            "usage_frequency": self.usage_frequency,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SocialPostLearning(Base):
    """Sosyal medya gonderilerinden ogrenilen marka tonu.

    Gecmis sosyal medya gonderileri analiz edilerek
    marka tonu, dil kullanimi, etkilesim oruntuleri cikarilir.
    """

    __tablename__ = "social_post_learning"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    # Gonderi ornegi
    post_sample = Column(MEDIUMTEXT, nullable=True)
    platform = Column(String(32), nullable=True)

    # Ogrenilenler
    tone_label = Column(String(64), nullable=True)
    language_style = Column(String(64), nullable=True)
    emoji_usage = Column(String(32), nullable=True)
    hashtag_pattern = Column(JSON, nullable=True, default=list)
    call_to_action_style = Column(String(64), nullable=True)
    engagement_score = Column(Float, nullable=True)

    # Istatistiksel analiz
    avg_sentence_length = Column(Float, nullable=True)
    vocabulary_richness = Column(Float, nullable=True)
    formality_score = Column(Float, nullable=True)

    # Metadata
    post_count_analyzed = Column(Integer, default=0)
    date_range = Column(JSON, nullable=True, default=dict)

    # Zaman damgalari
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Index
    __table_args__ = (
        Index("ix_social_company_tone", "company_id", "tone_label"),
        Index("ix_social_platform", "platform"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "post_sample": self.post_sample,
            "platform": self.platform,
            "tone_label": self.tone_label,
            "language_style": self.language_style,
            "emoji_usage": self.emoji_usage,
            "hashtag_pattern": self.hashtag_pattern or [],
            "call_to_action_style": self.call_to_action_style,
            "engagement_score": self.engagement_score,
            "avg_sentence_length": self.avg_sentence_length,
            "vocabulary_richness": self.vocabulary_richness,
            "formality_score": self.formality_score,
            "post_count_analyzed": self.post_count_analyzed,
            "date_range": self.date_range or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
