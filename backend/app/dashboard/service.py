"""KPI Engine Service - Reusable KPI aggregation functions.

All KPI calculations use real SQLAlchemy async aggregation queries.
Redis caching is applied at the router level (5-minute TTL).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.models import AdCampaign, AdMetric, CampaignStatus
from app.ai.models import AIUsageLog
from app.auth.models import User, UserStatus
from app.branches.models import Branch, BranchStatus
from app.companies.models import Company, SubscriptionStatus


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def get_date_range(days: int = 30) -> Tuple[date, date]:
    """Return (start_date, end_date) tuple for the last N days."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def get_month_start() -> date:
    """Return the first day of the current month."""
    today = datetime.now(timezone.utc).date()
    return date(today.year, today.month, 1)


def get_current_month_label() -> str:
    """Return 'YYYY-MM' for the current month."""
    today = datetime.now(timezone.utc).date()
    return today.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Generic KPI aggregations
# ---------------------------------------------------------------------------


async def get_active_branches_count(
    db: AsyncSession, company_id: int
) -> int:
    """Count active branches for a company."""
    result = await db.execute(
        select(func.count(Branch.id))
        .where(Branch.company_id == company_id)
        .where(Branch.is_active.is_(True))
    )
    return result.scalar() or 0


async def get_company_users_count(
    db: AsyncSession, company_id: int
) -> int:
    """Count active users for a company."""
    result = await db.execute(
        select(func.count(User.id))
        .where(User.company_id == company_id)
        .where(User.status == UserStatus.ACTIVE)
    )
    return result.scalar() or 0


async def get_active_campaigns_count(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
) -> int:
    """Count ENABLED campaigns for a company, optionally filtered by branch."""
    query = (
        select(func.count(AdCampaign.id))
        .where(AdCampaign.company_id == company_id)
        .where(AdCampaign.status == CampaignStatus.ENABLED)
    )
    if branch_id is not None:
        query = query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(query)
    return result.scalar() or 0


async def get_total_campaigns_count(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
) -> int:
    """Count total campaigns for a company, optionally filtered by branch."""
    query = select(func.count(AdCampaign.id)).where(
        AdCampaign.company_id == company_id
    )
    if branch_id is not None:
        query = query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(query)
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Ad metric aggregations (this month)
# ---------------------------------------------------------------------------


