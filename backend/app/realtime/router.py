"""Realtime REST API Router.

Provides HTTP endpoints for:
- Connection statistics (admin/monitoring)
- Manual broadcast (admin)
- Connection health check
- Triggering test pushes
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_user, require_role
from app.realtime.alerts import (
    push_alert,
    push_error_spike_alert,
    push_inventory_alert,
    push_rate_limit_alert,
    push_system_health_alert,
    push_threshold_alert,
)
from app.realtime.dashboard import (
    push_ai_credits_update,
    push_conversion_rate_update,
    push_customers_update,
    push_dashboard_refresh,
    push_kpi_batch,
    push_kpi_update,
    push_orders_update,
    push_revenue_update,
)
from app.realtime.manager import get_connection_manager
from app.realtime.notifications import (
    push_company_broadcast,
    push_notification,
    push_notification_bulk,
)
from app.realtime.publisher import get_pubsub_bridge
from app.realtime.support_inbox import (
    push_agent_assigned,
    push_ai_response,
    push_new_message,
    push_ticket_created,
    push_ticket_status_change,
    push_unread_count,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Statistics & Health
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=dict,
    summary="WebSocket connection statistics",
    tags=["Realtime"],
)
async def get_websocket_stats(
    _=Depends(require_role(["super_admin", "company_admin"])),
) -> dict:
    """Get WebSocket connection statistics.

    Returns counts of active connections, users, companies, and channel subscriptions.
    Requires company_admin or super_admin role.
    """
    manager = get_connection_manager()
    stats = manager.get_stats()
    return {
        "success": True,
        "data": stats,
    }


@router.get(
    "/health",
    response_model=dict,
    summary="Realtime system health check",
    tags=["Realtime"],
)
async def get_realtime_health() -> dict:
    """Check the health of the realtime subsystem."""
    manager = get_connection_manager()
    stats = manager.get_stats()
    return {
        "success": True,
        "data": {
            "status": "healthy" if stats["stale_connections"] == 0 else "degraded",
            "total_connections": stats["total_connections"],
            "stale_connections": stats["stale_connections"],
            "unique_users": stats["unique_users"],
        },
    }


# ---------------------------------------------------------------------------
# Admin Broadcast
# ---------------------------------------------------------------------------


@router.post(
    "/broadcast",
    response_model=dict,
    summary="Broadcast a message to all connections",
    tags=["Realtime"],
)
async def admin_broadcast(
    payload: Dict[str, Any],
    _=Depends(require_role(["super_admin"])),
) -> dict:
    """Broadcast a message to ALL connected WebSocket clients.

    **Admin only.** Use with caution.

    Args:
        payload: JSON payload to broadcast (will be wrapped in envelope).
    """
    manager = get_connection_manager()
    bridge = await get_pubsub_bridge()
    await bridge.publish_broadcast(payload)
    return {
        "success": True,
        "message": "Broadcast message published",
        "target_connections": manager.get_stats()["total_connections"],
    }


@router.post(
    "/broadcast/company/{company_id}",
    response_model=dict,
    summary="Broadcast to a specific company",
    tags=["Realtime"],
)
async def broadcast_to_company(
    company_id: int,
    payload: Dict[str, Any],
    channel: Optional[str] = Query(None, description="Filter by channel"),
    branch_id: Optional[int] = Query(None, description="Filter by branch"),
    _=Depends(require_role(["super_admin", "company_admin"])),
) -> dict:
    """Broadcast a message to all WebSocket connections of a company.

    Args:
        company_id: Target company ID.
        payload: JSON payload.
        channel: Optional channel filter.
        branch_id: Optional branch filter.
    """
    manager = get_connection_manager()
    envelope = {
        "msg_type": "event",
        "message_id": "admin_broadcast",
        "timestamp": __import__("time").time(),
        "payload": payload,
    }
    sent = await manager.broadcast_to_company(
        company_id=company_id,
        message=envelope,
        channel=channel,
        branch_id=branch_id,
    )
    return {
        "success": True,
        "message": f"Broadcast to company {company_id}",
        "delivered": sent,
    }


# ---------------------------------------------------------------------------
# Notification Push Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/push/notification",
    response_model=dict,
    summary="Push a notification to a user",
    tags=["Realtime"],
)
async def api_push_notification(
    user_id: int,
    company_id: int,
    title: str,
    message: str,
    notif_type: str = Query("info"),
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push a realtime notification to a specific user.

    Args:
        user_id: Target user ID.
        company_id: Target company ID.
        title: Notification title.
        message: Notification body.
        notif_type: Type (info, warning, success, error).
    """
    notif_id = await push_notification(
        user_id=user_id,
        company_id=company_id,
        title=title,
        message=message,
        notif_type=notif_type,
    )
    return {"success": True, "notification_id": notif_id}


