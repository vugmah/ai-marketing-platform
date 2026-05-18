"""Billing and SaaS subscription database models.

Contains all billing-related tables: subscription plans, company subscriptions,
usage records, usage quotas, invoices, feature flags, and billing events.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle statuses."""

    TRIAL = "trial"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    EXPIRED = "expired"


class BillingCycle(str, enum.Enum):
    """Supported billing cycle intervals."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


class ResourceType(str, enum.Enum):
    """Types of billable resources tracked in usage records."""

    AI_REQUEST = "ai_request"
    SOCIAL_POST = "social_post"
    STORAGE = "storage"
    API_CALL = "api_call"
    SMS = "sms"
    EMAIL = "email"


class QuotaPeriod(str, enum.Enum):
    """Quota reset periods."""

    DAILY = "daily"
    MONTHLY = "monthly"


class InvoiceStatus(str, enum.Enum):
    """Invoice lifecycle statuses."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


class FeatureName(str, enum.Enum):
    """Named features that can be enabled/disabled per company."""

    AI_CONTENT = "ai_content"
    SOCIAL_API = "social_api"
    WEBHOOK = "webhook"
    AUTOMATION = "automation"
    ADVANCED_ANALYTICS = "advanced_analytics"
    ERP_INTEGRATION = "erp_integration"
    MULTI_BRANCH = "multi_branch"
    CUSTOM_BRANDING = "custom_branding"
    PRIORITY_SUPPORT = "priority_support"
    API_ACCESS = "api_access"


