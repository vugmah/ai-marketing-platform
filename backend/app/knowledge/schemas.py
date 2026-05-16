"""Knowledge Ingestion - Pydantic Schemas.

Request/Response modelleri ve validasyon semalari.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# =============================================================================
# Enums
# =============================================================================

class IngestionSource(str, Enum):
    WEBSITE = "website"
    PDF = "pdf"
    DOCX = "docx"
    OCR = "ocr"
    SOCIAL_MEDIA = "social_media"
    MANUAL = "manual"
    CAMPAIGN = "campaign"
    VISUAL = "visual"


class IngestionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ChunkType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    BRAND_STATEMENT = "brand_statement"
    CAMPAIGN_DATA = "campaign_data"
    VISUAL_DESCRIPTION = "visual_description"


class BrandAttributeType(str, Enum):
    TONE = "tone"
    COLOR = "color"
    VALUE = "value"
    MISSION = "mission"
    VISION = "vision"
    SLOGAN = "slogan"
    PERSONALITY = "personality"
    TARGET_AUDIENCE = "target_audience"


# =============================================================================
# Base Schemas
# =============================================================================

class KnowledgeBaseBase(BaseModel):
    """Knowledge base temel semasi."""

    company_id: int
    branch_id: Optional[int] = None
    source_type: IngestionSource = IngestionSource.WEBSITE
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_description: Optional[str] = None
    content_metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseCreate(KnowledgeBaseBase):
    """Knowledge base olusturma semasi."""

    raw_content: Optional[str] = None


class KnowledgeBaseUpdate(BaseModel):
    """Knowledge base guncelleme semasi."""

    source_title: Optional[str] = None
    source_description: Optional[str] = None
    content_metadata: Optional[Dict[str, Any]] = None
    status: Optional[IngestionStatus] = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    """Knowledge base yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: IngestionStatus
    chunk_count: int = 0
    embedding_count: int = 0
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    """Knowledge base liste yaniti."""

    items: List[KnowledgeBaseResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Chunk Schemas
# =============================================================================

class KnowledgeChunkBase(BaseModel):
    """Chunk temel semasi."""

    knowledge_base_id: int
    company_id: int
    branch_id: Optional[int] = None
    chunk_type: ChunkType = ChunkType.PARAGRAPH
    content: str
    sequence: int = 0
    token_count: int = 0
    char_count: int = 0
    semantic_tags: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    source_section: Optional[str] = None
    source_heading: Optional[str] = None


class KnowledgeChunkCreate(KnowledgeChunkBase):
    """Chunk olusturma semasi."""
    pass


class KnowledgeChunkResponse(KnowledgeChunkBase):
    """Chunk yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class SemanticChunkRequest(BaseModel):
    """Semantic chunking istek semasi."""

    text: str = Field(..., min_length=1, description="Chunk'lanacak metin")
    chunk_size: int = Field(default=512, ge=128, le=2048, description="Hedef token sayisi")
    chunk_overlap: int = Field(default=64, ge=0, le=256, description="Overlap token sayisi")
    preserve_headings: bool = Field(default=True, description="Basliklarin korunup korunmayacagi")
    extract_keywords: bool = Field(default=True, description="Anahtar kelime cikarimi")


class SemanticChunkResponse(BaseModel):
    """Semantic chunking yanit semasi."""

    chunks: List[KnowledgeChunkResponse]
    total_chunks: int
    total_tokens: int
    avg_chunk_size: float
    processing_time_ms: float


# =============================================================================
# Embedding Schemas
# =============================================================================

class EmbeddingRequest(BaseModel):
    """Embedding uretim istek semasi."""

    knowledge_base_id: int
    model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    batch_size: int = Field(default=32, ge=1, le=128)


class EmbeddingResponse(BaseModel):
    """Embedding uretim yanit semasi."""

    knowledge_base_id: int
    embedding_count: int
    model_name: str
    dimension: int
    processing_time_ms: float


class SimilaritySearchRequest(BaseModel):
    """Benzerlik arama istek semasi."""

    query: str = Field(..., min_length=1, description="Arama sorgusu")
    company_id: int
    branch_id: Optional[int] = None
    top_k: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)
    chunk_types: Optional[List[ChunkType]] = None


class SimilaritySearchResult(BaseModel):
    """Benzerlik arama sonucu."""

    chunk_id: int
    knowledge_base_id: int
    content: str
    chunk_type: str
    similarity_score: float
    source_section: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class SimilaritySearchResponse(BaseModel):
    """Benzerlik arama yanit semasi."""

    query: str
    results: List[SimilaritySearchResult]
    total_results: int
    processing_time_ms: float


# =============================================================================
# Ingestion Schemas
# =============================================================================

class WebsiteIngestRequest(BaseModel):
    """Website ingestion istek semasi."""

    url: str = Field(..., min_length=1, description="Scrape edilecek URL")
    company_id: int
    branch_id: Optional[int] = None
    max_depth: int = Field(default=2, ge=1, le=5, description="Tarama derinligi")
    max_pages: int = Field(default=50, ge=1, le=200, description="Maksimum sayfa sayisi")
    follow_links: bool = Field(default=True, description="Baglantilari takip et")
    css_selector: Optional[str] = None
    exclude_patterns: List[str] = Field(default_factory=list)
    include_patterns: List[str] = Field(default_factory=list)


class FileIngestRequest(BaseModel):
    """Dosya ingestion istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    source_type: IngestionSource
    file_url: Optional[str] = None
    file_content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRIngestRequest(BaseModel):
    """OCR ingestion istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    image_url: str = Field(..., min_length=1, description="OCR uygulanacak gorsel URL")
    language: str = Field(default="tur")
    preprocess: bool = Field(default=True)


class IngestResponse(BaseModel):
    """Ingestion yanit semasi."""

    knowledge_base_id: int
    status: IngestionStatus
    message: str
    celery_task_id: Optional[str] = None
    estimated_time_seconds: int = 30


class IngestBatchRequest(BaseModel):
    """Toplu ingestion istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    sources: List[Union[WebsiteIngestRequest, FileIngestRequest]]
    process_parallel: bool = Field(default=True)


class IngestBatchResponse(BaseModel):
    """Toplu ingestion yanit semasi."""

    jobs: List[IngestResponse]
    total_jobs: int


# =============================================================================
# Brand Learning Schemas
# =============================================================================

class BrandProfileBase(BaseModel):
    """Brand profili temel semasi."""

    company_id: int
    branch_id: Optional[int] = None
    attribute_type: BrandAttributeType
    attribute_key: str
    attribute_value: str
    confidence_score: float = 0.5
    source: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class BrandProfileCreate(BrandProfileBase):
    pass


class BrandProfileUpdate(BaseModel):
    """Brand profili guncelleme semasi."""

    attribute_value: Optional[str] = None
    confidence_score: Optional[float] = None
    source: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class BrandProfileResponse(BrandProfileBase):
    """Brand profili yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_count: int = 1
    created_at: datetime
    updated_at: datetime


class BrandLearningRequest(BaseModel):
    """Brand ogrenme istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    source_type: str = Field(default="auto")
    source_content: Optional[str] = None
    source_url: Optional[str] = None
    analyze_tone: bool = Field(default=True)
    analyze_colors: bool = Field(default=True)
    analyze_values: bool = Field(default=True)
    analyze_personality: bool = Field(default=True)


class BrandLearningResponse(BaseModel):
    """Brand ogrenme yanit semasi."""

    company_id: int
    profiles_learned: int
    attribute_summary: Dict[str, int]
    processing_time_ms: float


class BrandIdentityResponse(BaseModel):
    """Marka kimligi tam yanit."""

    company_id: int
    branch_id: Optional[int] = None
    tone: Dict[str, Any] = Field(default_factory=dict)
    colors: List[Dict[str, Any]] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)
    personality: Dict[str, Any] = Field(default_factory=dict)
    mission: Optional[str] = None
    vision: Optional[str] = None
    slogans: List[str] = Field(default_factory=list)
    target_audience: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)


