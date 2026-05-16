"""Pydantic v2 schemas for the Follower Intelligence module.

All schemas use strict validation and include proper examples for API docs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Shared / Base Schemas
# =============================================================================


class PaginatedResponse(BaseModel):
    """Base paginated response wrapper."""

    total: int = Field(..., description="Total record count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    items: List[Any] = Field(default_factory=list, description="Paginated items")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 100,
            "page": 1,
            "page_size": 20,
            "items": [],
        }
    })


# =============================================================================
# Follower Snapshot Schemas
# =============================================================================


class FollowerSnapshotBase(BaseModel):
    """Base fields for follower snapshot schemas."""

    platform: str = Field(..., description="Social media platform")
    external_account_id: str = Field(..., min_length=1, max_length=255)
    follower_count: int = Field(default=0, ge=0)
    following_count: Optional[int] = Field(default=0, ge=0)
    post_count: Optional[int] = Field(default=0, ge=0)
    snapshot_date: datetime = Field(..., description="Snapshot timestamp")
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class FollowerSnapshotCreate(FollowerSnapshotBase):
    """Schema for creating a new follower snapshot."""

    account_id: int = Field(..., description="Linked social account ID")


class FollowerSnapshotResponse(FollowerSnapshotBase):
    """API response for follower snapshot endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    created_at: datetime


class FollowerSnapshotListResponse(PaginatedResponse):
    """Paginated list of follower snapshots."""

    items: List[FollowerSnapshotResponse] = Field(default_factory=list)


class FollowerSyncSummary(BaseModel):
    """Summary of a follower sync operation."""

    account_id: int
    platform: str
    old_follower_count: int
    new_follower_count: int
    gained: int
    lost: int
    snapshot_id: int
    sync_date: datetime


class FollowerGrowthTrend(BaseModel):
    """Follower growth trend data point."""

    date: str = Field(..., description="ISO date string")
    follower_count: int
    following_count: int
    net_change: int
    daily_growth_rate: float = Field(description="Daily growth rate percentage")


# =============================================================================
# Bot Detection Schemas
# =============================================================================


class BotSignal(BaseModel):
    """Individual bot detection signal."""

    signal_type: str = Field(..., description="Type of signal detected")
    description: str
    score_contribution: float = Field(..., description="Contribution to bot score (0.0-1.0)")
    detected_value: Optional[str] = None


class BotPatternBase(BaseModel):
    """Base fields for bot pattern schemas."""

    platform: str
    detected_username: str = Field(..., min_length=1, max_length=255)
    detected_account_id: str = Field(..., min_length=1, max_length=255)
    has_profile_pic: Optional[bool] = None
    post_count: Optional[int] = Field(default=0, ge=0)
    follower_count: Optional[int] = Field(default=0, ge=0)
    following_count: Optional[int] = Field(default=0, ge=0)
    account_age_days: Optional[int] = None
    bio_text: Optional[str] = None
    is_verified: bool = False
    is_private: bool = False

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class BotPatternCreate(BotPatternBase):
    """Schema for creating a bot pattern record."""

    account_id: int
    bot_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: str = Field(..., description="low, medium, high, critical")
    signals: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"risk_level must be one of {allowed}")
        return v


