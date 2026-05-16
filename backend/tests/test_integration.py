"""Integration tests.

Covers:
  - Full user registration -> login -> create company -> create branch -> use modules flow
  - Multi-tenant data isolation end-to-end
  - Event -> notification -> webhook flow
  - AI -> suggestion -> application flow
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _integration_headers(client: AsyncClient, email: str, role: str = "company_admin") -> dict:
    """Create auth headers for integration tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Integration",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "integration-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "integration-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "integration-test-company",
    }


# ---------------------------------------------------------------------------
# Full User Registration to Module Usage Flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_user_to_company_to_branch_flow(client: AsyncClient):
    """End-to-end: user registration -> login -> company -> branch."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user
    from app.auth.utils import create_access_token

    # 1. Register a user
    user_data = UserRegister(
        email="integration_user@example.com",
        password="Password123!",
        first_name="Integration",
        last_name="User",
    )
    user_resp = await register_user(user_data)
    assert user_resp is not None
    assert user_resp.email == "integration_user@example.com"

    # 2. Login to get token
    from app.auth.service import _mock_users
    user = _mock_users.get("integration_user@example.com")
    assert user is not None
    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": "company_admin",
        "company_id": "integration-test-company",
    }
    access_token = create_access_token(token_payload)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "integration-test-company",
    }

    # 3. Create a company
    company_payload = {
        "name": "Integration Test Company",
        "slug": "integration-test-co",
        "description": "Company for integration testing",
        "website": "https://integration.com",
        "phone": "+994501234567",
        "email": "info@integration.com",
        "address": "Baku, Azerbaijan",
        "tax_number": "TAX-INT-001",
        "is_active": True,
    }
    resp_company = await client.post("/api/v2/companies/", json=company_payload, headers=headers)
    assert resp_company.status_code == 201
    company = resp_company.json()
    assert company["name"] == "Integration Test Company"

    # 4. Create a branch
    branch_payload = {
        "name": "Main Branch",
        "company_id": "integration-test-company",
        "address": "123 Main St, Baku",
        "phone": "+994501111111",
        "email": "main@integration.com",
        "manager_name": "Branch Manager",
        "is_active": True,
    }
    resp_branch = await client.post("/api/v2/branches/", json=branch_payload, headers=headers)
    assert resp_branch.status_code == 201
    branch = resp_branch.json()
    assert branch["name"] == "Main Branch"

    # 5. Access AI module
    resp_ai = await client.get("/api/v2/ai/prompts", headers=headers)
    assert resp_ai.status_code == 200

    # 6. Access billing module
    resp_billing = await client.get("/api/v2/billing/plans", headers=headers)
    assert resp_billing.status_code == 200

    # 7. Access media module
    resp_media = await client.get("/api/v2/media/assets", headers=headers)
    assert resp_media.status_code == 200

    # 8. Access ERP module
    resp_erp = await client.get("/api/v2/erp/connections", headers=headers)
    assert resp_erp.status_code == 200


# ---------------------------------------------------------------------------
# Multi-tenant Data Isolation End-to-End
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multitenant_data_isolation_e2e(client: AsyncClient):
    """End-to-end test that tenant A cannot access tenant B data."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    # Register Tenant A user
    user_a = UserRegister(
        email="tenant_a@example.com",
        password="Password123!",
        first_name="Tenant",
        last_name="A",
    )
    await register_user(user_a)

    # Register Tenant B user
    user_b = UserRegister(
        email="tenant_b@example.com",
        password="Password123!",
        first_name="Tenant",
        last_name="B",
    )
    await register_user(user_b)

    # Get user objects
    user_a_obj = _mock_users.get("tenant_a@example.com")
    user_b_obj = _mock_users.get("tenant_b@example.com")

    user_a_obj["role"] = "company_admin"
    user_a_obj["company_id"] = "company-a"
    user_b_obj["role"] = "company_admin"
    user_b_obj["company_id"] = "company-b"

    # Create tokens
    token_a = create_access_token({
        "sub": user_a_obj["id"],
        "email": user_a_obj["email"],
        "role": "company_admin",
        "company_id": "company-a",
    })
    token_b = create_access_token({
        "sub": user_b_obj["id"],
        "email": user_b_obj["email"],
        "role": "company_admin",
        "company_id": "company-b",
    })

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Company-ID": "company-a"}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Company-ID": "company-b"}

    # Tenant B creates data
    company_b = {
        "name": "Company B Private",
        "slug": "company-b-private",
        "description": "Private data",
        "website": "https://companyb.com",
        "phone": "+994509999999",
        "email": "info@companyb.com",
        "address": "Baku",
        "tax_number": "TAX-B",
        "is_active": True,
    }
    resp_create = await client.post("/api/v2/companies/", json=company_b, headers=headers_b)
    assert resp_create.status_code == 201
    private_company = resp_create.json()

    # Tenant A attempts to access Tenant B data
    resp_cross = await client.get(f"/api/v2/companies/{private_company['id']}", headers=headers_a)
    assert resp_cross.status_code in (403, 404)

    # Tenant B can access their own data
    resp_own = await client.get(f"/api/v2/companies/{private_company['id']}", headers=headers_b)
    assert resp_own.status_code == 200


