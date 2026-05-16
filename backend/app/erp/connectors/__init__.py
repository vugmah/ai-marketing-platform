"""ERP connector registry.

Import this module to access all available ERP connectors.
New connectors are registered in ``CONNECTOR_REGISTRY`` so the sync engine
can instantiate them dynamically at runtime.

Private Beta Status:
- ``custom``: FULLY SUPPORTED - CustomERPConnector with REST API contract
- All other providers: NOT IMPLEMENTED - StubERPConnector (returns 501)

All non-custom providers use StubERPConnector which raises
NotImplementedError on any sync operation, ensuring that private beta
users can only sync with real custom ERP integrations.
"""

from typing import Any, Dict

from app.erp.connector_base import ERPConnectorBase
from app.erp.connectors.custom_connector import CustomERPConnector
from app.erp.connectors.stub_connector import StubERPConnector

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

# Fully supported providers (private beta)
SUPPORTED_PROVIDERS = {"custom"}

# Future providers (stub only - will return 501 Not Implemented)
FUTURE_PROVIDERS = {
    "odoo",
    "sap",
    "netsuite",
    "dynamics",
    "logo",
    "mikro",
    "parasut",
    "1c",
}

# Registry of all available connectors keyed by *provider_type*.
CONNECTOR_REGISTRY: Dict[str, Any] = {
    # Private beta - fully supported
    "custom": CustomERPConnector,
    # Future providers - stub (returns 501 on any sync operation)
    "odoo": StubERPConnector,
    "sap": StubERPConnector,
    "netsuite": StubERPConnector,
    "dynamics": StubERPConnector,
    "logo": StubERPConnector,
    "mikro": StubERPConnector,
    "parasut": StubERPConnector,
    "1c": StubERPConnector,
}

# Human-readable provider labels
PROVIDER_LABELS: Dict[str, str] = {
    "custom": "Custom REST API ERP",
    "odoo": "Odoo",
    "sap": "SAP",
    "netsuite": "NetSuite",
    "dynamics": "Microsoft Dynamics",
    "logo": "Logo",
    "mikro": "Mikro",
    "parasut": "Paraşüt",
    "1c": "1C",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_provider_supported(provider_type: str) -> bool:
    """Check if a provider is fully supported in private beta.

    Args:
        provider_type: The ERP provider key.

    Returns:
        True if the provider is fully supported, False if it's a stub.
    """
    return provider_type in SUPPORTED_PROVIDERS


def get_provider_label(provider_type: str) -> str:
    """Get a human-readable label for a provider type.

    Args:
        provider_type: The ERP provider key.

    Returns:
        Human-readable provider name.
    """
    return PROVIDER_LABELS.get(provider_type, provider_type.upper())


def list_supported_providers() -> Dict[str, str]:
    """List all fully supported providers.

    Returns:
        Dict mapping provider_type to human-readable label.
    """
    return {k: PROVIDER_LABELS[k] for k in SUPPORTED_PROVIDERS}


def list_future_providers() -> Dict[str, str]:
    """List all future (not yet implemented) providers.

    Returns:
        Dict mapping provider_type to human-readable label.
    """
    return {k: PROVIDER_LABELS[k] for k in FUTURE_PROVIDERS}


def get_connector(provider_type: str, config: Dict[str, Any]) -> ERPConnectorBase:
    """Instantiate the appropriate connector for *provider_type*.

    Args:
        provider_type: The ERP provider key (e.g. ``"custom"``).
        config: Connection configuration dict (``base_url``, ``api_key``, ...).

    Raises:
        ValueError: If *provider_type* is not registered at all.

    Returns:
        An ERPConnectorBase subclass instance. For future providers,
        this will be a StubERPConnector that raises NotImplementedError
        on any sync operation.
    """
    # Inject provider_type into config so stub can reference it
    config_with_provider = dict(config)
    config_with_provider["provider_type"] = provider_type

    connector_class = CONNECTOR_REGISTRY.get(provider_type)
    if not connector_class:
        available = ", ".join(sorted(CONNECTOR_REGISTRY.keys()))
        raise ValueError(
            f"Unknown ERP provider: '{provider_type}'. "
            f"Available providers: {available}. "
            f"Only 'custom' is fully supported in private beta."
        )

    return connector_class(config_with_provider)
