"""Analytics aggregation service.

Provides async DB aggregation functions for all analytics endpoints.
Each function performs real SQLAlchemy 2.0 async aggregation queries
with proper tenant isolation, date range filtering, and empty dataset handling.

All aggregation results are cached via the analytics router with a 5-minute TTL.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.models import AdCampaign, AdMetric, CampaignStatus
from app.ai.models import (
    AIRecommendation,
    AIUsageLog,
    RecommendationStatus,
    AISuggestion,
    AIConversation,
    AIMessage,
    AIModelName,
)
from app.branches.models import Branch
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANALYTICS_CACHE_TTL = 300  # 5 minutes in seconds


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def _cache_key(prefix: str, company_id: Optional[int], **params: Any) -> str:
    """Build a per-company scoped cache key with optional parameters."""
    parts = [f"analytics:{prefix}", str(company_id or "global")]
    for key, value in sorted(params.items()):
        if value is not None:
            parts.append(f"{key}:{value}")
    return ":".join(parts)


def _date_range_str(start: Optional[date], end: Optional[date]) -> str:
    """Serialize a date range for cache keys."""
    s = start.isoformat() if start else "_"
    e = end.isoformat() if end else "_"
    return f"{s}_{e}"


# ---------------------------------------------------------------------------
# Tenant isolation helper
# ---------------------------------------------------------------------------


def _apply_company_filter(query, company_id: Optional[int], model) -> Any:
    """Apply company_id tenant isolation to a query."""
    if company_id is not None:
        return query.where(model.company_id == company_id)
    return query


# ---------------------------------------------------------------------------
# Date range parser
# ---------------------------------------------------------------------------


def _parse_date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    default_days: int = 30,
) -> Tuple[date, date]:
    """Parse optional date strings and return a validated (start, end) range."""
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid end_date format. Use YYYY-MM-DD")
    else:
        end_dt = datetime.now(timezone.utc).date()

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid start_date format. Use YYYY-MM-DD")
    else:
        start_dt = end_dt - timedelta(days=default_days)

    return start_dt, end_dt


# ---------------------------------------------------------------------------
# 1. Conversion Analytics
# ---------------------------------------------------------------------------


async def get_conversion_analytics(
    db: AsyncSession,
    company_id: Optional[int],
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate conversion analytics from AdMetric and ERPSalesOrder.

    Calculates:
    - conversion_rate: clicks-to-conversion ratio from ad metrics
    - order_conversion_rate: ERP orders-to-customers ratio
    - total_conversions, total_clicks, total_impressions
    - revenue_per_conversion, total_conversion_value
    - daily conversion trend

    Args:
        db: Async SQLAlchemy session.
        company_id: Tenant filter (required for isolation).
        branch_id: Optional branch filter.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        Dictionary with conversion KPIs and trend data.
    """
    start_dt, end_dt = _parse_date_range(start_date, end_date, default_days=30)

    # --- 1. Core ad conversion aggregates ---
    query = select(
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
        func.coalesce(func.sum(AdMetric.impressions), 0),
        func.coalesce(func.sum(AdMetric.conversion_value), 0.0),
        func.coalesce(func.avg(AdMetric.ctr), 0.0),
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

    total_conversions = int(row[0]) if row else 0
    total_clicks = int(row[1]) if row else 0
    total_impressions = int(row[2]) if row else 0
    total_conversion_value = float(row[3]) if row else 0.0
    avg_ctr = float(row[4]) if row else 0.0
    avg_roas = float(row[5]) if row else 0.0

    # --- 2. Conversion funnel rates ---
    click_through_rate = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0.0
    impression_to_conversion_rate = (total_conversions / total_impressions * 100) if total_impressions > 0 else 0.0

    # --- 3. ERP-based order/customer data ---
    erp_order_query = select(
        func.count(ERPSalesOrder.id),
        func.coalesce(func.sum(ERPSalesOrder.total_amount), 0.0),
    ).where(
        ERPSalesOrder.order_date >= datetime.combine(start_dt, datetime.min.time()),
        ERPSalesOrder.order_date <= datetime.combine(end_dt, datetime.max.time()),
    )
    erp_order_query = _apply_company_filter(erp_order_query, company_id, ERPSalesOrder)
    if branch_id is not None:
        erp_order_query = erp_order_query.where(ERPSalesOrder.branch_id == branch_id)

    result = await db.execute(erp_order_query)
    order_row = result.first()
    total_orders = int(order_row[0]) if order_row else 0
    total_order_value = float(order_row[1]) if order_row else 0.0

    # --- 4. Distinct customer count from ERP ---
    customer_query = select(
        func.count(func.distinct(ERPCustomer.external_id)),
    ).where(
        ERPCustomer.created_at >= datetime.combine(start_dt, datetime.min.time()),
        ERPCustomer.created_at <= datetime.combine(end_dt, datetime.max.time()),
    )
    customer_query = _apply_company_filter(customer_query, company_id, ERPCustomer)
    if branch_id is not None:
        customer_query = customer_query.where(ERPCustomer.branch_id == branch_id)

    result = await db.execute(customer_query)
    new_customers = result.scalar() or 0

    # --- 5. Order-to-customer conversion rate ---
    order_conversion_rate = (total_orders / new_customers * 100) if new_customers > 0 else 0.0

    # --- 6. Daily conversion trend ---
    trend_query = select(
        AdMetric.date,
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
        func.coalesce(func.sum(AdMetric.conversion_value), 0.0),
    ).select_from(AdMetric).join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    ).where(
        AdMetric.date >= start_dt,
        AdMetric.date <= end_dt,
    ).group_by(
        AdMetric.date,
    ).order_by(AdMetric.date)

    trend_query = _apply_company_filter(trend_query, company_id, AdCampaign)
    if branch_id is not None:
        trend_query = trend_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(trend_query)
    trend_rows = result.all()

    daily_trend = []
    for t_row in trend_rows:
        conv = int(t_row[1])
        clicks = int(t_row[2])
        conv_rate = (conv / clicks * 100) if clicks > 0 else 0.0
        daily_trend.append({
            "date": str(t_row[0]),
            "conversions": conv,
            "clicks": clicks,
            "conversion_rate": round(conv_rate, 4),
            "conversion_value": round(float(t_row[3]), 2),
        })

    # --- 7. Campaign-level conversion breakdown ---
    campaign_query = select(
        AdCampaign.id,
        AdCampaign.name,
        AdCampaign.platform,
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
        func.coalesce(func.sum(AdMetric.conversion_value), 0.0),
    ).select_from(AdCampaign).outerjoin(
        AdMetric,
        (AdCampaign.id == AdMetric.campaign_id) &
        (AdMetric.date >= start_dt) &
        (AdMetric.date <= end_dt),
    ).group_by(
        AdCampaign.id,
        AdCampaign.name,
        AdCampaign.platform,
    )

    campaign_query = _apply_company_filter(campaign_query, company_id, AdCampaign)
    if branch_id is not None:
        campaign_query = campaign_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(campaign_query)
    camp_rows = result.all()

    campaign_conversions = []
    for c_row in camp_rows:
        c_conv = int(c_row[3])
        c_clicks = int(c_row[4])
        c_rate = (c_conv / c_clicks * 100) if c_clicks > 0 else 0.0
        campaign_conversions.append({
            "campaign_id": c_row[0],
            "campaign_name": c_row[1],
            "platform": c_row[2].value if hasattr(c_row[2], "value") else str(c_row[2]),
            "conversions": c_conv,
            "conversion_value": round(float(c_row[5]), 2),
            "conversion_rate": round(c_rate, 4),
        })

    return {
        "conversion_rate": round(conversion_rate, 4),
        "click_through_rate": round(click_through_rate, 4),
        "impression_to_conversion_rate": round(impression_to_conversion_rate, 4),
        "order_conversion_rate": round(order_conversion_rate, 4),
        "total_conversions": total_conversions,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "total_conversion_value": round(total_conversion_value, 2),
        "revenue_per_conversion": round(total_conversion_value / total_conversions, 2) if total_conversions > 0 else 0.0,
        "total_orders": total_orders,
        "total_order_value": round(total_order_value, 2),
        "new_customers": new_customers,
        "avg_ctr": round(avg_ctr, 4),
        "avg_roas": round(avg_roas, 4),
        "daily_trend": daily_trend,
        "campaign_conversions": campaign_conversions,
        "date_range": {"start": str(start_dt), "end": str(end_dt)},
        "_empty": total_conversions == 0 and total_orders == 0,
    }