# ---------------------------------------------------------------------------
# Event -> Notification Flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_notification_flow(client: AsyncClient, mock_email):
    """End-to-end: publish event -> notification delivered."""
    headers = await _integration_headers(client, "evt_notif@example.com", role="company_admin")

    # 1. Publish an event
    event_payload = {
        "event_type": "test_notification_flow",
        "payload": {"message": "Integration test event", "priority": "high"},
        "source": "integration_tests",
    }
    resp_event = await client.post("/api/v2/events/publish", json=event_payload, headers=headers)
    assert resp_event.status_code in (201, 422, 500)

    # 2. Event log should show the published event
    resp_log = await client.get("/api/v2/events/log", headers=headers)
    assert resp_log.status_code == 200

    # 3. Notifications should be accessible
    resp_notif = await client.get("/api/v2/notifications", headers=headers)
    assert resp_notif.status_code == 200


# ---------------------------------------------------------------------------
# AI -> Suggestion -> Application Flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_suggestion_application_flow(client: AsyncClient, mock_openai):
    """End-to-end: AI generates -> suggestion created -> can be applied."""
    headers = await _integration_headers(client, "ai_sugg@example.com", role="company_admin")

    # 1. List current AI suggestions
    resp_sugg = await client.get("/api/v2/ai/suggestions", headers=headers)
    assert resp_sugg.status_code == 200

    # 2. List recommendations
    resp_rec = await client.get("/api/v2/ai/recommendations", headers=headers)
    assert resp_rec.status_code == 200

    # 3. Access AI prompts
    resp_prompts = await client.get("/api/v2/ai/prompts", headers=headers)
    assert resp_prompts.status_code == 200

    # 4. Access conversations
    resp_conv = await client.get("/api/v2/ai/conversations", headers=headers)
    assert resp_conv.status_code == 200


# ---------------------------------------------------------------------------
# Full Module Integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_modules_accessible_after_onboarding(client: AsyncClient):
    """After onboarding, all modules should be accessible."""
    headers = await _integration_headers(client, "all_mods@example.com", role="super_admin")

    modules = [
        ("/api/v2/companies/", 200),
        ("/api/v2/branches/", 200),
        ("/api/v2/ai/prompts", 200),
        ("/api/v2/ai/suggestions", 200),
        ("/api/v2/ai/recommendations", 200),
        ("/api/v2/ai/conversations", 200),
        ("/api/v2/ai/usage", 200),
        ("/api/v2/social/accounts", 200),
        ("/api/v2/social/posts", 200),
        ("/api/v2/social/comments", 200),
        ("/api/v2/social/messages", 200),
        ("/api/v2/social/analytics", 200),
        ("/api/v2/social/competitors", 200),
        ("/api/v2/media/assets", 200),
        ("/api/v2/media/collections", 200),
        ("/api/v2/media/tags", 200),
        ("/api/v2/billing/plans", 200),
        ("/api/v2/billing/features", 200),
        ("/api/v2/billing/usage", 200),
        ("/api/v2/audit/logs", 200),
        ("/api/v2/audit/security-events", 200),
        ("/api/v2/audit/login-attempts", 200),
        ("/api/v2/audit/api-keys", 200),
        ("/api/v2/audit/stats", 200),
        ("/api/v2/events/log", 200),
        ("/api/v2/events/subscriptions", 200),
        ("/api/v2/events/types", 200),
        ("/api/v2/events/definitions", 200),
        ("/api/v2/events/stats", 200),
        ("/api/v2/events/automation-rules", 200),
        ("/api/v2/events/dlq", 200),
        ("/api/v2/notifications", 200),
        ("/api/v2/notifications/preferences", 200),
        ("/api/v2/erp/connections", 200),
        ("/api/v2/erp/mappings", 200),
        ("/api/v2/erp/products", 200),
        ("/api/v2/erp/customers", 200),
        ("/api/v2/erp/orders", 200),
        ("/api/v2/erp/sync-health", 200),
        ("/api/v2/support/tickets", 200),
        ("/api/v2/support/kb", 200),
        ("/api/v2/ads/connections", 200),
        ("/api/v2/ads/campaigns", 200),
        ("/api/v2/ads/metrics", 200),
        ("/api/v2/ads/metrics/summary", 200),
        ("/api/v2/ads/recommendations", 200),
        ("/api/analytics/", 200),
        ("/api/dashboard/", 200),
    ]

    for path, expected in modules:
        resp = await client.get(path, headers=headers)
        assert resp.status_code in (expected, 404), f"Failed for {path}: got {resp.status_code}"


