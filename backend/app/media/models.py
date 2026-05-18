"""
Media pipeline database models for the Creative Studio module.

Defines 10 tables:
- media_assets: Core media files (images, videos, documents)
- media_variants: Derived versions (thumbnails, webp, optimized, resized)
- media_tags: Company-scoped tags for organizing media
- media_tag_mappings: Many-to-many join between assets and tags
- media_collections: Named groups of media assets
- media_collection_items: Ordered items within a collection
- media_analytics: View/download counters per asset
- ai_image_analysis: AI-generated analysis results (captions, hashtags, scores, objects)
- branch_brand_identities: Per-branch brand color/tone/voice configuration
- creative_audits: AI creative audit history and fatigue detection
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class StorageProvider(str, enum.Enum):
    """Supported storage backends for media assets."""

    LOCAL = "local"
    S3 = "s3"
    R2 = "r2"


class MediaStatus(str, enum.Enum):
    """Lifecycle status of a media asset."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    DELETED = "deleted"


class VariantType(str, enum.Enum):
    """Types of derived media variants."""

    THUMBNAIL = "thumbnail"
    WEBP = "webp"
    OPTIMIZED = "optimized"
    RESIZED = "resized"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    VIDEO_THUMBNAIL = "video_thumbnail"


class AnalysisType(str, enum.Enum):
    """Types of AI image analysis."""

    CAPTION = "caption"
    HASHTAG = "hashtag"
    SCORE = "score"
    OBJECTS = "objects"
    BRAND_ALIGNMENT = "brand_alignment"
    INSTAGRAM_OPTIMIZE = "instagram_optimize"
    CREATIVE_AUDIT = "creative_audit"


class VirusScanStatus(str, enum.Enum):
    """Virus scanning status for uploaded files."""

    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    SKIPPED = "skipped"
    ERROR = "error"


class BrandTone(str, enum.Enum):
    """Brand voice/tone options."""

    PROFESSIONAL = "professional"
    CASUAL = "casual"
    PLAYFUL = "playful"
    LUXURY = "luxury"
    FRIENDLY = "friendly"
    BOLD = "bold"
    INSPIRATIONAL = "inspirational"
    INFORMATIVE = "informative"
    WARM = "warm"
    MODERN = "modern"


