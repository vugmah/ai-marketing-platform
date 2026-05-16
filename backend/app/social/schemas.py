"""Pydantic v2 schemas for the social media integration module.

All schemas use strict validation and include proper examples for API docs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Shared Schemas
# =============================================================================


class PlatformEnum(str):
    """Platform string literal type."""

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    GOOGLE_MAPS = "google_maps"


class PaginatedResponse(BaseModel):
    """Base paginated response wrapper."""

    total: int = Field(..., description="Total record count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    items: List[Any] = Field(..., description="Paginated items")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 100,
            "page": 1,
            "page_size": 20,
            "items": [],
        }
    })


# =============================================================================
# Social Account Schemas
# =============================================================================


class SocialAccountBase(BaseModel):
    """Base fields for social account schemas."""

    platform: str = Field(..., description="Social media platform")
    account_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    account_id: str = Field(..., min_length=1, max_length=255, description="Platform account ID")
    profile_url: Optional[str] = Field(None, max_length=500, description="Public profile URL")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific settings")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class SocialAccountCreate(SocialAccountBase):
    """Schema for connecting a new social account."""

    access_token: str = Field(..., min_length=1, description="OAuth access token")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token")
    token_expires_at: Optional[datetime] = Field(None, description="Token expiration")


class SocialAccountUpdate(BaseModel):
    """Schema for updating account settings."""

    account_name: Optional[str] = Field(None, max_length=255)
    profile_url: Optional[str] = Field(None, max_length=500)
    settings: Optional[Dict[str, Any]] = None


class SocialAccountInDB(SocialAccountBase):
    """Schema representing an account as stored in the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    follower_count: int = 0
    status: str = "active"
    last_sync_at: Optional[datetime] = None
    webhook_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SocialAccountResponse(BaseModel):
    """API response for account endpoints (no sensitive tokens)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    platform: str
    account_name: str
    account_id: str
    profile_url: Optional[str] = None
    follower_count: int
    status: str
    last_sync_at: Optional[datetime] = None
    webhook_url: Optional[str] = None
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None


class SocialAccountListResponse(PaginatedResponse):
    """Paginated list of social accounts."""

    items: List[SocialAccountResponse] = Field(default_factory=list)


class TokenRefreshRequest(BaseModel):
    """Request to manually refresh an account token."""

    force: bool = Field(default=False, description="Force refresh even if not expired")


class TokenRefreshResponse(BaseModel):
    """Response after token refresh."""

    success: bool
    expires_at: Optional[datetime] = None
    message: str


# =============================================================================
# Social Post Schemas
# =============================================================================


class SocialPostBase(BaseModel):
    """Base fields for social post schemas."""

    content: str = Field(..., min_length=1, max_length=5000, description="Post text content")
    media_urls: List[str] = Field(default_factory=list, description="Media file URLs")
    hashtags: Optional[str] = Field(None, max_length=500, description="Hashtags")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled publish time")


class SocialPostCreate(SocialPostBase):
    """Schema for creating a new post."""

    account_id: int = Field(..., description="Target social account ID")
    platform: str = Field(..., description="Target platform")
    ai_generated: bool = Field(default=False, description="Was content AI-generated")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class SocialPostUpdate(BaseModel):
    """Schema for updating a draft or scheduled post."""

    content: Optional[str] = Field(None, max_length=5000)
    media_urls: Optional[List[str]] = None
    hashtags: Optional[str] = Field(None, max_length=500)
    scheduled_at: Optional[datetime] = None


class SocialPostInDB(SocialPostBase):
    """Schema representing a post as stored in the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    external_post_id: Optional[str] = None
    status: str = "draft"
    published_at: Optional[datetime] = None
    engagement_stats: Dict[str, Any]
    ai_generated: bool = False
    created_at: datetime
    updated_at: datetime


