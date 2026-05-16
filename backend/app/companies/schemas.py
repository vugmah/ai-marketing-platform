"""Pydantic schemas for Company CRUD operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.companies.models import PlanType, SubscriptionStatus


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class CompanyBase(BaseModel):
    """Shared company fields."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=5000)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    website: Optional[str] = Field(default=None, max_length=255)
    email: str = Field(..., max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    plan: PlanType = Field(default=PlanType.STARTER)
    subscription_status: SubscriptionStatus = Field(default=SubscriptionStatus.TRIAL)
    max_branches: int = Field(default=2, ge=1)
    max_users: int = Field(default=3, ge=1)
    ai_requests_limit: int = Field(default=500, ge=0)
    timezone: str = Field(default="Asia/Baku", max_length=50)
    currency: str = Field(default="AZN", max_length=3)
    language: str = Field(default="az", max_length=5)
    is_active: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

class CompanyCreate(CompanyBase):
    """Schema for creating a new company."""


class CompanyUpdate(BaseModel):
    """Schema for updating an existing company (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=5000)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    website: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    plan: Optional[PlanType] = None
    subscription_status: Optional[SubscriptionStatus] = None
    max_branches: Optional[int] = Field(default=None, ge=1)
    max_users: Optional[int] = Field(default=None, ge=1)
    ai_requests_limit: Optional[int] = Field(default=None, ge=0)
    timezone: Optional[str] = Field(default=None, max_length=50)
    currency: Optional[str] = Field(default=None, max_length=3)
    language: Optional[str] = Field(default=None, max_length=5)
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class CompanyResponse(CompanyBase):
    """Schema for company response (includes DB-generated fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    """Schema for paginated company list."""

    items: list[CompanyResponse]
    total: int
