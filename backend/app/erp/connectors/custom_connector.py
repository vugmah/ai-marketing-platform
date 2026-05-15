"""Connector for custom / internal ERP systems."""

from typing import Any, Dict, Optional

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
    """

    provider_type = "custom"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Ping the ERP health endpoint to validate connectivity."""
        try:
            result = await self._make_request("GET", "/api/health")
            return result.get("status") == "ok"
        except Exception as exc:
            logger.error("Custom ERP auth failed: %s", exc)
            return False

    async def refresh_auth(self) -> bool:
        """Custom ERPs typically use static API keys – no refresh needed."""
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
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/products", params=params)

    async def get_product(self, external_id: str) -> Optional[Dict[str, Any]]:
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
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page}
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
        params: Dict[str, Any] = {"page": page}
        if since:
            params["since"] = since
        return await self._make_request("GET", "/api/payments", params=params)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        try:
            result = await self._make_request("GET", "/api/health")
            return {
                "status": "ok",
                "message": "Custom ERP connected",
                "details": result,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
