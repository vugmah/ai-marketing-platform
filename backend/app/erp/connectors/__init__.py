"""ERP connector registry.

Import this module to access all available ERP connectors.
New connectors are registered in ``CONNECTOR_REGISTRY`` so the sync engine
can instantiate them dynamically at runtime.
"""

from typing import Any, Dict

from app.erp.connector_base import ERPConnectorBase
from app.erp.connectors.custom_connector import CustomERPConnector

# Registry of all available connectors keyed by *provider_type*.
CONNECTOR_REGISTRY: Dict[str, Any] = {
    "custom": CustomERPConnector,
    # Future connectors (to be implemented):
    # "odoo": OdooConnector,
    # "sap": SAPConnector,
    # "netsuite": NetSuiteConnector,
}


def get_connector(provider_type: str, config: Dict[str, Any]) -> ERPConnectorBase:
    """Instantiate the appropriate connector for *provider_type*.

    Args:
        provider_type: The ERP provider key (e.g. ``"custom"``).
        config: Connection configuration dict (``base_url``, ``api_key``, …).

    Raises:
        ValueError: If *provider_type* is not registered.
    """
    connector_class = CONNECTOR_REGISTRY.get(provider_type)
    if not connector_class:
        raise ValueError(f"Unknown ERP provider: {provider_type}")
    return connector_class(config)
