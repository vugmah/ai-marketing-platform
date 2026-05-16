"""Celery tasks for ERP synchronization.

Provides background tasks for syncing various ERP entities:
- sync_inventory: Sync inventory/stock levels
- sync_products: Sync product catalog
- sync_customers: Sync customer records
- sync_invoices: Sync invoice records
- sync_sales_orders: Sync sales orders
- sync_payments: Sync payment records

All tasks use exponential backoff retry (max 5) and are routed
to the 'erp' queue by default.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------------------------

RETRY_KWARGS = {
    "max_retries": 5,
    "countdown": 10,  # Base delay, doubled each retry
    "retry_backoff": True,
    "retry_backoff_max": 300,  # Max 5 min between retries
    "retry_jitter": True,  # Add random jitter to prevent thundering herd
}

# ---------------------------------------------------------------------------
# Helper: Get active connections
# ---------------------------------------------------------------------------

async def _get_active_connections(db):
    """Fetch all active ERP connections."""
    from sqlalchemy import select
    from app.erp.models import ERPConnection

    result = await db.execute(select(ERPConnection).where(ERPConnection.is_active == True))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Task: sync_inventory
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.sync_inventory",
    queue="erp",
    default_retry_delay=10,
    **{k: v for k, v in RETRY_KWARGS.items() if k not in ["countdown", "retry_backoff", "retry_backoff_max", "retry_jitter"]},
)
def sync_inventory(
    self,
    connection_id: Optional[int] = None,
    sync_type: str = "incremental",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync inventory/stock levels from ERP.

    Args:
        connection_id: Specific ERP connection to sync. If None, syncs all active.
        sync_type: 'incremental' or 'full'
        company_id: Optional company filter.

    Returns:
        Dict with sync results: total_processed, total_failed, errors.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.erp.sync_service import inventory_sync
        from app.erp.models import ERPConnection
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            if connection_id:
                conn = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connections = [conn.scalar_one_or_none()]
            else:
                query = select(ERPConnection).where(ERPConnection.is_active == True)
                if company_id:
                    query = query.where(ERPConnection.company_id == company_id)
                conn_result = await db.execute(query)
                connections = list(conn_result.scalars().all())

            for conn in connections:
                if not conn:
                    continue
                try:
                    result = await inventory_sync(conn.id, db)
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "success",
                            "processed": result.get("records_processed", 0),
                            "failed": result.get("records_failed", 0),
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "Inventory sync failed for connection %s: %s",
                        conn.id,
                        exc,
                    )
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_inventory",
            "timestamp": datetime.utcnow().isoformat(),
            "total_connections": len(connections),
            "total_processed": sum(r.get("processed", 0) for r in results),
            "total_failed_syncs": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_inventory hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_inventory failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_inventory exhausted all %d retries. Task moved to dead letter.",
                RETRY_KWARGS["max_retries"],
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_products
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.sync_products",
    queue="erp",
    default_retry_delay=10,
    max_retries=5,
)
def sync_products(
    self,
    connection_id: Optional[int] = None,
    sync_type: str = "incremental",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync product catalog from ERP.

    Args:
        connection_id: Specific ERP connection to sync. If None, syncs all active.
        sync_type: 'incremental' or 'full'
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.erp.sync_service import product_sync
        from app.erp.models import ERPConnection
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            if connection_id:
                conn = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connections = [conn.scalar_one_or_none()]
            else:
                query = select(ERPConnection).where(ERPConnection.is_active == True)
                if company_id:
                    query = query.where(ERPConnection.company_id == company_id)
                conn_result = await db.execute(query)
                connections = list(conn_result.scalars().all())

            for conn in connections:
                if not conn:
                    continue
                try:
                    result = await product_sync(conn.id, db)
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "success",
                            "processed": result.get("records_processed", 0),
                            "failed": result.get("records_failed", 0),
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "Product sync failed for connection %s: %s",
                        conn.id,
                        exc,
                    )
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_products",
            "timestamp": datetime.utcnow().isoformat(),
            "total_connections": len(connections),
            "total_processed": sum(r.get("processed", 0) for r in results),
            "total_failed_syncs": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_products hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_products failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_products exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_customers
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.sync_customers",
    queue="erp",
    default_retry_delay=10,
    max_retries=5,
)
def sync_customers(
    self,
    connection_id: Optional[int] = None,
    sync_type: str = "incremental",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync customer records from ERP.

    Args:
        connection_id: Specific ERP connection to sync. If None, syncs all active.
        sync_type: 'incremental' or 'full'
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.erp.sync_service import customer_sync
        from app.erp.models import ERPConnection
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            if connection_id:
                conn = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connections = [conn.scalar_one_or_none()]
            else:
                query = select(ERPConnection).where(ERPConnection.is_active == True)
                if company_id:
                    query = query.where(ERPConnection.company_id == company_id)
                conn_result = await db.execute(query)
                connections = list(conn_result.scalars().all())

            for conn in connections:
                if not conn:
                    continue
                try:
                    result = await customer_sync(conn.id, db)
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "success",
                            "processed": result.get("records_processed", 0),
                            "failed": result.get("records_failed", 0),
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "Customer sync failed for connection %s: %s",
                        conn.id,
                        exc,
                    )
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_customers",
            "timestamp": datetime.utcnow().isoformat(),
            "total_connections": len(connections),
            "total_processed": sum(r.get("processed", 0) for r in results),
            "total_failed_syncs": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_customers hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_customers failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_customers exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_sales_orders
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.sync_sales_orders",
    queue="erp",
    default_retry_delay=10,
    max_retries=5,
)
def sync_sales_orders(
    self,
    connection_id: Optional[int] = None,
    sync_type: str = "incremental",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync sales orders from ERP.

    Args:
        connection_id: Specific ERP connection to sync. If None, syncs all active.
        sync_type: 'incremental' or 'full'
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.erp.sync_service import sales_order_sync
        from app.erp.models import ERPConnection
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            if connection_id:
                conn = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connections = [conn.scalar_one_or_none()]
            else:
                query = select(ERPConnection).where(ERPConnection.is_active == True)
                if company_id:
                    query = query.where(ERPConnection.company_id == company_id)
                conn_result = await db.execute(query)
                connections = list(conn_result.scalars().all())

            for conn in connections:
                if not conn:
                    continue
                try:
                    result = await sales_order_sync(conn.id, db)
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "success",
                            "processed": result.get("records_processed", 0),
                            "failed": result.get("records_failed", 0),
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "Sales order sync failed for connection %s: %s",
                        conn.id,
                        exc,
                    )
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_sales_orders",
            "timestamp": datetime.utcnow().isoformat(),
            "total_connections": len(connections),
            "total_processed": sum(r.get("processed", 0) for r in results),
            "total_failed_syncs": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_sales_orders hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_sales_orders failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_sales_orders exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_invoices
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.sync_invoices",
    queue="erp",
    default_retry_delay=10,
    max_retries=5,
)
def sync_invoices(
    self,
    connection_id: Optional[int] = None,
    sync_type: str = "incremental",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync invoices from ERP.

    Args:
        connection_id: Specific ERP connection to sync. If None, syncs all active.
        sync_type: 'incremental' or 'full'
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.erp.sync_service import invoice_sync
        from app.erp.models import ERPConnection
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            if connection_id:
                conn = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connections = [conn.scalar_one_or_none()]
            else:
                query = select(ERPConnection).where(ERPConnection.is_active == True)
                if company_id:
                    query = query.where(ERPConnection.company_id == company_id)
                conn_result = await db.execute(query)
                connections = list(conn_result.scalars().all())

            for conn in connections:
                if not conn:
                    continue
                try:
                    result = await invoice_sync(conn.id, db)
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "success",
                            "processed": result.get("records_processed", 0),
                            "failed": result.get("records_failed", 0),
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "Invoice sync failed for connection %s: %s",
                        conn.id,
                        exc,
                    )
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_invoices",
            "timestamp": datetime.utcnow().isoformat(),
            "total_connections": len(connections),
            "total_processed": sum(r.get("processed", 0) for r in results),
            "total_failed_syncs": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_invoices hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_invoices failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_invoices exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_payments
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.sync_payments",
    queue="erp",
    default_retry_delay=10,
    max_retries=5,
)
def sync_payments(
    self,
    connection_id: Optional[int] = None,
    sync_type: str = "incremental",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync payments from ERP.

    Args:
        connection_id: Specific ERP connection to sync. If None, syncs all active.
        sync_type: 'incremental' or 'full'
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.erp.sync_service import payment_sync
        from app.erp.models import ERPConnection
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            if connection_id:
                conn = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connections = [conn.scalar_one_or_none()]
            else:
                query = select(ERPConnection).where(ERPConnection.is_active == True)
                if company_id:
                    query = query.where(ERPConnection.company_id == company_id)
                conn_result = await db.execute(query)
                connections = list(conn_result.scalars().all())

            for conn in connections:
                if not conn:
                    continue
                try:
                    result = await payment_sync(conn.id, db)
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "success",
                            "processed": result.get("records_processed", 0),
                            "failed": result.get("records_failed", 0),
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "Payment sync failed for connection %s: %s",
                        conn.id,
                        exc,
                    )
                    results.append(
                        {
                            "connection_id": conn.id,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_payments",
            "timestamp": datetime.utcnow().isoformat(),
            "total_connections": len(connections),
            "total_processed": sum(r.get("processed", 0) for r in results),
            "total_failed_syncs": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_payments hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_payments failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_payments exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: run_full_sync (chained full sync)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.erp.tasks.run_full_sync",
    queue="erp",
    default_retry_delay=10,
    max_retries=3,
)
def run_full_sync(
    self,
    connection_id: int,
    company_id: int,
) -> Dict[str, Any]:
    """Run a full sync for all ERP entities for a connection.

    Chains all entity syncs together for a complete refresh.

    Args:
        connection_id: The ERP connection ID.
        company_id: The company ID.

    Returns:
        Dict with combined sync results.
    """
    import asyncio

    from celery import chain

    # Chain all sync tasks together
    job = chain(
        sync_inventory.s(connection_id=connection_id, sync_type="full", company_id=company_id),
        sync_products.s(connection_id=connection_id, sync_type="full", company_id=company_id),
        sync_customers.s(connection_id=connection_id, sync_type="full", company_id=company_id),
    )
    result = job.apply_async(queue="erp")

    return {
        "task": "run_full_sync",
        "timestamp": datetime.utcnow().isoformat(),
        "connection_id": connection_id,
        "chained_task_id": result.id,
        "status": "dispatched",
    }
