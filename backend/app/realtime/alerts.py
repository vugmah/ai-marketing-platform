"""Realtime Alert Service.

Pushes threshold-based and system alerts to WebSocket subscribers.

Alert severities:
    critical  → Immediate attention required (red)
    warning   → Attention soon (yellow/amber)
    info      → Informational (blue)

Alert types:
    threshold_exceeded   → KPI crossed above threshold
    threshold_below      → KPI dropped below threshold
    inventory_low        → Stock running low
    rate_limit_warning   → API rate limit approaching
    error_spike          → Error rate spike detected
    system_health        → System health status change

Usage:
    from app.realtime.alerts import push_alert, push_threshold_alert
    await push_threshold_alert(
        company_id=5, metric_name="revenue", current_value=500,
        threshold_value=1000, operator="below"
    )
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

REALTIME_CHANNEL_PREFIX = "realtime"


async def push_alert(
    company_id: int,
    severity: str,
    alert_type: str,
    title: str,
    message: str,
    branch_id: Optional[int] = None,
    metric_name: Optional[str] = None,
    metric_value: Optional[float] = None,
    threshold_value: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    alert_id: Optional[str] = None,
) -> str:
    """Push a generic alert to subscribed WebSocket clients.

    Args:
        company_id: Target company ID.
        severity: "critical" | "warning" | "info".
        alert_type: Type identifier (e.g. "threshold_exceeded").
        title: Short alert title.
        message: Detailed alert message.
        branch_id: Optional branch ID.
        metric_name: Optional related metric name.
        metric_value: Optional current metric value.
        threshold_value: Optional threshold that was crossed.
        metadata: Optional additional data.
        alert_id: Optional explicit alert ID.

    Returns:
        The alert ID.
    """
    aid = alert_id or f"alert_{uuid.uuid4().hex[:8]}"
    payload = {
        "alert_id": aid,
        "severity": severity,
        "alert_type": alert_type,
        "title": title,
        "message": message,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "threshold_value": threshold_value,
        "company_id": company_id,
        "branch_id": branch_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata": metadata or {},
    }

    # Persist alert in Redis for alert history
    redis = await get_redis_client()
    alert_key = f"alerts:{company_id}"
    await redis.lpush(alert_key, payload)
    await redis.ltrim(alert_key, 0, 499)  # Keep last 500 alerts

    # Publish to realtime channel
    await redis.publish(f"{REALTIME_CHANNEL_PREFIX}:alerts", payload)

    logger.info(
        "Pushed %s alert %s to company=%s: %s",
        severity,
        aid,
        company_id,
        title,
    )
    return aid


async def push_threshold_alert(
    company_id: int,
    metric_name: str,
    current_value: float,
    threshold_value: float,
    operator: str = "above",
    branch_id: Optional[int] = None,
    severity: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Push a threshold-crossing alert.

    Args:
        company_id: Target company ID.
        metric_name: Name of the metric (e.g. "revenue", "conversion_rate").
        current_value: Current metric value.
        threshold_value: Threshold that was crossed.
        operator: "above" | "below" - which direction was crossed.
        branch_id: Optional branch ID.
        severity: Override severity (auto-detected if not set).
        metadata: Optional additional data.

    Returns:
        The alert ID.
    """
    # Auto-detect severity based on deviation
    if severity is None:
        if threshold_value and threshold_value != 0:
            deviation = abs(current_value - threshold_value) / abs(threshold_value)
            if deviation > 0.5:
                severity = "critical"
            elif deviation > 0.2:
                severity = "warning"
            else:
                severity = "info"
        else:
            severity = "warning"

    # Determine direction and wording
    if operator == "above":
        title = f"{metric_name.upper()} esigi asildi"
        message = (
            f"'{metric_name}' degeri {current_value:.2f} ile "
            f"esik deger {threshold_value:.2f} uzerine cikmistir."
        )
        alert_type = "threshold_exceeded"
    else:
        title = f"{metric_name.upper()} esiginin altina dustu"
        message = (
            f"'{metric_name}' degeri {current_value:.2f} ile "
            f"esik deger {threshold_value:.2f} altina dusmustur."
        )
        alert_type = "threshold_below"

    return await push_alert(
        company_id=company_id,
        severity=severity,
        alert_type=alert_type,
        title=title,
        message=message,
        branch_id=branch_id,
        metric_name=metric_name,
        metric_value=current_value,
        threshold_value=threshold_value,
        metadata=metadata or {"operator": operator},
    )


async def push_inventory_alert(
    company_id: int,
    product_name: str,
    current_stock: int,
    threshold: int,
    branch_id: Optional[int] = None,
    product_id: Optional[str] = None,
) -> str:
    """Push an inventory low-stock alert.

    Args:
        company_id: Target company ID.
        product_name: Name of the product.
        current_stock: Current stock level.
        threshold: Low-stock threshold.
        branch_id: Optional branch ID.
        product_id: Optional product ID.

    Returns:
        The alert ID.
    """
    severity = "critical" if current_stock == 0 else "warning" if current_stock < threshold / 2 else "warning"

    return await push_alert(
        company_id=company_id,
        severity=severity,
        alert_type="inventory_low",
        title=f"Dusuk Stok: {product_name}",
        message=(
            f"'{product_name}' urununun stok seviyesi {current_stock}. "
            f"Esik deger: {threshold}. Yeniden siparis vermeniz onerilir."
        ),
        branch_id=branch_id,
        metric_name="stock_level",
        metric_value=float(current_stock),
        threshold_value=float(threshold),
        metadata={"product_name": product_name, "product_id": product_id},
    )


