"""ERP Integration API router.

Provides endpoints for:
- ERP connection CRUD (create, list, get, update, soft-delete)
- Sync operations (manual trigger, status check, logs, cancel)
- Field mapping CRUD
- Webhook endpoint for receiving ERP events (public, no auth)
- Health checks and sync statistics

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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
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
    SyncHealthCheckResponse,
    SyncLogListResponse,
    SyncLogResponse,
    SyncStatsResponse,
    SyncStatusResponse,
    SyncTriggerRequest,
    WebhookResponse,
)
from app.erp.connectors import (
    FUTURE_PROVIDERS,
    is_provider_supported,
    list_future_providers,
    list_supported_providers,
)
from app.erp.service import (
    ERPAuditService,
    ERPConnectionService,
    ERPFieldMappingService,
    ERPSyncLogService,
    ERPSyncService,
    ERPHealthService,
)
from app.utils.encryption import fernet_decrypt

router = APIRouter()

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new ERP connection for the current user's company.

    Validates provider_type and stores credentials securely (encrypted at rest).
    Returns the connection with sensitive fields stripped.
    """
    if current_user.company_id is None:
        raise ValidationError(detail="User must belong to a company to create ERP connections")

    # Private beta: only "custom" provider is fully supported
    provider = data.provider_type
    if not is_provider_supported(provider):
        raise HTTPException(
            status_code=501,
            detail=f"{provider.upper()} ERP connector is not yet available in private beta. "
                   f"Custom ERP connector is supported. "
                   f"Future providers: {', '.join(sorted(list_future_providers()))}",
        )

    connection = await ERPConnectionService.create_connection(
        db=db,
        company_id=current_user.company_id,
        branch_id=current_user.branch_id,
        name=data.name,
        provider_type=data.provider_type,
        base_url=str(data.base_url),
        api_key=data.api_key,
        api_secret=data.api_secret,
        webhook_secret=data.webhook_secret,
        sync_enabled=data.sync_enabled,
        auto_sync_interval_minutes=data.auto_sync_interval_minutes,
    )

    # Audit log
    await ERPAuditService.log_connection_created(
        db=db,
        connection_id=connection.id,
        company_id=current_user.company_id,
        performed_by=current_user.id,
    )

    resp = ERPConnectionService.to_response_dict(connection)
    return {
        "success": True,
        "data": resp,
    }


@router.get(
    "/connections",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List ERP connections",
)
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_type: Optional[str] = Query(default=None, description="Filter by provider type"),
    include_inactive: bool = Query(default=False, description="Include deactivated connections"),
) -> dict:
    """List ERP connections for the current user's company.

    Supports filtering by provider_type. Sensitive credentials are stripped.
    """
    connections = await ERPConnectionService.list_connections(
        db=db,
        company_id=current_user.company_id,
        provider_type=provider_type,
        include_inactive=include_inactive,
    )

    safe_connections = [ERPConnectionService.to_response_dict(c) for c in connections]

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a single ERP connection by ID. Returns 404 if not found or unauthorized."""
    connection = await ERPConnectionService.get_connection(
        db=db,
        connection_id=connection_id,
        company_id=current_user.company_id,
    )

    resp = ERPConnectionService.to_response_dict(connection)
    return {
        "success": True,
        "data": resp,
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update an existing ERP connection. Only provided fields are updated.

    Sensitive fields are updated if provided but never returned in the response.
    """
    # Build updates dict from non-None fields
    updates = {}
    for field in ["name", "base_url", "sync_enabled", "is_active", "auto_sync_interval_minutes"]:
        value = getattr(data, field)
        if value is not None:
            updates[field] = value
    for sensitive_field in ["api_key", "api_secret", "webhook_secret"]:
        value = getattr(data, sensitive_field)
        if value is not None:
            updates[sensitive_field] = value

    connection = await ERPConnectionService.update_connection(
        db=db,
        connection_id=connection_id,
        company_id=current_user.company_id,
        **updates,
    )

    # Audit log
    await ERPAuditService.log_connection_updated(
        db=db,
        connection_id=connection.id,
        company_id=current_user.company_id,
        performed_by=current_user.id,
        changed_fields=list(updates.keys()),
    )

    resp = ERPConnectionService.to_response_dict(connection)
    return {
        "success": True,
        "data": resp,
    }


