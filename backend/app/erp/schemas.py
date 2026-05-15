"""Pydantic schemas for the ERP Integration module.

Request and response models for:
- ERP connection management (create, read, update)
- Sync operations (trigger, status, logs)
- Field mapping CRUD
- Webhook payload handling
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Provider type literal (shared)
# ---------------------------------------------------------------------------

ProviderType = Literal[
    "custom", "odoo", "sap", "netsuite", "dynamics",
    "logo", "mikro", "parasut", "1c",
]

EntityType = Literal[
    "products", "inventory", "sales_orders",
    "customers", "invoices", "payments", "all",
]

SyncType = Literal["incremental", "full"]


# ---------------------------------------------------------------------------
# Connection schemas
# ---------------------------------------------------------------------------

class ERPConnectionCreate(BaseModel):
    """Schema for creating a new ERP connection."""

    name: str = Field(..., min_length=1, max_length=255, description="Display name for the connection")
    provider_type: ProviderType = Field(..., description="ERP provider type")
    base_url: str = Field(..., min_length=1, max_length=500, description="Base URL of the ERP API")
    api_key: Optional[str] = Field(default=None, max_length=500, description="API key for authentication")
    api_secret: Optional[str] = Field(default=None, max_length=500, description="API secret for authentication")
    webhook_secret: Optional[str] = Field(default=None, max_length=500, description="Secret for webhook signature validation")
    sync_enabled: bool = Field(default=True, description="Whether automatic sync is enabled")
    auto_sync_interval_minutes: int = Field(default=60, ge=5, le=1440, description="Auto-sync interval in minutes")

    @field_validator("auto_sync_interval_minutes")
    @classmethod
    def validate_sync_interval(cls, value: int) -> int:
        if value < 5:
            raise ValueError("Auto-sync interval must be at least 5 minutes")
        if value > 1440:
            raise ValueError("Auto-sync interval must not exceed 1440 minutes (24 hours)")
        return value


class ERPConnectionUpdate(BaseModel):
    """Schema for updating an existing ERP connection."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    api_key: Optional[str] = Field(default=None, max_length=500)
    api_secret: Optional[str] = Field(default=None, max_length=500)
    webhook_secret: Optional[str] = Field(default=None, max_length=500)
    sync_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    auto_sync_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)


class ERPConnectionResponse(BaseModel):
    """Schema for returning ERP connection data (sensitive fields excluded)."""

    id: int = Field(..., description="Connection ID")
    company_id: int = Field(..., description="Owning company ID")
    name: str = Field(..., description="Display name")
    provider_type: str = Field(..., description="ERP provider type")
    base_url: str = Field(..., description="Base URL of the ERP API")
    sync_enabled: bool = Field(..., description="Whether auto-sync is enabled")
    auto_sync_interval_minutes: int = Field(..., description="Auto-sync interval in minutes")
    last_sync_status: str = Field(default="never", description="Status of the last sync")
    last_sync_at: Optional[str] = Field(default=None, description="ISO timestamp of last sync")
    is_active: bool = Field(..., description="Whether the connection is active")
    created_at: str = Field(..., description="ISO timestamp of creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Sync operation schemas
# ---------------------------------------------------------------------------

class SyncTriggerRequest(BaseModel):
    """Schema for triggering a manual sync job."""

    connection_id: int = Field(..., description="ID of the ERP connection to sync")
    entity_type: EntityType = Field(..., description="Type of entity to sync")
    sync_type: SyncType = Field(default="incremental", description="Sync type: incremental or full")


class SyncStatusResponse(BaseModel):
    """Schema for returning sync job status."""

    job_id: int = Field(..., description="Unique sync job ID")
    connection_id: int = Field(..., description="ERP connection ID")
    status: str = Field(..., description="Job status: queued, running, completed, failed, cancelled")
    entity_type: str = Field(..., description="Entity type being synced")
    sync_type: str = Field(..., description="Sync type used")
    records_total: int = Field(default=0, description="Total records to process")
    records_processed: int = Field(default=0, description="Records successfully processed")
    records_failed: int = Field(default=0, description="Records that failed")
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when job started")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when job completed")
    error_message: Optional[str] = Field(default=None, description="Error message if job failed")
    created_at: str = Field(..., description="ISO timestamp when job was created")

    class Config:
        from_attributes = True


