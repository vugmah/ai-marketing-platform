"""Redis Pub/Sub → WebSocket Bridge.

Listens on Redis pub/sub channels for events published by the EventBus
(or any other module) and forwards them to subscribed WebSocket connections
via the ConnectionManager.

Channels:
- events:channel:*        → Forwarded as generic 'event' messages
- realtime:notifications  → Forwarded as 'notification' messages
- realtime:dashboard      → Forwarded as 'dashboard_update' messages
- realtime:support        → Forwarded as 'support_message' messages
- realtime:alerts         → Forwarded as 'alert' messages
- realtime:broadcast      → Broadcast to all connections
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from app.config import settings
from app.events.constants import REDIS_CHANNEL_PREFIX
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Channel Mapping: Redis channel → WS outbound type + WS channel
# ---------------------------------------------------------------------------

REALTIME_CHANNEL_PREFIX = "realtime"

CHANNEL_MAP: Dict[str, Dict[str, str]] = {
    f"{REALTIME_CHANNEL_PREFIX}:notifications": {
        "msg_type": "notification",
        "ws_channel": "notifications",
    },
    f"{REALTIME_CHANNEL_PREFIX}:dashboard": {
        "msg_type": "dashboard_update",
        "ws_channel": "dashboard",
    },
    f"{REALTIME_CHANNEL_PREFIX}:support": {
        "msg_type": "support_message",
        "ws_channel": "support_inbox",
    },
    f"{REALTIME_CHANNEL_PREFIX}:alerts": {
        "msg_type": "alert",
        "ws_channel": "alerts",
    },
    f"{REALTIME_CHANNEL_PREFIX}:broadcast": {
        "msg_type": "event",
        "ws_channel": "all",
    },
}

# ---------------------------------------------------------------------------
# Redis Pub/Sub Bridge
# ---------------------------------------------------------------------------


class RedisPubSubBridge:
    """Bridge between Redis pub/sub and WebSocket connections.

    Subscribes to Redis channels and forwards messages to the
    ConnectionManager for delivery to WebSocket clients.
    """

    _instance: Optional["RedisPubSubBridge"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "RedisPubSubBridge":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._redis = None
        self._pubsub = None
        self._running = False
        self._listener_task: Optional[asyncio.Task] = None
        self._handlers: Dict[str, List[Callable]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Redis pub/sub bridge."""
        if self._running:
            return
        self._running = True
        self._redis = await get_redis_client()
        self._pubsub = self._redis.pubsub()

        # Subscribe to all mapped channels + event bus wildcard
        channels = list(CHANNEL_MAP.keys())
        channels.append(f"{REDIS_CHANNEL_PREFIX}:*")
        channels.append(f"{REALTIME_CHANNEL_PREFIX}:*")

        await self._pubsub.psubscribe(*channels)
        self._listener_task = asyncio.create_task(
            self._listen(),
            name="redis_pubsub_bridge",
        )

        logger.info(
            "RedisPubSubBridge started with channels: %s",
            channels,
        )

    async def stop(self) -> None:
        """Gracefully stop the bridge."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        logger.info("RedisPubSubBridge stopped")

    # ------------------------------------------------------------------
    # Listener Loop
    # ------------------------------------------------------------------

    async def _listen(self) -> None:
        """Main listen loop for Redis pub/sub messages."""
        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break
                if message["type"] not in ("pmessage", "message"):
                    continue

                channel = message.get("channel", "")
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8")

                data = message.get("data", b"")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    payload = {"raw": data}

                await self._route_message(channel, payload)
        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener cancelled")
        except Exception as exc:
            logger.error("Redis pub/sub listener error: %s", exc, exc_info=True)

    async def _route_message(self, channel: str, payload: Dict[str, Any]) -> None:
        """Route a Redis message to the appropriate handler.

        Args:
            channel: Redis channel name.
            payload: Parsed JSON payload.
        """
        # Import here to avoid circular imports
        from app.realtime.manager import get_connection_manager

        manager = get_connection_manager()

        # 1. Direct realtime channel → immediate WebSocket push
        if channel in CHANNEL_MAP:
            mapping = CHANNEL_MAP[channel]
            msg_type = mapping["msg_type"]
            ws_channel = mapping["ws_channel"]

            company_id = payload.get("company_id")
            branch_id = payload.get("branch_id")

            envelope = {
                "msg_type": msg_type,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "timestamp": time.time(),
                "payload": payload,
            }

            if ws_channel == "all":
                # Broadcast to everyone
                await manager.broadcast(envelope)
            elif company_id is not None:
                await manager.broadcast_to_company(
                    company_id=company_id,
                    message=envelope,
                    channel=ws_channel,
                    branch_id=branch_id,
                )
            else:
                await manager.broadcast_to_channel(ws_channel, envelope)

            # Execute custom handlers
            for handler in self._handlers.get(channel, []):
                try:
                    await handler(payload)
                except Exception as exc:
                    logger.warning("Handler error on channel %s: %s", channel, exc)

            return

        # 2. Event bus channel → forward as generic 'event' message
        if channel.startswith(f"{REDIS_CHANNEL_PREFIX}:"):
            event_name = channel.replace(f"{REDIS_CHANNEL_PREFIX}:", "")
            company_id = payload.get("company_id")
            branch_id = payload.get("branch_id")
            user_id = payload.get("user_id")

            envelope = {
                "msg_type": "event",
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "timestamp": time.time(),
                "payload": {
                    "event_name": event_name,
                    **payload,
                },
            }

            # If user-specific event, send to that user only
            if user_id is not None:
                await manager.send_to_user(user_id, envelope)
            elif company_id is not None:
                await manager.broadcast_to_company(
                    company_id=company_id,
                    message=envelope,
                    channel="events",
                    branch_id=branch_id,
                )
            else:
                await manager.broadcast_to_channel("events", envelope)

            return

        # 3. Pattern-matched realtime channels
        if channel.startswith(f"{REALTIME_CHANNEL_PREFIX}:"):
            for mapped_channel, mapping in CHANNEL_MAP.items():
                if channel == mapped_channel:
                    break
            else:
                # Unknown realtime channel, broadcast anyway
                envelope = {
                    "msg_type": "event",
                    "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                    "timestamp": time.time(),
                    "payload": payload,
                }
                await manager.broadcast(envelope)

    # ------------------------------------------------------------------
    # Publish Helpers (for use from other modules)
    # ------------------------------------------------------------------

    async def publish_notification(
        self,
        user_id: int,
        company_id: int,
        notification: Dict[str, Any],
    ) -> None:
        """Publish a notification to the realtime channel.

        Args:
            user_id: Target user ID.
            company_id: Target company ID.
            notification: Notification payload dict.
        """
        redis = await get_redis_client()
        payload = {
            "user_id": user_id,
            "company_id": company_id,
            **notification,
        }
        await redis.publish(
            f"{REALTIME_CHANNEL_PREFIX}:notifications",
            json.dumps(payload),
        )
        logger.debug("Published notification for user=%s", user_id)

    async def publish_dashboard_update(
        self,
        company_id: int,
        branch_id: Optional[int],
        kpis: List[Dict[str, Any]],
    ) -> None:
        """Publish a dashboard KPI update.

        Args:
            company_id: Target company ID.
            branch_id: Optional branch ID for branch-scoped updates.
            kpis: List of KPI update dicts.
        """
        redis = await get_redis_client()
        payload = {
            "company_id": company_id,
            "branch_id": branch_id,
            "kpis": kpis,
            "timestamp": time.time(),
        }
        await redis.publish(
            f"{REALTIME_CHANNEL_PREFIX}:dashboard",
            json.dumps(payload),
        )

    async def publish_support_message(
        self,
        company_id: int,
        ticket_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Publish a new support message.

        Args:
            company_id: Target company ID.
            ticket_id: Support ticket ID.
            message: Message payload dict.
        """
        redis = await get_redis_client()
        payload = {
            "company_id": company_id,
            "ticket_id": ticket_id,
            **message,
        }
        await redis.publish(
            f"{REALTIME_CHANNEL_PREFIX}:support",
            json.dumps(payload),
        )

    async def publish_alert(
        self,
        company_id: int,
        alert: Dict[str, Any],
    ) -> None:
        """Publish a realtime alert.

        Args:
            company_id: Target company ID.
            alert: Alert payload dict.
        """
        redis = await get_redis_client()
        payload = {
            "company_id": company_id,
            **alert,
        }
        await redis.publish(
            f"{REALTIME_CHANNEL_PREFIX}:alerts",
            json.dumps(payload),
        )

    async def publish_broadcast(self, payload: Dict[str, Any]) -> None:
        """Publish a message to all connected clients.

        Args:
            payload: Message payload dict.
        """
        redis = await get_redis_client()
        await redis.publish(
            f"{REALTIME_CHANNEL_PREFIX}:broadcast",
            json.dumps(payload),
        )

    # ------------------------------------------------------------------
    # Custom Handlers
    # ------------------------------------------------------------------

    def add_handler(self, channel: str, handler: Callable) -> None:
        """Add a custom handler for a specific channel.

        Args:
            channel: Redis channel name.
            handler: Async callable receiving the payload dict.
        """
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)
        logger.info("Added custom handler for channel: %s", channel)


# ---------------------------------------------------------------------------
# Singleton Getter
# ---------------------------------------------------------------------------

_bridge_instance: Optional[RedisPubSubBridge] = None


async def get_pubsub_bridge() -> RedisPubSubBridge:
    """Get or create the RedisPubSubBridge singleton."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = RedisPubSubBridge()
        await _bridge_instance.start()
    return _bridge_instance


async def close_pubsub_bridge() -> None:
    """Shutdown the bridge."""
    global _bridge_instance
    if _bridge_instance is not None:
        await _bridge_instance.stop()
        _bridge_instance = None
