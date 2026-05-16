"""Pydantic v2 schemas for the Ads Intelligence module.

Provides comprehensive request and response schemas for all CRUD operations
across ad platforms, campaigns, ad sets, creatives, metrics, audiences,
budget recommendations, and creative analysis.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ads.constants import (
    AdPlatform,
    AudienceType,
    BidStrategy,
    CallToAction,
    CampaignObjective,
    CampaignStatus,
    CreativeType,
    PlatformStatus,
)


# =============================================================================
# Shared / Base Schemas
# =============================================================================


class PaginatedResponse(BaseModel):
    """Base paginated response schema."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=50, ge=1, le=100, description="Items per page")


class DateRangeFilter(BaseModel):
    """Date range filter for metric queries."""

    start_date: Optional[date] = Field(default=None, description="Start date (inclusive)")
    end_date: Optional[date] = Field(default=None, description="End date (inclusive)")

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: Optional[date], info) -> Optional[date]:
        """Ensure end_date is after start_date."""
        if v is None:
            return v
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be after start_date")
        return v


# =============================================================================
# Ad Platform Schemas
# =============================================================================


class AdPlatformBase(BaseModel):
    """Base schema for ad platform account data."""

    platform: AdPlatform = Field(..., description="Ad platform type")
    account_id: str = Field(..., min_length=1, max_length=255, description="Platform account ID")
    account_name: str = Field(..., min_length=1, max_length=255, description="Account name")
    currency: str = Field(default="USD", max_length=3, description="Account currency")
    timezone: str = Field(default="America/New_York", max_length=100, description="Account timezone")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific settings")


class AdPlatformCredentials(BaseModel):
    """Schema for ad platform credentials."""

    access_token: str = Field(..., min_length=1, description="OAuth access token")
    refresh_token: str = Field(..., min_length=1, description="OAuth refresh token")
    developer_token: Optional[str] = Field(default=None, description="Developer token (Google Ads)")


class AdPlatformCreate(AdPlatformBase):
    """Schema for creating a new ad platform connection."""

    branch_id: Optional[int] = Field(default=None, ge=1, description="Branch ID")
    credentials: AdPlatformCredentials = Field(..., description="OAuth credentials")


class AdPlatformUpdate(BaseModel):
    """Schema for updating an ad platform connection."""

    account_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    currency: Optional[str] = Field(default=None, max_length=3)
    timezone: Optional[str] = Field(default=None, max_length=100)
    status: Optional[PlatformStatus] = Field(default=None)
    settings: Optional[Dict[str, Any]] = Field(default=None)


class AdPlatformResponse(AdPlatformBase):
    """Schema for ad platform account response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Record ID")
    company_id: int = Field(..., description="Company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    status: PlatformStatus = Field(..., description="Connection status")
    last_sync_at: Optional[datetime] = Field(default=None, description="Last successful sync")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AdPlatformListResponse(BaseModel):
    """Schema for listing ad platform accounts."""

    items: List[AdPlatformResponse] = Field(..., description="List of platform accounts")
    total: int = Field(..., description="Total count")


# =============================================================================
# Ad Campaign Schemas
# =============================================================================


class AdCampaignBase(BaseModel):
    """Base schema for ad campaign data."""

    platform: AdPlatform = Field(..., description="Ad platform")
    name: str = Field(..., min_length=1, max_length=500, description="Campaign name")
    objective: Optional[CampaignObjective] = Field(default=None, description="Campaign objective")
    status: CampaignStatus = Field(default=CampaignStatus.ENABLED, description="Campaign status")
    budget: Decimal = Field(..., ge=0, description="Budget amount")
    budget_type: str = Field(default="daily", description="Budget type: daily/lifetime")
    start_date: Optional[date] = Field(default=None, description="Start date")
    end_date: Optional[date] = Field(default=None, description="End date")
    targeting: Dict[str, Any] = Field(default_factory=dict, description="Targeting configuration")
    bid_strategy: Optional[BidStrategy] = Field(default=None, description="Bid strategy")

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: Optional[date], info) -> Optional[date]:
        """Ensure end_date is after start_date."""
        if v is None:
            return v
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be after start_date")
        return v


class AdCampaignCreate(AdCampaignBase):
    """Schema for creating a new ad campaign."""

    platform_campaign_id: Optional[str] = Field(default=None, description="Platform campaign ID")
    ai_optimized: bool = Field(default=False, description="Whether AI optimization is enabled")


class AdCampaignUpdate(BaseModel):
    """Schema for updating an existing ad campaign."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    objective: Optional[CampaignObjective] = Field(default=None)
    status: Optional[CampaignStatus] = Field(default=None)
    budget: Optional[Decimal] = Field(default=None, ge=0)
    budget_type: Optional[str] = Field(default=None)
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    targeting: Optional[Dict[str, Any]] = Field(default=None)
    bid_strategy: Optional[BidStrategy] = Field(default=None)
    ai_optimized: Optional[bool] = Field(default=None)

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: Optional[date], info) -> Optional[date]:
        """Ensure end_date is after start_date."""
        if v is None:
            return v
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be after start_date")
        return v