async def get_ad_metrics_aggregation(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """Aggregate AdMetric data for a company/branch over a period.

    Returns dict with:
    - total_revenue (float)
    - total_orders (int)
    - total_impressions (int)
    - total_clicks (int)
    - total_conversions (int)
    - avg_ctr (float)
    - avg_roas (float)
    """
    start_date, end_date = get_date_range(days)

    query = (
        select(
            func.coalesce(func.sum(AdMetric.cost), 0.0).label("revenue"),
            func.coalesce(func.sum(AdMetric.conversions), 0).label("orders"),
            func.coalesce(func.sum(AdMetric.impressions), 0).label("impressions"),
            func.coalesce(func.sum(AdMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(AdMetric.conversions), 0).label("conversions"),
            func.coalesce(func.avg(AdMetric.ctr), 0.0).label("avg_ctr"),
            func.coalesce(func.avg(AdMetric.roas), 0.0).label("avg_roas"),
        )
        .select_from(AdMetric)
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            AdCampaign.company_id == company_id,
            AdMetric.date >= start_date,
            AdMetric.date <= end_date,
        )
    )
    if branch_id is not None:
        query = query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(query)
    row = result.first()

    if row is None:
        return {
            "total_revenue": 0.0,
            "total_orders": 0,
            "total_impressions": 0,
            "total_clicks": 0,
            "total_conversions": 0,
            "avg_ctr": 0.0,
            "avg_roas": 0.0,
        }

    return {
        "total_revenue": float(row[0] or 0),
        "total_orders": int(row[1] or 0),
        "total_impressions": int(row[2] or 0),
        "total_clicks": int(row[3] or 0),
        "total_conversions": int(row[4] or 0),
        "avg_ctr": float(row[5] or 0),
        "avg_roas": float(row[6] or 0),
    }


# ---------------------------------------------------------------------------
# AI usage aggregations (this month)
# ---------------------------------------------------------------------------


async def get_ai_usage_aggregation(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """Aggregate AIUsageLog data for a company/branch.

    Returns dict with:
    - total_tokens (int)
    - total_cost (float)
    - request_count (int)
    """
    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(
            func.coalesce(func.sum(AIUsageLog.tokens_input + AIUsageLog.tokens_output), 0).label("total_tokens"),
            func.coalesce(func.sum(AIUsageLog.cost_estimate), 0.0).label("total_cost"),
            func.count(AIUsageLog.id).label("request_count"),
        )
        .where(
            AIUsageLog.company_id == company_id,
            AIUsageLog.created_at >= start_dt,
        )
    )
    # AIUsageLog has branch_id column as of v2 schema
    if branch_id is not None:
        query = query.where(AIUsageLog.branch_id == branch_id)

    result = await db.execute(query)
    row = result.first()

    if row is None:
        return {"total_tokens": 0, "total_cost": 0.0, "request_count": 0}

    return {
        "total_tokens": int(row[0] or 0),
        "total_cost": float(row[1] or 0),
        "request_count": int(row[2] or 0),
    }


async def get_ai_suggestions_count(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
    days: int = 30,
) -> int:
    """Count AI suggestions generated for a company/branch.

    Uses the AISuggestion table to count suggestions created within
    the specified period.
    """
    from app.ai.models import AISuggestion

    start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(func.count(AISuggestion.id))
        .where(
            AISuggestion.company_id == company_id,
            AISuggestion.created_at >= start_dt,
        )
    )
    if branch_id is not None:
        query = query.where(AISuggestion.branch_id == branch_id)

    result = await db.execute(query)
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Branch-level KPI aggregation
# ---------------------------------------------------------------------------


async def get_branch_kpi_data(
    db: AsyncSession,
    company_id: int,
    branch_id: int,
    days: int = 30,
) -> Dict[str, Any]:
    """Fetch all KPI data for a single branch.

    Returns a flat dict that maps to BranchDashboardData schema.
    """
    # Branch details
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id, Branch.company_id == company_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise ValueError(f"Branch {branch_id} not found for company {company_id}")

    # Campaign counts
    active_campaigns = await get_active_campaigns_count(
        db, company_id, branch_id=branch_id
    )
    total_campaigns = await get_total_campaigns_count(
        db, company_id, branch_id=branch_id
    )

    # Ad metrics
    ad_metrics = await get_ad_metrics_aggregation(
        db, company_id, branch_id=branch_id, days=days
    )

    # AI usage (branch-level when branch_id is provided)
    ai_usage = await get_ai_usage_aggregation(
        db, company_id, branch_id=branch_id, days=days
    )

    # AI suggestions count for this branch
    ai_suggestions_count = await get_ai_suggestions_count(
        db, company_id, branch_id=branch_id, days=days
    )

    # Users count for this branch
    users_result = await db.execute(
        select(func.count(User.id)).where(
            User.company_id == company_id,
            User.branch_id == branch_id,
            User.status == UserStatus.ACTIVE,
        )
    )
    users_count = users_result.scalar() or 0

    # Target progress
    target_progress_pct = 0.0
    if branch.monthly_revenue_target and branch.monthly_revenue_target > 0:
        target_progress_pct = (
            ad_metrics["total_revenue"] / branch.monthly_revenue_target
        ) * 100.0

    return {
        "branch_id": branch.id,
        "branch_name": branch.name,
        "city": branch.city or "",
        "status": branch.status.value if branch.status else "",
        "employee_count": branch.employee_count or 0,
        "active_campaigns": active_campaigns,
        "total_campaigns": total_campaigns,
        "revenue_this_month": round(ad_metrics["total_revenue"], 2),
        "orders_this_month": ad_metrics["total_orders"],
        "impressions_this_month": ad_metrics["total_impressions"],
        "clicks_this_month": ad_metrics["total_clicks"],
        "conversions_this_month": ad_metrics["total_conversions"],
        "avg_ctr": round(ad_metrics["avg_ctr"], 4),
        "avg_roas": round(ad_metrics["avg_roas"], 4),
        "ai_tokens_this_month": ai_usage["total_tokens"],
        "ai_cost_this_month": round(ai_usage["total_cost"], 4),
        "ai_suggestions_count": ai_suggestions_count,
        "monthly_revenue_target": branch.monthly_revenue_target or 0.0,
        "target_progress_pct": round(min(target_progress_pct, 999.99), 2),
        "users_count": users_count,
    }