class BotPatternResponse(BotPatternBase):
    """API response for bot pattern endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    bot_score: float
    risk_level: str
    signals: Dict[str, Any]
    detected_at: datetime
    reviewed: bool
    review_result: str
    created_at: datetime


class BotDetectionResult(BaseModel):
    """Result of a bot detection analysis run."""

    account_id: int
    platform: str
    total_analyzed: int
    bots_detected: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    bot_percentage: float
    average_bot_score: float
    risk_distribution: Dict[str, int]
    top_signals: List[str]
    detected_accounts: List[BotPatternResponse] = Field(default_factory=list)


class BotPatternListResponse(PaginatedResponse):
    """Paginated list of bot patterns."""

    items: List[BotPatternResponse] = Field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None


# =============================================================================
# Suspicious Activity Schemas
# =============================================================================


class SuspiciousActivityBase(BaseModel):
    """Base fields for suspicious activity schemas."""

    platform: str
    alert_type: str = Field(..., description="Type of alert")
    severity: str = Field(..., description="low, medium, high, critical")
    description: str = Field(..., min_length=1)
    affected_followers: int = Field(default=0, ge=0)
    baseline_value: Optional[float] = None
    actual_value: Optional[float] = None
    deviation_pct: Optional[float] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    start_date: datetime

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        allowed = {
            "sudden_spike",
            "sudden_drop",
            "bot_influx",
            "low_engagement",
            "inactive_followers",
            "suspicious_activity",
        }
        if v not in allowed:
            raise ValueError(f"alert_type must be one of {allowed}")
        return v


class SuspiciousActivityCreate(SuspiciousActivityBase):
    """Schema for creating a suspicious activity record."""

    account_id: int


class SuspiciousActivityResponse(SuspiciousActivityBase):
    """API response for suspicious activity endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    end_date: Optional[datetime] = None
    resolved: bool
    created_at: datetime


class FollowerAlert(BaseModel):
    """Active alert summary for dashboard."""

    alert_type: str
    severity: str
    count: int
    latest_occurrence: Optional[datetime] = None
    affected_accounts: List[int] = Field(default_factory=list)


class SuspiciousActivityListResponse(PaginatedResponse):
    """Paginated list of suspicious activities."""

    items: List[SuspiciousActivityResponse] = Field(default_factory=list)
    active_alerts: List[FollowerAlert] = Field(default_factory=list)


# =============================================================================
# Audience Demographics Schemas
# =============================================================================


class AgeDistribution(BaseModel):
    """Age range distribution."""

    range_13_17: float = Field(default=0.0, ge=0.0, le=100.0)
    range_18_24: float = Field(default=0.0, ge=0.0, le=100.0)
    range_25_34: float = Field(default=0.0, ge=0.0, le=100.0)
    range_35_44: float = Field(default=0.0, ge=0.0, le=100.0)
    range_45_54: float = Field(default=0.0, ge=0.0, le=100.0)
    range_55_64: float = Field(default=0.0, ge=0.0, le=100.0)
    range_65_plus: float = Field(default=0.0, ge=0.0, le=100.0)


class GenderDistribution(BaseModel):
    """Gender distribution."""

    male: float = Field(default=0.0, ge=0.0, le=100.0)
    female: float = Field(default=0.0, ge=0.0, le=100.0)
    unknown: float = Field(default=100.0, ge=0.0, le=100.0)


