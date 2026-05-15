"""
ERP Sync Service – Core synchronization engine.

Handles all sync operations:

* Manual sync (triggered via API)
* Scheduled sync (triggered via Celery)
* Webhook-triggered sync (triggered via webhook)
* Incremental sync (only changed records since last sync)
* Full sync (all records)
"""

import asyncio
import functools
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.erp.connector_base import ERPConnectorBase
from app.erp.connectors import get_connector

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
# Sync Engine
# ---------------------------------------------------------------------------


class SyncEngine:
    """Core sync engine that orchestrates ERP data synchronization."""

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

    @with_retry(max_retries=3, base_delay=1.0)
    async def run_sync(
        self,
        job_id: int,
        connection_id: int,
        entity_type: str,
        sync_type: str = "incremental",
    ) -> Dict[str, Any]:
        """Execute a sync job.  This is the main entry point.

        Args:
            job_id: The ``ERPSyncJob`` primary key.
            connection_id: The ``ERPConnection`` primary key.
            entity_type: What to sync (``"products"``, ``"inventory"``,
                         ``"all"``, …).
            sync_type: ``"incremental"`` or ``"full"``.

        Returns:
            A dict with ``status``, ``records_processed``,
            ``records_failed``, and ``error``.
        """
        result: Dict[str, Any] = {
            "status": "completed",
            "records_processed": 0,
            "records_failed": 0,
            "error": None,
        }

        try:
            async with get_db_context() as db:
                # ------------------------------------------------------
                # 1. Load connection config
                # ------------------------------------------------------
                from app.erp.models import ERPConnection

                conn_result = await db.execute(
                    select(ERPConnection).where(ERPConnection.id == connection_id)
                )
                connection = conn_result.scalar_one_or_none()

                if not connection:
                    raise ValueError(f"Connection {connection_id} not found")

                # ------------------------------------------------------
                # 2. Build connector instance
                # ------------------------------------------------------
                config = {
                    "base_url": connection.base_url,
                    "api_key": connection.api_key,
                    "api_secret": connection.api_secret,
                }
                connector = get_connector(connection.provider_type, config)

                # ------------------------------------------------------
                # 3. Authenticate
                # ------------------------------------------------------
                if not await connector.authenticate():
                    raise ConnectionError(
                        f"Failed to authenticate with {connection.provider_type}"
                    )

                # ------------------------------------------------------
                # 4. Determine entities and 'since' timestamp
                # ------------------------------------------------------
                entities = (
                    list(self.ENTITY_HANDLERS.keys())
                    if entity_type == "all"
                    else [entity_type]
                )

                since: Optional[str] = None
                if sync_type == "incremental" and connection.last_sync_at:
                    since = connection.last_sync_at.isoformat()

                # ------------------------------------------------------
                # 5. Sync each entity
                # ------------------------------------------------------
                for entity in entities:
                    handler_name = self.ENTITY_HANDLERS.get(entity)
                    if handler_name:
                        handler = getattr(self, handler_name)
                        entity_result = await handler(
                            connector, connection, db, since
                        )
                        result["records_processed"] += entity_result.get(
                            "processed", 0
                        )
                        result["records_failed"] += entity_result.get("failed", 0)

                # ------------------------------------------------------
                # 6. Update connection sync state
                # ------------------------------------------------------
                connection.last_sync_at = datetime.utcnow()
                connection.last_sync_status = "success"
                connection.last_sync_error = None
                await db.commit()

                logger.info(
                    "Sync job %d completed: %d processed, %d failed",
                    job_id,
                    result["records_processed"],
                    result["records_failed"],
                )

        except Exception as exc:
            logger.error("Sync job %d failed: %s", job_id, exc)
            result["status"] = "failed"
            result["error"] = str(exc)

            # Best-effort status update on the connection row
            try:
                async with get_db_context() as db:
                    from app.erp.models import ERPConnection

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
                        await self._upsert_product(db, connection, item)
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
    ) -> Dict[str, int]:
        """Sync inventory levels."""
        result = {"processed": 0, "failed": 0}

        try:
            data = await connector.get_inventory()
            items = self._extract_items(data)

            for item in items:
                try:
                    await self._upsert_inventory(db, connection, item)
                    result["processed"] += 1
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
    ) -> Dict[str, int]:
        """Sync sales orders."""
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
                        await self._upsert_sales_order(db, connection, item)
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
    ) -> Dict[str, int]:
        """Sync customers."""
        result = {"processed": 0, "failed": 0}

        try:
            page = 1
            while True:
                data = await connector.get_customers(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        await self._upsert_customer(db, connection, item)
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
    ) -> Dict[str, int]:
        """Sync invoices."""
        result = {"processed": 0, "failed": 0}

        try:
            page = 1
            while True:
                data = await connector.get_invoices(page=page, since=since)
                items = self._extract_items(data)
                if not items:
                    break

                for item in items:
                    try:
                        await self._upsert_invoice(db, connection, item)
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
    ) -> Dict[str, int]:
        """Sync payments."""
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
                        await self._upsert_payment(db, connection, item)
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
    # Upsert helpers
    # ------------------------------------------------------------------

    async def _upsert_product(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
    ) -> None:
        """Insert or update a product record."""
        from app.erp.models import ERPProduct

        external_id = str(item.get("id", item.get("product_id", "")))

        result = await db.execute(
            select(ERPProduct).where(
                ERPProduct.connection_id == connection.id,
                ERPProduct.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = item.get("name", existing.name)
            existing.description = item.get("description", existing.description)
            existing.unit_price = self._to_float(
                item.get("price", item.get("unit_price", 0))
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
                item.get("tax_rate", item.get("vat_rate", 0))
            )
            existing.is_active = item.get(
                "is_active", item.get("active", existing.is_active)
            )
            existing.raw_data = str(item)
            existing.last_synced_at = datetime.utcnow()
        else:
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
                raw_data=str(item),
                last_synced_at=datetime.utcnow(),
            )
            db.add(new_product)

    async def _upsert_inventory(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
    ) -> None:
        """Insert or update an inventory record."""
        from app.erp.models import ERPInventory

        ext_product_id = str(item.get("product_id", item.get("id", "")))
        warehouse = item.get("warehouse_code", item.get("warehouse", None))

        result = await db.execute(
            select(ERPInventory).where(
                ERPInventory.connection_id == connection.id,
                ERPInventory.external_product_id == ext_product_id,
                ERPInventory.warehouse_code == warehouse,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.quantity_on_hand = self._to_float(
                item.get("quantity_on_hand", item.get("qty_on_hand", 0))
            )
            existing.quantity_reserved = self._to_float(
                item.get("quantity_reserved", item.get("qty_reserved", 0))
            )
            existing.quantity_available = self._to_float(
                item.get(
                    "quantity_available",
                    item.get("qty_available", 0),
                )
            )
            existing.raw_data = str(item)
            existing.last_synced_at = datetime.utcnow()
        else:
            db.add(
                ERPInventory(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    external_product_id=ext_product_id,
                    warehouse_code=warehouse,
                    quantity_on_hand=self._to_float(
                        item.get("quantity_on_hand", item.get("qty_on_hand", 0))
                    ),
                    quantity_reserved=self._to_float(
                        item.get("quantity_reserved", item.get("qty_reserved", 0))
                    ),
                    quantity_available=self._to_float(
                        item.get(
                            "quantity_available",
                            item.get("qty_available", 0),
                        )
                    ),
                    raw_data=str(item),
                    last_synced_at=datetime.utcnow(),
                )
            )

    async def _upsert_sales_order(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
    ) -> None:
        """Insert or update a sales order record."""
        from app.erp.models import ERPSalesOrder

        external_id = str(item.get("id", item.get("order_id", "")))

        result = await db.execute(
            select(ERPSalesOrder).where(
                ERPSalesOrder.connection_id == connection.id,
                ERPSalesOrder.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.order_number = item.get(
                "order_number", item.get("number", existing.order_number)
            )
            existing.status = item.get("status", existing.status)
            existing.total_amount = self._to_float(
                item.get("total_amount", item.get("total", 0))
            )
            existing.currency = item.get("currency", existing.currency)
            existing.raw_data = str(item)
            existing.last_synced_at = datetime.utcnow()
        else:
            db.add(
                ERPSalesOrder(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    external_id=external_id,
                    external_customer_id=str(
                        item.get("customer_id", item.get("client_id", ""))
                    ),
                    order_number=item.get("order_number", item.get("number")),
                    order_date=item.get("order_date"),
                    status=item.get("status"),
                    total_amount=self._to_float(
                        item.get("total_amount", item.get("total", 0))
                    ),
                    currency=item.get("currency", "AZN"),
                    raw_data=str(item),
                    last_synced_at=datetime.utcnow(),
                )
            )

    async def _upsert_customer(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
    ) -> None:
        """Insert or update a customer record."""
        from app.erp.models import ERPCustomer

        external_id = str(item.get("id", item.get("customer_id", "")))

        result = await db.execute(
            select(ERPCustomer).where(
                ERPCustomer.connection_id == connection.id,
                ERPCustomer.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = item.get("name", existing.name)
            existing.email = item.get("email", existing.email)
            existing.phone = item.get("phone", existing.phone)
            existing.tax_number = item.get(
                "tax_number", item.get("tax_id", existing.tax_number)
            )
            existing.address = item.get("address", existing.address)
            existing.customer_type = item.get("type", existing.customer_type)
            existing.is_active = item.get(
                "is_active", item.get("active", existing.is_active)
            )
            existing.raw_data = str(item)
            existing.last_synced_at = datetime.utcnow()
        else:
            db.add(
                ERPCustomer(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    external_id=external_id,
                    name=item.get("name", "Unknown"),
                    email=item.get("email"),
                    phone=item.get("phone"),
                    tax_number=item.get("tax_number", item.get("tax_id")),
                    address=item.get("address"),
                    customer_type=item.get("type"),
                    is_active=item.get("is_active", item.get("active", True)),
                    raw_data=str(item),
                    last_synced_at=datetime.utcnow(),
                )
            )

    async def _upsert_invoice(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
    ) -> None:
        """Insert or update an invoice record."""
        from app.erp.models import ERPInvoice

        external_id = str(item.get("id", item.get("invoice_id", "")))

        result = await db.execute(
            select(ERPInvoice).where(
                ERPInvoice.connection_id == connection.id,
                ERPInvoice.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.invoice_number = item.get(
                "invoice_number", item.get("number", existing.invoice_number)
            )
            existing.status = item.get("status", existing.status)
            existing.total_amount = self._to_float(
                item.get("total_amount", item.get("total", 0))
            )
            existing.paid_amount = self._to_float(
                item.get("paid_amount", item.get("paid", 0))
            )
            existing.currency = item.get("currency", existing.currency)
            existing.raw_data = str(item)
            existing.last_synced_at = datetime.utcnow()
        else:
            db.add(
                ERPInvoice(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    external_id=external_id,
                    external_order_id=str(
                        item.get("order_id", item.get("sales_order_id", ""))
                    ),
                    invoice_number=item.get(
                        "invoice_number", item.get("number")
                    ),
                    invoice_date=item.get("invoice_date"),
                    due_date=item.get("due_date"),
                    status=item.get("status"),
                    total_amount=self._to_float(
                        item.get("total_amount", item.get("total", 0))
                    ),
                    paid_amount=self._to_float(
                        item.get("paid_amount", item.get("paid", 0))
                    ),
                    currency=item.get("currency", "AZN"),
                    raw_data=str(item),
                    last_synced_at=datetime.utcnow(),
                )
            )

    async def _upsert_payment(
        self,
        db: AsyncSession,
        connection: Any,
        item: Dict[str, Any],
    ) -> None:
        """Insert or update a payment record."""
        from app.erp.models import ERPPayment

        external_id = str(item.get("id", item.get("payment_id", "")))

        result = await db.execute(
            select(ERPPayment).where(
                ERPPayment.connection_id == connection.id,
                ERPPayment.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.amount = self._to_float(
                item.get("amount", item.get("payment_amount", 0))
            )
            existing.currency = item.get("currency", existing.currency)
            existing.payment_method = item.get(
                "payment_method",
                item.get("method", existing.payment_method),
            )
            existing.status = item.get("status", existing.status)
            existing.reference = item.get("reference", existing.reference)
            existing.raw_data = str(item)
            existing.last_synced_at = datetime.utcnow()
        else:
            db.add(
                ERPPayment(
                    company_id=connection.company_id,
                    branch_id=connection.branch_id,
                    connection_id=connection.id,
                    external_id=external_id,
                    external_invoice_id=str(
                        item.get("invoice_id", item.get("invoice", ""))
                    ),
                    payment_date=item.get("payment_date"),
                    amount=self._to_float(
                        item.get("amount", item.get("payment_amount", 0))
                    ),
                    currency=item.get("currency", "AZN"),
                    payment_method=item.get("payment_method", item.get("method")),
                    status=item.get("status"),
                    reference=item.get("reference"),
                    raw_data=str(item),
                    last_synced_at=datetime.utcnow(),
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
                     "invoices", "payments", "records", "entries"):
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


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

sync_engine = SyncEngine()
