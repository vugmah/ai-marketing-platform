"""WebSocket Gateway Endpoint.

Primary WebSocket handler at /ws:

1. Connection   → Accept, authenticate via JWT token
2. Welcome      → Send welcome message with connection info
3. Subscribe    → Handle channel subscriptions (notifications, dashboard, etc.)
4. Listen       → Keep connection alive with ping/pong
5. Push         → Receive events from Redis pub/sub and push to client
6. Disconnect   → Clean up connection metadata

Protocol:
    Client → Server (text JSON):
        {"type": "subscribe",   "channel": "notifications", "branch_id": 1}
        {"type": "unsubscribe", "channel": "dashboard"}
        {"type": "ping",        "timestamp": 1716000000.0}
        {"type": "ack",         "message_id": "msg_abc123"}

    Server → Client (text JSON):
        {"msg_type": "welcome",           ...}
        {"msg_type": "subscribed",        ...}
        {"msg_type": "unsubscribed",      ...}
        {"msg_type": "pong",              ...}
        {"msg_type": "notification",      ...}
        {"msg_type": "dashboard_update",  ...}
        {"msg_type": "support_message",   ...}
        {"msg_type": "alert",             ...}
        {"msg_type": "error",             ...}
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings
from app.realtime.manager import ConnectionManager, get_connection_manager
from app.realtime.publisher import get_pubsub_bridge
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WS_HEARTBEAT_INTERVAL = 30  # seconds between server pings
WS_MAX_INACTIVITY = 90  # seconds before disconnecting idle client


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _extract_token_from_query(query_string: str) -> Optional[str]:
    """Extract JWT token from query string (e.g. '?token=xyz')."""
    if not query_string:
        return None
    # Remove leading '?'
    qs = query_string.lstrip("?")
    for param in qs.split("&"):
        if "=" in param:
            key, value = param.split("=", 1)
            if key == "token":
                return value
    return None


async def _authenticate_websocket(websocket: WebSocket) -> Dict[str, Any]:
    """Authenticate a WebSocket connection via JWT token.

    Token priority:
    1. query parameter '?token=...'
    2. subprotocol header (Sec-WebSocket-Protocol: token,...)

    Args:
        websocket: The WebSocket instance.

    Returns:
        Dict with user_id, company_id, role if auth succeeds.

    Raises:
        WebSocketException: If authentication fails.
    """
    # Try query parameter
    token = _extract_token_from_query(websocket.query_string.decode("utf-8"))

    # Try subprotocol
    if token is None:
        subprotocols = websocket.scope.get("subprotocols", [])
        for proto in subprotocols:
            if proto.startswith("token,"):
                token = proto.replace("token,", "", 1)
                break

    if token is None:
        raise ValueError("No authentication token provided")

    # Verify JWT
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError("Invalid token payload: missing 'sub'")

    # Check Redis for revoked token
    redis = await get_redis_client()
    revoked = await redis.get(f"revoked:{token}")
    if revoked:
        raise ValueError("Token has been revoked")

    # Get user details from Redis cache if available
    user_cache_key = f"user:ws:{user_id}"
    cached = await redis.get(user_cache_key)
    if cached:
        try:
            if isinstance(cached, str):
                user_data = json.loads(cached)
            else:
                user_data = json.loads(cached.decode("utf-8"))
            return {
                "user_id": int(user_id),
                "company_id": user_data.get("company_id"),
                "role": user_data.get("role", ""),
                "email": user_data.get("email", ""),
            }
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: return basic info from token
    return {
        "user_id": int(user_id),
        "company_id": payload.get("company_id"),
        "role": payload.get("role", ""),
        "email": payload.get("email", ""),
    }


# ---------------------------------------------------------------------------
# Message Handlers (Client → Server)
# ---------------------------------------------------------------------------


async def _handle_subscribe(
    connection_id: str,
    data: Dict[str, Any],
    manager: ConnectionManager,
) -> Dict[str, Any]:
    """Handle subscription request."""
    channel = data.get("channel", "")
    branch_id_raw = data.get("branch_id")
    branch_id = int(branch_id_raw) if branch_id_raw is not None else None

    success = manager.subscribe(connection_id, channel, branch_id)
    if success:
        return {
            "msg_type": "subscribed",
            "message_id": f"msg_{connection_id[:8]}",
            "timestamp": time.time(),
            "payload": {
                "channel": channel,
                "branch_id": branch_id,
                "message": f"Subscribed to {channel}",
            },
        }
    return {
        "msg_type": "error",
        "message_id": f"msg_{connection_id[:8]}",
        "timestamp": time.time(),
        "payload": {
            "code": "subscribe_failed",
            "message": f"Failed to subscribe to channel: {channel}",
        },
    }


async def _handle_unsubscribe(
    connection_id: str,
    data: Dict[str, Any],
    manager: ConnectionManager,
) -> Dict[str, Any]:
    """Handle unsubscription request."""
    channel = data.get("channel", "")
    success = manager.unsubscribe(connection_id, channel)
    if success:
        return {
            "msg_type": "unsubscribed",
            "message_id": f"msg_{connection_id[:8]}",
            "timestamp": time.time(),
            "payload": {
                "channel": channel,
                "message": f"Unsubscribed from {channel}",
            },
        }
    return {
        "msg_type": "error",
        "message_id": f"msg_{connection_id[:8]}",
        "timestamp": time.time(),
        "payload": {
            "code": "unsubscribe_failed",
            "message": f"Failed to unsubscribe from channel: {channel}",
        },
    }


async def _handle_ping(
    connection_id: str,
    data: Dict[str, Any],
    manager: ConnectionManager,
) -> Dict[str, Any]:
    """Handle ping (heartbeat)."""
    manager.update_ping(connection_id)
    client_time = data.get("timestamp")
    return {
        "msg_type": "pong",
        "message_id": f"msg_{connection_id[:8]}",
        "timestamp": time.time(),
        "payload": {
            "server_time": time.time(),
            "client_time": client_time,
        },
    }


async def _handle_ack(
    connection_id: str,
    data: Dict[str, Any],
    manager: ConnectionManager,
) -> None:
    """Handle client acknowledgment (no response needed)."""
    message_id = data.get("message_id")
    logger.debug("ACK received: conn=%s msg=%s", connection_id, message_id)
    return None


# Message type → handler mapping
_INBOUND_HANDLERS = {
    "subscribe": _handle_subscribe,
    "unsubscribe": _handle_unsubscribe,
    "ping": _handle_ping,
    "ack": _handle_ack,
}


# ---------------------------------------------------------------------------
# Main WebSocket Endpoint
# ---------------------------------------------------------------------------


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint handler.

    Handles the full lifecycle of a WebSocket connection:
    1. Accept & authenticate
    2. Send welcome message
    3. Enter message loop (receive + heartbeat)
    4. Cleanup on disconnect
    """
    await websocket.accept()

    connection_id: Optional[str] = None
    manager = get_connection_manager()

    try:
        # ---- Step 1: Authenticate ----
        try:
            auth_info = await _authenticate_websocket(websocket)
        except ValueError as exc:
            logger.warning("WebSocket auth failed: %s", exc)
            await websocket.send_json({
                "msg_type": "error",
                "message_id": "msg_auth_fail",
                "timestamp": time.time(),
                "payload": {
                    "code": "auth_failed",
                    "message": str(exc),
                },
            })
            await websocket.close(code=4001, reason="Authentication failed")
            return

        user_id = auth_info["user_id"]
        company_id = auth_info.get("company_id")
        user_role = auth_info.get("role", "")

        # ---- Step 2: Register connection ----
        meta = await manager.connect(
            websocket=websocket,
            user_id=user_id,
            company_id=company_id,
            user_role=user_role,
        )
        connection_id = meta.connection_id

        # Ensure the pub/sub bridge is running
        await get_pubsub_bridge()

        # ---- Step 3: Send welcome message ----
        await websocket.send_json({
            "msg_type": "welcome",
            "message_id": f"msg_{connection_id[:8]}",
            "timestamp": time.time(),
            "payload": {
                "connection_id": connection_id,
                "user_id": user_id,
                "company_id": company_id,
                "subscribed_channels": [],
                "server_time": time.time(),
                "message": "Connected to realtime gateway",
            },
        })

        logger.info(
            "WebSocket ready: conn=%s user=%s company=%s role=%s",
            connection_id,
            user_id,
            company_id,
            user_role,
        )

        # ---- Step 4: Message loop + heartbeat ----
        last_activity = time.time()

        while True:
            try:
                # Wait for client message with timeout for heartbeat
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WS_HEARTBEAT_INTERVAL,
                )
                last_activity = time.time()

                # Parse JSON
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "msg_type": "error",
                        "message_id": f"msg_{connection_id[:8]}",
                        "timestamp": time.time(),
                        "payload": {
                            "code": "invalid_json",
                            "message": "Invalid JSON payload",
                        },
                    })
                    continue

                # Route to handler
                msg_type = data.get("type", "")
                handler = _INBOUND_HANDLERS.get(msg_type)

                if handler is None:
                    await websocket.send_json({
                        "msg_type": "error",
                        "message_id": f"msg_{connection_id[:8]}",
                        "timestamp": time.time(),
                        "payload": {
                            "code": "unknown_type",
                            "message": f"Unknown message type: {msg_type}",
                            "valid_types": list(_INBOUND_HANDLERS.keys()),
                        },
                    })
                    continue

                response = await handler(connection_id, data, manager)
                if response is not None:
                    await websocket.send_json(response)

            except asyncio.TimeoutError:
                # Send heartbeat ping
                now = time.time()
                if (now - last_activity) > WS_MAX_INACTIVITY:
                    logger.info(
                        "WebSocket idle timeout: conn=%s", connection_id
                    )
                    break

                # Check connection health
                if connection_id and not manager._connections.get(connection_id, (None, None))[1].is_alive:
                    logger.info("WebSocket stale: conn=%s", connection_id)
                    break

                # Send server-side ping (pong response expected from client)
                try:
                    await websocket.send_json({
                        "msg_type": "pong",
                        "message_id": f"hb_{connection_id[:8]}",
                        "timestamp": time.time(),
                        "payload": {"server_time": time.time()},
                    })
                except Exception:
                    logger.debug("Failed to send heartbeat to conn=%s", connection_id)
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: conn=%s", connection_id)
    except Exception as exc:
        logger.error(
            "WebSocket error: conn=%s error=%s",
            connection_id,
            exc,
            exc_info=True,
        )
    finally:
        # ---- Step 5: Cleanup ----
        if connection_id:
            try:
                await manager.disconnect(connection_id)
            except Exception as exc:
                logger.warning("Disconnect cleanup error: %s", exc)
        try:
            await websocket.close()
        except Exception:
            pass
