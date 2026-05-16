"""Stub connector for future ERP providers (not yet available in private beta).

All methods raise NotImplementedError with a descriptive message indicating
that the provider is not yet available. The custom ERP connector is the
only fully-supported provider during the private beta phase.

Supported providers in private beta:
- custom: Fully implemented via CustomERPConnector

Future providers (will return 501 Not Implemented):
- odoo, sap, netsuite, dynamics, logo, mikro, parasut, 1c
"""

import logging
from typing import Any, Dict, List, Optional

from app.erp.connector_base import ERPConnectorBase

logger = logging.getLogger(__name__)


class StubERPConnector(ERPConnectorBase):
    """Stub connector that raises NotImplementedError for all operations.

    Used as a placeholder for ERP providers that are not yet implemented
    in the private beta release. Attempting to authenticate or sync with
    these providers will fail gracefully with a descriptive error.
    """

    provider_type = "stub"

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _raise_not_implemented(self, operation: str) -> None:
        """Raise NotImplementedError with a provider-specific message."""
        provider = self.config.get("provider_type", self.provider_type)
        raise NotImplementedError(
            f"{provider.upper()} ERP connector is not yet available in private beta. "
            f"Operation '{operation}' failed. "
            f"Please use the 'custom' ERP connector for private beta integrations."
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("authenticate")
        return False  # pragma: no cover

    async def refresh_auth(self) -> bool:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("refresh_auth")
        return False  # pragma: no cover

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    async def get_products(
        self,
        page: int = 1,
        page_size: int = 100,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_products")
        return {}  # pragma: no cover

    async def get_product(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_product")
        return None  # pragma: no cover

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    async def get_inventory(
        self,
        warehouse_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_inventory")
        return {}  # pragma: no cover

    # ------------------------------------------------------------------
    # Sales Orders
    # ------------------------------------------------------------------

    async def get_sales_orders(
        self,
        page: int = 1,
        page_size: int = 100,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_sales_orders")
        return {}  # pragma: no cover

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    async def get_customers(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_customers")
        return {}  # pragma: no cover

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    async def get_invoices(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_invoices")
        return {}  # pragma: no cover

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    async def get_payments(
        self,
        page: int = 1,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Always raises NotImplementedError - provider not available."""
        self._raise_not_implemented("get_payments")
        return {}  # pragma: no cover

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Return an error status indicating the provider is not available."""
        provider = self.config.get("provider_type", self.provider_type)
        return {
            "status": "error",
            "message": (
                f"{provider.upper()} ERP connector is not yet available in private beta. "
                f"Please use the 'custom' ERP connector."
            ),
        }