@router.delete(
    "/connections/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Deactivate an ERP connection (soft delete)",
)
async def deactivate_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete (deactivate) an ERP connection instead of permanently removing it."""
    connection = await ERPConnectionService.deactivate_connection(
        db=db,
        connection_id=connection_id,
        company_id=current_user.company_id,
    )

    # Audit log
    await ERPAuditService.log_connection_deactivated(
        db=db,
        connection_id=connection.id,
        company_id=current_user.company_id,
        performed_by=current_user.id,
    )

    return {
        "success": True,
        "data": {"id": connection_id, "is_active": False, "message": "Connection deactivated"},
    }


# ---------------------------------------------------------------------------
# Provider discovery endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/providers",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List available ERP providers",
)
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all available ERP providers and their private beta status.

    Returns supported providers (fully functional) and future providers
    (not yet implemented - will return 501 if used).
    """
    return {
        "success": True,
        "data": {
            "supported": list_supported_providers(),
            "future": list_future_providers(),
            "note": "Only 'custom' ERP connector is fully supported in private beta.",
        },
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Trigger a manual sync job for an ERP connection.

    Creates an ERPSyncJob record with status='queued' and returns the job_id
    immediately. The actual sync processing happens asynchronously.
    """
    # Verify the connection exists and user has access
    connection = await ERPConnectionService.get_connection(
        db=db,
        connection_id=data.connection_id,
        company_id=current_user.company_id,
    )

    if not connection.is_active:
        raise ValidationError(detail="Cannot sync with an inactive connection")

    # Private beta: block sync for non-custom providers at API level
    provider = connection.provider_type.value if hasattr(connection.provider_type, "value") else str(connection.provider_type)
    if not is_provider_supported(provider):
        raise HTTPException(
            status_code=501,
            detail=f"{provider.upper()} ERP connector is not yet available in private beta. "
                   f"Custom ERP connector is supported.",
        )

    job = await ERPSyncService.create_sync_job(
        db=db,
        connection_id=data.connection_id,
        company_id=connection.company_id,
        branch_id=connection.branch_id,
        entity_type=data.entity_type,
        sync_type=data.sync_type,
        created_by=current_user.id,
    )

    # Audit log
    await ERPAuditService.log_sync_triggered(
        db=db,
        connection_id=data.connection_id,
        company_id=connection.company_id,
        job_id=job.id,
        entity_type=data.entity_type,
        sync_type=data.sync_type,
        performed_by=current_user.id,
    )

    return {
        "success": True,
        "data": {
            "job_id": job.id,
            "status": "queued",
            "message": "Sync job has been queued successfully",
        },
    }


@router.get(
    "/sync/status/{job_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync job status",
)
async def get_sync_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get the status of a sync job by its ID."""
    job = await ERPSyncService.get_sync_job(
        db=db,
        job_id=job_id,
        company_id=current_user.company_id,
    )

    resp = ERPSyncService.job_to_response_dict(job)
    return {
        "success": True,
        "data": resp,
    }


@router.get(
    "/sync/logs",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync logs (paginated)",
)
async def get_sync_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    connection_id: Optional[int] = Query(default=None, description="Filter by connection ID"),
    job_id: Optional[int] = Query(default=None, description="Filter by job ID"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    log_level: Optional[str] = Query(default=None, description="Filter by log level"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> dict:
    """Get sync logs with optional filtering and pagination."""
    result = await ERPSyncLogService.get_sync_logs(
        db=db,
        company_id=current_user.company_id,
        connection_id=connection_id,
        job_id=job_id,
        entity_type=entity_type,
        log_level=log_level,
        page=page,
        page_size=page_size,
    )

    logs = result["logs"]
    log_dicts = [ERPSyncLogService.log_to_response_dict(log) for log in logs]

    return {
        "success": True,
        "data": {
            "logs": log_dicts,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Cancel a sync job that is queued or running."""
    job = await ERPSyncService.cancel_sync_job(
        db=db,
        job_id=job_id,
        company_id=current_user.company_id,
    )

    # Audit log
    await ERPSyncLogService.create_sync_log(
        db=db,
        company_id=job.company_id,
        connection_id=job.connection_id,
        job_id=job_id,
        log_level="warning",
        entity_type=str(job.entity_type) if job.entity_type else "unknown",
        action="cancel",
        message=f"Sync job {job_id} cancelled by user {current_user.id}",
    )

    resp = ERPSyncService.job_to_response_dict(job)
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new field mapping for an ERP connection.

    Maps an ERP system field to an internal field with optional transformation.
    """
    # Verify the connection exists and user has access
    connection = await ERPConnectionService.get_connection(
        db=db,
        connection_id=data.connection_id,
        company_id=current_user.company_id,
    )

    mapping = await ERPFieldMappingService.create_mapping(
        db=db,
        company_id=connection.company_id,
        connection_id=data.connection_id,
        provider_type=connection.provider_type.value if hasattr(connection.provider_type, "value") else str(connection.provider_type),
        entity_type=data.entity_type,
        erp_field=data.erp_field,
        internal_field=data.internal_field,
        transformation=data.transformation,
        is_required=data.is_required,
        default_value=data.default_value,
    )

    # Audit log
    await ERPAuditService.log_field_mapping_change(
        db=db,
        connection_id=data.connection_id,
        company_id=connection.company_id,
        mapping_id=mapping.id,
        action="create",
        performed_by=current_user.id,
    )

    resp = ERPFieldMappingService.mapping_to_response_dict(mapping)
    return {
        "success": True,
        "data": resp,
    }


@router.get(
    "/mappings",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List field mappings",
)
async def list_field_mappings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    connection_id: Optional[int] = Query(default=None, description="Filter by connection ID"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
) -> dict:
    """List field mappings for the current user's company.

    Optionally filter by connection_id and/or entity_type.
    """
    mappings = await ERPFieldMappingService.list_mappings(
        db=db,
        company_id=current_user.company_id,
        connection_id=connection_id,
        entity_type=entity_type,
    )

    mapping_dicts = [ERPFieldMappingService.mapping_to_response_dict(m) for m in mappings]

    return {
        "success": True,
        "data": mapping_dicts,
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update an existing field mapping. Only provided fields are changed."""
    updates = {}
    for field in [
        "entity_type", "erp_field", "internal_field",
        "transformation", "is_required", "default_value",
    ]:
        value = getattr(data, field)
        if value is not None:
            updates[field] = value

    mapping = await ERPFieldMappingService.update_mapping(
        db=db,
        mapping_id=mapping_id,
        company_id=current_user.company_id,
        **updates,
    )

    # Audit log
    await ERPAuditService.log_field_mapping_change(
        db=db,
        connection_id=mapping.connection_id,
        company_id=mapping.company_id,
        mapping_id=mapping.id,
        action="update",
        performed_by=current_user.id,
    )

    resp = ERPFieldMappingService.mapping_to_response_dict(mapping)
    return {
        "success": True,
        "data": resp,
    }


@router.delete(
    "/mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a field mapping",
)
async def delete_field_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Permanently delete a field mapping."""
    mapping = await ERPFieldMappingService.get_mapping(
        db=db,
        mapping_id=mapping_id,
        company_id=current_user.company_id,
    )

    connection_id = mapping.connection_id
    company_id = mapping.company_id

    await ERPFieldMappingService.delete_mapping(
        db=db,
        mapping_id=mapping_id,
        company_id=current_user.company_id,
    )

    # Audit log
    await ERPAuditService.log_field_mapping_change(
        db=db,
        connection_id=connection_id,
        company_id=company_id,
        mapping_id=mapping_id,
        action="delete",
        performed_by=current_user.id,
    )


# ---------------------------------------------------------------------------
# Health check endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sync/health/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync health for an ERP connection",
)
async def get_sync_health(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get the sync health status for an ERP connection."""
    health = await ERPHealthService.get_sync_health(
        db=db,
        connection_id=connection_id,
        company_id=current_user.company_id,
    )

    return {
        "success": True,
        "data": health,
    }


@router.get(
    "/sync/stats/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync statistics for an ERP connection",
)
async def get_sync_stats(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    period_hours: int = Query(default=24, ge=1, le=168, description="Statistics period in hours"),
) -> dict:
    """Get sync statistics for an ERP connection."""
    stats = await ERPHealthService.get_sync_stats(
        db=db,
        connection_id=connection_id,
        company_id=current_user.company_id,
        period_hours=period_hours,
    )

    return {
        "success": True,
        "data": stats,
    }


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
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_webhook_signature: Optional[str] = Header(default=None, description="Webhook signature header (HMAC-SHA256 hex digest)"),
) -> dict:
    """Receive and process a webhook event from an external ERP system.

    This endpoint is **public** and does not require authentication.
    If a webhook_secret is configured for a matching connection,
    the HMAC-SHA256 signature is validated before accepting the payload.

    Processing is done asynchronously (fire-and-forget). Returns 200 immediately.

    Signature validation:
    - Computes HMAC-SHA256(secret, raw_body_bytes) and compares hex digest
    - Uses ``hmac.compare_digest`` to prevent timing attacks
    - Supports both 'sig=...' prefixed signatures and raw hex digests
    """
    # Read raw body bytes BEFORE any JSON parsing (FastAPI consumes the stream)
    raw_body = await request.body()

    # Parse JSON payload from raw bytes
    try:
        import json
        payload_data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event = payload_data.get("event", "")
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'event' field in payload",
        )

    # Find matching active connections for this provider type
    connections = await ERPConnectionService.list_connections(
        db=db,
        company_id=None,  # Check all companies for webhook
        include_inactive=False,
    )

    matching_connections = [
        c for c in connections
        if (c.provider_type.value if hasattr(c.provider_type, "value") else str(c.provider_type)) == provider_type
    ]

    if not matching_connections:
        # Return 200 regardless so the ERP doesn't retry unnecessarily
        return {
            "success": True,
            "message": "Webhook received but no matching active connection found",
        }

    # Attempt signature validation on connections with webhook_secret
    validated_connection = None
    signature_valid = False

    for connection in matching_connections:
        secret = None
        if connection.webhook_secret:
            try:
                secret = fernet_decrypt(connection.webhook_secret)
            except Exception:
                secret = connection.webhook_secret  # May be unencrypted legacy value

        if secret and x_webhook_signature:
            # Normalize signature: strip "sig=" or "sha256=" prefix if present
            sig = x_webhook_signature
            if "=" in sig and len(sig) < 100:
                sig = sig.split("=", 1)[1]
            if validate_webhook_signature(raw_body, sig, secret):
                validated_connection = connection
                signature_valid = True
                break
        elif not secret and not x_webhook_signature:
            # Neither secret nor signature configured, accept without validation
            validated_connection = connection
            break
        elif not secret and x_webhook_signature:
            # Signature sent but no secret configured - skip this connection
            continue

    if not validated_connection and any(
        c.webhook_secret for c in matching_connections
    ):
        # Signature was required but didn't match any connection
        # Log the failed attempt for security monitoring
        await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=matching_connections[0].company_id,
            connection_id=matching_connections[0].id,
            job_id=None,
            log_level="warning",
            entity_type=event.split(".")[0] if "." in event else "unknown",
            action="webhook_rejected",
            message=f"Invalid webhook signature from {provider_type}: event={event}",
            details={"event": event, "signature_header": x_webhook_signature},
        )
        return {
            "success": False,
            "message": "Invalid webhook signature",
        }

    connection = validated_connection or matching_connections[0]

    # Log the webhook payload (audit trail)
    await ERPSyncLogService.create_sync_log(
        db=db,
        company_id=connection.company_id,
        connection_id=connection.id,
        job_id=None,
        log_level="info",
        entity_type=event.split(".")[0] if "." in event else "unknown",
        action="webhook",
        message=f"Webhook received: {event} from {provider_type}",
        details={
            "event": event,
            "data": payload_data.get("data", {}),
            "signature_valid": signature_valid,
            "timestamp": payload_data.get("timestamp"),
        },
    )

    # In a real implementation, background task processing would be here:
    # await _process_webhook_event(connection.id, event, payload_data.get("data", {}))

    return {
        "success": True,
        "message": "Webhook accepted",
        "signature_valid": signature_valid,
    }
