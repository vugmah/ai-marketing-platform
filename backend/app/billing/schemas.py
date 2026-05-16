"""Billing Pydantic v2 schemas for request and response validation.

Provides comprehensive schemas for subscription plans, company subscriptions,
usage records, quotas, invoices, feature flags, and billing events.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.billing.constants import (
    ApprovalStatus,
    BillingCycle,
    BillingEventType,
    FeatureName,
    InvoiceStatus,
    QuotaPeriod,
    RequestType,
    ResourceType,
    SubscriptionStatus,
)


# =============================================================================
# Subscription Plan Schemas
# =============================================================================


class PlanBase(BaseModel):
    """Base schema for subscription plan data."""

    name: str = Field(..., min_length=1, max_length=50, description="Plan name")
    description: Optional[str] = Field(default=None, description="Plan description")
    price_monthly: Decimal = Field(..., ge=0, description="Monthly price")
    price_yearly: Decimal = Field(..., ge=0, description="Yearly price")
    currency: str = Field(default="USD", max_length=3, description="Currency code")
    features: Dict[str, Any] = Field(default_factory=dict, description="Feature flags")
    limits: Dict[str, Any] = Field(default_factory=dict, description="Usage limits")
    is_active: bool = Field(default=True, description="Whether plan is available")
    stripe_price_id: Optional[str] = Field(default=None, description="Stripe price ID")
    sort_order: int = Field(default=0, ge=0, description="Display sort order")


class PlanCreate(PlanBase):
    """Schema for creating a new subscription plan."""

    pass


class PlanUpdate(BaseModel):
    """Schema for updating an existing subscription plan."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = Field(default=None)
    price_monthly: Optional[Decimal] = Field(default=None, ge=0)
    price_yearly: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=3)
    features: Optional[Dict[str, Any]] = Field(default=None)
    limits: Optional[Dict[str, Any]] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    stripe_price_id: Optional[str] = Field(default=None)
    sort_order: Optional[int] = Field(default=None, ge=0)


class PlanResponse(PlanBase):
    """Schema for subscription plan response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Plan ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PlanListResponse(BaseModel):
    """Schema for listing subscription plans."""

    items: List[PlanResponse] = Field(..., description="List of plans")
    total: int = Field(..., description="Total number of plans")


# =============================================================================
# Company Subscription Schemas
# =============================================================================


class SubscriptionBase(BaseModel):
    """Base schema for company subscription data."""

    plan_id: int = Field(..., ge=1, description="Subscription plan ID")
    billing_cycle: BillingCycle = Field(
        default=BillingCycle.MONTHLY, description="Billing cycle"
    )
    auto_renew: bool = Field(default=True, description="Auto-renew subscription")


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a new subscription."""

    company_id: int = Field(..., ge=1, description="Company ID")
    trial_days: Optional[int] = Field(default=14, ge=0, le=30, description="Trial duration")


