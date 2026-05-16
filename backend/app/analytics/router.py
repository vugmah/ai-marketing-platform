"""Analytics router for aggregated analytics data.

Provides endpoints for analytics overview, traffic trends, audience
demographics, conversion analytics, campaign analytics, branch KPIs,
ERP correlation, AI insights, and growth metrics.

All data is sourced from real database tables with SQLAlchemy
aggregation queries and cached in Redis with a 5-minute TTL.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.models import AdCampaign, AdMetric, CampaignStatus
from app.ai.models import (
    AIConversation,
    AIMessage,
    AIRecommendation,
    AISuggestion,
    AIUsageLog,
    AIModelName,
    MessageRole,
    RecommendationCategory,
    RecommendationStatus,
    SuggestionTriggerType,
)
from app.auth.models import User
from app.billing.models import UsageRecord
from app.branches.models import Branch
from app.companies.models import Company
from app.database import get_db
from app.dependencies import get_current_user
from app.erp.models import (
    ERPConnection,
    ERPCustomer,
    ERPInventory,
    ERPProduct,
    ERPSalesOrder,
    ERPSyncJob,
    SyncJobStatus,
    SyncStatus,
)
from app.redis_client import get_cache

from app.analytics.service import (
    get_conversion_analytics,
    get_campaign_analytics,
    get_branch_kpi_analytics,
    get_erp_correlation_analytics,
    get_ai_insights_analytics,
    get_growth_metrics,
    ANALYTICS_CACHE_TTL,
    _cache_key,
    _date_range_str,
    _apply_company_filter,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Tenant isolation helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/overview
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get analytics overview summary",
)
async def get_analytics_overview(
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return analytics overview with real DB aggregation.

    KPIs calculated from:
    - total_campaigns: active AdCampaign count
    - total_impressions: sum of AdMetric.impressions
    - total_clicks: sum of AdMetric.clicks
    - total_spend: sum of AdMetric.cost
    - avg_ctr: average CTR from AdMetric
    - active_branches: count of active branches
    - total_usage: count of UsageRecord entries

    Data is cached in Redis for 5 minutes with per-company tenant isolation.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    cache_key = _cache_key("overview", company_id, branch=branch_id)

    # Check cache first
    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    # --- 1. Active campaign count ---
    campaign_query = select(func.count()).select_from(AdCampaign).where(
        AdCampaign.status == CampaignStatus.ENABLED
    )
    campaign_query = _apply_company_filter(campaign_query, company_id, AdCampaign)
    if branch_id is not None:
        campaign_query = campaign_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(campaign_query)
    total_campaigns = result.scalar() or 0

    # --- 2. Ad metric aggregates (impressions, clicks, cost, CTR) ---
    metrics_query = select(
        func.coalesce(func.sum(AdMetric.impressions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
        func.coalesce(func.sum(AdMetric.cost), 0.0),
        func.coalesce(func.avg(AdMetric.ctr), 0.0),
    ).select_from(AdMetric)

    # Join with AdCampaign for tenant isolation
    metrics_query = metrics_query.join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    )
    metrics_query = _apply_company_filter(metrics_query, company_id, AdCampaign)
    if branch_id is not None:
        metrics_query = metrics_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(metrics_query)
    row = result.first()
    total_impressions = int(row[0]) if row else 0
    total_clicks = int(row[1]) if row else 0
    total_spend = float(row[2]) if row else 0.0
    avg_ctr = float(row[3]) if row else 0.0

    # --- 3. Active branch count ---
    branch_query = select(func.count()).select_from(Branch).where(
        Branch.is_active.is_(True)
    )
    branch_query = _apply_company_filter(branch_query, company_id, Branch)

    result = await db.execute(branch_query)
    active_branches = result.scalar() or 0

    # --- 4. Usage record count ---
    usage_query = select(func.count()).select_from(UsageRecord)
    usage_query = _apply_company_filter(usage_query, company_id, UsageRecord)

    result = await db.execute(usage_query)
    total_usage = result.scalar() or 0

    # --- 5. ROAS and conversion aggregates ---
    roas_query = select(
        func.coalesce(func.avg(AdMetric.roas), 0.0),
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.conversion_value), 0.0),
    ).select_from(AdMetric).join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    )
    roas_query = _apply_company_filter(roas_query, company_id, AdCampaign)
    if branch_id is not None:
        roas_query = roas_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(roas_query)
    roas_row = result.first()
    avg_roas = float(roas_row[0]) if roas_row else 0.0
    total_conversions = int(roas_row[1]) if roas_row else 0
    total_conversion_value = float(roas_row[2]) if roas_row else 0.0

    # --- 6. Platform breakdown ---
    platform_query = select(
        AdCampaign.platform,
        func.count(AdCampaign.id).label("campaign_count"),
        func.coalesce(func.sum(AdMetric.impressions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
    ).select_from(AdCampaign).outerjoin(
        AdMetric, AdCampaign.id == AdMetric.campaign_id
    ).group_by(AdCampaign.platform)
    platform_query = _apply_company_filter(platform_query, company_id, AdCampaign)
    if branch_id is not None:
        platform_query = platform_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(platform_query)
    platform_rows = result.all()

    platform_breakdown = []
    for p_row in platform_rows:
        platform_breakdown.append({
            "platform": p_row[0].value if hasattr(p_row[0], "value") else str(p_row[0]),
            "campaigns": int(p_row[1]),
            "impressions": int(p_row[2]),
            "clicks": int(p_row[3]),
        })

    # --- Assemble response ---
    data = {
        "total_campaigns": total_campaigns,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_spend": round(total_spend, 2),
        "avg_ctr": round(avg_ctr, 4),
        "avg_roas": round(avg_roas, 4),
        "total_conversions": total_conversions,
        "total_conversion_value": round(total_conversion_value, 2),
        "active_branches": active_branches,
        "total_usage_events": total_usage,
        "platform_breakdown": platform_breakdown,
    }

    # Empty dataset handling
    if total_campaigns == 0 and total_impressions == 0:
        data["meta"] = {"note": "No analytics data available for the current filters"}

    # Store in cache
    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)

    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/traffic
# ---------------------------------------------------------------------------


@router.get(
    "/traffic",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get daily traffic for the last N days",
)
async def get_traffic_data(
    days: int = Query(30, ge=1, le=90, description="Number of days to fetch"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return daily traffic data from AdMetric aggregation.

    Data is sourced from daily AdMetric records (impressions, clicks, cost)
    grouped by date for the requested date range.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    cache_key = _cache_key("traffic", company_id, days=days, branch=branch_id)

    # Check cache first
    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    # Compute date range
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    # Query daily aggregates from AdMetric via AdCampaign for tenant isolation
    query = select(
        AdMetric.date,
        func.coalesce(func.sum(AdMetric.impressions), 0).label("impressions"),
        func.coalesce(func.sum(AdMetric.clicks), 0).label("clicks"),
        func.coalesce(func.sum(AdMetric.cost), 0.0).label("cost"),
        func.coalesce(func.sum(AdMetric.conversions), 0).label("conversions"),
        func.coalesce(func.avg(AdMetric.ctr), 0.0).label("avg_ctr"),
    ).select_from(AdMetric).join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    ).where(
        AdMetric.date >= start_date,
        AdMetric.date <= end_date,
    ).group_by(
        AdMetric.date
    ).order_by(AdMetric.date)

    query = _apply_company_filter(query, company_id, AdCampaign)
    if branch_id is not None:
        query = query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(query)
    rows = result.all()

    # Build daily data arrays
    dates: List[str] = []
    impressions: List[int] = []
    clicks: List[int] = []
    costs: List[float] = []
    conversions: List[int] = []
    ctrs: List[float] = []

    if not rows:
        # Return empty dataset with proper structure
        data = {
            "dates": [],
            "impressions": [],
            "clicks": [],
            "costs": [],
            "conversions": [],
            "ctr": [],
            "meta": {
                "total": 0,
                "days": days,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "note": "No traffic data available for the current filters",
            },
        }
        await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
        return {"success": True, "data": data}

    for row in rows:
        dates.append(str(row[0]))
        impressions.append(int(row[1]))
        clicks.append(int(row[2]))
        costs.append(round(float(row[3]), 2))
        conversions.append(int(row[4]))
        ctrs.append(round(float(row[5]), 4))

    data = {
        "dates": dates,
        "impressions": impressions,
        "clicks": clicks,
        "costs": costs,
        "conversions": conversions,
        "ctr": ctrs,
        "meta": {
            "total": len(rows),
            "days": days,
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
    }

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/audience
# ---------------------------------------------------------------------------


@router.get(
    "/audience",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get audience demographics",
)
async def get_audience_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return audience demographics from real DB data.

    Sources:
    - city_breakdown: GROUP BY Branch.city with counts
    - company_growth: companies created per month
    - user_activity: active vs inactive user counts
    - branch_types: GROUP BY Branch.type
    """
    cache = await get_cache()
    company_id = current_user.company_id
    cache_key = _cache_key("audience", company_id)

    # Check cache first
    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    # --- 1. City breakdown from Branch table ---
    city_query = select(
        Branch.city,
        func.count(Branch.id).label("branch_count"),
        func.coalesce(func.sum(Branch.employee_count), 0).label("total_employees"),
    ).group_by(Branch.city).order_by(func.count(Branch.id).desc())

    city_query = _apply_company_filter(city_query, company_id, Branch)

    result = await db.execute(city_query)
    city_rows = result.all()

    city_breakdown = []
    for c_row in city_rows:
        city_breakdown.append({
            "city": c_row[0],
            "branches": int(c_row[1]),
            "employees": int(c_row[2]),
        })

    # --- 2. Branch type distribution ---
    type_query = select(
        Branch.type,
        func.count(Branch.id).label("count"),
    ).group_by(Branch.type)

    type_query = _apply_company_filter(type_query, company_id, Branch)

    result = await db.execute(type_query)
    type_rows = result.all()

    branch_types = []
    for t_row in type_rows:
        type_val = t_row[0].value if hasattr(t_row[0], "value") else str(t_row[0])
        branch_types.append({
            "type": type_val,
            "count": int(t_row[1]),
        })

    # --- 3. User activity status ---
    from app.auth.models import UserStatus

    user_status_query = select(
        User.status,
        func.count(User.id).label("count"),
    ).group_by(User.status)

    user_status_query = _apply_company_filter(user_status_query, company_id, User)

    result = await db.execute(user_status_query)
    user_rows = result.all()

    user_activity = {}
    for u_row in user_rows:
        status_val = u_row[0].value if hasattr(u_row[0], "value") else str(u_row[0])
        user_activity[status_val] = int(u_row[1])

    # --- 4. Company subscription status distribution ---
    from app.companies.models import SubscriptionStatus

    sub_query = select(
        Company.subscription_status,
        func.count(Company.id).label("count"),
    ).group_by(Company.subscription_status)

    result = await db.execute(sub_query)
    sub_rows = result.all()

    subscription_status = {}
    for s_row in sub_rows:
        status_val = s_row[0].value if hasattr(s_row[0], "value") else str(s_row[0])
        subscription_status[status_val] = int(s_row[1])

    # --- 5. Monthly company growth ---
    growth_query = select(
        func.date_trunc("month", Company.created_at).label("month"),
        func.count(Company.id).label("count"),
    ).group_by(
        func.date_trunc("month", Company.created_at)
    ).order_by(
        func.date_trunc("month", Company.created_at)
    )

    result = await db.execute(growth_query)
    growth_rows = result.all()

    monthly_growth = []
    for g_row in growth_rows:
        month_dt = g_row[0]
        month_str = month_dt.strftime("%Y-%m") if hasattr(month_dt, "strftime") else str(month_dt)[:7]
        monthly_growth.append({
            "month": month_str,
            "new_companies": int(g_row[1]),
        })

    # --- Assemble response ---
    data = {
        "city_breakdown": city_breakdown,
        "branch_types": branch_types,
        "user_activity": user_activity,
        "subscription_status": subscription_status,
        "monthly_growth": monthly_growth,
    }

    # Empty dataset handling
    if not city_breakdown and not branch_types:
        data["meta"] = {"note": "No audience data available for the current tenant"}

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/kpi
# ---------------------------------------------------------------------------