class FatigueLevel(str, enum.Enum):
    """Creative fatigue severity levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# media_assets
# ---------------------------------------------------------------------------


class MediaAsset(Base):
    """
    Core media asset entity (image, video, or document).

    Attributes:
        id: Primary key (UUID string).
        company_id: Owning company for tenant isolation.
        branch_id: Optional branch for sub-tenant isolation.
        filename: Unique stored filename.
        original_filename: Original user-provided filename.
        file_path: Relative path to the stored file.
        file_size: Size in bytes.
        mime_type: MIME type (e.g., image/jpeg).
        width: Image/video width in pixels (nullable for non-visual).
        height: Image/video height in pixels.
        duration: Video duration in seconds (nullable for images).
        thumbnail_path: Path to the default thumbnail variant.
        storage_provider: Backend used (local/s3/r2).
        storage_key: Object key in remote storage.
        checksum: SHA-256 checksum for integrity verification.
        status: Current processing status.
        metadata: Free-form JSON metadata (camera info, location, etc.).
        created_by: User ID who uploaded the asset.
        created_at: Upload timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "media_assets"
    __table_args__ = {"comment": "Core media assets (images, videos, documents)"}

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    filename = Column(String(255), nullable=False, unique=True, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    mime_type = Column(String(100), nullable=False, index=True)
    category = Column(String(20), nullable=False, default="unknown", index=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    storage_provider = Column(
        Enum(StorageProvider, name="storageprovider", create_type=True),
        default=StorageProvider.LOCAL,
        nullable=False,
    )
    storage_key = Column(String(500), nullable=True)
    checksum = Column(String(64), nullable=True)
    status = Column(
        Enum(MediaStatus, name="mediastatus", create_type=True),
        default=MediaStatus.UPLOADING,
        nullable=False,
        index=True,
    )
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)
    # EXIF / image metadata extracted during upload (camera, lens, GPS, etc.)
    exif_data = Column(JSON, nullable=True, default=dict)
    # Virus scan status: pending / clean / infected / skipped / error
    virus_scan_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    variants = relationship(
        "MediaVariant",
        back_populates="media",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tag_mappings = relationship(
        "MediaTagMapping",
        back_populates="media",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    collection_items = relationship(
        "MediaCollectionItem",
        back_populates="media",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    analytics = relationship(
        "MediaAnalytics",
        back_populates="media",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ai_analyses = relationship(
        "AIImageAnalysis",
        back_populates="media",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    creative_audits = relationship(
        "CreativeAudit",
        back_populates="media",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<MediaAsset(id={self.id}, filename='{self.filename}', "
            f"mime_type='{self.mime_type}', status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# media_variants
# ---------------------------------------------------------------------------


class MediaVariant(Base):
    """
    Derived media variant (thumbnail, webp, optimized, resized).

    Attributes:
        id: Primary key (UUID string).
        media_id: Parent media asset.
        variant_type: Type of variant (thumbnail/webp/optimized/resized/small/medium/large).
        file_path: Relative path to the variant file.
        width: Variant width in pixels.
        height: Variant height in pixels.
        file_size: Variant file size in bytes.
        quality: Compression quality setting used (0-100).
        created_at: Variant creation timestamp.
    """

    __tablename__ = "media_variants"
    __table_args__ = {"comment": "Derived media variants (thumbnails, webp, optimized)"}

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_type = Column(
        Enum(VariantType, name="varianttype", create_type=True),
        nullable=False,
    )
    file_path = Column(String(500), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size = Column(Integer, nullable=False, default=0)
    quality = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    media = relationship("MediaAsset", back_populates="variants")

    def __repr__(self) -> str:
        return (
            f"<MediaVariant(id={self.id}, media_id={self.media_id}, "
            f"type='{self.variant_type}', size={self.width}x{self.height})>"
        )


# ---------------------------------------------------------------------------
# media_tags
# ---------------------------------------------------------------------------


class MediaTag(Base):
    """
    Company-scoped tag for organizing media assets.

    Attributes:
        id: Primary key.
        company_id: Owning company for tenant isolation.
        name: Tag name (unique within company).
        color: Hex color code for visual identification.
        created_at: Creation timestamp.
    """

    __tablename__ = "media_tags"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_media_tags_company_name"),
        {"comment": "Company-scoped tags for media organization"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False, index=True)
    color = Column(String(7), nullable=True, default="#6366F1")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    mappings = relationship(
        "MediaTagMapping",
        back_populates="tag",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<MediaTag(id={self.id}, name='{self.name}', company_id={self.company_id})>"


# ---------------------------------------------------------------------------
# media_tag_mappings
# ---------------------------------------------------------------------------


class MediaTagMapping(Base):
    """
    Many-to-many join table linking media assets to tags.

    Attributes:
        media_id: Foreign key to media_assets.
        tag_id: Foreign key to media_tags.
    """

    __tablename__ = "media_tag_mappings"
    __table_args__ = (
        UniqueConstraint("media_id", "tag_id", name="uq_media_tag_mapping"),
        {"comment": "Media asset to tag mappings"},
    )

    media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(
        Integer,
        ForeignKey("media_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    media = relationship("MediaAsset", back_populates="tag_mappings")
    tag = relationship("MediaTag", back_populates="mappings")

    def __repr__(self) -> str:
        return f"<MediaTagMapping(media_id={self.media_id}, tag_id={self.tag_id})>"


# ---------------------------------------------------------------------------
# media_collections
# ---------------------------------------------------------------------------


class MediaCollection(Base):
    """
    Named collection of media assets.

    Attributes:
        id: Primary key.
        company_id: Owning company for tenant isolation.
        branch_id: Optional branch for sub-tenant isolation.
        name: Collection name.
        description: Optional description.
        cover_media_id: Optional media asset used as cover image.
        item_count: Cached count of items in the collection.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "media_collections"
    __table_args__ = {"comment": "Named collections of media assets"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cover_media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    items = relationship(
        "MediaCollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MediaCollectionItem.order_index",
    )

    def __repr__(self) -> str:
        return (
            f"<MediaCollection(id={self.id}, name='{self.name}', "
            f"company_id={self.company_id}, items={self.item_count})>"
        )


# ---------------------------------------------------------------------------
# media_collection_items
# ---------------------------------------------------------------------------


class MediaCollectionItem(Base):
    """
    Ordered item within a media collection.

    Attributes:
        collection_id: Parent collection.
        media_id: Media asset in the collection.
        order_index: Zero-based display order.
        added_at: When the item was added.
    """

    __tablename__ = "media_collection_items"
    __table_args__ = (
        UniqueConstraint(
            "collection_id", "media_id", name="uq_collection_media_item"
        ),
        {"comment": "Ordered items within media collections"},
    )

    collection_id = Column(
        Integer,
        ForeignKey("media_collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    order_index = Column(Integer, default=0, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    collection = relationship("MediaCollection", back_populates="items")
    media = relationship("MediaAsset", back_populates="collection_items")

    def __repr__(self) -> str:
        return (
            f"<MediaCollectionItem(collection_id={self.collection_id}, "
            f"media_id={self.media_id}, order={self.order_index})>"
        )


# ---------------------------------------------------------------------------
# media_analytics
# ---------------------------------------------------------------------------


class MediaAnalytics(Base):
    """
    Analytics counters for a media asset.

    Attributes:
        id: Primary key.
        media_id: Associated media asset.
        views: Number of times the asset has been viewed.
        downloads: Number of times the asset has been downloaded.
        last_viewed_at: Timestamp of the most recent view.
        created_at: First analytics record timestamp.
    """

    __tablename__ = "media_analytics"
    __table_args__ = {"comment": "View and download counters per media asset"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    views = Column(Integer, default=0, nullable=False)
    downloads = Column(Integer, default=0, nullable=False)
    last_viewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    media = relationship("MediaAsset", back_populates="analytics")

    def __repr__(self) -> str:
        return (
            f"<MediaAnalytics(media_id={self.media_id}, "
            f"views={self.views}, downloads={self.downloads})>"
        )


# ---------------------------------------------------------------------------
# ai_image_analysis
# ---------------------------------------------------------------------------


    account = relationship(
        "app.social.models.SocialAccount",
        back_populates="analytics",
        lazy="selectin",
    )

class AIImageAnalysis(Base):
    """
    AI-generated analysis results for a media asset.

    Supports caption generation, hashtag suggestions, image quality scoring,
    object/brand detection, brand alignment analysis, Instagram optimization,
    and creative auditing via OpenAI Vision API.

    Attributes:
        id: Primary key.
        media_id: Associated media asset.
        company_id: Owning company for tenant isolation.
        branch_id: Optional branch for branch-aware analysis.
        analysis_type: Type of analysis performed.
        result: JSON-structured analysis output.
        confidence: Overall confidence score (0.0 - 1.0).
        model_used: AI model identifier (e.g., gpt-4o-mini).
        brand_identity_applied: Whether brand identity was factored into analysis.
        created_at: Analysis timestamp.
    """

    __tablename__ = "ai_image_analysis"
    __table_args__ = (
        UniqueConstraint(
            "media_id", "analysis_type", name="uq_ai_analysis_media_type"
        ),
        {"comment": "AI-generated analysis results for media assets"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_type = Column(
        Enum(AnalysisType, name="analysistype", create_type=True),
        nullable=False,
    )
    result = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=True)
    model_used = Column(String(100), nullable=True)
    brand_identity_applied = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    media = relationship("MediaAsset", back_populates="ai_analyses")

    def __repr__(self) -> str:
        return (
            f"<AIImageAnalysis(id={self.id}, media_id={self.media_id}, "
            f"type='{self.analysis_type}', model='{self.model_used}')>"
        )


# ---------------------------------------------------------------------------
# branch_brand_identities
# ---------------------------------------------------------------------------


class BranchBrandIdentity(Base):
    """
    Per-branch brand identity configuration for creative consistency.

    Stores brand colors, tone of voice, target audience, and style guidelines
    that the AI uses to align generated content with the brand.

    Attributes:
        id: Primary key.
        branch_id: Associated branch.
        company_id: Owning company for tenant isolation.
        brand_name: Display name for the brand.
        primary_color: Hex primary brand color.
        secondary_color: Hex secondary brand color.
        accent_color: Hex accent brand color.
        brand_tone: Voice/tone of the brand.
        target_audience: Description of target demographic.
        industry: Business industry/category.
        language: Primary content language (e.g., 'tr', 'en').
        font_style: Preferred font style (modern, classic, playful, etc.).
        visual_style: Overall visual direction (minimal, vibrant, elegant, etc.).
        hashtags_always_include: Array of hashtags to always include.
        hashtags_never_include: Array of hashtags to avoid.
        competitors_to_differentiate: Array of competitor names for differentiation.
        is_active: Whether this brand identity is active.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "branch_brand_identities"
    __table_args__ = (
        UniqueConstraint("branch_id", name="uq_branch_brand_identity"),
        {"comment": "Per-branch brand identity for creative consistency"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Brand basics
    brand_name = Column(String(255), nullable=False)
    primary_color = Column(String(7), nullable=True, default="#6366F1")
    secondary_color = Column(String(7), nullable=True)
    accent_color = Column(String(7), nullable=True)

    # Brand voice & audience
    brand_tone = Column(
        Enum(BrandTone, name="brandtone", create_type=True),
        default=BrandTone.PROFESSIONAL,
        nullable=False,
    )
    target_audience = Column(Text, nullable=True)
    industry = Column(String(100), nullable=True)
    language = Column(String(10), nullable=False, default="tr")

    # Visual identity
    font_style = Column(String(50), nullable=True)
    visual_style = Column(String(50), nullable=True)

    # Hashtag rules
    hashtags_always_include = Column(JSON, nullable=True, default=list)
    hashtags_never_include = Column(JSON, nullable=True, default=list)

    # Competitive differentiation
    competitors_to_differentiate = Column(JSON, nullable=True, default=list)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<BranchBrandIdentity(id={self.id}, branch_id={self.branch_id}, "
            f"brand_name='{self.brand_name}', tone='{self.brand_tone}')>"
        )


# ---------------------------------------------------------------------------
# creative_audits
# ---------------------------------------------------------------------------


class CreativeAudit(Base):
    """
    AI creative audit record for media assets.

    Tracks creative fatigue detection, originality scoring, trend alignment,
    and historical audit results for portfolio analysis.

    Attributes:
        id: Primary key.
        media_id: Associated media asset.
        company_id: Owning company for tenant isolation.
        branch_id: Optional branch for branch-scoped audits.
        originality_score: 1-10 originality rating.
        fatigue_level: Detected fatigue severity.
        fatigue_signals: Array of detected fatigue signal strings.
        trend_alignment: JSON with trending themes and alignment scores.
        competitor_similarity_risk: Risk level of similarity to competitors.
        best_practices_checklist: JSON with checklist results.
        refresh_recommendations: Array of actionable refresh suggestions.
        engagement_prediction: JSON with predicted engagement metrics.
        similar_media_ids: Array of media IDs flagged as similar.
        audit_metadata: Free-form JSON for extensibility.
        created_at: Audit timestamp.
    """

    __tablename__ = "creative_audits"
    __table_args__ = (
        UniqueConstraint("media_id", name="uq_creative_audit_media"),
        {"comment": "AI creative audit results for media assets"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_id = Column(
        String(36),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Scoring
    originality_score = Column(Integer, nullable=True)  # 1-10
    fatigue_level = Column(
        Enum(FatigueLevel, name="fatiguelevel", create_type=True),
        default=FatigueLevel.NONE,
        nullable=False,
    )
    fatigue_signals = Column(JSON, nullable=True, default=list)

    # Trend & competitive analysis
    trend_alignment = Column(JSON, nullable=True, default=dict)
    competitor_similarity_risk = Column(String(20), nullable=True)

    # Best practices
    best_practices_checklist = Column(JSON, nullable=True, default=dict)
    refresh_recommendations = Column(JSON, nullable=True, default=list)

    # Predictions
    engagement_prediction = Column(JSON, nullable=True, default=dict)

    # Similarity detection
    similar_media_ids = Column(JSON, nullable=True, default=list)

    # Extensibility
    audit_metadata = Column(JSON, nullable=True, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    media = relationship("MediaAsset", back_populates="creative_audits")

    def __repr__(self) -> str:
        return (
            f"<CreativeAudit(id={self.id}, media_id={self.media_id}, "
            f"originality={self.originality_score}, fatigue='{self.fatigue_level}')>"
        )