async def push_rate_limit_alert(
    company_id: int,
    api_name: str,
    usage_percent: float,
    limit: int,
    current_usage: int,
) -> str:
    """Push an API rate limit warning.

    Args:
        company_id: Target company ID.
        api_name: Name of the API (e.g. "OpenAI", "Meta Ads").
        usage_percent: Percentage of limit used (0-100).
        limit: Total API call limit.
        current_usage: Current number of API calls.

    Returns:
        The alert ID.
    """
    severity = "critical" if usage_percent >= 95 else "warning" if usage_percent >= 80 else "info"

    return await push_alert(
        company_id=company_id,
        severity=severity,
        alert_type="rate_limit_warning",
        title=f"{api_name} API Limiti Uyarisi",
        message=(
            f"{api_name} API kullanimi %{usage_percent:.1f} seviyesinde "
            f"({current_usage}/{limit} cagri). Limit yaklasti."
        ),
        metric_name=f"{api_name}_api_usage",
        metric_value=float(current_usage),
        threshold_value=float(limit),
        metadata={
            "api_name": api_name,
            "usage_percent": usage_percent,
            "limit": limit,
        },
    )


async def push_error_spike_alert(
    company_id: int,
    error_rate: float,
    threshold_rate: float,
    time_window: str = "5m",
    branch_id: Optional[int] = None,
) -> str:
    """Push an error rate spike alert.

    Args:
        company_id: Target company ID.
        error_rate: Current error rate (0-1).
        threshold_rate: Threshold error rate.
        time_window: Time window string (e.g. "5m", "1h").
        branch_id: Optional branch ID.

    Returns:
        The alert ID.
    """
    severity = "critical" if error_rate > 0.2 else "warning" if error_rate > 0.1 else "info"

    return await push_alert(
        company_id=company_id,
        severity=severity,
        alert_type="error_spike",
        title="Hata Orani Artisi Tespit Edildi",
        message=(
            f"Son {time_window} icinde hata orani %{error_rate*100:.1f}. "
            f"Kabul edilebilir esik: %{threshold_rate*100:.1f}. "
            f"Mudahale gerekebilir."
        ),
        branch_id=branch_id,
        metric_name="error_rate",
        metric_value=error_rate,
        threshold_value=threshold_rate,
        metadata={"time_window": time_window},
    )


async def push_system_health_alert(
    company_id: int,
    service_name: str,
    status: str,
    previous_status: str,
    details: Optional[str] = None,
) -> str:
    """Push a system health status change alert.

    Args:
        company_id: Target company ID.
        service_name: Name of the service (e.g. "Database", "Redis").
        status: Current status ("healthy" | "degraded" | "unhealthy").
        previous_status: Previous status.
        details: Optional details.

    Returns:
        The alert ID.
    """
    severity_map = {
        "healthy": "info",
        "degraded": "warning",
        "unhealthy": "critical",
    }
    severity = severity_map.get(status, "warning")

    title = f"Sistem Durumu: {service_name}"
    if status == "healthy":
        message = f"{service_name} hizmeti normale dondu."
    elif status == "degraded":
        message = f"{service_name} hizmetinde performans dususu tespit edildi."
    else:
        message = f"{service_name} hizmetinde kritik sorun!"

    if details:
        message += f" Detaylar: {details}"

    return await push_alert(
        company_id=company_id,
        severity=severity,
        alert_type="system_health",
        title=title,
        message=message,
        metadata={
            "service_name": service_name,
            "status": status,
            "previous_status": previous_status,
            "details": details,
        },
    )


# ---------------------------------------------------------------------------
# Event Bus Integration
# ---------------------------------------------------------------------------


async def on_event_bus_alert(event_payload: Dict[str, Any]) -> None:
    """Handler called by EventBus for alert-relevant events.

    Triggered on: inventory_low, erp_sync_failed, payment_failed
    """
    event_name = event_payload.get("event_name", "")
    company_id = event_payload.get("company_id")

    if not company_id:
        return

    if event_name == "inventory_low":
        await push_inventory_alert(
            company_id=company_id,
            product_name=event_payload.get("product_name", "Bilinmeyen Urun"),
            current_stock=event_payload.get("current_stock", 0),
            threshold=event_payload.get("threshold", 10),
            branch_id=event_payload.get("branch_id"),
            product_id=event_payload.get("product_id"),
        )
    elif event_name == "erp_sync_failed":
        await push_alert(
            company_id=company_id,
            severity="critical",
            alert_type="system_health",
            title="ERP Senkronizasyonu Basarisiz",
            message=f"ERP senkronizasyonu basarisiz: {event_payload.get('error', 'Bilinmeyen hata')}",
            metadata={"error": event_payload.get("error")},
        )
    elif event_name == "payment_failed":
        await push_alert(
            company_id=company_id,
            severity="warning",
            alert_type="threshold_exceeded",
            title="Odeme Basarisiz",
            message=f"Odeme islemi basarisiz: {event_payload.get('error', 'Bilinmeyen hata')}",
            branch_id=event_payload.get("branch_id"),
            metadata={"error": event_payload.get("error")},
        )