class BrandColorBase(BaseModel):
    """Brand rengi temel semasi."""

    company_id: int
    branch_id: Optional[int] = None
    hex_code: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    color_name: Optional[str] = None
    color_role: Optional[str] = None
    usage_area: Optional[str] = None
    usage_frequency: float = 0.0
    confidence: float = 0.5
    source: Optional[str] = None


class BrandColorCreate(BrandColorBase):
    pass


class BrandColorResponse(BrandColorBase):
    """Brand rengi yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Visual Learning Schemas
# =============================================================================

class VisualAssetBase(BaseModel):
    """Gorsel varlik temel semasi."""

    company_id: int
    branch_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    image_url: str
    image_type: Optional[str] = None
    source_url: Optional[str] = None


class VisualAssetCreate(VisualAssetBase):
    pass


class VisualAssetAnalyzeRequest(BaseModel):
    """Gorsel analiz istek semasi."""

    image_url: str
    company_id: int
    branch_id: Optional[int] = None
    analyze_colors: bool = Field(default=True)
    analyze_objects: bool = Field(default=True)
    analyze_text: bool = Field(default=True)
    analyze_composition: bool = Field(default=True)
    detect_brand_elements: bool = Field(default=True)


class VisualAssetResponse(VisualAssetBase):
    """Gorsel varlik yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    description: Optional[str] = None
    dominant_colors: List[Dict[str, Any]] = Field(default_factory=list)
    detected_objects: List[str] = Field(default_factory=list)
    detected_text: Optional[str] = None
    brand_elements: List[str] = Field(default_factory=list)
    composition_analysis: Dict[str, Any] = Field(default_factory=dict)
    style_tags: List[str] = Field(default_factory=list)
    is_brand_asset: bool = False
    brand_relevance_score: float = 0.0
    analyzed_at: Optional[datetime] = None
    created_at: datetime


