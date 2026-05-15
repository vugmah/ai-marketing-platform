"""Pydantic schemas for dashboard API responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Dashboard KPI Stats
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
