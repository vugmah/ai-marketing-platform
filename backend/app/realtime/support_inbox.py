"""Live Support Inbox Service.

Pushes real-time support ticket and message updates to WebSocket subscribers.

Use cases:
- New support ticket created
- New message on a ticket
- Ticket status change (open → resolved)
- Agent assigned to ticket
- AI response generated

Usage:
    from app.realtime.support_inbox import (
        push_ticket_created, push_new_message, push_ticket_status_change
    )
    await push_new_message(company_id=5, ticket_id="TICK-42", message={...})
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

REALTIME_CHANNEL_PREFIX = "realtime"


async def push_ticket_created(
    company_id: int,
    ticket_id: str,
    ticket_title: str,
    created_by: str,
    branch_id: Optional[int] = None,
    priority: str = "medium",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Push a new support ticket notification.

    Args:
        company_id: Target company ID.
        ticket_id: Support ticket ID.
        ticket_title: Ticket title.
        created_by: Name of the user who created the ticket.
        branch_id: Optional branch ID.
        priority: Ticket priority (low, medium, high, critical).
        metadata: Optional extra data.
    """
    message_id = f"msg_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_id": company_id,
        "branch_id": branch_id,
        "ticket_id": ticket_id,
        "message_id": message_id,
        "sender_type": "system",
        "sender_name": "Sistem",
        "content": f"Yeni destek talebi olusturuldu: '{ticket_title}' ({created_by})",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "ticket_created",
        "priority": priority,
        "metadata": {
            "ticket_title": ticket_title,
            "created_by": created_by,
            **(metadata or {}),
        },
    }

    redis = await get_redis_client()
    await redis.publish(f"{REALTIME_CHANNEL_PREFIX}:support", payload)
    logger.debug("Pushed ticket_created: %s for company=%s", ticket_id, company_id)


async def push_new_message(
    company_id: int,
    ticket_id: str,
    sender_type: str,
    sender_name: str,
    content: str,
    branch_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Push a new message on a support ticket.

    Args:
        company_id: Target company ID.
        ticket_id: Support ticket ID.
        sender_type: "user" | "agent" | "ai".
        sender_name: Name of the sender.
        content: Message content.
        branch_id: Optional branch ID.
        metadata: Optional extra data.

    Returns:
        The message ID.
    """
    message_id = f"msg_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_id": company_id,
        "branch_id": branch_id,
        "ticket_id": ticket_id,
        "message_id": message_id,
        "sender_type": sender_type,
        "sender_name": sender_name,
        "content": content,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "new_message",
        "metadata": metadata or {},
    }

    redis = await get_redis_client()
    await redis.publish(f"{REALTIME_CHANNEL_PREFIX}:support", payload)
    logger.debug(
        "Pushed message %s on ticket %s (sender=%s)",
        message_id,
        ticket_id,
        sender_name,
    )
    return message_id


async def push_ticket_status_change(
    company_id: int,
    ticket_id: str,
    old_status: str,
    new_status: str,
    changed_by: str,
    branch_id: Optional[int] = None,
) -> None:
    """Push a ticket status change notification.

    Args:
        company_id: Target company ID.
        ticket_id: Support ticket ID.
        old_status: Previous status.
        new_status: New status.
        changed_by: Name of the user who changed the status.
        branch_id: Optional branch ID.
    """
    message_id = f"msg_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_id": company_id,
        "branch_id": branch_id,
        "ticket_id": ticket_id,
        "message_id": message_id,
        "sender_type": "system",
        "sender_name": "Sistem",
        "content": f"Talep durumu degisti: {old_status} -> {new_status} ({changed_by})",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "status_change",
        "metadata": {
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": changed_by,
        },
    }

    redis = await get_redis_client()
    await redis.publish(f"{REALTIME_CHANNEL_PREFIX}:support", payload)
    logger.debug(
        "Pushed status change on ticket %s: %s -> %s",
        ticket_id,
        old_status,
        new_status,
    )


async def push_agent_assigned(
    company_id: int,
    ticket_id: str,
    agent_name: str,
    branch_id: Optional[int] = None,
) -> None:
    """Push an agent assignment notification.

    Args:
        company_id: Target company ID.
        ticket_id: Support ticket ID.
        agent_name: Name of the assigned agent.
        branch_id: Optional branch ID.
    """
    message_id = f"msg_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_id": company_id,
        "branch_id": branch_id,
        "ticket_id": ticket_id,
        "message_id": message_id,
        "sender_type": "system",
        "sender_name": "Sistem",
        "content": f"Talebe '{agent_name}' atanmistir.",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "agent_assigned",
        "metadata": {"agent_name": agent_name},
    }

    redis = await get_redis_client()
    await redis.publish(f"{REALTIME_CHANNEL_PREFIX}:support", payload)


async def push_ai_response(
    company_id: int,
    ticket_id: str,
    ai_response: str,
    confidence: Optional[float] = None,
    branch_id: Optional[int] = None,
) -> None:
    """Push an AI-generated response to a support ticket.

    Args:
        company_id: Target company ID.
        ticket_id: Support ticket ID.
        ai_response: The AI-generated response text.
        confidence: Optional confidence score (0-1).
        branch_id: Optional branch ID.
    """
    message_id = f"msg_{uuid.uuid4().hex[:8]}"
    payload = {
        "company_id": company_id,
        "branch_id": branch_id,
        "ticket_id": ticket_id,
        "message_id": message_id,
        "sender_type": "ai",
        "sender_name": "AI Asistan",
        "content": ai_response,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "ai_response",
        "metadata": {"confidence": confidence} if confidence else {},
    }

    redis = await get_redis_client()
    await redis.publish(f"{REALTIME_CHANNEL_PREFIX}:support", payload)
    logger.debug("Pushed AI response on ticket %s", ticket_id)


async def push_unread_count(
    user_id: int,
    company_id: int,
    unread_count: int,
) -> None:
    """Push the unread support message count to a user.

    Args:
        user_id: Target user ID.
        company_id: Company ID.
        unread_count: Number of unread messages.
    """
    redis = await get_redis_client()
    await redis.publish(
        f"{REALTIME_CHANNEL_PREFIX}:support",
        {
            "user_id": user_id,
            "company_id": company_id,
            "unread_count": unread_count,
            "timestamp": time.time(),
            "event": "unread_count",
        },
    )