class VisualLearningRequest(BaseModel):
    """Gorsel ogrenme istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    image_urls: List[str] = Field(..., min_length=1)
    source_type: str = Field(default="website")
    auto_detect_brand: bool = Field(default=True)


class VisualLearningResponse(BaseModel):
    """Gorsel ogrenme yanit semasi."""

    company_id: int
    images_analyzed: int
    brand_assets_found: int
    dominant_colors: List[Dict[str, Any]] = Field(default_factory=list)
    common_style_tags: List[str] = Field(default_factory=list)
    brand_elements_detected: List[str] = Field(default_factory=list)
    processing_time_ms: float


# =============================================================================
# Campaign Learning Schemas
# =============================================================================

class CampaignInsightBase(BaseModel):
    """Kampanya insight temel semasi."""

    company_id: int
    branch_id: Optional[int] = None
    knowledge_base_id: Optional[int] = None
    campaign_name: str
    campaign_type: Optional[str] = None
    platform: Optional[str] = None


class CampaignInsightCreate(CampaignInsightBase):
    """Kampanya insight olusturma semasi."""

    reach: Optional[int] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    spend: Optional[float] = None
    revenue: Optional[float] = None
    engagement_rate: Optional[float] = None
    ctr: Optional[float] = None
    roas: Optional[float] = None
    cpa: Optional[float] = None
    success_factors: List[str] = Field(default_factory=list)
    failure_factors: List[str] = Field(default_factory=list)
    ai_summary: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class CampaignInsightUpdate(BaseModel):
    """Kampanya insight guncelleme semasi."""

    reach: Optional[int] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    spend: Optional[float] = None
    revenue: Optional[float] = None
    engagement_rate: Optional[float] = None
    ctr: Optional[float] = None
    roas: Optional[float] = None
    cpa: Optional[float] = None
    success_factors: Optional[List[str]] = None
    failure_factors: Optional[List[str]] = None
    ai_summary: Optional[str] = None


class CampaignInsightResponse(CampaignInsightCreate):
    """Kampanya insight yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    audience_insights: Dict[str, Any] = Field(default_factory=dict)
    content_analysis: Dict[str, Any] = Field(default_factory=dict)
    timing_insights: Dict[str, Any] = Field(default_factory=dict)
    creative_analysis: Dict[str, Any] = Field(default_factory=dict)
    recommended_strategies: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CampaignLearningRequest(BaseModel):
    """Kampanya ogrenme istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    campaign_data: Optional[List[Dict[str, Any]]] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    platforms: Optional[List[str]] = None
    analyze_success_factors: bool = Field(default=True)
    recommend_strategies: bool = Field(default=True)


class CampaignLearningResponse(BaseModel):
    """Kampanya ogrenme yanit semasi."""

    company_id: int
    campaigns_analyzed: int
    success_factors: List[str] = Field(default_factory=list)
    failure_factors: List[str] = Field(default_factory=list)
    recommended_strategies: List[str] = Field(default_factory=list)
    audience_insights: Dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float


# =============================================================================
# Social Post Learning Schemas
# =============================================================================

class SocialPostLearningBase(BaseModel):
    """Sosyal medya ogrenme temel semasi."""

    company_id: int
    branch_id: Optional[int] = None
    platform: Optional[str] = None
    tone_label: Optional[str] = None


class SocialPostLearningCreate(SocialPostLearningBase):
    """Sosyal medya ogrenme olusturma semasi."""

    post_sample: Optional[str] = None
    language_style: Optional[str] = None
    emoji_usage: Optional[str] = None
    hashtag_pattern: List[str] = Field(default_factory=list)
    call_to_action_style: Optional[str] = None
    engagement_score: Optional[float] = None
    avg_sentence_length: Optional[float] = None
    vocabulary_richness: Optional[float] = None
    formality_score: Optional[float] = None
    post_count_analyzed: int = 0
    date_range: Dict[str, Any] = Field(default_factory=dict)


class SocialPostLearningResponse(SocialPostLearningCreate):
    """Sosyal medya ogrenme yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SocialToneRequest(BaseModel):
    """Sosyal medya ton analiz istek semasi."""

    company_id: int
    branch_id: Optional[int] = None
    platform: Optional[str] = None
    posts: List[str] = Field(..., min_length=1, max_length=100)


