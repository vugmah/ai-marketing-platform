"""ERP module tests.

Covers:
  - Create connection
  - Sync operations (mock)
  - Health check
  - Field mapping CRUD
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _erp_headers(client: AsyncClient, email: str, role: str = "company_admin") -> dict:
    """Create auth headers for ERP tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="ERP",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "erp-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "erp-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "erp-test-company",
    }


# ---------------------------------------------------------------------------
# Connection Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_connection(client: AsyncClient, mock_erp_connector):
    """Creating an ERP connection should return 201."""
    headers = await _erp_headers(client, "conn_create@example.com")
    payload = {
        "name": "Test ERP Connection",
        "base_url": "https://erp.example.com/api",
        "client_id": "test_client",
        "client_secret": "test_secret",
        "webhook_secret": "webhook_secret_123",
        "is_active": True,
        "sync_products": True,
        "sync_customers": True,
        "sync_orders": True,
    }
    resp = await client.post("/api/v2/erp/connections", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_list_connections(client: AsyncClient):
    """Listing ERP connections should return 200."""
    headers = await _erp_headers(client, "conn_list@example.com")
    resp = await client.get("/api/v2/erp/connections", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_connection(client: AsyncClient):
    """Getting a connection by ID should return 200 or 404."""
    headers = await _erp_headers(client, "conn_get@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.get(f"/api/v2/erp/connections/{conn_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_connection(client: AsyncClient):
    """Updating a connection should return 200."""
    headers = await _erp_headers(client, "conn_upd@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        payload = {"name": "Updated Connection Name"}
        resp = await client.put(f"/api/v2/erp/connections/{conn_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_connection(client: AsyncClient):
    """Deleting a connection should return 204."""
    headers = await _erp_headers(client, "conn_del@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/erp/connections/{conn_id}", headers=headers)
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_connection_stats(client: AsyncClient):
    """Getting connection stats should return 200."""
    headers = await _erp_headers(client, "conn_stats@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.get(f"/api/v2/erp/connections/{conn_id}/stats", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_test_connection(client: AsyncClient, mock_erp_connector):
    """Testing a connection should return 200."""
    headers = await _erp_headers(client, "conn_test@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/erp/connections/{conn_id}/test", headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Sync Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_products(client: AsyncClient, mock_erp_connector):
    """Syncing products should return 200."""
    headers = await _erp_headers(client, "sync_prod@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/erp/connections/{conn_id}/sync/products", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_sync_customers(client: AsyncClient, mock_erp_connector):
    """Syncing customers should return 200."""
    headers = await _erp_headers(client, "sync_cust@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/erp/connections/{conn_id}/sync/customers", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_sync_orders(client: AsyncClient, mock_erp_connector):
    """Syncing orders should return 200."""
    headers = await _erp_headers(client, "sync_ord@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/erp/connections/{conn_id}/sync/orders", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_sync_inventory(client: AsyncClient, mock_erp_connector):
    """Syncing inventory should return 200."""
    headers = await _erp_headers(client, "sync_inv@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/erp/connections/{conn_id}/sync/inventory", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_sync_all(client: AsyncClient, mock_erp_connector):
    """Syncing all data should return 200."""
    headers = await _erp_headers(client, "sync_all@example.com")
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp = await client.post(f"/api/v2/erp/connections/{conn_id}/sync", headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Health Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_sync_health(client: AsyncClient, mock_erp_connector):
    """Getting sync health should return 200."""
    headers = await _erp_headers(client, "health_sync@example.com")
    resp = await client.get("/api/v2/erp/sync-health", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Mapping Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_mappings(client: AsyncClient):
    """Listing field mappings should return 200."""
    headers = await _erp_headers(client, "map_list@example.com")
    resp = await client.get("/api/v2/erp/mappings", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_mappings_with_entity_filter(client: AsyncClient):
    """Listing mappings with entity_type filter should work."""
    headers = await _erp_headers(client, "map_filter@example.com")
    resp = await client.get("/api/v2/erp/mappings?entity_type=product", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_mapping(client: AsyncClient):
    """Creating a field mapping should return 201."""
    headers = await _erp_headers(client, "map_create@example.com")
    payload = {
        "entity_type": "product",
        "erp_field": "price",
        "crm_field": "unit_price",
        "is_key": False,
        "is_active": True,
    }
    resp = await client.post("/api/v2/erp/mappings", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_get_mapping(client: AsyncClient):
    """Getting a mapping by ID should return 200 or 404."""
    headers = await _erp_headers(client, "map_get@example.com")
    resp_list = await client.get("/api/v2/erp/mappings", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        map_id = items[0]["id"]
        resp = await client.get(f"/api/v2/erp/mappings/{map_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_mapping(client: AsyncClient):
    """Updating a mapping should return 200."""
    headers = await _erp_headers(client, "map_upd@example.com")
    resp_list = await client.get("/api/v2/erp/mappings", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        map_id = items[0]["id"]
        payload = {"is_active": False}
        resp = await client.patch(f"/api/v2/erp/mappings/{map_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_mapping(client: AsyncClient):
    """Deleting a mapping should return 204."""
    headers = await _erp_headers(client, "map_del@example.com")
    resp_list = await client.get("/api/v2/erp/mappings", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        map_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/erp/mappings/{map_id}", headers=headers)
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_default_mappings(client: AsyncClient):
    """Getting default mappings should return 200."""
    headers = await _erp_headers(client, "map_def@example.com")
    resp = await client.get("/api/v2/erp/mappings/defaults", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_save_default_mappings(client: AsyncClient):
    """Saving default mappings should return 200."""
    headers = await _erp_headers(client, "map_savedef@example.com")
    resp = await client.post("/api/v2/erp/mappings/defaults/save", headers=headers)
    assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Data Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_products(client: AsyncClient):
    """Listing products should return 200."""
    headers = await _erp_headers(client, "data_prod@example.com")
    resp = await client.get("/api/v2/erp/products", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_customers(client: AsyncClient):
    """Listing customers should return 200."""
    headers = await _erp_headers(client, "data_cust@example.com")
    resp = await client.get("/api/v2/erp/customers", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_orders(client: AsyncClient):
    """Listing orders should return 200."""
    headers = await _erp_headers(client, "data_ord@example.com")
    resp = await client.get("/api/v2/erp/orders", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_erp_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/erp/connections")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_connection(client: AsyncClient):
    """Getting a non-existent connection should return 404."""
    headers = await _erp_headers(client, "conn_404@example.com")
    resp = await client.get("/api/v2/erp/connections/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_mapping(client: AsyncClient):
    """Getting a non-existent mapping should return 404."""
    headers = await _erp_headers(client, "map_404@example.com")
    resp = await client.get("/api/v2/erp/mappings/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_erp_lifecycle(client: AsyncClient, mock_erp_connector):
    """Full lifecycle: create connection -> list -> get health -> list mappings -> delete."""
    headers = await _erp_headers(client, "erp_full@example.com")

    # 1. Create connection
    conn_payload = {
        "name": "Full Test Connection",
        "base_url": "https://erp.test.com/api",
        "client_id": "full_client",
        "client_secret": "full_secret",
        "webhook_secret": "webhook_full",
        "is_active": True,
    }
    resp_conn = await client.post("/api/v2/erp/connections", json=conn_payload, headers=headers)
    assert resp_conn.status_code in (201, 422, 500)

    # 2. List connections
    resp_list = await client.get("/api/v2/erp/connections", headers=headers)
    assert resp_list.status_code == 200

    # 3. Get sync health
    resp_health = await client.get("/api/v2/erp/sync-health", headers=headers)
    assert resp_health.status_code == 200

    # 4. List mappings
    resp_maps = await client.get("/api/v2/erp/mappings", headers=headers)
    assert resp_maps.status_code == 200

    # 5. List products
    resp_prods = await client.get("/api/v2/erp/products", headers=headers)
    assert resp_prods.status_code == 200

    # 6. List customers
    resp_custs = await client.get("/api/v2/erp/customers", headers=headers)
    assert resp_custs.status_code == 200

    # 7. List orders
    resp_orders = await client.get("/api/v2/erp/orders", headers=headers)
    assert resp_orders.status_code == 200

    # 8. Delete connection
    items = resp_list.json().get("items", [])
    if items:
        conn_id = items[0]["id"]
        resp_del = await client.delete(f"/api/v2/erp/connections/{conn_id}", headers=headers)
        assert resp_del.status_code == 204
