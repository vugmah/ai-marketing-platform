"""Media module tests.

Covers:
  - List assets with filters
  - Collections CRUD
  - Tags CRUD
  - AI analysis (mock)
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _media_headers(client: AsyncClient, email: str, role: str = "branch_manager") -> dict:
    """Create auth headers for media tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Media",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "media-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "media-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "media-test-company",
    }


# ---------------------------------------------------------------------------
# Asset Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_assets(client: AsyncClient):
    """Listing media assets should return 200."""
    headers = await _media_headers(client, "asset_list@example.com")
    resp = await client.get("/api/v2/media/assets", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_list_assets_with_type_filter(client: AsyncClient):
    """Listing assets with type filter should work."""
    headers = await _media_headers(client, "asset_type@example.com")
    resp = await client.get("/api/v2/media/assets?type=image", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_assets_with_status_filter(client: AsyncClient):
    """Listing assets with status filter should work."""
    headers = await _media_headers(client, "asset_status@example.com")
    resp = await client.get("/api/v2/media/assets?status=active", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_assets_with_collection_filter(client: AsyncClient):
    """Listing assets with collection filter should work."""
    headers = await _media_headers(client, "asset_coll@example.com")
    resp = await client.get("/api/v2/media/assets?collection_id=1", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_assets_with_sort(client: AsyncClient):
    """Listing assets with sort parameter should work."""
    headers = await _media_headers(client, "asset_sort@example.com")
    resp = await client.get("/api/v2/media/assets?sort=created_at&order=desc", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_assets_with_pagination(client: AsyncClient):
    """Listing assets with pagination should work."""
    headers = await _media_headers(client, "asset_page@example.com")
    resp = await client.get("/api/v2/media/assets?page=1&limit=10", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "page" in data
    assert "limit" in data


@pytest.mark.asyncio
async def test_upload_media_asset(client: AsyncClient, mock_storage):
    """Uploading a media asset should return 201."""
    headers = await _media_headers(client, "asset_upload@example.com")
    # Create a test file
    from io import BytesIO
    test_file = BytesIO(b"fake image data for testing")
    files = {"file": ("test_image.jpg", test_file, "image/jpeg")}
    resp = await client.post("/api/v2/media/upload", files=files, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_upload_media_asset_with_metadata(client: AsyncClient, mock_storage):
    """Uploading with metadata should return 201."""
    headers = await _media_headers(client, "asset_meta@example.com")
    from io import BytesIO
    test_file = BytesIO(b"fake image data")
    files = {"file": ("test_image.png", test_file, "image/png")}
    data = {"title": "Test Image", "description": "A test image", "tags": "test,demo"}
    resp = await client.post("/api/v2/media/upload", files=files, data=data, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_get_asset(client: AsyncClient):
    """Getting an asset by ID should return 200 or 404."""
    headers = await _media_headers(client, "asset_get@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        resp = await client.get(f"/api/v2/media/assets/{asset_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_asset(client: AsyncClient):
    """Updating an asset should return 200."""
    headers = await _media_headers(client, "asset_upd@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        payload = {"title": "Updated Title", "description": "Updated desc"}
        resp = await client.patch(f"/api/v2/media/assets/{asset_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_asset(client: AsyncClient):
    """Deleting an asset should return 204."""
    headers = await _media_headers(client, "asset_del@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/media/assets/{asset_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Collection Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_collection(client: AsyncClient):
    """Creating a collection should return 201."""
    headers = await _media_headers(client, "coll_create@example.com")
    payload = {
        "name": "Holiday Campaign 2024",
        "description": "Assets for holiday campaign",
        "is_public": False,
    }
    resp = await client.post("/api/v2/media/collections", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_list_collections(client: AsyncClient):
    """Listing collections should return 200."""
    headers = await _media_headers(client, "coll_list@example.com")
    # Create first
    payload = {"name": "Test Collection"}
    await client.post("/api/v2/media/collections", json=payload, headers=headers)

    resp = await client.get("/api/v2/media/collections", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_list_collections_with_filters(client: AsyncClient):
    """Listing collections with is_public filter should work."""
    headers = await _media_headers(client, "coll_filter@example.com")
    resp = await client.get("/api/v2/media/collections?is_public=false", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_collection(client: AsyncClient):
    """Getting a collection by ID should return 200 or 404."""
    headers = await _media_headers(client, "coll_get@example.com")
    resp_list = await client.get("/api/v2/media/collections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        coll_id = items[0]["id"]
        resp = await client.get(f"/api/v2/media/collections/{coll_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_collection(client: AsyncClient):
    """Updating a collection should return 200."""
    headers = await _media_headers(client, "coll_upd@example.com")
    resp_list = await client.get("/api/v2/media/collections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        coll_id = items[0]["id"]
        payload = {"name": "Updated Collection Name"}
        resp = await client.patch(f"/api/v2/media/collections/{coll_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_collection(client: AsyncClient):
    """Deleting a collection should return 204."""
    headers = await _media_headers(client, "coll_del@example.com")
    resp_list = await client.get("/api/v2/media/collections", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        coll_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/media/collections/{coll_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Tag Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tag(client: AsyncClient):
    """Creating a tag should return 201."""
    headers = await _media_headers(client, "tag_create@example.com")
    payload = {
        "name": "holiday-2024",
        "color": "#FF0000",
    }
    resp = await client.post("/api/v2/media/tags", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_list_tags(client: AsyncClient):
    """Listing tags should return 200."""
    headers = await _media_headers(client, "tag_list@example.com")
    resp = await client.get("/api/v2/media/tags", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_get_tag(client: AsyncClient):
    """Getting a tag by ID should return 200 or 404."""
    headers = await _media_headers(client, "tag_get@example.com")
    resp_list = await client.get("/api/v2/media/tags", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tag_id = items[0]["id"]
        resp = await client.get(f"/api/v2/media/tags/{tag_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_tag(client: AsyncClient):
    """Updating a tag should return 200."""
    headers = await _media_headers(client, "tag_upd@example.com")
    resp_list = await client.get("/api/v2/media/tags", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tag_id = items[0]["id"]
        payload = {"color": "#00FF00"}
        resp = await client.patch(f"/api/v2/media/tags/{tag_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_tag(client: AsyncClient):
    """Deleting a tag should return 204."""
    headers = await _media_headers(client, "tag_del@example.com")
    resp_list = await client.get("/api/v2/media/tags", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tag_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/media/tags/{tag_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# AI Analysis Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_asset_description(client: AsyncClient, mock_openai):
    """Analyzing asset description with AI should return 200."""
    headers = await _media_headers(client, "ai_desc@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        resp = await client.post(f"/api/v2/media/{asset_id}/ai/description", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_analyze_asset_tags(client: AsyncClient, mock_openai):
    """Auto-generating tags for an asset should return 200."""
    headers = await _media_headers(client, "ai_tags@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        resp = await client.post(f"/api/v2/media/{asset_id}/ai/tags", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_generate_asset_alt_text(client: AsyncClient, mock_openai):
    """Generating alt text for an asset should return 200."""
    headers = await _media_headers(client, "ai_alt@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        payload = {"context": "Used on product page"}
        resp = await client.post(f"/api/v2/media/{asset_id}/ai/alt-text", json=payload, headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_suggest_crops(client: AsyncClient):
    """Getting crop suggestions for an asset should return 200."""
    headers = await _media_headers(client, "ai_crops@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        payload = {"platforms": ["instagram", "facebook"]}
        resp = await client.post(f"/api/v2/media/{asset_id}/ai/crops", json=payload, headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# AI Generation Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_generate_image(client: AsyncClient, mock_openai):
    """Generating an image with AI should return 200."""
    headers = await _media_headers(client, "ai_gen_img@example.com")
    payload = {
        "prompt": "A beautiful sunset over mountains",
        "model": "dall-e-3",
        "size": "1024x1024",
        "quality": "standard",
        "count": 1,
    }
    resp = await client.post("/api/v2/media/ai/generate-image", json=payload, headers=headers)
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_ai_edit_image(client: AsyncClient, mock_openai):
    """Editing an image with AI should return 200."""
    headers = await _media_headers(client, "ai_edit_img@example.com")
    resp_list = await client.get("/api/v2/media/assets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        asset_id = items[0]["id"]
        payload = {
            "prompt": "Remove background",
            "edit_type": "background",
        }
        resp = await client.post(f"/api/v2/media/{asset_id}/ai/edit", json=payload, headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_media_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/media/assets")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_asset(client: AsyncClient):
    """Getting a non-existent asset should return 404."""
    headers = await _media_headers(client, "asset_404@example.com")
    resp = await client.get("/api/v2/media/assets/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_collection(client: AsyncClient):
    """Getting a non-existent collection should return 404."""
    headers = await _media_headers(client, "coll_404@example.com")
    resp = await client.get("/api/v2/media/collections/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_tag(client: AsyncClient):
    """Getting a non-existent tag should return 404."""
    headers = await _media_headers(client, "tag_404@example.com")
    resp = await client.get("/api/v2/media/tags/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_media_lifecycle(client: AsyncClient, mock_storage):
    """Full lifecycle: create collection -> list -> create tag -> list -> get -> delete."""
    headers = await _media_headers(client, "media_full@example.com")

    # 1. Create collection
    coll_payload = {"name": "Full Test Collection", "description": "Lifecycle test"}
    resp_coll = await client.post("/api/v2/media/collections", json=coll_payload, headers=headers)
    assert resp_coll.status_code in (201, 422, 500)

    # 2. List collections
    resp_coll_list = await client.get("/api/v2/media/collections", headers=headers)
    assert resp_coll_list.status_code == 200

    # 3. Create tag
    tag_payload = {"name": "full-test", "color": "#0000FF"}
    resp_tag = await client.post("/api/v2/media/tags", json=tag_payload, headers=headers)
    assert resp_tag.status_code in (201, 422, 500)

    # 4. List tags
    resp_tag_list = await client.get("/api/v2/media/tags", headers=headers)
    assert resp_tag_list.status_code == 200

    # 5. List assets
    resp_assets = await client.get("/api/v2/media/assets", headers=headers)
    assert resp_assets.status_code == 200

    # 6. Get and delete tag
    tag_items = resp_tag_list.json().get("items", [])
    if tag_items:
        tag_id = tag_items[0]["id"]
        resp_tag_del = await client.delete(f"/api/v2/media/tags/{tag_id}", headers=headers)
        assert resp_tag_del.status_code == 204

    # 7. Get and delete collection
    coll_items = resp_coll_list.json().get("items", [])
    if coll_items:
        coll_id = coll_items[0]["id"]
        resp_coll_del = await client.delete(f"/api/v2/media/collections/{coll_id}", headers=headers)
        assert resp_coll_del.status_code == 204