class SocialPostResponse(BaseModel):
    """API response for post endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    external_post_id: Optional[str] = None
    content: str
    media_urls: List[str]
    hashtags: Optional[str] = None
    status: str
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    engagement_stats: Dict[str, Any]
    ai_generated: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class SocialPostListResponse(PaginatedResponse):
    """Paginated list of social posts."""

    items: List[SocialPostResponse] = Field(default_factory=list)


class PublishNowRequest(BaseModel):
    """Request to publish a scheduled/draft post immediately."""

    pass


class PublishNowResponse(BaseModel):
    """Response after immediate publish attempt."""

    success: bool
    external_post_id: Optional[str] = None
    message: str


# =============================================================================
# Social Comment Schemas
# =============================================================================


class SocialCommentBase(BaseModel):
    """Base fields for social comment schemas."""

    content: str = Field(..., min_length=1, description="Comment text")


class SocialCommentCreate(SocialCommentBase):
    """Schema for creating a comment record (usually from sync)."""

    account_id: int
    post_id: int
    external_comment_id: Optional[str] = None
    parent_comment_id: Optional[str] = None
    author_name: str = Field(..., min_length=1)
    author_id: Optional[str] = None
    sentiment: Optional[str] = None

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"positive", "negative", "neutral"}
        if v not in allowed:
            raise ValueError(f"sentiment must be one of {allowed}")
        return v


class SocialCommentUpdate(BaseModel):
    """Schema for updating comment status."""

    status: Optional[str] = None
    sentiment: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"new", "read", "replied"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"positive", "negative", "neutral"}
        if v not in allowed:
            raise ValueError(f"sentiment must be one of {allowed}")
        return v


class SocialCommentResponse(BaseModel):
    """API response for comment endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    post_id: int
    external_comment_id: Optional[str] = None
    parent_comment_id: Optional[str] = None
    author_name: str
    author_id: Optional[str] = None
    content: str
    sentiment: Optional[str] = None
    status: str
    replied_content: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class SocialCommentListResponse(PaginatedResponse):
    """Paginated list of comments."""

    items: List[SocialCommentResponse] = Field(default_factory=list)


class CommentReplyRequest(BaseModel):
    """Request to reply to a comment."""

    reply_content: str = Field(..., min_length=1, max_length=2000, description="Reply text")


class CommentReplyResponse(BaseModel):
    """Response after replying to a comment."""

    success: bool
    reply_id: Optional[str] = None
    message: str


class CommentMarkReadResponse(BaseModel):
    """Response after marking a comment as read."""

    success: bool
    message: str


# =============================================================================
# Social Message Schemas
# =============================================================================


class SocialMessageBase(BaseModel):
    """Base fields for social message schemas."""

    content: str = Field(..., min_length=1, description="Message text")


class SocialMessageCreate(SocialMessageBase):
    """Schema for creating a message record."""

    account_id: int
    platform: str
    external_conversation_id: str
    external_message_id: Optional[str] = None
    sender_name: str = Field(..., min_length=1)
    sender_id: Optional[str] = None
    direction: str = Field(..., description="inbound or outbound")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        allowed = {"inbound", "outbound"}
        if v not in allowed:
            raise ValueError(f"direction must be one of {allowed}")
        return v


class SocialMessageResponse(BaseModel):
    """API response for message endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    external_conversation_id: str
    external_message_id: Optional[str] = None
    sender_name: str
    sender_id: Optional[str] = None
    content: str
    direction: str
    status: str
    sentiment: Optional[str] = None
    ai_suggested_reply: Optional[str] = None
    ai_auto_reply_sent: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None


class ConversationSummary(BaseModel):
    """Summary of a conversation thread."""

    external_conversation_id: str
    platform: str
    account_id: int
    participant_name: str
    last_message: str
    last_message_at: datetime
    unread_count: int
    messages: List[SocialMessageResponse] = Field(default_factory=list)


class ConversationListResponse(PaginatedResponse):
    """Paginated list of conversation summaries."""

    items: List[ConversationSummary] = Field(default_factory=list)


class MessageReplyRequest(BaseModel):
    """Request to reply to a conversation."""

    reply_content: str = Field(..., min_length=1, max_length=4000, description="Reply text")


class MessageReplyResponse(BaseModel):
    """Response after replying to a conversation."""

    success: bool
    message_id: Optional[str] = None
    message: str


class MarkReadResponse(BaseModel):
    """Response after marking messages as read."""

    success: bool
    marked_count: int = 0
    message: str


class AIReplySuggestion(BaseModel):
    """AI-generated reply suggestion for a conversation."""

    suggestion: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    tone: str = "professional"
    auto_send_enabled: bool = False
    message: str = ""


class ConversationSyncResponse(BaseModel):
    """Response after syncing conversations from a platform."""

    success: bool
    fetched: int = 0
    new_messages: int = 0
    message: str


class SentimentAnalysisResult(BaseModel):
    """Sentiment analysis result for a message."""

    sentiment: str = Field(..., pattern="^(positive|negative|neutral)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    escalated: bool = False
    message: str


# =============================================================================
# Social Analytics Schemas
# =============================================================================


class SocialAnalyticsBase(BaseModel):
    """Base fields for analytics schemas."""

    metric_date: datetime = Field(..., description="Date of the metrics")
    impressions: int = Field(default=0, ge=0)
    reach: int = Field(default=0, ge=0)
    engagement: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    followers_gained: int = Field(default=0)
    followers_lost: int = Field(default=0)


class SocialAnalyticsCreate(SocialAnalyticsBase):
    """Schema for creating an analytics snapshot."""

    account_id: int
    platform: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class SocialAnalyticsResponse(SocialAnalyticsBase):
    """API response for analytics endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    raw_data: Dict[str, Any]
    created_at: datetime


