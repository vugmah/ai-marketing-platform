"""Billing API router.

Provides endpoints for:
- Subscription plan management
- Company subscription lifecycle
- Usage tracking and analytics
- Quota enforcement queries
- Invoice management
- Feature flag toggling
- Billing events and statistics

Router is mounted at /api/v2/billing via main.py registration.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.constants import (
    ApprovalStatus,
    BillingCycle,
    BillingEventType,
    FeatureName,
    InvoiceStatus,
    RequestType,
    ResourceType,
    SubscriptionStatus,
)
from app.billing.schemas import (
    AIUsageTrackRequest,
    ApprovalActionRequest,
    ApprovalEditRequest,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
    ApprovalRequestSubmit,
    ApprovalStatsResponse,
    BillingEventListResponse,
    BillingEventResponse,
    BillingStatsResponse,
    CompanyBillingSummary,
    FeatureCheckResponse,
    FeatureFlagResponse,
    FeatureFlagToggleRequest,
    InvoiceListResponse,
    InvoiceResponse,
    PlanListResponse,
    PlanResponse,
    QuotaCheckResponse,
    QuotaResponse,
    ResourceBreakdownResponse,
    StripeStatusResponse,
    SubscribeRequest,
    SubscriptionCancelRequest,
    SubscriptionResponse,
    SubscriptionUpdate,
    UsageRecordResponse,
    UsageSummaryResponse,
    UsageTimeseriesResponse,
    UsageTrackRequest,
)
from app.billing.service import (
    ApprovalService,
    BillingEventService,
    FeatureFlagService,
    InvoiceService,
    PlanService,
    QuotaEnforcementService,
    StripeReadyService,
    SubscriptionService,
    UsageTrackingService,
)
from app.config import settings
from app.dependencies import get_current_user, get_db, require_role
from app.exceptions import NotFoundError, ValidationError

router = APIRouter()


# ============================================================================
# Stripe availability guard
# ============================================================================


def require_stripe():
    """Dependency that returns 503 if Stripe is not configured.

    Use this on any endpoint that requires actual Stripe payment processing.
    Tracking-only endpoints should NOT use this guard.
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Stripe is not configured. Billing is running in tracking-only mode. "
                "Set STRIPE_SECRET_KEY to enable payment processing."
            ),
        )


# ============================================================================
# Plan endpoints
# ============================================================================


@router.get(
    "/plans",
    response_model=PlanListResponse,
    status_code=status.HTTP_200_OK,
    summary="List available subscription plans",
)
async def list_plans(
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = Query(default=False, description="Include inactive plans"),
) -> PlanListResponse:
    """List all available subscription plans.

    Returns plans ordered by sort_order. Only active plans are shown by default.
    """
    plans = await PlanService.list_plans(db, include_inactive=include_inactive)
    plan_responses = [PlanResponse.model_validate(p) for p in plans]
    return PlanListResponse(
        items=plan_responses,
        total=len(plan_responses),
    )


@router.get(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get plan details",
)
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Get detailed information about a specific subscription plan."""
    plan = await PlanService.get_plan(db, plan_id)
    return PlanResponse.model_validate(plan)


# ============================================================================
# Subscription endpoints
# ============================================================================


@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to a plan",
)
async def subscribe(
    data: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> SubscriptionResponse:
    """Subscribe the current user's company to a plan.

    Starts with a trial period. If an active subscription already exists,
    it will be upgraded/downgraded to the new plan.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)

    # Check for existing subscription
    existing = await SubscriptionService.get_subscription(db, company_id)
    if existing:
        # Change plan instead of creating new
        updated = await SubscriptionService.change_plan(
            db,
            company_id=company_id,
            new_plan_id=data.plan_id,
            billing_cycle=data.billing_cycle,
        )
        return await SubscriptionService.to_response(db, updated)

    from app.billing.schemas import SubscriptionCreate

    sub_data = SubscriptionCreate(
        company_id=company_id,
        plan_id=data.plan_id,
        billing_cycle=data.billing_cycle,
        auto_renew=data.auto_renew,
        trial_days=14,
    )
    subscription = await SubscriptionService.create_subscription(db, sub_data)
    return await SubscriptionService.to_response(db, subscription)


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current subscription",
)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> SubscriptionResponse:
    """Get the current subscription for the user's company."""
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    subscription = await SubscriptionService.get_subscription(db, company_id)
    if subscription is None:
        raise NotFoundError(detail="No active subscription found")

    # Check trial status
    await SubscriptionService.check_trial_status(db, company_id)

    return await SubscriptionService.to_response(db, subscription)


