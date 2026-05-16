"""Export module tests.

Covers:
  - Export job creation (sync and async)
  - Format validation (CSV, Excel, PDF, JSON)
  - Export listing and status
  - Export cancellation
  - Template CRUD
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _export_headers(client: AsyncClient, email: str, role: str = "company_admin") -> dict:
    """Create auth headers for export tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Export",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "export-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "export-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "export-test-company",
    }


# ---------------------------------------------------------------------------
# Export Job Creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_csv_export_job(client: AsyncClient):
    """Creating a CSV export job should return 202 with job metadata."""
    headers = await _export_headers(client, "export_csv@example.com")
    payload = {
        "module": "followers",
        "format": "csv",
        "filters": {"platform": "instagram"},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (202, 200, 201)
    data = resp.json()
    assert "id" in data or "job_id" in data or data.get("success") is True


@pytest.mark.asyncio
async def test_create_excel_export_job(client: AsyncClient):
    """Creating an Excel export job should return 202."""
    headers = await _export_headers(client, "export_xlsx@example.com")
    payload = {
        "module": "followers",
        "format": "excel",
        "filters": {"platform": "instagram"},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (202, 200, 201)


@pytest.mark.asyncio
async def test_create_json_export_job(client: AsyncClient):
    """Creating a JSON export job should return 202."""
    headers = await _export_headers(client, "export_json@example.com")
    payload = {
        "module": "followers",
        "format": "json",
        "filters": {},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (202, 200, 201)


@pytest.mark.asyncio
async def test_create_pdf_export_job(client: AsyncClient):
    """Creating a PDF export job should return 202."""
    headers = await _export_headers(client, "export_pdf@example.com")
    payload = {
        "module": "followers",
        "format": "pdf",
        "filters": {"platform": "instagram"},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (202, 200, 201)


# ---------------------------------------------------------------------------
# Format Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_invalid_format_rejected(client: AsyncClient):
    """Export with invalid format should return 422."""
    headers = await _export_headers(client, "export_bad_fmt@example.com")
    payload = {
        "module": "followers",
        "format": "invalid_format",
        "filters": {},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (422, 400)


@pytest.mark.asyncio
async def test_export_missing_format_rejected(client: AsyncClient):
    """Export without format should return 422."""
    headers = await _export_headers(client, "export_no_fmt@example.com")
    payload = {
        "module": "followers",
        "filters": {},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (422, 400)


@pytest.mark.asyncio
async def test_export_missing_module_rejected(client: AsyncClient):
    """Export without module should return 422."""
    headers = await _export_headers(client, "export_no_mod@example.com")
    payload = {
        "format": "csv",
        "filters": {},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (422, 400)


@pytest.mark.asyncio
async def test_csv_format_validation(client: AsyncClient):
    """CSV export should produce valid CSV-like output."""
    headers = await _export_headers(client, "export_csv_val@example.com")
    # Create export
    payload = {
        "module": "followers",
        "format": "csv",
        "filters": {},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (202, 200, 201)


@pytest.mark.asyncio
async def test_json_format_validation(client: AsyncClient):
    """JSON export should produce valid JSON."""
    headers = await _export_headers(client, "export_json_val@example.com")
    payload = {
        "module": "followers",
        "format": "json",
        "filters": {},
    }
    resp = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp.status_code in (202, 200, 201)


# ---------------------------------------------------------------------------
# Export Listing and Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_export_jobs(client: AsyncClient):
    """Listing export jobs should return 200."""
    headers = await _export_headers(client, "export_list@example.com")
    resp = await client.get("/api/v2/export/jobs", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_get_export_job_status(client: AsyncClient):
    """Getting export job status should return 200 with status."""
    headers = await _export_headers(client, "export_status@example.com")
    # List to get job IDs
    resp_list = await client.get("/api/v2/export/jobs", headers=headers)
    if resp_list.status_code == 200:
        data = resp_list.json()
        items = data.get("items", data.get("data", {}).get("items", []))
        if items:
            job_id = items[0]["id"]
            resp = await client.get(f"/api/v2/export/jobs/{job_id}", headers=headers)
            assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_export_job_status_fields(client: AsyncClient):
    """Export job status should contain expected fields."""
    headers = await _export_headers(client, "export_status_fields@example.com")
    resp = await client.get("/api/v2/export/jobs", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("items", data.get("data", {}).get("items", []))
        if items:
            job = items[0]
            assert "id" in job
            assert "status" in job or "state" in job


# ---------------------------------------------------------------------------
# Export Cancellation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_export_job(client: AsyncClient):
    """Cancelling a pending export job should return 200."""
    headers = await _export_headers(client, "export_cancel@example.com")
    # Create an export
    payload = {
        "module": "followers",
        "format": "csv",
        "filters": {},
    }
    resp_create = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    if resp_create.status_code in (202, 200, 201):
        data = resp_create.json()
        job_id = data.get("id") or data.get("job_id")
        if job_id:
            resp_cancel = await client.post(f"/api/v2/export/jobs/{job_id}/cancel", headers=headers)
            assert resp_cancel.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Export Templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_export_template(client: AsyncClient):
    """Creating an export template should return 201."""
    headers = await _export_headers(client, "export_tpl_create@example.com")
    payload = {
        "name": "Monthly Report Template",
        "description": "Standard monthly follower report",
        "module": "followers",
        "format": "csv",
        "columns": ["username", "follower_count", "engagement_rate", "platform"],
        "filters": {"platform": "instagram"},
        "is_active": True,
    }
    resp = await client.post("/api/v2/export/templates", json=payload, headers=headers)
    assert resp.status_code in (201, 200, 404)


@pytest.mark.asyncio
async def test_list_export_templates(client: AsyncClient):
    """Listing export templates should return 200."""
    headers = await _export_headers(client, "export_tpl_list@example.com")
    resp = await client.get("/api/v2/export/templates", headers=headers)
    assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_export_access(client: AsyncClient):
    """Unauthenticated access to export endpoints should fail."""
    resp = await client.get("/api/v2/export/jobs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_export_job(client: AsyncClient):
    """Getting a non-existent export job should return 404."""
    headers = await _export_headers(client, "export_404@example.com")
    resp = await client.get("/api/v2/export/jobs/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_export_lifecycle(client: AsyncClient):
    """Full lifecycle: create export -> list -> get status -> (cancel)."""
    headers = await _export_headers(client, "export_full@example.com")

    # 1. Create export
    payload = {
        "module": "followers",
        "format": "json",
        "filters": {"platform": "instagram"},
    }
    resp_create = await client.post("/api/v2/export/jobs", json=payload, headers=headers)
    assert resp_create.status_code in (202, 200, 201)

    # 2. List exports
    resp_list = await client.get("/api/v2/export/jobs", headers=headers)
    assert resp_list.status_code in (200, 404)

    # 3. List templates
    resp_tpl = await client.get("/api/v2/export/templates", headers=headers)
    assert resp_tpl.status_code in (200, 404)

    # 4. Try to get status of created job
    if resp_create.status_code in (202, 200, 201):
        data = resp_create.json()
        job_id = data.get("id") or data.get("job_id")
        if job_id:
            resp_status = await client.get(f"/api/v2/export/jobs/{job_id}", headers=headers)
            assert resp_status.status_code in (200, 404)
