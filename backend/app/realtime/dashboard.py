"""Live Dashboard KPI Update Service.

Pushes real-time dashboard KPI updates to WebSocket subscribers.

Supported KPIs:
- revenue, orders, customers, conversion_rate
- ad_spend, roas, impressions, clicks
- inventory, low_stock_count
- ai_requests_used, ai_credits_remaining

Usage:
    from app.realtime.dashboard import push_kpi_update, push_dashboard_refresh
    await push_kpi_update(company_id=5, branch_id=2, metric_name="revenue", value=15000.0)
    await push_dashboard_refresh(company_id=5)
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

REALTIME_CHANNEL_PREFIX = "realtime"


async def push_kpi_update(
    company_id: int,
    metric_name: str,
    metric_value: float,
    previous_value: Optional[float] = None,
    branch_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Push a single KPI update to subscribed dashboard clients.

    Args:
        company_id: Target company ID.
        metric_name: Name of the KPI (e.g. 'revenue', 'orders').
        metric_value: Current metric value.
        previous_value: Optional previous value for change calculation.
        branch_id: Optional branch-scoped update.
        metadata: Optional additional data (labels, units, etc.).
    """
    change_percent = None
    if previous_value and previous_value != 0:
        change_percent = round(
            ((metric_value - previous_value) / abs(previous_value)) * 100, 2
        )

    kpi = {
        "metric_name": metric_name,
        "metric_value": metric_value,
        "previous_value": previous_value,
        "change_percent": change_percent,
        "branch_id": branch_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata": metadata or {},
    }

    redis = await get_redis_client()
    await redis.publish(
        f"{REALTIME_CHANNEL_PREFIX}:dashboard",
        {
            "company_id": company_id,
            "branch_id": branch_id,
            "kpis": [kpi],
            "timestamp": time.time(),
        },
    )

    logger.debug(
        "Pushed KPI %s=%s to company=%s branch=%s",
        metric_name,
        metric_value,
        company_id,
        branch_id,
    )


async def push_dashboard_refresh(
    company_id: int,
    branch_id: Optional[int] = None,
) -> None:
    """Signal all dashboard subscribers to refresh their data.

    Used when a significant update occurs that requires a full refresh.

    Args:
        company_id: Target company ID.
        branch_id: Optional branch filter.
    """
    redis = await get_redis_client()
    await redis.publish(
        f"{REALTIME_CHANNEL_PREFIX}:dashboard",
        {
            "company_id": company_id,
            "branch_id": branch_id,
            "refresh": True,
            "timestamp": time.time(),
        },
    )
    logger.info("Sent dashboard refresh to company=%s branch=%s", company_id, branch_id)


async def push_kpi_batch(
    company_id: int,
    kpis: List[Dict[str, Any]],
    branch_id: Optional[int] = None,
) -> None:
    """Push multiple KPI updates in a single message.

    Args:
        company_id: Target company ID.
        kpis: List of KPI dicts with keys: metric_name, metric_value, [previous_value].
        branch_id: Optional branch filter.
    """
    formatted_kpis = []
    for kpi in kpis:
        metric_value = kpi.get("metric_value", 0)
        previous_value = kpi.get("previous_value")
        change_percent = None
        if previous_value and previous_value != 0:
            change_percent = round(
                ((metric_value - previous_value) / abs(previous_value)) * 100, 2
            )
        formatted_kpis.append({
            "metric_name": kpi["metric_name"],
            "metric_value": metric_value,
            "previous_value": previous_value,
            "change_percent": change_percent,
            "branch_id": branch_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metadata": kpi.get("metadata", {}),
        })

    redis = await get_redis_client()
    await redis.publish(
        f"{REALTIME_CHANNEL_PREFIX}:dashboard",
        {
            "company_id": company_id,
            "branch_id": branch_id,
            "kpis": formatted_kpis,
            "timestamp": time.time(),
        },
    )
    logger.debug("Pushed %d KPIs to company=%s", len(formatted_kpis), company_id)


# ---------------------------------------------------------------------------
# Convenience helpers for common KPIs
# ---------------------------------------------------------------------------


