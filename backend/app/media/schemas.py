"""
Pydantic v2 schemas for the Creative Studio & Media Pipeline module.

Covers all CRUD operations, filtering, pagination, AI analysis schemas,
brand identity schemas, social optimization schemas, and creative audit schemas
for media assets, variants, tags, collections, and analytics.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.media.constants import (
    MAX_DOCUMENT_SIZE,
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
    ALLOWED_MIME_TYPES,
)


# ---------------------------------------------------------------------------
# Shared / base schemas
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=24, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Base paginated response wrapper."""

    total: int = Field(..., description="Total number of matching items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


class SortParams(BaseModel):
    """Query parameters for sorting list endpoints."""

    sort_by: str = Field(
        default="created_at",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort direction: asc or desc",
    )


# ---------------------------------------------------------------------------
# Media tag schemas
# ---------------------------------------------------------------------------


class MediaTagCreate(BaseModel):
    """Schema for creating a new media tag."""

    name: str = Field(..., min_length=1, max_length=100, description="Tag name")
    color: Optional[str] = Field(default="#6366F1", max_length=7, description="Hex color code")


class MediaTagUpdate(BaseModel):
    """Schema for updating a media tag."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    color: Optional[str] = Field(default=None, max_length=7)


class MediaTagResponse(BaseModel):
    """Schema for returning a media tag."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Tag ID")
    company_id: int = Field(..., description="Owning company ID")
    name: str = Field(..., description="Tag name")
    color: Optional[str] = Field(default=None, description="Hex color code")
    created_at: datetime = Field(..., description="Creation timestamp")
    usage_count: int = Field(default=0, description="Number of assets using this tag")


# ---------------------------------------------------------------------------
# Media variant schemas
# ---------------------------------------------------------------------------