# ---------------------------------------------------------------------------
# Company-level executive summary
# ---------------------------------------------------------------------------


async def get_executive_summary_data(
    db: AsyncSession,
    company_id: int,
    days: int = 30,
) -> Dict[str, Any]:
    """Fetch executive-level KPI summary for a company.

    Returns a flat dict that maps to ExecutiveSummaryData schema.
    """
    # Active branches
    active_branches = await get_active_branches_count(db, company_id)

    # Company users
    users_count = await get_company_users_count(db, company_id)

    # Active campaigns
    active_campaigns = await get_active_campaigns_count(db, company_id)

    # Ad metrics aggregation
    ad_metrics = await get_ad_metrics_aggregation(db, company_id, days=days)

    # AI usage
    ai_usage = await get_ai_usage_aggregation(db, company_id, days=days)

    # Subscription status
    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()
    subscription_status = company.subscription_status.value if company else ""

    return {
        "total_orders": ad_metrics["total_orders"],
        "total_revenue": round(ad_metrics["total_revenue"], 2),
        "active_branches": active_branches,
        "ai_tokens_month": ai_usage["total_tokens"],
        "active_campaigns": active_campaigns,
        "avg_ctr": round(ad_metrics["avg_ctr"], 4),
        "total_impressions": ad_metrics["total_impressions"],
        "total_clicks": ad_metrics["total_clicks"],
        "total_conversions": ad_metrics["total_conversions"],
        "ai_cost_estimate": round(ai_usage["total_cost"], 4),
        "users_count": users_count,
        "subscription_status": subscription_status,
    }


# ---------------------------------------------------------------------------
# Branch comparison data
# ---------------------------------------------------------------------------