async def push_revenue_update(
    company_id: int,
    revenue: float,
    previous_revenue: Optional[float] = None,
    branch_id: Optional[int] = None,
) -> None:
    """Push a revenue KPI update."""
    await push_kpi_update(
        company_id=company_id,
        metric_name="revenue",
        metric_value=revenue,
        previous_value=previous_revenue,
        branch_id=branch_id,
        metadata={"unit": "currency", "label": "Gelir"},
    )


async def push_orders_update(
    company_id: int,
    orders: int,
    previous_orders: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> None:
    """Push an orders KPI update."""
    await push_kpi_update(
        company_id=company_id,
        metric_name="orders",
        metric_value=float(orders),
        previous_value=float(previous_orders) if previous_orders is not None else None,
        branch_id=branch_id,
        metadata={"unit": "count", "label": "Siparis"},
    )


async def push_customers_update(
    company_id: int,
    customers: int,
    previous_customers: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> None:
    """Push a customers KPI update."""
    await push_kpi_update(
        company_id=company_id,
        metric_name="customers",
        metric_value=float(customers),
        previous_value=float(previous_customers) if previous_customers is not None else None,
        branch_id=branch_id,
        metadata={"unit": "count", "label": "Musteri"},
    )


async def push_conversion_rate_update(
    company_id: int,
    rate: float,
    previous_rate: Optional[float] = None,
    branch_id: Optional[int] = None,
) -> None:
    """Push a conversion rate KPI update."""
    await push_kpi_update(
        company_id=company_id,
        metric_name="conversion_rate",
        metric_value=rate,
        previous_value=previous_rate,
        branch_id=branch_id,
        metadata={"unit": "percent", "label": "Donusum Orani"},
    )


async def push_ad_spend_update(
    company_id: int,
    spend: float,
    previous_spend: Optional[float] = None,
    branch_id: Optional[int] = None,
) -> None:
    """Push an ad spend KPI update."""
    await push_kpi_update(
        company_id=company_id,
        metric_name="ad_spend",
        metric_value=spend,
        previous_value=previous_spend,
        branch_id=branch_id,
        metadata={"unit": "currency", "label": "Reklam Harcamasi"},
    )


async def push_ai_credits_update(
    company_id: int,
    credits_used: int,
    credits_limit: int,
) -> None:
    """Push AI credits usage update.

    Args:
        company_id: Target company ID.
        credits_used: Number of AI credits consumed.
        credits_limit: Total AI credit limit.
    """
    await push_kpi_update(
        company_id=company_id,
        metric_name="ai_credits_used",
        metric_value=float(credits_used),
        metadata={
            "unit": "count",
            "label": "AI Kullanimi",
            "limit": credits_limit,
            "remaining": credits_limit - credits_used,
            "percent_used": round(credits_used / credits_limit * 100, 1) if credits_limit else 0,
        },
    )


# ---------------------------------------------------------------------------
# Event Bus Integration
# ---------------------------------------------------------------------------


async def on_event_bus_dashboard(event_payload: Dict[str, Any]) -> None:
    """Handler called by EventBus for dashboard-relevant events.

    Triggered on: order_created, payment_received, campaign_updated,
    inventory_low, ai_request_completed
    """
    event_name = event_payload.get("event_name", "")
    company_id = event_payload.get("company_id")
    branch_id = event_payload.get("branch_id")

    if not company_id:
        return

    # Map event types to dashboard KPI pushes
    if event_name == "order_created":
        await push_dashboard_refresh(company_id, branch_id)
    elif event_name == "payment_received":
        await push_dashboard_refresh(company_id, branch_id)
    elif event_name == "campaign_updated":
        await push_dashboard_refresh(company_id)
    elif event_name == "inventory_low":
        await push_kpi_update(
            company_id=company_id,
            metric_name="low_stock_count",
            metric_value=event_payload.get("low_stock_count", 1),
            branch_id=branch_id,
            metadata={"unit": "count", "label": "Dusuk Stok Uyarisi"},
        )
    elif event_name == "ai_request_completed":
        await push_ai_credits_update(
            company_id=company_id,
            credits_used=event_payload.get("credits_used", 0),
            credits_limit=event_payload.get("credits_limit", 1000),
        )
