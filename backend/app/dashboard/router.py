"""Dashboard API router with aggregated statistics, chart data, and alerts.

All KPIs are sourced from real database tables using SQLAlchemy async
aggregation queries with Redis caching (5-minute TTL).

Endpoints:
    GET /stats               - Legacy dashboard KPI statistics
    GET /chart               - 30-day trend chart data
    GET /alerts              - System alerts / warnings
    GET /summary             - Executive summary (company-wide KPIs)
    GET /branch/{branch_id}  - Branch-scoped dashboard KPIs
    GET /branch-comparison   - Branch-to-branch KPI comparison
    GET /growth              - Branch growth analytics (MoM)
    GET /alerts/thresholds   - KPI threshold alert widgets
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.models import AdCampaign, AdMetric, CampaignStatus
from app.auth.models import User, UserStatus
from app.branches.models import Branch, BranchStatus
from app.companies.models import Company, SubscriptionStatus
from app.dashboard.schemas import (
    BranchComparisonItem,
    BranchComparisonResponse,
    BranchDashboardData,
    BranchDashboardResponse,
    BranchGrowthResponse,
    BranchMonthlyGrowth,
    DashboardAlertItem,
    DashboardAlertsResponse,
    DashboardChartData,
    DashboardChartResponse,
    DashboardStatsData,
    DashboardStatsResponse,
    ExecutiveSummaryData,
    ExecutiveSummaryResponse,
    KPIAlertThreshold,
    KPIAlertThresholdsResponse,
)
from app.dashboard.service import (
    get_branch_comparison_data,
    get_branch_growth_data,
    get_branch_kpi_data,
    get_daily_chart_data,
    get_executive_summary_data,
    get_threshold_alerts,
    invalidate_dashboard_cache,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.redis_client import get_cache

router = APIRouter()

# ---------------------------------------------------------------------------
# Cache constants
# ---------------------------------------------------------------------------

DASHBOARD_CACHE_TTL = 300  # 5 minutes


def _stats_cache_key(company_id: Optional[int]) -> str:
    return f"dashboard:stats:{company_id or 'global'}"


def _chart_cache_key(company_id: Optional[int], days: int = 30) -> str:
    return f"dashboard:chart:{company_id or 'global'}:d{days}"


def _alerts_cache_key(company_id: Optional[int]) -> str:
    return f"dashboard:alerts:{company_id or 'global'}"


def _summary_cache_key(company_id: Optional[int], days: int = 30) -> str:
    return f"dashboard:summary:{company_id or 'global'}:d{days}"


def _branch_cache_key(branch_id: int, days: int = 30) -> str:
    return f"dashboard:branch:{branch_id}:d{days}"


def _branch_comparison_cache_key(company_id: int, days: int = 30) -> str:
    return f"dashboard:branch_comparison:{company_id}:d{days}"


def _growth_cache_key(company_id: int, months: int = 6) -> str:
    return f"dashboard:growth:{company_id}:m{months}"


def _thresholds_cache_key(company_id: int) -> str:
    return f"dashboard:thresholds:{company_id}"


# ---------------------------------------------------------------------------
# Helper: apply company tenant filter
# ---------------------------------------------------------------------------


def _apply_company_filter(query, company_id: Optional[int], model):
    """Apply company_id tenant isolation filter to a query."""
    if company_id is not None:
        return query.where(model.company_id == company_id)
    return query


# ---------------------------------------------------------------------------
# Helper: build consistent success/error responses
# ---------------------------------------------------------------------------


def _error_response(message: str, schema_class):
    """Build a standardized error response."""
    return schema_class(success=False, message=message)


# ===========================================================================
# Endpoint 1: GET /stats -- Legacy Dashboard KPI statistics
# ===========================================================================


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard KPI statistics",
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardStatsResponse:
    """Return aggregated KPIs for the dashboard from real DB queries.

    Calculates:
    - total_companies: active companies count
    - total_branches: active branches count
    - total_users: active users count
    - active_campaigns: ENABLED AdCampaign count from DB
    - revenue_this_month: sum of AdMetric.cost (last 30 days)
    - engagement_rate: average CTR from AdMetric
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _stats_cache_key(company_id)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            return DashboardStatsResponse(success=True, data=DashboardStatsData(**cached))

        # --- Total active companies ---
        result = await db.execute(
            select(func.count()).select_from(Company).where(Company.is_active.is_(True))
        )
        total_companies = result.scalar() or 0

        # --- Total active branches ---
        result = await db.execute(
            select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))
        )
        total_branches = result.scalar() or 0

        # --- Total active users ---
        result = await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.status == UserStatus.ACTIVE)
        )
        total_users = result.scalar() or 0

        # --- Active campaigns: real DB count ---
        campaign_query = (
            select(func.count())
            .select_from(AdCampaign)
            .where(AdCampaign.status == CampaignStatus.ENABLED)
        )
        campaign_query = _apply_company_filter(campaign_query, company_id, AdCampaign)
        result = await db.execute(campaign_query)
        active_campaigns = result.scalar() or 0

        # --- Revenue this month: sum of AdMetric.cost (last 30 days) ---
        month_ago = datetime.now(timezone.utc).date() - timedelta(days=30)
        revenue_query = (
            select(func.coalesce(func.sum(AdMetric.cost), 0.0))
            .select_from(AdMetric)
            .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
            .where(AdMetric.date >= month_ago)
        )
        revenue_query = _apply_company_filter(revenue_query, company_id, AdCampaign)
        result = await db.execute(revenue_query)
        revenue_this_month = float(result.scalar() or 0.0)

        # --- Engagement rate: average CTR from AdMetric ---
        engagement_query = (
            select(func.coalesce(func.avg(AdMetric.ctr), 0.0))
            .select_from(AdMetric)
            .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
            .where(AdMetric.date >= month_ago)
        )
        engagement_query = _apply_company_filter(engagement_query, company_id, AdCampaign)
        result = await db.execute(engagement_query)
        engagement_rate = float(result.scalar() or 0.0)

        data = DashboardStatsData(
            total_companies=total_companies,
            total_branches=total_branches,
            total_users=total_users,
            active_campaigns=active_campaigns,
            revenue_this_month=round(revenue_this_month, 2),
            engagement_rate=round(engagement_rate, 4),
        )

        # Cache the result
        await cache.set(cache_key, data.model_dump(), ttl=DASHBOARD_CACHE_TTL)

        return DashboardStatsResponse(success=True, data=data)

    except Exception as exc:
        return _error_response(
            f"Failed to load dashboard stats: {str(exc)}", DashboardStatsResponse
        )