class AudienceDemographicsBase(BaseModel):
    """Base fields for audience demographics schemas."""

    platform: str
    age_distribution: AgeDistribution = Field(default_factory=AgeDistribution)
    gender_distribution: GenderDistribution = Field(default_factory=GenderDistribution)
    top_locations: Dict[str, Any] = Field(
        default_factory=lambda: {"cities": [], "countries": []}
    )
    top_languages: List[Dict[str, Any]] = Field(default_factory=list)
    interests: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_accounts: int = Field(default=0, ge=0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class AudienceDemographicsCreate(AudienceDemographicsBase):
    """Schema for creating audience demographics."""

    account_id: int
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class AudienceDemographicsResponse(AudienceDemographicsBase):
    """API response for audience demographics endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    analysis_date: datetime
    raw_data: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None


class AudienceDemographicsListResponse(PaginatedResponse):
    """Paginated list of audience demographics."""

    items: List[AudienceDemographicsResponse] = Field(default_factory=list)


# =============================================================================
# Engagement Quality Schemas
# =============================================================================


class QualityFactors(BaseModel):
    """Breakdown of engagement quality factors."""

    engagement_rate_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    comment_quality_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    reach_efficiency_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    consistency_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    share_ratio_factor: float = Field(default=0.0, ge=0.0, le=1.0)


class EngagementQualityBase(BaseModel):
    """Base fields for engagement quality schemas."""

    platform: str
    engagement_rate: float = Field(default=0.0, ge=0.0)
    like_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    share_count: int = Field(default=0, ge=0)
    reach_count: int = Field(default=0, ge=0)
    impression_count: int = Field(default=0, ge=0)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class EngagementQualityCreate(EngagementQualityBase):
    """Schema for creating engagement quality record."""

    account_id: int
    post_id: Optional[int] = None
    period_start: datetime
    period_end: datetime
    like_to_comment_ratio: float = Field(default=0.0, ge=0.0)
    reach_to_follower_ratio: float = Field(default=0.0, ge=0.0)
    consistency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tier: str = Field(default="average", description="elite, high, average, low, very_low")
    factors: Dict[str, float] = Field(default_factory=dict)

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = {"elite", "high", "average", "low", "very_low"}
        if v not in allowed:
            raise ValueError(f"tier must be one of {allowed}")
        return v


class EngagementQualityResponse(EngagementQualityBase):
    """API response for engagement quality endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    post_id: Optional[int] = None
    period_start: datetime
    period_end: datetime
    like_to_comment_ratio: float
    reach_to_follower_ratio: float
    consistency_score: float
    quality_score: float
    tier: str
    factors: Dict[str, float]
    created_at: datetime


class QualityMetrics(BaseModel):
    """Aggregated quality metrics for a period."""

    average_engagement_rate: float
    average_like_to_comment_ratio: float
    average_reach_to_follower_ratio: float
    consistency_score: float
    overall_quality_score: float
    tier: str
    trend_direction: str = Field(default="stable", description="improving, declining, stable")


class EngagementQualityListResponse(PaginatedResponse):
    """Paginated list of engagement quality records."""

    items: List[EngagementQualityResponse] = Field(default_factory=list)
    summary: Optional[QualityMetrics] = None


# =============================================================================
# Follower Health Score Schemas
# =============================================================================


class FollowerHealthDetail(BaseModel):
    """Detailed health score breakdown."""

    engagement_quality_score: int = Field(..., ge=0, le=100)
    bot_ratio_score: int = Field(..., ge=0, le=100)
    growth_stability_score: int = Field(..., ge=0, le=100)
    audience_diversity_score: int = Field(..., ge=0, le=100)
    activity_recency_score: int = Field(..., ge=0, le=100)


class FollowerHealthBase(BaseModel):
    """Base fields for follower health schemas."""

    platform: str
    overall_score: int = Field(default=50, ge=0, le=100)
    bot_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    inactive_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    engagement_rate_pct: float = Field(default=0.0, ge=0.0)
    growth_rate_pct: float = Field(default=0.0)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class FollowerHealthCreate(FollowerHealthBase):
    """Schema for creating a health score record."""

    account_id: int
    component_scores: FollowerHealthDetail
    status: str = Field(default="moderate", description="excellent, good, moderate, poor, critical")
    recommendations: List[str] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"excellent", "good", "moderate", "poor", "critical"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class FollowerHealthResponse(FollowerHealthBase):
    """API response for follower health endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    status: str
    component_scores: FollowerHealthDetail
    recommendations: List[str]
    score_date: datetime
    created_at: datetime


class FollowerHealthListResponse(PaginatedResponse):
    """Paginated list of follower health scores."""

    items: List[FollowerHealthResponse] = Field(default_factory=list)
    average_score: Optional[float] = None


# =============================================================================
# Follower Insight Schemas
# =============================================================================


class FollowerInsightBase(BaseModel):
    """Base fields for follower insight schemas."""

    platform: str
    follower_username: str = Field(..., min_length=1, max_length=255)
    follower_account_id: str = Field(..., min_length=1, max_length=255)
    estimated_gender: str = Field(default="unknown", description="male, female, unknown")
    estimated_age_range: Optional[str] = Field(None, max_length=20)
    estimated_location: Optional[str] = Field(None, max_length=255)
    account_type: str = Field(default="unknown", description="personal, business, creator, brand, unknown")
    is_active: bool = True
    last_activity_at: Optional[datetime] = None
    engagement_count: int = Field(default=0, ge=0)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v

    @field_validator("estimated_gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        allowed = {"male", "female", "unknown"}
        if v not in allowed:
            raise ValueError(f"estimated_gender must be one of {allowed}")
        return v

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        allowed = {"personal", "business", "creator", "brand", "unknown"}
        if v not in allowed:
            raise ValueError(f"account_type must be one of {allowed}")
        return v


class FollowerInsightCreate(FollowerInsightBase):
    """Schema for creating a follower insight record."""

    account_id: int
    bot_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_flagged: bool = False
    flag_reason: Optional[str] = Field(None, max_length=255)
    raw_profile: Dict[str, Any] = Field(default_factory=dict)


class FollowerInsightResponse(FollowerInsightBase):
    """API response for follower insight endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    bot_score: float
    is_flagged: bool
    flag_reason: Optional[str] = None
    raw_profile: Dict[str, Any]
    analyzed_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None


class FollowerInsightListResponse(PaginatedResponse):
    """Paginated list of follower insights."""

    items: List[FollowerInsightResponse] = Field(default_factory=list)
    flagged_count: Optional[int] = None
    bot_distribution: Optional[Dict[str, int]] = None


# =============================================================================
# AI Audience Recommendation Schemas
# =============================================================================


class TargetAudience(BaseModel):
    """Target demographic specification."""

    age_ranges: List[str] = Field(default_factory=list)
    genders: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)


