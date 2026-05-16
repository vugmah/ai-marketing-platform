"""ERP Sync Service - Core synchronization engine.

Handles all sync operations:

* Manual sync (triggered via API)
* Scheduled sync (triggered via Celery)
* Webhook-triggered sync (triggered via webhook)
* Incremental sync (only changed records since last sync)
* Full sync (all records)

All sync operations use conflict-aware upserts and support multiple
entity types: products, inventory, sales_orders, customers, invoices, payments.

Features:
- Field mapping from DB (ERPFieldMapping) applied during sync
- Conflict resolution: last-write-wins, merge, local-wins, erp-wins
- Customer deduplication by email (merge strategy)
- Invoice status mapping and order linking
- Invoice linking to payments
- Retry with exponential backoff
"""

import asyncio
import functools
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.erp.connector_base import ERPConnectorBase
from app.erp.connectors import get_connector
from app.erp.constants import ConflictStrategy, RetryConfig
from app.erp.models import (
    ERPConnection,
    ERPCustomer,
    ERPFieldMapping,
    ERPInventory,
    ERPInvoice,
    ERPPayment,
    ERPProduct,
    ERPSalesOrder,
    ERPSyncJob,
    ERPSyncLog,
)
from app.erp.service import ERPAuditService, ERPSyncLogService
from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry decorator with exponential backoff
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[F], F]:
    """Decorator for retrying async functions with exponential backoff.

    The delay after attempt *n* (0-indexed) is
    ``min(base_delay * 2**n, max_delay)`` seconds.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs: %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
            return None  # pragma: no cover

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Field Mapping Engine
# ---------------------------------------------------------------------------

class FieldMappingEngine:
    """Applies DB-stored field mappings during sync operations.

    Loads field mappings from erp_field_mappings table and uses them
    to transform ERP field names to internal field names.
    """

    def __init__(self, mappings: List[ERPFieldMapping]):
        self.mappings = mappings
        # Build lookup dict: erp_field -> internal_field
        self._forward_map: Dict[str, str] = {}
        # Build reverse lookup: internal_field -> erp_field
        self._reverse_map: Dict[str, str] = {}
        # Default values per internal field
        self._defaults: Dict[str, str] = {}
        for m in mappings:
            self._forward_map[m.erp_field] = m.internal_field
            self._reverse_map[m.internal_field] = m.erp_field
            if m.default_value is not None:
                self._defaults[m.internal_field] = m.default_value

    def apply(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field mappings to an ERP data item.

        Maps erp_field names to internal_field names and fills
        required fields with default values.

        Args:
            item: Raw dict from ERP API.

        Returns:
            Dict with internal field names.
        """
        if not self._forward_map:
            return dict(item)

        mapped: Dict[str, Any] = {}
        for erp_key, value in item.items():
            internal_key = self._forward_map.get(erp_key, erp_key)
            mapped[internal_key] = value

        # Fill required fields with defaults
        for internal_field, default in self._defaults.items():
            if internal_field not in mapped or mapped[internal_field] is None:
                mapped[internal_field] = default

        return mapped

    def get_internal(self, erp_field: str) -> str:
        """Get the internal field name for an ERP field."""
        return self._forward_map.get(erp_field, erp_field)

    def get_erp_field(self, internal_field: str) -> str:
        """Get the ERP field name for an internal field."""
        return self._reverse_map.get(internal_field, internal_field)

    def has_mapping(self, erp_field: str) -> bool:
        """Check if an ERP field has a mapping."""
        return erp_field in self._forward_map


async def _load_field_mappings(
    db: AsyncSession,
    connection_id: int,
    entity_type: str,
) -> FieldMappingEngine:
    """Load field mappings from DB for a connection and entity type."""
    result = await db.execute(
        select(ERPFieldMapping).where(
            ERPFieldMapping.connection_id == connection_id,
            ERPFieldMapping.entity_type == entity_type,
        )
    )
    mappings = result.scalars().all()
    return FieldMappingEngine(list(mappings))


# ---------------------------------------------------------------------------
# Invoice Status Mapper
# ---------------------------------------------------------------------------

class InvoiceStatusMapper:
    """Maps ERP-specific invoice statuses to normalized internal statuses.

    Supports configurable status mapping via STATUS_MAP dict.
    Unknown statuses are passed through as-is.
    """

    # Default ERP -> Internal status mapping
    DEFAULT_STATUS_MAP: Dict[str, str] = {
        "draft": "draft",
        "open": "open",
        "sent": "sent",
        "paid": "paid",
        "partially_paid": "partial",
        "overdue": "overdue",
        "cancelled": "cancelled",
        "void": "cancelled",
        "refunded": "refunded",
        "credit_note": "credit_note",
        # Turkish ERP common statuses
        "taslak": "draft",
        "acik": "open",
        "gonderildi": "sent",
        "odendi": "paid",
        "kismi_odendi": "partial",
        "gecikmis": "overdue",
        "iptal": "cancelled",
    }

    def __init__(self, custom_map: Optional[Dict[str, str]] = None):
        self._map: Dict[str, str] = {}
        self._map.update(self.DEFAULT_STATUS_MAP)
        if custom_map:
            self._map.update(custom_map)

    def map_status(self, erp_status: str) -> str:
        """Map an ERP status to an internal normalized status.

        Args:
            erp_status: Raw status string from ERP.

        Returns:
            Normalized internal status. Unknown values returned as-is.
        """
        if not erp_status:
            return "unknown"
        key = erp_status.lower().strip()
        return self._map.get(key, key)


# ---------------------------------------------------------------------------
# Top-level sync API functions (callable from router, service layer, etc.)
# ---------------------------------------------------------------------------

