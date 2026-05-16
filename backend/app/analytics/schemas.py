"""Pydantic schemas for analytics API requests and responses.

Defines input validation and output serialization models for all
analytics endpoints including overview, traffic, audience, KPI,
branch comparison, conversion, campaign, branch KPI, ERP correlation,
AI insights, and growth metrics.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Analytics Overview
# ---------------------------------------------------------------------------


class PlatformBreakdownItem(BaseModel):
    """Platform-level metric aggregation."""

    platform: str = Field(..., description="Ad platform name")
    campaigns: int = Field(..., description="Number of campaigns")
    impressions: int = Field(..., description="Total impressions")
    clicks: int = Field(..., description="Total clicks")


class AnalyticsOverviewData(BaseModel):
    """Aggregated analytics overview response data."""

    total_campaigns: int = Field(..., description="Active campaign count")
    total_impressions: int = Field(..., description="Total impressions")
    total_clicks: int = Field(..., description="Total clicks")
    total_spend: float = Field(..., description="Total ad spend")
    avg_ctr: float = Field(..., description="Average CTR")
    avg_roas: float = Field(..., description="Average ROAS")
    total_conversions: int = Field(..., description="Total conversions")
    total_conversion_value: float = Field(..., description="Total conversion value")
    active_branches: int = Field(..., description="Active branch count")
    total_usage_events: int = Field(..., description="Total usage events")
    platform_breakdown: List[PlatformBreakdownItem] = Field(
        default=[], description="Per-platform metrics"
    )
    meta: Optional[Dict[str, str]] = Field(
        default=None, description="Optional metadata (e.g., empty dataset note)"
    )


class AnalyticsOverviewResponse(BaseModel):
    """Standard response wrapper for analytics overview."""

    success: bool
    data: Optional[AnalyticsOverviewData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Traffic Data
# ---------------------------------------------------------------------------


class TrafficMeta(BaseModel):
    """Metadata for traffic data response."""

    total: int = Field(..., description="Number of data points")
    days: int = Field(..., description="Requested day count")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    note: Optional[str] = Field(default=None, description="Optional note for empty datasets")


class TrafficData(BaseModel):
    """Daily traffic time-series data."""

    dates: List[str] = Field(..., description="Date labels")
    impressions: List[int] = Field(..., description="Daily impressions")
    clicks: List[int] = Field(..., description="Daily clicks")
    costs: List[float] = Field(..., description="Daily costs")
    conversions: List[int] = Field(..., description="Daily conversions")
    ctr: List[float] = Field(..., description="Daily CTR values")
    meta: TrafficMeta = Field(..., description="Response metadata")


class TrafficResponse(BaseModel):
    """Standard response wrapper for traffic data."""

    success: bool
    data: Optional[TrafficData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Audience Data
# ---------------------------------------------------------------------------


class CityBreakdownItem(BaseModel):
    """City-level branch and employee counts."""

    city: str = Field(..., description="City name")
    branches: int = Field(..., description="Number of branches")
    employees: int = Field(..., description="Total employees")


class BranchTypeItem(BaseModel):
    """Branch type distribution item."""

    type: str = Field(..., description="Branch type")
    count: int = Field(..., description="Number of branches")


class MonthlyGrowthItem(BaseModel):
    """Monthly company growth entry."""

    month: str = Field(..., description="Month (YYYY-MM)")
    new_companies: int = Field(..., description="New companies created")


class AudienceData(BaseModel):
    """Aggregated audience demographics data."""

    city_breakdown: List[CityBreakdownItem] = Field(default=[])
    branch_types: List[BranchTypeItem] = Field(default=[])
    user_activity: Dict[str, int] = Field(default={})
    subscription_status: Dict[str, int] = Field(default={})
    monthly_growth: List[MonthlyGrowthItem] = Field(default=[])
    meta: Optional[Dict[str, str]] = Field(default=None)


class AudienceResponse(BaseModel):
    """Standard response wrapper for audience data."""

    success: bool
    data: Optional[AudienceData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# KPI Metrics
# ---------------------------------------------------------------------------


class DateRange(BaseModel):
    """Date range specification."""

    start: str = Field(..., description="Start date (YYYY-MM-DD)")
    end: str = Field(..., description="End date (YYYY-MM-DD)")


class KpiMetricsData(BaseModel):
    """Detailed KPI metrics response."""

    impressions: int = Field(..., description="Total impressions")
    clicks: int = Field(..., description="Total clicks")
    conversions: int = Field(..., description="Total conversions")
    cost: float = Field(..., description="Total cost")
    ctr: float = Field(..., description="Average CTR")
    cpc: float = Field(..., description="Average CPC")
    cpa: float = Field(..., description="Average CPA")
    roas: float = Field(..., description="Average ROAS")
    campaign_status: Dict[str, int] = Field(default={})
    date_range: DateRange = Field(...)
    meta: Optional[Dict[str, str]] = Field(default=None)


class KpiMetricsResponse(BaseModel):
    """Standard response wrapper for KPI metrics."""

    success: bool
    data: Optional[KpiMetricsData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Branch Comparison
# ---------------------------------------------------------------------------


class BranchComparisonItem(BaseModel):
    """Single branch comparison metrics."""

    branch_id: int = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch name")
    city: str = Field(..., description="Branch city")
    impressions: int = Field(..., description="Total impressions")
    clicks: int = Field(..., description="Total clicks")
    cost: float = Field(..., description="Total cost")
    conversions: int = Field(..., description="Total conversions")
    ctr: float = Field(..., description="Average CTR")
    roas: float = Field(..., description="Average ROAS")


class BranchComparisonMeta(BaseModel):
    """Metadata for branch comparison response."""

    total: int = Field(..., description="Number of branches")
    date_range: DateRange = Field(...)
    note: Optional[str] = Field(default=None)


class BranchComparisonData(BaseModel):
    """Branch comparison response data."""

    branches: List[BranchComparisonItem] = Field(default=[])
    meta: BranchComparisonMeta = Field(...)


class BranchComparisonResponse(BaseModel):
    """Standard response wrapper for branch comparison."""

    success: bool
    data: Optional[BranchComparisonData] = None
    message: Optional[str] = None


# ===========================================================================
# NEW SCHEMAS (Agent 5 - Real DB Aggregation Endpoints)
# ===========================================================================


# ---------------------------------------------------------------------------
# Conversion Analytics
# ---------------------------------------------------------------------------


class DailyConversionTrendItem(BaseModel):
    """Daily conversion trend entry."""

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    conversions: int = Field(..., description="Total conversions")
    clicks: int = Field(..., description="Total clicks")
    conversion_rate: float = Field(..., description="Conversion rate %")
    conversion_value: float = Field(..., description="Conversion value")


class CampaignConversionItem(BaseModel):
    """Campaign-level conversion metrics."""

    campaign_id: int = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    platform: str = Field(..., description="Ad platform")
    conversions: int = Field(..., description="Total conversions")
    conversion_value: float = Field(..., description="Total conversion value")
    conversion_rate: float = Field(..., description="Conversion rate %")


class ConversionAnalyticsData(BaseModel):
    """Conversion analytics response data."""

    conversion_rate: float = Field(..., description="Click-to-conversion rate %")
    click_through_rate: float = Field(..., description="Impression-to-click rate %")
    impression_to_conversion_rate: float = Field(..., description="Impression-to-conversion rate %")
    order_conversion_rate: float = Field(..., description="Order-to-customer rate %")
    total_conversions: int = Field(..., description="Total conversions")
    total_clicks: int = Field(..., description="Total clicks")
    total_impressions: int = Field(..., description="Total impressions")
    total_conversion_value: float = Field(..., description="Total conversion value")
    revenue_per_conversion: float = Field(..., description="Average revenue per conversion")
    total_orders: int = Field(..., description="Total ERP orders")
    total_order_value: float = Field(..., description="Total order value")
    new_customers: int = Field(..., description="New customers from ERP")
    avg_ctr: float = Field(..., description="Average CTR")
    avg_roas: float = Field(..., description="Average ROAS")
    daily_trend: List[DailyConversionTrendItem] = Field(default=[])
    campaign_conversions: List[CampaignConversionItem] = Field(default=[])
    date_range: DateRange = Field(...)
    meta: Optional[Dict[str, str]] = Field(default=None)


class ConversionAnalyticsResponse(BaseModel):
    """Standard response wrapper for conversion analytics."""

    success: bool
    data: Optional[ConversionAnalyticsData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Campaign Analytics
# ---------------------------------------------------------------------------


class CategoryBreakdownItem(BaseModel):
    """AI recommendation category breakdown."""

    category: str = Field(..., description="Recommendation category")
    count: int = Field(..., description="Number of recommendations")
    avg_confidence: float = Field(..., description="Average confidence score")


class TopCampaignItem(BaseModel):
    """Top performing campaign metrics."""

    campaign_id: int = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    platform: str = Field(..., description="Ad platform")
    conversions: int = Field(..., description="Total conversions")
    clicks: int = Field(..., description="Total clicks")
    impressions: int = Field(..., description="Total impressions")
    cost: float = Field(..., description="Total cost")


class CampaignAnalyticsData(BaseModel):
    """Campaign analytics response data."""

    total_campaigns: int = Field(..., description="Total campaign count")
    campaign_status: Dict[str, int] = Field(default={}, description="Campaign count by status")
    ai_suggestion_applied_rate: float = Field(..., description="AI suggestion applied rate %")
    total_suggestions: int = Field(..., description="Total AI suggestions")
    applied_suggestions: int = Field(..., description="Applied suggestions count")
    recommendation_applied_rate: float = Field(..., description="Recommendation applied rate %")
    recommendation_dismissal_rate: float = Field(..., description="Recommendation dismissal rate %")
    total_recommendations: int = Field(..., description="Total recommendations")
    applied_recommendations: int = Field(..., description="Applied recommendations")
    dismissed_recommendations: int = Field(..., description="Dismissed recommendations")
    pending_recommendations: int = Field(..., description="Pending recommendations")
    avg_confidence_score: float = Field(..., description="Average confidence score")
    max_confidence_score: float = Field(..., description="Max confidence score")
    min_confidence_score: float = Field(..., description="Min confidence score")
    category_breakdown: List[CategoryBreakdownItem] = Field(default=[])
    top_campaigns: List[TopCampaignItem] = Field(default=[])
    date_range: DateRange = Field(...)
    meta: Optional[Dict[str, str]] = Field(default=None)


class CampaignAnalyticsResponse(BaseModel):
    """Standard response wrapper for campaign analytics."""

    success: bool
    data: Optional[CampaignAnalyticsData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Branch KPI Analytics
# ---------------------------------------------------------------------------


class BranchKpiItem(BaseModel):
    """Single branch KPI metrics."""

    branch_id: int = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch name")
    city: str = Field(..., description="Branch city")
    type: str = Field(..., description="Branch type")
    status: str = Field(..., description="Branch status")
    employee_count: int = Field(..., description="Number of employees")
    revenue_target: float = Field(..., description="Monthly revenue target")
    impressions: int = Field(..., description="Total impressions")
    clicks: int = Field(..., description="Total clicks")
    conversions: int = Field(..., description="Total conversions")
    cost: float = Field(..., description="Total cost")
    ctr: float = Field(..., description="Average CTR")
    roas: float = Field(..., description="Average ROAS")
    cpa: float = Field(..., description="Average CPA")
    campaigns: int = Field(..., description="Campaign count")
    orders: int = Field(..., description="ERP order count")
    ai_recommendations: int = Field(..., description="AI recommendation count")


class BranchKpiSummary(BaseModel):
    """Summary across all branches."""

    total_branches: int = Field(..., description="Total number of branches")
    total_impressions: int = Field(..., description="Total impressions")
    total_clicks: int = Field(..., description="Total clicks")
    total_conversions: int = Field(..., description="Total conversions")
    total_cost: float = Field(..., description="Total cost")
    avg_ctr: float = Field(..., description="Average CTR %")


class BranchKpiData(BaseModel):
    """Branch KPI analytics response data."""

    branches: List[BranchKpiItem] = Field(default=[])
    summary: BranchKpiSummary = Field(...)
    date_range: DateRange = Field(...)
    meta: Optional[Dict[str, str]] = Field(default=None)


class BranchKpiResponse(BaseModel):
    """Standard response wrapper for branch KPI analytics."""

    success: bool
    data: Optional[BranchKpiData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# ERP Correlation Analytics
# ---------------------------------------------------------------------------


class ConnectionItem(BaseModel):
    """ERP connection summary item."""

    provider: str = Field(..., description="ERP provider type")
    count: int = Field(..., description="Connection count")
    sync_status: str = Field(..., description="Last sync status")


class SyncJobItem(BaseModel):
    """Sync job status breakdown item."""

    count: int = Field(..., description="Job count")
    records_processed: int = Field(..., description="Total records processed")
    records_failed: int = Field(..., description="Total records failed")


class InventorySummary(BaseModel):
    """ERP inventory summary."""

    total_available: float = Field(..., description="Total available quantity")
    total_reserved: float = Field(..., description="Total reserved quantity")
    sku_count: int = Field(..., description="Number of SKUs")


class SalesOrderSummary(BaseModel):
    """ERP sales order summary."""

    total_orders: int = Field(..., description="Total orders")
    total_value: float = Field(..., description="Total order value")
    total_tax: float = Field(..., description="Total tax")
    total_discount: float = Field(..., description="Total discount")


class ERPCorrelationData(BaseModel):
    """ERP correlation analytics response data."""

    active_connections: int = Field(..., description="Active ERP connections")
    connections: List[ConnectionItem] = Field(default=[])
    sync_jobs: Dict[str, SyncJobItem] = Field(default={})
    sync_success_rate: float = Field(..., description="Sync success rate %")
    total_records_processed: int = Field(..., description="Total records processed")
    total_records_failed: int = Field(..., description="Total records failed")
    total_products: int = Field(..., description="Total ERP products")
    inventory: InventorySummary = Field(...)
    sales_orders: SalesOrderSummary = Field(...)
    ad_spend: float = Field(..., description="Ad spend in same period")
    ad_conversions: int = Field(..., description="Ad conversions in same period")
    roas: float = Field(..., description="Revenue / Ad spend ROAS")
    total_customers: int = Field(..., description="Total ERP customers")
    date_range: DateRange = Field(...)
    meta: Optional[Dict[str, str]] = Field(default=None)


class ERPCorrelationResponse(BaseModel):
    """Standard response wrapper for ERP correlation analytics."""

    success: bool
    data: Optional[ERPCorrelationData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Insights Analytics
# ---------------------------------------------------------------------------


class ModelBreakdownItem(BaseModel):
    """Per-model AI usage breakdown."""

    model: str = Field(..., description="AI model name")
    requests: int = Field(..., description="Request count")
    tokens_input: int = Field(..., description="Input tokens")
    tokens_output: int = Field(..., description="Output tokens")
    cost: float = Field(..., description="Estimated cost")
    avg_latency_ms: float = Field(..., description="Average latency in ms")


class DailyUsageItem(BaseModel):
    """Daily AI usage entry."""

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    requests: int = Field(..., description="Request count")
    tokens_input: int = Field(..., description="Input tokens")
    tokens_output: int = Field(..., description="Output tokens")
    cost: float = Field(..., description="Estimated cost")
    avg_latency_ms: float = Field(..., description="Average latency in ms")


class SuggestionTypeItem(BaseModel):
    """AI suggestion trigger type distribution."""

    trigger_type: str = Field(..., description="Trigger type")
    count: int = Field(..., description="Suggestion count")
    avg_tokens: float = Field(..., description="Average tokens used")


class ConversationSummary(BaseModel):
    """AI conversation summary."""

    total: int = Field(..., description="Total conversations")
    total_tokens: int = Field(..., description="Total tokens consumed")
    unique_users: int = Field(..., description="Unique user count")


class MessageStatsItem(BaseModel):
    """Message stats by role."""

    count: int = Field(..., description="Message count")
    tokens: int = Field(..., description="Total tokens")


class AIInsightsData(BaseModel):
    """AI insights analytics response data."""

    total_requests: int = Field(..., description="Total AI requests")
    total_tokens_input: int = Field(..., description="Total input tokens")
    total_tokens_output: int = Field(..., description="Total output tokens")
    total_tokens: int = Field(..., description="Total tokens")
    total_cost: float = Field(..., description="Total estimated cost")
    avg_latency_ms: float = Field(..., description="Average latency ms")
    max_latency_ms: int = Field(..., description="Max latency ms")
    min_latency_ms: int = Field(..., description="Min latency ms")
    cost_per_request: float = Field(..., description="Average cost per request")
    tokens_per_request: float = Field(..., description="Average tokens per request")
    model_breakdown: List[ModelBreakdownItem] = Field(default=[])
    daily_usage: List[DailyUsageItem] = Field(default=[])
    suggestion_types: List[SuggestionTypeItem] = Field(default=[])
    conversations: ConversationSummary = Field(...)
    message_stats: Dict[str, MessageStatsItem] = Field(default={})
    date_range: DateRange = Field(...)
    meta: Optional[Dict[str, str]] = Field(default=None)


class AIInsightsResponse(BaseModel):
    """Standard response wrapper for AI insights analytics."""

    success: bool
    data: Optional[AIInsightsData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Growth Metrics
# ---------------------------------------------------------------------------


class MonthlyGrowthItem(BaseModel):
    """Monthly growth metrics entry."""

    month: str = Field(..., description="Month (YYYY-MM)")
    campaigns: int = Field(..., description="Campaign count")
    campaign_growth: Optional[float] = Field(default=None, description="MoM campaign growth %")
    ad_spend: float = Field(..., description="Ad spend")
    spend_growth: Optional[float] = Field(default=None, description="MoM spend growth %")
    conversions: int = Field(..., description="Total conversions")
    conversion_growth: Optional[float] = Field(default=None, description="MoM conversion growth %")
    impressions: int = Field(..., description="Total impressions")
    clicks: int = Field(..., description="Total clicks")
    orders: int = Field(..., description="Total ERP orders")
    order_growth: Optional[float] = Field(default=None, description="MoM order growth %")
    order_value: float = Field(..., description="Total order value")
    ai_requests: int = Field(..., description="AI requests")
    ai_tokens: int = Field(..., description="AI tokens consumed")
    ai_cost: float = Field(..., description="AI cost")
    ctr: float = Field(..., description="CTR %")


class GrowthSummary(BaseModel):
    """Growth summary comparing latest vs previous month."""

    campaign_growth: Optional[float] = Field(default=None)
    spend_growth: Optional[float] = Field(default=None)
    conversion_growth: Optional[float] = Field(default=None)
    order_growth: Optional[float] = Field(default=None)
    latest_month: Optional[str] = Field(default=None)
    previous_month: Optional[str] = Field(default=None)


class GrowthMetricsData(BaseModel):
    """Growth metrics response data."""

    monthly: List[MonthlyGrowthItem] = Field(default=[])
    summary: GrowthSummary = Field(...)
    period_months: int = Field(..., description="Analysis period in months")
    meta: Optional[Dict[str, str]] = Field(default=None)


class GrowthMetricsResponse(BaseModel):
    """Standard response wrapper for growth metrics."""

    success: bool
    data: Optional[GrowthMetricsData] = None
    message: Optional[str] = None
