"""Connector for custom / internal ERP systems."""

from typing import Any, Dict, Optional

import httpx
import logging

from app.erp.connector_base import ERPConnectorBase

logger = logging.getLogger(__name__)


class CustomERPConnector(ERPConnectorBase):
    """
    Connector for custom / internal ERP systems.

    This connector expects a REST API interface from the ERP system.
    Endpoints assumed (configurable via field mappings):

    +----------------+------------------------------+
    | Method         | Endpoint                     |
    +================+==============================+
    | GET            | /api/products                |
    | GET            | /api/products/{id}           |
    | GET            | /api/inventory               |
    | GET            | /api/sales-orders            |
    | GET            | /api/customers               |
    | GET            | /api/invoices                |
    | GET            | /api/payments                |
    | POST           | /api/webhook                 |
    +----------------+------------------------------+

    Authentication uses an API Key passed in the ``X-API-Key`` header
    (if ``api_secret`` is provided) or a standard ``Bearer`` token
    via the base ``_make_request`` helper.

    REST API Contract:
    - All endpoints return JSON responses
    - List endpoints return {items: [...], total: int, next_page: int|null}
    - Error responses return {error: str, message: str} with 4xx/5xx status
    - Timestamps in ISO 8601 format (UTC)
    - Pagination via page/page_size query params
    - Incremental sync via since param (ISO timestamp)
    """

    provider_type = "custom"

    # ------------------------------------------------------------------
    # Low-level request override for X-API-Key auth
    # ------------------------------------------------------------------

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generic async HTTP request helper with X-API-Key support.

        If ``api_secret`` is configured, sends it as ``X-API-Key`` header.
        Falls back to standard ``Bearer <api_key>`` authorization.
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        headers: Dict[str, str] = {"Content-Type": "application/json"}

        # Prefer api_secret as X-API-Key (common for custom/internal ERPs)
        if self.api_secret:
            headers["X-API-Key"] = self.api_secret
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            # No credentials - attempt anonymous (some internal ERPs)
            logger.warning("No API credentials configured for custom ERP")

        # Allow custom headers from kwargs to override defaults
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Ping the ERP health endpoint to validate connectivity.

        Returns True if the ERP responds with a valid health payload.
        Handles both {status: "ok"} and {health: "up"} response shapes.
        """
        try:
            result = await self._make_request("GET", "/api/health")
            # Accept multiple health response shapes
            health_ok = (
                result.get("status") in ("ok", "up", "healthy", "success")
                or result.get("health") in ("ok", "up", "healthy")
            )
            if health_ok:
                logger.info("Custom ERP auth success: %s", self.base_url)
            else:
                logger.warning(
                    "Custom ERP health check returned unexpected status: %s",
                    result,
                )
            return health_ok
        except Exception as exc:
            logger.error("Custom ERP auth failed: %s", exc)
            return False

    async def refresh_auth(self) -> bool:
        """Custom ERPs typically use static API keys -- no refresh needed."""
        return True

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    async def get_products(
        self,
        page: int = 1,
        page_size: int = 100,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated products with optional incremental filter.

        Args:
            page: Page number (1-based).
            page_size: Items per page.
            since: ISO timestamp for incremental sync.

        Returns:
            Dict with ``items``, ``total``, and ``next_page`` keys.
        """
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/products", params=params)

    async def get_product(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single product by its external ID."""
        try:
            return await self._make_request("GET", f"/api/products/{external_id}")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    async def get_inventory(
        self,
        warehouse_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch inventory / stock levels.

        Args:
            warehouse_code: Optional warehouse filter.

        Returns:
            Dict with ``items`` key containing inventory records.
            Each item should have: product_id, quantity_available,
            quantity_reserved, quantity_incoming, warehouse_code.
        """
        params: Dict[str, Any] = {}
        if warehouse_code:
            params["warehouse"] = warehouse_code
        return await self._make_request("GET", "/api/inventory", params=params)

    # ------------------------------------------------------------------
    # Sales Orders
    # ------------------------------------------------------------------

    async def get_sales_orders(
        self,
        page: int = 1,
        page_size: int = 100,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated sales orders."""
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/sales-orders", params=params)

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    async def get_customers(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated customers.

        Expected customer fields: id, name, email, phone, tax_number,
        address, city, country, type, credit_limit, is_active.
        """
        params: Dict[str, Any] = {"page": page}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/customers", params=params)

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    async def get_invoices(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated invoices.

        Expected invoice fields: id, invoice_number, customer_id,
        customer_name, order_id, invoice_date, due_date, status,
        subtotal, tax_amount, total_amount, currency.

        Status values should be mapped via InvoiceStatusMapper.
        """
        params: Dict[str, Any] = {"page": page}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/invoices", params=params)

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    async def get_payments(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated payments."""
        params: Dict[str, Any] = {"page": page}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/payments", params=params)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Check ERP connection health."""
        try:
            result = await self._make_request("GET", "/api/health")
            return {
                "status": "ok",
                "message": "Custom ERP connected",
                "details": result,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