class MediaVariantResponse(BaseModel):
    """Schema for returning a media variant."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Variant ID")
    media_id: str = Field(..., description="Parent media asset ID")
    variant_type: str = Field(..., description="Type of variant (thumbnail/webp/optimized/small/medium/large)")
    file_path: str = Field(..., description="Relative file path")
    width: Optional[int] = Field(default=None, description="Variant width in pixels")
    height: Optional[int] = Field(default=None, description="Variant height in pixels")
    file_size: int = Field(default=0, description="Variant file size in bytes")
    quality: Optional[int] = Field(default=None, description="Compression quality (0-100)")
    created_at: datetime = Field(..., description="Variant creation timestamp")
    url: Optional[str] = Field(default=None, description="Accessible URL for the variant")


# ---------------------------------------------------------------------------
# Media asset schemas
# ---------------------------------------------------------------------------


class MediaAssetCreate(BaseModel):
    """Schema for creating a media asset record (typically used internally)."""

    original_filename: str = Field(..., max_length=255, description="Original filename")
    mime_type: str = Field(..., max_length=100, description="MIME type")
    file_size: int = Field(default=0, ge=0, description="File size in bytes")
    width: Optional[int] = Field(default=None, ge=0, description="Width in pixels")
    height: Optional[int] = Field(default=None, ge=0, description="Height in pixels")
    duration: Optional[float] = Field(default=None, ge=0, description="Video duration in seconds")
    storage_provider: str = Field(default="", description="Storage backend (empty = use STORAGE_PROVIDER setting)")
    storage_key: Optional[str] = Field(default=None, max_length=500)
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class MediaAssetUpdate(BaseModel):
    """Schema for updating a media asset."""

    original_filename: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class MediaAssetResponse(BaseModel):
    """Schema for returning a media asset with all details."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Media asset ID (UUID)")
    company_id: int = Field(..., description="Owning company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    filename: str = Field(..., description="Stored unique filename")
    original_filename: str = Field(..., description="Original user filename")
    file_path: str = Field(..., description="Relative file path")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    category: str = Field(..., description="Category: image/video/document")
    width: Optional[int] = Field(default=None, description="Width in pixels")
    height: Optional[int] = Field(default=None, description="Height in pixels")
    duration: Optional[float] = Field(default=None, description="Video duration")
    thumbnail_path: Optional[str] = Field(default=None, description="Thumbnail path")
    storage_provider: str = Field(..., description="Storage backend")
    storage_key: Optional[str] = Field(default=None)
    checksum: Optional[str] = Field(default=None)
    status: str = Field(..., description="Processing status")
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    created_by: Optional[int] = Field(default=None, description="Uploader user ID")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    tags: List[MediaTagResponse] = Field(default_factory=list, description="Associated tags")
    variants: List[MediaVariantResponse] = Field(default_factory=list, description="Generated variants")
    views: int = Field(default=0, description="View count")
    downloads: int = Field(default=0, description="Download count")
    url: Optional[str] = Field(default=None, description="Accessible URL")
    virus_scan_status: str = Field(default="skipped", description="Virus scan status: pending/clean/infected/skipped/error")
    exif_data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted EXIF metadata (images only)")


class MediaAssetListItem(BaseModel):
    """Lightweight schema for listing media assets."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Media asset ID")
    filename: str = Field(..., description="Stored filename")
    original_filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type")
    category: str = Field(..., description="Category: image/video/document")
    file_size: int = Field(..., description="File size in bytes")
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    duration: Optional[float] = Field(default=None)
    status: str = Field(..., description="Processing status")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    created_at: datetime = Field(..., description="Upload timestamp")
    tag_names: List[str] = Field(default_factory=list, description="Tag names")
    virus_scan_status: str = Field(default="skipped", description="Virus scan status")


class MediaAssetListResponse(PaginatedResponse):
    """Paginated list of media assets."""

    items: List[MediaAssetListItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Media filter / search schemas
# ---------------------------------------------------------------------------


class MediaAssetFilter(BaseModel):
    """Query parameters for filtering media assets."""

    model_config = ConfigDict(from_attributes=True)

    category: Optional[str] = Field(
        default=None,
        description="Filter by category: image/video/document",
    )
    status: Optional[str] = Field(default=None, description="Filter by status")
    tags: Optional[List[int]] = Field(default=None, description="Filter by tag IDs")
    search: Optional[str] = Field(default=None, description="Search in filename")
    date_from: Optional[datetime] = Field(default=None, description="Uploaded on or after")
    date_to: Optional[datetime] = Field(default=None, description="Uploaded on or before")
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


# ---------------------------------------------------------------------------
# Upload schemas
# ---------------------------------------------------------------------------


class UploadInitiateRequest(BaseModel):
    """Schema for initiating a presigned URL upload."""

    filename: str = Field(..., max_length=255, description="Original filename")
    mime_type: str = Field(..., max_length=100, description="File MIME type")
    file_size: int = Field(..., gt=0, description="Expected file size in bytes")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        if value not in ALLOWED_MIME_TYPES:
            allowed_list = ", ".join(sorted(ALLOWED_MIME_TYPES))
            raise ValueError(f"Unsupported MIME type: {value}. Allowed: {allowed_list}")
        return value

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, value: int, info) -> int:
        mime = info.data.get("mime_type", "")
        if mime.startswith("image/") and value > MAX_IMAGE_SIZE:
            raise ValueError(f"Image exceeds max size of {MAX_IMAGE_SIZE} bytes")
        if mime.startswith("video/") and value > MAX_VIDEO_SIZE:
            raise ValueError(f"Video exceeds max size of {MAX_VIDEO_SIZE} bytes")
        if mime == "application/pdf" and value > MAX_DOCUMENT_SIZE:
            raise ValueError(f"PDF exceeds max size of {MAX_DOCUMENT_SIZE} bytes")
        return value


class PresignedUploadUrlResponse(BaseModel):
    """Schema for returning a presigned upload URL."""

    upload_url: str = Field(..., description="Presigned URL for direct upload")
    media_id: str = Field(..., description="Pre-allocated media asset ID")
    storage_key: str = Field(..., description="Storage key/path to upload to")
    expires_in: int = Field(..., description="URL expiry in seconds")
    fields: Optional[Dict[str, str]] = Field(default=None, description="Additional form fields for POST upload")


class UploadCompleteRequest(BaseModel):
    """Schema for confirming a direct upload is complete."""

    media_id: str = Field(..., description="Media asset ID")
    storage_key: str = Field(..., description="Storage key where file was uploaded")
    checksum: Optional[str] = Field(default=None, description="File SHA-256 checksum")


class UploadResponse(BaseModel):
    """Schema for returning a completed upload result."""

    media_id: str = Field(..., description="Media asset ID")
    filename: str = Field(..., description="Stored filename")
    original_filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Current processing status")
    url: Optional[str] = Field(default=None, description="Access URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    created_at: datetime = Field(..., description="Upload timestamp")


# ---------------------------------------------------------------------------
# Download / signed URL schemas
# ---------------------------------------------------------------------------


class SignedUrlResponse(BaseModel):
    """Schema for returning a signed download URL."""

    url: str = Field(..., description="Time-limited signed URL")
    expires_in: int = Field(..., description="URL expiry in seconds")
    filename: str = Field(..., description="Original filename for download")


class ThumbnailSizeParam(BaseModel):
    """Path parameter for thumbnail size."""

    size: str = Field(..., pattern="^(s|m|l|t)$", description="Thumbnail size: s=small, m=medium, l=large, t=thumbnail")


# ---------------------------------------------------------------------------
# Tag management schemas
# ---------------------------------------------------------------------------


class TagAddRequest(BaseModel):
    """Schema for adding tags to a media asset."""

    tag_ids: List[int] = Field(..., min_length=1, description="Tag IDs to add")


class BulkTagRequest(BaseModel):
    """Schema for bulk tagging media assets."""

    media_ids: List[str] = Field(..., min_length=1, description="Media asset IDs")
    tag_ids: List[int] = Field(..., min_length=1, description="Tag IDs to add")


class BulkDeleteRequest(BaseModel):
    """Schema for bulk deleting media assets."""

    media_ids: List[str] = Field(..., min_length=1, description="Media asset IDs to delete")


# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------


class MediaCollectionCreate(BaseModel):
    """Schema for creating a media collection."""

    name: str = Field(..., min_length=1, max_length=255, description="Collection name")
    description: Optional[str] = Field(default=None, max_length=2000, description="Collection description")
    cover_media_id: Optional[str] = Field(default=None, description="Media asset ID to use as cover")


class MediaCollectionUpdate(BaseModel):
    """Schema for updating a media collection."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    cover_media_id: Optional[str] = Field(default=None)


class MediaCollectionItemAdd(BaseModel):
    """Schema for adding items to a collection."""

    media_ids: List[str] = Field(..., min_length=1, description="Media asset IDs to add")
    order_index: Optional[int] = Field(default=None, description="Optional starting order index")


class MediaCollectionResponse(BaseModel):
    """Schema for returning a media collection."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Collection ID")
    company_id: int = Field(..., description="Owning company ID")
    branch_id: Optional[int] = Field(default=None)
    name: str = Field(..., description="Collection name")
    description: Optional[str] = Field(default=None)
    cover_media_id: Optional[str] = Field(default=None)
    cover_url: Optional[str] = Field(default=None, description="Cover image URL")
    item_count: int = Field(default=0, description="Number of items")
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)
    items: List[MediaAssetListItem] = Field(default_factory=list)


class MediaCollectionListResponse(PaginatedResponse):
    """Paginated list of media collections."""

    items: List[MediaCollectionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AI analysis schemas
# ---------------------------------------------------------------------------


class AIAnalysisRequest(BaseModel):
    """Schema for requesting AI analysis on a media asset."""

    analysis_type: str = Field(
        ...,
        pattern="^(caption|hashtag|score|objects|brand_alignment|instagram_optimize|creative_audit)$",
        description="Type of analysis to perform",
    )
    force_refresh: bool = Field(default=False, description="Re-run even if cached results exist")
    platform: Optional[str] = Field(default=None, description="Target platform: instagram/facebook/tiktok")
    language: Optional[str] = Field(default=None, description="Output language (e.g., 'tr', 'en')")
    max_chars: Optional[int] = Field(default=None, description="Max caption characters")


class AIAnalysisResult(BaseModel):
    """Schema for returning AI analysis results."""

    id: int = Field(..., description="Analysis record ID")
    media_id: str = Field(..., description="Media asset ID")
    analysis_type: str = Field(..., description="Type of analysis")
    result: Dict[str, Any] = Field(..., description="Structured analysis output")
    confidence: Optional[float] = Field(default=None, description="Confidence score 0-1")
    model_used: Optional[str] = Field(default=None, description="AI model identifier")
    brand_identity_applied: bool = Field(default=False, description="Whether brand identity was used")
    created_at: datetime = Field(..., description="Analysis timestamp")


class AIScoreResult(BaseModel):
    """Schema for AI image quality scoring results."""

    composition: int = Field(..., ge=0, le=100, description="Composition score")
    lighting: int = Field(..., ge=0, le=100, description="Lighting score")
    color: int = Field(..., ge=0, le=100, description="Color score")
    sharpness: int = Field(..., ge=0, le=100, description="Sharpness score")
    relevance: int = Field(..., ge=0, le=100, description="Relevance/engagement score")
    overall: int = Field(..., ge=0, le=100, description="Weighted overall score")
    explanation: Optional[str] = Field(default=None, description="Brief explanation")


class AIObjectDetectionResult(BaseModel):
    """Schema for AI object detection results."""

    label: str = Field(..., description="Detected object label")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    bounding_box: Optional[Dict[str, float]] = Field(default=None, description="Bounding box coordinates")


class AIAnalysisTypesResponse(BaseModel):
    """Schema for listing available analysis types."""

    analysis_types: List[str] = Field(default_factory=list)
    media_id: str = Field(...)
    existing_analyses: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Brand identity schemas
# ---------------------------------------------------------------------------


class BrandIdentityCreate(BaseModel):
    """Schema for creating a branch brand identity."""

    brand_name: str = Field(..., min_length=1, max_length=255, description="Brand display name")
    primary_color: Optional[str] = Field(default="#6366F1", max_length=7, description="Primary hex color")
    secondary_color: Optional[str] = Field(default=None, max_length=7, description="Secondary hex color")
    accent_color: Optional[str] = Field(default=None, max_length=7, description="Accent hex color")
    brand_tone: str = Field(
        default="professional",
        pattern="^(professional|casual|playful|luxury|friendly|bold|inspirational|informative|warm|modern)$",
        description="Brand voice/tone",
    )
    target_audience: Optional[str] = Field(default=None, description="Target demographic description")
    industry: Optional[str] = Field(default=None, max_length=100, description="Business industry")
    language: str = Field(default="tr", max_length=10, description="Primary content language")
    font_style: Optional[str] = Field(default=None, max_length=50, description="Preferred font style")
    visual_style: Optional[str] = Field(default=None, max_length=50, description="Visual direction")
    hashtags_always_include: List[str] = Field(default_factory=list, description="Always-use hashtags")
    hashtags_never_include: List[str] = Field(default_factory=list, description="Never-use hashtags")
    competitors_to_differentiate: List[str] = Field(default_factory=list, description="Competitor names")


class BrandIdentityUpdate(BaseModel):
    """Schema for updating a branch brand identity."""

    brand_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    primary_color: Optional[str] = Field(default=None, max_length=7)
    secondary_color: Optional[str] = Field(default=None, max_length=7)
    accent_color: Optional[str] = Field(default=None, max_length=7)
    brand_tone: Optional[str] = Field(
        default=None,
        pattern="^(professional|casual|playful|luxury|friendly|bold|inspirational|informative|warm|modern)$",
    )
    target_audience: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None, max_length=100)
    language: Optional[str] = Field(default=None, max_length=10)
    font_style: Optional[str] = Field(default=None, max_length=50)
    visual_style: Optional[str] = Field(default=None, max_length=50)
    hashtags_always_include: Optional[List[str]] = Field(default=None)
    hashtags_never_include: Optional[List[str]] = Field(default=None)
    competitors_to_differentiate: Optional[List[str]] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class BrandIdentityResponse(BaseModel):
    """Schema for returning a branch brand identity."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Brand identity ID")
    branch_id: int = Field(..., description="Branch ID")
    company_id: int = Field(..., description="Company ID")
    brand_name: str = Field(..., description="Brand display name")
    primary_color: Optional[str] = Field(default=None, description="Primary hex color")
    secondary_color: Optional[str] = Field(default=None, description="Secondary hex color")
    accent_color: Optional[str] = Field(default=None, description="Accent hex color")
    brand_tone: str = Field(..., description="Brand voice/tone")
    target_audience: Optional[str] = Field(default=None, description="Target demographic")
    industry: Optional[str] = Field(default=None, description="Business industry")
    language: str = Field(..., description="Primary content language")
    font_style: Optional[str] = Field(default=None, description="Preferred font style")
    visual_style: Optional[str] = Field(default=None, description="Visual direction")
    hashtags_always_include: List[str] = Field(default_factory=list)
    hashtags_never_include: List[str] = Field(default_factory=list)
    competitors_to_differentiate: List[str] = Field(default_factory=list)
    is_active: bool = Field(..., description="Whether active")
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)