class AnalyticsDashboard(BaseModel):
    """Aggregated analytics dashboard response."""

    total_followers: int
    total_impressions: int
    total_engagement: int
    total_clicks: int
    followers_change_7d: int
    impressions_change_7d: int
    engagement_rate_avg: float
    platform_breakdown: List[Dict[str, Any]]
    daily_trend: List[Dict[str, Any]]


class AnalyticsQueryParams(BaseModel):
    """Query parameters for analytics endpoints."""

    account_id: Optional[int] = None
    platform: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SocialAnalyticsListResponse(PaginatedResponse):
    """Paginated list of analytics records."""

    items: List[SocialAnalyticsResponse] = Field(default_factory=list)


# =============================================================================
# Social Competitor Schemas
# =============================================================================


class SocialCompetitorBase(BaseModel):
    """Base fields for competitor schemas."""

    platform: str = Field(..., description="Competitor's platform")
    competitor_name: str = Field(..., min_length=1, max_length=255)
    competitor_account_id: str = Field(..., min_length=1, max_length=255)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class SocialCompetitorCreate(SocialCompetitorBase):
    """Schema for adding a new competitor."""

    pass


class SocialCompetitorUpdate(BaseModel):
    """Schema for updating competitor tracking."""

    competitor_name: Optional[str] = Field(None, max_length=255)


class SocialCompetitorResponse(BaseModel):
    """API response for competitor endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    platform: str
    competitor_name: str
    competitor_account_id: str
    follower_count: Optional[int] = None
    post_count: Optional[int] = None
    avg_engagement: Optional[float] = None
    last_analyzed_at: Optional[datetime] = None
    metrics_history: List[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime] = None


class SocialCompetitorListResponse(PaginatedResponse):
    """Paginated list of competitors."""

    items: List[SocialCompetitorResponse] = Field(default_factory=list)


# =============================================================================
# Webhook Schemas
# =============================================================================


class WebhookPayload(BaseModel):
    """Schema for incoming webhook payloads."""

    model_config = ConfigDict(extra="allow")


class WebhookEventResponse(BaseModel):
    """API response for webhook event records."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    account_id: Optional[int] = None
    platform: str
    event_type: str
    payload: Dict[str, Any]
    processed: bool
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime


class WebhookEventListResponse(PaginatedResponse):
    """Paginated list of webhook events."""

    items: List[WebhookEventResponse] = Field(default_factory=list)


class WebhookVerifyResponse(BaseModel):
    """Response after webhook verification challenge."""

    challenge: Optional[str] = None
    message: str = "Webhook received"


class WebhookProcessingStatus(BaseModel):
    """Webhook processing status summary."""

    total_events: int
    processed_count: int
    failed_count: int
    pending_count: int


# =============================================================================
# Publishing Queue Schemas
# =============================================================================


class QueueStatusEnum(str):
    """Queue status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PublishingQueueBase(BaseModel):
    """Base fields for publishing queue schemas."""

    sequence_order: int = Field(default=0, ge=0, description="Publishing sequence order")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled publish time")
    rate_limit_delay: int = Field(default=60, ge=0, description="Delay in seconds to next publish")


class PublishingQueueCreate(PublishingQueueBase):
    """Schema for adding a post to the publishing queue."""

    account_id: int = Field(..., description="Target social account ID")
    post_id: int = Field(..., description="Social post ID to publish")
    platform: str = Field(..., description="Target platform")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class PublishingQueueUpdate(BaseModel):
    """Schema for updating a queue item."""

    sequence_order: Optional[int] = Field(None, ge=0)
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    rate_limit_delay: Optional[int] = Field(None, ge=0)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"pending", "processing", "published", "failed", "cancelled"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class PublishingQueueResponse(BaseModel):
    """API response for publishing queue endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    post_id: int
    platform: str
    sequence_order: int
    status: str
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    retry_count: int
    last_error: Optional[str] = None
    rate_limit_delay: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class PublishingQueueListResponse(PaginatedResponse):
    """Paginated list of publishing queue items."""

    items: List[PublishingQueueResponse] = Field(default_factory=list)