class SubscribeRequest(BaseModel):
    """Schema for subscribe endpoint request."""

    plan_id: int = Field(..., ge=1, description="Plan ID to subscribe to")
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)
    auto_renew: bool = Field(default=True)


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription (plan change)."""

    plan_id: int = Field(..., ge=1, description="New plan ID")
    billing_cycle: Optional[BillingCycle] = Field(default=None)
    auto_renew: Optional[bool] = Field(default=None)


class SubscriptionCancelRequest(BaseModel):
    """Schema for subscription cancellation request."""

    reason: Optional[str] = Field(default=None, description="Cancellation reason")
    immediate: bool = Field(default=False, description="Cancel immediately vs end of period")


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Subscription ID")
    company_id: int = Field(..., description="Company ID")
    plan_id: int = Field(..., description="Plan ID")
    plan_name: str = Field(..., description="Plan name")
    status: SubscriptionStatus = Field(..., description="Subscription status")
    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    started_at: datetime = Field(..., description="Subscription start date")
    current_period_start: datetime = Field(..., description="Current period start")
    current_period_end: datetime = Field(..., description="Current period end")
    trial_ends_at: Optional[datetime] = Field(default=None, description="Trial end date")
    cancelled_at: Optional[datetime] = Field(default=None, description="Cancellation date")
    cancellation_reason: Optional[str] = Field(default=None, description="Cancellation reason")
    auto_renew: bool = Field(..., description="Auto-renew enabled")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# =============================================================================
# Usage Record Schemas
# =============================================================================


class UsageRecordBase(BaseModel):
    """Base schema for usage record data."""

    resource_type: ResourceType = Field(..., description="Type of resource used")
    quantity: int = Field(default=1, ge=1, description="Amount consumed")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    cost: Optional[Decimal] = Field(default=None, ge=0, description="Cost of usage")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class UsageRecordCreate(UsageRecordBase):
    """Schema for creating a usage record (internal)."""

    company_id: int = Field(..., ge=1, description="Company ID")

    @field_validator("unit")
    @classmethod
    def set_default_unit(cls, v: Optional[str], info) -> str:
        """Set default unit based on resource type."""
        if v:
            return v
        resource_type = info.data.get("resource_type")
        unit_map = {
            ResourceType.AI_REQUEST: "request",
            ResourceType.SOCIAL_POST: "post",
            ResourceType.STORAGE: "gb",
            ResourceType.API_CALL: "call",
            ResourceType.SMS: "message",
            ResourceType.EMAIL: "message",
        }
        return unit_map.get(resource_type, "unit")


class UsageTrackRequest(BaseModel):
    """Schema for tracking usage via API endpoint."""

    resource_type: ResourceType = Field(..., description="Type of resource used")
    quantity: int = Field(default=1, ge=1, description="Amount consumed")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class UsageRecordResponse(UsageRecordBase):
    """Schema for usage record response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Record ID")
    company_id: int = Field(..., description="Company ID")
    unit: str = Field(..., description="Unit of measurement")
    recorded_at: datetime = Field(..., description="Recording timestamp")


class UsageSummaryResponse(BaseModel):
    """Schema for usage summary analytics."""

    company_id: int = Field(..., description="Company ID")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    breakdown: Dict[str, Dict[str, Any]] = Field(
        ..., description="Usage by resource type"
    )
    total_cost: Decimal = Field(..., description="Total cost for period")


# =============================================================================
# Usage Quota Schemas
# =============================================================================


class QuotaBase(BaseModel):
    """Base schema for usage quota data."""

    resource_type: ResourceType = Field(..., description="Resource type")
    limit_amount: int = Field(..., ge=-1, description="Quota limit (-1 for unlimited)")
    period: QuotaPeriod = Field(default=QuotaPeriod.MONTHLY, description="Reset period")


class QuotaCreate(QuotaBase):
    """Schema for creating a usage quota."""

    company_id: int = Field(..., ge=1, description="Company ID")


class QuotaUpdate(BaseModel):
    """Schema for updating a usage quota."""

    limit_amount: Optional[int] = Field(default=None, ge=-1)
    current_usage: Optional[int] = Field(default=None, ge=0)
    period: Optional[QuotaPeriod] = Field(default=None)
    reset_at: Optional[datetime] = Field(default=None)
    warning_sent: Optional[bool] = Field(default=None)