# ---------------------------------------------------------------------------
# Social optimization schemas
# ---------------------------------------------------------------------------


class PlatformOptimizationResponse(BaseModel):
    """Schema for platform-specific optimization recommendations."""

    platform: str = Field(..., description="Social platform name")
    recommended_format: str = Field(..., description="Recommended post format")
    recommended_aspect_ratio: str = Field(..., description="Optimal aspect ratio")
    crop_suggestions: List[Dict[str, str]] = Field(default_factory=list, description="Crop region suggestions")
    text_overlay_suggestions: List[Dict[str, str]] = Field(default_factory=list, description="Text overlay ideas")
    color_adjustments: Dict[str, int] = Field(default_factory=dict, description="Color adjustment values")
    best_posting_time: str = Field(..., description="Optimal posting time")
    engagement_prediction: Dict[str, str] = Field(default_factory=dict, description="Predicted engagement")
    content_tips: List[str] = Field(default_factory=list, description="Content optimization tips")
    accessibility_notes: List[str] = Field(default_factory=list, description="Accessibility suggestions")
    specs: Dict[str, Any] = Field(default_factory=dict, description="Platform technical specs")


class MultiPlatformOptimizationResponse(BaseModel):
    """Schema for optimization across multiple platforms."""

    media_id: str = Field(..., description="Media asset ID")
    platforms: List[PlatformOptimizationResponse] = Field(default_factory=list)
    universal_tips: List[str] = Field(default_factory=list, description="Cross-platform tips")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Creative audit schemas
