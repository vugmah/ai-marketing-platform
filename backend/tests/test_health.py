"""Health check endpoint tests.

Covers:
  - Basic health check
  - Database health check
  - Redis health check
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Basic health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_basic(client: AsyncClient):
    """Basic health endpoint should return 200 with healthy status."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data
    assert "service" in data


# ---------------------------------------------------------------------------
# Database health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_db(client: AsyncClient):
    """DB health endpoint should return 200 with connected status."""
    resp = await client.get("/api/health/db")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "timestamp" in data
    # When DB is connected, status should be healthy
    if data["status"] == "healthy":
        assert data["database"] == "connected"
        assert "response_time_ms" in data


# ---------------------------------------------------------------------------
# Redis health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_redis(client: AsyncClient):
    """Redis health endpoint should return 200 with connected status."""
    resp = await client.get("/api/health/redis")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "redis" in data
    assert "timestamp" in data
    # When Redis is connected, status should be healthy
    if data["status"] == "healthy":
        assert data["redis"] == "connected"
        assert "response_time_ms" in data
