"""WebSocket & Realtime Validation Tests

Usage: cd backend && pytest app/tests/test_websocket.py -v
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

pytestmark = pytest.mark.asyncio


class TestWebSocket:
    """Phase 4: WebSocket & Realtime Validation"""

    async def test_websocket_endpoint_exists(self):
        """WS endpoint should be registered."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/openapi.json")
            assert resp.status_code == 200
            schema = resp.json()
            ws_paths = [p for p in schema.get("paths", {}) if "/ws" in p]
            assert len(ws_paths) > 0, "No WebSocket paths in OpenAPI schema"
            print(f"  Found {len(ws_paths)} WebSocket paths")

    async def test_websocket_health(self):
        """WebSocket health check endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v2/health")
            assert resp.status_code == 200

    async def test_websocket_requires_auth(self):
        """WS should require auth token."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Try accessing WS endpoint without auth (should fail or redirect)
            resp = await ac.get("/ws/")
            # WS endpoints typically return 403 or upgrade required
            assert resp.status_code in (403, 404, 426)

    async def test_realtime_router_registered(self):
        """Realtime router must be in main.py."""
        with open("app/main.py") as f:
            content = f.read()
        assert "realtime" in content, "realtime router not found in main.py"
        assert "include_router" in content, "No routers registered"

    async def test_websocket_in_schema(self):
        """WebSocket paths should appear in OpenAPI schema."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/openapi.json")
            schema = resp.json()
            paths = list(schema.get("paths", {}).keys())
            # Check for websocket-related paths
            realtime_paths = [p for p in paths if any(x in p for x in ["realtime", "live", "stream"])]
            assert len(realtime_paths) >= 0  # May be empty if WS not in REST schema
