"""ERP Integration API router.

Provides endpoints for:
- ERP connection CRUD (create, list, get, update, soft-delete)
- Sync operations (manual trigger, status check, logs, cancel)
- Field mapping CRUD
- Webhook endpoint for receiving ERP events (public, no auth)

Security:
- All endpoints (except webhook) require authentication via get_current_user
- Tenant isolation is enforced via company_id matching
- Sensitive credential fields are stripped from all responses
- Webhook signatures are validated when a webhook_secret is configured
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import (
    AlreadyExistsError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.erp.schemas import (
    ERPConnectionCreate,
    ERPConnectionResponse,
    ERPConnectionUpdate,
    ERPWebhookPayload,
    FieldMappingCreate,
    FieldMappingResponse,
    FieldMappingUpdate,
    SuccessResponse,
    SyncLogListResponse,
    SyncLogResponse,
    SyncStatusResponse,
    SyncTriggerRequest,
    WebhookResponse,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory mock stores (replace with database tables in production)
# ---------------------------------------------------------------------------

_mock_connections: Dict[int, Dict[str, Any]] = {}
_mock_sync_jobs: Dict[int, Dict[str, Any]] = {}
_mock_sync_logs: Dict[int, Dict[str, Any]] = {}
_mock_field_mappings: Dict[int, Dict[str, Any]] = {}

# Sequences for IDs
_connection_id_seq = 0
_sync_job_id_seq = 0
_sync_log_id_seq = 0
_mapping_id_seq = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _strip_sensitive(connection: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of connection dict with sensitive fields removed."""
    safe = dict(connection)
    for key in ("api_key", "api_secret", "oauth_token", "oauth_token_secret", "webhook_secret"):
        safe.pop(key, None)
    return safe


def _require_company_access(connection: Dict[str, Any], user: User) -> None:
    """Ensure the user's company_id matches the connection's company_id.

    Raises TenantError if the user does not have access.
    """
    if user.company_id is None:
        # Super admins can access any company's data
        return
    if connection.get("company_id") != user.company_id:
        raise AuthorizationError(
            detail="You do not have access to this ERP connection"
        )


# ---------------------------------------------------------------------------
# Webhook signature validation
# ---------------------------------------------------------------------------