# ---------------------------------------------------------------------------


class CreativeAuditRequest(BaseModel):
    """Schema for requesting a creative audit."""

    compare_with_company_history: bool = Field(default=True, description="Compare with company's past creatives")
    compare_industry_benchmarks: bool = Field(default=False, description="Compare against industry benchmarks")
    detect_similarity: bool = Field(default=True, description="Detect similar existing creatives")
    force_refresh: bool = Field(default=False, description="Re-run even if cached")


class BestPracticesChecklist(BaseModel):
    """Schema for creative best practices checklist."""

    rule_of_thirds: bool = Field(default=False)
    leading_lines: bool = Field(default=False)
    negative_space: bool = Field(default=False)
    focal_point: bool = Field(default=False)
    color_contrast: bool = Field(default=False)


class CreativeAuditResult(BaseModel):
    """Schema for returning a creative audit result."""

    id: int = Field(..., description="Audit record ID")
    media_id: str = Field(..., description="Media asset ID")
    originality_score: int = Field(..., ge=1, le=10, description="Originality 1-10")
    fatigue_level: str = Field(..., description="Fatigue severity: none/low/medium/high/critical")
    fatigue_signals: List[str] = Field(default_factory=list, description="Detected fatigue signals")
    trend_alignment: Dict[str, Any] = Field(default_factory=dict, description="Trend alignment data")
    competitor_similarity_risk: str = Field(..., description="Risk level: low/medium/high")
    best_practices_checklist: BestPracticesChecklist = Field(default_factory=BestPracticesChecklist)
    refresh_recommendations: List[str] = Field(default_factory=list, description="Refresh suggestions")
    engagement_prediction: Dict[str, Any] = Field(default_factory=dict, description="Predicted engagement")
    similar_media_ids: List[str] = Field(default_factory=list, description="Similar media IDs")
    created_at: datetime = Field(...)