@router.post(
    "/push/notification/broadcast",
    response_model=dict,
    summary="Broadcast a notification to a company",
    tags=["Realtime"],
)
async def api_broadcast_notification(
    company_id: int,
    title: str,
    message: str,
    notif_type: str = Query("info"),
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Broadcast a notification to all users in a company.

    Args:
        company_id: Target company ID.
        title: Notification title.
        message: Notification body.
        notif_type: Type (info, warning, success, error).
    """
    notif_id = await push_company_broadcast(
        company_id=company_id,
        title=title,
        message=message,
        notif_type=notif_type,
    )
    return {"success": True, "notification_id": notif_id}


# ---------------------------------------------------------------------------
# Dashboard Push Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/push/dashboard/refresh",
    response_model=dict,
    summary="Trigger a dashboard refresh",
    tags=["Realtime"],
)
async def api_push_dashboard_refresh(
    company_id: int,
    branch_id: Optional[int] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Trigger a dashboard refresh for a company."""
    await push_dashboard_refresh(company_id=company_id, branch_id=branch_id)
    return {"success": True, "message": f"Dashboard refresh triggered for company {company_id}"}


@router.post(
    "/push/dashboard/kpi",
    response_model=dict,
    summary="Push a KPI update",
    tags=["Realtime"],
)
async def api_push_kpi(
    company_id: int,
    metric_name: str,
    metric_value: float,
    previous_value: Optional[float] = None,
    branch_id: Optional[int] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push a single KPI update to dashboard subscribers."""
    await push_kpi_update(
        company_id=company_id,
        metric_name=metric_name,
        metric_value=metric_value,
        previous_value=previous_value,
        branch_id=branch_id,
    )
    return {"success": True}


@router.post(
    "/push/dashboard/kpi-batch",
    response_model=dict,
    summary="Push multiple KPI updates",
    tags=["Realtime"],
)
async def api_push_kpi_batch(
    company_id: int,
    kpis: list[dict],
    branch_id: Optional[int] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push multiple KPI updates in a single message."""
    await push_kpi_batch(
        company_id=company_id,
        kpis=kpis,
        branch_id=branch_id,
    )
    return {"success": True, "kpi_count": len(kpis)}


# ---------------------------------------------------------------------------
# Support Inbox Push Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/push/support/message",
    response_model=dict,
    summary="Push a support message",
    tags=["Realtime"],
)
async def api_push_support_message(
    company_id: int,
    ticket_id: str,
    sender_type: str,
    sender_name: str,
    content: str,
    branch_id: Optional[int] = None,
    _=Depends(require_role(["support_agent", "company_admin", "super_admin"])),
) -> dict:
    """Push a new support message to subscribers."""
    msg_id = await push_new_message(
        company_id=company_id,
        ticket_id=ticket_id,
        sender_type=sender_type,
        sender_name=sender_name,
        content=content,
        branch_id=branch_id,
    )
    return {"success": True, "message_id": msg_id}


@router.post(
    "/push/support/ticket-created",
    response_model=dict,
    summary="Push a ticket creation notification",
    tags=["Realtime"],
)
async def api_push_ticket_created(
    company_id: int,
    ticket_id: str,
    ticket_title: str,
    created_by: str,
    branch_id: Optional[int] = None,
    priority: str = "medium",
    _=Depends(require_role(["support_agent", "company_admin", "super_admin"])),
) -> dict:
    """Push a ticket creation notification."""
    await push_ticket_created(
        company_id=company_id,
        ticket_id=ticket_id,
        ticket_title=ticket_title,
        created_by=created_by,
        branch_id=branch_id,
        priority=priority,
    )
    return {"success": True}


@router.post(
    "/push/support/status-change",
    response_model=dict,
    summary="Push a ticket status change",
    tags=["Realtime"],
)
async def api_push_status_change(
    company_id: int,
    ticket_id: str,
    old_status: str,
    new_status: str,
    changed_by: str,
    branch_id: Optional[int] = None,
    _=Depends(require_role(["support_agent", "company_admin", "super_admin"])),
) -> dict:
    """Push a ticket status change notification."""
    await push_ticket_status_change(
        company_id=company_id,
        ticket_id=ticket_id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        branch_id=branch_id,
    )
    return {"success": True}


# ---------------------------------------------------------------------------
# Alert Push Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/push/alert",
    response_model=dict,
    summary="Push a generic alert",
    tags=["Realtime"],
)
async def api_push_alert(
    company_id: int,
    severity: str,
    alert_type: str,
    title: str,
    message: str,
    branch_id: Optional[int] = None,
    metric_name: Optional[str] = None,
    metric_value: Optional[float] = None,
    threshold_value: Optional[float] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push a generic alert to subscribed WebSocket clients."""
    alert_id = await push_alert(
        company_id=company_id,
        severity=severity,
        alert_type=alert_type,
        title=title,
        message=message,
        branch_id=branch_id,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold_value=threshold_value,
    )
    return {"success": True, "alert_id": alert_id}


@router.post(
    "/push/alert/threshold",
    response_model=dict,
    summary="Push a threshold alert",
    tags=["Realtime"],
)
async def api_push_threshold_alert(
    company_id: int,
    metric_name: str,
    current_value: float,
    threshold_value: float,
    operator: str = Query("above", description="above or below"),
    branch_id: Optional[int] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push a threshold-crossing alert."""
    alert_id = await push_threshold_alert(
        company_id=company_id,
        metric_name=metric_name,
        current_value=current_value,
        threshold_value=threshold_value,
        operator=operator,
        branch_id=branch_id,
    )
    return {"success": True, "alert_id": alert_id}


@router.post(
    "/push/alert/inventory",
    response_model=dict,
    summary="Push an inventory low-stock alert",
    tags=["Realtime"],
)
async def api_push_inventory_alert(
    company_id: int,
    product_name: str,
    current_stock: int,
    threshold: int,
    branch_id: Optional[int] = None,
    product_id: Optional[str] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push an inventory low-stock alert."""
    alert_id = await push_inventory_alert(
        company_id=company_id,
        product_name=product_name,
        current_stock=current_stock,
        threshold=threshold,
        branch_id=branch_id,
        product_id=product_id,
    )
    return {"success": True, "alert_id": alert_id}


@router.post(
    "/push/alert/error-spike",
    response_model=dict,
    summary="Push an error rate spike alert",
    tags=["Realtime"],
)
async def api_push_error_spike_alert(
    company_id: int,
    error_rate: float,
    threshold_rate: float,
    time_window: str = Query("5m"),
    branch_id: Optional[int] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push an error rate spike alert."""
    alert_id = await push_error_spike_alert(
        company_id=company_id,
        error_rate=error_rate,
        threshold_rate=threshold_rate,
        time_window=time_window,
        branch_id=branch_id,
    )
    return {"success": True, "alert_id": alert_id}


@router.post(
    "/push/alert/system-health",
    response_model=dict,
    summary="Push a system health alert",
    tags=["Realtime"],
)
async def api_push_system_health_alert(
    company_id: int,
    service_name: str,
    status: str,
    previous_status: str,
    details: Optional[str] = None,
    _=Depends(require_role(["company_admin", "super_admin"])),
) -> dict:
    """Push a system health status change alert."""
    alert_id = await push_system_health_alert(
        company_id=company_id,
        service_name=service_name,
        status=status,
        previous_status=previous_status,
        details=details,
    )
    return {"success": True, "alert_id": alert_id}