# ---------------------------------------------------------------------------
# 2. Campaign Analytics
# ---------------------------------------------------------------------------


async def get_campaign_analytics(
    db: AsyncSession,
    company_id: Optional[int],
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate campaign analytics including AI recommendation rates.

    Calculates:
    - campaign_count by status
    - ai_suggestion_applied_rate: % of AI suggestions that were applied
    - recommendation_dismissal_rate: % of recommendations dismissed
    - recommendation_applied_rate: % of recommendations applied
    - avg_confidence_score of recommendations
    - top performing campaigns

    Args:
        db: Async SQLAlchemy session.
        company_id: Tenant filter.
        branch_id: Optional branch filter.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        Dictionary with campaign KPIs and AI interaction rates.
    """
    start_dt, end_dt = _parse_date_range(start_date, end_date, default_days=30)
    start_dt_naive = datetime.combine(start_dt, datetime.min.time())
    end_dt_naive = datetime.combine(end_dt, datetime.max.time())

    # --- 1. Campaign count by status ---
    status_query = select(
        AdCampaign.status,
        func.count(AdCampaign.id).label("count"),
    ).group_by(AdCampaign.status)

    status_query = _apply_company_filter(status_query, company_id, AdCampaign)
    if branch_id is not None:
        status_query = status_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(status_query)
    status_rows = result.all()

    campaign_status_counts = {}
    total_campaigns = 0
    for s_row in status_rows:
        val = s_row[0].value if hasattr(s_row[0], "value") else str(s_row[0])
        count = int(s_row[1])
        campaign_status_counts[val] = count
        total_campaigns += count

    # --- 2. AI Suggestion analytics ---
    suggestion_total_query = select(func.count(AISuggestion.id))
    suggestion_total_query = _apply_company_filter(suggestion_total_query, company_id, AISuggestion)
    if branch_id is not None:
        suggestion_total_query = suggestion_total_query.where(AISuggestion.branch_id == branch_id)
    if start_date or end_date:
        suggestion_total_query = suggestion_total_query.where(
            AISuggestion.created_at >= start_dt_naive,
            AISuggestion.created_at <= end_dt_naive,
        )

    result = await db.execute(suggestion_total_query)
    total_suggestions = result.scalar() or 0

    suggestion_applied_query = select(func.count(AISuggestion.id)).where(
        AISuggestion.was_applied.is_(True)
    )
    suggestion_applied_query = _apply_company_filter(suggestion_applied_query, company_id, AISuggestion)
    if branch_id is not None:
        suggestion_applied_query = suggestion_applied_query.where(AISuggestion.branch_id == branch_id)
    if start_date or end_date:
        suggestion_applied_query = suggestion_applied_query.where(
            AISuggestion.created_at >= start_dt_naive,
            AISuggestion.created_at <= end_dt_naive,
        )

    result = await db.execute(suggestion_applied_query)
    applied_suggestions = result.scalar() or 0

    suggestion_rate = (applied_suggestions / total_suggestions * 100) if total_suggestions > 0 else 0.0

    # --- 3. AI Recommendation analytics ---
    rec_total_query = select(
        func.count(AIRecommendation.id),
    )
    rec_total_query = _apply_company_filter(rec_total_query, company_id, AIRecommendation)
    if branch_id is not None:
        rec_total_query = rec_total_query.where(AIRecommendation.branch_id == branch_id)
    if start_date or end_date:
        rec_total_query = rec_total_query.where(
            AIRecommendation.created_at >= start_dt_naive,
            AIRecommendation.created_at <= end_dt_naive,
        )

    result = await db.execute(rec_total_query)
    total_recommendations = result.scalar() or 0

    # Applied
    rec_applied_query = select(func.count(AIRecommendation.id)).where(
        AIRecommendation.status == RecommendationStatus.APPLIED
    )
    rec_applied_query = _apply_company_filter(rec_applied_query, company_id, AIRecommendation)
    if branch_id is not None:
        rec_applied_query = rec_applied_query.where(AIRecommendation.branch_id == branch_id)
    if start_date or end_date:
        rec_applied_query = rec_applied_query.where(
            AIRecommendation.created_at >= start_dt_naive,
            AIRecommendation.created_at <= end_dt_naive,
        )

    result = await db.execute(rec_applied_query)
    applied_recommendations = result.scalar() or 0

    # Dismissed
    rec_dismissed_query = select(func.count(AIRecommendation.id)).where(
        AIRecommendation.status == RecommendationStatus.DISMISSED
    )
    rec_dismissed_query = _apply_company_filter(rec_dismissed_query, company_id, AIRecommendation)
    if branch_id is not None:
        rec_dismissed_query = rec_dismissed_query.where(AIRecommendation.branch_id == branch_id)
    if start_date or end_date:
        rec_dismissed_query = rec_dismissed_query.where(
            AIRecommendation.created_at >= start_dt_naive,
            AIRecommendation.created_at <= end_dt_naive,
        )

    result = await db.execute(rec_dismissed_query)
    dismissed_recommendations = result.scalar() or 0

    # Pending
    rec_pending_query = select(func.count(AIRecommendation.id)).where(
        AIRecommendation.status == RecommendationStatus.PENDING
    )
    rec_pending_query = _apply_company_filter(rec_pending_query, company_id, AIRecommendation)
    if branch_id is not None:
        rec_pending_query = rec_pending_query.where(AIRecommendation.branch_id == branch_id)
    if start_date or end_date:
        rec_pending_query = rec_pending_query.where(
            AIRecommendation.created_at >= start_dt_naive,
            AIRecommendation.created_at <= end_dt_naive,
        )

    result = await db.execute(rec_pending_query)
    pending_recommendations = result.scalar() or 0

    # --- 4. Confidence score aggregates ---
    conf_query = select(
        func.coalesce(func.avg(AIRecommendation.confidence_score), 0.0),
        func.coalesce(func.max(AIRecommendation.confidence_score), 0.0),
        func.coalesce(func.min(AIRecommendation.confidence_score), 0.0),
    )
    conf_query = _apply_company_filter(conf_query, company_id, AIRecommendation)
    if branch_id is not None:
        conf_query = conf_query.where(AIRecommendation.branch_id == branch_id)
    if start_date or end_date:
        conf_query = conf_query.where(
            AIRecommendation.created_at >= start_dt_naive,
            AIRecommendation.created_at <= end_dt_naive,
        )

    result = await db.execute(conf_query)
    conf_row = result.first()
    avg_confidence = float(conf_row[0]) if conf_row else 0.0
    max_confidence = float(conf_row[1]) if conf_row else 0.0
    min_confidence = float(conf_row[2]) if conf_row else 0.0

    applied_rate = (applied_recommendations / total_recommendations * 100) if total_recommendations > 0 else 0.0
    dismissal_rate = (dismissed_recommendations / total_recommendations * 100) if total_recommendations > 0 else 0.0

    # --- 5. Category breakdown ---
    cat_query = select(
        AIRecommendation.category,
        func.count(AIRecommendation.id),
        func.coalesce(func.avg(AIRecommendation.confidence_score), 0.0),
    ).group_by(AIRecommendation.category)
    cat_query = _apply_company_filter(cat_query, company_id, AIRecommendation)
    if branch_id is not None:
        cat_query = cat_query.where(AIRecommendation.branch_id == branch_id)
    if start_date or end_date:
        cat_query = cat_query.where(
            AIRecommendation.created_at >= start_dt_naive,
            AIRecommendation.created_at <= end_dt_naive,
        )

    result = await db.execute(cat_query)
    cat_rows = result.all()

    category_breakdown = []
    for cat_row in cat_rows:
        category_breakdown.append({
            "category": cat_row[0].value if hasattr(cat_row[0], "value") else str(cat_row[0]),
            "count": int(cat_row[1]),
            "avg_confidence": round(float(cat_row[2]), 4),
        })

    # --- 6. Top campaigns by conversions in date range ---
    top_campaigns_query = select(
        AdCampaign.id,
        AdCampaign.name,
        AdCampaign.platform,
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
        func.coalesce(func.sum(AdMetric.impressions), 0),
        func.coalesce(func.sum(AdMetric.cost), 0.0),
    ).select_from(AdCampaign).outerjoin(
        AdMetric,
        (AdCampaign.id == AdMetric.campaign_id) &
        (AdMetric.date >= start_dt) &
        (AdMetric.date <= end_dt),
    ).group_by(
        AdCampaign.id,
        AdCampaign.name,
        AdCampaign.platform,
    ).order_by(func.sum(AdMetric.conversions).desc()).limit(10)

    top_campaigns_query = _apply_company_filter(top_campaigns_query, company_id, AdCampaign)
    if branch_id is not None:
        top_campaigns_query = top_campaigns_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(top_campaigns_query)
    top_rows = result.all()

    top_campaigns = []
    for t_row in top_rows:
        top_campaigns.append({
            "campaign_id": t_row[0],
            "campaign_name": t_row[1],
            "platform": t_row[2].value if hasattr(t_row[2], "value") else str(t_row[2]),
            "conversions": int(t_row[3]),
            "clicks": int(t_row[4]),
            "impressions": int(t_row[5]),
            "cost": round(float(t_row[6]), 2),
        })

    return {
        "total_campaigns": total_campaigns,
        "campaign_status": campaign_status_counts,
        "ai_suggestion_applied_rate": round(suggestion_rate, 4),
        "total_suggestions": total_suggestions,
        "applied_suggestions": applied_suggestions,
        "recommendation_applied_rate": round(applied_rate, 4),
        "recommendation_dismissal_rate": round(dismissal_rate, 4),
        "total_recommendations": total_recommendations,
        "applied_recommendations": applied_recommendations,
        "dismissed_recommendations": dismissed_recommendations,
        "pending_recommendations": pending_recommendations,
        "avg_confidence_score": round(avg_confidence, 4),
        "max_confidence_score": round(max_confidence, 4),
        "min_confidence_score": round(min_confidence, 4),
        "category_breakdown": category_breakdown,
        "top_campaigns": top_campaigns,
        "date_range": {"start": str(start_dt), "end": str(end_dt)},
        "_empty": total_campaigns == 0 and total_suggestions == 0 and total_recommendations == 0,
    }


# ---------------------------------------------------------------------------
# 3. Branch KPI Analytics
# ---------------------------------------------------------------------------


async def get_branch_kpi_analytics(
    db: AsyncSession,
    company_id: Optional[int],
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate branch-level KPI analytics.

    Calculates per-branch:
    - impressions, clicks, conversions, cost totals
    - CTR, ROAS, CPA averages
    - campaign counts
    - ERP order/customer correlation
    - AI recommendation counts

    Args:
        db: Async SQLAlchemy session.
        company_id: Tenant filter.
        branch_id: Optional single branch filter.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        Dictionary with branch KPI array and summary.
    """
    start_dt, end_dt = _parse_date_range(start_date, end_date, default_days=30)

    # --- 1. Branch list with filters ---
    branch_query = select(
        Branch.id,
        Branch.name,
        Branch.city,
        Branch.type,
        Branch.status,
        Branch.employee_count,
        Branch.monthly_revenue_target,
    )
    if company_id is not None:
        branch_query = branch_query.where(Branch.company_id == company_id)
    if branch_id is not None:
        branch_query = branch_query.where(Branch.id == branch_id)

    result = await db.execute(branch_query)
    branch_rows = result.all()

    if not branch_rows:
        return {
            "branches": [],
            "summary": {
                "total_branches": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "total_conversions": 0,
                "total_cost": 0.0,
            },
            "date_range": {"start": str(start_dt), "end": str(end_dt)},
            "_empty": True,
        }

    branches_data = []
    total_impressions = 0
    total_clicks = 0
    total_conversions = 0
    total_cost = 0.0

    for b_row in branch_rows:
        bid = b_row[0]

        # --- Ad metrics for this branch ---
        ad_query = select(
            func.coalesce(func.sum(AdMetric.impressions), 0),
            func.coalesce(func.sum(AdMetric.clicks), 0),
            func.coalesce(func.sum(AdMetric.conversions), 0),
            func.coalesce(func.sum(AdMetric.cost), 0.0),
            func.coalesce(func.avg(AdMetric.ctr), 0.0),
            func.coalesce(func.avg(AdMetric.roas), 0.0),
            func.coalesce(func.avg(AdMetric.cpa), 0.0),
        ).select_from(AdMetric).join(
            AdCampaign, AdMetric.campaign_id == AdCampaign.id
        ).where(
            AdCampaign.branch_id == bid,
            AdMetric.date >= start_dt,
            AdMetric.date <= end_dt,
        )

        result = await db.execute(ad_query)
        ad_row = result.first()

        b_impressions = int(ad_row[0]) if ad_row else 0
        b_clicks = int(ad_row[1]) if ad_row else 0
        b_conversions = int(ad_row[2]) if ad_row else 0
        b_cost = float(ad_row[3]) if ad_row else 0.0
        b_ctr = float(ad_row[4]) if ad_row else 0.0
        b_roas = float(ad_row[5]) if ad_row else 0.0
        b_cpa = float(ad_row[6]) if ad_row else 0.0

        # --- Campaign count for this branch ---
        camp_query = select(func.count(AdCampaign.id)).where(AdCampaign.branch_id == bid)
        camp_query = _apply_company_filter(camp_query, company_id, AdCampaign)

        result = await db.execute(camp_query)
        b_campaigns = result.scalar() or 0

        # --- ERP order count ---
        order_query = select(func.count(ERPSalesOrder.id)).where(
            ERPSalesOrder.branch_id == bid,
            ERPSalesOrder.order_date >= datetime.combine(start_dt, datetime.min.time()),
            ERPSalesOrder.order_date <= datetime.combine(end_dt, datetime.max.time()),
        )
        order_query = _apply_company_filter(order_query, company_id, ERPSalesOrder)

        result = await db.execute(order_query)
        b_orders = result.scalar() or 0

        # --- AI recommendation count ---
        rec_query = select(func.count(AIRecommendation.id)).where(AIRecommendation.branch_id == bid)
        rec_query = _apply_company_filter(rec_query, company_id, AIRecommendation)

        result = await db.execute(rec_query)
        b_recommendations = result.scalar() or 0

        total_impressions += b_impressions
        total_clicks += b_clicks
        total_conversions += b_conversions
        total_cost += b_cost

        branches_data.append({
            "branch_id": bid,
            "branch_name": b_row[1],
            "city": b_row[2],
            "type": b_row[3].value if hasattr(b_row[3], "value") else str(b_row[3]),
            "status": b_row[4].value if hasattr(b_row[4], "value") else str(b_row[4]),
            "employee_count": b_row[5],
            "revenue_target": b_row[6],
            "impressions": b_impressions,
            "clicks": b_clicks,
            "conversions": b_conversions,
            "cost": round(b_cost, 2),
            "ctr": round(b_ctr, 4),
            "roas": round(b_roas, 4),
            "cpa": round(b_cpa, 4),
            "campaigns": b_campaigns,
            "orders": b_orders,
            "ai_recommendations": b_recommendations,
        })

    return {
        "branches": branches_data,
        "summary": {
            "total_branches": len(branches_data),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_cost": round(total_cost, 2),
            "avg_ctr": round((total_clicks / total_impressions * 100), 4) if total_impressions > 0 else 0.0,
        },
        "date_range": {"start": str(start_dt), "end": str(end_dt)},
        "_empty": len(branches_data) == 0,
    }


# ---------------------------------------------------------------------------
# 4. ERP Correlation Analytics
# ---------------------------------------------------------------------------


async def get_erp_correlation_analytics(
    db: AsyncSession,
    company_id: Optional[int],
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Cross-reference ERP sync data with analytics metrics.

    Calculates:
    - ERP connection status summary
    - Sync job success/failure rates
    - Product/inventory counts
    - Sales order correlation with ad spend
    - Customer growth

    Args:
        db: Async SQLAlchemy session.
        company_id: Tenant filter.
        branch_id: Optional branch filter.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        Dictionary with ERP-analytics correlation data.
    """
    start_dt, end_dt = _parse_date_range(start_date, end_date, default_days=30)
    start_dt_naive = datetime.combine(start_dt, datetime.min.time())
    end_dt_naive = datetime.combine(end_dt, datetime.max.time())

    # --- 1. ERP connection summary ---
    conn_query = select(
        ERPConnection.provider_type,
        func.count(ERPConnection.id),
        ERPConnection.last_sync_status,
    ).group_by(ERPConnection.provider_type, ERPConnection.last_sync_status)
    conn_query = _apply_company_filter(conn_query, company_id, ERPConnection)
    if branch_id is not None:
        conn_query = conn_query.where(ERPConnection.branch_id == branch_id)

    result = await db.execute(conn_query)
    conn_rows = result.all()

    connections = []
    for c_row in conn_rows:
        connections.append({
            "provider": c_row[0].value if hasattr(c_row[0], "value") else str(c_row[0]),
            "count": int(c_row[1]),
            "sync_status": c_row[2].value if hasattr(c_row[2], "value") else str(c_row[2]),
        })

    # --- 2. Total active connections ---
    active_conn_query = select(func.count(ERPConnection.id)).where(
        ERPConnection.is_active.is_(True)
    )
    active_conn_query = _apply_company_filter(active_conn_query, company_id, ERPConnection)
    if branch_id is not None:
        active_conn_query = active_conn_query.where(ERPConnection.branch_id == branch_id)

    result = await db.execute(active_conn_query)
    active_connections = result.scalar() or 0

    # --- 3. Sync job analytics ---
    job_query = select(
        ERPSyncJob.status,
        func.count(ERPSyncJob.id),
        func.coalesce(func.sum(ERPSyncJob.records_processed), 0),
        func.coalesce(func.sum(ERPSyncJob.records_failed), 0),
    ).where(
        ERPSyncJob.created_at >= start_dt_naive,
        ERPSyncJob.created_at <= end_dt_naive,
    ).group_by(ERPSyncJob.status)
    job_query = _apply_company_filter(job_query, company_id, ERPSyncJob)
    if branch_id is not None:
        job_query = job_query.where(ERPSyncJob.branch_id == branch_id)

    result = await db.execute(job_query)
    job_rows = result.all()

    sync_jobs = {}
    total_records_processed = 0
    total_records_failed = 0
    for j_row in job_rows:
        status_val = j_row[0].value if hasattr(j_row[0], "value") else str(j_row[0])
        rec_processed = int(j_row[2])
        rec_failed = int(j_row[3])
        sync_jobs[status_val] = {
            "count": int(j_row[1]),
            "records_processed": rec_processed,
            "records_failed": rec_failed,
        }
        total_records_processed += rec_processed
        total_records_failed += rec_failed

    # --- 4. Product catalog size ---
    product_query = select(func.count(ERPProduct.id))
    product_query = _apply_company_filter(product_query, company_id, ERPProduct)
    if branch_id is not None:
        product_query = product_query.where(ERPProduct.branch_id == branch_id)

    result = await db.execute(product_query)
    total_products = result.scalar() or 0

    # --- 5. Inventory summary ---
    inv_query = select(
        func.coalesce(func.sum(ERPInventory.quantity_available), 0.0),
        func.coalesce(func.sum(ERPInventory.quantity_reserved), 0.0),
        func.count(ERPInventory.id),
    )
    inv_query = _apply_company_filter(inv_query, company_id, ERPInventory)
    if branch_id is not None:
        inv_query = inv_query.where(ERPInventory.branch_id == branch_id)

    result = await db.execute(inv_query)
    inv_row = result.first()
    total_inventory_available = float(inv_row[0]) if inv_row else 0.0
    total_inventory_reserved = float(inv_row[1]) if inv_row else 0.0
    inventory_skus = int(inv_row[2]) if inv_row else 0

    # --- 6. Sales order summary ---
    so_query = select(
        func.count(ERPSalesOrder.id),
        func.coalesce(func.sum(ERPSalesOrder.total_amount), 0.0),
        func.coalesce(func.sum(ERPSalesOrder.tax_amount), 0.0),
        func.coalesce(func.sum(ERPSalesOrder.discount_amount), 0.0),
    ).where(
        ERPSalesOrder.order_date >= start_dt_naive,
        ERPSalesOrder.order_date <= end_dt_naive,
    )
    so_query = _apply_company_filter(so_query, company_id, ERPSalesOrder)
    if branch_id is not None:
        so_query = so_query.where(ERPSalesOrder.branch_id == branch_id)

    result = await db.execute(so_query)
    so_row = result.first()
    total_orders = int(so_row[0]) if so_row else 0
    total_order_value = float(so_row[1]) if so_row else 0.0
    total_tax = float(so_row[2]) if so_row else 0.0
    total_discount = float(so_row[3]) if so_row else 0.0

    # --- 7. Ad spend in same period (for correlation) ---
    ad_spend_query = select(
        func.coalesce(func.sum(AdMetric.cost), 0.0),
        func.coalesce(func.sum(AdMetric.conversions), 0),
    ).select_from(AdMetric).join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    ).where(
        AdMetric.date >= start_dt,
        AdMetric.date <= end_dt,
    )
    ad_spend_query = _apply_company_filter(ad_spend_query, company_id, AdCampaign)
    if branch_id is not None:
        ad_spend_query = ad_spend_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(ad_spend_query)
    ad_row = result.first()
    ad_spend = float(ad_row[0]) if ad_row else 0.0
    ad_conversions = int(ad_row[1]) if ad_row else 0

    # --- 8. ROAS: Revenue from orders / Ad spend ---
    roas = (total_order_value / ad_spend) if ad_spend > 0 else 0.0

    # --- 9. Customer count ---
    cust_query = select(func.count(ERPCustomer.id))
    cust_query = _apply_company_filter(cust_query, company_id, ERPCustomer)
    if branch_id is not None:
        cust_query = cust_query.where(ERPCustomer.branch_id == branch_id)

    result = await db.execute(cust_query)
    total_customers = result.scalar() or 0

    # --- 10. Sync success rate ---
    total_jobs = sum(j["count"] for j in sync_jobs.values())
    completed_jobs = sync_jobs.get("completed", {}).get("count", 0)
    sync_success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0.0

    return {
        "active_connections": active_connections,
        "connections": connections,
        "sync_jobs": sync_jobs,
        "sync_success_rate": round(sync_success_rate, 4),
        "total_records_processed": total_records_processed,
        "total_records_failed": total_records_failed,
        "total_products": total_products,
        "inventory": {
            "total_available": round(total_inventory_available, 2),
            "total_reserved": round(total_inventory_reserved, 2),
            "sku_count": inventory_skus,
        },
        "sales_orders": {
            "total_orders": total_orders,
            "total_value": round(total_order_value, 2),
            "total_tax": round(total_tax, 2),
            "total_discount": round(total_discount, 2),
        },
        "ad_spend": round(ad_spend, 2),
        "ad_conversions": ad_conversions,
        "roas": round(roas, 4),
        "total_customers": total_customers,
        "date_range": {"start": str(start_dt), "end": str(end_dt)},
        "_empty": active_connections == 0 and total_orders == 0 and total_products == 0,
    }


# ---------------------------------------------------------------------------
# 5. AI Insights Analytics
# ---------------------------------------------------------------------------


async def get_ai_insights_analytics(
    db: AsyncSession,
    company_id: Optional[int],
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate AI usage statistics: tokens, cost, latency.

    Calculates:
    - Total token consumption (input/output)
    - Total estimated cost
    - Average/median latency
    - Requests per model
    - Daily usage trend
    - Suggestion trigger type distribution
    - Conversation metrics

    Args:
        db: Async SQLAlchemy session.
        company_id: Tenant filter.
        branch_id: Optional branch filter.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        Dictionary with AI usage KPIs.
    """
    start_dt, end_dt = _parse_date_range(start_date, end_date, default_days=30)
    start_dt_naive = datetime.combine(start_dt, datetime.min.time())
    end_dt_naive = datetime.combine(end_dt, datetime.max.time())

    # --- 1. Token and cost aggregates ---
    token_query = select(
        func.coalesce(func.sum(AIUsageLog.tokens_input), 0),
        func.coalesce(func.sum(AIUsageLog.tokens_output), 0),
        func.coalesce(func.sum(AIUsageLog.cost_estimate), 0.0),
        func.coalesce(func.avg(AIUsageLog.latency_ms), 0.0),
        func.coalesce(func.max(AIUsageLog.latency_ms), 0),
        func.coalesce(func.min(AIUsageLog.latency_ms), 0),
        func.count(AIUsageLog.id),
    ).where(
        AIUsageLog.created_at >= start_dt_naive,
        AIUsageLog.created_at <= end_dt_naive,
    )
    token_query = _apply_company_filter(token_query, company_id, AIUsageLog)

    result = await db.execute(token_query)
    t_row = result.first()
    total_tokens_input = int(t_row[0]) if t_row else 0
    total_tokens_output = int(t_row[1]) if t_row else 0
    total_cost = float(t_row[2]) if t_row else 0.0
    avg_latency = float(t_row[3]) if t_row else 0.0
    max_latency = int(t_row[4]) if t_row else 0
    min_latency = int(t_row[5]) if t_row else 0
    total_requests = int(t_row[6]) if t_row else 0

    # --- 2. Per-model breakdown ---
    model_query = select(
        AIUsageLog.model,
        func.count(AIUsageLog.id),
        func.coalesce(func.sum(AIUsageLog.tokens_input), 0),
        func.coalesce(func.sum(AIUsageLog.tokens_output), 0),
        func.coalesce(func.sum(AIUsageLog.cost_estimate), 0.0),
        func.coalesce(func.avg(AIUsageLog.latency_ms), 0.0),
    ).where(
        AIUsageLog.created_at >= start_dt_naive,
        AIUsageLog.created_at <= end_dt_naive,
    ).group_by(AIUsageLog.model)
    model_query = _apply_company_filter(model_query, company_id, AIUsageLog)

    result = await db.execute(model_query)
    model_rows = result.all()

    model_breakdown = []
    for m_row in model_rows:
        model_breakdown.append({
            "model": m_row[0].value if hasattr(m_row[0], "value") else str(m_row[0]),
            "requests": int(m_row[1]),
            "tokens_input": int(m_row[2]),
            "tokens_output": int(m_row[3]),
            "cost": round(float(m_row[4]), 4),
            "avg_latency_ms": round(float(m_row[5]), 2),
        })

    # --- 3. Daily usage trend ---
    daily_query = select(
        func.date_trunc("day", AIUsageLog.created_at).label("day"),
        func.count(AIUsageLog.id),
        func.coalesce(func.sum(AIUsageLog.tokens_input), 0),
        func.coalesce(func.sum(AIUsageLog.tokens_output), 0),
        func.coalesce(func.sum(AIUsageLog.cost_estimate), 0.0),
        func.coalesce(func.avg(AIUsageLog.latency_ms), 0.0),
    ).where(
        AIUsageLog.created_at >= start_dt_naive,
        AIUsageLog.created_at <= end_dt_naive,
    ).group_by(
        func.date_trunc("day", AIUsageLog.created_at),
    ).order_by(
        func.date_trunc("day", AIUsageLog.created_at),
    )
    daily_query = _apply_company_filter(daily_query, company_id, AIUsageLog)

    result = await db.execute(daily_query)
    daily_rows = result.all()

    daily_usage = []
    for d_row in daily_rows:
        day_dt = d_row[0]
        day_str = day_dt.strftime("%Y-%m-%d") if hasattr(day_dt, "strftime") else str(day_dt)[:10]
        daily_usage.append({
            "date": day_str,
            "requests": int(d_row[1]),
            "tokens_input": int(d_row[2]),
            "tokens_output": int(d_row[3]),
            "cost": round(float(d_row[4]), 4),
            "avg_latency_ms": round(float(d_row[5]), 2),
        })

    # --- 4. Suggestion trigger type distribution ---
    sugg_query = select(
        AISuggestion.trigger_type,
        func.count(AISuggestion.id),
        func.coalesce(func.avg(AISuggestion.tokens_used), 0.0),
    ).group_by(AISuggestion.trigger_type)
    sugg_query = _apply_company_filter(sugg_query, company_id, AISuggestion)
    if branch_id is not None:
        sugg_query = sugg_query.where(AISuggestion.branch_id == branch_id)
    if start_date or end_date:
        sugg_query = sugg_query.where(
            AISuggestion.created_at >= start_dt_naive,
            AISuggestion.created_at <= end_dt_naive,
        )

    result = await db.execute(sugg_query)
    sugg_rows = result.all()

    suggestion_types = []
    for s_row in sugg_rows:
        suggestion_types.append({
            "trigger_type": s_row[0].value if hasattr(s_row[0], "value") else str(s_row[0]),
            "count": int(s_row[1]),
            "avg_tokens": round(float(s_row[2]), 2),
        })

    # --- 5. Conversation metrics ---
    conv_query = select(
        func.count(AIConversation.id),
        func.coalesce(func.sum(AIConversation.total_tokens), 0),
        func.count(func.distinct(AIConversation.user_id)),
    ).where(
        AIConversation.created_at >= start_dt_naive,
        AIConversation.created_at <= end_dt_naive,
    )
    conv_query = _apply_company_filter(conv_query, company_id, AIConversation)
    if branch_id is not None:
        conv_query = conv_query.where(AIConversation.branch_id == branch_id)

    result = await db.execute(conv_query)
    conv_row = result.first()
    total_conversations = int(conv_row[0]) if conv_row else 0
    conv_total_tokens = int(conv_row[1]) if conv_row else 0
    unique_users = int(conv_row[2]) if conv_row else 0

    # --- 6. Message counts by role ---
    msg_query = select(
        AIMessage.role,
        func.count(AIMessage.id),
        func.coalesce(func.sum(AIMessage.tokens), 0),
    ).select_from(AIMessage).join(
        AIConversation, AIMessage.conversation_id == AIConversation.id
    ).where(
        AIConversation.created_at >= start_dt_naive,
        AIConversation.created_at <= end_dt_naive,
    ).group_by(AIMessage.role)
    msg_query = _apply_company_filter(msg_query, company_id, AIConversation)

    result = await db.execute(msg_query)
    msg_rows = result.all()

    message_stats = {}
    for m_row in msg_rows:
        role_val = m_row[0].value if hasattr(m_row[0], "value") else str(m_row[0])
        message_stats[role_val] = {
            "count": int(m_row[1]),
            "tokens": int(m_row[2]),
        }

    return {
        "total_requests": total_requests,
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "total_tokens": total_tokens_input + total_tokens_output,
        "total_cost": round(total_cost, 4),
        "avg_latency_ms": round(avg_latency, 2),
        "max_latency_ms": max_latency,
        "min_latency_ms": min_latency,
        "cost_per_request": round(total_cost / total_requests, 6) if total_requests > 0 else 0.0,
        "tokens_per_request": round((total_tokens_input + total_tokens_output) / total_requests, 2) if total_requests > 0 else 0,
        "model_breakdown": model_breakdown,
        "daily_usage": daily_usage,
        "suggestion_types": suggestion_types,
        "conversations": {
            "total": total_conversations,
            "total_tokens": conv_total_tokens,
            "unique_users": unique_users,
        },
        "message_stats": message_stats,
        "date_range": {"start": str(start_dt), "end": str(end_dt)},
        "_empty": total_requests == 0 and total_conversations == 0,
    }


# ---------------------------------------------------------------------------
# 6. Growth Metrics (MoM)
# ---------------------------------------------------------------------------


async def get_growth_metrics(
    db: AsyncSession,
    company_id: Optional[int],
    branch_id: Optional[int] = None,
    months: int = 6,
) -> Dict[str, Any]:
    """Calculate Month-over-Month growth metrics.

    Tracks:
    - Campaign count MoM
    - Ad spend MoM
    - Conversion MoM
    - Impression/click MoM
    - ERP order MoM
    - AI usage MoM

    Args:
        db: Async SQLAlchemy session.
        company_id: Tenant filter.
        branch_id: Optional branch filter.
        months: Number of months to analyze (default 6).

    Returns:
        Dictionary with monthly trends and growth rates.
    """
    end_dt = datetime.now(timezone.utc).date().replace(day=1)
    start_dt = end_dt
    for _ in range(months):
        # Go back one month
        if start_dt.month == 1:
            start_dt = start_dt.replace(year=start_dt.year - 1, month=12)
        else:
            start_dt = start_dt.replace(month=start_dt.month - 1)

    start_dt_naive = datetime.combine(start_dt, datetime.min.time())
    end_dt_naive = datetime.combine(end_dt, datetime.max.time())

    # --- 1. Monthly campaign counts ---
    campaign_monthly_query = select(
        func.date_trunc("month", AdCampaign.created_at).label("month"),
        func.count(AdCampaign.id),
    ).where(
        AdCampaign.created_at >= start_dt_naive,
        AdCampaign.created_at <= end_dt_naive,
    ).group_by(
        func.date_trunc("month", AdCampaign.created_at),
    ).order_by(
        func.date_trunc("month", AdCampaign.created_at),
    )
    campaign_monthly_query = _apply_company_filter(campaign_monthly_query, company_id, AdCampaign)
    if branch_id is not None:
        campaign_monthly_query = campaign_monthly_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(campaign_monthly_query)
    camp_rows = result.all()
    campaign_monthly = _rows_to_monthly_dict(camp_rows)

    # --- 2. Monthly ad spend ---
    spend_monthly_query = select(
        func.date_trunc("month", AdMetric.created_at).label("month"),
        func.coalesce(func.sum(AdMetric.cost), 0.0),
        func.coalesce(func.sum(AdMetric.conversions), 0),
        func.coalesce(func.sum(AdMetric.impressions), 0),
        func.coalesce(func.sum(AdMetric.clicks), 0),
    ).select_from(AdMetric).join(
        AdCampaign, AdMetric.campaign_id == AdCampaign.id
    ).where(
        AdMetric.created_at >= start_dt_naive,
        AdMetric.created_at <= end_dt_naive,
    ).group_by(
        func.date_trunc("month", AdMetric.created_at),
    ).order_by(
        func.date_trunc("month", AdMetric.created_at),
    )
    spend_monthly_query = _apply_company_filter(spend_monthly_query, company_id, AdCampaign)
    if branch_id is not None:
        spend_monthly_query = spend_monthly_query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(spend_monthly_query)
    spend_rows = result.all()
    spend_monthly = _rows_to_monthly_dict(spend_rows, value_index=1)
    conversion_monthly = _rows_to_monthly_dict(spend_rows, value_index=2)
    impression_monthly = _rows_to_monthly_dict(spend_rows, value_index=3)
    click_monthly = _rows_to_monthly_dict(spend_rows, value_index=4)

    # --- 3. Monthly ERP orders ---
    order_monthly_query = select(
        func.date_trunc("month", ERPSalesOrder.created_at).label("month"),
        func.count(ERPSalesOrder.id),
        func.coalesce(func.sum(ERPSalesOrder.total_amount), 0.0),
    ).where(
        ERPSalesOrder.created_at >= start_dt_naive,
        ERPSalesOrder.created_at <= end_dt_naive,
    ).group_by(
        func.date_trunc("month", ERPSalesOrder.created_at),
    ).order_by(
        func.date_trunc("month", ERPSalesOrder.created_at),
    )
    order_monthly_query = _apply_company_filter(order_monthly_query, company_id, ERPSalesOrder)
    if branch_id is not None:
        order_monthly_query = order_monthly_query.where(ERPSalesOrder.branch_id == branch_id)

    result = await db.execute(order_monthly_query)
    order_rows = result.all()
    order_monthly = _rows_to_monthly_dict(order_rows, value_index=1)
    order_value_monthly = _rows_to_monthly_dict(order_rows, value_index=2)

    # --- 4. Monthly AI requests ---
    ai_monthly_query = select(
        func.date_trunc("month", AIUsageLog.created_at).label("month"),
        func.count(AIUsageLog.id),
        func.coalesce(func.sum(AIUsageLog.tokens_input + AIUsageLog.tokens_output), 0),
        func.coalesce(func.sum(AIUsageLog.cost_estimate), 0.0),
    ).where(
        AIUsageLog.created_at >= start_dt_naive,
        AIUsageLog.created_at <= end_dt_naive,
    ).group_by(
        func.date_trunc("month", AIUsageLog.created_at),
    ).order_by(
        func.date_trunc("month", AIUsageLog.created_at),
    )
    ai_monthly_query = _apply_company_filter(ai_monthly_query, company_id, AIUsageLog)

    result = await db.execute(ai_monthly_query)
    ai_rows = result.all()
    ai_requests_monthly = _rows_to_monthly_dict(ai_rows, value_index=1)
    ai_tokens_monthly = _rows_to_monthly_dict(ai_rows, value_index=2)
    ai_cost_monthly = _rows_to_monthly_dict(ai_rows, value_index=3)

    # --- 5. Build unified monthly report with MoM growth ---
    all_months = sorted(set(
        list(campaign_monthly.keys()) +
        list(spend_monthly.keys()) +
        list(order_monthly.keys()) +
        list(ai_requests_monthly.keys())
    ))

    monthly_report = []
    prev_campaigns = None
    prev_spend = None
    prev_conversions = None
    prev_orders = None

    for month in all_months:
        campaigns = campaign_monthly.get(month, 0)
        spend = float(spend_monthly.get(month, 0))
        conversions = int(conversion_monthly.get(month, 0))
        impressions = int(impression_monthly.get(month, 0))
        clicks = int(click_monthly.get(month, 0))
        orders = int(order_monthly.get(month, 0))
        order_value = float(order_value_monthly.get(month, 0))
        ai_requests = int(ai_requests_monthly.get(month, 0))
        ai_tokens = int(ai_tokens_monthly.get(month, 0))
        ai_cost = float(ai_cost_monthly.get(month, 0))

        # Calculate MoM growth rates
        campaign_growth = _calc_growth(campaigns, prev_campaigns)
        spend_growth = _calc_growth(spend, prev_spend)
        conversion_growth = _calc_growth(conversions, prev_conversions)
        order_growth = _calc_growth(orders, prev_orders)

        monthly_report.append({
            "month": month,
            "campaigns": campaigns,
            "campaign_growth": campaign_growth,
            "ad_spend": round(spend, 2),
            "spend_growth": spend_growth,
            "conversions": conversions,
            "conversion_growth": conversion_growth,
            "impressions": impressions,
            "clicks": clicks,
            "orders": orders,
            "order_growth": order_growth,
            "order_value": round(order_value, 2),
            "ai_requests": ai_requests,
            "ai_tokens": ai_tokens,
            "ai_cost": round(ai_cost, 4),
            "ctr": round((clicks / impressions * 100), 4) if impressions > 0 else 0.0,
        })

        prev_campaigns = campaigns
        prev_spend = spend
        prev_conversions = conversions
        prev_orders = orders

    # --- 6. Summary growth rates (latest month vs previous) ---
    if len(monthly_report) >= 2:
        latest = monthly_report[-1]
        previous = monthly_report[-2]
        summary = {
            "campaign_growth": latest["campaign_growth"],
            "spend_growth": latest["spend_growth"],
            "conversion_growth": latest["conversion_growth"],
            "order_growth": latest["order_growth"],
            "latest_month": latest["month"],
            "previous_month": previous["month"],
        }
    elif len(monthly_report) == 1:
        summary = {
            "campaign_growth": None,
            "spend_growth": None,
            "conversion_growth": None,
            "order_growth": None,
            "latest_month": monthly_report[0]["month"],
            "previous_month": None,
        }
    else:
        summary = {
            "campaign_growth": None,
            "spend_growth": None,
            "conversion_growth": None,
            "order_growth": None,
            "latest_month": None,
            "previous_month": None,
        }

    return {
        "monthly": monthly_report,
        "summary": summary,
        "period_months": months,
        "_empty": len(monthly_report) == 0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rows_to_monthly_dict(
    rows: list,
    value_index: int = 1,
) -> Dict[str, Any]:
    """Convert SQL date_trunc rows to {YYYY-MM: value} dict."""
    result = {}
    for row in rows:
        dt = row[0]
        month_str = dt.strftime("%Y-%m") if hasattr(dt, "strftime") else str(dt)[:7]
        value = row[value_index]
        # Handle Decimal / Numeric types
        if hasattr(value, "__float__"):
            value = float(value)
        result[month_str] = value
    return result


def _calc_growth(current: float, previous: Optional[float]) -> Optional[float]:
    """Calculate percentage growth rate. Returns None if no previous value."""
    if previous is None:
        return None
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 4)
