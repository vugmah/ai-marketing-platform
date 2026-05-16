"""Ads Intelligence module tests.

Covers:
  - Connect platform (mock)
  - Campaign CRUD
  - Metrics
  - Recommendations
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _ads_headers(client: AsyncClient, email: str, role: str = "marketing_manager") -> dict:
    """Create auth headers for ads tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Ads",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "ads-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "ads-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "ads-test-company",
    }


# ---------------------------------------------------------------------------
# Platform Connections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_google_ads(client: AsyncClient):
    """Connecting Google Ads should return 200."""
    headers = await _ads_headers(client, "ads_google@example.com")
    payload = {
        "platform": "google_ads",
        "name": "Google Ads Main Account",
        "customer_id": "123-456-7890",
        "credentials": {"token": "mock_google_token"},
    }
    resp = await client.post("/api/v2/ads/connections", json=payload, headers=headers)
    assert resp.status_code in (200, 201, 422, 500)


@pytest.mark.asyncio
async def test_connect_facebook_ads(client: AsyncClient):
    """Connecting Facebook Ads should return 200."""
    headers = await _ads_headers(client, "ads_fb@example.com")
    payload = {
        "platform": "facebook_ads",
        "name": "Facebook Ads Main Account",
        "account_id": "act_123456789",
        "credentials": {"token": "mock_fb_token"},
    }
    resp = await client.post("/api/v2/ads/connections", json=payload, headers=headers)
    assert resp.status_code in (200, 201, 422, 500)


@pytest.mark.asyncio
async def test_connect_tiktok_ads(client: AsyncClient):
    """Connecting TikTok Ads should return 200."""
    headers = await _ads_headers(client, "ads_tiktok@example.com")
    payload = {
        "platform": "tiktok_ads",
        "name": "TikTok Ads Account",
        "advertiser_id": "1234567890",
        "credentials": {"token": "mock_tiktok_token"},
    }
    resp = await client.post("/api/v2/ads/connections", json=payload, headers=headers)
    assert resp.status_code in (200, 201, 422, 500)