async def inventory_sync(
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
) -> Dict[str, Any]:
    """Sync inventory from ERP for a given connection.

    Uses conflict-aware upserts with last-write-wins by default.
    Applies field mappings from DB before upsert.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts.

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type="inventory",
        conflict_strategy=conflict_strategy,
    )


async def product_sync(
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
) -> Dict[str, Any]:
    """Sync products from ERP for a given connection with dedup by external_id.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts.

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type="products",
        conflict_strategy=conflict_strategy,
    )


async def customer_sync(
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.MERGE,
) -> Dict[str, Any]:
    """Sync customers from ERP for a given connection with merge strategy.

    Uses email-based deduplication (MERGE strategy): if a customer with
    the same email already exists for this connection, fields are merged.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts (default: MERGE).

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type="customers",
        conflict_strategy=conflict_strategy,
    )


async def invoice_sync(
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
) -> Dict[str, Any]:
    """Sync invoices from ERP for a given connection with order linking.

    Links invoices to sales_orders via external_order_id lookup.
    Applies invoice status normalization mapping.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts.

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type="invoices",
        conflict_strategy=conflict_strategy,
    )


async def sales_order_sync(
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
) -> Dict[str, Any]:
    """Sync sales orders from ERP for a given connection.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts.

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type="sales_orders",
        conflict_strategy=conflict_strategy,
    )


async def payment_sync(
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
) -> Dict[str, Any]:
    """Sync payments from ERP for a given connection.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts.

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type="payments",
        conflict_strategy=conflict_strategy,
    )


async def sync_with_conflict_handling(
    entity_type: str,
    connection_id: int,
    db: AsyncSession,
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
) -> Dict[str, Any]:
    """Generic sync with configurable conflict resolution.

    Args:
        entity_type: Type of entity to sync.
        connection_id: The ERP connection ID.
        db: Async database session.
        conflict_strategy: How to resolve conflicts.

    Returns:
        Dict with 'processed', 'failed', 'status' keys.
    """
    engine = SyncEngine()
    return await engine.sync_entity(
        connection_id=connection_id,
        db=db,
        entity_type=entity_type,
        conflict_strategy=conflict_strategy,
    )


def validate_webhook_payload(
    provider_type: str,
    payload: Dict[str, Any],
    secret: str,
    signature: Optional[str] = None,
) -> bool:
    """Validate a webhook payload signature and structure.

    Args:
        provider_type: The ERP provider type.
        payload: The webhook payload dict.
        secret: The webhook secret for signature validation.
        signature: Optional signature from the request header.

    Returns:
        True if the payload is valid, False otherwise.
    """
    # Check payload structure
    if not isinstance(payload, dict):
        logger.warning("Webhook payload is not a dict")
        return False

    if "event" not in payload:
        logger.warning("Webhook payload missing 'event' field")
        return False

    # Validate signature if provided
    if signature and secret:
        try:
            payload_str = json.dumps(payload, sort_keys=True)
            expected = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256,
            ).hexdigest()
            is_valid = hmac.compare_digest(expected, signature)
            if not is_valid:
                logger.warning("Webhook signature mismatch for provider %s", provider_type)
            return is_valid
        except Exception as exc:
            logger.error("Webhook signature validation failed: %s", exc)
            return False

    # No signature required - accept
    return True


