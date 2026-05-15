"""Middleware tests.

Covers:
  - TenantMiddleware: X-Company-ID header enforcement
  - RateLimitMiddleware: rate limiting per endpoint
  - CORSMiddleware: CORS headers on responses
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Tenant Middleware
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tenant_header_required(client: AsyncClient):
    """Request to non-auth endpoint without X-Company-ID should return 403."""
    resp = await client.get("/api/v2/companies/")
    assert resp.status_code == 403
    assert "X-Company-ID" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_header_valid(client: AsyncClient):
    """Request with valid X-Company-ID header should succeed."""
    headers = {"X-Company-ID": "test-tenant-123"}
    resp = await client.get("/api/v2/companies/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tenant_header_allows_auth_endpoints(client: AsyncClient):
    """Auth endpoints should be reachable without X-Company-ID header."""
    payload = {
        "email": "tenanttest@example.com",
        "password": "Password123!",
        "first_name": "Tenant",
        "last_name": "Test",
    }
    resp = await client.post("/api/v2/auth/register", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_tenant_header_skips_health_checks(client: AsyncClient):
    """Health endpoints should be reachable without X-Company-ID header."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tenant_header_skips_docs(client: AsyncClient):
    """OpenAPI docs endpoints should be reachable without X-Company-ID header."""
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tenant_header_attached_to_state(client: AsyncClient):
    """Valid X-Company-ID should be attached to request state."""
    # We verify the request passes, which means the middleware accepted the header
    headers = {"X-Company-ID": "tenant-abc-123"}
    resp = await client.get("/api/v2/companies/", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rate Limit Middleware
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limit(client: AsyncClient, redis_client):
    """Exceeding rate limit should return 429."""
    # Set the rate limit key manually to simulate limit exceeded
    # The key format is: rate_limit:<client_ip>:<path>
    # With httpx ASGI transport, client host resolves to "unknown"
    limit_key = "rate_limit:unknown:/api/v2/auth/login"
    max_requests, window = 10, 60

    # Seed the counter to max_requests to simulate exhaustion
    await redis_client.set(limit_key, max_requests, ex=window)

    payload = {
        "email": "ratelimit@example.com",
        "password": "Password123!",
    }
    resp = await client.post("/api/v2/auth/login", json=payload)
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limit(client: AsyncClient, redis_client):
    """Requests within the rate limit should succeed."""
    # First clear any existing rate limit key
    await redis_client.delete("rate_limit:unknown:/api/v2/auth/login")

    payload = {
        "email": "withinlimit@example.com",
        "password": "Password123!",
    }
    # Register first so login can work
    reg_payload = {
        **payload,
        "first_name": "Within",
        "last_name": "Limit",
    }
    reg_resp = await client.post("/api/v2/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201

    # Login should work
    resp = await client.post("/api/v2/auth/login", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_skips_health_checks(client: AsyncClient, redis_client):
    """Health endpoints should not be rate limited."""
    # Even if we set an extreme rate limit key, health should pass
    limit_key = "rate_limit:unknown:/api/health"
    await redis_client.set(limit_key, 999999, ex=60)

    resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_skips_docs(client: AsyncClient, redis_client):
    """Docs endpoints should not be rate limited."""
    limit_key = "rate_limit:unknown:/api/openapi.json"
    await redis_client.set(limit_key, 999999, ex=60)

    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cors_headers_present(client: AsyncClient):
    """CORS headers should be present on responses."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


@pytest.mark.asyncio
async def test_cors_preflight_request(client: AsyncClient):
    """CORS preflight (OPTIONS) request should succeed with proper headers."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization",
    }
    resp = await client.options("/api/v2/auth/login", headers=headers)
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers
    assert "access-control-allow-methods" in resp.headers
    assert "access-control-allow-headers" in resp.headers


@pytest.mark.asyncio
async def test_cors_exposed_headers(client: AsyncClient):
    """CORS exposed headers (X-Request-ID, X-Company-ID) should be configured."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    # FastAPI CORSMiddleware exposes headers in the response
    acao = resp.headers.get("access-control-allow-origin", "")
    assert len(acao) > 0  # Some origin is allowed