def validate_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate a webhook payload signature using HMAC-SHA256.

    Args:
        payload: Raw request body bytes.
        signature: The signature provided in the webhook request header.
        secret: The webhook_secret configured for the ERP connection.

    Returns:
        True if the signature is valid, False otherwise.
    """
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Connection management endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/connections",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ERP connection",
)
async def create_connection(
    data: ERPConnectionCreate,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new ERP connection for the current user's company.

    Validates provider_type and stores credentials securely (in-memory mock).
    Returns the connection with sensitive fields stripped.
    """
    global _connection_id_seq

    if current_user.company_id is None:
        raise ValidationError(detail="User must belong to a company to create ERP connections")

    _connection_id_seq += 1
    conn_id = _connection_id_seq

    now = _now_iso()
    connection = {
        "id": conn_id,
        "company_id": current_user.company_id,
        "name": data.name,
        "provider_type": data.provider_type,
        "base_url": str(data.base_url),
        "api_key": data.api_key,
        "api_secret": data.api_secret,
        "webhook_secret": data.webhook_secret,
        "sync_enabled": data.sync_enabled,
        "auto_sync_interval_minutes": data.auto_sync_interval_minutes,
        "last_sync_status": "never",
        "last_sync_at": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    _mock_connections[conn_id] = connection

    return {
        "success": True,
        "data": _strip_sensitive(connection),
    }


@router.get(
    "/connections",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List ERP connections",
)
async def list_connections(
    current_user: User = Depends(get_current_user),
    provider_type: Optional[str] = Query(default=None, description="Filter by provider type"),
    include_inactive: bool = Query(default=False, description="Include deactivated connections"),
) -> dict:
    """List ERP connections for the current user's company.

    Supports filtering by provider_type. Sensitive credentials are stripped.
    """
    if current_user.company_id is None:
        # Super admin: can see all connections (optional filter)
        connections = list(_mock_connections.values())
    else:
        connections = [
            c for c in _mock_connections.values()
            if c["company_id"] == current_user.company_id
        ]

    # Apply provider_type filter
    if provider_type:
        connections = [c for c in connections if c["provider_type"] == provider_type]

    # Exclude inactive unless requested
    if not include_inactive:
        connections = [c for c in connections if c.get("is_active", True)]

    safe_connections = [_strip_sensitive(c) for c in connections]

    return {
        "success": True,
        "data": safe_connections,
    }


@router.get(
    "/connections/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get an ERP connection by ID",
)
async def get_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a single ERP connection by ID. Returns 404 if not found or unauthorized."""
    connection = _mock_connections.get(connection_id)
    if not connection:
        raise NotFoundError(detail=f"ERP connection with ID '{connection_id}' not found")

    _require_company_access(connection, current_user)

    return {
        "success": True,
        "data": _strip_sensitive(connection),
    }


@router.put(
    "/connections/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update an ERP connection",
)
async def update_connection(
    connection_id: int,
    data: ERPConnectionUpdate,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update an existing ERP connection. Only provided fields are updated.

    Sensitive fields are updated if provided but never returned in the response.
    """
    connection = _mock_connections.get(connection_id)
    if not connection:
        raise NotFoundError(detail=f"ERP connection with ID '{connection_id}' not found")

    _require_company_access(connection, current_user)

    updatable_fields = [
        "name", "base_url", "sync_enabled", "is_active", "auto_sync_interval_minutes",
    ]
    for field in updatable_fields:
        value = getattr(data, field)
        if value is not None:
            connection[field] = value

    # Handle sensitive fields separately (update but don't return)
    for sensitive_field in ["api_key", "api_secret", "webhook_secret"]:
        value = getattr(data, sensitive_field)
        if value is not None:
            connection[sensitive_field] = value

    connection["updated_at"] = _now_iso()
    _mock_connections[connection_id] = connection

    return {
        "success": True,
        "data": _strip_sensitive(connection),
    }


@router.delete(
    "/connections/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Deactivate an ERP connection (soft delete)",
)
async def deactivate_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete (deactivate) an ERP connection instead of permanently removing it."""
    connection = _mock_connections.get(connection_id)
    if not connection:
        raise NotFoundError(detail=f"ERP connection with ID '{connection_id}' not found")

    _require_company_access(connection, current_user)

    connection["is_active"] = False
    connection["sync_enabled"] = False
    connection["updated_at"] = _now_iso()
    _mock_connections[connection_id] = connection

    return {
        "success": True,
        "data": {"id": connection_id, "is_active": False, "message": "Connection deactivated"},
    }


# ---------------------------------------------------------------------------
# Sync operation endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/sync/manual",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a manual sync job",
)
async def trigger_manual_sync(
    data: SyncTriggerRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Trigger a manual sync job for an ERP connection.

    Creates an ERPSyncJob record with status='queued' and returns the job_id
    immediately. The actual sync processing happens asynchronously.
    """
    global _sync_job_id_seq

    # Verify the connection exists and user has access
    connection = _mock_connections.get(data.connection_id)
    if not connection:
        raise NotFoundError(detail=f"ERP connection with ID '{data.connection_id}' not found")

    _require_company_access(connection, current_user)

    if not connection.get("is_active", True):
        raise ValidationError(detail="Cannot sync with an inactive connection")

    _sync_job_id_seq += 1
    job_id = _sync_job_id_seq
    now = _now_iso()

    job = {
        "id": job_id,
        "connection_id": data.connection_id,
        "company_id": connection["company_id"],
        "status": "queued",
        "entity_type": data.entity_type,
        "sync_type": data.sync_type,
        "records_total": 0,
        "records_processed": 0,
        "records_failed": 0,
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "created_by": current_user.id,
        "created_at": now,
    }

    _mock_sync_jobs[job_id] = job

    # Create a log entry for the job creation
    _create_sync_log(
        job_id=job_id,
        connection_id=data.connection_id,
        company_id=connection["company_id"],
        log_level="info",
        entity_type=data.entity_type,
        action="sync",
        message=f"Sync job created: {data.entity_type} ({data.sync_type})",
    )

    return {
        "success": True,
        "data": {
            "job_id": job_id,
            "status": "queued",
            "message": "Sync job has been queued successfully",
        },
    }


def _create_sync_log(
    job_id: Optional[int],
    connection_id: int,
    company_id: int,
    log_level: str,
    entity_type: str,
    action: str,
    message: str,
    external_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a sync log entry in the mock store."""
    global _sync_log_id_seq
    _sync_log_id_seq += 1
    log_id = _sync_log_id_seq

    log_entry = {
        "id": log_id,
        "job_id": job_id,
        "connection_id": connection_id,
        "company_id": company_id,
        "log_level": log_level,
        "entity_type": entity_type,
        "action": action,
        "external_id": external_id,
        "message": message,
        "created_at": _now_iso(),
    }

    _mock_sync_logs[log_id] = log_entry
    return log_entry


@router.get(
    "/sync/status/{job_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync job status",
)
async def get_sync_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get the status of a sync job by its ID."""
    job = _mock_sync_jobs.get(job_id)
    if not job:
        raise NotFoundError(detail=f"Sync job with ID '{job_id}' not found")

    _require_company_access(job, current_user)

    return {
        "success": True,
        "data": {
            "job_id": job["id"],
            "connection_id": job["connection_id"],
            "status": job["status"],
            "entity_type": job["entity_type"],
            "sync_type": job["sync_type"],
            "records_total": job["records_total"],
            "records_processed": job["records_processed"],
            "records_failed": job["records_failed"],
            "started_at": job["started_at"],
            "completed_at": job["completed_at"],
            "error_message": job["error_message"],
            "created_at": job["created_at"],
        },
    }


@router.get(
    "/sync/logs",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync logs (paginated)",
)
async def get_sync_logs(
    current_user: User = Depends(get_current_user),
    connection_id: Optional[int] = Query(default=None, description="Filter by connection ID"),
    job_id: Optional[int] = Query(default=None, description="Filter by job ID"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    log_level: Optional[str] = Query(default=None, description="Filter by log level"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> dict:
    """Get sync logs with optional filtering and pagination."""
    logs = list(_mock_sync_logs.values())

    # Apply company filter (tenant isolation)
    if current_user.company_id is not None:
        logs = [l for l in logs if l.get("company_id") == current_user.company_id]

    # Apply optional filters
    if connection_id:
        logs = [l for l in logs if l["connection_id"] == connection_id]
    if job_id:
        logs = [l for l in logs if l.get("job_id") == job_id]
    if entity_type:
        logs = [l for l in logs if l["entity_type"] == entity_type]
    if log_level:
        logs = [l for l in logs if l["log_level"] == log_level]

    # Sort by created_at descending (newest first)
    logs.sort(key=lambda x: x["created_at"], reverse=True)

    total = len(logs)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_logs = logs[start:end]

    return {
        "success": True,
        "data": {
            "logs": paginated_logs,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.post(
    "/sync/{job_id}/cancel",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Cancel a running sync job",
)
async def cancel_sync_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Cancel a sync job that is queued or running."""
    job = _mock_sync_jobs.get(job_id)
    if not job:
        raise NotFoundError(detail=f"Sync job with ID '{job_id}' not found")

    _require_company_access(job, current_user)

    if job["status"] not in ("queued", "running"):
        raise ValidationError(
            detail=f"Cannot cancel sync job with status '{job['status']}'. Only 'queued' or 'running' jobs can be cancelled."
        )

    job["status"] = "cancelled"
    job["completed_at"] = _now_iso()
    _mock_sync_jobs[job_id] = job

    # Log the cancellation
    _create_sync_log(
        job_id=job_id,
        connection_id=job["connection_id"],
        company_id=job["company_id"],
        log_level="warning",
        entity_type=job["entity_type"],
        action="cancel",
        message=f"Sync job {job_id} cancelled by user {current_user.id}",
    )

    return {
        "success": True,
        "data": {"job_id": job_id, "status": "cancelled", "message": "Sync job cancelled"},
    }


# ---------------------------------------------------------------------------
# Field mapping endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/mappings",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a field mapping",
)
async def create_field_mapping(
    data: FieldMappingCreate,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new field mapping for an ERP connection.

    Maps an ERP system field to an internal field with optional transformation.
    """
    global _mapping_id_seq

    # Verify the connection exists and user has access
    connection = _mock_connections.get(data.connection_id)
    if not connection:
        raise NotFoundError(detail=f"ERP connection with ID '{data.connection_id}' not found")

    _require_company_access(connection, current_user)

    _mapping_id_seq += 1
    mapping_id = _mapping_id_seq
    now = _now_iso()

    mapping = {
        "id": mapping_id,
        "connection_id": data.connection_id,
        "company_id": connection["company_id"],
        "entity_type": data.entity_type,
        "erp_field": data.erp_field,
        "internal_field": data.internal_field,
        "transformation": data.transformation,
        "is_required": data.is_required,
        "default_value": data.default_value,
        "created_at": now,
        "updated_at": now,
    }

    _mock_field_mappings[mapping_id] = mapping

    return {
        "success": True,
        "data": mapping,
    }


@router.get(
    "/mappings",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List field mappings",
)
async def list_field_mappings(
    current_user: User = Depends(get_current_user),
    connection_id: Optional[int] = Query(default=None, description="Filter by connection ID"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
) -> dict:
    """List field mappings for the current user's company.

    Optionally filter by connection_id and/or entity_type.
    """
    mappings = list(_mock_field_mappings.values())

    # Apply company filter (tenant isolation)
    if current_user.company_id is not None:
        mappings = [m for m in mappings if m.get("company_id") == current_user.company_id]

    if connection_id:
        mappings = [m for m in mappings if m["connection_id"] == connection_id]
    if entity_type:
        mappings = [m for m in mappings if m["entity_type"] == entity_type]

    return {
        "success": True,
        "data": mappings,
    }


@router.put(
    "/mappings/{mapping_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update a field mapping",
)
async def update_field_mapping(
    mapping_id: int,
    data: FieldMappingUpdate,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update an existing field mapping. Only provided fields are changed."""
    mapping = _mock_field_mappings.get(mapping_id)
    if not mapping:
        raise NotFoundError(detail=f"Field mapping with ID '{mapping_id}' not found")

    _require_company_access(mapping, current_user)

    updatable_fields = [
        "entity_type", "erp_field", "internal_field",
        "transformation", "is_required", "default_value",
    ]
    for field in updatable_fields:
        value = getattr(data, field)
        if value is not None:
            mapping[field] = value

    mapping["updated_at"] = _now_iso()
    _mock_field_mappings[mapping_id] = mapping

    return {
        "success": True,
        "data": mapping,
    }


@router.delete(
    "/mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a field mapping",
)
async def delete_field_mapping(
    mapping_id: int,
    current_user: User = Depends(get_current_user),
) -> None:
    """Permanently delete a field mapping."""
    mapping = _mock_field_mappings.get(mapping_id)
    if not mapping:
        raise NotFoundError(detail=f"Field mapping with ID '{mapping_id}' not found")

    _require_company_access(mapping, current_user)

    del _mock_field_mappings[mapping_id]


# ---------------------------------------------------------------------------
# Webhook endpoint (public - no auth required)
# ---------------------------------------------------------------------------


@router.post(
    "/webhook/{provider_type}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Receive webhook from an ERP system",
)
async def receive_webhook(
    provider_type: str,
    payload: ERPWebhookPayload,
    request: Request,
    x_webhook_signature: Optional[str] = Header(default=None, description="Webhook signature header"),
) -> dict:
    """Receive and process a webhook event from an external ERP system.

    This endpoint is **public** and does not require authentication.
    If a webhook_secret is configured for a matching connection,
    the signature is validated before accepting the payload.

    Processing is done asynchronously (fire-and-forget). Returns 200 immediately.
    """
    # Find matching active connections for this provider type
    matching_connections = [
        c for c in _mock_connections.values()
        if c["provider_type"] == provider_type and c.get("is_active", True)
    ]

    if not matching_connections:
        # Return 200 regardless so the ERP doesn't retry unnecessarily
        return {
            "success": True,
            "message": "Webhook received but no matching active connection found",
        }

    # Attempt signature validation on connections with webhook_secret
    validated_connection = None
    for connection in matching_connections:
        secret = connection.get("webhook_secret")
        if secret and x_webhook_signature:
            # Read raw body for signature validation
            body = await request.body()
            if validate_webhook_signature(body, x_webhook_signature, secret):
                validated_connection = connection
                break
        elif not secret:
            # No secret configured, accept without validation
            validated_connection = connection
            break

    if validated_connection is None and any(
        c.get("webhook_secret") for c in matching_connections
    ):
        # Signature was required but didn't match any connection
        return {
            "success": False,
            "message": "Invalid webhook signature",
        }

    connection = validated_connection or matching_connections[0]

    # Log the webhook payload asynchronously (fire-and-forget)
    _create_sync_log(
        job_id=None,
        connection_id=connection["id"],
        company_id=connection["company_id"],
        log_level="info",
        entity_type=payload.event.split(".")[0] if "." in payload.event else "unknown",
        action="webhook",
        message=f"Webhook received: {payload.event} from {provider_type}",
        external_id=None,
    )

    # In a real implementation, background task processing would be here:
    # await _process_webhook_event(connection["id"], payload.event, payload.data)

    return {
        "success": True,
        "message": "Webhook accepted",
    }