async def get_branch_comparison_data(
    db: AsyncSession,
    company_id: int,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch KPI data for all branches of a company for comparison.

    Returns list of dicts that map to BranchComparisonItem schema.
    """
    # Get all active branches for this company
    branches_result = await db.execute(
        select(Branch).where(
            Branch.company_id == company_id,
            Branch.is_active.is_(True),
        )
    )
    branches = branches_result.scalars().all()

    items: List[Dict[str, Any]] = []
    for branch in branches:
        ad_metrics = await get_ad_metrics_aggregation(
            db, company_id, branch_id=branch.id, days=days
        )
        ai_usage = await get_ai_usage_aggregation(
            db, company_id, branch_id=branch.id, days=days
        )
        active_campaigns = await get_active_campaigns_count(
            db, company_id, branch_id=branch.id
        )

        items.append(
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "city": branch.city or "",
                "revenue": round(ad_metrics["total_revenue"], 2),
                "orders": ad_metrics["total_orders"],
                "impressions": ad_metrics["total_impressions"],
                "clicks": ad_metrics["total_clicks"],
                "conversions": ad_metrics["total_conversions"],
                "ctr": round(ad_metrics["avg_ctr"], 4),
                "roas": round(ad_metrics["avg_roas"], 4),
                "ai_tokens": ai_usage["total_tokens"],
                "ai_cost": round(ai_usage["total_cost"], 4),
                "active_campaigns": active_campaigns,
                "revenue_rank": 0,  # Will be calculated later
                "orders_rank": 0,
            }
        )

    # Calculate rankings
    sorted_by_revenue = sorted(
        items, key=lambda x: x["revenue"], reverse=True
    )
    for rank, item in enumerate(sorted_by_revenue, start=1):
        item["revenue_rank"] = rank

    sorted_by_orders = sorted(
        items, key=lambda x: x["orders"], reverse=True
    )
    for rank, item in enumerate(sorted_by_orders, start=1):
        item["orders_rank"] = rank

    return items


# ---------------------------------------------------------------------------
# Branch growth analytics (month-over-month)
# ---------------------------------------------------------------------------


async def get_branch_growth_data(
    db: AsyncSession,
    company_id: int,
    months: int = 6,
) -> List[Dict[str, Any]]:
    """Fetch monthly growth data for each branch.

    Returns list of dicts that map to BranchMonthlyGrowth schema.
    Growth rates are calculated vs the previous month.
    """
    now = datetime.now(timezone.utc)

    # Get all active branches
    branches_result = await db.execute(
        select(Branch).where(
            Branch.company_id == company_id,
            Branch.is_active.is_(True),
        )
    )
    branches = branches_result.scalars().all()

    results: List[Dict[str, Any]] = []

    for branch in branches:
        prev_data: Optional[Dict[str, Any]] = None

        for m_offset in range(months - 1, -1, -1):
            month_dt = now - timedelta(days=m_offset * 30)
            month_start = date(month_dt.year, month_dt.month, 1)
            if month_dt.month == 12:
                next_month = date(month_dt.year + 1, 1, 1)
            else:
                next_month = date(month_dt.year, month_dt.month + 1, 1)
            month_label = month_start.strftime("%Y-%m")

            # Aggregate metrics for this branch+month
            agg_result = await db.execute(
                select(
                    func.coalesce(func.sum(AdMetric.cost), 0.0).label("revenue"),
                    func.coalesce(func.sum(AdMetric.conversions), 0).label("orders"),
                    func.coalesce(func.sum(AdMetric.impressions), 0).label("impressions"),
                    func.coalesce(func.sum(AdMetric.clicks), 0).label("clicks"),
                    func.coalesce(func.sum(AdMetric.conversions), 0).label("conversions"),
                )
                .select_from(AdMetric)
                .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
                .where(
                    AdCampaign.company_id == company_id,
                    AdCampaign.branch_id == branch.id,
                    AdMetric.date >= month_start,
                    AdMetric.date < next_month,
                )
            )
            row = agg_result.first()

            revenue = float(row[0] or 0)
            orders_val = int(row[1] or 0)
            impressions = int(row[2] or 0)
            clicks = int(row[3] or 0)
            conversions_val = int(row[4] or 0)

            # AI usage for this month (company-wide)
            ai_month_start = datetime(month_start.year, month_start.month, 1, tzinfo=timezone.utc)
            if month_start.month == 12:
                ai_month_end = datetime(month_start.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                ai_month_end = datetime(month_start.year, month_start.month + 1, 1, tzinfo=timezone.utc)

            ai_result = await db.execute(
                select(
                    func.coalesce(func.sum(AIUsageLog.tokens_input + AIUsageLog.tokens_output), 0).label("tokens"),
                    func.coalesce(func.sum(AIUsageLog.cost_estimate), 0.0).label("cost"),
                )
                .where(
                    AIUsageLog.company_id == company_id,
                    AIUsageLog.created_at >= ai_month_start,
                    AIUsageLog.created_at < ai_month_end,
                )
            )
            ai_row = ai_result.first()
            ai_tokens = int(ai_row[0] or 0)
            ai_cost = float(ai_row[1] or 0)

            # Growth rates
            revenue_growth = None
            orders_growth = None
            impressions_growth = None

            if prev_data is not None:
                if prev_data["revenue"] != 0:
                    revenue_growth = round(
                        ((revenue - prev_data["revenue"]) / prev_data["revenue"]) * 100, 2
                    )
                if prev_data["orders"] != 0:
                    orders_growth = round(
                        ((orders_val - prev_data["orders"]) / prev_data["orders"]) * 100, 2
                    )
                if prev_data["impressions"] != 0:
                    impressions_growth = round(
                        ((impressions - prev_data["impressions"]) / prev_data["impressions"]) * 100, 2
                    )

            entry = {
                "month": month_label,
                "branch_id": branch.id,
                "branch_name": branch.name,
                "revenue": round(revenue, 2),
                "orders": orders_val,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions_val,
                "ai_tokens": ai_tokens,
                "ai_cost": round(ai_cost, 4),
                "revenue_growth_pct": revenue_growth,
                "orders_growth_pct": orders_growth,
                "impressions_growth_pct": impressions_growth,
            }
            results.append(entry)

            prev_data = {
                "revenue": revenue if revenue > 0 else 1,  # avoid div by zero
                "orders": orders_val if orders_val > 0 else 1,
                "impressions": impressions if impressions > 0 else 1,
            }

    return results


# ---------------------------------------------------------------------------
# Threshold alert engine
# ---------------------------------------------------------------------------

# Pre-defined KPI thresholds (company-wide defaults)
DEFAULT_KPI_THRESHOLDS: List[Dict[str, Any]] = [
    {"kpi_name": "revenue", "threshold_type": "below", "threshold_value": 100.0, "severity": "warning"},
    {"kpi_name": "revenue", "threshold_type": "below", "threshold_value": 50.0, "severity": "error"},
    {"kpi_name": "ctr", "threshold_type": "below", "threshold_value": 1.0, "severity": "warning"},
    {"kpi_name": "ctr", "threshold_type": "below", "threshold_value": 0.5, "severity": "error"},
    {"kpi_name": "roas", "threshold_type": "below", "threshold_value": 2.0, "severity": "warning"},
    {"kpi_name": "roas", "threshold_type": "below", "threshold_value": 1.0, "severity": "error"},
    {"kpi_name": "active_campaigns", "threshold_type": "below", "threshold_value": 1, "severity": "info"},
]


async def get_threshold_alerts(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Evaluate KPI thresholds and return triggered alerts.

    Returns list of dicts that map to KPIAlertThreshold schema.
    """
    import uuid

    # Get actual KPI values
    exec_data = await get_executive_summary_data(db, company_id, days=days)
    ad_metrics = await get_ad_metrics_aggregation(db, company_id, days=days)

    kpi_values = {
        "revenue": exec_data["total_revenue"],
        "orders": exec_data["total_orders"],
        "ctr": exec_data["avg_ctr"],
        "roas": ad_metrics["avg_roas"],
        "active_campaigns": exec_data["active_campaigns"],
        "impressions": exec_data["total_impressions"],
        "clicks": exec_data["total_clicks"],
        "ai_tokens": exec_data["ai_tokens_month"],
        "users": exec_data["users_count"],
    }

    alerts: List[Dict[str, Any]] = []

    for threshold in DEFAULT_KPI_THRESHOLDS:
        kpi_name = threshold["kpi_name"]
        current_value = kpi_values.get(kpi_name, 0)
        threshold_type = threshold["threshold_type"]
        threshold_value = threshold["threshold_value"]
        severity = threshold["severity"]

        is_triggered = False
        if threshold_type == "below" and current_value < threshold_value:
            is_triggered = True
        elif threshold_type == "above" and current_value > threshold_value:
            is_triggered = True

        if is_triggered:
            message = (
                f"'{kpi_name}' deyeri ({current_value}) "
                f"{threshold_type} {threshold_value} limitini asti."
            )
            alerts.append(
                {
                    "id": f"alert-{uuid.uuid4().hex[:8]}",
                    "kpi_name": kpi_name,
                    "threshold_type": threshold_type,
                    "threshold_value": threshold_value,
                    "current_value": current_value,
                    "severity": severity,
                    "is_triggered": True,
                    "message": message,
                    "branch_id": branch_id,
                    "branch_name": None,
                }
            )

    return alerts


# ---------------------------------------------------------------------------
# Daily chart data (branch-scoped)
# ---------------------------------------------------------------------------


async def get_daily_chart_data(
    db: AsyncSession,
    company_id: int,
    branch_id: Optional[int] = None,
    days: int = 30,
) -> Dict[str, List[Any]]:
    """Fetch daily aggregated chart data for a company or branch.

    Returns dict with lists: labels, revenue, orders, engagement, roas.
    """
    start_date, end_date = get_date_range(days)

    query = (
        select(
            AdMetric.date,
            func.coalesce(func.sum(AdMetric.cost), 0.0).label("revenue"),
            func.coalesce(func.sum(AdMetric.conversions), 0).label("orders"),
            func.coalesce(func.avg(AdMetric.ctr), 0.0).label("engagement"),
            func.coalesce(func.avg(AdMetric.roas), 0.0).label("roas"),
        )
        .select_from(AdMetric)
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            AdCampaign.company_id == company_id,
            AdMetric.date >= start_date,
            AdMetric.date <= end_date,
        )
        .group_by(AdMetric.date)
        .order_by(AdMetric.date)
    )

    if branch_id is not None:
        query = query.where(AdCampaign.branch_id == branch_id)

    result = await db.execute(query)
    rows = result.all()

    # Build a lookup of existing data by date
    data_by_date: Dict[date, Tuple[float, int, float, float]] = {}
    for row in rows:
        data_by_date[row[0]] = (
            round(float(row[1]), 2),
            int(row[2]),
            round(float(row[3]), 4),
            round(float(row[4]), 4),
        )

    # Fill in all days in the range (including days with no data -> zeros)
    labels: List[str] = []
    revenue: List[float] = []
    orders: List[int] = []
    engagement: List[float] = []
    roas: List[float] = []

    current_date = start_date
    while current_date <= end_date:
        labels.append(current_date.strftime("%d %b"))
        day_data = data_by_date.get(current_date, (0.0, 0, 0.0, 0.0))
        revenue.append(day_data[0])
        orders.append(day_data[1])
        engagement.append(day_data[2])
        roas.append(day_data[3])
        current_date += timedelta(days=1)

    return {
        "labels": labels,
        "revenue": revenue,
        "orders": orders,
        "engagement": engagement,
        "roas": roas,
    }


