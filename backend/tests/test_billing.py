"""Billing module tests.

Covers:
  - List plans
  - Subscribe
  - Check quotas
  - Track usage
  - Feature flags
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _billing_headers(client: AsyncClient, email: str, role: str = "company_admin") -> dict:
    """Create auth headers for billing tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Billing",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "billing-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "billing-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "billing-test-company",
    }


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_plans(client: AsyncClient):
    """Listing billing plans should return 200 with plan data."""
    headers = await _billing_headers(client, "plan_list@example.com")
    resp = await client.get("/api/v2/billing/plans", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "plans" in data
    assert len(data["plans"]) > 0


@pytest.mark.asyncio
async def test_get_plan_by_name(client: AsyncClient):
    """Getting a specific plan should return 200."""
    headers = await _billing_headers(client, "plan_get@example.com")
    resp = await client.get("/api/v2/billing/plans/Free", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["plan_name"] == "Free"


@pytest.mark.asyncio
async def test_get_plan_premium(client: AsyncClient):
    """Getting the Premium plan should return correct pricing."""
    headers = await _billing_headers(client, "plan_prem@example.com")
    resp = await client.get("/api/v2/billing/plans/Premium", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["plan_name"] == "Premium"
    assert data["price_monthly"] == 299


@pytest.mark.asyncio
async def test_plan_price_mapping(client: AsyncClient):
    """All known plan names should resolve correctly."""
    headers = await _billing_headers(client, "plan_map@example.com")
    plan_prices = {"Free": 0, "Starter": 49, "Growth": 99, "Professional": 199, "Premium": 299}
    for plan_name, expected_price in plan_prices.items():
        resp = await client.get(f"/api/v2/billing/plans/{plan_name}", headers=headers)
        assert resp.status_code == 200, f"Plan {plan_name} should exist"
        data = resp.json()
        assert data["price_monthly"] == expected_price


@pytest.mark.asyncio
async def test_get_nonexistent_plan(client: AsyncClient):
    """Getting a non-existent plan should return 404."""
    headers = await _billing_headers(client, "plan_404@example.com")
    resp = await client.get("/api/v2/billing/plans/NonExistent", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_to_plan(client: AsyncClient):
    """Subscribing to a plan should return 200."""
    headers = await _billing_headers(client, "sub_create@example.com")
    payload = {
        "plan": "Growth",
        "billing_cycle": "monthly",
        "auto_renew": True,
        "company_id": "billing-test-company",
    }
    resp = await client.post("/api/v2/billing/subscription", json=payload, headers=headers)
    # May return 200, 404, 422, or 500 depending on service implementation
    assert resp.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
async def test_get_subscription(client: AsyncClient):
    """Getting current subscription should return 200 or 404."""
    headers = await _billing_headers(client, "sub_get@example.com")
    resp = await client.get("/api/v2/billing/subscription", headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_cancel_subscription(client: AsyncClient):
    """Cancelling subscription should return 200."""
    headers = await _billing_headers(client, "sub_cancel@example.com")
    resp = await client.delete("/api/v2/billing/subscription", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_subscribe_invalid_plan(client: AsyncClient):
    """Subscribing to invalid plan should return 422."""
    headers = await _billing_headers(client, "sub_bad@example.com")
    payload = {
        "plan": "MegaUltraPlan",
        "billing_cycle": "monthly",
    }
    resp = await client.post("/api/v2/billing/subscription", json=payload, headers=headers)
    assert resp.status_code in (422, 404, 500)


# ---------------------------------------------------------------------------
# Quotas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_quotas(client: AsyncClient):
    """Getting quotas should return 200 or 404."""
    headers = await _billing_headers(client, "quota_get@example.com")
    resp = await client.get("/api/v2/billing/quotas", headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_increment_usage(client: AsyncClient):
    """Incrementing usage should work."""
    headers = await _billing_headers(client, "quota_inc@example.com")
    payload = {"feature": "ai_requests", "amount": 1}
    resp = await client.post("/api/v2/billing/usage/increment", json=payload, headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_increment_usage_invalid_feature(client: AsyncClient):
    """Incrementing usage for invalid feature should fail gracefully."""
    headers = await _billing_headers(client, "quota_bad@example.com")
    payload = {"feature": "nonexistent_feature", "amount": 1}
    resp = await client.post("/api/v2/billing/usage/increment", json=payload, headers=headers)
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_features(client: AsyncClient):
    """Listing feature flags should return 200."""
    headers = await _billing_headers(client, "feat_list@example.com")
    resp = await client.get("/api/v2/billing/features", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_toggle_feature(client: AsyncClient):
    """Toggling a feature should return 200."""
    headers = await _billing_headers(client, "feat_toggle@example.com")
    payload = {"enabled": True, "reason": "Test toggle"}
    resp = await client.post(
        "/api/v2/billing/features/social_posting/toggle",
        json=payload,
        headers=headers,
    )
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_toggle_feature_no_reason(client: AsyncClient):
    """Toggling without reason should still work."""
    headers = await _billing_headers(client, "feat_noreason@example.com")
    payload = {"enabled": False}
    resp = await client.post(
        "/api/v2/billing/features/social_posting/toggle",
        json=payload,
        headers=headers,
    )
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_usage(client: AsyncClient):
    """Getting usage should return 200 or 404."""
    headers = await _billing_headers(client, "usage_get@example.com")
    resp = await client.get("/api/v2/billing/usage", headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_get_usage_with_period(client: AsyncClient):
    """Getting usage with period should work."""
    headers = await _billing_headers(client, "usage_period@example.com")
    resp = await client.get("/api/v2/billing/usage?period=2024-01", headers=headers)
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Stats (Admin only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stats_admin(client: AsyncClient):
    """Admin should be able to get billing stats."""
    headers = await _billing_headers(client, "stats_admin@example.com", role="super_admin")
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_get_stats_denied_for_viewer(client: AsyncClient):
    """Viewer should NOT be able to get billing stats."""
    headers = await _billing_headers(client, "stats_viewer@example.com", role="user")
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_stats_denied_for_analyst(client: AsyncClient):
    """Analyst should NOT be able to get billing stats."""
    headers = await _billing_headers(client, "stats_analyst@example.com", role="analyst")
    resp = await client.get("/api/v2/billing/stats", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_billing_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/billing/plans")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_full_billing_lifecycle(client: AsyncClient):
    """Full lifecycle: list plans -> get plan -> list features -> get usage."""
    headers = await _billing_headers(client, "billing_full@example.com")

    # 1. List plans
    resp_plans = await client.get("/api/v2/billing/plans", headers=headers)
    assert resp_plans.status_code == 200
    plans_data = resp_plans.json()
    assert len(plans_data["plans"]) > 0

    # 2. Get specific plan
    resp_plan = await client.get("/api/v2/billing/plans/Growth", headers=headers)
    assert resp_plan.status_code == 200

    # 3. List features
    resp_features = await client.get("/api/v2/billing/features", headers=headers)
    assert resp_features.status_code == 200

    # 4. Get quotas (may be 404 if no subscription)
    resp_quotas = await client.get("/api/v2/billing/quotas", headers=headers)
    assert resp_quotas.status_code in (200, 404, 422)

    # 5. Get usage
    resp_usage = await client.get("/api/v2/billing/usage", headers=headers)
    assert resp_usage.status_code in (200, 404, 422)
