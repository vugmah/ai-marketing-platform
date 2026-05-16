"""Realtime Notification Push Service.

Listens for notification events and pushes them to WebSocket subscribers.

Flow:
    1. EventBus publishes 'notification.new' → Redis
    2. RedisPubSubBridge routes to ConnectionManager
    3. ConnectionManager delivers to subscribed WebSocket clients

Usage from other modules:
    from app.realtime.notifications import push_notification
    await push_notification(user_id=42, company_id=5, notification={...})
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

REALTIME_CHANNEL_PREFIX = "realtime"


async def push_notification(
    user_id: int,
    company_id: int,
    title: str,
    message: str,
    notif_type: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
    notification_id: Optional[str] = None,
) -> str:
    """Push a realtime notification to a user via WebSocket.

    Args:
        user_id: Target user ID.
        company_id: Target company ID.
        title: Notification title.
        message: Notification body.
        notif_type: Type of notification (info, warning, success, error).
        metadata: Optional additional data.
        notification_id: Optional explicit ID (auto-generated if not provided).

    Returns:
        The notification ID that was sent.
    """
    notif_id = notification_id or f"notif_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": notif_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_id": user_id,
        "company_id": company_id,
        "metadata": metadata or {},
    }

    # Also persist to Redis notification list for offline retrieval
    redis = await get_redis_client()
    notif_key = f"notifications:{user_id}"
    await redis.lpush(notif_key, payload)
    await redis.ltrim(notif_key, 0, 99)  # Keep last 100

    # Publish to realtime channel
    await redis.publish(
        f"{REALTIME_CHANNEL_PREFIX}:notifications",
        payload,
    )

    logger.debug(
        "Pushed notification %s to user=%s company=%s",
        notif_id,
        user_id,
        company_id,
    )
    return notif_id


async def push_notification_bulk(
    user_ids: list[int],
    company_id: int,
    title: str,
    message: str,
    notif_type: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
) -> list[str]:
    """Push a notification to multiple users at once.

    Args:
        user_ids: List of target user IDs.
        company_id: Company ID.
        title: Notification title.
        message: Notification body.
        notif_type: Type of notification.
        metadata: Optional additional data.

    Returns:
        List of notification IDs that were sent.
    """
    notif_ids = []
    for uid in user_ids:
        nid = await push_notification(
            user_id=uid,
            company_id=company_id,
            title=title,
            message=message,
            notif_type=notif_type,
            metadata=metadata,
        )
        notif_ids.append(nid)
    logger.info(
        "Bulk pushed notification to %d users in company=%s",
        len(user_ids),
        company_id,
    )
    return notif_ids


async def push_company_broadcast(
    company_id: int,
    title: str,
    message: str,
    notif_type: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Broadcast a notification to ALL users in a company.

    Uses Redis pub/sub for delivery. All connected users in the company
    receive this notification instantly.

    Args:
        company_id: Target company ID.
        title: Notification title.
        message: Notification body.
        notif_type: Type of notification.
        metadata: Optional additional data.

    Returns:
        The broadcast notification ID.
    """
    notif_id = f"notif_broadcast_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": notif_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "company_id": company_id,
        "broadcast": True,
        "metadata": metadata or {},
    }

    redis = await get_redis_client()
    await redis.publish(
        f"{REALTIME_CHANNEL_PREFIX}:notifications",
        payload,
    )

    logger.info(
        "Broadcast notification %s to company=%s",
        notif_id,
        company_id,
    )
    return notif_id


# ---------------------------------------------------------------------------
# Event Handlers (called by EventBus on specific events)
# ---------------------------------------------------------------------------


async def on_user_registered(event_payload: Dict[str, Any]) -> None:
    """Handle user_registered event → notify company admins."""
    company_id = event_payload.get("company_id")
    user_id = event_payload.get("user_id")
    if company_id and user_id:
        await push_company_broadcast(
            company_id=company_id,
            title="Yeni kullanici kaydi",
            message=f"Kullanici #{user_id} platforma kaydoldu.",
            notif_type="info",
        )


async def on_order_created(event_payload: Dict[str, Any]) -> None:
    """Handle order_created event → notify relevant users."""
    company_id = event_payload.get("company_id")
    branch_id = event_payload.get("branch_id")
    order_id = event_payload.get("order_id")
    if company_id:
        msg = f"Yeni siparis alindi: #{order_id}"
        if branch_id:
            msg += f" (Sube: {branch_id})"
        await push_company_broadcast(
            company_id=company_id,
            title="Yeni Siparis",
            message=msg,
            notif_type="success",
            metadata={"order_id": order_id, "branch_id": branch_id},
        )


async def on_erp_sync_completed(event_payload: Dict[str, Any]) -> None:
    """Handle erp_sync_completed event → notify company."""
    company_id = event_payload.get("company_id")
    if company_id:
        await push_company_broadcast(
            company_id=company_id,
            title="ERP Senkronizasyonu Tamamlandi",
            message="ERP verileri basariyla senkronize edildi.",
            notif_type="success",
        )


async def on_erp_sync_failed(event_payload: Dict[str, Any]) -> None:
    """Handle erp_sync_failed event → notify company admins."""
    company_id = event_payload.get("company_id")
    error = event_payload.get("error", "Bilinmeyen hata")
    if company_id:
        await push_company_broadcast(
            company_id=company_id,
            title="ERP Senkronizasyonu Basarisiz",
            message=f"ERP senkronizasyonu basarisiz oldu: {error}",
            notif_type="error",
            metadata={"error": error},
        )


async def on_campaign_created(event_payload: Dict[str, Any]) -> None:
    """Handle campaign_created event → notify company."""
    company_id = event_payload.get("company_id")
    campaign_name = event_payload.get("campaign_name", "Yeni Kampanya")
    if company_id:
        await push_company_broadcast(
            company_id=company_id,
            title="Yeni Kampanya Olusturuldu",
            message=f"'{campaign_name}' kampanyasi basariyla olusturuldu.",
            notif_type="success",
            metadata={"campaign_name": campaign_name},
        )
