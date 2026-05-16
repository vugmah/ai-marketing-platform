"""WebSocket Connection Manager.

Manages all active WebSocket connections with:
- Connection registration/deregistration with metadata (user, company, branch)
- Channel-based subscriptions scoped per connection
- Targeted and broadcast message delivery
- Automatic connection health tracking
- Message acknowledgment tracking for reliable delivery
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection Metadata
# ---------------------------------------------------------------------------


@dataclass
class ConnectionMeta:
    """Metadata for a single WebSocket connection."""

    connection_id: str
    user_id: int
    company_id: Optional[int] = None
    user_role: str = ""
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    subscribed_channels: Set[str] = field(default_factory=set)
    branch_ids: Set[int] = field(default_factory=set)  # Branch-scoped subscriptions

    @property
    def is_alive(self) -> bool:
        """Check if connection is alive (last ping within 90 seconds)."""
        return (time.time() - self.last_ping) < 90.0


# ---------------------------------------------------------------------------
# Connection Manager (Singleton)
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Central registry for all WebSocket connections.

    Thread-safe asyncio-based manager supporting:
    - Company-scoped broadcast (all users in a company)
    - Branch-scoped broadcast (subset of company users)
    - User-targeted delivery (specific user across devices)
    - Channel-based subscription filtering
    """

    _instance: Optional["ConnectionManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "ConnectionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # connection_id -> (WebSocket, ConnectionMeta)
        self._connections: Dict[str, tuple[WebSocket, ConnectionMeta]] = {}

        # user_id -> {connection_ids} (a user may have multiple tabs/devices)
        self._user_index: Dict[int, Set[str]] = defaultdict(set)

        # company_id -> {connection_ids}
        self._company_index: Dict[Optional[int], Set[str]] = defaultdict(set)

        # branch_id -> {connection_ids}
        self._branch_index: Dict[int, Set[str]] = defaultdict(set)

        # channel -> {connection_ids}
        self._channel_index: Dict[str, Set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        company_id: Optional[int] = None,
        user_role: str = "",
    ) -> ConnectionMeta:
        """Register a new WebSocket connection.

        Args:
            websocket: The accepted WebSocket instance.
            user_id: Authenticated user ID.
            company_id: Optional company ID for tenant scoping.
            user_role: User role string for access control.

        Returns:
            ConnectionMeta for the new connection.
        """
        connection_id = f"ws_{uuid.uuid4().hex[:12]}"
        meta = ConnectionMeta(
            connection_id=connection_id,
            user_id=user_id,
            company_id=company_id,
            user_role=user_role,
        )
        self._connections[connection_id] = (websocket, meta)
        self._user_index[user_id].add(connection_id)
        if company_id is not None:
            self._company_index[company_id].add(connection_id)

        logger.info(
            "WebSocket connected: conn=%s user=%s company=%s role=%s (total=%d)",
            connection_id,
            user_id,
            company_id,
            user_role,
            len(self._connections),
        )
        return meta

    async def disconnect(self, connection_id: str) -> None:
        """Unregister a WebSocket connection and clean up all indexes."""
        entry = self._connections.pop(connection_id, None)
        if entry is None:
            return

        _, meta = entry

        # Remove from user index
        if meta.user_id in self._user_index:
            self._user_index[meta.user_id].discard(connection_id)
            if not self._user_index[meta.user_id]:
                del self._user_index[meta.user_id]

        # Remove from company index
        if meta.company_id in self._company_index:
            self._company_index[meta.company_id].discard(connection_id)
            if not self._company_index[meta.company_id]:
                del self._company_index[meta.company_id]

        # Remove from branch index
        for branch_id in list(meta.branch_ids):
            if branch_id in self._branch_index:
                self._branch_index[branch_id].discard(connection_id)
                if not self._branch_index[branch_id]:
                    del self._branch_index[branch_id]

        # Remove from channel index
        for channel in list(meta.subscribed_channels):
            if channel in self._channel_index:
                self._channel_index[channel].discard(connection_id)
                if not self._channel_index[channel]:
                    del self._channel_index[channel]

        logger.info(
            "WebSocket disconnected: conn=%s user=%s (total=%d)",
            connection_id,
            meta.user_id,
            len(self._connections),
        )

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    def subscribe(self, connection_id: str, channel: str, branch_id: Optional[int] = None) -> bool:
        """Subscribe a connection to a channel.

        Args:
            connection_id: The connection ID.
            channel: Channel name (e.g. "notifications", "dashboard").
            branch_id: Optional branch filter.

        Returns:
            True if subscription was successful.
        """
        entry = self._connections.get(connection_id)
        if entry is None:
            return False
        _, meta = entry

        meta.subscribed_channels.add(channel)
        self._channel_index[channel].add(connection_id)

        if branch_id is not None:
            meta.branch_ids.add(branch_id)
            self._branch_index[branch_id].add(connection_id)

        logger.debug(
            "Subscribed conn=%s to channel=%s branch=%s",
            connection_id,
            channel,
            branch_id,
        )
        return True

    def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a channel.

        Args:
            connection_id: The connection ID.
            channel: Channel name to unsubscribe from.

        Returns:
            True if unsubscription was successful.
        """
        entry = self._connections.get(connection_id)
        if entry is None:
            return False
        _, meta = entry

        meta.subscribed_channels.discard(channel)
        if channel in self._channel_index:
            self._channel_index[channel].discard(connection_id)
            if not self._channel_index[channel]:
                del self._channel_index[channel]

        logger.debug("Unsubscribed conn=%s from channel=%s", connection_id, channel)
        return True

    def update_ping(self, connection_id: str) -> None:
        """Update the last-ping timestamp for a connection."""
        entry = self._connections.get(connection_id)
        if entry:
            entry[1].last_ping = time.time()

    # ------------------------------------------------------------------
    # Delivery Methods
    # ------------------------------------------------------------------

    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send a JSON message to a specific connection.

        Args:
            connection_id: Target connection ID.
            message: JSON-serializable dict.

        Returns:
            True if message was sent successfully.
        """
        entry = self._connections.get(connection_id)
        if entry is None:
            return False
        websocket, _ = entry
        try:
            await websocket.send_json(message)
            return True
        except Exception as exc:
            logger.warning("Failed to send to conn=%s: %s", connection_id, exc)
            return False

    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> int:
        """Send a JSON message to all connections of a user.

        Returns:
            Number of successful deliveries.
        """
        sent = 0
        connection_ids = list(self._user_index.get(user_id, set()))
        for conn_id in connection_ids:
            if await self.send_to_connection(conn_id, message):
                sent += 1
        return sent

    async def broadcast_to_company(
        self,
        company_id: int,
        message: Dict[str, Any],
        channel: Optional[str] = None,
        branch_id: Optional[int] = None,
    ) -> int:
        """Broadcast a message to all connections in a company.

        Args:
            company_id: Target company ID.
            message: JSON-serializable dict.
            channel: If set, only deliver to connections subscribed to this channel.
            branch_id: If set, only deliver to connections subscribed to this branch.

        Returns:
            Number of successful deliveries.
        """
        sent = 0
        connection_ids = list(self._company_index.get(company_id, set()))

        for conn_id in connection_ids:
            entry = self._connections.get(conn_id)
            if entry is None:
                continue
            _, meta = entry

            # Channel filter
            if channel and channel not in meta.subscribed_channels:
                continue

            # Branch filter: if branch_id specified, connection must be interested
            if branch_id is not None and branch_id not in meta.branch_ids:
                # But still allow if user hasn't set any branch filter (global subscription)
                if meta.branch_ids:
                    continue

            if await self.send_to_connection(conn_id, message):
                sent += 1

        return sent

    async def broadcast_to_channel(
        self,
        channel: str,
        message: Dict[str, Any],
        company_id: Optional[int] = None,
    ) -> int:
        """Broadcast to all connections subscribed to a channel.

        Args:
            channel: Channel name.
            message: JSON-serializable dict.
            company_id: Optional company filter.

        Returns:
            Number of successful deliveries.
        """
        sent = 0
        connection_ids = list(self._channel_index.get(channel, set()))

        for conn_id in connection_ids:
            entry = self._connections.get(conn_id)
            if entry is None:
                continue
            _, meta = entry

            # Company filter
            if company_id is not None and meta.company_id != company_id:
                continue

            if await self.send_to_connection(conn_id, message):
                sent += 1

        return sent

    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast to ALL connected clients (admin/debug use).

        Returns:
            Number of successful deliveries.
        """
        sent = 0
        connection_ids = list(self._connections.keys())
        for conn_id in connection_ids:
            if await self.send_to_connection(conn_id, message):
                sent += 1
        return sent

    # ------------------------------------------------------------------
    # Health & Monitoring
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return connection statistics for monitoring."""
        return {
            "total_connections": len(self._connections),
            "unique_users": len(self._user_index),
            "companies": {
                str(cid or "none"): len(conns)
                for cid, conns in self._company_index.items()
            },
            "channels": {
                ch: len(conns) for ch, conns in self._channel_index.items()
            },
            "stale_connections": sum(
                1 for _, meta in self._connections.values() if not meta.is_alive
            ),
        }

    async def cleanup_stale(self, max_idle_seconds: float = 90.0) -> int:
        """Remove stale connections that haven't sent a ping recently.

        Returns:
            Number of connections removed.
        """
        now = time.time()
        stale_ids = [
            conn_id
            for conn_id, (_, meta) in self._connections.items()
            if (now - meta.last_ping) > max_idle_seconds
        ]
        for conn_id in stale_ids:
            await self.disconnect(conn_id)
        if stale_ids:
            logger.info("Cleaned up %d stale connections", len(stale_ids))
        return len(stale_ids)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_connection_manager() -> ConnectionManager:
    """Return the singleton ConnectionManager instance."""
    return ConnectionManager()
