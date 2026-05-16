"""Tests for the realtime WebSocket infrastructure.

Covers:
- ConnectionManager singleton and connection lifecycle
- Subscription management
- Broadcasting and targeted delivery
- Message envelope formatting
- RedisPubSubBridge channel routing
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.realtime.manager import ConnectionManager, get_connection_manager
from app.realtime.publisher import CHANNEL_MAP, RedisPubSubBridge
from app.realtime.schemas import (
    SubscriptionChannel,
    WSOutboundType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager():
    """Return a fresh ConnectionManager instance (reset singleton)."""
    ConnectionManager._instance = None
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Return a mock WebSocket."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# ConnectionManager Tests
# ---------------------------------------------------------------------------


class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager."""

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self, manager, mock_websocket):
        """Connecting a WebSocket should register it."""
        meta = await manager.connect(
            websocket=mock_websocket,
            user_id=42,
            company_id=5,
            user_role="company_admin",
        )
        assert meta.user_id == 42
        assert meta.company_id == 5
        assert meta.user_role == "company_admin"
        assert meta.connection_id is not None
        assert len(manager._connections) == 1

    @pytest.mark.asyncio
    async def test_connect_without_company(self, manager, mock_websocket):
        """Connecting without a company_id should work."""
        meta = await manager.connect(
            websocket=mock_websocket,
            user_id=1,
            company_id=None,
            user_role="super_admin",
        )
        assert meta.company_id is None
        assert len(manager._connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager, mock_websocket):
        """Disconnecting should clean up all indexes."""
        meta = await manager.connect(
            websocket=mock_websocket,
            user_id=42,
            company_id=5,
        )
        await manager.disconnect(meta.connection_id)
        assert len(manager._connections) == 0
        assert len(manager._user_index) == 0
        assert len(manager._company_index) == 0

    @pytest.mark.asyncio
    async def test_multiple_connections_same_user(self, manager, mock_websocket):
        """A user can have multiple connections (different tabs/devices)."""
        ws2 = AsyncMock()
        meta1 = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        meta2 = await manager.connect(
            websocket=ws2, user_id=42, company_id=5
        )
        assert meta1.connection_id != meta2.connection_id
        assert len(manager._user_index[42]) == 2

    @pytest.mark.asyncio
    async def test_subscribe(self, manager, mock_websocket):
        """Subscribing to a channel should work."""
        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        success = manager.subscribe(
            meta.connection_id, "notifications", branch_id=2
        )
        assert success is True
        assert "notifications" in meta.subscribed_channels
        assert 2 in meta.branch_ids

    @pytest.mark.asyncio
    async def test_subscribe_unknown_connection(self, manager):
        """Subscribing to a non-existent connection should fail."""
        success = manager.subscribe("nonexistent", "notifications")
        assert success is False

    @pytest.mark.asyncio
    async def test_unsubscribe(self, manager, mock_websocket):
        """Unsubscribing should remove from channel index."""
        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        manager.subscribe(meta.connection_id, "dashboard")
        manager.unsubscribe(meta.connection_id, "dashboard")
        assert "dashboard" not in meta.subscribed_channels

    @pytest.mark.asyncio
    async def test_send_to_connection(self, manager, mock_websocket):
        """Sending to a specific connection should call send_json."""
        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        message = {"test": "data"}
        success = await manager.send_to_connection(
            meta.connection_id, message
        )
        assert success is True
        mock_websocket.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_send_to_user(self, manager, mock_websocket):
        """Sending to a user should deliver to all their connections."""
        ws2 = AsyncMock()
        await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        await manager.connect(
            websocket=ws2, user_id=42, company_id=5
        )
        sent = await manager.send_to_user(42, {"type": "test"})
        assert sent == 2

    @pytest.mark.asyncio
    async def test_broadcast_to_company(self, manager, mock_websocket):
        """Broadcasting to a company should reach its connections."""
        ws_other = AsyncMock()
        await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        await manager.connect(
            websocket=ws_other, user_id=43, company_id=5
        )
        # Subscribe both to dashboard
        conn_ids = list(manager._connections.keys())
        for cid in conn_ids:
            manager.subscribe(cid, "dashboard")

        sent = await manager.broadcast_to_company(
            company_id=5, message={"kpi": "update"}, channel="dashboard"
        )
        assert sent == 2

    @pytest.mark.asyncio
    async def test_broadcast_to_company_with_branch_filter(self, manager, mock_websocket):
        """Branch filter should only deliver to matching connections."""
        ws2 = AsyncMock()
        meta1 = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        await manager.connect(
            websocket=ws2, user_id=43, company_id=5
        )
        # Subscribe with branch filter
        manager.subscribe(meta1.connection_id, "dashboard", branch_id=2)
        conn_ids = list(manager._connections.keys())
        for cid in conn_ids:
            if cid != meta1.connection_id:
                manager.subscribe(cid, "dashboard", branch_id=3)

        sent = await manager.broadcast_to_company(
            company_id=5, message={"kpi": "update"}, channel="dashboard", branch_id=2
        )
        assert sent == 1

    @pytest.mark.asyncio
    async def test_broadcast(self, manager, mock_websocket):
        """Broadcast to all should reach every connection."""
        ws2 = AsyncMock()
        await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        await manager.connect(
            websocket=ws2, user_id=43, company_id=6
        )
        sent = await manager.broadcast({"type": "broadcast"})
        assert sent == 2

    def test_get_stats_empty(self, manager):
        """Stats for empty manager should be zero."""
        stats = manager.get_stats()
        assert stats["total_connections"] == 0
        assert stats["unique_users"] == 0
        assert stats["stale_connections"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale(self, manager, mock_websocket):
        """Cleanup should remove stale connections."""
        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        # Manually set last ping to the past
        meta.last_ping = 0  # Very old
        removed = await manager.cleanup_stale(max_idle_seconds=1)
        assert removed == 1
        assert len(manager._connections) == 0

    @pytest.mark.asyncio
    async def test_update_ping(self, manager, mock_websocket):
        """Updating ping should refresh the timestamp."""
        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        old_ping = meta.last_ping
        manager.update_ping(meta.connection_id)
        assert meta.last_ping > old_ping


# ---------------------------------------------------------------------------
# RedisPubSubBridge Tests
# ---------------------------------------------------------------------------


class TestRedisPubSubBridge:
    """Tests for Redis pub/sub bridge routing."""

    def test_channel_map_completeness(self):
        """All mapped channels should have required keys."""
        for channel, mapping in CHANNEL_MAP.items():
            assert "msg_type" in mapping
            assert "ws_channel" in mapping
            assert channel.startswith("realtime:")

    @pytest.mark.asyncio
    async def test_singleton(self):
        """Bridge should be a singleton."""
        bridge1 = RedisPubSubBridge()
        bridge2 = RedisPubSubBridge()
        assert bridge1 is bridge2


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


class TestSchemas:
    """Tests for Pydantic schema validation."""

    def test_subscribe_message(self):
        """Subscribe message should validate correctly."""
        from app.realtime.schemas import SubscribeMessage
        msg = SubscribeMessage(channel="notifications", branch_id=1)
        assert msg.channel == SubscriptionChannel.NOTIFICATIONS
        assert msg.branch_id == 1

    def test_ping_message(self):
        """Ping message should validate correctly."""
        from app.realtime.schemas import PingMessage
        msg = PingMessage(timestamp=1716000000.0)
        assert msg.type == WSMessageType.PING
        assert msg.timestamp == 1716000000.0

    def test_notification_payload(self):
        """Notification payload should serialize correctly."""
        from app.realtime.schemas import NotificationPayload
        notif = NotificationPayload(
            id="notif_123",
            type="info",
            title="Test",
            message="Hello",
            created_at="2024-01-01T00:00:00Z",
        )
        assert notif.is_read is False
        assert notif.title == "Test"

    def test_dashboard_kpi_payload(self):
        """Dashboard KPI payload should handle change calculation."""
        from app.realtime.schemas import DashboardKPIPayload
        kpi = DashboardKPIPayload(
            metric_name="revenue",
            metric_value=15000.0,
            previous_value=12000.0,
            timestamp="2024-01-01T00:00:00Z",
        )
        assert kpi.metric_name == "revenue"
        assert kpi.change_percent == 25.0

    def test_alert_payload(self):
        """Alert payload should include severity."""
        from app.realtime.schemas import AlertPayload
        alert = AlertPayload(
            alert_id="alert_001",
            severity="critical",
            alert_type="threshold_exceeded",
            title="Test Alert",
            message="Something happened",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert alert.severity == "critical"


# ---------------------------------------------------------------------------
# Gateway Integration Tests (mock WebSocket)
# ---------------------------------------------------------------------------


class TestWebSocketGateway:
    """Integration-style tests for the WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_authentication_failure(self):
        """Missing token should close connection with 4001."""
        from app.realtime.gateway import _authenticate_websocket

        ws = AsyncMock()
        ws.query_string = b""
        ws.scope = {"subprotocols": []}

        with pytest.raises(ValueError, match="No authentication token"):
            await _authenticate_websocket(ws)

    @pytest.mark.asyncio
    async def test_authentication_with_query_token(self):
        """Token in query string should be validated."""
        import jwt as pyjwt
        from app.config import settings
        from app.realtime.gateway import _authenticate_websocket

        token = pyjwt.encode(
            {"sub": "42", "company_id": 5, "role": "company_admin"},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        ws = AsyncMock()
        ws.query_string = f"token={token}".encode()
        ws.scope = {"subprotocols": []}

        with patch("app.realtime.gateway.get_redis_client") as mock_redis:
            mock_redis.return_value = AsyncMock()
            mock_redis.return_value.get = AsyncMock(return_value=None)
            result = await _authenticate_websocket(ws)
            assert result["user_id"] == 42
            assert result["company_id"] == 5

    def test_message_handler_registry(self):
        """All expected message types should have handlers."""
        from app.realtime.gateway import _INBOUND_HANDLERS
        assert "subscribe" in _INBOUND_HANDLERS
        assert "unsubscribe" in _INBOUND_HANDLERS
        assert "ping" in _INBOUND_HANDLERS
        assert "ack" in _INBOUND_HANDLERS

    @pytest.mark.asyncio
    async def test_handle_subscribe(self, manager, mock_websocket):
        """Subscribe handler should confirm subscription."""
        from app.realtime.gateway import _handle_subscribe

        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        response = await _handle_subscribe(
            meta.connection_id,
            {"channel": "notifications", "branch_id": 1},
            manager,
        )
        assert response["msg_type"] == "subscribed"
        assert response["payload"]["channel"] == "notifications"

    @pytest.mark.asyncio
    async def test_handle_ping(self, manager, mock_websocket):
        """Ping handler should return a pong."""
        from app.realtime.gateway import _handle_ping

        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        response = await _handle_ping(
            meta.connection_id,
            {"timestamp": 1716000000.0},
            manager,
        )
        assert response["msg_type"] == "pong"
        assert response["payload"]["client_time"] == 1716000000.0

    @pytest.mark.asyncio
    async def test_handle_unsubscribe(self, manager, mock_websocket):
        """Unsubscribe handler should confirm unsubscription."""
        from app.realtime.gateway import _handle_unsubscribe

        meta = await manager.connect(
            websocket=mock_websocket, user_id=42, company_id=5
        )
        manager.subscribe(meta.connection_id, "dashboard")
        response = await _handle_unsubscribe(
            meta.connection_id,
            {"channel": "dashboard"},
            manager,
        )
        assert response["msg_type"] == "unsubscribed"
        assert "dashboard" not in manager._connections[meta.connection_id][1].subscribed_channels


# ---------------------------------------------------------------------------
# Push Service Tests
# ---------------------------------------------------------------------------


class TestNotificationPush:
    """Tests for notification push service."""

    @pytest.mark.asyncio
    async def test_push_notification(self):
        """Pushing a notification should publish to Redis."""
        from app.realtime.notifications import push_notification

        with patch("app.realtime.notifications.get_redis_client") as mock_redis:
            redis = AsyncMock()
            redis.lpush = AsyncMock()
            redis.ltrim = AsyncMock()
            redis.publish = AsyncMock()
            mock_redis.return_value = redis

            notif_id = await push_notification(
                user_id=42,
                company_id=5,
                title="Test",
                message="Hello",
                notif_type="info",
            )
            assert notif_id is not None
            redis.publish.assert_awaited()


class TestDashboardPush:
    """Tests for dashboard push service."""

    @pytest.mark.asyncio
    async def test_push_kpi_update(self):
        """Pushing a KPI update should publish to Redis."""
        from app.realtime.dashboard import push_kpi_update

        with patch("app.realtime.dashboard.get_redis_client") as mock_redis:
            redis = AsyncMock()
            redis.publish = AsyncMock()
            mock_redis.return_value = redis

            await push_kpi_update(
                company_id=5,
                metric_name="revenue",
                metric_value=15000.0,
                previous_value=12000.0,
            )
            redis.publish.assert_awaited()


class TestSupportPush:
    """Tests for support inbox push service."""

    @pytest.mark.asyncio
    async def test_push_new_message(self):
        """Pushing a support message should publish to Redis."""
        from app.realtime.support_inbox import push_new_message

        with patch("app.realtime.support_inbox.get_redis_client") as mock_redis:
            redis = AsyncMock()
            redis.publish = AsyncMock()
            mock_redis.return_value = redis

            msg_id = await push_new_message(
                company_id=5,
                ticket_id="TICK-42",
                sender_type="agent",
                sender_name="Ali",
                content="Merhaba, size nasil yardimci olabilirim?",
            )
            assert msg_id is not None
            redis.publish.assert_awaited()


class TestAlertPush:
    """Tests for alert push service."""

    @pytest.mark.asyncio
    async def test_push_threshold_alert(self):
        """Pushing a threshold alert should calculate severity."""
        from app.realtime.alerts import push_threshold_alert

        with patch("app.realtime.alerts.get_redis_client") as mock_redis:
            redis = AsyncMock()
            redis.lpush = AsyncMock()
            redis.ltrim = AsyncMock()
            redis.publish = AsyncMock()
            mock_redis.return_value = redis

            alert_id = await push_threshold_alert(
                company_id=5,
                metric_name="revenue",
                current_value=15000.0,
                threshold_value=10000.0,
                operator="above",
            )
            assert alert_id is not None
            redis.publish.assert_awaited()

    @pytest.mark.asyncio
    async def test_push_inventory_alert(self):
        """Pushing an inventory alert should handle zero stock."""
        from app.realtime.alerts import push_inventory_alert

        with patch("app.realtime.alerts.get_redis_client") as mock_redis:
            redis = AsyncMock()
            redis.lpush = AsyncMock()
            redis.ltrim = AsyncMock()
            redis.publish = AsyncMock()
            mock_redis.return_value = redis

            alert_id = await push_inventory_alert(
                company_id=5,
                product_name="Kahve",
                current_stock=0,
                threshold=10,
            )
            assert alert_id is not None
            redis.publish.assert_awaited()
