"""Abstract base class for all ERP connectors."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx


class ERPConnectorBase(ABC):
    """Abstract base class for all ERP connectors.

    All ERP-specific connectors must implement every method declared here.
    The ``_make_request`` helper is provided for convenience and uses
    ``httpx`` for fully async HTTP communication.
    """

    provider_type: str = ""

    def __init__(self, connection_config: Dict[str, Any]):
        self.config = connection_config
        self.base_url = connection_config.get("base_url", "")
        self.api_key = connection_config.get("api_key", "")
        self.api_secret = connection_config.get("api_secret", "")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @abstractmethod
    async def authenticate(self) -> bool:
        """Validate credentials and establish connection."""
        pass

    @abstractmethod
    async def refresh_auth(self) -> bool:
        """Refresh OAuth token if needed."""
        pass

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_products(
        self,
        page: int = 1,
        page_size: int = 100,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch products from ERP.

        Returns a dict with keys ``items``, ``total``, and ``next_page``.
        The ``items`` value is a list of product dicts.  ``next_page``
        should be ``None`` when there are no more pages.
        """
        pass

    @abstractmethod
    async def get_product(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single product by its external ID."""
        pass

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_inventory(
        self,
        warehouse_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch inventory / stock levels."""
        pass

    # ------------------------------------------------------------------
    # Sales Orders
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_sales_orders(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch sales orders."""
        pass

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_customers(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch customers."""
        pass

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_invoices(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch invoices."""
        pass

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_payments(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch payments."""
        pass

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check ERP connection health.

        Returns ``{status: "ok" | "error", message: str}``.
        """
        pass

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generic async HTTP request helper using ``httpx``."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
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