@router.get(
    "/kpi",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get detailed KPI metrics",
)
async def get_kpi_metrics(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return detailed KPI metrics with date range and branch filtering.

    Calculates:
    - impressions, clicks, conversions, cost totals
    - CTR, CPC, CPA, ROAS averages
    - Campaign count by status
    """
    cache = await get_cache()
    company_id = current_user.company_id

    # Parse date range
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    else:
        end_dt = datetime.now(timezone.utc).date()

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
    else:
        start_dt = end_dt - timedelta(days=30)

    date_range = _date_range_str(start_dt, end_dt)
    cache_key = _cache_key("kpi", company_id, range=date_range, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    # --- Core metrics ---
    query = select(
        func.coalesce(func.sum(AdMetric.impressions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.cost), 0.0),
        func.coalesce(func.avg(AdMetric.ctr), 0.0),
        func.coalesce(func.avg(AdMetric.cpc), 0.0),
        func.coalesce(func.avg(AdMetric.cpa), 0.0),
        func.coalesce(func.avg(AdMetric.roas), 0.0),
    ).select_from(AdMetric).join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    ).where(
        AdMetric.date >= start_dt,
        AdMetric.date <= end_dt,
    )

    query = _apply_company_filter(query, company_id, AdCampaign)
    if branch_id is not None:
        query = query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(query)
    row = result.first()

    # --- Campaign status breakdown ---
    status_query = select(
        AdCampaign.status,
        func.count(AdCampaign.id).label("count"),
    ).group_by(AdCampaign.status)

    status_query = _apply_company_filter(status_query, company_id, AdCampaign)
    if branch_id is not None:
        status_query = status_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(status_query)
    status_rows = result.all()

    campaign_status = {}
    for s_row in status_rows:
        status_val = s_row[0].value if hasattr(s_row[0], "value") else str(s_row[0])
        campaign_status[status_val] = int(s_row[1])

    data = {
        "impressions": int(row[0]) if row else 0,
        "clicks": int(row[1]) if row else 0,
        "conversions": int(row[2]) if row else 0,
        "cost": round(float(row[3]), 2) if row else 0.0,
        "ctr": round(float(row[4]), 4) if row else 0.0,
        "cpc": round(float(row[5]), 4) if row else 0.0,
        "cpa": round(float(row[6]), 4) if row else 0.0,
        "roas": round(float(row[7]), 4) if row else 0.0,
        "campaign_status": campaign_status,
        "date_range": {"start": str(start_dt), "end": str(end_dt)},
    }

    # Empty dataset handling
    if data["impressions"] == 0 and data["clicks"] == 0:
        data["meta"] = {"note": "No KPI data available for the current date range"}

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/branches
# ---------------------------------------------------------------------------


@router.get(
    "/branches",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get branch comparison analytics",
)
async def get_branch_comparison(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return branch-level comparison data with real DB aggregation.

    Groups metrics by branch: impressions, clicks, cost, conversions, CTR.
    """
    cache = await get_cache()
    company_id = current_user.company_id

    # Parse date range
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    else:
        end_dt = datetime.now(timezone.utc).date()

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
    else:
        start_dt = end_dt - timedelta(days=30)

    date_range = _date_range_str(start_dt, end_dt)
    cache_key = _cache_key("branches", company_id, range=date_range)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    # Branch comparison query with branch name
    query = select(
        Branch.id,
        Branch.name,
        Branch.city,
        func.coalesce(func.sum(AdMetric.impressions), 0).label("impressions"),
        func.coalesce(func.sum(AdMetric.clicks), 0).label("clicks"),
        func.coalesce(func.sum(AdMetric.cost), 0.0).label("cost"),
        func.coalesce(func.sum(AdMetric.conversions), 0).label("conversions"),
        func.coalesce(func.avg(AdMetric.ctr), 0.0).label("avg_ctr"),
        func.coalesce(func.avg(AdMetric.roas), 0.0).label("avg_roas"),
    ).select_from(Branch).outerjoin(
        AdCampaign, Branch.id == AdCampaign.branch_id
    ).outerjoin(
        AdMetric, AdCampaign.id == AdMetric.campaign_id
    ).where(
        AdMetric.date >= start_dt,
        AdMetric.date <= end_dt,
    ).group_by(
        Branch.id,
        Branch.name,
        Branch.city,
    ).order_by(func.sum(AdMetric.impressions).desc())

    if company_id is not None:
        query = query.where(Branch.company_id == company_id)

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        data = {
            "branches": [],
            "meta": {
                "total": 0,
                "date_range": {"start": str(start_dt), "end": str(end_dt)},
                "note": "No branch data available for the current filters",
            },
        }
        await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
        return {"success": True, "data": data}

    branches = []
    for row in rows:
        branches.append({
            "branch_id": row[0],
            "branch_name": row[1],
            "city": row[2],
            "impressions": int(row[3]),
            "clicks": int(row[4]),
            "cost": round(float(row[5]), 2),
            "conversions": int(row[6]),
            "ctr": round(float(row[7]), 4),
            "roas": round(float(row[8]), 4),
        })

    data = {
        "branches": branches,
        "meta": {
            "total": len(branches),
            "date_range": {"start": str(start_dt), "end": str(end_dt)},
        },
    }

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ===========================================================================
# NEW ANALYTICS ENDPOINTS (Agent 5 - Real DB Aggregation)
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. GET /api/v2/analytics/conversions
# ---------------------------------------------------------------------------


@router.get(
    "/conversions",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get conversion analytics (conversion rates, funnels)",
)
async def get_conversion_analytics_endpoint(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return conversion analytics with real DB aggregation.

    Calculates:
    - conversion_rate: clicks-to-conversion percentage
    - order_conversion_rate: ERP orders per new customers
    - revenue_per_conversion
    - Daily conversion trend
    - Campaign-level conversion breakdown

    Cached per-company with 5-minute TTL.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    date_range = _date_range_str(
        datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    cache_key = _cache_key("conversions", company_id, range=date_range, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    data = await get_conversion_analytics(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Empty dataset handling
    if data.get("_empty", False):
        data["meta"] = {"note": "No conversion data available for the current filters"}

    # Remove internal flag before returning
    data.pop("_empty", None)

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# 2. GET /api/v2/analytics/campaigns
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get campaign analytics (AI suggestion rates, recommendation stats)",
)
async def get_campaign_analytics_endpoint(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return campaign analytics with AI interaction rates.

    Calculates:
    - AI suggestion applied rate
    - Recommendation applied / dismissed / pending rates
    - Average confidence score
    - Category breakdown
    - Top performing campaigns

    Cached per-company with 5-minute TTL.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    date_range = _date_range_str(
        datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    cache_key = _cache_key("campaigns", company_id, range=date_range, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    data = await get_campaign_analytics(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
    )

    if data.get("_empty", False):
        data["meta"] = {"note": "No campaign analytics data available for the current filters"}

    data.pop("_empty", None)

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# 3. GET /api/v2/analytics/branches-kpi
# ---------------------------------------------------------------------------


@router.get(
    "/branches-kpi",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get detailed branch KPI aggregation",
)
async def get_branch_kpi_endpoint(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return detailed branch-level KPI analytics.

    Per-branch aggregation of:
    - Ad metrics (impressions, clicks, conversions, cost, CTR, ROAS, CPA)
    - Campaign counts
    - ERP order counts
    - AI recommendation counts
    - Branch metadata (employees, revenue target)

    Includes summary totals and averages across all branches.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    date_range = _date_range_str(
        datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    cache_key = _cache_key("branches-kpi", company_id, range=date_range, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    data = await get_branch_kpi_analytics(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
    )

    if data.get("_empty", False):
        data["meta"] = {"note": "No branch KPI data available for the current filters"}

    data.pop("_empty", None)

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# 4. GET /api/v2/analytics/erp-correlation
# ---------------------------------------------------------------------------


@router.get(
    "/erp-correlation",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get ERP sync + analytics cross-reference",
)
async def get_erp_correlation_endpoint(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return ERP-analytics correlation data.

    Cross-references:
    - ERP connection status and provider types
    - Sync job success/failure rates
    - Product/inventory counts
    - Sales orders correlated with ad spend
    - ROAS calculation from ERP revenue / ad spend
    - Customer growth

    Cached per-company with 5-minute TTL.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    date_range = _date_range_str(
        datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    cache_key = _cache_key("erp-correlation", company_id, range=date_range, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    data = await get_erp_correlation_analytics(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
    )

    if data.get("_empty", False):
        data["meta"] = {"note": "No ERP correlation data available for the current filters"}

    data.pop("_empty", None)

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# 5. GET /api/v2/analytics/ai-insights
# ---------------------------------------------------------------------------


@router.get(
    "/ai-insights",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get AI usage statistics (tokens, cost, latency)",
)
async def get_ai_insights_endpoint(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return AI usage analytics with token, cost, and latency metrics.

    Calculates:
    - Total token consumption (input/output)
    - Total estimated cost
    - Average/median latency in ms
    - Per-model breakdown
    - Daily usage trend
    - Suggestion trigger type distribution
    - Conversation metrics

    Cached per-company with 5-minute TTL.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    date_range = _date_range_str(
        datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    cache_key = _cache_key("ai-insights", company_id, range=date_range, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    data = await get_ai_insights_analytics(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
    )

    if data.get("_empty", False):
        data["meta"] = {"note": "No AI insights data available for the current filters"}

    data.pop("_empty", None)

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# 6. GET /api/v2/analytics/growth
# ---------------------------------------------------------------------------


@router.get(
    "/growth",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get month-over-month growth metrics",
)
async def get_growth_endpoint(
    months: int = Query(6, ge=2, le=24, description="Number of months to analyze"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return month-over-month growth metrics from real DB trend analysis.

    Tracks:
    - Campaign count MoM growth
    - Ad spend MoM growth
    - Conversion MoM growth
    - ERP order MoM growth
    - AI usage MoM growth
    - Impression/click trends

    Each month bucket contains absolute values and growth percentage
    relative to the previous month.

    Cached per-company with 5-minute TTL.
    """
    cache = await get_cache()
    company_id = current_user.company_id
    cache_key = _cache_key("growth", company_id, months=months, branch=branch_id)

    cached = await cache.get(cache_key)
    if cached:
        return {"success": True, "data": cached}

    data = await get_growth_metrics(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        months=months,
    )

    if data.get("_empty", False):
        data["meta"] = {"note": "No growth data available for the requested period"}

    data.pop("_empty", None)

    await cache.set(cache_key, data, ttl=ANALYTICS_CACHE_TTL)
    return {"success": True, "data": data}