class QuotaResponse(BaseModel):
    """Schema for quota response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Quota ID")
    company_id: int = Field(..., description="Company ID")
    resource_type: ResourceType = Field(..., description="Resource type")
    limit_amount: int = Field(..., description="Quota limit")
    current_usage: int = Field(..., description="Current usage")
    usage_percentage: float = Field(..., description="Usage as percentage")
    remaining: int = Field(..., description="Remaining quota")
    period: QuotaPeriod = Field(..., description="Reset period")
    reset_at: datetime = Field(..., description="Next reset time")
    warning_sent: bool = Field(..., description="Warning notification sent")
    is_unlimited: bool = Field(..., description="Whether quota is unlimited")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class QuotaCheckResponse(BaseModel):
    """Schema for quota check result."""

    allowed: bool = Field(..., description="Whether action is allowed")
    resource_type: ResourceType = Field(..., description="Resource type")
    current_usage: int = Field(..., description="Current usage")
    limit: int = Field(..., description="Quota limit")
    remaining: int = Field(..., description="Remaining quota")
    usage_percentage: float = Field(..., description="Usage percentage")
    would_exceed: bool = Field(..., description="Would this action exceed quota")
    reason: Optional[str] = Field(default=None, description="Reason if not allowed")


# =============================================================================
# Invoice Schemas
# =============================================================================


class InvoiceLineItem(BaseModel):
    """Schema for an invoice line item."""

    description: str = Field(..., description="Line item description")
    quantity: int = Field(default=1, ge=0, description="Quantity")
    unit_price: Decimal = Field(..., ge=0, description="Price per unit")
    amount: Decimal = Field(..., ge=0, description="Total amount")


class InvoiceBase(BaseModel):
    """Base schema for invoice data."""

    subtotal: Decimal = Field(..., ge=0, description="Subtotal before tax")
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Tax amount")
    total: Decimal = Field(..., ge=0, description="Total amount")
    currency: str = Field(default="USD", max_length=3, description="Currency code")
    due_date: datetime = Field(..., description="Payment due date")
    line_items: List[InvoiceLineItem] = Field(default_factory=list, description="Line items")


class InvoiceCreate(BaseModel):
    """Schema for creating an invoice."""

    company_id: int = Field(..., ge=1, description="Company ID")
    subtotal: Decimal = Field(..., ge=0, description="Subtotal before tax")
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Tax amount")
    total: Decimal = Field(..., ge=0, description="Total amount")
    currency: str = Field(default="USD", max_length=3)
    due_date: datetime = Field(..., description="Payment due date")
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice."""

    status: Optional[InvoiceStatus] = Field(default=None)
    subtotal: Optional[Decimal] = Field(default=None, ge=0)
    tax_amount: Optional[Decimal] = Field(default=None, ge=0)
    total: Optional[Decimal] = Field(default=None, ge=0)
    due_date: Optional[datetime] = Field(default=None)
    paid_at: Optional[datetime] = Field(default=None)
    line_items: Optional[List[InvoiceLineItem]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Invoice ID")
    company_id: int = Field(..., description="Company ID")
    invoice_number: str = Field(..., description="Invoice number")
    status: InvoiceStatus = Field(..., description="Invoice status")
    subtotal: Decimal = Field(..., description="Subtotal")
    tax_amount: Decimal = Field(..., description="Tax amount")
    total: Decimal = Field(..., description="Total amount")
    currency: str = Field(..., description="Currency code")
    due_date: datetime = Field(..., description="Due date")
    paid_at: Optional[datetime] = Field(default=None, description="Payment date")
    stripe_invoice_id: Optional[str] = Field(default=None, description="Stripe invoice ID")
    line_items: List[InvoiceLineItem] = Field(..., description="Line items")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class InvoiceListResponse(BaseModel):
    """Schema for listing invoices."""

    items: List[InvoiceResponse] = Field(..., description="List of invoices")
    total: int = Field(..., description="Total count")
    total_unpaid: Decimal = Field(default=Decimal("0.00"), description="Total unpaid amount")


# =============================================================================
# Feature Flag Schemas
# =============================================================================


class FeatureFlagBase(BaseModel):
    """Base schema for feature flag data."""

    feature_name: FeatureName = Field(..., description="Feature name")
    enabled: bool = Field(default=False, description="Whether feature is enabled")
    reason: Optional[str] = Field(default=None, description="Reason for enabling")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration date")


class FeatureFlagCreate(FeatureFlagBase):
    """Schema for creating a feature flag."""

    company_id: int = Field(..., ge=1, description="Company ID")
    enabled_by: Optional[int] = Field(default=None, description="User ID who enabled")


class FeatureFlagToggleRequest(BaseModel):
    """Schema for toggling a feature flag."""

    enabled: bool = Field(..., description="New enabled state")
    reason: Optional[str] = Field(default=None, description="Reason for toggle")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration")


class FeatureFlagResponse(FeatureFlagBase):
    """Schema for feature flag response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Flag ID")
    company_id: int = Field(..., description="Company ID")
    enabled_by: Optional[int] = Field(default=None, description="Enabled by user ID")
    enabled_at: Optional[datetime] = Field(default=None, description="Enabled timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class FeatureCheckResponse(BaseModel):
    """Schema for feature check result."""

    feature_name: FeatureName = Field(..., description="Feature name")
    enabled: bool = Field(..., description="Whether enabled")
    source: str = Field(..., description="Source of flag (plan/manual)")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration date")
    is_expired: bool = Field(default=False, description="Whether feature has expired")


# =============================================================================
# Billing Event Schemas
# =============================================================================


class BillingEventBase(BaseModel):
    """Base schema for billing event data."""

    event_type: BillingEventType = Field(..., description="Event type")
    description: Optional[str] = Field(default=None, description="Event description")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class BillingEventCreate(BillingEventBase):
    """Schema for creating a billing event."""

    company_id: int = Field(..., ge=1, description="Company ID")


class BillingEventResponse(BillingEventBase):
    """Schema for billing event response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Event ID")
    company_id: int = Field(..., description="Company ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class BillingEventListResponse(BaseModel):
    """Schema for listing billing events."""

    items: List[BillingEventResponse] = Field(..., description="List of events")
    total: int = Field(..., description="Total count")


# =============================================================================
# Billing Statistics Schemas
# =============================================================================


class BillingStatsResponse(BaseModel):
    """Schema for billing statistics (admin)."""

    total_companies: int = Field(..., description="Total companies")
    active_subscriptions: int = Field(..., description="Active subscriptions")
    trial_subscriptions: int = Field(..., description="Trial subscriptions")
    past_due_subscriptions: int = Field(..., description="Past due subscriptions")
    cancelled_subscriptions: int = Field(..., description="Cancelled subscriptions")
    total_mrr: Decimal = Field(..., description="Total monthly recurring revenue")
    total_outstanding: Decimal = Field(..., description="Total outstanding amount")
    revenue_by_plan: Dict[str, Decimal] = Field(..., description="Revenue per plan")
    recent_events: int = Field(..., description="Recent billing events count")


class CompanyBillingSummary(BaseModel):
    """Schema for company billing summary."""

    company_id: int = Field(..., description="Company ID")
    current_plan: str = Field(..., description="Current plan name")
    subscription_status: SubscriptionStatus = Field(..., description="Subscription status")
    billing_cycle: BillingCycle = Field(..., description="Billing cycle")
    current_period_end: datetime = Field(..., description="Period end date")
    is_trial: bool = Field(..., description="Whether in trial")
    days_remaining: int = Field(..., description="Days remaining in period")
    features: Dict[str, bool] = Field(..., description="Enabled features")
    quotas: Dict[str, Dict[str, Any]] = Field(..., description="Quota statuses")
    total_unpaid: Decimal = Field(..., description="Total unpaid invoices")


class UsageTimeseriesPoint(BaseModel):
    """Schema for a single daily usage data point."""

    date: str = Field(..., description="Date string (YYYY-MM-DD)")
    total_quantity: int = Field(default=0, description="Total quantity used")
    total_cost: Decimal = Field(default=Decimal("0.00"), description="Total cost")
    request_count: int = Field(default=0, description="Number of requests")
    by_resource: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Breakdown by resource type"
    )


class UsageTimeseriesResponse(BaseModel):
    """Schema for usage timeseries (dashboard line chart)."""

    company_id: int = Field(..., description="Company ID")
    days: int = Field(..., description="Number of days in the series")
    data: List[UsageTimeseriesPoint] = Field(..., description="Daily data points")


class ResourceBreakdownResponse(BaseModel):
    """Schema for resource usage breakdown (dashboard pie chart)."""

    company_id: int = Field(..., description="Company ID")
    breakdown: Dict[str, Dict[str, Any]] = Field(..., description="Usage by resource type")
    totals: Dict[str, Any] = Field(..., description="Aggregated totals")


class StripeStatusResponse(BaseModel):
    """Schema for Stripe configuration status."""

    enabled: bool = Field(..., description="Whether Stripe is configured")
    mode: str = Field(default="tracking-only", description="Billing mode")
    publishable_key_present: bool = Field(default=False, description="Stripe publishable key configured")


class AIUsageTrackRequest(BaseModel):
    """Schema for tracking AI usage internally."""

    model: str = Field(default="gpt-4", description="AI model used")
    tokens_used: int = Field(default=0, ge=0, description="Tokens consumed")
    prompt: Optional[str] = Field(default=None, description="Optional prompt reference")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


# =============================================================================
# Approval Workflow Schemas
# =============================================================================


class ApprovalRequestBase(BaseModel):
    """Base schema for approval request data."""

    request_type: RequestType = Field(..., description="Type of approval request")
    request_data: Dict[str, Any] = Field(default_factory=dict, description="Request payload")
    reason: Optional[str] = Field(default=None, description="Reason for request")


class ApprovalRequestCreate(ApprovalRequestBase):
    """Schema for creating an approval request."""

    company_id: int = Field(..., ge=1, description="Company ID")


class ApprovalRequestSubmit(BaseModel):
    """Schema for submitting a new approval request via API."""

    request_type: RequestType = Field(..., description="Type of approval request")
    request_data: Dict[str, Any] = Field(..., description="Request payload data")
    reason: Optional[str] = Field(default=None, description="Reason or context")


class ApprovalRequestResponse(BaseModel):
    """Schema for approval request response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Request ID")
    company_id: int = Field(..., description="Company ID")
    request_type: str = Field(..., description="Request type")
    requested_by: Optional[int] = Field(default=None, description="Requested by user ID")
    request_data: Dict[str, Any] = Field(..., description="Request payload")
    status: str = Field(..., description="Current status")
    approved_by: Optional[int] = Field(default=None, description="Approved by user ID")
    approved_at: Optional[datetime] = Field(default=None, description="Approval timestamp")
    reason: Optional[str] = Field(default=None, description="Reason for request")
    edited_data: Optional[Dict[str, Any]] = Field(default=None, description="Edited data")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ApprovalRequestListResponse(BaseModel):
    """Schema for listing approval requests."""

    items: List[ApprovalRequestResponse] = Field(..., description="List of requests")
    total: int = Field(..., description="Total count")
    pending_count: int = Field(default=0, description="Pending requests count")
    approved_count: int = Field(default=0, description="Approved requests count")
    rejected_count: int = Field(default=0, description="Rejected requests count")


class ApprovalActionRequest(BaseModel):
    """Schema for approve/reject action."""

    reason: Optional[str] = Field(default=None, description="Reason for decision")


class ApprovalEditRequest(BaseModel):
    """Schema for edit-then-approve action."""

    edited_data: Dict[str, Any] = Field(..., description="Edited request data")
    reason: Optional[str] = Field(default=None, description="Reason for edit")


class ApprovalStatsResponse(BaseModel):
    """Schema for approval statistics."""

    total: int = Field(..., description="Total requests")
    pending: int = Field(..., description="Pending count")
    approved: int = Field(..., description="Approved count")
    rejected: int = Field(..., description="Rejected count")
    edited: int = Field(..., description="Edited count")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Breakdown by type")
