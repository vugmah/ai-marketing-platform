"""Pydantic schemas for dashboard API responses."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Dashboard KPI Stats (Legacy)
# ---------------------------------------------------------------------------

class DashboardStatsData(BaseModel):
    """Aggregated KPI statistics for the dashboard."""

    total_companies: int = Field(..., description="Total active companies")
    total_branches: int = Field(..., description="Total active branches")
    total_users: int = Field(..., description="Total active users")
    active_campaigns: int = Field(..., description="Number of active campaigns")
    revenue_this_month: float = Field(..., description="Projected revenue this month")
    engagement_rate: float = Field(..., description="Average engagement rate (%)")


class DashboardStatsResponse(BaseModel):
    """Standard response wrapper for dashboard stats."""

    success: bool
    data: Optional[DashboardStatsData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Chart Data
# ---------------------------------------------------------------------------

class DashboardChartData(BaseModel):
    """30-day trend chart data for the dashboard."""

    labels: List[str] = Field(..., description="Day labels (e.g. '1 May')")
    revenue: List[float] = Field(..., description="Daily revenue values")
    orders: List[int] = Field(..., description="Daily order counts")
    engagement: List[float] = Field(..., description="Daily engagement rates (%)")
    roas: List[float] = Field(..., description="Daily ROAS values")


class DashboardChartResponse(BaseModel):
    """Standard response wrapper for chart data."""

    success: bool
    data: Optional[DashboardChartData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class DashboardAlertItem(BaseModel):
    """Individual system alert or warning."""

    id: str = Field(..., description="Unique alert identifier")
    type: str = Field(..., description="Alert severity: info, warning, error")
    title: str = Field(..., description="Short alert title")
    message: str = Field(..., description="Detailed alert message")
    created_at: str = Field(..., description="ISO-formatted timestamp")


class DashboardAlertsResponse(BaseModel):
    """Standard response wrapper for system alerts."""

    success: bool
    data: List[DashboardAlertItem] = []
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. Executive Summary Dashboard
# ---------------------------------------------------------------------------

class ExecutiveSummaryData(BaseModel):
    """Executive-level KPI summary for the authenticated company."""

    total_orders: int = Field(default=0, description="Total orders this month")
    total_revenue: float = Field(default=0.0, description="Total revenue this month")
    active_branches: int = Field(default=0, description="Number of active branches")
    ai_tokens_month: int = Field(default=0, description="AI tokens consumed this month")
    active_campaigns: int = Field(default=0, description="Active ad campaigns")
    avg_ctr: float = Field(default=0.0, description="Average CTR this month (%)")
    total_impressions: int = Field(default=0, description="Total impressions this month")
    total_clicks: int = Field(default=0, description="Total clicks this month")
    total_conversions: int = Field(default=0, description="Total conversions this month")
    ai_cost_estimate: float = Field(default=0.0, description="Estimated AI cost this month ($)")
    users_count: int = Field(default=0, description="Total users in company")
    subscription_status: str = Field(default="", description="Company subscription status")


class ExecutiveSummaryResponse(BaseModel):
    """Response wrapper for executive summary."""

    success: bool
    data: Optional[ExecutiveSummaryData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# 2. Branch Dashboard (branch-scoped KPIs)
# ---------------------------------------------------------------------------

class BranchDashboardData(BaseModel):
    """KPI data scoped to a single branch."""

    branch_id: int = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch display name")
    city: str = Field(default="", description="Branch city")
    status: str = Field(default="", description="Branch operational status")
    employee_count: int = Field(default=0, description="Number of employees")

    # Campaign metrics (this branch)
    active_campaigns: int = Field(default=0, description="Active campaigns for this branch")
    total_campaigns: int = Field(default=0, description="Total campaigns for this branch")

    # Revenue & engagement (this month)
    revenue_this_month: float = Field(default=0.0, description="Revenue this month")
    orders_this_month: int = Field(default=0, description="Orders this month")
    impressions_this_month: int = Field(default=0, description="Impressions this month")
    clicks_this_month: int = Field(default=0, description="Clicks this month")
    conversions_this_month: int = Field(default=0, description="Conversions this month")
    avg_ctr: float = Field(default=0.0, description="Average CTR this month (%)")
    avg_roas: float = Field(default=0.0, description="Average ROAS this month")

    # AI usage (this month)
    ai_tokens_this_month: int = Field(default=0, description="AI tokens consumed this month")
    ai_cost_this_month: float = Field(default=0.0, description="Estimated AI cost this month ($)")
    ai_suggestions_count: int = Field(default=0, description="AI suggestions generated")

    # Targets
    monthly_revenue_target: float = Field(default=0.0, description="Monthly revenue target")
    target_progress_pct: float = Field(default=0.0, description="Target achievement percentage (%)")

    # Users
    users_count: int = Field(default=0, description="Users assigned to this branch")


class BranchDashboardResponse(BaseModel):
    """Response wrapper for branch dashboard."""

    success: bool
    data: Optional[BranchDashboardData] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Branch Comparison
# ---------------------------------------------------------------------------

class BranchComparisonItem(BaseModel):
    """KPI snapshot for a single branch in comparison view."""

    branch_id: int = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch display name")
    city: str = Field(default="", description="Branch city")

    # Metrics
    revenue: float = Field(default=0.0, description="Revenue for the period")
    orders: int = Field(default=0, description="Orders for the period")
    impressions: int = Field(default=0, description="Impressions for the period")
    clicks: int = Field(default=0, description="Clicks for the period")
    conversions: int = Field(default=0, description="Conversions for the period")
    ctr: float = Field(default=0.0, description="Click-through rate (%)")
    roas: float = Field(default=0.0, description="Return on ad spend")
    ai_tokens: int = Field(default=0, description="AI tokens consumed")
    ai_cost: float = Field(default=0.0, description="AI cost estimate ($)")
    active_campaigns: int = Field(default=0, description="Active campaign count")

    # Rankings
    revenue_rank: int = Field(default=0, description="Revenue rank among branches")
    orders_rank: int = Field(default=0, description="Orders rank among branches")


class BranchComparisonResponse(BaseModel):
    """Response wrapper for branch comparison."""

    success: bool
    data: List[BranchComparisonItem] = []
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# 4. Branch Growth Analytics
# ---------------------------------------------------------------------------

class BranchMonthlyGrowth(BaseModel):
    """Monthly growth data for a single branch."""

    month: str = Field(..., description="Month label (e.g. '2024-01')")
    branch_id: int = Field(..., description="Branch ID")
    branch_name: str = Field(..., description="Branch name")

    revenue: float = Field(default=0.0, description="Monthly revenue")
    orders: int = Field(default=0, description="Monthly orders")
    impressions: int = Field(default=0, description="Monthly impressions")
    clicks: int = Field(default=0, description="Monthly clicks")
    conversions: int = Field(default=0, description="Monthly conversions")
    ai_tokens: int = Field(default=0, description="Monthly AI tokens")
    ai_cost: float = Field(default=0.0, description="Monthly AI cost ($)")

    # Growth rates vs previous month (percentage)
    revenue_growth_pct: Optional[float] = Field(default=None, description="Revenue growth vs previous month (%)")
    orders_growth_pct: Optional[float] = Field(default=None, description="Orders growth vs previous month (%)")
    impressions_growth_pct: Optional[float] = Field(default=None, description="Impressions growth vs previous month (%)")


class BranchGrowthResponse(BaseModel):
    """Response wrapper for branch growth analytics."""

    success: bool
    data: List[BranchMonthlyGrowth] = []
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# 5. Alert Threshold Widgets
# ---------------------------------------------------------------------------

class KPIAlertThreshold(BaseModel):
    """A threshold-based alert definition and current state."""

    id: str = Field(..., description="Alert ID")
    kpi_name: str = Field(..., description="KPI name (e.g. 'revenue', 'ctr')")
    threshold_type: str = Field(..., description="'above' or 'below'")
    threshold_value: float = Field(..., description="Threshold value")
    current_value: float = Field(..., description="Current KPI value")
    severity: str = Field(..., description="info, warning, error")
    is_triggered: bool = Field(default=False, description="Whether threshold is exceeded")
    message: str = Field(default="", description="Alert message")
    branch_id: Optional[int] = Field(default=None, description="Branch scope (null = company-wide)")
    branch_name: Optional[str] = Field(default=None, description="Branch name if scoped")


class KPIAlertThresholdsResponse(BaseModel):
    """Response wrapper for KPI threshold alerts."""

    success: bool
    data: List[KPIAlertThreshold] = []
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# 6. Dashboard Filters / Period Selectors
# ---------------------------------------------------------------------------

class PeriodFilter(BaseModel):
    """Period filter options for dashboard queries."""

    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")
    days: int = Field(default=30, description="Number of days to look back")


class BranchFilter(BaseModel):
    """Branch filter for scoped queries."""

    branch_ids: Optional[List[int]] = Field(default=None, description="List of branch IDs to include")
    include_all: bool = Field(default=True, description="Include all branches if no IDs specified")