# ===========================================================================
# Endpoint 2: GET /chart -- 30-day trend chart data
# ===========================================================================


@router.get(
    "/chart",
    response_model=DashboardChartResponse,
    summary="Get 30-day trend chart data",
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard_chart(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardChartResponse:
    """Return daily trend data from AdMetric aggregation.

    Data is sourced from real AdMetric records grouped by date:
    - revenue: daily sum of AdMetric.cost
    - orders: daily sum of AdMetric.conversions
    - engagement: daily average CTR
    - roas: daily average ROAS
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _chart_cache_key(company_id, days)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            return DashboardChartResponse(
                success=True, data=DashboardChartData(**cached)
            )

        chart_data = await get_daily_chart_data(
            db=db, company_id=company_id, days=days
        )

        data = DashboardChartData(
            labels=chart_data["labels"],
            revenue=chart_data["revenue"],
            orders=chart_data["orders"],
            engagement=chart_data["engagement"],
            roas=chart_data["roas"],
        )

        await cache.set(cache_key, data.model_dump(), ttl=DASHBOARD_CACHE_TTL)
        return DashboardChartResponse(success=True, data=data)

    except Exception as exc:
        return _error_response(
            f"Failed to load chart data: {str(exc)}", DashboardChartResponse
        )


# ===========================================================================
# Endpoint 3: GET /alerts -- System alerts / warnings
# ===========================================================================


@router.get(
    "/alerts",
    response_model=DashboardAlertsResponse,
    summary="Get system alerts and warnings",
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardAlertsResponse:
    """Return system alerts generated from real DB conditions.

    Alert sources:
    - Companies with subscription_status = 'past_due'  -> payment warning
    - Companies on trial created > 10 days ago         -> trial ending soon
    - Branches with status = 'pending'                 -> activation pending
    - Campaigns with zero impressions (last 7 days)    -> campaign performance warning
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _alerts_cache_key(company_id)

        # Check cache (alerts are more dynamic, use shorter TTL or skip)
        # For alerts we keep caching minimal - 2 minutes
        cached = await cache.get(cache_key)
        if cached:
            alerts_data = [DashboardAlertItem(**item) for item in cached]
            return DashboardAlertsResponse(success=True, data=alerts_data)

        alerts: list[DashboardAlertItem] = []
        now = datetime.now(timezone.utc)

        # --- 1. Past-due subscription warnings ---
        past_due_query = select(Company).where(
            Company.subscription_status == SubscriptionStatus.PAST_DUE
        )
        if company_id is not None:
            past_due_query = past_due_query.where(Company.id == company_id)

        result = await db.execute(past_due_query)
        past_due_companies = result.scalars().all()

        for company in past_due_companies:
            alerts.append(
                DashboardAlertItem(
                    id=f"alert-{uuid.uuid4().hex[:8]}",
                    type="error",
                    title="Odenis gecikmesi",
                    message=f"'{company.name}' sirketinin abunelik odenisi gecikib.",
                    created_at=company.updated_at.isoformat()
                    if company.updated_at
                    else now.isoformat(),
                )
            )

        # --- 2. Trial ending soon (created > 10 days ago) ---
        trial_cutoff = now - timedelta(days=10)
        trial_query = select(Company).where(
            Company.subscription_status == SubscriptionStatus.TRIAL,
            Company.created_at <= trial_cutoff,
        )
        if company_id is not None:
            trial_query = trial_query.where(Company.id == company_id)

        result = await db.execute(trial_query)
        trial_companies = result.scalars().all()

        for company in trial_companies:
            company_created = company.created_at
            if company_created.tzinfo is None:
                company_created = company_created.replace(tzinfo=timezone.utc)
            days_left = max(0, 14 - (now - company_created).days)
            alerts.append(
                DashboardAlertItem(
                    id=f"alert-{uuid.uuid4().hex[:8]}",
                    type="warning",
                    title="Trial abune bitmek uzere",
                    message=f"'{company.name}' sirketinin trial abuneliyi {days_left} gun sonra bitecek.",
                    created_at=now.isoformat(),
                )
            )

        # --- 3. Branches pending activation ---
        pending_query = select(Branch).where(Branch.status == BranchStatus.PENDING)
        if company_id is not None:
            pending_query = pending_query.where(Branch.company_id == company_id)

        result = await db.execute(pending_query)
        pending_branches = result.scalars().all()

        # Fetch company names for pending branches
        company_ids = {b.company_id for b in pending_branches}
        company_names: dict[int, str] = {}
        if company_ids:
            result = await db.execute(
                select(Company.id, Company.name).where(Company.id.in_(company_ids))
            )
            company_names = {row[0]: row[1] for row in result.all()}

        for branch in pending_branches:
            company_name = company_names.get(branch.company_id, "Bilinmeyen sirket")
            alerts.append(
                DashboardAlertItem(
                    id=f"alert-{uuid.uuid4().hex[:8]}",
                    type="info",
                    title="Sube aktivasyonu gozlemede",
                    message=f"'{branch.name}' ({company_name}) subesi aktivasyon gozlemededir.",
                    created_at=branch.created_at.isoformat()
                    if branch.created_at
                    else now.isoformat(),
                )
            )

        # --- 4. Campaigns with zero impressions (last 7 days) ---
        week_ago = now.date() - timedelta(days=7)
        zero_imp_query = (
            select(AdCampaign.id, AdCampaign.name, func.coalesce(func.sum(AdMetric.impressions), 0))
            .select_from(AdCampaign)
            .outerjoin(
                AdMetric,
                (AdCampaign.id == AdMetric.campaign_id) & (AdMetric.date >= week_ago),
            )
            .group_by(AdCampaign.id, AdCampaign.name)
            .having(func.coalesce(func.sum(AdMetric.impressions), 0) == 0)
        )
        zero_imp_query = _apply_company_filter(zero_imp_query, company_id, AdCampaign)

        result = await db.execute(zero_imp_query)
        zero_imp_campaigns = result.all()

        for camp in zero_imp_campaigns:
            alerts.append(
                DashboardAlertItem(
                    id=f"alert-{uuid.uuid4().hex[:8]}",
                    type="warning",
                    title="Kampanya performansi dusuk",
                    message=f"'{camp[1]}' kampanyasi son 7 gunde 0 gosterim alib.",
                    created_at=now.isoformat(),
                )
            )

        # Cache alerts with shorter TTL (2 minutes)
        alerts_serializable = [alert.model_dump() for alert in alerts]
        await cache.set(cache_key, alerts_serializable, ttl=120)

        return DashboardAlertsResponse(success=True, data=alerts)

    except Exception as exc:
        return _error_response(
            f"Failed to load alerts: {str(exc)}", DashboardAlertsResponse
        )


# ===========================================================================
# Endpoint 4: GET /summary -- Executive summary (company-wide KPIs)
# ===========================================================================


@router.get(
    "/summary",
    response_model=ExecutiveSummaryResponse,
    summary="Get executive summary dashboard KPIs",
    dependencies=[Depends(get_current_user)],
)
async def get_executive_summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExecutiveSummaryResponse:
    """Return executive-level KPI summary from real DB aggregations.

    Calculates from real tables:
    - total_orders: AdMetric.conversions sum
    - total_revenue: AdMetric.cost sum
    - active_branches: active Branch count
    - ai_tokens_month: AIUsageLog tokens sum
    - active_campaigns: ENABLED campaign count
    - avg_ctr: average click-through rate
    - total_impressions: AdMetric.impressions sum
    - total_clicks: AdMetric.clicks sum
    - total_conversions: AdMetric.conversions sum
    - ai_cost_estimate: AIUsageLog cost_estimate sum
    - users_count: active User count
    - subscription_status: Company.subscription_status
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _summary_cache_key(company_id, days)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            return ExecutiveSummaryResponse(
                success=True, data=ExecutiveSummaryData(**cached)
            )

        if company_id is None:
            return _error_response(
                "Company context required for executive summary",
                ExecutiveSummaryResponse,
            )

        summary_data = await get_executive_summary_data(
            db=db, company_id=company_id, days=days
        )

        data = ExecutiveSummaryData(**summary_data)

        # Cache result
        await cache.set(cache_key, data.model_dump(), ttl=DASHBOARD_CACHE_TTL)

        return ExecutiveSummaryResponse(success=True, data=data)

    except Exception as exc:
        return _error_response(
            f"Failed to load executive summary: {str(exc)}",
            ExecutiveSummaryResponse,
        )


# ===========================================================================
# Endpoint 5: GET /branch/{branch_id} -- Branch-scoped KPIs
# ===========================================================================


@router.get(
    "/branch/{branch_id}",
    response_model=BranchDashboardResponse,
    summary="Get branch-scoped dashboard KPIs",
    dependencies=[Depends(get_current_user)],
)
async def get_branch_dashboard(
    branch_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchDashboardResponse:
    """Return KPI data scoped to a single branch.

    Includes:
    - Branch details (name, city, status, employees)
    - Campaign metrics (active/total campaigns)
    - Revenue & engagement (this month)
    - AI usage (this month)
    - Target progress vs monthly_revenue_target
    - Users assigned to this branch
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _branch_cache_key(branch_id, days)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            return BranchDashboardResponse(
                success=True, data=BranchDashboardData(**cached)
            )

        if company_id is None:
            return _error_response(
                "Company context required for branch dashboard",
                BranchDashboardResponse,
            )

        branch_data = await get_branch_kpi_data(
            db=db, company_id=company_id, branch_id=branch_id, days=days
        )

        data = BranchDashboardData(**branch_data)

        # Cache result
        await cache.set(cache_key, data.model_dump(), ttl=DASHBOARD_CACHE_TTL)

        return BranchDashboardResponse(success=True, data=data)

    except ValueError as exc:
        return _error_response(str(exc), BranchDashboardResponse)
    except Exception as exc:
        return _error_response(
            f"Failed to load branch dashboard: {str(exc)}",
            BranchDashboardResponse,
        )


# ===========================================================================
# Endpoint 6: GET /branch-comparison -- Branch-to-branch comparison
# ===========================================================================


@router.get(
    "/branch-comparison",
    response_model=BranchComparisonResponse,
    summary="Get branch-to-branch KPI comparison",
    dependencies=[Depends(get_current_user)],
)
async def get_branch_comparison(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchComparisonResponse:
    """Return KPI comparison for all branches of the company.

    Each branch includes:
    - revenue, orders, impressions, clicks, conversions
    - ctr, roas, ai_tokens, ai_cost, active_campaigns
    - revenue_rank and orders_rank (calculated across all branches)
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _branch_comparison_cache_key(company_id, days)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            items = [BranchComparisonItem(**item) for item in cached]
            return BranchComparisonResponse(success=True, data=items)

        if company_id is None:
            return _error_response(
                "Company context required for branch comparison",
                BranchComparisonResponse,
            )

        comparison_data = await get_branch_comparison_data(
            db=db, company_id=company_id, days=days
        )

        items = [BranchComparisonItem(**item) for item in comparison_data]

        # Cache result
        serializable = [item.model_dump() for item in items]
        await cache.set(cache_key, serializable, ttl=DASHBOARD_CACHE_TTL)

        return BranchComparisonResponse(success=True, data=items)

    except Exception as exc:
        return _error_response(
            f"Failed to load branch comparison: {str(exc)}",
            BranchComparisonResponse,
        )


# ===========================================================================
# Endpoint 7: GET /growth -- Branch growth analytics (month-over-month)
# ===========================================================================


@router.get(
    "/growth",
    response_model=BranchGrowthResponse,
    summary="Get branch growth analytics (month-over-month)",
    dependencies=[Depends(get_current_user)],
)
async def get_branch_growth(
    months: int = 6,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchGrowthResponse:
    """Return monthly growth data for each branch.

    For each branch, returns month-by-month:
    - revenue, orders, impressions, clicks, conversions
    - ai_tokens, ai_cost
    - revenue_growth_pct, orders_growth_pct, impressions_growth_pct
      (percentage change vs previous month)
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _growth_cache_key(company_id, months)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            items = [BranchMonthlyGrowth(**item) for item in cached]
            return BranchGrowthResponse(success=True, data=items)

        if company_id is None:
            return _error_response(
                "Company context required for growth analytics",
                BranchGrowthResponse,
            )

        growth_data = await get_branch_growth_data(
            db=db, company_id=company_id, months=months
        )

        items = [BranchMonthlyGrowth(**item) for item in growth_data]

        # Cache result
        serializable = [item.model_dump() for item in items]
        await cache.set(cache_key, serializable, ttl=DASHBOARD_CACHE_TTL)

        return BranchGrowthResponse(success=True, data=items)

    except Exception as exc:
        return _error_response(
            f"Failed to load growth analytics: {str(exc)}",
            BranchGrowthResponse,
        )


# ===========================================================================
# Endpoint 8: GET /alerts/thresholds -- KPI threshold alert widgets
# ===========================================================================


@router.get(
    "/alerts/thresholds",
    response_model=KPIAlertThresholdsResponse,
    summary="Get KPI threshold alert widgets",
    dependencies=[Depends(get_current_user)],
)
async def get_kpi_threshold_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KPIAlertThresholdsResponse:
    """Return triggered KPI threshold alerts.

    Evaluates pre-defined thresholds against real KPI values:
    - revenue < 100 (warning), < 50 (error)
    - ctr < 1.0% (warning), < 0.5% (error)
    - roas < 2.0 (warning), < 1.0 (error)
    - active_campaigns < 1 (info)

    Each alert includes current value, threshold, and severity.
    """
    try:
        cache = await get_cache()
        company_id = current_user.company_id
        cache_key = _thresholds_cache_key(company_id)

        # Check cache
        cached = await cache.get(cache_key)
        if cached:
            items = [KPIAlertThreshold(**item) for item in cached]
            return KPIAlertThresholdsResponse(success=True, data=items)

        if company_id is None:
            return _error_response(
                "Company context required for threshold alerts",
                KPIAlertThresholdsResponse,
            )

        threshold_data = await get_threshold_alerts(
            db=db, company_id=company_id
        )

        items = [KPIAlertThreshold(**item) for item in threshold_data]

        # Cache result (2 minutes - alerts are dynamic)
        serializable = [item.model_dump() for item in items]
        await cache.set(cache_key, serializable, ttl=120)

        return KPIAlertThresholdsResponse(success=True, data=items)

    except Exception as exc:
        return _error_response(
            f"Failed to load threshold alerts: {str(exc)}",
            KPIAlertThresholdsResponse,
        )