async def get_sync_health(
    connection_id: int,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Get health check for sync status of a connection.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.

    Returns:
        Dict with health status information.
    """
    from app.erp.service import ERPHealthService

    return await ERPHealthService.get_sync_health(db, connection_id)


async def get_sync_stats(
    connection_id: int,
    db: AsyncSession,
    period_hours: int = 24,
) -> Dict[str, Any]:
    """Get sync statistics for a connection.

    Args:
        connection_id: The ERP connection ID.
        db: Async database session.
        period_hours: Statistics period in hours.

    Returns:
        Dict with sync statistics.
    """
    from app.erp.service import ERPHealthService

    return await ERPHealthService.get_sync_stats(db, connection_id, period_hours=period_hours)


# ---------------------------------------------------------------------------
# Sync Engine
# ---------------------------------------------------------------------------

class SyncEngine:
    """Core sync engine that orchestrates ERP data synchronization.

    Features:
    - Field mapping from DB per entity type
    - Conflict resolution strategies
    - Customer dedup by email
    - Invoice status normalization
    - Order linking for invoices
    - Audit logging per sync operation
    """

    ENTITY_HANDLERS = {
        "products": "_sync_products",
        "inventory": "_sync_inventory",
        "sales_orders": "_sync_sales_orders",
        "customers": "_sync_customers",
        "invoices": "_sync_invoices",
        "payments": "_sync_payments",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_entity(
        self,
        connection_id: int,
        db: AsyncSession,
        entity_type: str,
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        job_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sync a single entity type for a connection.

        Args:
            connection_id: The ERP connection ID.
            db: Async database session.
            entity_type: Entity type to sync.
            conflict_strategy: Conflict resolution strategy.
            job_id: Optional sync job ID for per-record audit correlation.

        Returns:
            Dict with 'processed', 'failed', 'status' keys.
        """
        result: Dict[str, Any] = {
            "status": "completed",
            "records_processed": 0,
            "records_failed": 0,
            "records_skipped": 0,
            "error": None,
        }
        connection = None

        try:
            # Load connection config
            conn_result = await db.execute(
                select(ERPConnection).where(ERPConnection.id == connection_id)
            )
            connection = conn_result.scalar_one_or_none()

            if not connection:
                raise ValueError(f"Connection {connection_id} not found")

            if not connection.is_active:
                raise ValidationError(
                    detail=f"Connection {connection_id} is not active"
                )

            # Build connector instance
            config = {
                "base_url": connection.base_url,
                "api_key": connection.api_key,
                "api_secret": connection.api_secret,
            }
            connector = get_connector(connection.provider_type, config)

            # Authenticate
            if not await connector.authenticate():
                raise ConnectionError(
                    f"Failed to authenticate with {connection.provider_type}"
                )

            # Load field mappings for this entity type
            field_mapping = await _load_field_mappings(
                db, connection_id, entity_type
            )

            # Determine 'since' timestamp for incremental sync
            since: Optional[str] = None
            if connection.last_sync_at:
                since = connection.last_sync_at.isoformat()

            # Route to entity handler
            handler_name = self.ENTITY_HANDLERS.get(entity_type)
            if handler_name:
                handler = getattr(self, handler_name)
                entity_result = await handler(
                    connector, connection, db, since, conflict_strategy,
                    field_mapping, job_id=job_id
                )
                result["records_processed"] = entity_result.get("processed", 0)
                result["records_failed"] = entity_result.get("failed", 0)
                result["records_skipped"] = entity_result.get("skipped", 0)
            else:
                raise ValueError(f"Unknown entity type: {entity_type}")

            # Update connection sync state
            connection.last_sync_at = datetime.now(timezone.utc)
            connection.last_sync_status = "success"
            connection.last_sync_error = None
            await db.commit()

            # Audit log: sync completed
            await ERPSyncLogService.create_sync_log(
                db=db,
                company_id=connection.company_id,
                connection_id=connection_id,
                job_id=job_id,
                log_level="info",
                entity_type=entity_type,
                action="sync_complete",
                message=f"Sync completed: {result['records_processed']} processed, {result['records_failed']} failed, {result['records_skipped']} skipped",
                details={"strategy": conflict_strategy.value},
            )

            logger.info(
                "Sync entity '%s' for connection %d completed: %d processed, %d failed, %d skipped",
                entity_type,
                connection_id,
                result["records_processed"],
                result["records_failed"],
                result["records_skipped"],
            )

        except Exception as exc:
            logger.error(
                "Sync entity '%s' for connection %d failed: %s",
                entity_type,
                connection_id,
                exc,
                exc_info=True,
            )
            result["status"] = "failed"
            result["error"] = str(exc)

            # Audit log: sync failed
            try:
                await ERPSyncLogService.create_sync_log(
                    db=db,
                    company_id=connection.company_id if connection else 0,
                    connection_id=connection_id,
                    job_id=job_id,
                    log_level="error",
                    entity_type=entity_type,
                    action="sync_fail",
                    message=f"Sync failed: {str(exc)}",
                    details={"error": str(exc), "strategy": conflict_strategy.value},
                )
            except Exception:
                pass

            # Best-effort status update on the connection row
            try:
                conn_result = await db.execute(
                    select(ERPConnection).where(
                        ERPConnection.id == connection_id
                    )
                )
                connection = conn_result.scalar_one_or_none()
                if connection:
                    connection.last_sync_status = "failed"
                    connection.last_sync_error = str(exc)
                    await db.commit()
            except Exception:
                pass

        return result

    @with_retry(max_retries=3, base_delay=1.0)
    async def run_sync(
        self,
        job_id: int,
        connection_id: int,
        entity_type: str,
        sync_type: str = "incremental",
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ) -> Dict[str, Any]:
        """Execute a sync job. This is the main entry point.

        Args:
            job_id: The ERPSyncJob primary key.
            connection_id: The ERPConnection primary key.
            entity_type: What to sync ("products", "inventory",
                         "all", ...).
            sync_type: "incremental" or "full".
            conflict_strategy: How to resolve conflicts.

        Returns:
            A dict with "status", "records_processed",
            "records_failed", and "error".
        """
        result: Dict[str, Any] = {
            "status": "completed",
            "records_processed": 0,
            "records_failed": 0,
            "error": None,
        }

        try:
            async with get_db_context() as db:
                # 1. Load connection config
                conn_result = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connection = conn_result.scalar_one_or_none()

                if not connection:
                    raise ValueError(f"Connection {connection_id} not found")

                # 2. Update job status to running
                job_result = await db.execute(
                    select(ERPSyncJob).where(ERPSyncJob.id == job_id)
                )
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = "running"
                    job.started_at = datetime.now(timezone.utc)
                    await db.commit()

                # 3. Build connector instance
                config = {
                    "base_url": connection.base_url,
                    "api_key": connection.api_key,
                    "api_secret": connection.api_secret,
                }
                connector = get_connector(connection.provider_type, config)

                # 4. Authenticate
                if not await connector.authenticate():
                    raise ConnectionError(
                        f"Failed to authenticate with {connection.provider_type}"
                    )

                # 5. Determine entities and 'since' timestamp
                entities = (
                    list(self.ENTITY_HANDLERS.keys())
                    if entity_type == "all"
                    else [entity_type]
                )

                since: Optional[str] = None
                if sync_type == "incremental" and connection.last_sync_at:
                    since = connection.last_sync_at.isoformat()

                # 6. Sync each entity
                for entity in entities:
                    handler_name = self.ENTITY_HANDLERS.get(entity)
                    if handler_name:
                        handler = getattr(self, handler_name)

                        # Load field mappings for this entity
                        field_mapping = await _load_field_mappings(
                            db, connection_id, entity
                        )

                        entity_result = await handler(
                            connector, connection, db, since, conflict_strategy,
                            field_mapping, job_id=job_id
                        )
                        result["records_processed"] += entity_result.get(
                            "processed", 0
                        )
                        result["records_failed"] += entity_result.get(
                            "failed", 0
                        )

                # 7. Update connection sync state
                connection.last_sync_at = datetime.now(timezone.utc)
                connection.last_sync_status = "success"
                connection.last_sync_error = None

                # 8. Update job to completed
                if job:
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.records_processed = result["records_processed"]
                    job.records_failed = result["records_failed"]

                await db.commit()

                # Audit log: sync job completed
                await ERPSyncLogService.create_sync_log(
                    db=db,
                    company_id=connection.company_id,
                    connection_id=connection_id,
                    job_id=job_id,
                    log_level="info",
                    entity_type=entity_type,
                    action="sync_complete",
                    message=f"Sync job {job_id} completed: {result['records_processed']} processed, {result['records_failed']} failed",
                    details={"sync_type": sync_type, "strategy": conflict_strategy.value},
                )

                logger.info(
                    "Sync job %d completed: %d processed, %d failed",
                    job_id,
                    result["records_processed"],
                    result["records_failed"],
                )

        except NotImplementedError as exc:
            # Future ERP provider (stub) - return clear 501 message
            err_msg = str(exc)
            logger.error("Sync job %d blocked: %s", job_id, err_msg)
            result["status"] = "failed"
            result["error"] = err_msg

            # Best-effort status update
            try:
                async with get_db_context() as db:
                    job_result = await db.execute(
                        select(ERPSyncJob).where(ERPSyncJob.id == job_id)
                    )
                    job = job_result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.error_message = err_msg
                        job.completed_at = datetime.now(timezone.utc)

                    conn_result = await db.execute(
                        select(ERPConnection).where(
                            ERPConnection.id == connection_id
                        )
                    )
                    connection = conn_result.scalar_one_or_none()
                    if connection:
                        connection.last_sync_status = "failed"
                        connection.last_sync_error = err_msg

                    await db.commit()
            except Exception:
                pass

        except Exception as exc:
            logger.error("Sync job %d failed: %s", job_id, exc)
            result["status"] = "failed"
            result["error"] = str(exc)

            # Best-effort status update
            try:
                async with get_db_context() as db:
                    # Update job to failed
                    job_result = await db.execute(
                        select(ERPSyncJob).where(ERPSyncJob.id == job_id)
                    )
                    job = job_result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.error_message = str(exc)
                        job.completed_at = datetime.now(timezone.utc)

                    # Update connection status
                    conn_result = await db.execute(
                        select(ERPConnection).where(
                            ERPConnection.id == connection_id
                        )
                    )
                    connection = conn_result.scalar_one_or_none()
                    if connection:
                        connection.last_sync_status = "failed"
                        connection.last_sync_error = str(exc)

                    await db.commit()
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # Entity sync handlers
    # ------------------------------------------------------------------

    async def _sync_products(
        self,
        connector: ERPConnectorBase,
        connection: Any,
        db: AsyncSession,
        since: Optional[str],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        field_mapping: Optional[FieldMappingEngine] = None,
        job_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync products with pagination and conflict-aware upserts."""
        result = {"processed": 0, "failed": 0}

        try:
            page = 1
            while True:
                data = await connector.get_products(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        # Apply field mappings
                        if field_mapping:
                            item = field_mapping.apply(item)
                        await self._upsert_product(
                            db, connection, item, conflict_strategy
                        )
                        result["processed"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync product %s: %s",
                            item.get("id"),
                            exc,
                        )
                        result["failed"] += 1

                # Commit after each page to keep transactions small
                await db.commit()

                next_page = data.get("next_page") or data.get("next")
                if not next_page or page >= 100:  # Safety guard
                    break
                page += 1

        except Exception as exc:
            logger.error("Product sync failed: %s", exc)
            result["failed"] += 1

        return result

    async def _sync_inventory(
        self,
        connector: ERPConnectorBase,
        connection: Any,
        db: AsyncSession,
        since: Optional[str],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        field_mapping: Optional[FieldMappingEngine] = None,
        job_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync inventory levels with conflict-aware upserts.

        Applies field mappings from DB before upsert operations.
        Uses last-write-wins by default for inventory conflicts.
        Per-record audit logging tracks every upsert decision.
        """
        result = {"processed": 0, "failed": 0, "skipped": 0}

        try:
            warehouse_codes = self._get_warehouse_codes(connection)
            targets = warehouse_codes if warehouse_codes else [None]

            for warehouse in targets:
                data = await connector.get_inventory(warehouse_code=warehouse)
                items = self._extract_items(data)

                for item in items:
                    try:
                        # Enrich item with warehouse code if not present
                        if warehouse and not item.get("warehouse_code"):
                            item["warehouse_code"] = warehouse

                        # Apply field mappings
                        if field_mapping:
                            item = field_mapping.apply(item)

                        action = await self._upsert_inventory(
                            db, connection, item, conflict_strategy, job_id=job_id
                        )
                        if action in ("updated", "inserted"):
                            result["processed"] += 1
                        elif action == "skipped":
                            result["skipped"] = result.get("skipped", 0) + 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync inventory %s: %s",
                            item.get("product_id"),
                            exc,
                        )
                        result["failed"] += 1

                await db.commit()

        except Exception as exc:
            logger.error("Inventory sync failed: %s", exc)
            result["failed"] += 1

        return result

    async def _sync_sales_orders(
        self,
        connector: ERPConnectorBase,
        connection: Any,
        db: AsyncSession,
        since: Optional[str],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        field_mapping: Optional[FieldMappingEngine] = None,
        job_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync sales orders with pagination and conflict-aware upserts."""
        result = {"processed": 0, "failed": 0}

        try:
            page = 1
            while True:
                data = await connector.get_sales_orders(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        if field_mapping:
                            item = field_mapping.apply(item)
                        await self._upsert_sales_order(
                            db, connection, item, conflict_strategy
                        )
                        result["processed"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync sales order %s: %s",
                            item.get("id"),
                            exc,
                        )
                        result["failed"] += 1

                await db.commit()

                next_page = data.get("next_page") or data.get("next")
                if not next_page or page >= 100:
                    break
                page += 1

        except Exception as exc:
            logger.error("Sales order sync failed: %s", exc)
            result["failed"] += 1

        return result

    async def _sync_customers(
        self,
        connector: ERPConnectorBase,
        connection: Any,
        db: AsyncSession,
        since: Optional[str],
        conflict_strategy: ConflictStrategy = ConflictStrategy.MERGE,
        field_mapping: Optional[FieldMappingEngine] = None,
        job_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync customers with merge-based conflict resolution.

        Uses email-based deduplication: if a customer with the same email
        already exists for this connection, the record is merged rather
        than creating a duplicate. This handles ERPs that use different
        customer IDs for the same person.
        """
        result = {"processed": 0, "failed": 0, "merged": 0, "deduped": 0}

        try:
            page = 1
            while True:
                data = await connector.get_customers(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        if field_mapping:
                            item = field_mapping.apply(item)

                        merge_result = await self._upsert_customer(
                            db, connection, item, conflict_strategy
                        )

                        if merge_result == "merged":
                            result["merged"] = result.get("merged", 0) + 1
                        elif merge_result == "deduped":
                            result["deduped"] = result.get("deduped", 0) + 1
                        else:
                            result["processed"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync customer %s: %s",
                            item.get("id"),
                            exc,
                        )
                        result["failed"] += 1

                await db.commit()

                next_page = data.get("next_page") or data.get("next")
                if not next_page or page >= 100:
                    break
                page += 1

        except Exception as exc:
            logger.error("Customer sync failed: %s", exc)
            result["failed"] += 1

        return result

    async def _sync_invoices(
        self,
        connector: ERPConnectorBase,
        connection: Any,
        db: AsyncSession,
        since: Optional[str],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        field_mapping: Optional[FieldMappingEngine] = None,
        job_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync invoices with order linking and status mapping.

        Links invoices to sales_orders via external_order_id lookup.
        Applies invoice status normalization using InvoiceStatusMapper.
        """
        result = {"processed": 0, "failed": 0}
        status_mapper = InvoiceStatusMapper()

        try:
            page = 1
            while True:
                data = await connector.get_invoices(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        if field_mapping:
                            item = field_mapping.apply(item)

                        # Normalize invoice status
                        raw_status = item.get("status", "")
                        item["status"] = status_mapper.map_status(raw_status)

                        await self._upsert_invoice(
                            db, connection, item, conflict_strategy
                        )
                        result["processed"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync invoice %s: %s",
                            item.get("id"),
                            exc,
                        )
                        result["failed"] += 1

                await db.commit()

                next_page = data.get("next_page") or data.get("next")
                if not next_page or page >= 100:
                    break
                page += 1

        except Exception as exc:
            logger.error("Invoice sync failed: %s", exc)
            result["failed"] += 1

        return result

    async def _sync_payments(
        self,
        connector: ERPConnectorBase,
        connection: Any,
        db: AsyncSession,
        since: Optional[str],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        field_mapping: Optional[FieldMappingEngine] = None,
        job_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync payments with pagination and conflict-aware upserts."""
        result = {"processed": 0, "failed": 0}

        try:
            page = 1
            while True:
                data = await connector.get_payments(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        if field_mapping:
                            item = field_mapping.apply(item)
                        await self._upsert_payment(
                            db, connection, item, conflict_strategy
                        )
                        result["processed"] += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to sync payment %s: %s",
                            item.get("id"),
                            exc,
                        )
                        result["failed"] += 1

                await db.commit()

                next_page = data.get("next_page") or data.get("next")
                if not next_page or page >= 100:
                    break
                page += 1

        except Exception as exc:
            logger.error("Payment sync failed: %s", exc)
            result["failed"] += 1

        return result

    # ------------------------------------------------------------------
    # Upsert helpers with conflict resolution
    # ------------------------------------------------------------------

    async def _upsert_product(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ) -> None:
        """Insert or update a product record with conflict resolution."""
        external_id = str(item.get("id", item.get("product_id", "")))

        result = await db.execute(
            select(ERPProduct).where(
                ERPProduct.connection_id == connection.id,
                ERPProduct.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if conflict_strategy == ConflictStrategy.LOCAL_WINS:
                return

            # Apply updates based on conflict strategy
            existing.name = item.get("name", existing.name)
            existing.description = item.get("description", existing.description)
            existing.unit_price = self._to_float(
                item.get("price", item.get("unit_price", existing.unit_price))
            )
            existing.cost_price = (
                self._to_float(item["cost_price"])
                if item.get("cost_price") is not None
                else existing.cost_price
            )
            existing.category = item.get(
                "category", item.get("category_name", existing.category)
            )
            existing.barcode = item.get(
                "barcode", item.get("ean", existing.barcode)
            )
            existing.tax_rate = self._to_float(
                item.get("tax_rate", item.get("vat_rate", existing.tax_rate))
            )
            existing.is_active = item.get(
                "is_active", item.get("active", existing.is_active)
            )
            existing.raw_data = item
            existing.last_synced_at = datetime.now(timezone.utc)
        else:
            # Insert new product
            new_product = ERPProduct(
                company_id=connection.company_id,
                branch_id=connection.branch_id,
                connection_id=connection.id,
                provider_type=connection.provider_type,
                external_id=external_id,
                external_code=item.get("code", item.get("sku", "")),
                name=item.get("name", "Unknown"),
                description=item.get("description"),
                category=item.get("category", item.get("category_name")),
                unit_price=self._to_float(
                    item.get("price", item.get("unit_price", 0))
                ),
                cost_price=(
                    self._to_float(item["cost_price"])
                    if item.get("cost_price") is not None
                    else None
                ),
                tax_rate=self._to_float(
                    item.get("tax_rate", item.get("vat_rate", 0))
                ),
                barcode=item.get("barcode", item.get("ean")),
                is_active=item.get("is_active", item.get("active", True)),
                raw_data=item,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(new_product)

    async def _upsert_inventory(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        job_id: Optional[int] = None,
    ) -> str:
        """Insert or update an inventory record with conflict resolution.

        Conflict resolution (last-write-wins):
        - Compares the ERP item's ``updated_at`` timestamp with the existing
          record's ``last_synced_at``. If the ERP data is older, the local
          record is kept (unless ERP_WINS or LOCAL_WINS overrides).

        Args:
            db: Async database session.
            connection: ERPConnection instance.
            item: Inventory data dict from ERP.
            conflict_strategy: Conflict resolution strategy.
            job_id: Optional sync job ID for audit logging.

        Returns:
            Action taken: 'inserted', 'updated', or 'skipped'.
        """
        ext_product_id = str(item.get("product_id", item.get("id", "")))
        warehouse = item.get("warehouse_code", item.get("warehouse", None))

        result = await db.execute(
            select(ERPInventory).where(
                ERPInventory.connection_id == connection.id,
                ERPInventory.external_id == ext_product_id,
                ERPInventory.external_warehouse_code == warehouse,
            )
        )
        existing = result.scalar_one_or_none()

        action = "inserted"

        if existing:
            if conflict_strategy == ConflictStrategy.LOCAL_WINS:
                # Per-record audit log
                await self._log_record_action(
                    db, connection, "inventory", ext_product_id,
                    "skip", job_id, reason="local_wins"
                )
                return "skipped"

            # Last-write-wins: compare timestamps
            if conflict_strategy == ConflictStrategy.LAST_WRITE_WINS:
                erp_updated_at = self._parse_timestamp(
                    item.get("updated_at", item.get("modified_at"))
                )
                if erp_updated_at and existing.last_synced_at:
                    if erp_updated_at <= existing.last_synced_at:
                        logger.debug(
                            "Inventory %s skipped: ERP timestamp (%s) <= local (%s)",
                            ext_product_id, erp_updated_at, existing.last_synced_at,
                        )
                        await self._log_record_action(
                            db, connection, "inventory", ext_product_id,
                            "skip", job_id, reason="timestamp_older"
                        )
                        return "skipped"

            if conflict_strategy == ConflictStrategy.ERP_WINS:
                pass  # Always overwrite (handled below)

            existing.quantity_available = self._to_float(
                item.get("quantity_available", item.get("qty_available", existing.quantity_available))
            )
            existing.quantity_reserved = self._to_float(
                item.get("quantity_reserved", item.get("qty_reserved", existing.quantity_reserved))
            )
            existing.quantity_incoming = self._to_float(
                item.get("quantity_incoming", item.get("qty_incoming", existing.quantity_incoming))
            )
            existing.reorder_level = (
                self._to_float(item["reorder_level"])
                if item.get("reorder_level") is not None
                else existing.reorder_level
            )
            existing.reorder_quantity = (
                self._to_float(item["reorder_quantity"])
                if item.get("reorder_quantity") is not None
                else existing.reorder_quantity
            )
            existing.raw_data = item
            existing.last_synced_at = datetime.now(timezone.utc)
            action = "updated"
        else:
            db.add(
                ERPInventory(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    product_id=None,  # Will be resolved on demand
                    provider_type=connection.provider_type,
                    external_id=ext_product_id,
                    external_warehouse_code=warehouse,
                    quantity_available=self._to_float(
                        item.get("quantity_available", item.get("qty_available", 0))
                    ),
                    quantity_reserved=self._to_float(
                        item.get("quantity_reserved", item.get("qty_reserved", 0))
                    ),
                    quantity_incoming=self._to_float(
                        item.get("quantity_incoming", item.get("qty_incoming", 0))
                    ),
                    reorder_level=self._to_float(item.get("reorder_level")) if item.get("reorder_level") is not None else None,
                    reorder_quantity=self._to_float(item.get("reorder_quantity")) if item.get("reorder_quantity") is not None else None,
                    raw_data=item,
                    last_synced_at=datetime.now(timezone.utc),
                )
            )

        # Per-record audit log
        await self._log_record_action(
            db, connection, "inventory", ext_product_id, action, job_id
        )
        return action

    async def _upsert_sales_order(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ) -> None:
        """Insert or update a sales order record with conflict resolution."""
        external_id = str(item.get("id", item.get("order_id", "")))

        result = await db.execute(
            select(ERPSalesOrder).where(
                ERPSalesOrder.connection_id == connection.id,
                ERPSalesOrder.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if conflict_strategy == ConflictStrategy.LOCAL_WINS:
                return

            existing.external_order_number = item.get(
                "order_number", item.get("number", existing.external_order_number)
            )
            existing.status = item.get("status", existing.status)
            existing.total_amount = self._to_float(
                item.get("total_amount", item.get("total", existing.total_amount))
            )
            existing.tax_amount = self._to_float(
                item.get("tax_amount", item.get("tax", existing.tax_amount))
            )
            existing.discount_amount = self._to_float(
                item.get("discount_amount", item.get("discount", existing.discount_amount))
            )
            existing.currency = item.get("currency", existing.currency)
            existing.customer_external_id = str(
                item.get("customer_id", item.get("client_id", existing.customer_external_id or ""))
            )
            existing.customer_name = item.get("customer_name", existing.customer_name)
            existing.raw_data = item
            existing.last_synced_at = datetime.now(timezone.utc)
        else:
            order_date_str = item.get("order_date")
            order_date = None
            if order_date_str:
                try:
                    order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    order_date = datetime.now(timezone.utc)
            else:
                order_date = datetime.now(timezone.utc)

            delivery_date_str = item.get("delivery_date")
            delivery_date = None
            if delivery_date_str:
                try:
                    delivery_date = datetime.fromisoformat(delivery_date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    delivery_date = None

            db.add(
                ERPSalesOrder(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    provider_type=connection.provider_type,
                    external_id=external_id,
                    external_order_number=item.get("order_number", item.get("number")),
                    customer_external_id=str(
                        item.get("customer_id", item.get("client_id", ""))
                    ),
                    customer_name=item.get("customer_name"),
                    order_date=order_date,
                    delivery_date=delivery_date,
                    status=item.get("status", "pending"),
                    payment_status=item.get("payment_status", "unpaid"),
                    total_amount=self._to_float(
                        item.get("total_amount", item.get("total", 0))
                    ),
                    tax_amount=self._to_float(
                        item.get("tax_amount", item.get("tax", 0))
                    ),
                    discount_amount=self._to_float(
                        item.get("discount_amount", item.get("discount", 0))
                    ),
                    currency=item.get("currency", "AZN"),
                    raw_data=item,
                    last_synced_at=datetime.now(timezone.utc),
                )
            )

    async def _upsert_customer(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
        conflict_strategy: ConflictStrategy = ConflictStrategy.MERGE,
    ) -> str:
        """Insert or update a customer record with merge-based conflict resolution.

        Implements email-based deduplication: if a customer with the same
        email already exists for this connection, fields are merged.

        Args:
            db: Async database session.
            connection: ERPConnection instance.
            item: Customer data dict.
            conflict_strategy: Conflict resolution strategy.

        Returns:
            Action taken: 'inserted', 'updated', 'merged', or 'deduped'.
        """
        external_id = str(item.get("id", item.get("customer_id", "")))
        email = item.get("email")

        # 1. Check by external_id first
        result = await db.execute(
            select(ERPCustomer).where(
                ERPCustomer.connection_id == connection.id,
                ERPCustomer.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        # 2. Email-based deduplication: check for same email, different external_id
        existing_by_email = None
        if email and not existing:
            email_result = await db.execute(
                select(ERPCustomer).where(
                    ERPCustomer.connection_id == connection.id,
                    ERPCustomer.email == email,
                    ERPCustomer.external_id != external_id,
                )
            )
            existing_by_email = email_result.scalar_one_or_none()

        if existing or existing_by_email:
            target = existing or existing_by_email
            assert target is not None  # type guard

            if conflict_strategy == ConflictStrategy.LOCAL_WINS:
                return "skipped"

            if conflict_strategy == ConflictStrategy.MERGE:
                # Merge non-null fields only (MERGE strategy)
                target.name = item.get("name", target.name)
                if item.get("email") is not None:
                    target.email = item.get("email")
                if item.get("phone") is not None:
                    target.phone = item.get("phone")
                target.tax_number = item.get(
                    "tax_number", item.get("tax_id", target.tax_number)
                )
                if item.get("address") is not None:
                    target.address = item.get("address")
                if item.get("city") is not None:
                    target.city = item.get("city")
                target.customer_type = item.get("type", target.customer_type)
                if item.get("credit_limit") is not None:
                    target.credit_limit = self._to_float(item["credit_limit"])
                target.country = item.get("country", target.country)
                target.is_active = item.get(
                    "is_active", item.get("active", target.is_active)
                )
            else:
                # Full overwrite (LAST_WRITE_WINS / ERP_WINS)
                target.name = item.get("name", target.name)
                target.email = item.get("email", target.email)
                target.phone = item.get("phone", target.phone)
                target.tax_number = item.get(
                    "tax_number", item.get("tax_id", target.tax_number)
                )
                target.address = item.get("address", target.address)
                target.city = item.get("city", target.city)
                target.customer_type = item.get("type", target.customer_type)
                target.country = item.get("country", target.country)
                target.is_active = item.get(
                    "is_active", item.get("active", target.is_active)
                )

            # Always update external_id to latest (for dedup tracking)
            target.external_id = external_id
            target.raw_data = item
            target.last_synced_at = datetime.now(timezone.utc)

            if existing_by_email:
                return "deduped"
            return "merged"
        else:
            # Insert new customer
            db.add(
                ERPCustomer(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    provider_type=connection.provider_type,
                    external_id=external_id,
                    external_code=item.get("code"),
                    name=item.get("name", "Unknown"),
                    email=email,
                    phone=item.get("phone"),
                    tax_number=item.get("tax_number", item.get("tax_id")),
                    address=item.get("address"),
                    city=item.get("city"),
                    country=item.get("country", "Azerbaijan"),
                    customer_type=item.get("type", "unknown"),
                    credit_limit=self._to_float(item["credit_limit"]) if item.get("credit_limit") is not None else None,
                    is_active=item.get("is_active", item.get("active", True)),
                    raw_data=item,
                    last_synced_at=datetime.now(timezone.utc),
                )
            )
            return "inserted"

    async def _upsert_invoice(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ) -> None:
        """Insert or update an invoice record with order linking."""
        external_id = str(item.get("id", item.get("invoice_id", "")))

        result = await db.execute(
            select(ERPInvoice).where(
                ERPInvoice.connection_id == connection.id,
                ERPInvoice.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if conflict_strategy == ConflictStrategy.LOCAL_WINS:
                return

            existing.external_invoice_number = item.get(
                "invoice_number", item.get("number", existing.external_invoice_number)
            )
            existing.status = item.get("status", existing.status)
            existing.total_amount = self._to_float(
                item.get("total_amount", item.get("total", existing.total_amount))
            )
            existing.subtotal = self._to_float(
                item.get("subtotal", existing.subtotal)
            )
            existing.tax_amount = self._to_float(
                item.get("tax_amount", item.get("tax", existing.tax_amount))
            )
            existing.currency = item.get("currency", existing.currency)
            existing.raw_data = item
            existing.last_synced_at = datetime.now(timezone.utc)
        else:
            # Try to find linked sales order
            external_order_id = str(item.get("order_id", item.get("sales_order_id", "")))
            sales_order_id = None
            if external_order_id:
                so_result = await db.execute(
                    select(ERPSalesOrder.id).where(
                        ERPSalesOrder.connection_id == connection.id,
                        ERPSalesOrder.external_id == external_order_id,
                    )
                )
                so_row = so_result.one_or_none()
                if so_row:
                    sales_order_id = so_row[0]

            invoice_date_str = item.get("invoice_date")
            invoice_date = None
            if invoice_date_str:
                try:
                    invoice_date = datetime.fromisoformat(invoice_date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    invoice_date = datetime.now(timezone.utc)
            else:
                invoice_date = datetime.now(timezone.utc)

            due_date_str = item.get("due_date")
            due_date = None
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    due_date = None

            db.add(
                ERPInvoice(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    sales_order_id=sales_order_id,
                    provider_type=connection.provider_type,
                    external_id=external_id,
                    external_invoice_number=item.get(
                        "invoice_number", item.get("number")
                    ),
                    customer_external_id=str(
                        item.get("customer_id", item.get("client_id", ""))
                    ),
                    customer_name=item.get("customer_name"),
                    invoice_date=invoice_date,
                    due_date=due_date,
                    status=item.get("status", "draft"),
                    subtotal=self._to_float(
                        item.get("subtotal", 0)
                    ),
                    tax_amount=self._to_float(
                        item.get("tax_amount", item.get("tax", 0))
                    ),
                    total_amount=self._to_float(
                        item.get("total_amount", item.get("total", 0))
                    ),
                    currency=item.get("currency", "AZN"),
                    raw_data=item,
                    last_synced_at=datetime.now(timezone.utc),
                )
            )

    async def _upsert_payment(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
        conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
    ) -> None:
        """Insert or update a payment record with conflict resolution."""
        external_id = str(item.get("id", item.get("payment_id", "")))

        result = await db.execute(
            select(ERPPayment).where(
                ERPPayment.connection_id == connection.id,
                ERPPayment.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if conflict_strategy == ConflictStrategy.LOCAL_WINS:
                return

            existing.amount = self._to_float(
                item.get("amount", item.get("payment_amount", existing.amount))
            )
            existing.currency = item.get("currency", existing.currency)
            existing.payment_method = item.get(
                "payment_method",
                item.get("method", existing.payment_method),
            )
            existing.status = item.get("status", existing.status)
            existing.reference_number = item.get("reference", existing.reference_number)
            existing.raw_data = item
            existing.last_synced_at = datetime.now(timezone.utc)
        else:
            # Try to find linked invoice
            external_invoice_id = str(item.get("invoice_id", item.get("invoice", "")))
            invoice_id = None
            if external_invoice_id:
                inv_result = await db.execute(
                    select(ERPInvoice.id).where(
                        ERPInvoice.connection_id == connection.id,
                        ERPInvoice.external_id == external_invoice_id,
                    )
                )
                inv_row = inv_result.one_or_none()
                if inv_row:
                    invoice_id = inv_row[0]

            payment_date_str = item.get("payment_date")
            payment_date = None
            if payment_date_str:
                try:
                    payment_date = datetime.fromisoformat(payment_date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    payment_date = datetime.now(timezone.utc)
            else:
                payment_date = datetime.now(timezone.utc)

            db.add(
                ERPPayment(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    invoice_id=invoice_id,
                    provider_type=connection.provider_type,
                    external_id=external_id,
                    customer_external_id=str(
                        item.get("customer_id", item.get("client_id", ""))
                    ),
                    payment_date=payment_date,
                    amount=self._to_float(
                        item.get("amount", item.get("payment_amount", 0))
                    ),
                    currency=item.get("currency", "AZN"),
                    payment_method=item.get("payment_method", item.get("method", "unknown")),
                    status=item.get("status", "completed"),
                    reference_number=item.get("reference"),
                    notes=item.get("notes"),
                    raw_data=item,
                    last_synced_at=datetime.now(timezone.utc),
                )
            )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract a list of items from various possible response shapes."""
        if isinstance(data, list):
            return data
        for key in ("items", "products", "data", "results", "orders", "customers",
                     "invoices", "payments", "records", "entries", "inventory", "stock"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []

    @staticmethod
    def _to_float(value: Any) -> float:
        """Safely convert a value to float."""
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        """Safely parse an ISO timestamp string to datetime.

        Handles multiple formats including 'Z' suffix and naive strings.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            s = str(value)
            # Replace 'Z' with '+00:00' for Python < 3.11 compatibility
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _get_warehouse_codes(connection: Any) -> List[Optional[str]]:
        """Get list of warehouse codes to sync from connection config.

        Returns empty list to sync all warehouses in a single call.
        Override via connection config 'warehouse_codes' if needed.
        """
        # Future: read from connection.sync_config JSON field
        return []

    async def _log_record_action(
        self,
        db: AsyncSession,
        connection: Any,
        entity_type: str,
        external_id: str,
        action: str,
        job_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Log a per-record sync action for audit trail.

        This creates a sync log entry for individual record operations,
        enabling full traceability of every upsert decision.

        Args:
            db: Async database session.
            connection: ERPConnection instance.
            entity_type: Type of entity (inventory, product, etc.).
            external_id: External ERP ID of the record.
            action: Action taken (inserted, updated, skipped, failed).
            job_id: Optional sync job ID for correlation.
            reason: Optional reason for skip actions.
        """
        try:
            # Only log at debug level for bulk operations to avoid DB flood
            # In production, consider batching these or using an in-memory buffer
            if action in ("skipped", "failed") or __debug__:
                await ERPSyncLogService.create_sync_log(
                    db=db,
                    company_id=connection.company_id,
                    connection_id=connection.id,
                    job_id=job_id,
                    log_level="debug" if action in ("inserted", "updated") else "info",
                    entity_type=entity_type,
                    action=action,
                    external_id=external_id,
                    message=f"Record {external_id}: {action}" + (f" ({reason})" if reason else ""),
                    details={"reason": reason} if reason else None,
                )
        except Exception:
            # Never fail the sync due to logging issues
            pass


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

sync_engine = SyncEngine()
