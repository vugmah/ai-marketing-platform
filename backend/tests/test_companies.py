"""Company CRUD endpoint tests.

Covers:
  - Create company
  - List companies
  - Get single company
  - Update company
  - Delete company
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
async def _create_company(client: AsyncClient, payload: dict, headers: dict | None = None) -> dict:
    """Helper to create a company and return the created data."""
    req_headers = headers or {}
    resp = await client.post("/api/v2/companies/", json=payload, headers=req_headers)
    assert resp.status_code == 201, f"Create failed: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_company(client: AsyncClient, company_data):
    """Creating a company should return 201 with the company data."""
    company = await _create_company(client, company_data)
    assert company["name"] == company_data["name"]
    assert company["slug"] == company_data["slug"]
    assert company["description"] == company_data["description"]
    assert company["website"] == company_data["website"]
    assert company["phone"] == company_data["phone"]
    assert company["email"] == company_data["email"]
    assert company["address"] == company_data["address"]
    assert company["tax_number"] == company_data["tax_number"]
    assert company["is_active"] == company_data["is_active"]
    assert "id" in company
    assert "created_at" in company
    assert "updated_at" in company


@pytest.mark.asyncio
async def test_create_company_minimal(client: AsyncClient):
    """Creating a company with minimal data should use defaults."""
    payload = {"name": "Minimal Co"}
    company = await _create_company(client, payload)
    assert company["name"] == "Minimal Co"
    assert company["slug"] == ""
    assert company["is_active"] is True


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_companies(client: AsyncClient, company_data):
    """Listing companies should return 200 with a list containing created companies."""
    # Create two companies
    c1_data = {**company_data, "name": "Company One", "slug": "company-one"}
    c2_data = {**company_data, "name": "Company Two", "slug": "company-two"}
    company1 = await _create_company(client, c1_data)
    company2 = await _create_company(client, c2_data)

    # List all companies
    resp = await client.get("/api/v2/companies/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    ids = {c["id"] for c in data}
    assert company1["id"] in ids
    assert company2["id"] in ids


@pytest.mark.asyncio
async def test_list_companies_empty(client: AsyncClient):
    """Listing companies when none exist should return an empty list."""
    resp = await client.get("/api/v2/companies/")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_company(client: AsyncClient, company_data):
    """Getting a company by ID should return 200 with the company data."""
    created = await _create_company(client, company_data)
    resp = await client.get(f"/api/v2/companies/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["name"] == created["name"]


@pytest.mark.asyncio
async def test_get_company_not_found(client: AsyncClient):
    """Getting a non-existent company should return 404."""
    resp = await client.get("/api/v2/companies/non-existent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_company(client: AsyncClient, company_data):
    """Updating a company should return 200 with updated data."""
    created = await _create_company(client, company_data)
    update_payload = {
        "name": "Updated Company Name",
        "website": "https://updated.com",
        "phone": "+994509998877",
    }
    resp = await client.put(f"/api/v2/companies/{created['id']}", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Company Name"
    assert data["website"] == "https://updated.com"
    assert data["phone"] == "+994509998877"
    # Unchanged fields should persist
    assert data["slug"] == company_data["slug"]
    assert data["email"] == company_data["email"]
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_update_company_not_found(client: AsyncClient):
    """Updating a non-existent company should return 404."""
    update_payload = {"name": "Should Fail"}
    resp = await client.put("/api/v2/companies/non-existent-id", json=update_payload)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_company_partial_fields(client: AsyncClient, company_data):
    """Updating a company with only some fields should preserve others."""
    created = await _create_company(client, company_data)
    # Update only the name
    resp = await client.put(
        f"/api/v2/companies/{created['id']}",
        json={"name": "Partial Update"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Partial Update"
    # Other fields should remain unchanged
    assert data["slug"] == company_data["slug"]
    assert data["description"] == company_data["description"]
    assert data["tax_number"] == company_data["tax_number"]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_company(client: AsyncClient, company_data):
    """Deleting a company should return 204."""
    created = await _create_company(client, company_data)
    resp = await client.delete(f"/api/v2/companies/{created['id']}")
    assert resp.status_code == 204

    # Verify the company is actually deleted
    get_resp = await client.get(f"/api/v2/companies/{created['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_company_not_found(client: AsyncClient):
    """Deleting a non-existent company should return 404."""
    resp = await client.delete("/api/v2/companies/non-existent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Full CRUD lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_company_full_lifecycle(client: AsyncClient, company_data):
    """Test the full CRUD lifecycle of a company."""
    # Create
    created = await _create_company(client, company_data)
    company_id = created["id"]

    # Read (list)
    list_resp = await client.get("/api/v2/companies/")
    assert list_resp.status_code == 200
    assert any(c["id"] == company_id for c in list_resp.json())

    # Read (get)
    get_resp = await client.get(f"/api/v2/companies/{company_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == company_id

    # Update
    update_resp = await client.put(
        f"/api/v2/companies/{company_id}",
        json={"name": "Lifecycle Updated"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Lifecycle Updated"

    # Delete
    del_resp = await client.delete(f"/api/v2/companies/{company_id}")
    assert del_resp.status_code == 204

    # Verify deletion
    get_resp2 = await client.get(f"/api/v2/companies/{company_id}")
    assert get_resp2.status_code == 404