class CreativeAuditSummary(BaseModel):
    """Schema for summarizing creative audit across a portfolio."""

    total_audited: int = Field(..., description="Total assets audited")
    average_originality: float = Field(..., description="Average originality score")
    fatigue_distribution: Dict[str, int] = Field(default_factory=dict, description="Fatigue level counts")
    high_fatigue_count: int = Field(default=0, description="Assets with high/critical fatigue")
    trend_alignment_pct: float = Field(default=0.0, description="Percentage aligned with trends")
    top_recommendations: List[str] = Field(default_factory=list, description="Top portfolio-wide recommendations")
    assets_needing_refresh: List[str] = Field(default_factory=list, description="Media IDs needing refresh")


# ---------------------------------------------------------------------------
# Job queue schemas
# ---------------------------------------------------------------------------


class JobStatusResponse(BaseModel):
    """Schema for returning async job status."""

    job_id: str = Field(..., description="Job identifier")
    job_type: str = Field(..., description="Type of processing job")
    status: str = Field(..., description="Current status: pending/running/completed/failed")
    progress: Optional[int] = Field(default=None, ge=0, le=100, description="Progress percentage")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Job result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# Stats / analytics schemas
# ---------------------------------------------------------------------------


class MediaStatsResponse(BaseModel):
    """Schema for media usage statistics."""

    total_assets: int = Field(..., description="Total media assets")
    total_size: int = Field(..., description="Total storage size in bytes")
    image_count: int = Field(..., description="Number of images")
    video_count: int = Field(..., description="Number of videos")
    document_count: int = Field(..., description="Number of documents")
    processing_count: int = Field(..., description="Assets still processing")
    error_count: int = Field(..., description="Assets with errors")
    total_views: int = Field(..., description="Total view count")
    total_downloads: int = Field(..., description="Total download count")
    collection_count: int = Field(..., description="Number of collections")
    tag_count: int = Field(..., description="Number of tags")
    storage_by_provider: Dict[str, int] = Field(default_factory=dict, description="Asset count per storage provider")
    virus_scan_summary: Dict[str, int] = Field(default_factory=dict, description="Asset count per virus scan status")
    recent_uploads: List[MediaAssetListItem] = Field(default_factory=list, description="5 most recent uploads")


# ---------------------------------------------------------------------------
# Bulk operation response schemas
# ---------------------------------------------------------------------------


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation results."""

    success_count: int = Field(..., description="Number of successful operations")
    failed_count: int = Field(default=0, description="Number of failed operations")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="Error details per failed item")
    processed_ids: List[str] = Field(default_factory=list, description="IDs that were successfully processed")