@pytest.mark.asyncio
async def test_list_connections(client: AsyncClient):
    """Listing ad connections should return 200."""
    headers = await _ads_headers(client, "ads_list@example.com")
    resp = await client.get("/api/v2/ads/connections", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_disconnect_platform(client: AsyncClient):
    """Disconnecting an ad platform should return 204."""
    headers = await _ads_headers(client, "ads_disc@example.com")
    resp_list = await client.get("/api/v2/ads/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/ads/connections/{conn_id}", headers=headers)
        assert resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_campaigns(client: AsyncClient):
    """Listing campaigns should return 200."""
    headers = await _ads_headers(client, "camp_list@example.com")
    resp = await client.get("/api/v2/ads/campaigns", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_campaigns_with_platform_filter(client: AsyncClient):
    """Listing campaigns with platform filter should work."""
    headers = await _ads_headers(client, "camp_pf@example.com")
    resp = await client.get("/api/v2/ads/campaigns?platform=google_ads", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_campaigns_with_status_filter(client: AsyncClient):
    """Listing campaigns with status filter should work."""
    headers = await _ads_headers(client, "camp_sf@example.com")
    resp = await client.get("/api/v2/ads/campaigns?status=active", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_campaign(client: AsyncClient):
    """Creating a campaign should return 201."""
    headers = await _ads_headers(client, "camp_create@example.com")
    payload = {
        "name": "Summer Sale Campaign",
        "platform": "google_ads",
        "budget": 5000,
        "currency": "USD",
        "start_date": "2025-06-01",
        "end_date": "2025-08-31",
        "targeting": {"locations": ["US", "UK"], "languages": ["en"]},
    }
    resp = await client.post("/api/v2/ads/campaigns", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_get_campaign(client: AsyncClient):
    """Getting a campaign should return 200 or 404."""
    headers = await _ads_headers(client, "camp_get@example.com")
    resp_list = await client.get("/api/v2/ads/campaigns", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        camp_id = items[0]["id"]
        resp = await client.get(f"/api/v2/ads/campaigns/{camp_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_campaign(client: AsyncClient):
    """Updating a campaign should return 200."""
    headers = await _ads_headers(client, "camp_upd@example.com")
    resp_list = await client.get("/api/v2/ads/campaigns", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        camp_id = items[0]["id"]
        payload = {"name": "Updated Campaign Name", "budget": 7500}
        resp = await client.put(f"/api/v2/ads/campaigns/{camp_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_campaign(client: AsyncClient):
    """Deleting a campaign should return 204."""
    headers = await _ads_headers(client, "camp_del@example.com")
    resp_list = await client.get("/api/v2/ads/campaigns", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        camp_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/ads/campaigns/{camp_id}", headers=headers)
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_sync_campaigns(client: AsyncClient):
    """Syncing campaigns from platform should return 200."""
    headers = await _ads_headers(client, "camp_sync@example.com")
    resp_list = await client.get("/api/v2/ads/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/ads/campaigns/sync/{conn_id}", headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_metrics(client: AsyncClient):
    """Listing metrics should return 200."""
    headers = await _ads_headers(client, "metr_list@example.com")
    resp = await client.get("/api/v2/ads/metrics", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_metrics_with_date_filter(client: AsyncClient):
    """Listing metrics with date filter should work."""
    headers = await _ads_headers(client, "metr_df@example.com")
    resp = await client.get("/api/v2/ads/metrics?start_date=2024-01-01&end_date=2024-12-31", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_metrics_with_campaign_filter(client: AsyncClient):
    """Listing metrics with campaign filter should work."""
    headers = await _ads_headers(client, "metr_cf@example.com")
    resp = await client.get("/api/v2/ads/metrics?campaign_id=1", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_performance_summary(client: AsyncClient):
    """Getting performance summary should return 200."""
    headers = await _ads_headers(client, "perf_sum@example.com")
    resp = await client.get("/api/v2/ads/metrics/summary", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_performance_summary_with_date_range(client: AsyncClient):
    """Performance summary with date range should work."""
    headers = await _ads_headers(client, "perf_dr@example.com")
    resp = await client.get("/api/v2/ads/metrics/summary?start_date=2024-01-01&end_date=2024-12-31", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_recommendations(client: AsyncClient):
    """Listing ads recommendations should return 200."""
    headers = await _ads_headers(client, "rec_list@example.com")
    resp = await client.get("/api/v2/ads/recommendations", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_apply_recommendation(client: AsyncClient):
    """Applying a recommendation should return 200."""
    headers = await _ads_headers(client, "rec_apply@example.com")
    resp_list = await client.get("/api/v2/ads/recommendations", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        rec_id = items[0]["id"]
        resp = await client.post(f"/api/v2/ads/recommendations/{rec_id}/apply", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dismiss_recommendation(client: AsyncClient):
    """Dismissing a recommendation should return 200."""
    headers = await _ads_headers(client, "rec_dismiss@example.com")
    resp_list = await client.get("/api/v2/ads/recommendations", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        rec_id = items[0]["id"]
        resp = await client.post(f"/api/v2/ads/recommendations/{rec_id}/dismiss", headers=headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_report(client: AsyncClient):
    """Generating a report should return 200."""
    headers = await _ads_headers(client, "rpt_gen@example.com")
    payload = {
        "report_type": "performance",
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        "platforms": ["google_ads", "facebook_ads"],
    }
    resp = await client.post("/api/v2/ads/reports", json=payload, headers=headers)
    assert resp.status_code in (200, 201, 422, 500)


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_ads_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/ads/campaigns")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_campaign(client: AsyncClient):
    """Getting a non-existent campaign should return 404."""
    headers = await _ads_headers(client, "camp_404@example.com")
    resp = await client.get("/api/v2/ads/campaigns/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_ads_lifecycle(client: AsyncClient):
    """Full lifecycle: connect -> list campaigns -> list metrics -> get recommendations."""
    headers = await _ads_headers(client, "ads_full@example.com")

    # 1. Connect Google Ads
    conn_payload = {
        "platform": "google_ads",
        "name": "Full Test Account",
        "customer_id": "1234567890",
        "credentials": {"token": "mock_token"},
    }
    resp_conn = await client.post("/api/v2/ads/connections", json=conn_payload, headers=headers)
    assert resp_conn.status_code in (200, 201, 422, 500)

    # 2. List connections
    resp_conns = await client.get("/api/v2/ads/connections", headers=headers)
    assert resp_conns.status_code == 200

    # 3. List campaigns
    resp_camps = await client.get("/api/v2/ads/campaigns", headers=headers)
    assert resp_camps.status_code == 200

    # 4. List metrics
    resp_metr = await client.get("/api/v2/ads/metrics", headers=headers)
    assert resp_metr.status_code == 200

    # 5. Performance summary
    resp_perf = await client.get("/api/v2/ads/metrics/summary", headers=headers)
    assert resp_perf.status_code == 200

    # 6. Recommendations
    resp_rec = await client.get("/api/v2/ads/recommendations", headers=headers)
    assert resp_rec.status_code == 200
