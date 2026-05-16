"""ERP business logic layer.

Provides service classes for:
- ERPConnectionService: CRUD with credential encryption
- ERPSyncService: Trigger sync, monitor progress, handle failures
- ERPHealthService: Health checks per connection
- ERPAuditService: Audit logging for all ERP operations
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.erp.constants import EncryptionConfig
from app.erp.models import (
    ERPConnection,
    ERPFieldMapping,
    ERPSyncJob,
    ERPSyncLog,
)
from app.exceptions import (
    AlreadyExistsError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.utils.encryption import fernet_decrypt, fernet_encrypt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encrypt_credential(value: Optional[str]) -> Optional[str]:
    """Encrypt a single credential value using Fernet."""
    if value is None:
        return None
    return fernet_encrypt(value)


def _decrypt_credential(value: Optional[str]) -> Optional[str]:
    """Decrypt a single credential value using Fernet."""
    if value is None:
        return None
    try:
        return fernet_decrypt(value)
    except Exception as exc:
        logger.warning("Failed to decrypt credential: %s", exc)
        return None


def _strip_sensitive_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive fields from a dict before returning in API response."""
    safe = dict(data)
    for key in EncryptionConfig.SENSITIVE_FIELDS:
        safe.pop(key, None)
    return safe


def _now_utc() -> datetime:
    """Current UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. ERP Connection Service
# ---------------------------------------------------------------------------

class ERPConnectionService:
    """Business logic for ERP connection CRUD with encrypted credentials."""

    @staticmethod
    async def create_connection(
        db: AsyncSession,
        company_id: int,
        branch_id: Optional[int],
        name: str,
        provider_type: str,
        base_url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        sync_enabled: bool = True,
        auto_sync_interval_minutes: int = 60,
    ) -> ERPConnection:
        """Create a new ERP connection with encrypted credentials.

        Args:
            db: Async database session.
            company_id: The owning company ID.
            branch_id: Optional branch ID.
            name: Display name for the connection.
            provider_type: ERP provider type.
            base_url: Base URL of the ERP API.
            api_key: Optional API key (encrypted at rest).
            api_secret: Optional API secret (encrypted at rest).
            webhook_secret: Optional webhook secret (encrypted at rest).
            sync_enabled: Whether auto-sync is enabled.
            auto_sync_interval_minutes: Auto-sync interval.

        Returns:
            The newly created ERPConnection model.
        """
        # Check for existing connection with same name in same company
        existing = await db.execute(
            select(ERPConnection).where(
                ERPConnection.company_id == company_id,
                ERPConnection.name == name,
            )
        )
        if existing.scalar_one_or_none():
            raise AlreadyExistsError(
                detail=f"ERP connection with name '{name}' already exists for this company"
            )

        now = _now_utc()

        connection = ERPConnection(
            company_id=company_id,
            branch_id=branch_id,
            name=name,
            provider_type=provider_type,
            base_url=base_url,
            api_key=_encrypt_credential(api_key),
            api_secret=_encrypt_credential(api_secret),
            webhook_secret=_encrypt_credential(webhook_secret),
            sync_enabled=sync_enabled,
            auto_sync_interval_minutes=auto_sync_interval_minutes,
            last_sync_status="never",
            last_sync_at=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        db.add(connection)
        await db.commit()
        await db.refresh(connection)

        logger.info("Created ERP connection %d (company=%d)", connection.id, company_id)
        return connection

    @staticmethod
    async def list_connections(
        db: AsyncSession,
        company_id: Optional[int],
        provider_type: Optional[str] = None,
        include_inactive: bool = False,
    ) -> Sequence[ERPConnection]:
        """List ERP connections with tenant isolation and optional filters.

        Args:
            db: Async database session.
            company_id: The company ID to filter by (None = all for super admin).
            provider_type: Optional filter by provider type.
            include_inactive: Whether to include deactivated connections.

        Returns:
            List of ERPConnection models.
        """
        query = select(ERPConnection)

        if company_id is not None:
            query = query.where(ERPConnection.company_id == company_id)

        if provider_type:
            query = query.where(ERPConnection.provider_type == provider_type)

        if not include_inactive:
            query = query.where(ERPConnection.is_active == True)

        query = query.order_by(desc(ERPConnection.created_at))

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_connection(
        db: AsyncSession,
        connection_id: int,
        company_id: Optional[int] = None,
    ) -> ERPConnection:
        """Get a single ERP connection by ID with tenant check.

        Args:
            db: Async database session.
            connection_id: The connection ID.
            company_id: Optional company ID for tenant isolation.

        Returns:
            The ERPConnection model.

        Raises:
            NotFoundError: If connection not found.
            AuthorizationError: If company_id doesn't match (tenant isolation).
        """
        result = await db.execute(
            select(ERPConnection).where(ERPConnection.id == connection_id)
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise NotFoundError(
                detail=f"ERP connection with ID '{connection_id}' not found"
            )

        if company_id is not None and connection.company_id != company_id:
            raise AuthorizationError(
                detail="You do not have access to this ERP connection"
            )

        return connection

    @staticmethod
    async def update_connection(
        db: AsyncSession,
        connection_id: int,
        company_id: Optional[int] = None,
        **updates: Any,
    ) -> ERPConnection:
        """Update an existing ERP connection. Only provided fields are updated.

        Args:
            db: Async database session.
            connection_id: The connection ID to update.
            company_id: Optional company ID for tenant isolation.
            **updates: Field values to update.

        Returns:
            The updated ERPConnection model.
        """
        connection = await ERPConnectionService.get_connection(
            db, connection_id, company_id
        )

        # Updatable non-sensitive fields
        plain_fields = [
            "name", "base_url", "sync_enabled", "is_active",
            "auto_sync_interval_minutes",
        ]
        for field in plain_fields:
            if field in updates and updates[field] is not None:
                setattr(connection, field, updates[field])

        # Sensitive fields - encrypt before storing
        sensitive_fields = ["api_key", "api_secret", "webhook_secret"]
        for field in sensitive_fields:
            if field in updates and updates[field] is not None:
                setattr(connection, field, _encrypt_credential(updates[field]))

        connection.updated_at = _now_utc()
        await db.commit()
        await db.refresh(connection)

        logger.info("Updated ERP connection %d", connection.id)
        return connection

    @staticmethod
    async def deactivate_connection(
        db: AsyncSession,
        connection_id: int,
        company_id: Optional[int] = None,
    ) -> ERPConnection:
        """Soft-delete (deactivate) an ERP connection.

        Args:
            db: Async database session.
            connection_id: The connection ID to deactivate.
            company_id: Optional company ID for tenant isolation.

        Returns:
            The deactivated ERPConnection model.
        """
        connection = await ERPConnectionService.get_connection(
            db, connection_id, company_id
        )

        connection.is_active = False
        connection.sync_enabled = False
        connection.updated_at = _now_utc()

        await db.commit()
        await db.refresh(connection)

        logger.info("Deactivated ERP connection %d", connection.id)
        return connection

    @staticmethod
    def to_response_dict(connection: ERPConnection) -> Dict[str, Any]:
        """Convert an ERPConnection model to a safe response dict."""
        return {
            "id": connection.id,
            "company_id": connection.company_id,
            "branch_id": connection.branch_id,
            "name": connection.name,
            "provider_type": connection.provider_type.value if hasattr(connection.provider_type, "value") else connection.provider_type,
            "base_url": connection.base_url,
            "sync_enabled": connection.sync_enabled,
            "auto_sync_interval_minutes": connection.auto_sync_interval_minutes,
            "last_sync_status": connection.last_sync_status.value if hasattr(connection.last_sync_status, "value") else connection.last_sync_status,
            "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
            "is_active": connection.is_active,
            "created_at": connection.created_at.isoformat() if connection.created_at else None,
            "updated_at": connection.updated_at.isoformat() if connection.updated_at else None,
        }


# ---------------------------------------------------------------------------
# 2. ERP Sync Service
# ---------------------------------------------------------------------------

class ERPSyncService:
    """Business logic for sync job lifecycle management."""

    @staticmethod
    async def create_sync_job(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        branch_id: Optional[int],
        entity_type: str,
        sync_type: str,
        created_by: int,
    ) -> ERPSyncJob:
        """Create a new sync job in 'queued' status.

        Args:
            db: Async database session.
            connection_id: The ERP connection ID.
            company_id: The company ID.
            branch_id: Optional branch ID.
            entity_type: Entity type to sync.
            sync_type: 'incremental' or 'full'.
            created_by: User ID who created the job.

        Returns:
            The newly created ERPSyncJob model.
        """
        now = _now_utc()

        job = ERPSyncJob(
            company_id=company_id,
            branch_id=branch_id,
            connection_id=connection_id,
            job_type="manual",
            entity_type=entity_type,
            status="queued",
            started_at=None,
            completed_at=None,
            records_total=0,
            records_processed=0,
            records_failed=0,
            error_message=None,
            retry_count=0,
            max_retries=3,
            next_page_token=None,
            created_at=now,
            updated_at=now,
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(
            "Created sync job %d for connection %d (entity=%s, type=%s)",
            job.id, connection_id, entity_type, sync_type,
        )
        return job

    @staticmethod
    async def get_sync_job(
        db: AsyncSession,
        job_id: int,
        company_id: Optional[int] = None,
    ) -> ERPSyncJob:
        """Get a sync job by ID with optional tenant check.

        Args:
            db: Async database session.
            job_id: The sync job ID.
            company_id: Optional company ID for tenant isolation.

        Returns:
            The ERPSyncJob model.

        Raises:
            NotFoundError: If job not found.
            AuthorizationError: If company_id doesn't match.
        """
        result = await db.execute(
            select(ERPSyncJob).where(ERPSyncJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            raise NotFoundError(
                detail=f"Sync job with ID '{job_id}' not found"
            )

        if company_id is not None and job.company_id != company_id:
            raise AuthorizationError(
                detail="You do not have access to this sync job"
            )

        return job

    @staticmethod
    async def cancel_sync_job(
        db: AsyncSession,
        job_id: int,
        company_id: Optional[int] = None,
    ) -> ERPSyncJob:
        """Cancel a sync job that is queued or running.

        Args:
            db: Async database session.
            job_id: The sync job ID.
            company_id: Optional company ID for tenant isolation.

        Returns:
            The updated ERPSyncJob model.

        Raises:
            ValidationError: If job is not in a cancellable state.
        """
        job = await ERPSyncService.get_sync_job(db, job_id, company_id)

        current_status = job.status
        if isinstance(current_status, str):
            status_val = current_status
        else:
            status_val = str(current_status.value) if hasattr(current_status, "value") else str(current_status)

        if status_val not in ("queued", "running"):
            raise ValidationError(
                detail=f"Cannot cancel sync job with status '{status_val}'. "
                       "Only 'queued' or 'running' jobs can be cancelled."
            )

        now = _now_utc()
        job.status = "cancelled"
        job.completed_at = now
        job.updated_at = now

        await db.commit()
        await db.refresh(job)

        logger.info("Cancelled sync job %d", job.id)
        return job

    @staticmethod
    async def get_sync_jobs(
        db: AsyncSession,
        company_id: Optional[int] = None,
        connection_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get sync jobs with optional filtering and pagination.

        Args:
            db: Async database session.
            company_id: Optional company ID for tenant isolation.
            connection_id: Optional filter by connection ID.
            entity_type: Optional filter by entity type.
            status: Optional filter by status.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Dict with 'jobs', 'total', 'page', 'page_size'.
        """
        query = select(ERPSyncJob)

        if company_id is not None:
            query = query.where(ERPSyncJob.company_id == company_id)
        if connection_id:
            query = query.where(ERPSyncJob.connection_id == connection_id)
        if entity_type:
            query = query.where(ERPSyncJob.entity_type == entity_type)
        if status:
            query = query.where(ERPSyncJob.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.order_by(desc(ERPSyncJob.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        jobs = result.scalars().all()

        return {
            "jobs": jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def job_to_response_dict(job: ERPSyncJob) -> Dict[str, Any]:
        """Convert an ERPSyncJob model to a response dict."""
        return {
            "job_id": job.id,
            "connection_id": job.connection_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "entity_type": job.entity_type.value if hasattr(job.entity_type, "value") else str(job.entity_type),
            "sync_type": "manual",
            "records_total": job.records_total,
            "records_processed": job.records_processed,
            "records_failed": job.records_failed,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }


# ---------------------------------------------------------------------------
# 3. ERP Sync Log Service
# ---------------------------------------------------------------------------

class ERPSyncLogService:
    """Business logic for sync log operations."""

    @staticmethod
    async def create_sync_log(
        db: AsyncSession,
        company_id: int,
        connection_id: int,
        job_id: Optional[int],
        log_level: str,
        entity_type: str,
        action: str,
        message: str,
        external_id: Optional[str] = None,
        internal_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ERPSyncLog:
        """Create a sync log entry.

        Args:
            db: Async database session.
            company_id: The company ID.
            connection_id: The ERP connection ID.
            job_id: Optional sync job ID.
            log_level: Log level (info, warning, error, debug).
            entity_type: Entity type.
            action: Action performed.
            message: Log message.
            external_id: Optional external ERP ID.
            internal_id: Optional internal ID.
            details: Optional JSON details.

        Returns:
            The newly created ERPSyncLog model.
        """
        log_entry = ERPSyncLog(
            company_id=company_id,
            connection_id=connection_id,
            job_id=job_id,
            log_level=log_level,
            entity_type=entity_type,
            action=action,
            external_id=external_id or "",
            internal_id=internal_id,
            message=message,
            details=details,
            created_at=_now_utc(),
        )

        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)

        return log_entry

    @staticmethod
    async def get_sync_logs(
        db: AsyncSession,
        company_id: Optional[int] = None,
        connection_id: Optional[int] = None,
        job_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        log_level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get sync logs with optional filtering and pagination.

        Args:
            db: Async database session.
            company_id: Optional company ID for tenant isolation.
            connection_id: Optional filter by connection ID.
            job_id: Optional filter by job ID.
            entity_type: Optional filter by entity type.
            log_level: Optional filter by log level.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Dict with 'logs', 'total', 'page', 'page_size'.
        """
        query = select(ERPSyncLog)

        if company_id is not None:
            query = query.where(ERPSyncLog.company_id == company_id)
        if connection_id:
            query = query.where(ERPSyncLog.connection_id == connection_id)
        if job_id:
            query = query.where(ERPSyncLog.job_id == job_id)
        if entity_type:
            query = query.where(ERPSyncLog.entity_type == entity_type)
        if log_level:
            query = query.where(ERPSyncLog.log_level == log_level)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.order_by(desc(ERPSyncLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        logs = result.scalars().all()

        return {
            "logs": logs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def log_to_response_dict(log: ERPSyncLog) -> Dict[str, Any]:
        """Convert an ERPSyncLog model to a response dict."""
        return {
            "id": log.id,
            "job_id": log.job_id,
            "connection_id": log.connection_id,
            "log_level": log.log_level.value if hasattr(log.log_level, "value") else str(log.log_level),
            "entity_type": log.entity_type,
            "action": log.action,
            "external_id": log.external_id,
            "message": log.message,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }


# ---------------------------------------------------------------------------
# 4. ERP Field Mapping Service
# ---------------------------------------------------------------------------

class ERPFieldMappingService:
    """Business logic for field mapping CRUD."""

    @staticmethod
    async def create_mapping(
        db: AsyncSession,
        company_id: int,
        connection_id: int,
        provider_type: str,
        entity_type: str,
        erp_field: str,
        internal_field: str,
        transformation: Optional[str] = None,
        is_required: bool = False,
        default_value: Optional[str] = None,
    ) -> ERPFieldMapping:
        """Create a new field mapping.

        Args:
            db: Async database session.
            company_id: The company ID.
            connection_id: The ERP connection ID.
            provider_type: ERP provider type.
            entity_type: Entity type being mapped.
            erp_field: Field name in the ERP system.
            internal_field: Corresponding internal field name.
            transformation: Optional transformation expression.
            is_required: Whether this field is required.
            default_value: Default value if ERP field is empty.

        Returns:
            The newly created ERPFieldMapping model.
        """
        now = _now_utc()

        mapping = ERPFieldMapping(
            company_id=company_id,
            connection_id=connection_id,
            provider_type=provider_type,
            entity_type=entity_type,
            erp_field=erp_field,
            internal_field=internal_field,
            transformation=transformation,
            is_required=is_required,
            default_value=default_value,
            created_at=now,
            updated_at=now,
        )

        db.add(mapping)
        await db.commit()
        await db.refresh(mapping)

        logger.info(
            "Created field mapping %d for connection %d (%s -> %s)",
            mapping.id, connection_id, erp_field, internal_field,
        )
        return mapping

    @staticmethod
    async def get_mapping(
        db: AsyncSession,
        mapping_id: int,
        company_id: Optional[int] = None,
    ) -> ERPFieldMapping:
        """Get a field mapping by ID with optional tenant check.

        Args:
            db: Async database session.
            mapping_id: The mapping ID.
            company_id: Optional company ID for tenant isolation.

        Returns:
            The ERPFieldMapping model.

        Raises:
            NotFoundError: If mapping not found.
            AuthorizationError: If company_id doesn't match.
        """
        result = await db.execute(
            select(ERPFieldMapping).where(ERPFieldMapping.id == mapping_id)
        )
        mapping = result.scalar_one_or_none()

        if not mapping:
            raise NotFoundError(
                detail=f"Field mapping with ID '{mapping_id}' not found"
            )

        if company_id is not None and mapping.company_id != company_id:
            raise AuthorizationError(
                detail="You do not have access to this field mapping"
            )

        return mapping

    @staticmethod
    async def list_mappings(
        db: AsyncSession,
        company_id: Optional[int] = None,
        connection_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> Sequence[ERPFieldMapping]:
        """List field mappings with optional filtering.

        Args:
            db: Async database session.
            company_id: Optional company ID for tenant isolation.
            connection_id: Optional filter by connection ID.
            entity_type: Optional filter by entity type.

        Returns:
            List of ERPFieldMapping models.
        """
        query = select(ERPFieldMapping)

        if company_id is not None:
            query = query.where(ERPFieldMapping.company_id == company_id)
        if connection_id:
            query = query.where(ERPFieldMapping.connection_id == connection_id)
        if entity_type:
            query = query.where(ERPFieldMapping.entity_type == entity_type)

        query = query.order_by(ERPFieldMapping.created_at)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_mapping(
        db: AsyncSession,
        mapping_id: int,
        company_id: Optional[int] = None,
        **updates: Any,
    ) -> ERPFieldMapping:
        """Update an existing field mapping. Only provided fields are changed.

        Args:
            db: Async database session.
            mapping_id: The mapping ID to update.
            company_id: Optional company ID for tenant isolation.
            **updates: Field values to update.

        Returns:
            The updated ERPFieldMapping model.
        """
        mapping = await ERPFieldMappingService.get_mapping(db, mapping_id, company_id)

        updatable_fields = [
            "entity_type", "erp_field", "internal_field",
            "transformation", "is_required", "default_value",
        ]
        for field in updatable_fields:
            if field in updates and updates[field] is not None:
                setattr(mapping, field, updates[field])

        mapping.updated_at = _now_utc()
        await db.commit()
        await db.refresh(mapping)

        logger.info("Updated field mapping %d", mapping.id)
        return mapping

    @staticmethod
    async def delete_mapping(
        db: AsyncSession,
        mapping_id: int,
        company_id: Optional[int] = None,
    ) -> None:
        """Delete a field mapping permanently.

        Args:
            db: Async database session.
            mapping_id: The mapping ID to delete.
            company_id: Optional company ID for tenant isolation.
        """
        mapping = await ERPFieldMappingService.get_mapping(db, mapping_id, company_id)

        await db.delete(mapping)
        await db.commit()

        logger.info("Deleted field mapping %d", mapping_id)

    @staticmethod
    def mapping_to_response_dict(mapping: ERPFieldMapping) -> Dict[str, Any]:
        """Convert an ERPFieldMapping model to a response dict."""
        return {
            "id": mapping.id,
            "connection_id": mapping.connection_id,
            "company_id": mapping.company_id,
            "entity_type": mapping.entity_type,
            "erp_field": mapping.erp_field,
            "internal_field": mapping.internal_field,
            "transformation": mapping.transformation,
            "is_required": mapping.is_required,
            "default_value": mapping.default_value,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
            "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
        }


# ---------------------------------------------------------------------------
# 5. ERP Health Service
# ---------------------------------------------------------------------------

class ERPHealthService:
    """Health check logic for ERP connections."""

    @staticmethod
    async def get_sync_health(
        db: AsyncSession,
        connection_id: int,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get health status for an ERP connection's sync operations.

        Args:
            db: Async database session.
            connection_id: The ERP connection ID.
            company_id: Optional company ID for tenant isolation.

        Returns:
            Dict with health check details.
        """
        # Get connection
        result = await db.execute(
            select(ERPConnection).where(ERPConnection.id == connection_id)
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise NotFoundError(
                detail=f"ERP connection with ID '{connection_id}' not found"
            )

        if company_id is not None and connection.company_id != company_id:
            raise AuthorizationError(
                detail="You do not have access to this ERP connection"
            )

        # Count pending/running jobs
        jobs_result = await db.execute(
            select(func.count()).select_from(ERPSyncJob)
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.status.in_(["queued", "running"]),
            )
        )
        pending_jobs = jobs_result.scalar() or 0

        # Count failed jobs in last 24 hours
        last_24h = _now_utc() - timedelta(hours=24)
        failed_result = await db.execute(
            select(func.count()).select_from(ERPSyncJob)
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.status == "failed",
                ERPSyncJob.created_at >= last_24h,
            )
        )
        failed_jobs_24h = failed_result.scalar() or 0

        # Determine overall status
        last_sync_status = connection.last_sync_status
        if hasattr(last_sync_status, "value"):
            last_sync_status = last_sync_status.value

        if failed_jobs_24h > 5 or last_sync_status == "failed":
            overall_status = "unhealthy"
        elif failed_jobs_24h > 0 or pending_jobs > 3:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "connection_id": connection.id,
            "connection_name": connection.name,
            "provider_type": connection.provider_type.value if hasattr(connection.provider_type, "value") else str(connection.provider_type),
            "status": overall_status,
            "connection_status": "ok" if last_sync_status == "success" else "error",
            "last_sync_status": str(last_sync_status),
            "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
            "pending_jobs": pending_jobs,
            "failed_jobs_last_24h": failed_jobs_24h,
            "message": f"Connection is {overall_status}",
        }

    @staticmethod
    async def get_sync_stats(
        db: AsyncSession,
        connection_id: int,
        company_id: Optional[int] = None,
        period_hours: int = 24,
    ) -> Dict[str, Any]:
        """Get sync statistics for an ERP connection.

        Args:
            db: Async database session.
            connection_id: The ERP connection ID.
            company_id: Optional company ID for tenant isolation.
            period_hours: Statistics period in hours.

        Returns:
            Dict with sync statistics.
        """
        # Get connection
        result = await db.execute(
            select(ERPConnection).where(ERPConnection.id == connection_id)
        )
        connection = result.scalar_one_or_none()

        if not connection:
            raise NotFoundError(
                detail=f"ERP connection with ID '{connection_id}' not found"
            )

        if company_id is not None and connection.company_id != company_id:
            raise AuthorizationError(
                detail="You do not have access to this ERP connection"
            )

        since = _now_utc() - timedelta(hours=period_hours)

        # Overall job counts
        total_result = await db.execute(
            select(func.count()).select_from(ERPSyncJob)
            .where(ERPSyncJob.connection_id == connection_id, ERPSyncJob.created_at >= since)
        )
        total_jobs = total_result.scalar() or 0

        completed_result = await db.execute(
            select(func.count()).select_from(ERPSyncJob)
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.created_at >= since,
                ERPSyncJob.status == "completed",
            )
        )
        completed_jobs = completed_result.scalar() or 0

        failed_result = await db.execute(
            select(func.count()).select_from(ERPSyncJob)
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.created_at >= since,
                ERPSyncJob.status == "failed",
            )
        )
        failed_jobs = failed_result.scalar() or 0

        cancelled_result = await db.execute(
            select(func.count()).select_from(ERPSyncJob)
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.created_at >= since,
                ERPSyncJob.status == "cancelled",
            )
        )
        cancelled_jobs = cancelled_result.scalar() or 0

        # Record counts
        records_result = await db.execute(
            select(
                func.coalesce(func.sum(ERPSyncJob.records_processed), 0),
                func.coalesce(func.sum(ERPSyncJob.records_failed), 0),
            )
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.created_at >= since,
            )
        )
        records_row = records_result.one_or_none()
        total_records_processed = records_row[0] if records_row else 0
        total_records_failed = records_row[1] if records_row else 0

        # Per-entity breakdown
        entity_result = await db.execute(
            select(
                ERPSyncJob.entity_type,
                func.coalesce(func.sum(ERPSyncJob.records_processed), 0),
                func.coalesce(func.sum(ERPSyncJob.records_failed), 0),
                func.count(),
            )
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.created_at >= since,
            )
            .group_by(ERPSyncJob.entity_type)
        )

        entity_breakdown: Dict[str, Dict[str, int]] = {}
        for row in entity_result.all():
            entity_type = row[0]
            entity_str = entity_type.value if hasattr(entity_type, "value") else str(entity_type)
            entity_breakdown[entity_str] = {
                "processed": row[1],
                "failed": row[2],
                "total": row[3],
            }

        # Duration stats
        duration_result = await db.execute(
            select(
                func.coalesce(func.avg(
                    func.extract("epoch", ERPSyncJob.completed_at - ERPSyncJob.started_at)
                ), 0),
            )
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.created_at >= since,
                ERPSyncJob.completed_at.isnot(None),
                ERPSyncJob.started_at.isnot(None),
            )
        )
        avg_duration = duration_result.scalar() or 0

        last_duration = None
        last_job_result = await db.execute(
            select(ERPSyncJob)
            .where(
                ERPSyncJob.connection_id == connection_id,
                ERPSyncJob.completed_at.isnot(None),
                ERPSyncJob.started_at.isnot(None),
            )
            .order_by(desc(ERPSyncJob.completed_at))
            .limit(1)
        )
        last_job = last_job_result.scalar_one_or_none()
        if last_job:
            last_duration = (
                last_job.completed_at - last_job.started_at
            ).total_seconds() if last_job.completed_at and last_job.started_at else None

        return {
            "connection_id": connection.id,
            "connection_name": connection.name,
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "cancelled_jobs": cancelled_jobs,
            "total_records_processed": total_records_processed,
            "total_records_failed": total_records_failed,
            "entity_breakdown": entity_breakdown,
            "period_hours": period_hours,
            "last_sync_duration_seconds": last_duration,
            "average_sync_duration_seconds": float(avg_duration) if avg_duration else None,
        }