class AdCampaignResponse(AdCampaignBase):
    """Schema for ad campaign response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Campaign ID")
    company_id: int = Field(..., description="Company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    platform_campaign_id: str = Field(..., description="Platform campaign ID")
    performance_score: Optional[Decimal] = Field(default=None, description="Performance score")
    ai_optimized: bool = Field(..., description="AI optimization enabled")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AdCampaignListResponse(BaseModel):
    """Schema for listing ad campaigns."""

    items: List[AdCampaignResponse] = Field(..., description="List of campaigns")
    total: int = Field(..., description="Total count")


class AdCampaignMetricsResponse(BaseModel):
    """Schema for campaign metrics summary."""

    campaign_id: int = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    platform: AdPlatform = Field(..., description="Ad platform")
    date_range: DateRangeFilter = Field(..., description="Date range")
    impressions: int = Field(default=0, description="Total impressions")
    clicks: int = Field(default=0, description="Total clicks")
    conversions: int = Field(default=0, description="Total conversions")
    cost: Decimal = Field(default=Decimal("0.00"), description="Total cost")
    ctr: Optional[Decimal] = Field(default=None, description="Click-through rate")
    cpc: Optional[Decimal] = Field(default=None, description="Cost per click")
    cpa: Optional[Decimal] = Field(default=None, description="Cost per acquisition")
    roas: Optional[Decimal] = Field(default=None, description="Return on ad spend")
    conversion_value: Decimal = Field(default=Decimal("0.00"), description="Conversion value")


# =============================================================================
# Ad Adset Schemas
# =============================================================================


class AdAdsetBase(BaseModel):
    """Base schema for ad set / ad group data."""

    name: str = Field(..., min_length=1, max_length=500, description="Ad set name")
    targeting: Dict[str, Any] = Field(default_factory=dict, description="Targeting configuration")
    budget: Optional[Decimal] = Field(default=None, ge=0, description="Budget amount")
    bid_amount: Optional[Decimal] = Field(default=None, ge=0, description="Bid amount")
    status: CampaignStatus = Field(default=CampaignStatus.ENABLED, description="Ad set status")


class AdAdsetCreate(AdAdsetBase):
    """Schema for creating a new ad set."""

    campaign_id: int = Field(..., ge=1, description="Parent campaign ID")
    platform_adset_id: Optional[str] = Field(default=None, description="Platform ad set ID")


class AdAdsetUpdate(BaseModel):
    """Schema for updating an ad set."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    targeting: Optional[Dict[str, Any]] = Field(default=None)
    budget: Optional[Decimal] = Field(default=None, ge=0)
    bid_amount: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[CampaignStatus] = Field(default=None)


