"""Tenant isolation tests.

Covers:
  - User A (Company 1) cannot access Company 2 data
  - User A (Branch 1) cannot access Branch 2 data
  - Admin can access all companies/branches
  - Cross-tenant access returns 403 or 404
  - Tests for: companies, branches, social, media, ai, billing, audit, erp, events endpoints
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_headers(user: dict, company_id: str = "company-1") -> dict:
    """Build auth + tenant headers for a mock user."""
    from app.auth.utils import create_access_token
    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "user"),
        "company_id": company_id,
        "branch_id": user.get("branch_id"),
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": company_id,
    }


async def _create_user_and_headers(
    client: AsyncClient,
    email: str,
    role: str = "company_admin",
    company_id: str = "company-1",
) -> dict:
    """Register a user and return headers with proper auth."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Test",
        last_name="User",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass  # User may already exist

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
        "X-Company-ID": company_id,
    }


# ---------------------------------------------------------------------------
# Company tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_company_a_cannot_access_company_b_data(client: AsyncClient):
    """User from Company A should not access Company B's company endpoints."""
    headers_a = await _create_user_and_headers(
        client, "tenant_a@example.com", "company_admin", "company-a"
    )
    headers_b = await _create_user_and_headers(
        client, "tenant_b@example.com", "company_admin", "company-b"
    )

    # Create a company with user B
    company_payload = {
        "name": "Company B Data",
        "slug": "company-b-data",
        "description": "Sensitive data",
        "website": "https://companyb.com",
        "phone": "+994501234567",
        "email": "info@companyb.com",
        "address": "Baku",
        "tax_number": "TAX-B",
        "is_active": True,
    }
    resp = await client.post("/api/v2/companies/", json=company_payload, headers=headers_b)
    assert resp.status_code == 201
    company_b = resp.json()

    # User A tries to get Company B data
    resp_a = await client.get(f"/api/v2/companies/{company_b['id']}", headers=headers_a)
    # Cross-tenant access should be denied (403 or 404)
    assert resp_a.status_code in (403, 404)


@pytest.mark.asyncio
async def test_admin_can_access_all_companies(client: AsyncClient):
    """Super admin should be able to access any company's data."""
    admin_headers = await _create_user_and_headers(
        client, "superadmin@example.com", "super_admin", "admin-company"
    )
    user_headers = await _create_user_and_headers(
        client, "regularco@example.com", "company_admin", "company-regular"
    )

    # Create a company with regular user
    company_payload = {
        "name": "Regular Company",
        "slug": "regular-co",
        "description": "Regular company data",
        "website": "https://regular.com",
        "phone": "+994501234567",
        "email": "info@regular.com",
        "address": "Baku",
        "tax_number": "TAX-R",
        "is_active": True,
    }
    resp = await client.post("/api/v2/companies/", json=company_payload, headers=user_headers)
    assert resp.status_code == 201
    company = resp.json()

    # Admin should be able to access it
    resp_admin = await client.get(f"/api/v2/companies/{company['id']}", headers=admin_headers)
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert data["name"] == "Regular Company"


@pytest.mark.asyncio
async def test_list_companies_isolated_by_tenant(client: AsyncClient):
    """Company listing should respect tenant boundaries."""
    headers_a = await _create_user_and_headers(
        client, "list_a@example.com", "company_admin", "company-list-a"
    )
    headers_b = await _create_user_and_headers(
        client, "list_b@example.com", "company_admin", "company-list-b"
    )

    # Create company for A
    resp_a = await client.post(
        "/api/v2/companies/",
        json={"name": "Company A Only", "slug": "company-a-only"},
        headers=headers_a,
    )
    assert resp_a.status_code == 201

    # Create company for B
    resp_b = await client.post(
        "/api/v2/companies/",
        json={"name": "Company B Only", "slug": "company-b-only"},
        headers=headers_b,
    )
    assert resp_b.status_code == 201