@router.put(
    "/subscription",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Change subscription plan",
)
async def change_subscription(
    data: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> SubscriptionResponse:
    """Change the current subscription plan (upgrade or downgrade)."""
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    updated = await SubscriptionService.change_plan(
        db,
        company_id=company_id,
        new_plan_id=data.plan_id,
        billing_cycle=data.billing_cycle,
    )
    return await SubscriptionService.to_response(db, updated)


@router.post(
    "/subscription/cancel",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel subscription",
)
async def cancel_subscription(
    data: SubscriptionCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> SubscriptionResponse:
    """Cancel the current subscription.

    By default, cancellation takes effect at the end of the current period.
    Set immediate=True to cancel immediately.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    subscription = await SubscriptionService.cancel_subscription(
        db,
        company_id=company_id,
        data=data,
    )
    return await SubscriptionService.to_response(db, subscription)


@router.post(
    "/subscription/renew",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Renew subscription",
)
async def renew_subscription(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> SubscriptionResponse:
    """Manually renew the subscription for a new period.

    Also resets usage quotas for the new period.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    subscription = await SubscriptionService.renew_subscription(db, company_id)
    return await SubscriptionService.to_response(db, subscription)


# ============================================================================
# Usage endpoints
# ============================================================================


@router.get(
    "/usage",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get usage analytics",
)
async def get_usage(
    resource_type: Optional[ResourceType] = Query(
        default=None, description="Filter by resource type"
    ),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> UsageSummaryResponse:
    """Get usage analytics for the current billing period.

    Returns a breakdown of usage by resource type with costs.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    subscription = await SubscriptionService.get_subscription(db, company_id)

    period_start = (
        subscription.current_period_start
        if subscription
        else datetime.utcnow() - timedelta(days=30)
    )
    period_end = datetime.utcnow()

    breakdown = await UsageTrackingService.get_usage_summary(
        db,
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
    )

    total_cost = sum(
        Decimal(str(v.get("total_cost", 0)))
        for v in breakdown.values()
    )

    return UsageSummaryResponse(
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        breakdown=breakdown,
        total_cost=total_cost,
    )


@router.post(
    "/usage/track",
    response_model=UsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track resource usage",
)
async def track_usage(
    data: UsageTrackRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> UsageRecordResponse:
    """Track resource usage (internal endpoint).

    Records a usage event and updates the corresponding quota.
    This endpoint is called internally when resources are consumed.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)

    # Record the usage
    record = await UsageTrackingService.record_usage_from_track(
        db,
        company_id=company_id,
        data=data,
    )

    # Update quota
    try:
        await QuotaEnforcementService.increment_usage(
            db,
            company_id=company_id,
            resource_type=data.resource_type,
            quantity=data.quantity,
        )
    except ValidationError:
        # Quota exceeded - record is still logged
        pass

    return UsageRecordResponse.model_validate(record)


# ============================================================================
# Quota endpoints
# ============================================================================


@router.get(
    "/quotas",
    response_model=List[QuotaResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current quotas",
)
async def get_quotas(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> List[QuotaResponse]:
    """Get all resource quotas and current usage for the company.

    Returns quota status including usage percentage and remaining amount.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    return await QuotaEnforcementService.get_quota_status(db, company_id)


@router.get(
    "/quotas/check",
    response_model=QuotaCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check if action is allowed",
)
async def check_quota(
    resource_type: ResourceType,
    quantity: int = Query(default=1, ge=1, description="Requested quantity"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> QuotaCheckResponse:
    """Check if a specific action is allowed within quota limits.

    Returns whether the action is allowed and quota details.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    return await QuotaEnforcementService.check_quota(
        db,
        company_id=company_id,
        resource_type=resource_type,
        requested_quantity=quantity,
    )


# ============================================================================
# Invoice endpoints
# ============================================================================


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List invoice history",
)
async def list_invoices(
    status: Optional[InvoiceStatus] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> InvoiceListResponse:
    """List all invoices for the company.

    Supports filtering by status and pagination.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    invoices = await InvoiceService.list_invoices(
        db,
        company_id=company_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    invoice_responses = [InvoiceResponse.model_validate(inv) for inv in invoices]
    total_unpaid = await InvoiceService.get_total_unpaid(db, company_id)

    return InvoiceListResponse(
        items=invoice_responses,
        total=len(invoice_responses),
        total_unpaid=total_unpaid,
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get invoice details",
)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> InvoiceResponse:
    """Get detailed information about a specific invoice."""
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    invoice = await InvoiceService.get_invoice(db, invoice_id)

    # Security check: ensure invoice belongs to user's company
    if invoice.company_id != int(current_user.company_id):
        raise ValidationError(detail="Invoice does not belong to your company")

    return InvoiceResponse.model_validate(invoice)


# ============================================================================
# Feature flag endpoints
# ============================================================================


@router.get(
    "/features",
    response_model=Dict[str, FeatureCheckResponse],
    status_code=status.HTTP_200_OK,
    summary="Get enabled features",
)
async def get_features(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, FeatureCheckResponse]:
    """Get all feature flags and their enabled status for the company.

    Returns a dictionary of feature names to their check results.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    flags = await FeatureFlagService.list_features(db, company_id)

    # Also check all possible features
    all_features = list(FeatureName)
    response: Dict[str, FeatureCheckResponse] = {}

    for feature in all_features:
        flag = next(
            (f for f in flags if f.feature_name == feature),
            None,
        )
        is_enabled = await FeatureFlagService.check_feature(db, company_id, feature)
        source = "plan" if flag is None else "manual"
        expires_at = flag.expires_at if flag else None
        is_expired = bool(expires_at and datetime.utcnow() > expires_at)

        response[feature.value] = FeatureCheckResponse(
            feature_name=feature,
            enabled=is_enabled and not is_expired,
            source=source,
            expires_at=expires_at,
            is_expired=is_expired,
        )

    return response


@router.post(
    "/features/{feature_name}/toggle",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle feature flag (admin)",
)
async def toggle_feature(
    feature_name: FeatureName,
    data: FeatureFlagToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["super_admin", "company_admin"])),
) -> FeatureFlagResponse:
    """Toggle a feature flag for the company.

    Requires super_admin or company_admin role.
    Can optionally set an expiration date.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    flag = await FeatureFlagService.toggle_feature(
        db,
        company_id=company_id,
        feature_name=feature_name,
        enabled=data.enabled,
        enabled_by=current_user.id,
        reason=data.reason,
        expires_at=data.expires_at,
    )
    return FeatureFlagResponse.model_validate(flag)


# ============================================================================
# Billing event endpoints
# ============================================================================


@router.get(
    "/events",
    response_model=BillingEventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List billing events",
)
async def list_events(
    event_type: Optional[BillingEventType] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> BillingEventListResponse:
    """List billing events for the company.

    Supports filtering by event type and pagination.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    events = await BillingEventService.list_events(
        db,
        company_id=company_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    event_responses = [BillingEventResponse.model_validate(e) for e in events]

    return BillingEventListResponse(
        items=event_responses,
        total=len(event_responses),
    )


# ============================================================================
# Statistics endpoints
# ============================================================================


@router.get(
    "/stats",
    response_model=BillingStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get billing statistics (admin)",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["super_admin"])),
) -> BillingStatsResponse:
    """Get platform-wide billing statistics.

    Returns aggregated data including MRR, subscription counts,
    and revenue breakdown by plan. Requires super_admin role.
    """
    from sqlalchemy import func, select

    from app.billing.models import CompanySubscription, Invoice, SubscriptionPlan

    # Subscription counts by status
    result = await db.execute(
        select(
            CompanySubscription.status,
            func.count().label("count"),
        ).group_by(CompanySubscription.status)
    )
    status_counts = {row.status: row.count for row in result.all()}

    active_subs = status_counts.get(SubscriptionStatus.ACTIVE, 0)
    trial_subs = status_counts.get(SubscriptionStatus.TRIAL, 0)
    past_due_subs = status_counts.get(SubscriptionStatus.PAST_DUE, 0)
    cancelled_subs = status_counts.get(SubscriptionStatus.CANCELLED, 0)
    total_companies = active_subs + trial_subs + past_due_subs

    # MRR calculation
    result = await db.execute(
        select(
            SubscriptionPlan.price_monthly,
            func.count().label("count"),
        )
        .join(
            CompanySubscription,
            SubscriptionPlan.id == CompanySubscription.plan_id,
        )
        .where(
            CompanySubscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIAL,
            ]),
        )
        .group_by(SubscriptionPlan.price_monthly)
    )
    total_mrr = sum(
        (row.price_monthly * row.count)
        for row in result.all()
    )

    # Revenue by plan
    result = await db.execute(
        select(
            SubscriptionPlan.name,
            SubscriptionPlan.price_monthly,
            func.count().label("count"),
        )
        .join(
            CompanySubscription,
            SubscriptionPlan.id == CompanySubscription.plan_id,
        )
        .where(
            CompanySubscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIAL,
            ]),
        )
        .group_by(SubscriptionPlan.name, SubscriptionPlan.price_monthly)
    )
    revenue_by_plan = {
        row.name: (row.price_monthly * row.count)
        for row in result.all()
    }

    # Total outstanding
    result = await db.execute(
        select(func.sum(Invoice.total)).where(
            Invoice.status == InvoiceStatus.OPEN,
        )
    )
    total_outstanding = result.scalar() or 0

    # Recent events count (last 30 days)
    from datetime import timedelta

    from app.billing.models import BillingEvent

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(func.count()).where(BillingEvent.created_at >= thirty_days_ago)
    )
    recent_events = result.scalar() or 0

    return BillingStatsResponse(
        total_companies=total_companies,
        active_subscriptions=active_subs,
        trial_subscriptions=trial_subs,
        past_due_subscriptions=past_due_subs,
        cancelled_subscriptions=cancelled_subs,
        total_mrr=total_mrr,
        total_outstanding=total_outstanding,
        revenue_by_plan=revenue_by_plan,
        recent_events=recent_events,
    )


