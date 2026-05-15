"""ERP sync HTTP API router.

Provides endpoints for triggering syncs, checking sync status,
managing ERP connections, and viewing synced data.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.erp.models import (
    ERPConnection,
    ERPSyncJob,
    ERPProduct,
    SyncStatus,
    SyncTrigger,
)
from app.erp.sync_service import sync_engine

router = APIRouter()


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


@router.get(
    "/connections",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="List ERP connections",
)
async def list_connections(db: AsyncSession = Depends(get_db)) -> List[dict]:
    """List all configured ERP connections."""
    result = await db.execute(select(ERPConnection))
    connections = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "provider_type": c.provider_type,
            "base_url": c.base_url,
            "sync_enabled": c.sync_enabled,
            "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
            "last_sync_status": c.last_sync_status,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in connections
    ]


@router.post(
    "/connections",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create ERP connection",
)
async def create_connection(payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    """Create a new ERP connection configuration."""
    connection = ERPConnection(
        company_id=payload["company_id"],
        branch_id=payload.get("branch_id"),
        name=payload["name"],
        provider_type=payload["provider_type"],
        base_url=payload["base_url"],
        api_key=payload.get("api_key"),
        api_secret=payload.get("api_secret"),
        sync_enabled=payload.get("sync_enabled", True),
        sync_entities=payload.get("sync_entities", []),
        field_mappings=payload.get("field_mappings"),
        webhook_url=payload.get("webhook_url"),
        webhook_secret=payload.get("webhook_secret"),
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return {"id": connection.id, "status": "created"}


@router.get(
    "/connections/{connection_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get ERP connection details",
)
async def get_connection(
    connection_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    """Get details of a single ERP connection."""
    result = await db.execute(
        select(ERPConnection).where(ERPConnection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )
    return {
        "id": connection.id,
        "name": connection.name,
        "provider_type": connection.provider_type,
        "base_url": connection.base_url,
        "sync_enabled": connection.sync_enabled,
        "sync_entities": connection.sync_entities,
        "field_mappings": connection.field_mappings,
        "last_sync_at": (
            connection.last_sync_at.isoformat() if connection.last_sync_at else None
        ),
        "last_sync_status": connection.last_sync_status,
        "last_sync_error": connection.last_sync_error,
        "is_active": connection.is_active,
    }


# ---------------------------------------------------------------------------
# Sync jobs
# ---------------------------------------------------------------------------


@router.post(
    "/sync",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a sync job",
)
async def trigger_sync(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a sync job for a given connection and entity type.

    The sync runs in the background so the HTTP response returns immediately.
    """
    connection_id = payload.get("connection_id")
    entity_type = payload.get("entity_type", "all")
    sync_type = payload.get("sync_type", "incremental")

    # Validate connection
    result = await db.execute(
        select(ERPConnection).where(ERPConnection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )

    # Create job record
    job = ERPSyncJob(
        connection_id=connection_id,
        entity_type=entity_type,
        sync_type=sync_type,
        trigger=SyncTrigger.MANUAL,
        status=SyncStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Launch sync in background
    background_tasks.add_task(
        sync_engine.run_sync,
        job_id=job.id,
        connection_id=connection_id,
        entity_type=entity_type,
        sync_type=sync_type,
    )

    return {
        "job_id": job.id,
        "status": "accepted",
        "message": "Sync job queued for execution",
    }


@router.get(
    "/sync/jobs",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="List sync jobs",
)
async def list_jobs(
    connection_id: Optional[int] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List sync job history."""
    query = select(ERPSyncJob).order_by(ERPSyncJob.created_at.desc()).limit(limit)
    if connection_id:
        query = query.where(ERPSyncJob.connection_id == connection_id)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "connection_id": j.connection_id,
            "entity_type": j.entity_type,
            "sync_type": j.sync_type,
            "trigger": j.trigger.value,
            "status": j.status.value,
            "records_processed": j.records_processed,
            "records_failed": j.records_failed,
            "error_message": j.error_message,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.get(
    "/sync/jobs/{job_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get sync job details",
)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Get detailed status of a single sync job."""
    result = await db.execute(select(ERPSyncJob).where(ERPSyncJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return {
        "id": job.id,
        "connection_id": job.connection_id,
        "entity_type": job.entity_type,
        "sync_type": job.sync_type,
        "trigger": job.trigger.value,
        "status": job.status.value,
        "records_processed": job.records_processed,
        "records_failed": job.records_failed,
        "error_message": job.error_message,
        "logs": job.logs,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


# ---------------------------------------------------------------------------
# Synced data (read-only views)
# ---------------------------------------------------------------------------


@router.get(
    "/products",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="List synced products",
)
async def list_products(
    connection_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """List products that have been synced from ERP systems."""
    query = select(ERPProduct).limit(limit).offset(offset)
    if connection_id:
        query = query.where(ERPProduct.connection_id == connection_id)
    if search:
        query = query.where(ERPProduct.name.ilike(f"%{search}%"))
    result = await db.execute(query)
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "connection_id": p.connection_id,
            "provider_type": p.provider_type,
            "external_id": p.external_id,
            "external_code": p.external_code,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "unit_price": p.unit_price,
            "cost_price": p.cost_price,
            "tax_rate": p.tax_rate,
            "barcode": p.barcode,
            "is_active": p.is_active,
            "last_synced_at": (
                p.last_synced_at.isoformat() if p.last_synced_at else None
            ),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in products
    ]


@router.get(
    "/health",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="ERP module health check",
)
async def health_check() -> dict:
    """Quick health check for the ERP sync module."""
    return {"status": "ok", "module": "erp_sync"}