class AdAdsetResponse(AdAdsetBase):
    """Schema for ad set response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Ad set ID")
    campaign_id: int = Field(..., description="Parent campaign ID")
    platform_adset_id: str = Field(..., description="Platform ad set ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AdAdsetListResponse(BaseModel):
    """Schema for listing ad sets."""

    items: List[AdAdsetResponse] = Field(..., description="List of ad sets")
    total: int = Field(..., description="Total count")


# =============================================================================
# Ad Creative Schemas
# =============================================================================


class AdCreativeBase(BaseModel):
    """Base schema for ad creative data."""

    name: str = Field(..., min_length=1, max_length=500, description="Creative name")
    creative_type: CreativeType = Field(..., description="Creative type")
    headline: Optional[str] = Field(default=None, max_length=255, description="Headline text")
    description: Optional[str] = Field(default=None, description="Description text")
    call_to_action: Optional[CallToAction] = Field(default=None, description="Call to action")
    media_urls: List[str] = Field(default_factory=list, description="Media asset URLs")
    status: CampaignStatus = Field(default=CampaignStatus.ENABLED, description="Creative status")


class AdCreativeCreate(AdCreativeBase):
    """Schema for creating a new ad creative."""

    campaign_id: int = Field(..., ge=1, description="Parent campaign ID")
    platform_creative_id: Optional[str] = Field(default=None, description="Platform creative ID")


class AdCreativeUpdate(BaseModel):
    """Schema for updating an ad creative."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    headline: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None)
    call_to_action: Optional[CallToAction] = Field(default=None)
    media_urls: Optional[List[str]] = Field(default=None)
    status: Optional[CampaignStatus] = Field(default=None)