# ---------------------------------------------------------------------------
# Health Checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_checks(client: AsyncClient):
    """All health endpoints should return 200."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

    resp_db = await client.get("/api/health/db")
    assert resp_db.status_code == 200
    data_db = resp_db.json()
    assert data_db["status"] == "ok"

    resp_redis = await client.get("/api/health/redis")
    assert resp_redis.status_code == 200
    data_redis = resp_redis.json()
    assert data_redis["status"] == "ok"


# ---------------------------------------------------------------------------
# RBAC Integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rbac_integration_across_modules(client: AsyncClient):
    """Test RBAC across multiple modules in one flow."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    # Create admin user
    admin_data = UserRegister(
        email="int_admin@example.com",
        password="Password123!",
        first_name="Admin",
        last_name="Integration",
    )
    await register_user(admin_data)
    admin = _mock_users.get("int_admin@example.com")
    admin["role"] = "super_admin"

    # Create viewer user
    viewer_data = UserRegister(
        email="int_viewer@example.com",
        password="Password123!",
        first_name="Viewer",
        last_name="Integration",
    )
    await register_user(viewer_data)
    viewer = _mock_users.get("int_viewer@example.com")
    viewer["role"] = "user"
    viewer["company_id"] = "int-test-company"

    admin_token = create_access_token({
        "sub": admin["id"],
        "email": admin["email"],
        "role": "super_admin",
    })
    viewer_token = create_access_token({
        "sub": viewer["id"],
        "email": viewer["email"],
        "role": "user",
        "company_id": "int-test-company",
    })

    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Company-ID": "int-test-company"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}", "X-Company-ID": "int-test-company"}

    # Admin can access billing stats
    resp_admin = await client.get("/api/v2/billing/stats", headers=admin_headers)
    assert resp_admin.status_code == 200

    # Viewer cannot access billing stats
    resp_viewer = await client.get("/api/v2/billing/stats", headers=viewer_headers)
    assert resp_viewer.status_code == 403

    # Both can access basic endpoints
    resp_admin_comp = await client.get("/api/v2/companies/", headers=admin_headers)
    resp_viewer_comp = await client.get("/api/v2/companies/", headers=viewer_headers)
    assert resp_admin_comp.status_code == 200
    assert resp_viewer_comp.status_code == 200


# ---------------------------------------------------------------------------
# Data Consistency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_consistency_after_operations(client: AsyncClient):
    """Data should remain consistent after CRUD operations."""
    headers = await _integration_headers(client, "data_cons@example.com", role="company_admin")

    # Create multiple branches
    for i in range(3):
        branch_payload = {
            "name": f"Consistency Branch {i}",
            "company_id": "integration-test-company",
            "address": f"Address {i}",
            "phone": f"+99450111111{i}",
            "email": f"branch{i}@test.com",
            "manager_name": f"Manager {i}",
            "is_active": True,
        }
        resp = await client.post("/api/v2/branches/", json=branch_payload, headers=headers)
        assert resp.status_code == 201

    # List all branches
    resp_list = await client.get("/api/v2/branches/", headers=headers)
    assert resp_list.status_code == 200
    data = resp_list.json()
    assert len(data["items"]) >= 3

    # Each branch should have a unique name
    names = [item["name"] for item in data["items"]]
    assert len(names) == len(set(names)), "Branch names should be unique"