# ---------------------------------------------------------------------------
# 6. ERP Audit Service
# ---------------------------------------------------------------------------

class ERPAuditService:
    """Audit logging for all ERP operations via sync logs."""

    @staticmethod
    async def log_connection_created(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        performed_by: Optional[int] = None,
    ) -> ERPSyncLog:
        """Audit log: connection created."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=None,
            log_level="info",
            entity_type="connection",
            action="create",
            message=f"ERP connection {connection_id} created",
            details={"performed_by": performed_by},
        )

    @staticmethod
    async def log_connection_updated(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        performed_by: Optional[int] = None,
        changed_fields: Optional[List[str]] = None,
    ) -> ERPSyncLog:
        """Audit log: connection updated."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=None,
            log_level="info",
            entity_type="connection",
            action="update",
            message=f"ERP connection {connection_id} updated",
            details={"performed_by": performed_by, "changed_fields": changed_fields or []},
        )

    @staticmethod
    async def log_connection_deactivated(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        performed_by: Optional[int] = None,
    ) -> ERPSyncLog:
        """Audit log: connection deactivated."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=None,
            log_level="warning",
            entity_type="connection",
            action="deactivate",
            message=f"ERP connection {connection_id} deactivated",
            details={"performed_by": performed_by},
        )

    @staticmethod
    async def log_sync_triggered(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        job_id: int,
        entity_type: str,
        sync_type: str,
        performed_by: Optional[int] = None,
    ) -> ERPSyncLog:
        """Audit log: sync triggered."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=job_id,
            log_level="info",
            entity_type=entity_type,
            action="sync_trigger",
            message=f"Sync triggered: {entity_type} ({sync_type}) for connection {connection_id}",
            details={"sync_type": sync_type, "performed_by": performed_by},
        )

    @staticmethod
    async def log_sync_completed(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        job_id: int,
        entity_type: str,
        records_processed: int,
        records_failed: int,
    ) -> ERPSyncLog:
        """Audit log: sync completed."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=job_id,
            log_level="info",
            entity_type=entity_type,
            action="sync_complete",
            message=f"Sync completed: {records_processed} processed, {records_failed} failed",
            details={
                "records_processed": records_processed,
                "records_failed": records_failed,
            },
        )

    @staticmethod
    async def log_sync_failed(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        job_id: int,
        entity_type: str,
        error_message: str,
    ) -> ERPSyncLog:
        """Audit log: sync failed."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=job_id,
            log_level="error",
            entity_type=entity_type,
            action="sync_fail",
            message=f"Sync failed: {error_message}",
            details={"error": error_message},
        )

    @staticmethod
    async def log_webhook_received(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        event: str,
        payload_size: int = 0,
    ) -> ERPSyncLog:
        """Audit log: webhook received."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=None,
            log_level="info",
            entity_type=event.split(".")[0] if "." in event else "unknown",
            action="webhook",
            message=f"Webhook received: {event}",
            details={"event": event, "payload_size": payload_size},
        )

    @staticmethod
    async def log_field_mapping_change(
        db: AsyncSession,
        connection_id: int,
        company_id: int,
        mapping_id: int,
        action: str,
        performed_by: Optional[int] = None,
    ) -> ERPSyncLog:
        """Audit log: field mapping change."""
        return await ERPSyncLogService.create_sync_log(
            db=db,
            company_id=company_id,
            connection_id=connection_id,
            job_id=None,
            log_level="info",
            entity_type="field_mapping",
            action=action,
            message=f"Field mapping {mapping_id} {action}",
            details={"mapping_id": mapping_id, "performed_by": performed_by},
        )