class AdCreativeResponse(AdCreativeBase):
    """Schema for ad creative response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Creative ID")
    company_id: int = Field(..., description="Company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    campaign_id: int = Field(..., description="Parent campaign ID")
    platform_creative_id: Optional[str] = Field(default=None, description="Platform creative ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AdCreativeListResponse(BaseModel):
    """Schema for listing ad creatives."""

    items: List[AdCreativeResponse] = Field(..., description="List of creatives")
    total: int = Field(..., description="Total count")


# =============================================================================
# Ad Metric Schemas
# =============================================================================


class AdMetricBase(BaseModel):
    """Base schema for ad metric data."""

    metric_date: date = Field(..., description="Metric date")
    impressions: int = Field(default=0, ge=0, description="Impressions")
    clicks: int = Field(default=0, ge=0, description="Clicks")
    conversions: int = Field(default=0, ge=0, description="Conversions")
    cost: Decimal = Field(default=Decimal("0.00"), ge=0, description="Cost")
    ctr: Optional[Decimal] = Field(default=None, ge=0, description="Click-through rate")
    cpc: Optional[Decimal] = Field(default=None, ge=0, description="Cost per click")
    cpa: Optional[Decimal] = Field(default=None, ge=0, description="Cost per acquisition")
    roas: Optional[Decimal] = Field(default=None, ge=0, description="Return on ad spend")
    conversion_value: Decimal = Field(default=Decimal("0.00"), ge=0, description="Conversion value")
    quality_score: Optional[Decimal] = Field(default=None, ge=0, description="Quality score")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Platform raw data")


class AdMetricCreate(AdMetricBase):
    """Schema for creating a metric record."""

    campaign_id: int = Field(..., ge=1, description="Campaign ID")
    adset_id: Optional[int] = Field(default=None, ge=1, description="Ad set ID")
    creative_id: Optional[int] = Field(default=None, ge=1, description="Creative ID")


class AdMetricResponse(AdMetricBase):
    """Schema for ad metric response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Metric ID")
    campaign_id: int = Field(..., description="Campaign ID")
    adset_id: Optional[int] = Field(default=None, description="Ad set ID")
    creative_id: Optional[int] = Field(default=None, description="Creative ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class AdMetricListResponse(BaseModel):
    """Schema for listing ad metrics."""

    items: List[AdMetricResponse] = Field(..., description="List of metrics")
    total: int = Field(..., description="Total count")


class AggregatedMetricsResponse(BaseModel):
    """Schema for aggregated metrics response."""

    date_range: DateRangeFilter = Field(..., description="Date range")
    platform: Optional[AdPlatform] = Field(default=None, description="Filtered platform")
    campaign_id: Optional[int] = Field(default=None, description="Filtered campaign ID")
    total_impressions: int = Field(default=0, description="Total impressions")
    total_clicks: int = Field(default=0, description="Total clicks")
    total_conversions: int = Field(default=0, description="Total conversions")
    total_cost: Decimal = Field(default=Decimal("0.00"), description="Total cost")
    total_conversion_value: Decimal = Field(default=Decimal("0.00"), description="Total conversion value")
    avg_ctr: Optional[Decimal] = Field(default=None, description="Average CTR")
    avg_cpc: Optional[Decimal] = Field(default=None, description="Average CPC")
    avg_cpa: Optional[Decimal] = Field(default=None, description="Average CPA")
    avg_roas: Optional[Decimal] = Field(default=None, description="Average ROAS")
    daily_breakdown: List[AdMetricResponse] = Field(
        default_factory=list, description="Daily metrics breakdown"
    )


# =============================================================================
# Ad Audience Schemas
# =============================================================================


class AdAudienceBase(BaseModel):
    """Base schema for ad audience data."""

    platform: AdPlatform = Field(..., description="Ad platform")
    name: str = Field(..., min_length=1, max_length=500, description="Audience name")
    audience_type: AudienceType = Field(..., description="Audience type")
    size_estimate: Optional[int] = Field(default=None, ge=0, description="Estimated audience size")
    targeting_spec: Dict[str, Any] = Field(default_factory=dict, description="Targeting specification")
    performance_score: Optional[Decimal] = Field(default=None, ge=0, le=100, description="Performance score")


class AdAudienceCreate(AdAudienceBase):
    """Schema for creating a new ad audience."""

    branch_id: Optional[int] = Field(default=None, ge=1, description="Branch ID")
    platform_audience_id: Optional[str] = Field(default=None, description="Platform audience ID")


class AdAudienceUpdate(BaseModel):
    """Schema for updating an ad audience."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    audience_type: Optional[AudienceType] = Field(default=None)
    size_estimate: Optional[int] = Field(default=None, ge=0)
    targeting_spec: Optional[Dict[str, Any]] = Field(default=None)
    performance_score: Optional[Decimal] = Field(default=None, ge=0, le=100)


class AdAudienceResponse(AdAudienceBase):
    """Schema for ad audience response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Audience ID")
    company_id: int = Field(..., description="Company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    platform_audience_id: Optional[str] = Field(default=None, description="Platform audience ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AdAudienceListResponse(BaseModel):
    """Schema for listing ad audiences."""

    items: List[AdAudienceResponse] = Field(..., description="List of audiences")
    total: int = Field(..., description="Total count")


class AudienceOverlapResponse(BaseModel):
    """Schema for audience overlap detection."""

    audience_id_1: int = Field(..., description="First audience ID")
    audience_name_1: str = Field(..., description="First audience name")
    audience_id_2: int = Field(..., description="Second audience ID")
    audience_name_2: str = Field(..., description="Second audience name")
    overlap_percentage: Decimal = Field(..., description="Overlap percentage")
    recommendation: str = Field(..., description="Recommendation for handling overlap")


class LookalikeSuggestion(BaseModel):
    """Schema for lookalike audience suggestion."""

    source_audience_id: int = Field(..., description="Source audience ID")
    source_audience_name: str = Field(..., description="Source audience name")
    suggested_platform: AdPlatform = Field(..., description="Platform for lookalike")
    suggested_size: str = Field(..., description="Suggested size tier (1%, 1-5%, 5-10%)")
    estimated_reach: int = Field(..., description="Estimated reach")
    confidence: Decimal = Field(..., description="Confidence score")


# =============================================================================
# Ad Budget Recommendation Schemas
# =============================================================================


class AdBudgetRecommendationBase(BaseModel):
    """Base schema for budget recommendation data."""

    platform: AdPlatform = Field(..., description="Ad platform")
    current_budget: Decimal = Field(..., ge=0, description="Current budget")
    recommended_budget: Decimal = Field(..., ge=0, description="Recommended budget")
    reason: str = Field(..., min_length=1, description="Recommendation reasoning")
    expected_improvement: Optional[Decimal] = Field(default=None, description="Expected improvement")
    confidence_score: Decimal = Field(..., ge=0, le=1, description="Confidence score (0-1)")


class AdBudgetRecommendationCreate(AdBudgetRecommendationBase):
    """Schema for creating a budget recommendation."""

    campaign_id: int = Field(..., ge=1, description="Campaign ID")


class AdBudgetRecommendationResponse(AdBudgetRecommendationBase):
    """Schema for budget recommendation response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Recommendation ID")
    company_id: int = Field(..., description="Company ID")
    branch_id: Optional[int] = Field(default=None, description="Branch ID")
    campaign_id: int = Field(..., description="Campaign ID")
    campaign_name: Optional[str] = Field(default=None, description="Campaign name")
    applied: bool = Field(..., description="Whether recommendation was applied")
    created_at: datetime = Field(..., description="Creation timestamp")


class AdBudgetRecommendationListResponse(BaseModel):
    """Schema for listing budget recommendations."""

    items: List[AdBudgetRecommendationResponse] = Field(..., description="List of recommendations")
    total: int = Field(..., description="Total count")


# =============================================================================
# Ad Creative Analysis Schemas
# =============================================================================


class AdCreativeAnalysisBase(BaseModel):
    """Base schema for creative analysis data."""

    analysis_type: str = Field(..., description="Analysis type: fatigue/score/ab_test")
    results: Dict[str, Any] = Field(default_factory=dict, description="Analysis results")
    ai_insights: Optional[str] = Field(default=None, description="AI-generated insights")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")


class AdCreativeAnalysisCreate(AdCreativeAnalysisBase):
    """Schema for creating a creative analysis record."""

    creative_id: int = Field(..., ge=1, description="Creative ID")
    company_id: int = Field(..., ge=1, description="Company ID")


class AdCreativeAnalysisResponse(AdCreativeAnalysisBase):
    """Schema for creative analysis response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Analysis ID")
    creative_id: int = Field(..., description="Creative ID")
    company_id: int = Field(..., description="Company ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreativeFatigueResponse(BaseModel):
    """Schema for creative fatigue analysis response."""

    creative_id: int = Field(..., description="Creative ID")
    creative_name: str = Field(..., description="Creative name")
    fatigue_score: Decimal = Field(..., description="Fatigue score (0-100, higher is better)")
    fatigue_level: str = Field(..., description="Fatigue level: fresh/mild/moderate/severe")
    days_since_launch: int = Field(..., description="Days since creative launch")
    total_impressions: int = Field(..., description="Total impressions")
    frequency: Optional[Decimal] = Field(default=None, description="Avg impressions per user")
    ctr_trend: Optional[Decimal] = Field(default=None, description="CTR trend (negative = declining)")
    conversion_trend: Optional[Decimal] = Field(default=None, description="Conversion trend")
    recommendation: str = Field(..., description="Primary recommendation")
    recommended_refresh_date: Optional[date] = Field(default=None, description="Suggested refresh date")


class ABTestResultResponse(BaseModel):
    """Schema for A/B test result response."""

    control_creative_id: int = Field(..., description="Control creative ID")
    variant_creative_id: int = Field(..., description="Variant creative ID")
    control_name: str = Field(..., description="Control creative name")
    variant_name: str = Field(..., description="Variant creative name")
    winner: str = Field(..., description="Winner: control/variant/tie")
    confidence_level: Decimal = Field(..., description="Statistical confidence level")
    lift_percentage: Optional[Decimal] = Field(default=None, description="Performance lift %")
    metric_compared: str = Field(..., description="Primary metric compared")


# =============================================================================
# Performance Dashboard Schemas
# =============================================================================


class PerformanceDashboardResponse(BaseModel):
    """Schema for performance dashboard data."""

    date_range: DateRangeFilter = Field(..., description="Date range")
    summary: Dict[str, Any] = Field(..., description="Summary metrics")
    platform_breakdown: List[Dict[str, Any]] = Field(
        ..., description="Metrics broken down by platform"
    )
    campaign_performance: List[Dict[str, Any]] = Field(
        ..., description="Top campaigns by performance"
    )
    trends: Dict[str, List[Dict[str, Any]]] = Field(
        ..., description="Metric trends over time"
    )


# =============================================================================
# ROAS / CPA Analysis Schemas
# =============================================================================


class ROASAnalysisResponse(BaseModel):
    """Schema for ROAS analysis response."""

    date_range: DateRangeFilter = Field(..., description="Date range")
    total_roas: Optional[Decimal] = Field(default=None, description="Overall ROAS")
    total_conversion_value: Decimal = Field(default=Decimal("0.00"))
    total_spend: Decimal = Field(default=Decimal("0.00"))
    roas_by_campaign: List[Dict[str, Any]] = Field(
        default_factory=list, description="ROAS per campaign"
    )
    roas_by_platform: List[Dict[str, Any]] = Field(
        default_factory=list, description="ROAS per platform"
    )
    roas_trend: List[Dict[str, Any]] = Field(
        default_factory=list, description="ROAS trend over time"
    )
    benchmark_comparison: Optional[Dict[str, Any]] = Field(
        default=None, description="Comparison to industry benchmark"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="ROAS improvement recommendations"
    )


class CPAAnalysisResponse(BaseModel):
    """Schema for CPA analysis response."""

    date_range: DateRangeFilter = Field(..., description="Date range")
    total_cpa: Optional[Decimal] = Field(default=None, description="Overall CPA")
    total_conversions: int = Field(default=0)
    total_cost: Decimal = Field(default=Decimal("0.00"))
    cpa_by_campaign: List[Dict[str, Any]] = Field(
        default_factory=list, description="CPA per campaign"
    )
    cpa_by_platform: List[Dict[str, Any]] = Field(
        default_factory=list, description="CPA per platform"
    )
    cpa_trend: List[Dict[str, Any]] = Field(
        default_factory=list, description="CPA trend over time"
    )
    benchmark_comparison: Optional[Dict[str, Any]] = Field(
        default=None, description="Comparison to industry benchmark"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="CPA optimization recommendations"
    )


# =============================================================================
# Local Campaign Schemas
# =============================================================================


class LocalCampaignRecommendation(BaseModel):
    """Schema for local campaign recommendation."""

    branch_id: int = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch name")
    location: Dict[str, Any] = Field(..., description="Location details")
    radius_miles: float = Field(..., description="Recommended targeting radius")
    daily_budget: Decimal = Field(..., description="Recommended daily budget")
    bid_modifiers: Dict[str, Decimal] = Field(
        default_factory=dict, description="Daypart bid modifiers"
    )
    suggested_keywords: List[str] = Field(
        default_factory=list, description="Suggested local keywords"
    )
    expected_reach: int = Field(..., description="Estimated daily reach")
    confidence_score: Decimal = Field(..., description="Confidence score")


class LocalRecommendationsResponse(BaseModel):
    """Schema for local campaign recommendations response."""

    company_id: int = Field(..., description="Company ID")
    industry: str = Field(..., description="Industry type")
    recommendations: List[LocalCampaignRecommendation] = Field(
        ..., description="Per-branch recommendations"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Sync Schemas
# =============================================================================


class SyncRequest(BaseModel):
    """Schema for ad platform sync request."""

    platform_account_id: Optional[int] = Field(
        default=None, ge=1, description="Specific platform account ID to sync"
    )
    date_range_days: int = Field(default=30, ge=1, le=90, description="Days of data to sync")
    sync_campaigns: bool = Field(default=True, description="Sync campaigns")
    sync_metrics: bool = Field(default=True, description="Sync metrics")
    sync_audiences: bool = Field(default=False, description="Sync audiences")
    force_refresh: bool = Field(default=False, description="Force refresh all data")


class SyncResponse(BaseModel):
    """Schema for ad platform sync response."""

    platform: AdPlatform = Field(..., description="Synced platform")
    status: str = Field(..., description="Sync status: success/partial/failed")
    campaigns_synced: int = Field(default=0, description="Number of campaigns synced")
    metrics_synced: int = Field(default=0, description="Number of metric records synced")
    audiences_synced: int = Field(default=0, description="Number of audiences synced")
    errors: List[str] = Field(default_factory=list, description="Sync errors")
    started_at: datetime = Field(..., description="Sync start time")
    completed_at: Optional[datetime] = Field(default=None, description="Sync completion time")