@router.get(
    "/summary",
    response_model=CompanyBillingSummary,
    status_code=status.HTTP_200_OK,
    summary="Get company billing summary",
)
async def get_company_summary(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> CompanyBillingSummary:
    """Get a comprehensive billing summary for the current company.

    Includes subscription status, quotas, features, and outstanding invoices.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    stats = await BillingEventService.get_company_stats(db, company_id)

    # Get features
    features_dict: Dict[str, bool] = {}
    for feature_name in FeatureName:
        features_dict[feature_name.value] = await FeatureFlagService.check_feature(
            db, company_id, feature_name
        )

    # Get quotas
    quotas_list = await QuotaEnforcementService.get_quota_status(db, company_id)
    quotas_dict = {}
    for q in quotas_list:
        quotas_dict[q.resource_type.value] = {
            "limit": q.limit_amount,
            "used": q.current_usage,
            "remaining": q.remaining,
            "percentage": q.usage_percentage,
            "is_unlimited": q.is_unlimited,
        }

    # Get unpaid total
    total_unpaid = await InvoiceService.get_total_unpaid(db, company_id)

    return CompanyBillingSummary(
        company_id=company_id,
        current_plan=stats.get("current_plan", "None"),
        subscription_status=stats.get(
            "subscription_status", SubscriptionStatus.EXPIRED
        ),
        billing_cycle=stats.get("billing_cycle", BillingCycle.MONTHLY),
        current_period_end=stats.get("current_period_end", datetime.utcnow()),
        is_trial=stats.get("is_trial", False),
        days_remaining=stats.get("days_remaining", 0),
        features=features_dict,
        quotas=quotas_dict,
        total_unpaid=total_unpaid,
    )


# ============================================================================
# Stripe-ready preview endpoints
# ============================================================================


@router.get(
    "/stripe/status",
    response_model=StripeStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Stripe configuration status",
)
async def get_stripe_status() -> StripeStatusResponse:
    """Get the current Stripe/payment processing configuration status.

    Returns whether Stripe is enabled and which billing mode is active.
    This endpoint is always available (no auth required) for UI configuration.
    """
    return StripeStatusResponse(
        enabled=settings.STRIPE_ENABLED,
        mode="payment" if settings.STRIPE_ENABLED else "tracking-only",
        publishable_key_present=bool(
            settings.STRIPE_PUBLISHABLE_KEY
            and settings.STRIPE_PUBLISHABLE_KEY.startswith("pk_")
        ),
    )


@router.get(
    "/invoice/preview",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Preview next invoice",
    dependencies=[Depends(require_stripe)],
)
async def preview_invoice(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """Preview the next invoice for the current subscription.

    Returns the invoice structure without creating an actual invoice.
    Requires Stripe to be configured (503 in tracking-only mode).
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    return await StripeReadyService.preview_invoice(db, company_id)


@router.get(
    "/stripe/customer",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get Stripe-compatible customer object",
    dependencies=[Depends(require_stripe)],
)
async def get_stripe_customer(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a Stripe-compatible customer object for the company.

    Returns the structure that would be used when creating a Stripe customer.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    # Fetch company data
    from sqlalchemy import select

    from app.companies.models import Company

    result = await db.execute(
        select(Company).where(Company.id == int(current_user.company_id))
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise NotFoundError(detail="Company not found")

    return StripeReadyService.create_stripe_customer_object({
        "id": company.id,
        "name": company.name,
        "email": company.email,
        "phone": company.phone,
        "slug": company.slug,
    })


@router.get(
    "/stripe/subscription",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get Stripe-compatible subscription object",
    dependencies=[Depends(require_stripe)],
)
async def get_stripe_subscription(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a Stripe-compatible subscription object.

    Returns the structure that matches Stripe's subscription API format.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    subscription = await SubscriptionService.get_subscription(db, company_id)
    if subscription is None:
        raise NotFoundError(detail="No active subscription found")

    plan = await PlanService.get_plan(db, subscription.plan_id)
    return StripeReadyService.create_stripe_subscription_object(
        subscription, plan
    )


# ============================================================================
# Usage analytics endpoints (dashboard charts)
# ============================================================================


@router.get(
    "/usage/timeseries",
    response_model=UsageTimeseriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get daily usage timeseries for charts",
)
async def get_usage_timeseries(
    resource_type: Optional[ResourceType] = Query(
        default=None, description="Filter by resource type"
    ),
    days: int = Query(default=30, ge=1, le=365, description="Days to look back"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> UsageTimeseriesResponse:
    """Get daily usage timeseries data for dashboard line/bar charts.

    Returns aggregated daily usage for the last N days, broken down by
    resource type. Suitable for rendering trend charts on the billing dashboard.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    data = await UsageTrackingService.get_usage_timeseries(
        db,
        company_id=company_id,
        resource_type=resource_type,
        days=days,
    )

    return UsageTimeseriesResponse(
        company_id=company_id,
        days=days,
        data=data,
    )


@router.get(
    "/usage/breakdown",
    response_model=ResourceBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Get resource usage breakdown for pie charts",
)
async def get_resource_breakdown(
    days: int = Query(default=30, ge=1, le=365, description="Days to look back"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ResourceBreakdownResponse:
    """Get usage breakdown by resource type for pie/donut charts.

    Returns aggregated usage stats per resource type over the specified period.
    Includes cost, quantity, and request counts for each resource.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    breakdown = await UsageTrackingService.get_resource_breakdown(
        db,
        company_id=company_id,
        days=days,
    )

    totals = breakdown.pop("_totals", {})

    return ResourceBreakdownResponse(
        company_id=company_id,
        breakdown=breakdown,
        totals=totals,
    )


@router.get(
    "/usage/top-days",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get top usage days for a resource",
)
async def get_top_usage_days(
    resource_type: ResourceType = Query(..., description="Resource type to analyze"),
    limit: int = Query(default=10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get top usage days for a specific resource type.

    Useful for identifying peak usage days on the dashboard.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    top_days = await UsageTrackingService.get_top_usage_days(
        db,
        company_id=company_id,
        resource_type=resource_type,
        limit=limit,
    )

    return {
        "company_id": company_id,
        "resource_type": resource_type.value,
        "top_days": top_days,
    }


# ============================================================================
# AI Usage tracking endpoint
# ============================================================================


@router.post(
    "/usage/track-ai",
    response_model=UsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track AI request usage (internal)",
)
async def track_ai_usage(
    data: AIUsageTrackRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> UsageRecordResponse:
    """Track an AI request and increment AI usage quota.

    This endpoint should be called internally after every AI completion.
    It records the usage and enforces the AI request quota limit.

    Raises 422 if the AI request quota has been exceeded.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)

    # Check quota first
    quota_check = await QuotaEnforcementService.check_quota(
        db,
        company_id=company_id,
        resource_type=ResourceType.AI_REQUEST,
        requested_quantity=1,
    )

    if not quota_check.allowed:
        raise ValidationError(
            detail=f"AI request quota exceeded: {quota_check.current_usage}/{quota_check.limit}"
        )

    record = await UsageTrackingService.track_ai_request(
        db,
        company_id=company_id,
        model=data.model,
        tokens_used=data.tokens_used,
    )

    return UsageRecordResponse.model_validate(record)


# ============================================================================
# AI Approval Center Endpoints
# ============================================================================


@router.get(
    "/approvals/pending",
    response_model=ApprovalRequestListResponse,
    status_code=status.HTTP_200_OK,
    summary="List pending approval requests",
)
async def list_pending_approvals(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ApprovalRequestListResponse:
    """List pending approval requests for the company.

    Returns all approval requests with status 'pending' that require
    human review before being applied.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    items = await ApprovalService.list_pending(
        db, company_id=company_id, limit=limit, offset=offset
    )

    # Also get counts for all statuses
    stats = await ApprovalService.get_stats(db, company_id)

    return ApprovalRequestListResponse(
        items=[ApprovalService.to_response(i) for i in items],
        total=stats["total"],
        pending_count=stats["pending"],
        approved_count=stats["approved"],
        rejected_count=stats["rejected"],
    )


@router.get(
    "/approvals",
    response_model=ApprovalRequestListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all approval requests",
)
async def list_all_approvals(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ApprovalRequestListResponse:
    """List all approval requests for the company.

    Supports filtering by status (pending, approved, rejected, edited).
    Returns paginated results with status counts.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    items = await ApprovalService.list_all(
        db, company_id=company_id, status=status, limit=limit, offset=offset
    )

    # Get status counts
    stats = await ApprovalService.get_stats(db, company_id)

    return ApprovalRequestListResponse(
        items=[ApprovalService.to_response(i) for i in items],
        total=stats["total"],
        pending_count=stats["pending"],
        approved_count=stats["approved"],
        rejected_count=stats["rejected"],
    )


@router.post(
    "/approvals",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new approval request",
)
async def submit_approval_request(
    data: ApprovalRequestSubmit,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ApprovalRequestResponse:
    """Submit a new approval request for review.

    Creates a pending approval request that requires review by an admin
    or authorized user before being applied.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)

    from app.billing.schemas import ApprovalRequestCreate

    create_data = ApprovalRequestCreate(
        company_id=company_id,
        request_type=data.request_type,
        request_data=data.request_data,
        requested_by=current_user.id,
        reason=data.reason,
    )

    req = await ApprovalService.create_request(db, create_data)
    return ApprovalService.to_response(req)


@router.get(
    "/approvals/{request_id}",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get approval request details",
)
async def get_approval_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ApprovalRequestResponse:
    """Get details of a specific approval request."""
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    req = await ApprovalService.get_request(db, request_id)

    # Security check
    if req.company_id != int(current_user.company_id):
        raise ValidationError(
            detail="Approval request does not belong to your company"
        )

    return ApprovalService.to_response(req)


@router.post(
    "/approvals/{request_id}/approve",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a pending request",
)
async def approve_request(
    request_id: int,
    data: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["company_admin", "branch_manager", "super_admin"])),
) -> ApprovalRequestResponse:
    """Approve a pending approval request.

    Requires company_admin, branch_manager, or super_admin role.
    The request status must be 'pending' to be approved.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    req = await ApprovalService.get_request(db, request_id)

    # Security check
    if req.company_id != int(current_user.company_id):
        raise ValidationError(
            detail="Approval request does not belong to your company"
        )

    result = await ApprovalService.approve(
        db,
        request_id=request_id,
        approved_by=current_user.id,
        reason=data.reason,
    )
    return ApprovalService.to_response(result)


@router.post(
    "/approvals/{request_id}/reject",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject a pending request",
)
async def reject_request(
    request_id: int,
    data: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["company_admin", "branch_manager", "super_admin"])),
) -> ApprovalRequestResponse:
    """Reject a pending approval request.

    Requires company_admin, branch_manager, or super_admin role.
    The request status must be 'pending' to be rejected.
    A rejection reason is recommended for audit trail.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    req = await ApprovalService.get_request(db, request_id)

    # Security check
    if req.company_id != int(current_user.company_id):
        raise ValidationError(
            detail="Approval request does not belong to your company"
        )

    result = await ApprovalService.reject(
        db,
        request_id=request_id,
        approved_by=current_user.id,
        reason=data.reason,
    )
    return ApprovalService.to_response(result)


@router.post(
    "/approvals/{request_id}/edit",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit and approve a pending request",
)
async def edit_and_approve_request(
    request_id: int,
    data: ApprovalEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["company_admin", "branch_manager", "super_admin"])),
) -> ApprovalRequestResponse:
    """Edit a pending approval request and approve it.

    Requires company_admin, branch_manager, or super_admin role.
    The request status must be 'pending'. The edited_data replaces
    the original request_data in the approval result.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    req = await ApprovalService.get_request(db, request_id)

    # Security check
    if req.company_id != int(current_user.company_id):
        raise ValidationError(
            detail="Approval request does not belong to your company"
        )

    result = await ApprovalService.edit_and_approve(
        db,
        request_id=request_id,
        approved_by=current_user.id,
        edited_data=data.edited_data,
        reason=data.reason,
    )
    return ApprovalService.to_response(result)


@router.get(
    "/approvals/stats/summary",
    response_model=ApprovalStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get approval statistics",
)
async def get_approval_stats(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ApprovalStatsResponse:
    """Get approval statistics for the company.

    Returns counts by status and breakdown by request type.
    """
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")

    company_id = int(current_user.company_id)
    stats = await ApprovalService.get_stats(db, company_id)

    return ApprovalStatsResponse(
        total=stats["total"],
        pending=stats["pending"],
        approved=stats["approved"],
        rejected=stats["rejected"],
        edited=stats["edited"],
        by_type=stats["by_type"],
    )