class PostingTimeSlot(BaseModel):
    """Optimal posting time recommendation."""

    day: str
    hour: int = Field(..., ge=0, le=23)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ContentSuggestion(BaseModel):
    """AI-generated content suggestion."""

    type: str
    title: str
    description: str
    expected_engagement: float = Field(..., ge=0.0)


class AIAudienceRecommendationBase(BaseModel):
    """Base fields for AI recommendation schemas."""

    platform: str
    recommendation_type: str = Field(
        ...,
        description="demographics, content, timing, growth, retention, engagement"
    )
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v

    @field_validator("recommendation_type")
    @classmethod
    def validate_rec_type(cls, v: str) -> str:
        allowed = {"demographics", "content", "timing", "growth", "retention", "engagement"}
        if v not in allowed:
            raise ValueError(f"recommendation_type must be one of {allowed}")
        return v


class TargetAudienceSuggestion(BaseModel):
    """AI-generated target audience suggestion."""

    segment_name: str
    age_range: str
    gender: str
    interests: List[str] = Field(default_factory=list)
    estimated_size: Optional[int] = None
    engagement_potential: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str


class AIAudienceRecommendationCreate(AIAudienceRecommendationBase):
    """Schema for creating an AI recommendation."""

    account_id: int
    target_demographics: Dict[str, Any] = Field(
        default_factory=lambda: {
            "age_ranges": [],
            "genders": [],
            "locations": [],
            "interests": [],
        }
    )
    suggested_hashtags: List[str] = Field(default_factory=list)
    optimal_posting_times: Dict[str, Any] = Field(
        default_factory=lambda: {"weekdays": {}, "weekends": {}}
    )
    content_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    expected_impact: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AIAudienceRecommendationResponse(AIAudienceRecommendationBase):
    """API response for AI recommendation endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    target_demographics: Dict[str, Any]
    suggested_hashtags: List[str]
    optimal_posting_times: Dict[str, Any]
    content_suggestions: List[Dict[str, Any]]
    expected_impact: int
    confidence: float
    implemented: bool
    implementation_result: Optional[str] = None
    generated_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None


class AIAudienceRecommendationListResponse(PaginatedResponse):
    """Paginated list of AI recommendations."""

    items: List[AIAudienceRecommendationResponse] = Field(default_factory=list)


# =============================================================================
# Dashboard / Aggregate Schemas
# =============================================================================


class FollowerDashboard(BaseModel):
    """Comprehensive follower intelligence dashboard."""

    account_id: int
    platform: str
    current_followers: int
    followers_7d_change: int
    followers_30d_change: int
    growth_rate: float
    health_score: int
    health_status: str
    bot_percentage: float
    inactive_percentage: float
    engagement_rate: float
    engagement_tier: str
    top_bot_signals: List[str] = Field(default_factory=list)
    recent_alerts: List[FollowerAlert] = Field(default_factory=list)
    demographics_summary: Optional[AudienceDemographicsResponse] = None
    ai_recommendations: List[AIAudienceRecommendationResponse] = Field(default_factory=list)


class FollowerAnalysisRequest(BaseModel):
    """Request to run a follower analysis."""

    account_id: int
    platform: str = Field(default="instagram")
    analysis_types: List[str] = Field(
        default_factory=lambda: [
            "bot_detection",
            "demographics",
            "engagement_quality",
            "health_score",
            "ai_recommendations",
        ]
    )
    lookback_days: int = Field(default=90, ge=7, le=365)
    follower_profiles: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("analysis_types")
    @classmethod
    def validate_types(cls, v: List[str]) -> List[str]:
        allowed = {
            "bot_detection",
            "demographics",
            "engagement_quality",
            "health_score",
            "ai_recommendations",
            "suspicious_activity",
        }
        invalid = [t for t in v if t not in allowed]
        if invalid:
            raise ValueError(f"Invalid analysis types: {invalid}. Allowed: {allowed}")
        return v


class FollowerAnalysisResponse(BaseModel):
    """Response from a comprehensive follower analysis."""

    account_id: int
    platform: str
    analysis_date: datetime
    bot_detection: Optional[BotDetectionResult] = None
    demographics: Optional[AudienceDemographicsResponse] = None
    engagement_quality: Optional[QualityMetrics] = None
    health_score: Optional[FollowerHealthResponse] = None
    suspicious_activities: List[SuspiciousActivityResponse] = Field(default_factory=list)
    ai_recommendations: List[AIAudienceRecommendationResponse] = Field(default_factory=list)
    processing_time_seconds: float


# =============================================================================
# Delta Event Schemas
# =============================================================================


class FollowerDeltaEventResponse(BaseModel):
    """Response schema for a follower delta event."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    event_type: str
    previous_snapshot_id: int
    current_snapshot_id: int
    follower_delta: int
    estimated_new: int
    estimated_unfollow: int
    confidence_score: float
    confidence_reason: Optional[str] = None
    is_suspicious: bool
    event_date: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class FollowerDeltaEventListResponse(BaseModel):
    """Paginated list of follower delta events."""

    total: int
    page: int
    page_size: int
    items: List[FollowerDeltaEventResponse]