class ApprovalStatus(str, enum.Enum):
    """Approval request lifecycle statuses."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class RequestType(str, enum.Enum):
    """Types of approval requests in the AI Approval Center."""

    AI_SUGGESTION = "ai_suggestion"
    CAMPAIGN_CHANGE = "campaign_change"
    BUDGET_CHANGE = "budget_change"
    CONTENT_PUBLISH = "content_publish"
    AUTOMATION_RULE = "automation_rule"
    WEBHOOK_CONFIG = "webhook_config"


class BillingEventType(str, enum.Enum):
    """Types of billing events logged in the system."""

    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_UPGRADED = "subscription_upgraded"
    SUBSCRIPTION_DOWNGRADED = "subscription_downgraded"
    USAGE_THRESHOLD = "usage_threshold"
    QUOTA_EXCEEDED = "quota_exceeded"
    QUOTA_WARNING = "quota_warning"
    INVOICE_GENERATED = "invoice_generated"
    INVOICE_PAID = "invoice_paid"
    INVOICE_OVERDUE = "invoice_overdue"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    FEATURE_ENABLED = "feature_enabled"
    FEATURE_DISABLED = "feature_disabled"


# ---------------------------------------------------------------------------
# 1. Subscription Plans
# ---------------------------------------------------------------------------

class SubscriptionPlan(Base):
    """
    Available subscription plans/tiers in the system.

    Defines pricing, feature sets, and usage limits for each plan.
    Stripe price IDs can be stored for future integration.
    """

    __tablename__ = "subscription_plans"
    __table_args__ = {
        "schema": None,
        "comment": "Available subscription plan tiers with pricing and limits",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    price_monthly = Column(Numeric(10, 2), nullable=False, default=0.00)
    price_yearly = Column(Numeric(10, 2), nullable=False, default=0.00)
    currency = Column(String(3), nullable=False, default="USD")
    features = Column(JSON, nullable=False, default=dict)
    limits = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    stripe_price_id = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    subscriptions = relationship(
        "CompanySubscription",
        back_populates="plan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan(id={self.id}, name='{self.name}', active={self.is_active})>"


# ---------------------------------------------------------------------------
# 2. Company Subscriptions
# ---------------------------------------------------------------------------

class CompanySubscription(Base):
    """
    Company subscription record linking a company to a plan.

    Tracks the full lifecycle of a subscription including trial periods,
    billing cycles, renewal dates, and cancellation.
    """

    __tablename__ = "company_subscriptions"
    __table_args__ = {
        "schema": None,
        "comment": "Company subscription records with lifecycle tracking",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_company_subscriptions_company_id",
        ),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        Integer,
        ForeignKey(
            "subscription_plans.id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="fk_company_subscriptions_plan_id",
        ),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(SubscriptionStatus, name="substatus", create_type=True),
        default=SubscriptionStatus.TRIAL,
        nullable=False,
        index=True,
    )
    billing_cycle = Column(
        Enum(BillingCycle, name="billingcycle", create_type=True),
        default=BillingCycle.MONTHLY,
        nullable=False,
    )
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    trial_ends_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    payment_method_id = Column(String(255), nullable=True)
    auto_renew = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

    def __repr__(self) -> str:
        return (
            f"<CompanySubscription(id={self.id}, company_id={self.company_id}, "
            f"plan_id={self.plan_id}, status='{self.status.value}')>"
        )


# ---------------------------------------------------------------------------
# 3. Usage Records
# ---------------------------------------------------------------------------

class UsageRecord(Base):
    """
    Individual usage record for tracking resource consumption.

    Each record represents a single usage event (e.g., one AI request,
    one social post, one API call) with quantity and cost tracking.
    """

    __tablename__ = "usage_records"
    __table_args__ = {
        "schema": None,
        "comment": "Resource usage records for billing and analytics",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_usage_records_company_id",
        ),
        nullable=False,
        index=True,
    )
    resource_type = Column(
        Enum(ResourceType, name="usageresourcetype", create_type=True),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False, default=1)
    unit = Column(String(50), nullable=False)
    cost = Column(Numeric(10, 4), nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    recorded_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<UsageRecord(id={self.id}, company_id={self.company_id}, "
            f"resource='{self.resource_type.value}', quantity={self.quantity})>"
        )


# ---------------------------------------------------------------------------
# 4. Usage Quotas
# ---------------------------------------------------------------------------

class UsageQuota(Base):
    """
    Per-company resource quotas with current usage tracking.

    Tracks how much of each resource a company has used against
    their plan limits, with automatic reset tracking.
    """

    __tablename__ = "usage_quotas"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "resource_type",
            "period",
            name="uq_usage_quotas_company_resource_period",
        ),
        {
            "schema": None,
            "comment": "Per-company resource usage quotas and current consumption",
        },
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_usage_quotas_company_id",
        ),
        nullable=False,
        index=True,
    )
    resource_type = Column(
        Enum(ResourceType, name="quotaresourcetype", create_type=True),
        nullable=False,
        index=True,
    )
    limit_amount = Column(Integer, nullable=False)
    current_usage = Column(Integer, default=0, nullable=False)
    period = Column(
        Enum(QuotaPeriod, name="quotaperiod", create_type=True),
        default=QuotaPeriod.MONTHLY,
        nullable=False,
    )
    reset_at = Column(DateTime, nullable=False)
    warning_sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<UsageQuota(id={self.id}, company_id={self.company_id}, "
            f"resource='{self.resource_type.value}', "
            f"usage={self.current_usage}/{self.limit_amount})>"
        )


# ---------------------------------------------------------------------------
# 5. Invoices
# ---------------------------------------------------------------------------

class Invoice(Base):
    """
    Invoice record for billing customers.

    Contains line items, totals, payment tracking, and Stripe invoice
    ID for future payment integration.
    """

    __tablename__ = "invoices"
    __table_args__ = {
        "schema": None,
        "comment": "Customer invoices with line items and payment tracking",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_invoices_company_id",
        ),
        nullable=False,
        index=True,
    )
    invoice_number = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(InvoiceStatus, name="invoicestatus", create_type=True),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )
    subtotal = Column(Numeric(12, 2), nullable=False, default=0.00)
    tax_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    total = Column(Numeric(12, 2), nullable=False, default=0.00)
    currency = Column(String(3), nullable=False, default="USD")
    due_date = Column(DateTime, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    stripe_invoice_id = Column(String(255), nullable=True)
    line_items = Column(JSON, nullable=False, default=list)
    meta = Column('metadata', JSON, nullable=True)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, number='{self.invoice_number}', "
            f"status='{self.status.value}', total={self.total})>"
        )


# ---------------------------------------------------------------------------
# 6. Feature Flags
# ---------------------------------------------------------------------------

class FeatureFlag(Base):
    """
    Per-company feature enablement flags.

    Controls which features are available to each company.
    Features can be enabled by plan defaults or manually toggled
    by super admins for custom access.
    """

    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "feature_name",
            name="uq_feature_flags_company_feature",
        ),
        {
            "schema": None,
            "comment": "Per-company feature enablement flags",
        },
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_feature_flags_company_id",
        ),
        nullable=False,
        index=True,
    )
    feature_name = Column(
        Enum(FeatureName, name="featurename", create_type=True),
        nullable=False,
        index=True,
    )
    enabled = Column(Boolean, default=False, nullable=False)
    enabled_by = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_feature_flags_enabled_by",
        ),
        nullable=True,
    )
    enabled_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<FeatureFlag(id={self.id}, company_id={self.company_id}, "
            f"feature='{self.feature_name.value}', enabled={self.enabled})>"
        )


# ---------------------------------------------------------------------------
# 7. Billing Events
# ---------------------------------------------------------------------------

class BillingEvent(Base):
    """
    Audit log of billing-related events.

    Records all significant billing events for compliance,
    debugging, and analytics purposes.
    """

    __tablename__ = "billing_events"
    __table_args__ = {
        "schema": None,
        "comment": "Billing event audit log",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_billing_events_company_id",
        ),
        nullable=False,
        index=True,
    )
    event_type = Column(
        Enum(BillingEventType, name="billingeventtype", create_type=True),
        nullable=False,
        index=True,
    )
    description = Column(Text, nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<BillingEvent(id={self.id}, company_id={self.company_id}, "
            f"type='{self.event_type.value}')>"
        )


# ---------------------------------------------------------------------------
# 8. Approval Requests
# ---------------------------------------------------------------------------

class ApprovalRequest(Base):
    """
    AI Approval Center request model.

    Tracks approval workflow for AI suggestions, campaign changes,
    budget changes, and other actions requiring human review.
    Supports approve, reject, and edit-then-approve flows.
    """

    __tablename__ = "approval_requests"
    __table_args__ = (
        {
            "schema": None,
            "comment": "AI Approval Center workflow requests",
        },
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_approval_requests_company_id",
        ),
        nullable=False,
        index=True,
    )
    request_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="ai_suggestion, campaign_change, budget_change, etc.",
    )
    requested_by = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_approval_requests_requested_by",
        ),
        nullable=True,
        index=True,
    )
    request_data = Column(JSON, nullable=False, default=dict)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, approved, rejected, edited",
    )
    approved_by = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_approval_requests_approved_by",
        ),
        nullable=True,
        index=True,
    )
    approved_at = Column(DateTime, nullable=True)
    reason = Column(String(500), nullable=True)
    edited_data = Column(JSON, nullable=True)
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalRequest(id={self.id}, company_id={self.company_id}, "
            f"type='{self.request_type}', status='{self.status}')>"
        )