class QueueProcessResult(BaseModel):
    """Result of processing the publishing queue."""

    processed: int
    succeeded: int
    failed: int
    skipped: int
    details: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Social Listening Schemas
# =============================================================================


class SocialListeningBase(BaseModel):
    """Base fields for social listening schemas."""

    platform: str = Field(..., description="Platform to monitor")
    listen_type: str = Field(..., description="Type: hashtag, mention, keyword")
    target: str = Field(..., min_length=1, max_length=255, description="Hashtag, username or keyword")
    is_active: bool = Field(default=True, description="Whether monitoring is active")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Additional settings")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v

    @field_validator("listen_type")
    @classmethod
    def validate_listen_type(cls, v: str) -> str:
        allowed = {"hashtag", "mention", "keyword"}
        if v not in allowed:
            raise ValueError(f"listen_type must be one of {allowed}")
        return v


class SocialListeningCreate(SocialListeningBase):
    """Schema for creating a listening entry."""

    pass


class SocialListeningUpdate(BaseModel):
    """Schema for updating a listening entry."""

    target: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class SocialListeningResponse(BaseModel):
    """API response for social listening endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    platform: str
    listen_type: str
    target: str
    is_active: bool
    last_result_count: int
    last_checked_at: Optional[datetime] = None
    results_summary: List[Dict[str, Any]]
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None


class SocialListeningListResponse(PaginatedResponse):
    """Paginated list of social listening entries."""

    items: List[SocialListeningResponse] = Field(default_factory=list)


class ListeningCheckResult(BaseModel):
    """Result of a listening check."""

    listening_id: int
    target: str
    platform: str
    results_found: int
    results: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Hashtag Intelligence Schemas
# =============================================================================


class HashtagIntelligenceBase(BaseModel):
    """Base fields for hashtag intelligence schemas."""

    hashtag: str = Field(..., min_length=1, max_length=100, description="Hashtag without #")
    platform: str = Field(..., description="Target platform")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class HashtagIntelligenceCreate(HashtagIntelligenceBase):
    """Schema for creating a hashtag intelligence entry."""

    post_count: int = Field(default=0, ge=0)
    engagement_avg: float = Field(default=0.0, ge=0)
    trend_direction: str = Field(default="stable")
    related_hashtags: List[str] = Field(default_factory=list)
    suggested_for: List[str] = Field(default_factory=list)

    @field_validator("trend_direction")
    @classmethod
    def validate_trend(cls, v: str) -> str:
        allowed = {"up", "down", "stable"}
        if v not in allowed:
            raise ValueError(f"trend_direction must be one of {allowed}")
        return v


class HashtagIntelligenceUpdate(BaseModel):
    """Schema for updating hashtag intelligence."""

    post_count: Optional[int] = Field(None, ge=0)
    engagement_avg: Optional[float] = Field(None, ge=0)
    trend_direction: Optional[str] = None
    related_hashtags: Optional[List[str]] = None
    suggested_for: Optional[List[str]] = None


class HashtagIntelligenceResponse(BaseModel):
    """API response for hashtag intelligence endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    platform: str
    hashtag: str
    post_count: int
    engagement_avg: Optional[float] = None
    trend_direction: str
    related_hashtags: List[str]
    suggested_for: List[str]
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class HashtagIntelligenceListResponse(PaginatedResponse):
    """Paginated list of hashtag intelligence entries."""

    items: List[HashtagIntelligenceResponse] = Field(default_factory=list)


class HashtagSuggestionRequest(BaseModel):
    """Request hashtag suggestions for a topic."""

    topic: str = Field(..., min_length=1, max_length=200, description="Topic or content description")
    platform: str = Field(..., description="Target platform")
    count: int = Field(default=10, ge=1, le=50, description="Number of suggestions")


class HashtagSuggestionResponse(BaseModel):
    """Response with hashtag suggestions."""

    topic: str
    platform: str
    suggestions: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Webhook Signature Verification Schemas
# =============================================================================


class WebhookSignatureVerifyRequest(BaseModel):
    """Request to verify a webhook signature."""

    platform: str = Field(..., description="Platform name")
    payload: str = Field(..., description="Raw webhook payload body")
    signature: str = Field(..., description="Signature header value")
    secret: Optional[str] = Field(None, description="Webhook secret (optional)")


class WebhookSignatureVerifyResponse(BaseModel):
    """Response after signature verification."""

    valid: bool
    platform: str
    message: str