class SocialToneResponse(BaseModel):
    """Sosyal medya ton analiz yanit semasi."""

    company_id: int
    detected_tone: str
    language_style: str
    emoji_usage: str
    avg_sentence_length: float
    vocabulary_richness: float
    formality_score: float
    confidence: float
    recommendations: List[str] = Field(default_factory=list)


# =============================================================================
# Ingestion Job Schemas
# =============================================================================

class IngestionJobBase(BaseModel):
    """Ingestion job temel semasi."""

    knowledge_base_id: int
    company_id: int
    branch_id: Optional[int] = None
    job_type: str
    source_info: Dict[str, Any] = Field(default_factory=dict)


class IngestionJobCreate(IngestionJobBase):
    pass


class IngestionJobUpdate(BaseModel):
    """Ingestion job guncelleme semasi."""

    status: Optional[IngestionStatus] = None
    progress_percent: Optional[int] = None
    logs: Optional[List[str]] = None
    error_details: Optional[Dict[str, Any]] = None


class IngestionJobResponse(IngestionJobBase):
    """Ingestion job yanit semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    celery_task_id: Optional[str] = None
    status: IngestionStatus
    progress_percent: int = 0
    logs: List[str] = Field(default_factory=list)
    error_details: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Knowledge Query Schemas
# =============================================================================

class KnowledgeQueryRequest(BaseModel):
    """Knowledge base sorgu istek semasi."""

    query: str = Field(..., min_length=1)
    company_id: int
    branch_id: Optional[int] = None
    search_type: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None


class KnowledgeQueryResponse(BaseModel):
    """Knowledge base sorgu yanit semasi."""

    query: str
    results: List[SimilaritySearchResult]
    brand_context: Optional[Dict[str, Any]] = None
    processing_time_ms: float


class CompanyMemoryResponse(BaseModel):
    """Sirket hafizasi yanit semasi."""

    company_id: int
    branch_id: Optional[int] = None
    knowledge_base_count: int
    total_chunks: int
    total_embeddings: int
    brand_profiles: List[BrandProfileResponse]
    brand_colors: List[BrandColorResponse]
    visual_assets: List[VisualAssetResponse]
    campaign_insights: List[CampaignInsightResponse]
    last_updated: Optional[datetime] = None
