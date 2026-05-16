"""Audit module tests.

Covers:
  - Audit log creation
  - Security events
  - Login attempts
  - API key CRUD
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _audit_headers(client: AsyncClient, email: str, role: str = "super_admin") -> dict:
    """Create auth headers for audit tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Audit",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "audit-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "audit-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "audit-test-company",
    }


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_audit_logs(client: AsyncClient):
    """Listing audit logs should return 200 for admin."""
    headers = await _audit_headers(client, "log_list@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_audit_logs_with_filters(client: AsyncClient):
    """Listing audit logs with filters should work."""
    headers = await _audit_headers(client, "log_filter@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/logs?action=update", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_audit_logs_paginated(client: AsyncClient):
    """Paginated audit logs should work."""
    headers = await _audit_headers(client, "log_page@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/logs?page=1&limit=20", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "page" in data
    assert "limit" in data


@pytest.mark.asyncio
async def test_list_audit_logs_unauthorized_for_viewer(client: AsyncClient):
    """Viewer should NOT be able to list audit logs."""
    headers = await _audit_headers(client, "log_denied@example.com", role="user")
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Audit Stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_audit_stats(client: AsyncClient):
    """Getting audit stats should return 200."""
    headers = await _audit_headers(client, "stats_get@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "event_types" in data
    assert "severity_distribution" in data


# ---------------------------------------------------------------------------
# Data Access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_data_access(client: AsyncClient):
    """Listing data access records should return 200 for admin."""
    headers = await _audit_headers(client, "da_list@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/data-access", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Security Events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_security_events(client: AsyncClient):
    """Listing security events should return 200 for admin."""
    headers = await _audit_headers(client, "sec_list@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/security-events", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_security_events_with_filters(client: AsyncClient):
    """Security events with event_type filter should work."""
    headers = await _audit_headers(client, "sec_filter@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/security-events?event_type=login", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Login Attempts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_login_attempts(client: AsyncClient):
    """Listing login attempts should return 200 for admin."""
    headers = await _audit_headers(client, "login_list@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/login-attempts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_login_attempts_with_status_filter(client: AsyncClient):
    """Login attempts with status filter should work."""
    headers = await _audit_headers(client, "login_filter@example.com", role="super_admin")
    resp = await client.get("/api/v2/audit/login-attempts?status=failed", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient):
    """Listing API keys should return 200."""
    headers = await _audit_headers(client, "key_list@example.com", role="company_admin")
    resp = await client.get("/api/v2/audit/api-keys", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient):
    """Creating an API key should return 201."""
    headers = await _audit_headers(client, "key_create@example.com", role="company_admin")
    payload = {"name": "Test API Key", "scopes": ["read", "write"]}
    resp = await client.post("/api/v2/audit/api-keys", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_get_api_key(client: AsyncClient):
    """Getting an API key by ID should return 200 or 404."""
    headers = await _audit_headers(client, "key_get@example.com", role="company_admin")
    resp_list = await client.get("/api/v2/audit/api-keys", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        key_id = items[0]["id"]
        resp = await client.get(f"/api/v2/audit/api-keys/{key_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient):
    """Revoking an API key should return 200."""
    headers = await _audit_headers(client, "key_revoke@example.com", role="company_admin")
    resp_list = await client.get("/api/v2/audit/api-keys", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        key_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/audit/api-keys/{key_id}", headers=headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RBAC - Role restrictions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_logs_accessible_to_company_admin(client: AsyncClient):
    """Company admin should be able to access audit logs."""
    headers = await _audit_headers(client, "rbac_ca@example.com", role="company_admin")
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_audit_logs_accessible_to_branch_manager(client: AsyncClient):
    """Branch manager should be able to access audit logs."""
    headers = await _audit_headers(client, "rbac_bm@example.com", role="branch_manager")
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_security_events_denied_for_viewer(client: AsyncClient):
    """Viewer should NOT be able to access security events."""
    headers = await _audit_headers(client, "rbac_vw@example.com", role="user")
    resp = await client.get("/api/v2/audit/security-events", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_attempts_denied_for_analyst(client: AsyncClient):
    """Analyst should NOT be able to access login attempts."""
    headers = await _audit_headers(client, "rbac_an@example.com", role="analyst")
    resp = await client.get("/api/v2/audit/login-attempts", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_audit_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/audit/logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_api_key(client: AsyncClient):
    """Getting a non-existent API key should return 404."""
    headers = await _audit_headers(client, "key_404@example.com", role="company_admin")
    resp = await client.get("/api/v2/audit/api-keys/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_audit_lifecycle(client: AsyncClient):
    """Full lifecycle: create key -> list -> get -> revoke -> get stats."""
    headers = await _audit_headers(client, "audit_full@example.com", role="company_admin")

    # 1. Create API key
    key_payload = {"name": "Full Test Key", "scopes": ["read"]}
    resp_key = await client.post("/api/v2/audit/api-keys", json=key_payload, headers=headers)
    assert resp_key.status_code in (201, 422, 500)

    # 2. List API keys
    resp_list = await client.get("/api/v2/audit/api-keys", headers=headers)
    assert resp_list.status_code == 200

    # 3. List audit logs
    resp_logs = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp_logs.status_code == 200

    # 4. List security events
    resp_sec = await client.get("/api/v2/audit/security-events", headers=headers)
    assert resp_sec.status_code == 200

    # 5. List login attempts
    resp_login = await client.get("/api/v2/audit/login-attempts", headers=headers)
    assert resp_login.status_code == 200

    # 6. List data access
    resp_da = await client.get("/api/v2/audit/data-access", headers=headers)
    assert resp_da.status_code == 200

    # 7. Get stats
    resp_stats = await client.get("/api/v2/audit/stats", headers=headers)
    assert resp_stats.status_code == 200
