"""Realtime WebSocket infrastructure module.

Provides:
- WebSocket gateway with JWT auth and company/branch subscription
- ConnectionManager for managing active WebSocket connections
- Redis pub/sub → WebSocket bridge for live event streaming
- Realtime notifications, dashboard KPI updates, support inbox, and alerts
"""

from app.realtime.gateway import websocket_endpoint
from app.realtime.manager import ConnectionManager, get_connection_manager
from app.realtime.publisher import RedisPubSubBridge
from app.realtime.router import router as realtime_router

__all__ = [
    "ConnectionManager",
    "get_connection_manager",
    "RedisPubSubBridge",
    "realtime_router",
    "websocket_endpoint",
]
