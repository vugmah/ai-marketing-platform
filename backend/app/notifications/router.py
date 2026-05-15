"""Notifications router for user notification management.

Stores notifications in Redis (list per user) and provides endpoints to
list, mark as read, delete, and bulk-mark notifications.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branches.models import Branch
from app.companies.models import Company, SubscriptionStatus
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.redis_client import get_redis_client

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOTIFICATIONS_LIST_PREFIX = "notifications"
MAX_NOTIFICATIONS = 20  # Return last 20 notifications


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _notif_redis_key(user_id: int) -> str:
    """Build the Redis list key for a user's notifications."""
    return f"{NOTIFICATIONS_LIST_PREFIX}:{user_id}"


def _generate_notification_id() -> str:
    """Generate a unique notification ID."""
    return f"notif_{uuid.uuid4().hex[:6]}"


def _now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_notification(
    notif_type: str,
    title: str,
    message: str,
    is_read: bool = False,
) -> dict:
    """Create a notification dict with a unique ID."""
    return {
        "id": _generate_notification_id(),
        "type": notif_type,
        "title": title,
        "message": message,
        "is_read": is_read,
        "created_at": _now_iso(),
    }


async def _generate_default_notifications(
    user: User,
    db: AsyncSession,
) -> List[dict]:
    """Generate contextual default notifications based on user state.

    Rules:
        - Trial ending soon → info notification
        - Low AI credits    → warning notification
        - New branch added  → success notification
    """
    notifications: List[dict] = []

    if user.company_id is not None:
        # Fetch company details
        result = await db.execute(
            select(Company).where(Company.id == user.company_id)
        )
        company = result.scalar_one_or_none()

        if company is not None:
            # Trial ending notification
            if company.subscription_status == SubscriptionStatus.TRIAL:
                notifications.append(
                    _create_notification(
                        notif_type="info",
                        title="Deneme suresi bitiyor",
                        message="Deneme sureniz 3 gun icinde bitecek. Plan yukseltin.",
                    )
                )

            # Low AI credits (assume under 20% remaining)
            if company.ai_requests_limit is not None and company.ai_requests_limit <= 100:
                notifications.append(
                    _create_notification(
                        notif_type="warning",
                        title="AI Kredisi Dusuk",
                        message="Kalan AI krediniz %20. Yukseklmek icin planinizi guncelleyin.",
                    )
                )

            # Branch-related notification
            branch_result = await db.execute(
                select(func.count()).select_from(Branch).where(Branch.company_id == company.id)
            )
            branch_count = branch_result.scalar() or 0

            if branch_count > 0:
                notifications.append(
                    _create_notification(
                        notif_type="success",
                        title="Yeni sube eklendi",
                        message=f"Sirketinize {branch_count} sube kayitli. Yeni subeler eklemeye devam edin.",
                    )
                )

    # If no contextual notifications were generated, add generic ones
    if not notifications:
        notifications.append(
            _create_notification(
                notif_type="info",
                title="Platforma xos geldiniz",
                message="AI Marketing Platform-a qeydiyyat tamamlandi.",
            )
        )
        notifications.append(
            _create_notification(
                notif_type="warning",
                title="AI Kredisi Dusuk",
                message="Kalan AI krediniz %20",
            )
        )

    return notifications


async def _get_notifications_from_redis(
    redis: Redis,
    user_id: int,
) -> List[dict]:
    """Fetch notifications from Redis list (newest first)."""
    key = _notif_redis_key(user_id)
    raw_items = await redis.lrange(key, 0, MAX_NOTIFICATIONS - 1)
    notifications: List[dict] = []
    for raw in raw_items:
        try:
            if isinstance(raw, str):
                notifications.append(json.loads(raw))
            elif isinstance(raw, bytes):
                notifications.append(json.loads(raw.decode("utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return notifications


async def _save_notifications_to_redis(
    redis: Redis,
    user_id: int,
    notifications: List[dict],
) -> None:
    """Save notifications to Redis list (LPUSH for newest-first)."""
    key = _notif_redis_key(user_id)
    # Clear existing list
    await redis.delete(key)
    # Push each notification (LPUSH puts newest at head)
    pipe = redis.pipeline()
    for notif in notifications:
        pipe.lpush(key, json.dumps(notif))
    await pipe.execute()


# ---------------------------------------------------------------------------
# GET /api/v2/notifications
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List user notifications",
)
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the current user's notifications (last 20).

    If no notifications exist in Redis, generates contextual defaults
    based on company/branch status and persists them to Redis.
    """
    redis = await get_redis_client()
    notifications = await _get_notifications_from_redis(redis, current_user.id)

    if not notifications:
        # Generate and persist defaults
        notifications = await _generate_default_notifications(current_user, db)
        await _save_notifications_to_redis(redis, current_user.id, notifications)

    unread_count = sum(1 for n in notifications if not n.get("is_read", False))

    return {
        "success": True,
        "data": notifications,
        "unread_count": unread_count,
    }


# ---------------------------------------------------------------------------
# PATCH /api/v2/notifications/{notification_id}/read
# ---------------------------------------------------------------------------


@router.patch(
    "/{notification_id}/read",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark a single notification as read by its ID."""
    redis = await get_redis_client()
    notifications = await _get_notifications_from_redis(redis, current_user.id)

    found = False
    for notif in notifications:
        if notif.get("id") == notification_id:
            notif["is_read"] = True
            found = True
            break

    if not found:
        raise NotFoundError(detail=f"Notification '{notification_id}' not found")

    await _save_notifications_to_redis(redis, current_user.id, notifications)

    return {"success": True, "data": {"id": notification_id, "is_read": True}}


# ---------------------------------------------------------------------------
# DELETE /api/v2/notifications/{notification_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification",
)
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a notification by its ID."""
    redis = await get_redis_client()
    notifications = await _get_notifications_from_redis(redis, current_user.id)

    filtered = [n for n in notifications if n.get("id") != notification_id]

    if len(filtered) == len(notifications):
        raise NotFoundError(detail=f"Notification '{notification_id}' not found")

    await _save_notifications_to_redis(redis, current_user.id, filtered)


# ---------------------------------------------------------------------------
# POST /api/v2/notifications/read-all
# ---------------------------------------------------------------------------


@router.post(
    "/read-all",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark all of the current user's notifications as read."""
    redis = await get_redis_client()
    notifications = await _get_notifications_from_redis(redis, current_user.id)

    for notif in notifications:
        notif["is_read"] = True

    await _save_notifications_to_redis(redis, current_user.id, notifications)

    return {"success": True, "data": {"marked_read": len(notifications)}}