class FollowerDeltaSummaryResponse(BaseModel):
    """Summary of follower delta events."""

    period_days: int
    total_events: int
    estimated_new_followers: int
    estimated_unfollows: int
    net_change: int
    suspicious_events: int
    average_confidence: float
    note: str


# =============================================================================
# Engagement Event Schemas
# =============================================================================


class EngagementEventCreate(BaseModel):
    """Schema for creating an engagement event."""

    event_type: str
    follower_account_id: Optional[str] = None
    follower_username: Optional[str] = None
    post_id: Optional[str] = None
    message_preview: Optional[str] = None
    sentiment: str = "neutral"
    is_new_lead: bool = False
    lead_score: float = 0.0
    campaign_id: Optional[str] = None
    event_date: Optional[datetime] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class EngagementEventResponse(BaseModel):
    """Response schema for an engagement event."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    event_type: str
    follower_account_id: Optional[str] = None
    follower_username: Optional[str] = None
    post_id: Optional[str] = None
    message_preview: Optional[str] = None
    sentiment: str
    is_new_lead: bool
    lead_score: float
    campaign_id: Optional[str] = None
    event_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EngagementEventListResponse(BaseModel):
    """Paginated list of engagement events."""

    total: int
    page: int
    page_size: int
    items: List[EngagementEventResponse]


class NewEngagementSummaryResponse(BaseModel):
    """Summary of new engagements."""

    period_days: int
    total_events: int
    new_leads: int
    events_by_type: Dict[str, int] = Field(default_factory=dict)


# =============================================================================
# Reengagement Schemas
# =============================================================================


class ReengagementRecommendationResponse(BaseModel):
    """Response schema for a re-engagement recommendation."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    reengagement_type: str
    target_follower_id: Optional[str] = None
    target_follower_username: Optional[str] = None
    target_segment: Optional[str] = None
    ai_suggested_message: Optional[str] = None
    ai_suggested_subject: Optional[str] = None
    confidence_score: float
    expected_response_rate: float
    approval_status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReengagementRecommendationListResponse(BaseModel):
    """Paginated list of re-engagement recommendations."""

    total: int
    pending: int
    page: int
    page_size: int
    items: List[ReengagementRecommendationResponse]