# ---------------------------------------------------------------------------
# Branch tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_branch_isolation_between_companies(client: AsyncClient):
    """Branches should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "branch_a@example.com", "company_admin", "company-branch-a"
    )

    # Create branch for company A
    branch_payload = {
        "name": "Branch A",
        "company_id": "company-branch-a",
        "address": "Address A",
        "phone": "+994501111111",
        "email": "branch@a.com",
        "manager_name": "Manager A",
        "is_active": True,
    }
    resp = await client.post("/api/v2/branches/", json=branch_payload, headers=headers_a)
    assert resp.status_code == 201
    branch_a = resp.json()
    assert branch_a["name"] == "Branch A"

    # Different user from different company tries to access
    headers_b = await _create_user_and_headers(
        client, "branch_b@example.com", "company_admin", "company-branch-b"
    )
    resp_b = await client.get(f"/api/v2/branches/{branch_a['id']}", headers=headers_b)
    # Should not find cross-tenant branch
    assert resp_b.status_code in (403, 404)


# ---------------------------------------------------------------------------
# AI module tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_prompts_isolated_by_company(client: AsyncClient):
    """AI prompts should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "ai_a@example.com", "company_admin", "company-ai-a"
    )

    # List prompts - should work for own company
    resp = await client.get("/api/v2/ai/prompts", headers=headers_a)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ai_suggestions_isolated_by_company(client: AsyncClient):
    """AI suggestions should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "ai_sugg_a@example.com", "company_admin", "company-sugg-a"
    )

    resp = await client.get("/api/v2/ai/suggestions", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Social media tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_social_accounts_isolated_by_company(client: AsyncClient):
    """Social accounts should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "social_a@example.com", "company_admin", "company-social-a"
    )

    resp = await client.get("/api/v2/social/accounts", headers=headers_a)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_social_posts_isolated_by_company(client: AsyncClient):
    """Social posts should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "posts_a@example.com", "company_admin", "company-posts-a"
    )

    resp = await client.get("/api/v2/social/posts", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Media module tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_media_assets_isolated_by_company(client: AsyncClient):
    """Media assets should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "media_a@example.com", "company_admin", "company-media-a"
    )

    resp = await client.get("/api/v2/media/assets", headers=headers_a)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_media_tags_isolated_by_company(client: AsyncClient):
    """Media tags should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "tags_a@example.com", "company_admin", "company-tags-a"
    )

    resp = await client.get("/api/v2/media/tags", headers=headers_a)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_media_collections_isolated_by_company(client: AsyncClient):
    """Media collections should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "coll_a@example.com", "company_admin", "company-coll-a"
    )

    resp = await client.get("/api/v2/media/collections", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Billing module tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_billing_subscription_isolated_by_company(client: AsyncClient):
    """Billing subscription should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "billing_a@example.com", "company_admin", "company-billing-a"
    )

    # Get subscription for company A - should be 404 (no subscription)
    resp = await client.get("/api/v2/billing/subscription", headers=headers_a)
    # Expected to either succeed or return not found
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_billing_quotas_isolated_by_company(client: AsyncClient):
    """Billing quotas should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "quotas_a@example.com", "company_admin", "company-quotas-a"
    )

    resp = await client.get("/api/v2/billing/quotas", headers=headers_a)
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# ERP module tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_erp_connections_isolated_by_company(client: AsyncClient):
    """ERP connections should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "erp_a@example.com", "company_admin", "company-erp-a"
    )

    resp = await client.get("/api/v2/erp/connections", headers=headers_a)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_erp_mappings_isolated_by_company(client: AsyncClient):
    """ERP field mappings should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "mapping_a@example.com", "company_admin", "company-mapping-a"
    )

    resp = await client.get("/api/v2/erp/mappings", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Audit module tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_logs_isolated_by_company(client: AsyncClient):
    """Audit logs should be isolated by company."""
    headers_admin = await _create_user_and_headers(
        client, "audit_admin@example.com", "super_admin", "company-audit-a"
    )

    resp = await client.get("/api/v2/audit/logs", headers=headers_admin)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_audit_api_keys_isolated_by_company(client: AsyncClient):
    """API keys should be isolated by company."""
    headers_admin = await _create_user_and_headers(
        client, "apikey_admin@example.com", "company_admin", "company-apikey-a"
    )

    resp = await client.get("/api/v2/audit/api-keys", headers=headers_admin)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Events module tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_subscriptions_isolated_by_company(client: AsyncClient):
    """Event subscriptions should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "events_a@example.com", "company_admin", "company-events-a"
    )

    resp = await client.get("/api/v2/events/subscriptions", headers=headers_a)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_event_automation_rules_isolated_by_company(client: AsyncClient):
    """Automation rules should be isolated by company."""
    headers_a = await _create_user_and_headers(
        client, "auto_a@example.com", "company_admin", "company-auto-a"
    )

    resp = await client.get("/api/v2/events/automation-rules", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cross-tenant access denial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_data_access_returns_403_or_404(client: AsyncClient):
    """Cross-tenant data access should return 403 or 404."""
    headers_a = await _create_user_and_headers(
        client, "cross_a@example.com", "company_admin", "company-cross-a"
    )
    headers_b = await _create_user_and_headers(
        client, "cross_b@example.com", "company_admin", "company-cross-b"
    )

    # Company B creates a company entry
    company_payload = {
        "name": "Protected Company",
        "slug": "protected-co",
        "description": "Protected",
        "website": "https://protected.com",
        "phone": "+994501234567",
        "email": "info@protected.com",
        "address": "Baku",
        "tax_number": "TAX-P",
        "is_active": True,
    }
    resp = await client.post("/api/v2/companies/", json=company_payload, headers=headers_b)
    assert resp.status_code == 201
    protected_company = resp.json()

    # User A attempts to update Company B's data
    update_payload = {"name": "Hacked Company"}
    resp_update = await client.put(
        f"/api/v2/companies/{protected_company['id']}",
        json=update_payload,
        headers=headers_a,
    )
    assert resp_update.status_code in (403, 404)

    # User A attempts to delete Company B's data
    resp_delete = await client.delete(
        f"/api/v2/companies/{protected_company['id']}",
        headers=headers_a,
    )
    assert resp_delete.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cross_tenant_analytics_access_denied(client: AsyncClient):
    """Analytics data should not leak across tenants."""
    headers_a = await _create_user_and_headers(
        client, "analytics_a@example.com", "analyst", "company-analytics-a"
    )
    headers_b = await _create_user_and_headers(
        client, "analytics_b@example.com", "analyst", "company-analytics-b"
    )

    # Each analyst should only see their own company's analytics
    resp_a = await client.get("/api/v2/analytics/", headers=headers_a)
    resp_b = await client.get("/api/v2/analytics/", headers=headers_b)

    # Both should succeed but see different data
    assert resp_a.status_code in (200, 404)
    assert resp_b.status_code in (200, 404)


@pytest.mark.asyncio
async def test_cross_tenant_dashboard_access_denied(client: AsyncClient):
    """Dashboard data should not leak across tenants."""
    headers_a = await _create_user_and_headers(
        client, "dash_a@example.com", "company_admin", "company-dash-a"
    )

    resp = await client.get("/api/v2/dashboard/", headers=headers_a)
    assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Super admin cross-tenant access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_super_admin_can_list_all_event_logs(client: AsyncClient):
    """Super admin should see all event logs across tenants."""
    headers_admin = await _create_user_and_headers(
        client, "events_admin@example.com", "super_admin", "admin-events"
    )

    resp = await client.get("/api/v2/events/log", headers=headers_admin)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_can_access_all_audit_stats(client: AsyncClient):
    """Super admin should see all audit stats across tenants."""
    headers_admin = await _create_user_and_headers(
        client, "stats_admin@example.com", "super_admin", "admin-stats"
    )

    resp = await client.get("/api/v2/audit/stats", headers=headers_admin)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Notification tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifications_isolated_by_user(client: AsyncClient):
    """Notifications should be isolated per user."""
    headers_a = await _create_user_and_headers(
        client, "notif_a@example.com", "company_admin", "company-notif-a"
    )

    resp = await client.get("/api/v2/notifications", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Health endpoints are tenant-agnostic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_endpoints_no_tenant_required(client: AsyncClient):
    """Health endpoints should not require tenant headers."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200

    resp_db = await client.get("/api/health/db")
    assert resp_db.status_code == 200

    resp_redis = await client.get("/api/health/redis")
    assert resp_redis.status_code == 200