class SyncLogResponse(BaseModel):
    """Schema for returning a single sync log entry."""

    id: int = Field(..., description="Log entry ID")
    job_id: Optional[int] = Field(default=None, description="Associated sync job ID")
    connection_id: int = Field(..., description="ERP connection ID")
    log_level: str = Field(..., description="Log level: info, warning, error")
    entity_type: str = Field(..., description="Entity type affected")
    action: str = Field(..., description="Action performed: create, update, delete, sync")
    external_id: Optional[str] = Field(default=None, description="External ERP system ID")
    message: str = Field(..., description="Log message")
    created_at: str = Field(..., description="ISO timestamp")

    class Config:
        from_attributes = True


class SyncLogListResponse(BaseModel):
    """Schema for paginated sync log list."""

    logs: List[SyncLogResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total log count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")


# ---------------------------------------------------------------------------
# Webhook schemas
# ---------------------------------------------------------------------------

class ERPWebhookPayload(BaseModel):
    """Schema for incoming webhook payloads from ERP systems."""

    event: str = Field(..., description="Event type, e.g. 'product.created', 'inventory.updated'")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload data")
    timestamp: str = Field(..., description="ISO timestamp from the ERP system")
    signature: Optional[str] = Field(default=None, description="Webhook signature for verification")


class WebhookResponse(BaseModel):
    """Schema for webhook endpoint response."""

    success: bool = Field(..., description="Whether the webhook was accepted")
    message: str = Field(..., description="Status message")


# ---------------------------------------------------------------------------
# Field mapping schemas
# ---------------------------------------------------------------------------

class FieldMappingCreate(BaseModel):
    """Schema for creating a field mapping."""

    connection_id: int = Field(..., description="ID of the ERP connection")
    entity_type: str = Field(..., min_length=1, max_length=100, description="Entity type being mapped")
    erp_field: str = Field(..., min_length=1, max_length=255, description="Field name in the ERP system")
    internal_field: str = Field(..., min_length=1, max_length=255, description="Corresponding internal field name")
    transformation: Optional[str] = Field(default=None, max_length=500, description="Optional transformation expression")
    is_required: bool = Field(default=False, description="Whether this field is required")
    default_value: Optional[str] = Field(default=None, max_length=500, description="Default value if ERP field is empty")


class FieldMappingUpdate(BaseModel):
    """Schema for updating a field mapping."""

    entity_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    erp_field: Optional[str] = Field(default=None, min_length=1, max_length=255)
    internal_field: Optional[str] = Field(default=None, min_length=1, max_length=255)
    transformation: Optional[str] = Field(default=None, max_length=500)
    is_required: Optional[bool] = None
    default_value: Optional[str] = Field(default=None, max_length=500)


class FieldMappingResponse(BaseModel):
    """Schema for returning a field mapping."""

    id: int = Field(..., description="Mapping ID")
    connection_id: int = Field(..., description="ERP connection ID")
    entity_type: str = Field(..., description="Entity type")
    erp_field: str = Field(..., description="ERP field name")
    internal_field: str = Field(..., description="Internal field name")
    transformation: Optional[str] = Field(default=None, description="Transformation expression")
    is_required: bool = Field(..., description="Whether field is required")
    default_value: Optional[str] = Field(default=None, description="Default value")
    created_at: str = Field(..., description="ISO timestamp")
    updated_at: str = Field(..., description="ISO timestamp")

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Generic response wrapper
# ---------------------------------------------------------------------------

class SuccessResponse(BaseModel):
    """Generic success response wrapper used by all ERP endpoints."""

    success: bool = Field(default=True, description="Operation succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Response payload")
