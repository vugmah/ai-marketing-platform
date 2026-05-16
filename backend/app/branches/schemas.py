"""Pydantic schemas for Branch CRUD operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.branches.models import (
    BranchStatus,
    BranchType,
    ERPProvider,
    SocialPlatform,
)


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class BranchBase(BaseModel):
    """Shared branch fields."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    address: Optional[str] = Field(default=None, max_length=5000)
    type: BranchType = Field(default=BranchType.RESTAURANT)
    status: BranchStatus = Field(default=BranchStatus.ACTIVE)
    manager_name: Optional[str] = Field(default=None, max_length=255)
    manager_email: Optional[str] = Field(default=None, max_length=255)
    manager_phone: Optional[str] = Field(default=None, max_length=50)
    employee_count: int = Field(default=0, ge=0)
    monthly_revenue_target: float = Field(default=0.0, ge=0.0)
    daily_order_target: int = Field(default=0, ge=0)
    instagram_account: Optional[str] = Field(default=None, max_length=255)
    facebook_page_id: Optional[str] = Field(default=None, max_length=255)
    google_place_id: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

class BranchCreate(BranchBase):
    """Schema for creating a new branch.

    company_id is required because a branch must belong to a company.
    """

    company_id: int = Field(..., gt=0, description="Parent company ID")


class BranchUpdate(BaseModel):
    """Schema for updating an existing branch (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=100)
    city: Optional[str] = Field(default=None, min_length=1, max_length=100)
    address: Optional[str] = Field(default=None, max_length=5000)
    type: Optional[BranchType] = None
    status: Optional[BranchStatus] = None
    manager_name: Optional[str] = Field(default=None, max_length=255)
    manager_email: Optional[str] = Field(default=None, max_length=255)
    manager_phone: Optional[str] = Field(default=None, max_length=50)
    employee_count: Optional[int] = Field(default=None, ge=0)
    monthly_revenue_target: Optional[float] = Field(default=None, ge=0.0)
    daily_order_target: Optional[int] = Field(default=None, ge=0)
    instagram_account: Optional[str] = Field(default=None, max_length=255)
    facebook_page_id: Optional[str] = Field(default=None, max_length=255)
    google_place_id: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class BranchResponse(BranchBase):
    """Schema for branch response (includes DB-generated fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime


class BranchListResponse(BaseModel):
    """Schema for paginated branch list."""

    items: list[BranchResponse]
    total: int


# ---------------------------------------------------------------------------
# Branch Config schemas
# ---------------------------------------------------------------------------

class BranchConfigBase(BaseModel):
    """Shared branch config fields."""

    config_key: str = Field(..., min_length=1, max_length=255)
    config_value: Optional[str] = Field(default=None)


class BranchConfigCreate(BranchConfigBase):
    """Schema for creating a branch config entry."""


class BranchConfigUpdate(BaseModel):
    """Schema for updating a branch config entry."""

    config_value: Optional[str] = None


class BranchConfigResponse(BranchConfigBase):
    """Schema for branch config response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    created_at: datetime


class BranchConfigListResponse(BaseModel):
    """Schema for paginated branch config list."""

    items: list[BranchConfigResponse]
    total: int


# ============================================================================
# AI Prompt Override schemas
# ============================================================================


class AIPromptOverrideBase(BaseModel):
    """Shared AI prompt override fields."""

    prompt_key: str = Field(..., min_length=1, max_length=255)
    prompt_template: str = Field(..., min_length=1)
    is_active: bool = Field(default=True)
    priority: int = Field(default=0, ge=0)


class AIPromptOverrideCreate(AIPromptOverrideBase):
    """Schema for creating an AI prompt override."""


class AIPromptOverrideUpdate(BaseModel):
    """Schema for updating an AI prompt override."""

    prompt_template: Optional[str] = Field(default=None, min_length=1)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=0)


class AIPromptOverrideResponse(AIPromptOverrideBase):
    """Schema for AI prompt override response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    created_at: datetime
    updated_at: datetime


class AIPromptOverrideListResponse(BaseModel):
    """Schema for paginated AI prompt override list."""

    items: list[AIPromptOverrideResponse]
    total: int


# ============================================================================
# Social Account Config schemas
# ============================================================================


class SocialAccountConfigBase(BaseModel):
    """Shared social account config fields."""

    platform: SocialPlatform
    account_handle: Optional[str] = Field(default=None, max_length=255)
    page_id: Optional[str] = Field(default=None, max_length=255)
    is_connected: bool = Field(default=False)
    auto_publish: bool = Field(default=False)
    settings_json: Optional[str] = Field(default=None)


class SocialAccountConfigCreate(SocialAccountConfigBase):
    """Schema for creating a social account config.

    access_token and refresh_token are optional on create because
    they may be populated via OAuth flow after initial creation.
    """

    access_token: Optional[str] = Field(default=None)
    refresh_token: Optional[str] = Field(default=None)
    token_expires_at: Optional[datetime] = None


class SocialAccountConfigUpdate(BaseModel):
    """Schema for updating a social account config."""

    account_handle: Optional[str] = Field(default=None, max_length=255)
    access_token: Optional[str] = Field(default=None)
    refresh_token: Optional[str] = Field(default=None)
    token_expires_at: Optional[datetime] = None
    page_id: Optional[str] = Field(default=None, max_length=255)
    is_connected: Optional[bool] = None
    auto_publish: Optional[bool] = None
    settings_json: Optional[str] = Field(default=None)


class SocialAccountConfigResponse(SocialAccountConfigBase):
    """Schema for social account config response.

    Tokens are excluded from response for security.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    token_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SocialAccountConfigListResponse(BaseModel):
    """Schema for paginated social account config list."""

    items: list[SocialAccountConfigResponse]
    total: int


# ============================================================================
# ERP Connection Config schemas
# ============================================================================


class ERPConnectionConfigBase(BaseModel):
    """Shared ERP connection config fields."""

    provider: ERPProvider
    api_base_url: Optional[str] = Field(default=None, max_length=500)
    location_id: Optional[str] = Field(default=None, max_length=255)
    terminal_id: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    sync_enabled: bool = Field(default=False)
    sync_interval_minutes: int = Field(default=60, ge=1)
    settings_json: Optional[str] = Field(default=None)


class ERPConnectionConfigCreate(ERPConnectionConfigBase):
    """Schema for creating an ERP connection config.

    api_key and api_secret are optional on create because
    they may be populated via a separate secure flow.
    """

    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    webhook_secret: Optional[str] = Field(default=None)


class ERPConnectionConfigUpdate(BaseModel):
    """Schema for updating an ERP connection config."""

    api_base_url: Optional[str] = Field(default=None, max_length=500)
    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    webhook_secret: Optional[str] = Field(default=None)
    location_id: Optional[str] = Field(default=None, max_length=255)
    terminal_id: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None
    sync_enabled: Optional[bool] = None
    sync_interval_minutes: Optional[int] = Field(default=None, ge=1)
    settings_json: Optional[str] = Field(default=None)
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = Field(default=None, max_length=50)


class ERPConnectionConfigResponse(ERPConnectionConfigBase):
    """Schema for ERP connection config response.

    api_key, api_secret, and webhook_secret are excluded from response
    for security. Clients should use a separate credential-check endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ERPConnectionConfigListResponse(BaseModel):
    """Schema for paginated ERP connection config list."""

    items: list[ERPConnectionConfigResponse]
    total: int