# ---------------------------------------------------------------------------
# Cache invalidation helpers
# ---------------------------------------------------------------------------

# Cache key patterns (must match router.py patterns)
CACHE_KEY_PATTERNS = {
    "stats": "dashboard:stats:{company_id}",
    "chart": "dashboard:chart:{company_id}:d{days}",
    "alerts": "dashboard:alerts:{company_id}",
    "summary": "dashboard:summary:{company_id}:d{days}",
    "branch": "dashboard:branch:{branch_id}:d{days}",
    "branch_comparison": "dashboard:branch_comparison:{company_id}:d{days}",
    "growth": "dashboard:growth:{company_id}:m{months}",
    "thresholds": "dashboard:thresholds:{company_id}",
}


async def invalidate_dashboard_cache(
    cache,
    company_id: int,
    branch_id: Optional[int] = None,
) -> List[str]:
    """Invalidate all dashboard cache keys for a company/branch.

    Call this after any mutation that affects dashboard KPIs:
    - Campaign create/update/delete
    - AdMetric insert/update
    - AI usage log creation
    - Branch update

    Args:
        cache: Cache instance from get_cache()
        company_id: Company ID to invalidate cache for
        branch_id: Optional specific branch ID to invalidate

    Returns:
        List of invalidated cache key patterns
    """
    invalidated: List[str] = []
    company_key = str(company_id)

    # Invalidate company-wide caches
    keys_to_delete = [
        CACHE_KEY_PATTERNS["stats"].format(company_id=company_key),
        CACHE_KEY_PATTERNS["alerts"].format(company_id=company_key),
        CACHE_KEY_PATTERNS["summary"].format(company_id=company_key, days=30),
        CACHE_KEY_PATTERNS["branch_comparison"].format(company_id=company_key, days=30),
        CACHE_KEY_PATTERNS["growth"].format(company_id=company_key, months=6),
        CACHE_KEY_PATTERNS["thresholds"].format(company_id=company_key),
    ]

    # Chart caches for common day ranges
    for days in [7, 14, 30, 90]:
        keys_to_delete.append(
            CACHE_KEY_PATTERNS["chart"].format(company_id=company_key, days=days)
        )

    # Branch-specific cache
    if branch_id is not None:
        for days in [7, 14, 30, 90]:
            keys_to_delete.append(
                CACHE_KEY_PATTERNS["branch"].format(branch_id=branch_id, days=days)
            )

    for key in keys_to_delete:
        await cache.delete(key)
        invalidated.append(key)

    return invalidated
