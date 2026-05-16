"""Billing services for subscription management, usage tracking, and invoicing.

Provides comprehensive business logic for:
- Plan management (CRUD, default plans)
- Subscription lifecycle (create, upgrade, downgrade, cancel, renew, trial)
- Usage tracking and recording
- Quota enforcement and limit checking
- Invoice generation and management
- Feature flag management
- Billing event logging
- Stripe-ready structure preparation
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.billing.constants import (
    DEFAULT_COST_PER_UNIT,
    GRACE_PERIOD_DAYS,
    INVOICE_DUE_DAYS,
    INVOICE_NUMBER_PADDING,
    INVOICE_PREFIX,
    PAST_DUE_GRACE_PERIOD_DAYS,
    PLAN_DEFINITIONS,
    QUOTA_CRITICAL_THRESHOLD,
    QUOTA_EXCEEDED_THRESHOLD,
    QUOTA_WARNING_THRESHOLD,
    RESOURCE_UNITS,
    STRIPE_TAX_RATE_PERCENT,
    TRIAL_DURATION_DAYS,
    BillingCycle,
    BillingEventType,
    FeatureName,
    InvoiceStatus,
    PlanTier,
    QuotaPeriod,
    ResourceType,
    SubscriptionStatus,
)
from app.billing.models import (
    ApprovalRequest,
    BillingEvent,
    CompanySubscription,
    FeatureFlag,
    Invoice,
    SubscriptionPlan,
    UsageQuota,
    UsageRecord,
)
from app.billing.schemas import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    BillingEventCreate,
    FeatureFlagCreate,
    InvoiceCreate,
    QuotaCheckResponse,
    QuotaCreate,
    QuotaResponse,
    SubscriptionCancelRequest,
    SubscriptionCreate,
    SubscriptionResponse,
    UsageRecordCreate,
    UsageTrackRequest,
)
from app.config import settings
from app.exceptions import AlreadyExistsError, NotFoundError, ValidationError


# ============================================================================
# Helper functions
# ============================================================================


def _generate_invoice_number() -> str:
    """Generate a unique invoice number."""
    unique = uuid.uuid4().hex[:8].upper()
    return f"{INVOICE_PREFIX}-{unique}"


def _calculate_period_end(start: datetime, cycle: BillingCycle) -> datetime:
    """Calculate the period end date based on billing cycle."""
    if cycle == BillingCycle.YEARLY:
        return start + timedelta(days=365)
    return start + timedelta(days=30)


def _now() -> datetime:
    """Return current UTC datetime."""
    return datetime.utcnow()


def _calculate_proration(
    old_price: Decimal,
    new_price: Decimal,
    days_used: int,
    days_total: int,
) -> Decimal:
    """Calculate prorated amount for plan changes.

    Args:
        old_price: Current plan price for the billing cycle.
        new_price: New plan price for the billing cycle.
        days_used: Number of days used in current period.
        days_total: Total days in current billing period.

    Returns:
        Prorated difference (positive = charge, negative = credit).
    """
    if days_total <= 0:
        return Decimal("0.00")

    old_daily = old_price / Decimal(days_total)
    new_daily = new_price / Decimal(days_total)

    remaining_days = days_total - days_used
    used_credit = old_daily * Decimal(days_used)
    new_charge = new_daily * Decimal(days_total)

    return (new_charge - used_credit).quantize(Decimal("0.01"))


# ============================================================================
# PlanService
# ============================================================================


class PlanService:
    """Service for managing subscription plans."""

    @staticmethod
    async def get_plan(db: AsyncSession, plan_id: int) -> SubscriptionPlan:
        """Get a plan by ID.

        Args:
            db: Async database session.
            plan_id: Plan ID.

        Returns:
            SubscriptionPlan instance.

        Raises:
            NotFoundError: If plan does not exist.
        """
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundError(detail=f"Plan with ID {plan_id} not found")
        return plan

    @staticmethod
    async def list_plans(
        db: AsyncSession,
        include_inactive: bool = False,
    ) -> List[SubscriptionPlan]:
        """List all subscription plans.

        Args:
            db: Async database session.
            include_inactive: Whether to include inactive plans.

        Returns:
            List of SubscriptionPlan instances.
        """
        stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order)
        if not include_inactive:
            stmt = stmt.where(SubscriptionPlan.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_plan(
        db: AsyncSession,
        name: str,
        description: Optional[str] = None,
        price_monthly: Decimal = Decimal("0.00"),
        price_yearly: Decimal = Decimal("0.00"),
        currency: str = "USD",
        features: Optional[Dict[str, Any]] = None,
        limits: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        stripe_price_id: Optional[str] = None,
        sort_order: int = 0,
    ) -> SubscriptionPlan:
        """Create a new subscription plan.

        Args:
            db: Async database session.
            name: Plan name.
            description: Plan description.
            price_monthly: Monthly price.
            price_yearly: Yearly price.
            currency: Currency code.
            features: Feature flags dict.
            limits: Usage limits dict.
            is_active: Whether plan is active.
            stripe_price_id: Stripe price ID.
            sort_order: Display sort order.

        Returns:
            Created SubscriptionPlan instance.
        """
        plan = SubscriptionPlan(
            name=name,
            description=description,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            currency=currency,
            features=features or {},
            limits=limits or {},
            is_active=is_active,
            stripe_price_id=stripe_price_id,
            sort_order=sort_order,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def update_plan(
        db: AsyncSession,
        plan_id: int,
        **updates: Any,
    ) -> SubscriptionPlan:
        """Update a subscription plan.

        Args:
            db: Async database session.
            plan_id: Plan ID to update.
            **updates: Fields to update.

        Returns:
            Updated SubscriptionPlan instance.
        """
        plan = await PlanService.get_plan(db, plan_id)

        allowed_fields = {
            "name", "description", "price_monthly", "price_yearly",
            "currency", "features", "limits", "is_active",
            "stripe_price_id", "sort_order",
        }
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(plan, field, value)

        plan.updated_at = _now()
        await db.commit()
        await db.refresh(plan)
        return plan

    @staticmethod
    async def delete_plan(db: AsyncSession, plan_id: int) -> None:
        """Delete a subscription plan (only if no active subscriptions).

        Args:
            db: Async database session.
            plan_id: Plan ID to delete.

        Raises:
            ValidationError: If plan has active subscriptions.
        """
        plan = await PlanService.get_plan(db, plan_id)

        result = await db.execute(
            select(func.count()).select_from(CompanySubscription).where(
                CompanySubscription.plan_id == plan_id,
                CompanySubscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                    SubscriptionStatus.PAST_DUE,
                ]),
            )
        )
        active_count = result.scalar() or 0
        if active_count > 0:
            raise ValidationError(
                detail=f"Cannot delete plan with {active_count} active subscriptions"
            )

        await db.delete(plan)
        await db.commit()

    @staticmethod
    async def get_plan_features(db: AsyncSession, plan_id: int) -> Dict[str, Any]:
        """Get features for a plan.

        Args:
            db: Async database session.
            plan_id: Plan ID.

        Returns:
            Dictionary of feature flags.
        """
        plan = await PlanService.get_plan(db, plan_id)
        return plan.features or {}

    @staticmethod
    async def get_plan_limits(db: AsyncSession, plan_id: int) -> Dict[str, Any]:
        """Get limits for a plan.

        Args:
            db: Async database session.
            plan_id: Plan ID.

        Returns:
            Dictionary of usage limits.
        """
        plan = await PlanService.get_plan(db, plan_id)
        return plan.limits or {}

    @staticmethod
    async def initialize_default_plans(db: AsyncSession) -> List[SubscriptionPlan]:
        """Create default plans from constants if they don't exist.

        Args:
            db: Async database session.

        Returns:
            List of SubscriptionPlan instances.
        """
        existing = await PlanService.list_plans(db, include_inactive=True)
        if existing:
            return existing

        plans: List[SubscriptionPlan] = []
        for tier_key, definition in PLAN_DEFINITIONS.items():
            plan = SubscriptionPlan(
                name=definition["name"],
                description=definition["description"],
                price_monthly=definition["price_monthly"],
                price_yearly=definition["price_yearly"],
                currency=definition["currency"],
                features=definition["features"],
                limits=definition["limits"],
                is_active=definition["is_active"],
                sort_order=definition["sort_order"],
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(plan)
            plans.append(plan)

        await db.commit()
        for plan in plans:
            await db.refresh(plan)

        return plans


# ============================================================================
# SubscriptionService
# ============================================================================


class SubscriptionService:
    """Service for managing company subscriptions."""

    @staticmethod
    async def get_subscription(
        db: AsyncSession,
        company_id: int,
    ) -> Optional[CompanySubscription]:
        """Get current subscription for a company.

        Returns the most recent non-cancelled, non-expired subscription.
        Includes subscriptions that are scheduled for cancellation at
        period end (cancelled_at is set but status is still ACTIVE).

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            CompanySubscription or None.
        """
        now = _now()
        result = await db.execute(
            select(CompanySubscription)
            .options(selectinload(CompanySubscription.plan))
            .where(
                CompanySubscription.company_id == company_id,
                CompanySubscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                    SubscriptionStatus.PAST_DUE,
                ]),
                CompanySubscription.current_period_end > now,
            )
            .order_by(desc(CompanySubscription.created_at))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_subscription_by_id(
        db: AsyncSession,
        subscription_id: int,
    ) -> CompanySubscription:
        """Get subscription by ID.

        Args:
            db: Async database session.
            subscription_id: Subscription ID.

        Returns:
            CompanySubscription instance.

        Raises:
            NotFoundError: If subscription not found.
        """
        result = await db.execute(
            select(CompanySubscription)
            .options(selectinload(CompanySubscription.plan))
            .where(CompanySubscription.id == subscription_id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise NotFoundError(
                detail=f"Subscription with ID {subscription_id} not found"
            )
        return sub

    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        data: SubscriptionCreate,
    ) -> CompanySubscription:
        """Create a new subscription for a company.

        Starts with a trial period by default.

        Args:
            db: Async database session.
            data: Subscription creation data.

        Returns:
            Created CompanySubscription instance.
        """
        plan = await PlanService.get_plan(db, data.plan_id)
        now = _now()
        trial_days = data.trial_days or TRIAL_DURATION_DAYS

        period_end = _calculate_period_end(now, data.billing_cycle)
        trial_ends = now + timedelta(days=trial_days)

        subscription = CompanySubscription(
            company_id=data.company_id,
            plan_id=data.plan_id,
            status=SubscriptionStatus.TRIAL,
            billing_cycle=data.billing_cycle,
            started_at=now,
            current_period_start=now,
            current_period_end=period_end,
            trial_ends_at=trial_ends,
            auto_renew=data.auto_renew,
            created_at=now,
            updated_at=now,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        # Initialize quotas for the new subscription
        await UsageTrackingService.initialize_quotas(db, data.company_id, plan)

        # Initialize feature flags from plan defaults
        await FeatureFlagService.initialize_features(db, data.company_id, plan)

        # Log the event
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=data.company_id,
                event_type=BillingEventType.SUBSCRIPTION_CREATED,
                description=f"Subscribed to {plan.name} plan with {trial_days}-day trial",
                metadata={
                    "plan_id": plan.id,
                    "plan_name": plan.name,
                    "billing_cycle": data.billing_cycle.value,
                    "trial_days": trial_days,
                },
            ),
        )

        return subscription

    @staticmethod
    async def change_plan(
        db: AsyncSession,
        company_id: int,
        new_plan_id: int,
        billing_cycle: Optional[BillingCycle] = None,
    ) -> CompanySubscription:
        """Upgrade or downgrade a subscription to a different plan.

        Args:
            db: Async database session.
            company_id: Company ID.
            new_plan_id: New plan ID.
            billing_cycle: Optional new billing cycle.

        Returns:
            Updated CompanySubscription instance.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription is None:
            raise NotFoundError(
                detail=f"No active subscription found for company {company_id}"
            )

        old_plan = subscription.plan
        new_plan = await PlanService.get_plan(db, new_plan_id)

        old_price = (
            old_plan.price_monthly
            if subscription.billing_cycle == BillingCycle.MONTHLY
            else old_plan.price_yearly
        )
        new_price = (
            new_plan.price_monthly
            if (billing_cycle or subscription.billing_cycle) == BillingCycle.MONTHLY
            else new_plan.price_yearly
        )
        is_upgrade = new_price > old_price

        # Calculate proration (days_total = full period length)
        days_total = (subscription.current_period_end - subscription.current_period_start).days
        days_elapsed = (_now() - subscription.current_period_start).days
        proration = _calculate_proration(old_price, new_price, days_elapsed, max(days_total, 1))

        # Update subscription
        subscription.plan_id = new_plan_id
        if billing_cycle:
            subscription.billing_cycle = billing_cycle
        subscription.updated_at = _now()

        # If upgrading from trial, set to active
        if is_upgrade and subscription.status == SubscriptionStatus.TRIAL:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.trial_ends_at = None

        await db.commit()
        await db.refresh(subscription)

        # Re-initialize quotas and features for new plan
        await UsageTrackingService.initialize_quotas(db, company_id, new_plan)
        await FeatureFlagService.initialize_features(db, company_id, new_plan)

        event_type = (
            BillingEventType.SUBSCRIPTION_UPGRADED
            if is_upgrade
            else BillingEventType.SUBSCRIPTION_DOWNGRADED
        )
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=company_id,
                event_type=event_type,
                description=f"Plan changed from {old_plan.name} to {new_plan.name}",
                metadata={
                    "old_plan_id": old_plan.id,
                    "old_plan_name": old_plan.name,
                    "new_plan_id": new_plan.id,
                    "new_plan_name": new_plan.name,
                    "proration_amount": str(proration),
                    "is_upgrade": is_upgrade,
                },
            ),
        )

        return subscription

    @staticmethod
    async def cancel_subscription(
        db: AsyncSession,
        company_id: int,
        data: SubscriptionCancelRequest,
    ) -> CompanySubscription:
        """Cancel a company's subscription.

        - immediate=True: subscription ends immediately, status becomes CANCELLED
        - immediate=False: subscription remains active until period_end,
          auto_renew is disabled, status stays ACTIVE (will become CANCELLED
          at period_end naturally)

        Args:
            db: Async database session.
            company_id: Company ID.
            data: Cancellation request data.

        Returns:
            Updated CompanySubscription instance.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription is None:
            raise NotFoundError(
                detail=f"No active subscription found for company {company_id}"
            )

        now = _now()
        subscription.cancelled_at = now
        subscription.cancellation_reason = data.reason
        subscription.auto_renew = False
        subscription.updated_at = now

        if data.immediate:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.current_period_end = now
        else:
            # Period-end cancellation: keep status ACTIVE until period ends
            # The subscription remains usable until current_period_end.
            # A background job would mark it CANCELLED after period_end.
            pass

        await db.commit()
        await db.refresh(subscription)

        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=company_id,
                event_type=BillingEventType.SUBSCRIPTION_CANCELLED,
                description=(
                    "Subscription cancelled immediately"
                    if data.immediate
                    else "Subscription cancelled at period end"
                ),
                metadata={
                    "immediate": data.immediate,
                    "reason": data.reason,
                    "plan_id": subscription.plan_id,
                    "period_end": subscription.current_period_end.isoformat(),
                },
            ),
        )

        return subscription

    @staticmethod
    async def renew_subscription(
        db: AsyncSession,
        company_id: int,
    ) -> CompanySubscription:
        """Renew a subscription for a new billing period.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            Updated CompanySubscription instance.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription is None:
            raise NotFoundError(
                detail=f"No active subscription found for company {company_id}"
            )

        if subscription.status == SubscriptionStatus.CANCELLED:
            raise ValidationError(
                detail="Cannot renew a cancelled subscription"
            )

        now = _now()
        new_period_end = _calculate_period_end(now, subscription.billing_cycle)

        subscription.current_period_start = now
        subscription.current_period_end = new_period_end
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.updated_at = now

        await db.commit()
        await db.refresh(subscription)

        # Reset usage quotas for new period
        plan = await PlanService.get_plan(db, subscription.plan_id)
        await UsageTrackingService.initialize_quotas(db, company_id, plan)

        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=company_id,
                event_type=BillingEventType.SUBSCRIPTION_RENEWED,
                description=f"Subscription renewed for {subscription.billing_cycle.value} period",
                metadata={
                    "plan_id": subscription.plan_id,
                    "period_start": now.isoformat(),
                    "period_end": new_period_end.isoformat(),
                },
            ),
        )

        return subscription

    @staticmethod
    async def check_trial_status(
        db: AsyncSession,
        company_id: int,
    ) -> bool:
        """Check if a trial has expired and update status.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            True if trial is still active or was converted.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription is None:
            return False

        if subscription.status != SubscriptionStatus.TRIAL:
            return True

        if (
            subscription.trial_ends_at
            and _now() > subscription.trial_ends_at
        ):
            subscription.status = SubscriptionStatus.EXPIRED
            subscription.updated_at = _now()
            await db.commit()
            await db.refresh(subscription)

            await BillingEventService.create_event(
                db,
                BillingEventCreate(
                    company_id=company_id,
                    event_type=BillingEventType.QUOTA_EXCEEDED,
                    description="Trial period expired",
                    metadata={"trial_ended_at": subscription.trial_ends_at.isoformat()},
                ),
            )
            return False

        return True

    @staticmethod
    async def to_response(
        db: AsyncSession,
        subscription: CompanySubscription,
    ) -> SubscriptionResponse:
        """Convert a subscription model to a response schema.

        Args:
            db: Async database session.
            subscription: CompanySubscription instance.

        Returns:
            SubscriptionResponse schema.
        """
        plan = subscription.plan
        plan_name = plan.name if plan else "Unknown"

        return SubscriptionResponse(
            id=subscription.id,
            company_id=subscription.company_id,
            plan_id=subscription.plan_id,
            plan_name=plan_name,
            status=subscription.status,
            billing_cycle=subscription.billing_cycle,
            started_at=subscription.started_at,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
            cancelled_at=subscription.cancelled_at,
            cancellation_reason=subscription.cancellation_reason,
            auto_renew=subscription.auto_renew,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )


# ============================================================================
# UsageTrackingService
# ============================================================================


class UsageTrackingService:
    """Service for recording and querying usage data."""

    @staticmethod
    async def record_usage(
        db: AsyncSession,
        data: UsageRecordCreate,
    ) -> UsageRecord:
        """Record a usage event.

        Args:
            db: Async database session.
            data: Usage record creation data.

        Returns:
            Created UsageRecord instance.
        """
        unit = data.unit or RESOURCE_UNITS.get(data.resource_type.value, "unit")
        cost = data.cost or DEFAULT_COST_PER_UNIT.get(
            data.resource_type.value, Decimal("0.00")
        ) * Decimal(data.quantity)

        record = UsageRecord(
            company_id=data.company_id,
            resource_type=data.resource_type,
            quantity=data.quantity,
            unit=unit,
            cost=cost,
            metadata=data.metadata,
            recorded_at=_now(),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return record

    @staticmethod
    async def record_usage_from_track(
        db: AsyncSession,
        company_id: int,
        data: UsageTrackRequest,
    ) -> UsageRecord:
        """Record usage from a track request.

        Args:
            db: Async database session.
            company_id: Company ID.
            data: Usage track request data.

        Returns:
            Created UsageRecord instance.
        """
        unit = RESOURCE_UNITS.get(data.resource_type.value, "unit")
        cost = DEFAULT_COST_PER_UNIT.get(
            data.resource_type.value, Decimal("0.00")
        ) * Decimal(data.quantity)

        record = UsageRecord(
            company_id=company_id,
            resource_type=data.resource_type,
            quantity=data.quantity,
            unit=unit,
            cost=cost,
            metadata=data.metadata,
            recorded_at=_now(),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return record

    @staticmethod
    async def get_usage_summary(
        db: AsyncSession,
        company_id: int,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get usage summary broken down by resource type.

        Args:
            db: Async database session.
            company_id: Company ID.
            period_start: Start of period (default: current period).
            period_end: End of period (default: now).

        Returns:
            Dictionary mapping resource types to usage stats.
        """
        if period_start is None:
            subscription = await SubscriptionService.get_subscription(db, company_id)
            if subscription:
                period_start = subscription.current_period_start
            else:
                period_start = _now() - timedelta(days=30)

        if period_end is None:
            period_end = _now()

        result = await db.execute(
            select(
                UsageRecord.resource_type,
                func.sum(UsageRecord.quantity).label("total_quantity"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count().label("record_count"),
            )
            .where(
                UsageRecord.company_id == company_id,
                UsageRecord.recorded_at >= period_start,
                UsageRecord.recorded_at <= period_end,
            )
            .group_by(UsageRecord.resource_type)
        )

        breakdown: Dict[str, Dict[str, Any]] = {}
        for row in result.all():
            breakdown[row.resource_type.value] = {
                "total_quantity": int(row.total_quantity or 0),
                "total_cost": Decimal(str(row.total_cost or 0)).quantize(Decimal("0.0001")),
                "record_count": int(row.record_count or 0),
            }

        return breakdown

    @staticmethod
    async def initialize_quotas(
        db: AsyncSession,
        company_id: int,
        plan: SubscriptionPlan,
    ) -> List[UsageQuota]:
        """Initialize or reset usage quotas for a company based on plan.

        Args:
            db: Async database session.
            company_id: Company ID.
            plan: Subscription plan defining limits.

        Returns:
            List of UsageQuota instances.
        """
        limits = plan.limits or {}
        now = _now()
        reset_at = now + timedelta(days=30)

        resource_limit_map = {
            ResourceType.AI_REQUEST: limits.get("max_ai_requests", 0),
            ResourceType.SOCIAL_POST: limits.get("max_posts", 0),
            ResourceType.STORAGE: limits.get("storage_gb", 0),
            ResourceType.API_CALL: limits.get("max_api_calls", 0),
            ResourceType.SMS: limits.get("max_sms", 0),
            ResourceType.EMAIL: limits.get("max_email", 0),
        }

        quotas: List[UsageQuota] = []
        for resource_type, limit_amount in resource_limit_map.items():
            # Check if quota already exists
            result = await db.execute(
                select(UsageQuota).where(
                    UsageQuota.company_id == company_id,
                    UsageQuota.resource_type == resource_type,
                    UsageQuota.period == QuotaPeriod.MONTHLY,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.limit_amount = limit_amount
                existing.current_usage = 0
                existing.reset_at = reset_at
                existing.warning_sent = False
                existing.updated_at = now
                quotas.append(existing)
            else:
                quota = UsageQuota(
                    company_id=company_id,
                    resource_type=resource_type,
                    limit_amount=limit_amount,
                    current_usage=0,
                    period=QuotaPeriod.MONTHLY,
                    reset_at=reset_at,
                    warning_sent=False,
                    created_at=now,
                    updated_at=now,
                )
                db.add(quota)
                quotas.append(quota)

        await db.commit()
        for quota in quotas:
            await db.refresh(quota)

        return quotas

    @staticmethod
    async def track_ai_request(
        db: AsyncSession,
        company_id: int,
        model: str,
        tokens_used: int = 0,
        cost_override: Optional[Decimal] = None,
    ) -> UsageRecord:
        """Convenience method to track an AI request.

        Records both the usage record AND increments the AI_REQUEST quota.
        This should be called after every AI completion request.

        Args:
            db: Async database session.
            company_id: Company ID.
            model: AI model used (e.g. 'gpt-4', 'gpt-3.5-turbo').
            tokens_used: Number of tokens consumed.
            cost_override: Optional explicit cost override.

        Returns:
            Created UsageRecord instance.

        Raises:
            ValidationError: If AI_REQUEST quota is exceeded.
        """
        # Calculate cost per request with division-by-zero protection
        token_limit = max(getattr(settings, 'AI_MONTHLY_TOKEN_LIMIT', 1_000_000), 1)
        cost_limit = max(getattr(settings, 'AI_MONTHLY_COST_LIMIT_USD', 100.0), 0.01)
        cost_per_request = cost_override or Decimal(
            str(cost_limit / token_limit * max(tokens_used, 1))
        )

        record = UsageRecord(
            company_id=company_id,
            resource_type=ResourceType.AI_REQUEST,
            quantity=1,
            unit=RESOURCE_UNITS.get(ResourceType.AI_REQUEST.value, "request"),
            cost=cost_per_request,
            metadata={
                "model": model,
                "tokens_used": tokens_used,
                "tracked_at": _now().isoformat(),
            },
            recorded_at=_now(),
        )
        db.add(record)

        # Also increment the quota
        result = await db.execute(
            select(UsageQuota).where(
                UsageQuota.company_id == company_id,
                UsageQuota.resource_type == ResourceType.AI_REQUEST,
            )
        )
        quota = result.scalar_one_or_none()

        if quota is not None and quota.limit_amount >= 0:
            if (quota.current_usage + 1) > quota.limit_amount:
                await db.rollback()
                raise ValidationError(
                    detail=f"AI request quota exceeded: {quota.current_usage}/{quota.limit_amount}"
                )
            quota.current_usage += 1
            quota.updated_at = _now()

        await db.commit()
        await db.refresh(record)
        if quota is not None:
            await db.refresh(quota)

        return record

    @staticmethod
    async def get_usage_timeseries(
        db: AsyncSession,
        company_id: int,
        resource_type: Optional[ResourceType] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily usage timeseries for dashboard charts.

        Returns aggregated daily usage counts for the last N days,
        suitable for rendering line/bar charts on the billing dashboard.

        Args:
            db: Async database session.
            company_id: Company ID.
            resource_type: Optional filter for a specific resource type.
            days: Number of days to look back (default: 30).

        Returns:
            List of daily usage data points.
        """
        from sqlalchemy import cast, Date

        period_start = _now() - timedelta(days=days)

        stmt = (
            select(
                cast(UsageRecord.recorded_at, Date).label("date"),
                UsageRecord.resource_type,
                func.sum(UsageRecord.quantity).label("total_quantity"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count().label("request_count"),
            )
            .where(
                UsageRecord.company_id == company_id,
                UsageRecord.recorded_at >= period_start,
            )
            .group_by(
                cast(UsageRecord.recorded_at, Date),
                UsageRecord.resource_type,
            )
            .order_by(cast(UsageRecord.recorded_at, Date))
        )

        if resource_type:
            stmt = stmt.where(UsageRecord.resource_type == resource_type)

        result = await db.execute(stmt)

        data_points: Dict[str, Dict[str, Any]] = {}
        for row in result.all():
            date_key = str(row.date)
            if date_key not in data_points:
                data_points[date_key] = {
                    "date": date_key,
                    "total_quantity": 0,
                    "total_cost": Decimal("0.00"),
                    "request_count": 0,
                    "by_resource": {},
                }
            data_points[date_key]["total_quantity"] += int(row.total_quantity or 0)
            data_points[date_key]["total_cost"] += Decimal(str(row.total_cost or 0))
            data_points[date_key]["request_count"] += int(row.request_count or 0)
            resource_key = row.resource_type.value
            data_points[date_key]["by_resource"][resource_key] = {
                "quantity": int(row.total_quantity or 0),
                "cost": Decimal(str(row.total_cost or 0)).quantize(Decimal("0.0001")),
                "requests": int(row.request_count or 0),
            }

        return list(data_points.values())

    @staticmethod
    async def get_resource_breakdown(
        db: AsyncSession,
        company_id: int,
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """Get usage breakdown by resource type for pie/donut charts.

        Args:
            db: Async database session.
            company_id: Company ID.
            days: Number of days to look back.

        Returns:
            Dictionary mapping resource types to aggregated stats.
        """
        period_start = _now() - timedelta(days=days)

        result = await db.execute(
            select(
                UsageRecord.resource_type,
                func.sum(UsageRecord.quantity).label("total_quantity"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count().label("request_count"),
            )
            .where(
                UsageRecord.company_id == company_id,
                UsageRecord.recorded_at >= period_start,
            )
            .group_by(UsageRecord.resource_type)
        )

        breakdown: Dict[str, Dict[str, Any]] = {}
        total_cost = Decimal("0.00")
        total_requests = 0

        for row in result.all():
            resource_key = row.resource_type.value
            cost = Decimal(str(row.total_cost or 0))
            requests = int(row.request_count or 0)
            breakdown[resource_key] = {
                "quantity": int(row.total_quantity or 0),
                "cost": cost.quantize(Decimal("0.0001")),
                "requests": requests,
                "unit": RESOURCE_UNITS.get(resource_key, "unit"),
            }
            total_cost += cost
            total_requests += requests

        breakdown["_totals"] = {
            "total_cost": total_cost.quantize(Decimal("0.0001")),
            "total_requests": total_requests,
            "period_days": days,
        }

        return breakdown

    @staticmethod
    async def get_top_usage_days(
        db: AsyncSession,
        company_id: int,
        resource_type: ResourceType,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get top usage days for a resource type.

        Useful for identifying peak usage days on the dashboard.

        Args:
            db: Async database session.
            company_id: Company ID.
            resource_type: Resource type to analyze.
            limit: Number of top days to return.

        Returns:
            List of top usage day records.
        """
        from sqlalchemy import cast, Date

        result = await db.execute(
            select(
                cast(UsageRecord.recorded_at, Date).label("date"),
                func.sum(UsageRecord.quantity).label("total_quantity"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count().label("request_count"),
            )
            .where(
                UsageRecord.company_id == company_id,
                UsageRecord.resource_type == resource_type,
            )
            .group_by(cast(UsageRecord.recorded_at, Date))
            .order_by(func.sum(UsageRecord.quantity).desc())
            .limit(limit)
        )

        return [
            {
                "date": str(row.date),
                "quantity": int(row.total_quantity or 0),
                "cost": Decimal(str(row.total_cost or 0)).quantize(Decimal("0.0001")),
                "requests": int(row.request_count or 0),
            }
            for row in result.all()
        ]


# ============================================================================
# QuotaEnforcementService
# ============================================================================


class QuotaEnforcementService:
    """Service for enforcing usage quotas and limits."""

    @staticmethod
    async def check_quota(
        db: AsyncSession,
        company_id: int,
        resource_type: ResourceType,
        requested_quantity: int = 1,
    ) -> QuotaCheckResponse:
        """Check if an action is allowed within quota limits.

        Args:
            db: Async database session.
            company_id: Company ID.
            resource_type: Type of resource to check.
            requested_quantity: Amount requested.

        Returns:
            QuotaCheckResponse with result details.
        """
        result = await db.execute(
            select(UsageQuota).where(
                UsageQuota.company_id == company_id,
                UsageQuota.resource_type == resource_type,
            )
        )
        quota = result.scalar_one_or_none()

        # If no quota record exists, check if company has a subscription
        if quota is None:
            subscription = await SubscriptionService.get_subscription(db, company_id)
            if subscription is None:
                return QuotaCheckResponse(
                    allowed=False,
                    resource_type=resource_type,
                    current_usage=0,
                    limit=0,
                    remaining=0,
                    usage_percentage=0.0,
                    would_exceed=True,
                    reason="No active subscription found",
                )
            # Allow if no specific quota defined (unlimited for this resource)
            return QuotaCheckResponse(
                allowed=True,
                resource_type=resource_type,
                current_usage=0,
                limit=-1,
                remaining=-1,
                usage_percentage=0.0,
                would_exceed=False,
            )

        # Zero limit = feature disabled for this plan
        if quota.limit_amount == 0:
            return QuotaCheckResponse(
                allowed=False,
                resource_type=resource_type,
                current_usage=quota.current_usage,
                limit=0,
                remaining=0,
                usage_percentage=100.0,
                would_exceed=True,
                reason=f"{resource_type.value} is not included in the current plan",
            )

        # Unlimited quota (-1)
        if quota.limit_amount < 0:
            return QuotaCheckResponse(
                allowed=True,
                resource_type=resource_type,
                current_usage=quota.current_usage,
                limit=-1,
                remaining=-1,
                usage_percentage=0.0,
                would_exceed=False,
            )

        remaining = quota.limit_amount - quota.current_usage
        usage_percentage = (
            (quota.current_usage / quota.limit_amount * 100)
            if quota.limit_amount > 0
            else 0.0
        )
        would_exceed = (quota.current_usage + requested_quantity) > quota.limit_amount

        if would_exceed:
            return QuotaCheckResponse(
                allowed=False,
                resource_type=resource_type,
                current_usage=quota.current_usage,
                limit=quota.limit_amount,
                remaining=remaining,
                usage_percentage=round(usage_percentage, 2),
                would_exceed=True,
                reason=f"Quota exceeded: {quota.current_usage}/{quota.limit_amount} {quota.resource_type.value} used",
            )

        return QuotaCheckResponse(
            allowed=True,
            resource_type=resource_type,
            current_usage=quota.current_usage,
            limit=quota.limit_amount,
            remaining=remaining,
            usage_percentage=round(usage_percentage, 2),
            would_exceed=False,
        )

    @staticmethod
    async def increment_usage(
        db: AsyncSession,
        company_id: int,
        resource_type: ResourceType,
        quantity: int = 1,
    ) -> UsageQuota:
        """Increment usage for a resource type.

        Args:
            db: Async database session.
            company_id: Company ID.
            resource_type: Type of resource used.
            quantity: Amount consumed.

        Returns:
            Updated UsageQuota instance.

        Raises:
            ValidationError: If quota would be exceeded.
        """
        result = await db.execute(
            select(UsageQuota).where(
                UsageQuota.company_id == company_id,
                UsageQuota.resource_type == resource_type,
            )
        )
        quota = result.scalar_one_or_none()

        if quota is None:
            raise ValidationError(
                detail=f"No quota defined for resource type {resource_type.value}"
            )

        # Unlimited
        if quota.limit_amount < 0:
            quota.current_usage += quantity
            quota.updated_at = _now()
            await db.commit()
            await db.refresh(quota)
            return quota

        # Check if increment would exceed
        if (quota.current_usage + quantity) > quota.limit_amount:
            raise ValidationError(
                detail=f"Quota exceeded for {resource_type.value}: "
                f"{quota.current_usage}/{quota.limit_amount}"
            )

        quota.current_usage += quantity
        quota.updated_at = _now()

        # Check warning thresholds
        usage_percentage = (quota.current_usage / quota.limit_amount) * 100
        if not quota.warning_sent and usage_percentage >= QUOTA_WARNING_THRESHOLD:
            quota.warning_sent = True

        await db.commit()
        await db.refresh(quota)

        # Log threshold events
        if usage_percentage >= QUOTA_EXCEEDED_THRESHOLD:
            await BillingEventService.create_event(
                db,
                BillingEventCreate(
                    company_id=company_id,
                    event_type=BillingEventType.QUOTA_EXCEEDED,
                    description=f"Quota exceeded for {resource_type.value}",
                    metadata={
                        "resource_type": resource_type.value,
                        "current_usage": quota.current_usage,
                        "limit": quota.limit_amount,
                        "percentage": usage_percentage,
                    },
                ),
            )
        elif usage_percentage >= QUOTA_WARNING_THRESHOLD:
            await BillingEventService.create_event(
                db,
                BillingEventCreate(
                    company_id=company_id,
                    event_type=BillingEventType.QUOTA_WARNING,
                    description=f"Quota warning for {resource_type.value}: {usage_percentage:.0f}% used",
                    metadata={
                        "resource_type": resource_type.value,
                        "current_usage": quota.current_usage,
                        "limit": quota.limit_amount,
                        "percentage": usage_percentage,
                    },
                ),
            )

        return quota

    @staticmethod
    async def get_quota_status(
        db: AsyncSession,
        company_id: int,
    ) -> List[QuotaResponse]:
        """Get all quota statuses for a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            List of QuotaResponse schemas.
        """
        result = await db.execute(
            select(UsageQuota)
            .where(UsageQuota.company_id == company_id)
            .order_by(UsageQuota.resource_type)
        )
        quotas = result.scalars().all()

        responses: List[QuotaResponse] = []
        for quota in quotas:
            limit = quota.limit_amount
            is_unlimited = limit < 0
            usage_percentage = (
                0.0
                if is_unlimited
                else (quota.current_usage / limit * 100) if limit > 0 else 0.0
            )
            remaining = -1 if is_unlimited else max(0, limit - quota.current_usage)

            responses.append(QuotaResponse(
                id=quota.id,
                company_id=quota.company_id,
                resource_type=quota.resource_type,
                limit_amount=limit,
                current_usage=quota.current_usage,
                usage_percentage=round(usage_percentage, 2),
                remaining=remaining,
                period=quota.period,
                reset_at=quota.reset_at,
                warning_sent=quota.warning_sent,
                is_unlimited=is_unlimited,
                created_at=quota.created_at,
                updated_at=quota.updated_at,
            ))

        return responses


# ============================================================================
# InvoiceService
# ============================================================================


class InvoiceService:
    """Service for invoice generation and management."""

    @staticmethod
    async def get_invoice(db: AsyncSession, invoice_id: int) -> Invoice:
        """Get an invoice by ID.

        Args:
            db: Async database session.
            invoice_id: Invoice ID.

        Returns:
            Invoice instance.

        Raises:
            NotFoundError: If invoice not found.
        """
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise NotFoundError(detail=f"Invoice with ID {invoice_id} not found")
        return invoice

    @staticmethod
    async def list_invoices(
        db: AsyncSession,
        company_id: int,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Invoice]:
        """List invoices for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            status: Optional status filter.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List of Invoice instances.
        """
        stmt = select(Invoice).where(
            Invoice.company_id == company_id,
        ).order_by(desc(Invoice.created_at)).limit(limit).offset(offset)

        if status:
            stmt = stmt.where(Invoice.status == status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_invoice(
        db: AsyncSession,
        data: InvoiceCreate,
    ) -> Invoice:
        """Create a new invoice.

        Args:
            db: Async database session.
            data: Invoice creation data.

        Returns:
            Created Invoice instance.
        """
        invoice_number = _generate_invoice_number()
        now = _now()
        due_date = data.due_date or (now + timedelta(days=INVOICE_DUE_DAYS))

        invoice = Invoice(
            company_id=data.company_id,
            invoice_number=invoice_number,
            status=InvoiceStatus.DRAFT,
            subtotal=data.subtotal,
            tax_amount=data.tax_amount,
            total=data.total,
            currency=data.currency,
            due_date=due_date,
            line_items=[item.model_dump() for item in data.line_items],
            metadata=data.metadata,
            created_at=now,
            updated_at=now,
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        return invoice

    @staticmethod
    async def generate_subscription_invoice(
        db: AsyncSession,
        company_id: int,
    ) -> Invoice:
        """Generate an invoice for the current subscription period.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            Created Invoice instance.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription is None:
            raise NotFoundError(
                detail=f"No active subscription for company {company_id}"
            )

        plan = await PlanService.get_plan(db, subscription.plan_id)
        unit_price = (
            plan.price_monthly
            if subscription.billing_cycle == BillingCycle.MONTHLY
            else plan.price_yearly
        )

        tax = (unit_price * STRIPE_TAX_RATE_PERCENT / 100).quantize(Decimal("0.01"))
        total = unit_price + tax

        line_item = {
            "description": f"{plan.name} Plan - {subscription.billing_cycle.value.title()}",
            "quantity": 1,
            "unit_price": str(unit_price),
            "amount": str(unit_price),
        }

        due_date = _now() + timedelta(days=INVOICE_DUE_DAYS)

        invoice = Invoice(
            company_id=company_id,
            invoice_number=_generate_invoice_number(),
            status=InvoiceStatus.OPEN,
            subtotal=unit_price,
            tax_amount=tax,
            total=total,
            currency=plan.currency,
            due_date=due_date,
            line_items=[line_item],
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        # Also create via schema for event logging
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=company_id,
                event_type=BillingEventType.INVOICE_GENERATED,
                description=f"Invoice {invoice.invoice_number} generated",
                metadata={
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "total": str(total),
                    "plan_id": plan.id,
                },
            ),
        )

        return invoice

    @staticmethod
    async def mark_paid(db: AsyncSession, invoice_id: int) -> Invoice:
        """Mark an invoice as paid.

        Args:
            db: Async database session.
            invoice_id: Invoice ID.

        Returns:
            Updated Invoice instance.
        """
        invoice = await InvoiceService.get_invoice(db, invoice_id)
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = _now()
        invoice.updated_at = _now()

        await db.commit()
        await db.refresh(invoice)

        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=invoice.company_id,
                event_type=BillingEventType.INVOICE_PAID,
                description=f"Invoice {invoice.invoice_number} marked as paid",
                metadata={
                    "invoice_id": invoice.id,
                    "amount": str(invoice.total),
                },
            ),
        )

        return invoice

    @staticmethod
    async def void_invoice(db: AsyncSession, invoice_id: int) -> Invoice:
        """Void an invoice.

        Args:
            db: Async database session.
            invoice_id: Invoice ID.

        Returns:
            Updated Invoice instance.
        """
        invoice = await InvoiceService.get_invoice(db, invoice_id)

        if invoice.status == InvoiceStatus.PAID:
            raise ValidationError(detail="Cannot void a paid invoice")

        invoice.status = InvoiceStatus.VOID
        invoice.updated_at = _now()

        await db.commit()
        await db.refresh(invoice)
        return invoice

    @staticmethod
    async def get_total_unpaid(db: AsyncSession, company_id: int) -> Decimal:
        """Get total unpaid amount for a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            Total unpaid amount.
        """
        result = await db.execute(
            select(func.sum(Invoice.total)).where(
                Invoice.company_id == company_id,
                Invoice.status == InvoiceStatus.OPEN,
            )
        )
        total = result.scalar()
        return Decimal(str(total or "0.00")).quantize(Decimal("0.01"))


# ============================================================================
# FeatureFlagService
# ============================================================================


class FeatureFlagService:
    """Service for managing feature flags per company."""

    @staticmethod
    async def get_feature_flag(
        db: AsyncSession,
        company_id: int,
        feature_name: FeatureName,
    ) -> Optional[FeatureFlag]:
        """Get a feature flag by company and feature name.

        Args:
            db: Async database session.
            company_id: Company ID.
            feature_name: Feature name.

        Returns:
            FeatureFlag instance or None.
        """
        result = await db.execute(
            select(FeatureFlag).where(
                FeatureFlag.company_id == company_id,
                FeatureFlag.feature_name == feature_name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_features(
        db: AsyncSession,
        company_id: int,
    ) -> List[FeatureFlag]:
        """List all feature flags for a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            List of FeatureFlag instances.
        """
        result = await db.execute(
            select(FeatureFlag)
            .where(FeatureFlag.company_id == company_id)
            .order_by(FeatureFlag.feature_name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def check_feature(
        db: AsyncSession,
        company_id: int,
        feature_name: FeatureName,
    ) -> bool:
        """Check if a feature is enabled for a company.

        Checks both plan-based defaults AND manually toggled feature flags.
        Priority: manual override > plan default. If a feature flag exists in
        the database, it takes precedence over plan defaults.

        Args:
            db: Async database session.
            company_id: Company ID.
            feature_name: Feature name.

        Returns:
            True if feature is enabled and not expired.
        """
        # First check for manual override (FeatureFlag table)
        flag = await FeatureFlagService.get_feature_flag(db, company_id, feature_name)

        if flag is not None:
            # Manual override exists - respect it unless expired
            if not flag.enabled:
                return False
            if flag.expires_at and _now() > flag.expires_at:
                return False
            return True

        # No manual override - fall back to plan-based default
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription and subscription.plan:
            plan_features = subscription.plan.features or {}
            return bool(plan_features.get(feature_name.value, False))

        # No subscription, no flag -> feature is disabled
        return False

    @staticmethod
    async def toggle_feature(
        db: AsyncSession,
        company_id: int,
        feature_name: FeatureName,
        enabled: bool,
        enabled_by: Optional[int] = None,
        reason: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> FeatureFlag:
        """Toggle a feature flag.

        Args:
            db: Async database session.
            company_id: Company ID.
            feature_name: Feature name.
            enabled: New enabled state.
            enabled_by: User ID who toggled.
            reason: Reason for toggle.
            expires_at: Optional expiration date.

        Returns:
            Updated FeatureFlag instance.
        """
        flag = await FeatureFlagService.get_feature_flag(db, company_id, feature_name)
        now = _now()

        if flag:
            flag.enabled = enabled
            flag.enabled_by = enabled_by if enabled else None
            flag.enabled_at = now if enabled else flag.enabled_at
            flag.reason = reason or flag.reason
            flag.expires_at = expires_at or flag.expires_at
            flag.updated_at = now
        else:
            flag = FeatureFlag(
                company_id=company_id,
                feature_name=feature_name,
                enabled=enabled,
                enabled_by=enabled_by if enabled else None,
                enabled_at=now if enabled else None,
                reason=reason,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            db.add(flag)

        await db.commit()
        await db.refresh(flag)

        event_type = (
            BillingEventType.FEATURE_ENABLED
            if enabled
            else BillingEventType.FEATURE_DISABLED
        )
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=company_id,
                event_type=event_type,
                description=f"Feature {feature_name.value} {'enabled' if enabled else 'disabled'}",
                metadata={
                    "feature_name": feature_name.value,
                    "enabled": enabled,
                    "enabled_by": enabled_by,
                    "reason": reason,
                },
            ),
        )

        return flag

    @staticmethod
    async def initialize_features(
        db: AsyncSession,
        company_id: int,
        plan: SubscriptionPlan,
    ) -> List[FeatureFlag]:
        """Initialize feature flags from plan defaults.

        Args:
            db: Async database session.
            company_id: Company ID.
            plan: Subscription plan with default features.

        Returns:
            List of FeatureFlag instances.
        """
        features = plan.features or {}
        now = _now()
        flags: List[FeatureFlag] = []

        for feature_name_value, enabled in features.items():
            try:
                feature_name = FeatureName(feature_name_value)
            except ValueError:
                continue

            result = await db.execute(
                select(FeatureFlag).where(
                    FeatureFlag.company_id == company_id,
                    FeatureFlag.feature_name == feature_name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.enabled = enabled
                existing.updated_at = now
                flags.append(existing)
            else:
                flag = FeatureFlag(
                    company_id=company_id,
                    feature_name=feature_name,
                    enabled=enabled,
                    created_at=now,
                    updated_at=now,
                )
                db.add(flag)
                flags.append(flag)

        await db.commit()
        for flag in flags:
            await db.refresh(flag)

        return flags


# ============================================================================
# BillingEventService
# ============================================================================


class BillingEventService:
    """Service for logging and querying billing events."""

    @staticmethod
    async def create_event(
        db: AsyncSession,
        data: BillingEventCreate,
    ) -> BillingEvent:
        """Create a billing event log entry.

        Args:
            db: Async database session.
            data: Billing event creation data.

        Returns:
            Created BillingEvent instance.
        """
        event = BillingEvent(
            company_id=data.company_id,
            event_type=data.event_type,
            description=data.description,
            metadata=data.metadata,
            created_at=_now(),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def list_events(
        db: AsyncSession,
        company_id: int,
        event_type: Optional[BillingEventType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BillingEvent]:
        """List billing events for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            event_type: Optional event type filter.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List of BillingEvent instances.
        """
        stmt = select(BillingEvent).where(
            BillingEvent.company_id == company_id,
        ).order_by(desc(BillingEvent.created_at)).limit(limit).offset(offset)

        if event_type:
            stmt = stmt.where(BillingEvent.event_type == event_type)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_company_stats(
        db: AsyncSession,
        company_id: int,
    ) -> Dict[str, Any]:
        """Get billing statistics for a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            Dictionary of billing statistics.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        quotas = await QuotaEnforcementService.get_quota_status(db, company_id)
        unpaid = await InvoiceService.get_total_unpaid(db, company_id)

        features = {}
        if subscription and subscription.plan:
            features = subscription.plan.features or {}

        days_remaining = 0
        is_trial = False
        if subscription:
            is_trial = subscription.status == SubscriptionStatus.TRIAL
            if is_trial and subscription.trial_ends_at:
                days_remaining = max(0, (subscription.trial_ends_at - _now()).days)
            else:
                days_remaining = max(0, (subscription.current_period_end - _now()).days)

        quota_dict = {}
        for q in quotas:
            quota_dict[q.resource_type.value] = {
                "limit": q.limit_amount,
                "used": q.current_usage,
                "remaining": q.remaining,
                "percentage": q.usage_percentage,
                "is_unlimited": q.is_unlimited,
            }

        return {
            "company_id": company_id,
            "current_plan": subscription.plan.name if subscription and subscription.plan else "None",
            "subscription_status": subscription.status if subscription else SubscriptionStatus.EXPIRED,
            "billing_cycle": subscription.billing_cycle if subscription else BillingCycle.MONTHLY,
            "current_period_end": subscription.current_period_end if subscription else None,
            "is_trial": is_trial,
            "days_remaining": days_remaining,
            "features": features,
            "quotas": quota_dict,
            "total_unpaid": unpaid,
        }


# ============================================================================
# StripeReadyService
# ============================================================================


class StripeReadyService:
    """Service for preparing Stripe-compatible billing structures.

    This service provides methods that create data structures compatible
    with the Stripe API, making future Stripe integration seamless.
    No actual payment processing is performed.
    """

    @staticmethod
    def create_stripe_customer_object(company: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Stripe-compatible customer object.

        Args:
            company: Company data dictionary.

        Returns:
            Stripe customer object structure.
        """
        return {
            "object": "customer",
            "id": f"cus_company_{company.get('id', 'unknown')}",
            "name": company.get("name", ""),
            "email": company.get("email", ""),
            "phone": company.get("phone", ""),
            "description": f"Customer for company {company.get('id', '')}",
            "metadata": {
                "company_id": str(company.get("id", "")),
                "slug": company.get("slug", ""),
            },
            "created": int(_now().timestamp()),
        }

    @staticmethod
    def create_stripe_subscription_object(
        subscription: CompanySubscription,
        plan: SubscriptionPlan,
    ) -> Dict[str, Any]:
        """Create a Stripe-compatible subscription object.

        Args:
            subscription: CompanySubscription instance.
            plan: SubscriptionPlan instance.

        Returns:
            Stripe subscription object structure.
        """
        price_amount = (
            plan.price_monthly
            if subscription.billing_cycle == BillingCycle.MONTHLY
            else plan.price_yearly
        )

        return {
            "object": "subscription",
            "id": f"sub_{subscription.id}",
            "customer": f"cus_company_{subscription.company_id}",
            "status": subscription.status.value,
            "current_period_start": int(subscription.current_period_start.timestamp()),
            "current_period_end": int(subscription.current_period_end.timestamp()),
            "cancel_at_period_end": not subscription.auto_renew,
            "canceled_at": (
                int(subscription.cancelled_at.timestamp())
                if subscription.cancelled_at
                else None
            ),
            "items": {
                "object": "list",
                "data": [
                    {
                        "object": "subscription_item",
                        "id": f"si_{subscription.id}",
                        "price": {
                            "object": "price",
                            "id": plan.stripe_price_id or f"price_plan_{plan.id}",
                            "unit_amount": int(price_amount * 100),  # cents
                            "currency": plan.currency.lower(),
                            "recurring": {
                                "interval": (
                                    "month"
                                    if subscription.billing_cycle == BillingCycle.MONTHLY
                                    else "year"
                                ),
                            },
                        },
                        "quantity": 1,
                    }
                ],
            },
            "metadata": {
                "company_id": str(subscription.company_id),
                "plan_id": str(plan.id),
                "plan_name": plan.name,
            },
        }

    @staticmethod
    def create_stripe_invoice_object(
        invoice: Invoice,
        company: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe-compatible invoice object.

        Args:
            invoice: Invoice instance.
            company: Optional company data.

        Returns:
            Stripe invoice object structure.
        """
        customer_id = (
            f"cus_company_{company.get('id')}" if company else "cus_unknown"
        )

        line_items = []
        if invoice.line_items:
            for idx, item in enumerate(invoice.line_items):
                line_items.append({
                    "object": "line_item",
                    "id": f"il_{invoice.id}_{idx}",
                    "description": item.get("description", ""),
                    "amount": int(Decimal(str(item.get("amount", 0))) * 100),  # cents
                    "currency": invoice.currency.lower(),
                    "quantity": item.get("quantity", 1),
                })

        return {
            "object": "invoice",
            "id": invoice.stripe_invoice_id or f"inv_{invoice.id}",
            "customer": customer_id,
            "number": invoice.invoice_number,
            "status": invoice.status.value,
            "subtotal": int(invoice.subtotal * 100),  # cents
            "tax": int(invoice.tax_amount * 100),  # cents
            "total": int(invoice.total * 100),  # cents
            "currency": invoice.currency.lower(),
            "due_date": int(invoice.due_date.timestamp()) if invoice.due_date else None,
            "lines": {
                "object": "list",
                "data": line_items,
            },
            "metadata": {
                "internal_invoice_id": str(invoice.id),
            },
        }

    @staticmethod
    async def generate_stripe_checkout_session(
        db: AsyncSession,
        company_id: int,
        plan_id: int,
        billing_cycle: BillingCycle,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """Generate a Stripe-compatible checkout session object.

        This creates the structure needed for a Stripe Checkout Session.
        When Stripe integration is added, this structure can be passed
        directly to Stripe's API.

        Args:
            db: Async database session.
            company_id: Company ID.
            plan_id: Plan ID.
            billing_cycle: Billing cycle.
            success_url: Redirect URL on success.
            cancel_url: Redirect URL on cancel.

        Returns:
            Stripe checkout session object structure.
        """
        plan = await PlanService.get_plan(db, plan_id)
        price = (
            plan.price_monthly
            if billing_cycle == BillingCycle.MONTHLY
            else plan.price_yearly
        )

        return {
            "object": "checkout.session",
            "id": f"cs_{uuid.uuid4().hex[:24]}",
            "mode": "subscription",
            "client_reference_id": str(company_id),
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items": [
                {
                    "price_data": {
                        "currency": plan.currency.lower(),
                        "product_data": {
                            "name": plan.name,
                            "description": plan.description,
                        },
                        "unit_amount": int(price * 100),  # cents
                        "recurring": {
                            "interval": (
                                "month"
                                if billing_cycle == BillingCycle.MONTHLY
                                else "year"
                            ),
                        },
                    },
                    "quantity": 1,
                }
            ],
            "subscription_data": {
                "metadata": {
                    "company_id": str(company_id),
                    "plan_id": str(plan_id),
                },
                "trial_period_days": TRIAL_DURATION_DAYS,
            },
            "metadata": {
                "company_id": str(company_id),
                "plan_id": str(plan_id),
                "billing_cycle": billing_cycle.value,
            },
        }

    @staticmethod
    async def preview_invoice(
        db: AsyncSession,
        company_id: int,
    ) -> Dict[str, Any]:
        """Preview the next invoice for a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            Invoice preview dictionary.
        """
        subscription = await SubscriptionService.get_subscription(db, company_id)
        if subscription is None:
            return {"error": "No active subscription"}

        plan = await PlanService.get_plan(db, subscription.plan_id)
        unit_price = (
            plan.price_monthly
            if subscription.billing_cycle == BillingCycle.MONTHLY
            else plan.price_yearly
        )

        tax = (unit_price * STRIPE_TAX_RATE_PERCENT / 100).quantize(Decimal("0.01"))
        total = unit_price + tax

        return {
            "company_id": company_id,
            "plan_name": plan.name,
            "billing_cycle": subscription.billing_cycle.value,
            "period_start": subscription.current_period_start.isoformat(),
            "period_end": subscription.current_period_end.isoformat(),
            "line_items": [
                {
                    "description": f"{plan.name} Plan - {subscription.billing_cycle.value.title()}",
                    "quantity": 1,
                    "unit_price": str(unit_price),
                    "amount": str(unit_price),
                }
            ],
            "subtotal": str(unit_price),
            "tax_rate": str(STRIPE_TAX_RATE_PERCENT),
            "tax_amount": str(tax),
            "total": str(total),
            "currency": plan.currency,
            "due_date": (_now() + timedelta(days=INVOICE_DUE_DAYS)).isoformat(),
        }


# ============================================================================
# ApprovalService (AI Approval Center)
# ============================================================================


class ApprovalService:
    """Service for managing AI Approval Center workflow requests.

    Handles the full approval lifecycle: create, list, approve, reject,
    edit-and-approve. Provides audit trail for all approval actions.
    """

    @staticmethod
    async def get_request(db: AsyncSession, request_id: int) -> ApprovalRequest:
        """Get an approval request by ID.

        Args:
            db: Async database session.
            request_id: Approval request ID.

        Returns:
            ApprovalRequest instance.

        Raises:
            NotFoundError: If request does not exist.
        """
        result = await db.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        )
        req = result.scalar_one_or_none()
        if req is None:
            raise NotFoundError(
                detail=f"Approval request with ID {request_id} not found"
            )
        return req

    @staticmethod
    async def create_request(
        db: AsyncSession,
        data: ApprovalRequestCreate,
    ) -> ApprovalRequest:
        """Create a new approval request.

        Args:
            db: Async database session.
            data: Approval request creation data.

        Returns:
            Created ApprovalRequest instance.
        """
        from app.billing.constants import RequestType

        request_type_value = (
            data.request_type.value
            if hasattr(data.request_type, "value")
            else str(data.request_type)
        )

        req = ApprovalRequest(
            company_id=data.company_id,
            request_type=request_type_value,
            requested_by=data.requested_by,
            request_data=data.request_data,
            status="pending",
            reason=data.reason,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)

        # Log the event
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=data.company_id,
                event_type=BillingEventType.USAGE_THRESHOLD,
                description=f"Approval request created: {request_type_value}",
                metadata={
                    "request_id": req.id,
                    "request_type": request_type_value,
                    "requested_by": data.requested_by,
                    "status": "pending",
                },
            ),
        )

        return req

    @staticmethod
    async def list_pending(
        db: AsyncSession,
        company_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """List pending approval requests for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List of pending ApprovalRequest instances.
        """
        result = await db.execute(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.company_id == company_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(desc(ApprovalRequest.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_all(
        db: AsyncSession,
        company_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """List all approval requests for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            status: Optional status filter.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List of ApprovalRequest instances.
        """
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.company_id == company_id)
            .order_by(desc(ApprovalRequest.created_at))
            .limit(limit)
            .offset(offset)
        )

        if status:
            stmt = stmt.where(ApprovalRequest.status == status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def approve(
        db: AsyncSession,
        request_id: int,
        approved_by: int,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Approve an approval request.

        Args:
            db: Async database session.
            request_id: Request ID to approve.
            approved_by: User ID who approved.
            reason: Optional approval reason.

        Returns:
            Updated ApprovalRequest instance.

        Raises:
            ValidationError: If request is not pending.
        """
        req = await ApprovalService.get_request(db, request_id)

        if req.status != "pending":
            raise ValidationError(
                detail=f"Cannot approve request with status '{req.status}'. "
                "Only pending requests can be approved."
            )

        req.status = "approved"
        req.approved_by = approved_by
        req.approved_at = _now()
        req.reason = reason or req.reason
        req.updated_at = _now()

        await db.commit()
        await db.refresh(req)

        # Log the event
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=req.company_id,
                event_type=BillingEventType.PAYMENT_SUCCEEDED,
                description=f"Approval request #{request_id} approved",
                metadata={
                    "request_id": request_id,
                    "request_type": req.request_type,
                    "approved_by": approved_by,
                    "reason": reason,
                    "previous_status": "pending",
                },
            ),
        )

        return req

    @staticmethod
    async def reject(
        db: AsyncSession,
        request_id: int,
        approved_by: int,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Reject an approval request.

        Args:
            db: Async database session.
            request_id: Request ID to reject.
            approved_by: User ID who rejected.
            reason: Rejection reason (required for audit).

        Returns:
            Updated ApprovalRequest instance.

        Raises:
            ValidationError: If request is not pending.
        """
        req = await ApprovalService.get_request(db, request_id)

        if req.status != "pending":
            raise ValidationError(
                detail=f"Cannot reject request with status '{req.status}'. "
                "Only pending requests can be rejected."
            )

        req.status = "rejected"
        req.approved_by = approved_by
        req.approved_at = _now()
        req.reason = reason or req.reason
        req.updated_at = _now()

        await db.commit()
        await db.refresh(req)

        # Log the event
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=req.company_id,
                event_type=BillingEventType.PAYMENT_FAILED,
                description=f"Approval request #{request_id} rejected",
                metadata={
                    "request_id": request_id,
                    "request_type": req.request_type,
                    "rejected_by": approved_by,
                    "reason": reason,
                    "previous_status": "pending",
                },
            ),
        )

        return req

    @staticmethod
    async def edit_and_approve(
        db: AsyncSession,
        request_id: int,
        approved_by: int,
        edited_data: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Edit an approval request and then approve it.

        This is the "edit then approve" flow where the approver modifies
        the request data before approving.

        Args:
            db: Async database session.
            request_id: Request ID to edit and approve.
            approved_by: User ID who edited and approved.
            edited_data: Modified request data.
            reason: Optional reason for edits.

        Returns:
            Updated ApprovalRequest instance.

        Raises:
            ValidationError: If request is not pending.
        """
        req = await ApprovalService.get_request(db, request_id)

        if req.status != "pending":
            raise ValidationError(
                detail=f"Cannot edit-and-approve request with status '{req.status}'. "
                "Only pending requests can be edited and approved."
            )

        # Store original data in metadata
        original_data = dict(req.request_data)

        req.status = "edited"
        req.approved_by = approved_by
        req.approved_at = _now()
        req.edited_data = edited_data
        req.reason = reason or req.reason
        req.updated_at = _now()

        await db.commit()
        await db.refresh(req)

        # Log the event
        await BillingEventService.create_event(
            db,
            BillingEventCreate(
                company_id=req.company_id,
                event_type=BillingEventType.PAYMENT_SUCCEEDED,
                description=f"Approval request #{request_id} edited and approved",
                metadata={
                    "request_id": request_id,
                    "request_type": req.request_type,
                    "approved_by": approved_by,
                    "reason": reason,
                    "previous_status": "pending",
                    "original_data": original_data,
                    "edited_data": edited_data,
                },
            ),
        )

        return req

    @staticmethod
    async def get_stats(db: AsyncSession, company_id: int) -> Dict[str, Any]:
        """Get approval statistics for a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            Dictionary of approval statistics.
        """
        from sqlalchemy import func

        result = await db.execute(
            select(
                ApprovalRequest.status,
                func.count().label("count"),
            )
            .where(ApprovalRequest.company_id == company_id)
            .group_by(ApprovalRequest.status)
        )
        status_counts = {row.status: row.count for row in result.all()}

        result = await db.execute(
            select(
                ApprovalRequest.request_type,
                func.count().label("count"),
            )
            .where(ApprovalRequest.company_id == company_id)
            .group_by(ApprovalRequest.request_type)
        )
        by_type = {row.request_type: row.count for row in result.all()}

        total = sum(status_counts.values())

        return {
            "total": total,
            "pending": status_counts.get("pending", 0),
            "approved": status_counts.get("approved", 0),
            "rejected": status_counts.get("rejected", 0),
            "edited": status_counts.get("edited", 0),
            "by_type": by_type,
        }

    @staticmethod
    def to_response(req: ApprovalRequest) -> ApprovalRequestResponse:
        """Convert an ApprovalRequest model to a response schema.

        Args:
            req: ApprovalRequest instance.

        Returns:
            ApprovalRequestResponse schema.
        """
        return ApprovalRequestResponse(
            id=req.id,
            company_id=req.company_id,
            request_type=req.request_type,
            requested_by=req.requested_by,
            request_data=req.request_data or {},
            status=req.status,
            approved_by=req.approved_by,
            approved_at=req.approved_at,
            reason=req.reason,
            edited_data=req.edited_data,
            created_at=req.created_at,
            updated_at=req.updated_at,
        )