class GenerateReengagementRequest(BaseModel):
    """Request to generate a re-engagement recommendation."""

    account_id: int
    platform: str
    reengagement_type: str = Field(..., description="welcome_new_follower, campaign_suggestion, reengagement_for_low, win_back_unfollow, dm_follow_up, local_branch_campaign")
    target_follower_id: Optional[str] = None
    target_username: Optional[str] = None
    target_segment: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    confidence: float = 0.65


class RequestApprovalRequest(BaseModel):
    """Request to create an approval request."""

    reengagement_id: int


class ReviewApprovalRequest(BaseModel):
    """Request to review an approval."""

    approved: bool
    notes: Optional[str] = None


class SendApprovedRequest(BaseModel):
    """Request to send an approved message."""

    approval_id: int


class OutreachApprovalResponse(BaseModel):
    """Response schema for an outreach approval request."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    reengagement_id: Optional[int] = None
    platform: str
    recipient_account_id: Optional[str] = None
    recipient_username: Optional[str] = None
    message_subject: Optional[str] = None
    message_body: str
    message_type: str
    status: str
    policy_check_result: str
    policy_check_details: Optional[str] = None
    requested_by: Optional[int] = None
    requested_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    sent_at: Optional[datetime] = None
    sent_by: Optional[int] = None
    send_result: Optional[str] = None

    class Config:
        from_attributes = True


class OutreachApprovalListResponse(BaseModel):
    """Paginated list of outreach approval requests."""

    total: int
    page: int
    page_size: int
    items: List[OutreachApprovalResponse]


# =============================================================================
# Audience Loss Schemas
# =============================================================================


class AudienceLossEstimateResponse(BaseModel):
    """Response schema for an audience loss estimate."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    loss_type: str
    estimated_loss_count: int
    confidence_score: float
    confidence_reason: Optional[str] = None
    previous_follower_count: int
    current_follower_count: int
    net_change: int
    is_suspicious: bool
    triggered_alert: bool
    estimate_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Follower Value Schemas
# =============================================================================


class FollowerValueScoreResponse(BaseModel):
    """Response schema for a follower value score."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    account_id: int
    platform: str
    follower_account_id: str
    follower_username: Optional[str] = None
    value_tier: str
    engagement_frequency: float
    last_engagement_at: Optional[datetime] = None
    total_engagements: int
    engagement_quality_avg: float
    days_since_engagement: int
    value_score: float
    confidence_score: float
    is_inactive: bool
    is_ghost: bool
    scored_at: datetime

    class Config:
        from_attributes = True


class FollowerValueScoreListResponse(BaseModel):
    """Paginated list of follower value scores."""

    total: int
    page: int
    page_size: int
    items: List[FollowerValueScoreResponse]


class FollowerValueSummaryResponse(BaseModel):
    """Summary of follower value scores."""

    total_scored: int
    tier_distribution: Dict[str, int] = Field(default_factory=dict)
    inactive_count: int
    ghost_count: int
    high_value_count: int
    average_value_score: float


# =============================================================================
# Safe Messaging Schemas
# =============================================================================


class SafeMessageTemplateCreate(BaseModel):
    """Schema for creating a safe message template."""

    platform: str
    template_type: str
    name: str
    subject_template: Optional[str] = None
    body_template: str
    variables: List[str] = Field(default_factory=list)


class SafeMessageTemplateResponse(BaseModel):
    """Response schema for a safe message template."""

    id: int
    company_id: int
    branch_id: Optional[int] = None
    platform: str
    template_type: str
    name: str
    subject_template: Optional[str] = None
    body_template: str
    variables: List[str] = Field(default_factory=list)
    policy_status: str
    is_active: bool
    use_count: int
    avg_response_rate: float
    created_at: datetime

    class Config:
        from_attributes = True
