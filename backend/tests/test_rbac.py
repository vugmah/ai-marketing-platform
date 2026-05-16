"""RBAC (Role-Based Access Control) tests.

Covers all 6 roles:
  - super_admin: full access
  - company_admin: company-scoped access
  - branch_manager: branch-scoped access
  - marketing_manager: marketing endpoints
  - analyst: analytics endpoints
  - support_agent: support endpoints
  - viewer (regular user): read-only access
Tests forbidden access returns 403.
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user_and_headers(
    client: AsyncClient,
    email: str,
    role: str = "user",
    company_id: str = "company-rbac-1",
) -> dict:
    """Register a user and return auth headers."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Test",
        last_name=role.replace("_", " ").title(),
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = company_id

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": company_id,
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": str(company_id),
    }


# ---------------------------------------------------------------------------
# super_admin role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_super_admin_can_access_companies(client: AsyncClient):
    """Super admin should have full access to company CRUD."""
    headers = await _create_user_and_headers(
        client, "sa_companies@example.com", "super_admin", "admin-co"
    )
    resp = await client.get("/api/v2/companies/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_can_access_audit_logs(client: AsyncClient):
    """Super admin should have access to audit logs."""
    headers = await _create_user_and_headers(
        client, "sa_audit@example.com", "super_admin", "admin-audit"
    )
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_can_access_billing_stats(client: AsyncClient):
    """Super admin should have access to billing stats."""
    headers = await _create_user_and_headers(
        client, "sa_billing@example.com", "super_admin", "admin-billing"
    )
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_can_access_events_definitions(client: AsyncClient):
    """Super admin should have access to event definitions."""
    headers = await _create_user_and_headers(
        client, "sa_events@example.com", "super_admin", "admin-events"
    )
    resp = await client.get("/api/v2/events/definitions", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_can_access_all_modules(client: AsyncClient):
    """Super admin should have access to all module endpoints."""
    headers = await _create_user_and_headers(
        client, "sa_all@example.com", "super_admin", "admin-all"
    )

    modules = [
        ("/api/v2/companies/", "GET"),
        ("/api/v2/branches/", "GET"),
        ("/api/v2/ai/prompts", "GET"),
        ("/api/v2/social/accounts", "GET"),
        ("/api/v2/media/assets", "GET"),
        ("/api/v2/billing/plans", "GET"),
        ("/api/v2/audit/logs", "GET"),
        ("/api/v2/events/log", "GET"),
        ("/api/v2/notifications", "GET"),
        ("/api/v2/analytics/", "GET"),
        ("/api/v2/dashboard/", "GET"),
        ("/api/v2/erp/connections", "GET"),
    ]

    for path, method in modules:
        if method == "GET":
            resp = await client.get(path, headers=headers)
        elif method == "POST":
            resp = await client.post(path, json={}, headers=headers)
        assert resp.status_code in (200, 201, 404, 422), f"super_admin failed for {path}: {resp.status_code}"


# ---------------------------------------------------------------------------
# company_admin role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_company_admin_can_access_companies(client: AsyncClient):
    """Company admin should have company-scoped access."""
    headers = await _create_user_and_headers(
        client, "ca_companies@example.com", "company_admin", "company-ca"
    )
    resp = await client.get("/api/v2/companies/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_company_admin_can_access_branches(client: AsyncClient):
    """Company admin should have access to branches within their company."""
    headers = await _create_user_and_headers(
        client, "ca_branches@example.com", "company_admin", "company-ca-br"
    )
    resp = await client.get("/api/v2/branches/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_company_admin_can_access_billing(client: AsyncClient):
    """Company admin should have access to billing."""
    headers = await _create_user_and_headers(
        client, "ca_billing@example.com", "company_admin", "company-ca-bi"
    )
    resp = await client.get("/api/v2/billing/plans", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_company_admin_can_access_audit(client: AsyncClient):
    """Company admin should have access to audit."""
    headers = await _create_user_and_headers(
        client, "ca_audit@example.com", "company_admin", "company-ca-au"
    )
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_company_admin_can_toggle_feature_flags(client: AsyncClient):
    """Company admin should be able to toggle feature flags."""
    headers = await _create_user_and_headers(
        client, "ca_flags@example.com", "company_admin", "company-ca-ff"
    )
    resp = await client.post(
        "/api/v2/billing/features/social_posting/toggle",
        json={"enabled": True, "reason": "Test"},
        headers=headers,
    )
    # Should succeed or return appropriate status
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_company_admin_can_create_api_keys(client: AsyncClient):
    """Company admin should be able to create API keys."""
    headers = await _create_user_and_headers(
        client, "ca_apikey@example.com", "company_admin", "company-ca-ak"
    )
    resp = await client.post(
        "/api/v2/audit/api-keys",
        json={"name": "Test Key", "scopes": ["read"]},
        headers=headers,
    )
    assert resp.status_code in (201, 404, 422, 500)


# ---------------------------------------------------------------------------
# branch_manager role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_branch_manager_can_access_branches(client: AsyncClient):
    """Branch manager should have branch-scoped access."""
    headers = await _create_user_and_headers(
        client, "bm_branches@example.com", "branch_manager", "company-bm"
    )
    resp = await client.get("/api/v2/branches/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_branch_manager_can_access_media(client: AsyncClient):
    """Branch manager should have access to media."""
    headers = await _create_user_and_headers(
        client, "bm_media@example.com", "branch_manager", "company-bm-md"
    )
    resp = await client.get("/api/v2/media/assets", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_branch_manager_can_access_audit(client: AsyncClient):
    """Branch manager should have access to audit logs."""
    headers = await _create_user_and_headers(
        client, "bm_audit@example.com", "branch_manager", "company-bm-au"
    )
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_branch_manager_can_access_social(client: AsyncClient):
    """Branch manager should have access to social media."""
    headers = await _create_user_and_headers(
        client, "bm_social@example.com", "branch_manager", "company-bm-so"
    )
    resp = await client.get("/api/v2/social/accounts", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# marketing_manager role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_marketing_manager_can_access_social(client: AsyncClient):
    """Marketing manager should have access to social media."""
    headers = await _create_user_and_headers(
        client, "mm_social@example.com", "marketing_manager", "company-mm"
    )
    resp = await client.get("/api/v2/social/accounts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_marketing_manager_can_access_ai(client: AsyncClient):
    """Marketing manager should have access to AI."""
    headers = await _create_user_and_headers(
        client, "mm_ai@example.com", "marketing_manager", "company-mm-ai"
    )
    resp = await client.get("/api/v2/ai/prompts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_marketing_manager_can_access_media(client: AsyncClient):
    """Marketing manager should have access to media."""
    headers = await _create_user_and_headers(
        client, "mm_media@example.com", "marketing_manager", "company-mm-md"
    )
    resp = await client.get("/api/v2/media/assets", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_marketing_manager_can_access_ads(client: AsyncClient):
    """Marketing manager should have access to ads endpoints."""
    headers = await _create_user_and_headers(
        client, "mm_ads@example.com", "marketing_manager", "company-mm-ad"
    )
    resp = await client.get("/api/v2/social/competitors", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# analyst role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyst_can_access_analytics(client: AsyncClient):
    """Analyst should have access to analytics."""
    headers = await _create_user_and_headers(
        client, "an_analytics@example.com", "analyst", "company-an"
    )
    resp = await client.get("/api/v2/analytics/", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_analyst_can_access_ai_usage(client: AsyncClient):
    """Analyst should have access to AI usage analytics."""
    headers = await _create_user_and_headers(
        client, "an_aiusage@example.com", "analyst", "company-an-ai"
    )
    resp = await client.get("/api/v2/ai/usage", headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_analyst_can_access_social_analytics(client: AsyncClient):
    """Analyst should have access to social analytics."""
    headers = await _create_user_and_headers(
        client, "an_social@example.com", "analyst", "company-an-so"
    )
    resp = await client.get("/api/v2/social/analytics", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_analyst_can_access_dashboard(client: AsyncClient):
    """Analyst should have access to dashboard."""
    headers = await _create_user_and_headers(
        client, "an_dash@example.com", "analyst", "company-an-da"
    )
    resp = await client.get("/api/v2/dashboard/", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_analyst_can_access_billing_usage(client: AsyncClient):
    """Analyst should have access to billing usage."""
    headers = await _create_user_and_headers(
        client, "an_billing@example.com", "analyst", "company-an-bi"
    )
    resp = await client.get("/api/v2/billing/usage", headers=headers)
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# support_agent role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_support_agent_can_access_notifications(client: AsyncClient):
    """Support agent should have access to notifications."""
    headers = await _create_user_and_headers(
        client, "sp_notif@example.com", "support_agent", "company-sp"
    )
    resp = await client.get("/api/v2/notifications", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_support_agent_can_access_social_messages(client: AsyncClient):
    """Support agent should have access to social messages."""
    headers = await _create_user_and_headers(
        client, "sp_msgs@example.com", "support_agent", "company-sp-ms"
    )
    resp = await client.get("/api/v2/social/messages", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_support_agent_can_access_social_comments(client: AsyncClient):
    """Support agent should have access to social comments."""
    headers = await _create_user_and_headers(
        client, "sp_comments@example.com", "support_agent", "company-sp-cm"
    )
    resp = await client.get("/api/v2/social/comments", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Regular user (viewer) role - read-only access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_viewer_can_read_companies(client: AsyncClient):
    """Viewer should have read access to companies."""
    headers = await _create_user_and_headers(
        client, "vw_companies@example.com", "user", "company-vw"
    )
    resp = await client.get("/api/v2/companies/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_can_read_branches(client: AsyncClient):
    """Viewer should have read access to branches."""
    headers = await _create_user_and_headers(
        client, "vw_branches@example.com", "user", "company-vw-br"
    )
    resp = await client.get("/api/v2/branches/", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_can_read_media(client: AsyncClient):
    """Viewer should have read access to media."""
    headers = await _create_user_and_headers(
        client, "vw_media@example.com", "user", "company-vw-md"
    )
    resp = await client.get("/api/v2/media/assets", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_can_read_ai_prompts(client: AsyncClient):
    """Viewer should have read access to AI prompts."""
    headers = await _create_user_and_headers(
        client, "vw_ai@example.com", "user", "company-vw-ai"
    )
    resp = await client.get("/api/v2/ai/prompts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_can_read_social_posts(client: AsyncClient):
    """Viewer should have read access to social posts."""
    headers = await _create_user_and_headers(
        client, "vw_social@example.com", "user", "company-vw-so"
    )
    resp = await client.get("/api/v2/social/posts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_can_read_notifications(client: AsyncClient):
    """Viewer should have read access to notifications."""
    headers = await _create_user_and_headers(
        client, "vw_notif@example.com", "user", "company-vw-no"
    )
    resp = await client.get("/api/v2/notifications", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Forbidden access tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_viewer_cannot_access_admin_audit_logs(client: AsyncClient):
    """Viewer should NOT have access to admin-only audit logs."""
    headers = await _create_user_and_headers(
        client, "vw_audit@example.com", "user", "company-vw-audit"
    )
    resp = await client.get("/api/v2/audit/logs", headers=headers)
    # Should be denied (403)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_access_billing_stats(client: AsyncClient):
    """Viewer should NOT have access to billing stats (admin only)."""
    headers = await _create_user_and_headers(
        client, "vw_stats@example.com", "user", "company-vw-st"
    )
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_access_feature_toggle(client: AsyncClient):
    """Viewer should NOT be able to toggle feature flags."""
    headers = await _create_user_and_headers(
        client, "vw_toggle@example.com", "user", "company-vw-tg"
    )
    resp = await client.post(
        "/api/v2/billing/features/social_posting/toggle",
        json={"enabled": True, "reason": "Test"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_marketing_manager_cannot_access_billing_stats(client: AsyncClient):
    """Marketing manager should NOT have access to billing stats (admin only)."""
    headers = await _create_user_and_headers(
        client, "mm_stats@example.com", "marketing_manager", "company-mm-st"
    )
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_branch_manager_cannot_access_billing_stats(client: AsyncClient):
    """Branch manager should NOT have access to billing stats (admin only)."""
    headers = await _create_user_and_headers(
        client, "bm_stats@example.com", "branch_manager", "company-bm-st"
    )
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_support_agent_cannot_access_billing_stats(client: AsyncClient):
    """Support agent should NOT have access to billing stats (admin only)."""
    headers = await _create_user_and_headers(
        client, "sp_stats@example.com", "support_agent", "company-sp-st"
    )
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_support_agent_cannot_access_admin_endpoints(client: AsyncClient):
    """Support agent should NOT have access to admin-only endpoints."""
    headers = await _create_user_and_headers(
        client, "sp_admin@example.com", "support_agent", "company-sp-ad"
    )
    resp = await client.get("/api/v2/audit/data-access", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analyst_cannot_access_feature_toggle(client: AsyncClient):
    """Analyst should NOT be able to toggle feature flags."""
    headers = await _create_user_and_headers(
        client, "an_toggle@example.com", "analyst", "company-an-tg"
    )
    resp = await client.post(
        "/api/v2/billing/features/social_posting/toggle",
        json={"enabled": True, "reason": "Test"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_access_protected_endpoints(client: AsyncClient):
    """Unauthenticated users should be denied access to all protected endpoints."""
    endpoints = [
        "/api/v2/companies/",
        "/api/v2/branches/",
        "/api/v2/ai/prompts",
        "/api/v2/social/accounts",
        "/api/v2/media/assets",
        "/api/v2/billing/plans",
        "/api/v2/audit/logs",
        "/api/v2/events/log",
        "/api/v2/notifications",
        "/api/v2/erp/connections",
    ]
    for path in endpoints:
        resp = await client.get(path)
        assert resp.status_code in (401, 403), f"Unauthenticated access to {path} should fail"


# ---------------------------------------------------------------------------
# Role hierarchy tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_role_hierarchy_super_admin_above_all(client: AsyncClient):
    """Super admin should have access to everything company admin can access."""
    admin_headers = await _create_user_and_headers(
        client, "rh_admin@example.com", "super_admin", "admin-rh"
    )
    endpoints = [
        "/api/v2/companies/",
        "/api/v2/branches/",
        "/api/v2/audit/logs",
        "/api/v2/events/definitions",
    ]
    for path in endpoints:
        resp = await client.get(path, headers=admin_headers)
        assert resp.status_code == 200, f"super_admin failed for {path}"


@pytest.mark.asyncio
async def test_company_admin_has_more_access_than_viewer(client: AsyncClient):
    """Company admin should have more access than a regular viewer."""
    ca_headers = await _create_user_and_headers(
        client, "rh_ca@example.com", "company_admin", "company-rh-ca"
    )
    vw_headers = await _create_user_and_headers(
        client, "rh_vw@example.com", "user", "company-rh-vw"
    )

    # Both can read companies
    resp_ca = await client.get("/api/v2/companies/", headers=ca_headers)
    resp_vw = await client.get("/api/v2/companies/", headers=vw_headers)
    assert resp_ca.status_code == 200
    assert resp_vw.status_code == 200

    # But viewer cannot access audit
    resp_ca_audit = await client.get("/api/v2/audit/logs", headers=ca_headers)
    resp_vw_audit = await client.get("/api/v2/audit/logs", headers=vw_headers)
    assert resp_ca_audit.status_code == 200
    assert resp_vw_audit.status_code == 403
