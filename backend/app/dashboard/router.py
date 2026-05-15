"""Dashboard API router with aggregated statistics, chart data, and alerts."""

import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserStatus
from app.branches.models import Branch, BranchStatus
from app.companies.models import Company, SubscriptionStatus
from app.dashboard.schemas import (
    DashboardAlertsResponse,
    DashboardAlertItem,
    DashboardChartData,
    DashboardChartResponse,
    DashboardStatsData,
    DashboardStatsResponse,
)
from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: build consistent success/error responses
# ---------------------------------------------------------------------------

def _error_response(message: str, schema_class):
    """Build a standardized error response."""
    return schema_class(success=False, message=message)


# ---------------------------------------------------------------------------
# Endpoint 1: GET /stats — Dashboard KPI statistics
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard KPI statistics",
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    """Return aggregated KPIs for the dashboard.

    Calculates totals from the database:
    - total_companies: active companies count
    - total_branches: active branches count
    - total_users: active users count
    - active_campaigns: hardcoded (no campaigns table yet)
    - revenue_this_month: sum of branches' monthly_revenue_target
    - engagement_rate: hardcoded baseline
    """
    try:
        # Total active companies
        result = await db.execute(
            select(func.count()).select_from(Company).where(Company.is_active.is_(True))
        )
        total_companies = result.scalar() or 0

        # Total active branches
        result = await db.execute(
            select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))
        )
        total_branches = result.scalar() or 0

        # Total active users (status == 'active')
        result = await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.status == UserStatus.ACTIVE)
        )
        total_users = result.scalar() or 0

        # Active campaigns — hardcoded until campaigns table exists
        active_campaigns = 0

        # Revenue this month: sum of monthly_revenue_target across all branches
        result = await db.execute(
            select(func.coalesce(func.sum(Branch.monthly_revenue_target), 0.0))
        )
        revenue_this_month = float(result.scalar() or 0.0)

        # Engagement rate — hardcoded baseline for now
        engagement_rate = 4.2

        data = DashboardStatsData(
            total_companies=total_companies,
            total_branches=total_branches,
            total_users=total_users,
            active_campaigns=active_campaigns,
            revenue_this_month=round(revenue_this_month, 2),
            engagement_rate=engagement_rate,
        )

        return DashboardStatsResponse(success=True, data=data)

    except Exception as exc:
        return _error_response(
            f"Failed to load dashboard stats: {str(exc)}", DashboardStatsResponse
        )


# ---------------------------------------------------------------------------
# Endpoint 2: GET /chart — 30-day trend chart data
# ---------------------------------------------------------------------------

@router.get(
    "/chart",
    response_model=DashboardChartResponse,
    summary="Get 30-day trend chart data",
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard_chart(
    db: AsyncSession = Depends(get_db),
) -> DashboardChartResponse:
    """Return 30-day trend data for dashboard charts.

    Generates realistic daily data based on branch revenue targets.
    - labels: last 30 days formatted as 'DD MMM'
    - revenue: daily revenue around avg target per branch
    - orders: daily order count (30–100)
    - engagement: daily engagement rate % (2.0–6.0)
    - roas: daily ROAS (1.5–4.0)
    """
    try:
        # Compute average daily revenue target across all branches
        result = await db.execute(
            select(func.coalesce(func.sum(Branch.monthly_revenue_target), 0.0))
        )
        total_monthly_target = float(result.scalar() or 0.0)

        # If there are branches, divide by 30 for a daily baseline;
        # otherwise use a sensible default.
        daily_revenue_base = total_monthly_target / 30.0 if total_monthly_target > 0 else 1500.0

        # Seed RNG for reproducibility within the request
        rng = random.Random(42)

        labels: list[str] = []
        revenue: list[float] = []
        orders: list[int] = []
        engagement: list[float] = []
        roas: list[float] = []

        today = datetime.now(timezone.utc)
        for day_offset in range(29, -1, -1):
            day = today - timedelta(days=day_offset)
            labels.append(day.strftime("%d %b"))

            # Revenue: random ±20% around daily baseline
            rev = daily_revenue_base * rng.uniform(0.8, 1.2)
            revenue.append(round(rev, 2))

            # Orders: random 30–100
            orders.append(rng.randint(30, 100))

            # Engagement: random 2.0–6.0
            engagement.append(round(rng.uniform(2.0, 6.0), 2))

            # ROAS: random 1.5–4.0
            roas.append(round(rng.uniform(1.5, 4.0), 2))

        data = DashboardChartData(
            labels=labels,
            revenue=revenue,
            orders=orders,
            engagement=engagement,
            roas=roas,
        )

        return DashboardChartResponse(success=True, data=data)

    except Exception as exc:
        return _error_response(
            f"Failed to load chart data: {str(exc)}", DashboardChartResponse
        )


# ---------------------------------------------------------------------------
# Endpoint 3: GET /alerts — System alerts / warnings
# ---------------------------------------------------------------------------

@router.get(
    "/alerts",
    response_model=DashboardAlertsResponse,
    summary="Get system alerts and warnings",
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard_alerts(
    db: AsyncSession = Depends(get_db),
) -> DashboardAlertsResponse:
    """Return system alerts generated from real DB conditions.

    Alert sources:
    - Companies with subscription_status = 'past_due'  → payment warning
    - Companies on trial created > 10 days ago         → trial ending soon
    - Branches with status = 'pending'                 → activation pending
    """
    try:
        alerts: list[DashboardAlertItem] = []
        now = datetime.now(timezone.utc)

        # --- 1. Past-due subscription warnings ---
        result = await db.execute(
            select(Company).where(
                Company.subscription_status == SubscriptionStatus.PAST_DUE
            )
        )
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
        result = await db.execute(
            select(Company).where(
                Company.subscription_status == SubscriptionStatus.TRIAL,
                Company.created_at <= trial_cutoff,
            )
        )
        trial_companies = result.scalars().all()

        for company in trial_companies:
            days_left = max(0, 14 - (now - company.created_at.replace(tzinfo=timezone.utc)).days)
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
        result = await db.execute(
            select(Branch).where(Branch.status == BranchStatus.PENDING)
        )
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
                    message=f"'{branch.name}' ( {company_name} ) subesi aktivasyon gozlemededir.",
                    created_at=branch.created_at.isoformat()
                    if branch.created_at
                    else now.isoformat(),
                )
            )

        return DashboardAlertsResponse(success=True, data=alerts)

    except Exception as exc:
        return _error_response(
            f"Failed to load alerts: {str(exc)}", DashboardAlertsResponse
        )
