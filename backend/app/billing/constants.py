"""Billing constants, plan definitions, and configuration defaults.

This module contains all billing-related constants including plan definitions
with their default limits, resource types, quota thresholds, grace period settings,
and feature flag defaults per plan tier.
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List


class PlanTier(str, Enum):
    """Subscription plan tiers available in the system."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle statuses."""

    TRIAL = "trial"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    EXPIRED = "expired"


class BillingCycle(str, Enum):
    """Supported billing cycle intervals."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


class ResourceType(str, Enum):
    """Types of billable resources tracked in usage records."""

    AI_REQUEST = "ai_request"
    SOCIAL_POST = "social_post"
    STORAGE = "storage"
    API_CALL = "api_call"
    SMS = "sms"
    EMAIL = "email"


class InvoiceStatus(str, Enum):
    """Invoice lifecycle statuses."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


class FeatureName(str, Enum):
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


class BillingEventType(str, Enum):
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


class ApprovalStatus(str, Enum):
    """Approval request lifecycle statuses."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class RequestType(str, Enum):
    """Types of approval requests in the AI Approval Center."""

    AI_SUGGESTION = "ai_suggestion"
    CAMPAIGN_CHANGE = "campaign_change"
    BUDGET_CHANGE = "budget_change"
    CONTENT_PUBLISH = "content_publish"
    AUTOMATION_RULE = "automation_rule"
    WEBHOOK_CONFIG = "webhook_config"


class QuotaPeriod(str, Enum):
    """Quota reset periods."""

    DAILY = "daily"
    MONTHLY = "monthly"


# ---------------------------------------------------------------------------
# Quota warning thresholds (% of limit)
# ---------------------------------------------------------------------------

QUOTA_WARNING_THRESHOLD: int = 80
QUOTA_CRITICAL_THRESHOLD: int = 95
QUOTA_EXCEEDED_THRESHOLD: int = 100

# ---------------------------------------------------------------------------
# Grace period settings (days)
# ---------------------------------------------------------------------------

GRACE_PERIOD_DAYS: int = 3
PAST_DUE_GRACE_PERIOD_DAYS: int = 7
TRIAL_DURATION_DAYS: int = 14

# ---------------------------------------------------------------------------
# Default currency
# ---------------------------------------------------------------------------

DEFAULT_CURRENCY: str = "USD"
SUPPORTED_CURRENCIES: List[str] = ["USD", "EUR", "AZN"]

# ---------------------------------------------------------------------------
# Plan definitions with default limits
# ---------------------------------------------------------------------------

PLAN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    PlanTier.FREE.value: {
        "name": "Free",
        "description": "Perfect for individuals and small trials. Limited features but enough to get started.",
        "price_monthly": Decimal("0.00"),
        "price_yearly": Decimal("0.00"),
        "currency": DEFAULT_CURRENCY,
        "sort_order": 1,
        "is_active": True,
        "limits": {
            "max_branches": 1,
            "max_users": 1,
            "max_ai_requests": 50,
            "max_posts": 10,
            "storage_gb": 1,
            "max_api_calls": 100,
            "max_sms": 0,
            "max_email": 50,
        },
        "features": {
            "ai_content": True,
            "social_api": False,
            "webhook": False,
            "automation": False,
            "advanced_analytics": False,
            "erp_integration": False,
            "multi_branch": False,
            "custom_branding": False,
            "priority_support": False,
            "api_access": False,
        },
    },
    PlanTier.STARTER.value: {
        "name": "Starter",
        "description": "Ideal for small businesses with one or two locations starting their digital marketing journey.",
        "price_monthly": Decimal("29.00"),
        "price_yearly": Decimal("290.00"),
        "currency": DEFAULT_CURRENCY,
        "sort_order": 2,
        "is_active": True,
        "limits": {
            "max_branches": 2,
            "max_users": 3,
            "max_ai_requests": 500,
            "max_posts": 100,
            "storage_gb": 5,
            "max_api_calls": 1000,
            "max_sms": 100,
            "max_email": 500,
        },
        "features": {
            "ai_content": True,
            "social_api": True,
            "webhook": False,
            "automation": False,
            "advanced_analytics": False,
            "erp_integration": False,
            "multi_branch": True,
            "custom_branding": False,
            "priority_support": False,
            "api_access": False,
        },
    },
    PlanTier.PRO.value: {
        "name": "Pro",
        "description": "For growing businesses that need advanced AI features, automation, and multi-location support.",
        "price_monthly": Decimal("99.00"),
        "price_yearly": Decimal("990.00"),
        "currency": DEFAULT_CURRENCY,
        "sort_order": 3,
        "is_active": True,
        "limits": {
            "max_branches": 10,
            "max_users": 15,
            "max_ai_requests": 5000,
            "max_posts": 1000,
            "storage_gb": 25,
            "max_api_calls": 10000,
            "max_sms": 1000,
            "max_email": 5000,
        },
        "features": {
            "ai_content": True,
            "social_api": True,
            "webhook": True,
            "automation": True,
            "advanced_analytics": True,
            "erp_integration": True,
            "multi_branch": True,
            "custom_branding": True,
            "priority_support": False,
            "api_access": True,
        },
    },
    PlanTier.ENTERPRISE.value: {
        "name": "Enterprise",
        "description": "Full-featured plan for large organizations with custom needs, dedicated support, and unlimited usage.",
        "price_monthly": Decimal("299.00"),
        "price_yearly": Decimal("2990.00"),
        "currency": DEFAULT_CURRENCY,
        "sort_order": 4,
        "is_active": True,
        "limits": {
            "max_branches": -1,  # unlimited
            "max_users": -1,  # unlimited
            "max_ai_requests": -1,  # unlimited
            "max_posts": -1,  # unlimited
            "storage_gb": 100,
            "max_api_calls": -1,  # unlimited
            "max_sms": -1,  # unlimited
            "max_email": -1,  # unlimited
        },
        "features": {
            "ai_content": True,
            "social_api": True,
            "webhook": True,
            "automation": True,
            "advanced_analytics": True,
            "erp_integration": True,
            "multi_branch": True,
            "custom_branding": True,
            "priority_support": True,
            "api_access": True,
        },
    },
}

# ---------------------------------------------------------------------------
# Feature flag defaults (used when no plan-based override exists)
# ---------------------------------------------------------------------------

FEATURE_FLAG_DEFAULTS: Dict[str, bool] = {
    FeatureName.AI_CONTENT.value: False,
    FeatureName.SOCIAL_API.value: False,
    FeatureName.WEBHOOK.value: False,
    FeatureName.AUTOMATION.value: False,
    FeatureName.ADVANCED_ANALYTICS.value: False,
    FeatureName.ERP_INTEGRATION.value: False,
    FeatureName.MULTI_BRANCH.value: False,
    FeatureName.CUSTOM_BRANDING.value: False,
    FeatureName.PRIORITY_SUPPORT.value: False,
    FeatureName.API_ACCESS.value: False,
}

# ---------------------------------------------------------------------------
# Resource unit mapping
# ---------------------------------------------------------------------------

RESOURCE_UNITS: Dict[str, str] = {
    ResourceType.AI_REQUEST.value: "request",
    ResourceType.SOCIAL_POST.value: "post",
    ResourceType.STORAGE.value: "gb",
    ResourceType.API_CALL.value: "call",
    ResourceType.SMS.value: "message",
    ResourceType.EMAIL.value: "message",
}

# ---------------------------------------------------------------------------
# Default cost per unit (for internal cost tracking, not customer pricing)
# ---------------------------------------------------------------------------

DEFAULT_COST_PER_UNIT: Dict[str, Decimal] = {
    ResourceType.AI_REQUEST.value: Decimal("0.01"),
    ResourceType.SOCIAL_POST.value: Decimal("0.05"),
    ResourceType.STORAGE.value: Decimal("0.10"),  # per GB per month
    ResourceType.API_CALL.value: Decimal("0.001"),
    ResourceType.SMS.value: Decimal("0.05"),
    ResourceType.EMAIL.value: Decimal("0.01"),
}

# ---------------------------------------------------------------------------
# Invoice settings
# ---------------------------------------------------------------------------

INVOICE_DUE_DAYS: int = 7
INVOICE_PREFIX: str = "INV"
INVOICE_NUMBER_PADDING: int = 6

# ---------------------------------------------------------------------------
# Stripe-ready constants (for future integration)
# ---------------------------------------------------------------------------

STRIPE_TAX_RATE_PERCENT: Decimal = Decimal("18.00")  # VAT/GST rate
STRIPE_CURRENCY: str = "usd"

# Plan to Stripe Price ID mapping (populated when Stripe products are created)
STRIPE_PRICE_IDS: Dict[str, Dict[str, str]] = {
    PlanTier.STARTER.value: {
        BillingCycle.MONTHLY.value: "",
        BillingCycle.YEARLY.value: "",
    },
    PlanTier.PRO.value: {
        BillingCycle.MONTHLY.value: "",
        BillingCycle.YEARLY.value: "",
    },
    PlanTier.ENTERPRISE.value: {
        BillingCycle.MONTHLY.value: "",
        BillingCycle.YEARLY.value: "",
    },
}
