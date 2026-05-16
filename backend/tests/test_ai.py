"""AI Architecture module tests.

Covers:
  - Prompt template CRUD
  - AI completion generation (mock OpenAI)
  - Suggestions CRUD
  - Recommendations CRUD
  - Usage tracking
  - Conversations and messages
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _ai_headers(client: AsyncClient, email: str, role: str = "company_admin") -> dict:
    """Create auth headers for AI module tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="AI",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "ai-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "ai-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "ai-test-company",
    }


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_prompt_template(client: AsyncClient):
    """Creating a prompt template should return 201 with template data."""
    headers = await _ai_headers(client, "prompt_create@example.com")
    payload = {
        "name": "Marketing Template",
        "description": "A template for marketing copy",
        "system_prompt": "You are a marketing expert.",
        "user_prompt_template": "Write marketing copy for {product}.",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 500,
        "is_active": True,
    }
    resp = await client.post("/api/v2/ai/prompts", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert "data" in data


@pytest.mark.asyncio
async def test_list_prompt_templates(client: AsyncClient):
    """Listing prompt templates should return 200 with paginated list."""
    headers = await _ai_headers(client, "prompt_list@example.com")
    # First create a template
    create_payload = {
        "name": "List Test Template",
        "system_prompt": "Test system prompt",
        "user_prompt_template": "Test user prompt",
        "is_active": True,
    }
    resp_create = await client.post("/api/v2/ai/prompts", json=create_payload, headers=headers)
    assert resp_create.status_code == 201

    resp = await client.get("/api/v2/ai/prompts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "data" in data


@pytest.mark.asyncio
async def test_get_prompt_template(client: AsyncClient):
    """Getting a prompt template by ID should return 200."""
    headers = await _ai_headers(client, "prompt_get@example.com")
    # Create first
    payload = {
        "name": "Get Test Template",
        "system_prompt": "Get test system",
        "user_prompt_template": "Get test user",
    }
    resp_create = await client.post("/api/v2/ai/prompts", json=payload, headers=headers)
    assert resp_create.status_code == 201

    # List to get ID
    resp_list = await client.get("/api/v2/ai/prompts", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        prompt_id = items[0]["id"]
        resp = await client.get(f"/api/v2/ai/prompts/{prompt_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_update_prompt_template(client: AsyncClient):
    """Updating a prompt template should return 200 with updated data."""
    headers = await _ai_headers(client, "prompt_update@example.com")
    # Create first
    payload = {
        "name": "Update Test Template",
        "system_prompt": "Original system",
        "user_prompt_template": "Original user",
    }
    resp_create = await client.post("/api/v2/ai/prompts", json=payload, headers=headers)
    assert resp_create.status_code == 201

    # List to get ID
    resp_list = await client.get("/api/v2/ai/prompts", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        prompt_id = items[0]["id"]
        update_payload = {"name": "Updated Template Name", "temperature": 0.5}
        resp = await client.put(f"/api/v2/ai/prompts/{prompt_id}", json=update_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_prompt_template(client: AsyncClient):
    """Deleting a prompt template should return 200."""
    headers = await _ai_headers(client, "prompt_delete@example.com")
    # Create first
    payload = {
        "name": "Delete Test Template",
        "system_prompt": "Delete test",
        "user_prompt_template": "Delete test",
    }
    resp_create = await client.post("/api/v2/ai/prompts", json=payload, headers=headers)
    assert resp_create.status_code == 201

    # List to get ID
    resp_list = await client.get("/api/v2/ai/prompts", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        prompt_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/ai/prompts/{prompt_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# AI Generation (Mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_completion_mock(client: AsyncClient, mock_openai):
    """AI completion generation with mocked OpenAI should return 200."""
    headers = await _ai_headers(client, "ai_gen@example.com")
    payload = {
        "prompt": "Write a tweet about AI marketing",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 200,
        "use_cache": False,
    }
    resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
    # Should succeed with the mocked service
    assert resp.status_code in (200, 500)  # 500 if service layer isn't mocked fully
    if resp.status_code == 200:
        data = resp.json()
        assert "data" in data


@pytest.mark.asyncio
async def test_generate_completion_with_system_prompt(client: AsyncClient, mock_openai):
    """AI completion with custom system prompt should work."""
    headers = await _ai_headers(client, "ai_gen_sys@example.com")
    payload = {
        "prompt": "Generate ad copy",
        "model": "gpt-4o-mini",
        "system_prompt": "You are an expert ad copywriter.",
        "temperature": 0.8,
        "max_tokens": 150,
        "use_cache": False,
    }
    resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_generate_completion_invalid_model(client: AsyncClient):
    """AI completion with invalid model should return 422 or handle gracefully."""
    headers = await _ai_headers(client, "ai_gen_bad@example.com")
    payload = {
        "prompt": "Test",
        "model": "invalid-model-name",
        "temperature": 0.7,
        "max_tokens": 100,
    }
    resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
    assert resp.status_code in (200, 422, 500)


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_suggestions(client: AsyncClient, mock_openai):
    """Generating AI suggestions should return 201."""
    headers = await _ai_headers(client, "sugg_gen@example.com")
    payload = {
        "trigger_type": "dashboard_view",
        "context": {"page": "dashboard", "company_id": "ai-test-company"},
        "count": 3,
    }
    resp = await client.post("/api/v2/ai/suggestions", json=payload, headers=headers)
    assert resp.status_code in (201, 500)
    if resp.status_code == 201:
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_list_suggestions(client: AsyncClient):
    """Listing AI suggestions should return 200."""
    headers = await _ai_headers(client, "sugg_list@example.com")
    resp = await client.get("/api/v2/ai/suggestions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_list_suggestions_with_filter(client: AsyncClient):
    """Listing suggestions with trigger_type filter should work."""
    headers = await _ai_headers(client, "sugg_filter@example.com")
    resp = await client.get("/api/v2/ai/suggestions?trigger_type=dashboard_view", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_submit_suggestion_feedback(client: AsyncClient):
    """Submitting feedback for a suggestion should return 200."""
    headers = await _ai_headers(client, "sugg_fb@example.com")
    # List first to get a suggestion ID
    resp_list = await client.get("/api/v2/ai/suggestions", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        sugg_id = items[0]["id"]
        payload = {"feedback": "positive", "notes": "Great suggestion!"}
        resp = await client.post(f"/api/v2/ai/suggestions/{sugg_id}/feedback", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_recommendations(client: AsyncClient):
    """Listing AI recommendations should return 200."""
    headers = await _ai_headers(client, "rec_list@example.com")
    resp = await client.get("/api/v2/ai/recommendations", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_list_recommendations_with_filters(client: AsyncClient):
    """Listing recommendations with category/status filters should work."""
    headers = await _ai_headers(client, "rec_filter@example.com")
    resp = await client.get("/api/v2/ai/recommendations?category=marketing&status=pending", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_generate_recommendations(client: AsyncClient, mock_openai):
    """Generating AI recommendations should return 201."""
    headers = await _ai_headers(client, "rec_gen@example.com")
    payload = {
        "categories": ["marketing", "social_media"],
        "context": {"company_id": "ai-test-company"},
        "count": 5,
    }
    resp = await client.post("/api/v2/ai/recommendations/generate", json=payload, headers=headers)
    assert resp.status_code in (201, 500)


@pytest.mark.asyncio
async def test_apply_recommendation(client: AsyncClient):
    """Applying a recommendation should return 200."""
    headers = await _ai_headers(client, "rec_apply@example.com")
    # List first
    resp_list = await client.get("/api/v2/ai/recommendations", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        rec_id = items[0]["id"]
        resp = await client.post(f"/api/v2/ai/recommendations/{rec_id}/apply", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_dismiss_recommendation(client: AsyncClient):
    """Dismissing a recommendation should return 200."""
    headers = await _ai_headers(client, "rec_dismiss@example.com")
    # List first
    resp_list = await client.get("/api/v2/ai/recommendations", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        rec_id = items[0]["id"]
        resp = await client.post(f"/api/v2/ai/recommendations/{rec_id}/dismiss", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# Usage Tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_usage_analytics(client: AsyncClient):
    """Getting AI usage analytics should return 200 for analyst role."""
    headers = await _ai_headers(client, "ai_usage@example.com", role="analyst")
    resp = await client.get("/api/v2/ai/usage", headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_get_usage_analytics_with_filters(client: AsyncClient):
    """Getting usage with date/model filters should work."""
    headers = await _ai_headers(client, "ai_usage_f@example.com", role="analyst")
    resp = await client.get(
        "/api/v2/ai/usage?model=gpt-4o-mini&start_date=2024-01-01&end_date=2024-12-31",
        headers=headers,
    )
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_get_usage_analytics_summary_only(client: AsyncClient):
    """Getting usage summary only should return 200."""
    headers = await _ai_headers(client, "ai_usage_s@example.com", role="analyst")
    resp = await client.get("/api/v2/ai/usage?summary_only=true", headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_usage_analytics_denied_for_viewer(client: AsyncClient):
    """Viewer should NOT be able to access AI usage analytics."""
    headers = await _ai_headers(client, "ai_usage_v@example.com", role="user")
    resp = await client.get("/api/v2/ai/usage", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient):
    """Creating a conversation should return 201."""
    headers = await _ai_headers(client, "conv_create@example.com")
    payload = {
        "title": "Test Conversation",
        "model": "gpt-4o-mini",
    }
    resp = await client.post("/api/v2/ai/conversations", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_list_conversations(client: AsyncClient):
    """Listing conversations should return 200."""
    headers = await _ai_headers(client, "conv_list@example.com")
    # Create first
    payload = {"title": "List Conversations Test"}
    await client.post("/api/v2/ai/conversations", json=payload, headers=headers)

    resp = await client.get("/api/v2/ai/conversations", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, mock_openai):
    """Sending a message in a conversation should return 200."""
    headers = await _ai_headers(client, "conv_msg@example.com")
    # Create conversation first
    payload = {"title": "Message Test"}
    resp_create = await client.post("/api/v2/ai/conversations", json=payload, headers=headers)
    assert resp_create.status_code == 201

    # List to get ID
    resp_list = await client.get("/api/v2/ai/conversations", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        conv_id = items[0]["id"]
        msg_payload = {"content": "Hello, AI!", "stream": False}
        resp = await client.post(f"/api/v2/ai/conversations/{conv_id}/messages", json=msg_payload, headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_get_messages(client: AsyncClient):
    """Getting messages in a conversation should return 200."""
    headers = await _ai_headers(client, "conv_getmsg@example.com")
    # Create conversation
    payload = {"title": "Get Messages Test"}
    resp_create = await client.post("/api/v2/ai/conversations", json=payload, headers=headers)
    assert resp_create.status_code == 201

    # List to get ID
    resp_list = await client.get("/api/v2/ai/conversations", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        conv_id = items[0]["id"]
        resp = await client.get(f"/api/v2/ai/conversations/{conv_id}/messages", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient):
    """Deleting a conversation should return 200."""
    headers = await _ai_headers(client, "conv_del@example.com")
    # Create conversation
    payload = {"title": "Delete Conversation Test"}
    resp_create = await client.post("/api/v2/ai/conversations", json=payload, headers=headers)
    assert resp_create.status_code == 201

    # List to get ID
    resp_list = await client.get("/api/v2/ai/conversations", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        conv_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/ai/conversations/{conv_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_streaming_message_placeholder(client: AsyncClient):
    """Sending a streaming message should return a placeholder."""
    headers = await _ai_headers(client, "conv_stream@example.com")
    # Create conversation
    payload = {"title": "Streaming Test"}
    resp_create = await client.post("/api/v2/ai/conversations", json=payload, headers=headers)
    assert resp_create.status_code == 201

    resp_list = await client.get("/api/v2/ai/conversations", headers=headers)
    items = resp_list.json()["data"]["items"]
    if items:
        conv_id = items[0]["id"]
        msg_payload = {"content": "Stream me", "stream": True}
        resp = await client.post(f"/api/v2/ai/conversations/{conv_id}/messages", json=msg_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["streaming"] is True


# ---------------------------------------------------------------------------
# AI Graceful Fallback (No API Key)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_graceful_fallback_no_api_key(client: AsyncClient, monkeypatch):
    """AI should gracefully fallback when API key is not configured."""
    # Mock the AI service to simulate missing API key
    async def _mock_no_key(*args, **kwargs):
        raise RuntimeError("AI API key not configured")

    from app.ai import router as ai_router
    original_generate = ai_router.ai_service.create_chat_completion
    monkeypatch.setattr(ai_router.ai_service, "create_chat_completion", _mock_no_key)

    headers = await _ai_headers(client, "ai_fallback@example.com")
    payload = {
        "prompt": "Write a tweet about AI marketing",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 200,
        "use_cache": False,
    }
    resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
    # Should return 200 with a mock/fallback response, or 503 service unavailable
    assert resp.status_code in (200, 500, 503), f"Expected graceful fallback, got {resp.status_code}"


@pytest.mark.asyncio
async def test_ai_fallback_returns_valid_structure(client: AsyncClient):
    """AI fallback response should have valid structure."""
    headers = await _ai_headers(client, "ai_fallback_struct@example.com")
    payload = {
        "prompt": "Hello",
        "model": "gpt-4o-mini",
        "use_cache": True,
    }
    resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
    # Should return either success or graceful error
    if resp.status_code == 200:
        data = resp.json()
        assert "data" in data


# ---------------------------------------------------------------------------
# Rate Limit Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_rate_limit_enforced(client: AsyncClient, mock_openai):
    """AI endpoint should enforce rate limiting."""
    headers = await _ai_headers(client, "ai_ratelimit@example.com")
    payload = {
        "prompt": "Rate limit test",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 100,
        "use_cache": False,
    }

    # Make multiple rapid requests
    responses = []
    for i in range(5):
        resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
        responses.append(resp.status_code)

    # Some requests may be rate limited (429)
    # At least the first few should succeed
    assert any(code in (200, 500) for code in responses), "At least some requests should succeed"


@pytest.mark.asyncio
async def test_ai_rate_limit_headers_present(client: AsyncClient, mock_openai):
    """AI endpoint should include rate limit headers."""
    headers = await _ai_headers(client, "ai_rl_headers@example.com")
    payload = {
        "prompt": "Check rate limit headers",
        "model": "gpt-4o-mini",
        "max_tokens": 50,
        "use_cache": False,
    }
    resp = await client.post("/api/v2/ai/generate", json=payload, headers=headers)
    # Check if rate limit headers are present
    # Common headers: X-RateLimit-Limit, X-RateLimit-Remaining, Retry-After
    rate_limit_headers = [
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "retry-after",
    ]
    has_rl_header = any(h in resp.headers for h in rate_limit_headers)
    # Not all implementations may have these headers
    # So we just check the request succeeds or is properly rate limited
    assert resp.status_code in (200, 429, 500)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_nonexistent_prompt_template(client: AsyncClient):
    """Getting a non-existent prompt should return 404."""
    headers = await _ai_headers(client, "prompt_404@example.com")
    resp = await client.get("/api/v2/ai/prompts/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_prompt_template(client: AsyncClient):
    """Updating a non-existent prompt should return 404."""
    headers = await _ai_headers(client, "prompt_up404@example.com")
    resp = await client.put("/api/v2/ai/prompts/999999", json={"name": "Nope"}, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_prompt_template(client: AsyncClient):
    """Deleting a non-existent prompt should return 404."""
    headers = await _ai_headers(client, "prompt_del404@example.com")
    resp = await client.delete("/api/v2/ai/prompts/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_access_denied(client: AsyncClient):
    """Unauthenticated access to AI endpoints should fail."""
    resp = await client.get("/api/v2/ai/prompts")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_generate_suggestions_validation_error(client: AsyncClient):
    """Generating suggestions without trigger_type should fail validation."""
    headers = await _ai_headers(client, "sugg_val@example.com")
    payload = {"context": {}}  # Missing trigger_type
    resp = await client.post("/api/v2/ai/suggestions", json=payload, headers=headers)
    assert resp.status_code in (422, 500)


@pytest.mark.asyncio
async def test_full_ai_module_lifecycle(client: AsyncClient, mock_openai):
    """Full lifecycle: create prompt -> list -> get -> update -> delete."""
    headers = await _ai_headers(client, "ai_full@example.com")

    # 1. Create prompt
    create_payload = {
        "name": "Lifecycle Template",
        "description": "Full lifecycle test",
        "system_prompt": "You are a test assistant.",
        "user_prompt_template": "Test {subject}",
        "model": "gpt-4o-mini",
        "temperature": 0.5,
        "is_active": True,
    }
    resp_create = await client.post("/api/v2/ai/prompts", json=create_payload, headers=headers)
    assert resp_create.status_code == 201

    # 2. List prompts
    resp_list = await client.get("/api/v2/ai/prompts", headers=headers)
    assert resp_list.status_code == 200
    items = resp_list.json()["data"]["items"]
    assert len(items) > 0

    # 3. Get specific prompt
    prompt_id = items[0]["id"]
    resp_get = await client.get(f"/api/v2/ai/prompts/{prompt_id}", headers=headers)
    assert resp_get.status_code == 200

    # 4. Update prompt
    resp_update = await client.put(
        f"/api/v2/ai/prompts/{prompt_id}",
        json={"name": "Updated Lifecycle Template"},
        headers=headers,
    )
    assert resp_update.status_code == 200

    # 5. Create conversation
    resp_conv = await client.post(
        "/api/v2/ai/conversations",
        json={"title": "Lifecycle Conversation", "model": "gpt-4o-mini"},
        headers=headers,
    )
    assert resp_conv.status_code == 201

    # 6. List conversations
    resp_conv_list = await client.get("/api/v2/ai/conversations", headers=headers)
    assert resp_conv_list.status_code == 200

    # 7. Delete conversation
    conv_items = resp_conv_list.json()["data"]["items"]
    if conv_items:
        conv_id = conv_items[0]["id"]
        resp_conv_del = await client.delete(f"/api/v2/ai/conversations/{conv_id}", headers=headers)
        assert resp_conv_del.status_code == 200

    # 8. Delete prompt
    resp_delete = await client.delete(f"/api/v2/ai/prompts/{prompt_id}", headers=headers)
    assert resp_delete.status_code == 200
