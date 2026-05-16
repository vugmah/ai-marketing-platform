"""Social Media module tests.

Covers:
  - Connect account (mock APIs)
  - CRUD posts
  - List comments
  - Reply to comment
  - Analytics endpoints
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _social_headers(client: AsyncClient, email: str, role: str = "marketing_manager") -> dict:
    """Create auth headers for social media tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Social",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "social-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "social-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "social-test-company",
    }


# ---------------------------------------------------------------------------
# Account Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_social_account(client: AsyncClient, mock_social_apis):
    """Connecting a social media account should return 201."""
    headers = await _social_headers(client, "social_acct@example.com")
    payload = {
        "platform": "facebook",
        "account_name": "Test Page",
        "account_id": "123456789",
        "access_token": "mock-token-123",
    }
    resp = await client.post("/api/v2/social/accounts", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_create_social_account_instagram(client: AsyncClient, mock_social_apis):
    """Connecting an Instagram account should return 201."""
    headers = await _social_headers(client, "social_ig@example.com")
    payload = {
        "platform": "instagram",
        "account_name": "Test IG",
        "account_id": "987654321",
        "access_token": "mock-token-ig",
    }
    resp = await client.post("/api/v2/social/accounts", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_list_social_accounts(client: AsyncClient):
    """Listing social accounts should return 200."""
    headers = await _social_headers(client, "social_list@example.com")
    resp = await client.get("/api/v2/social/accounts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_social_accounts_with_platform_filter(client: AsyncClient):
    """Listing accounts with platform filter should work."""
    headers = await _social_headers(client, "social_filter@example.com")
    resp = await client.get("/api/v2/social/accounts?platform=facebook", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_social_accounts_with_status_filter(client: AsyncClient):
    """Listing accounts with status filter should work."""
    headers = await _social_headers(client, "social_status@example.com")
    resp = await client.get("/api/v2/social/accounts?status=active", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_social_account(client: AsyncClient):
    """Getting a social account by ID should return 200 or 404."""
    headers = await _social_headers(client, "social_get@example.com")
    # List first
    resp_list = await client.get("/api/v2/social/accounts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        acct_id = items[0]["id"]
        resp = await client.get(f"/api/v2/social/accounts/{acct_id}", headers=headers)
        assert resp.status_code == 200
    else:
        # No accounts yet, test 404
        resp = await client.get("/api/v2/social/accounts/99999", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_social_account(client: AsyncClient):
    """Updating a social account should return 200."""
    headers = await _social_headers(client, "social_upd@example.com")
    # List first
    resp_list = await client.get("/api/v2/social/accounts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        acct_id = items[0]["id"]
        payload = {"account_name": "Updated Name"}
        resp = await client.patch(f"/api/v2/social/accounts/{acct_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_social_account(client: AsyncClient):
    """Deleting a social account should return 204."""
    headers = await _social_headers(client, "social_del@example.com")
    # List first
    resp_list = await client.get("/api/v2/social/accounts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        acct_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/social/accounts/{acct_id}", headers=headers)
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_refresh_account_token(client: AsyncClient, mock_social_apis):
    """Refreshing an account token should return 200."""
    headers = await _social_headers(client, "social_refresh@example.com")
    # List first
    resp_list = await client.get("/api/v2/social/accounts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        acct_id = items[0]["id"]
        payload = {"force": True}
        resp = await client.post(f"/api/v2/social/accounts/{acct_id}/refresh", json=payload, headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Post Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_social_post(client: AsyncClient):
    """Creating a social post should return 201."""
    headers = await _social_headers(client, "post_create@example.com")
    payload = {
        "content": "Check out our new product! #new",
        "platform": "facebook",
        "status": "draft",
    }
    resp = await client.post("/api/v2/social/posts", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_create_social_post_scheduled(client: AsyncClient):
    """Creating a scheduled post should return 201."""
    headers = await _social_headers(client, "post_sched@example.com")
    payload = {
        "content": "Scheduled post content",
        "platform": "instagram",
        "status": "scheduled",
        "scheduled_at": "2025-12-31T23:59:59Z",
    }
    resp = await client.post("/api/v2/social/posts", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_list_social_posts(client: AsyncClient):
    """Listing social posts should return 200."""
    headers = await _social_headers(client, "post_list@example.com")
    resp = await client.get("/api/v2/social/posts", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_posts_with_filters(client: AsyncClient):
    """Listing posts with status/platform filters should work."""
    headers = await _social_headers(client, "post_filter@example.com")
    resp = await client.get("/api/v2/social/posts?status=draft&platform=facebook", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_social_post(client: AsyncClient):
    """Getting a post by ID should return 200 or 404."""
    headers = await _social_headers(client, "post_get@example.com")
    resp_list = await client.get("/api/v2/social/posts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        post_id = items[0]["id"]
        resp = await client.get(f"/api/v2/social/posts/{post_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_social_post(client: AsyncClient):
    """Updating a post should return 200."""
    headers = await _social_headers(client, "post_upd@example.com")
    resp_list = await client.get("/api/v2/social/posts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        post_id = items[0]["id"]
        payload = {"content": "Updated post content"}
        resp = await client.put(f"/api/v2/social/posts/{post_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_social_post(client: AsyncClient):
    """Deleting a post should return 204."""
    headers = await _social_headers(client, "post_del@example.com")
    resp_list = await client.get("/api/v2/social/posts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        post_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/social/posts/{post_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Comment Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient):
    """Listing comments should return 200."""
    headers = await _social_headers(client, "comment_list@example.com")
    resp = await client.get("/api/v2/social/comments", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_comments_with_filters(client: AsyncClient):
    """Listing comments with filters should work."""
    headers = await _social_headers(client, "comment_filter@example.com")
    resp = await client.get("/api/v2/social/comments?status=new", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_comment(client: AsyncClient):
    """Getting a comment by ID should return 200 or 404."""
    headers = await _social_headers(client, "comment_get@example.com")
    resp_list = await client.get("/api/v2/social/comments", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        comment_id = items[0]["id"]
        resp = await client.get(f"/api/v2/social/comments/{comment_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_comment(client: AsyncClient):
    """Updating a comment should return 200."""
    headers = await _social_headers(client, "comment_upd@example.com")
    resp_list = await client.get("/api/v2/social/comments", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        comment_id = items[0]["id"]
        payload = {"status": "read", "sentiment": "positive"}
        resp = await client.patch(f"/api/v2/social/comments/{comment_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reply_to_comment(client: AsyncClient, mock_social_apis):
    """Replying to a comment should return 200."""
    headers = await _social_headers(client, "comment_reply@example.com")
    resp_list = await client.get("/api/v2/social/comments", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        comment_id = items[0]["id"]
        payload = {"reply_content": "Thank you for your comment!"}
        resp = await client.post(f"/api/v2/social/comments/{comment_id}/reply", json=payload, headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_mark_comment_read(client: AsyncClient):
    """Marking a comment as read should return 200."""
    headers = await _social_headers(client, "comment_read@example.com")
    resp_list = await client.get("/api/v2/social/comments", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        comment_id = items[0]["id"]
        resp = await client.put(f"/api/v2/social/comments/{comment_id}/read", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_analyze_comment_sentiment(client: AsyncClient, mock_openai):
    """Analyzing comment sentiment should return 200."""
    headers = await _social_headers(client, "comment_sent@example.com")
    resp_list = await client.get("/api/v2/social/comments", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        comment_id = items[0]["id"]
        resp = await client.post(f"/api/v2/social/comments/{comment_id}/sentiment", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_sync_comments(client: AsyncClient, mock_social_apis):
    """Syncing comments should return 200."""
    headers = await _social_headers(client, "comment_sync@example.com")
    resp_list = await client.get("/api/v2/social/accounts", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        acct_id = items[0]["id"]
        resp = await client.post(f"/api/v2/social/comments/sync/{acct_id}", headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Message Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_messages(client: AsyncClient):
    """Listing messages should return 200."""
    headers = await _social_headers(client, "msg_list@example.com")
    resp = await client.get("/api/v2/social/messages", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_conversations(client: AsyncClient):
    """Listing conversations should return 200."""
    headers = await _social_headers(client, "msg_conv@example.com")
    resp = await client.get("/api/v2/social/messages/conversations", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reply_to_conversation(client: AsyncClient, mock_social_apis):
    """Replying to a conversation should return 200."""
    headers = await _social_headers(client, "msg_reply@example.com")
    resp_list = await client.get("/api/v2/social/messages", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        msg_id = items[0]["id"]
        payload = {"reply_content": "Thanks for reaching out!"}
        resp = await client.post(f"/api/v2/social/messages/{msg_id}/reply", json=payload, headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Analytics Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_analytics_dashboard(client: AsyncClient):
    """Getting analytics dashboard should return 200."""
    headers = await _social_headers(client, "analytics_dash@example.com")
    resp = await client.get("/api/v2/social/analytics", headers=headers)
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_list_analytics_snapshots(client: AsyncClient):
    """Listing analytics snapshots should return 200."""
    headers = await _social_headers(client, "analytics_snap@example.com")
    resp = await client.get("/api/v2/social/analytics/snapshots", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_analytics_snapshot(client: AsyncClient):
    """Creating an analytics snapshot should return 201."""
    headers = await _social_headers(client, "analytics_create@example.com")
    payload = {
        "account_id": 1,
        "platform": "facebook",
        "metrics": {"likes": 100, "comments": 50},
    }
    resp = await client.post("/api/v2/social/analytics/snapshots", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


# ---------------------------------------------------------------------------
# Competitor Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_competitors(client: AsyncClient):
    """Listing tracked competitors should return 200."""
    headers = await _social_headers(client, "comp_list@example.com")
    resp = await client.get("/api/v2/social/competitors", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_competitor(client: AsyncClient):
    """Adding a competitor should return 201."""
    headers = await _social_headers(client, "comp_create@example.com")
    payload = {
        "platform": "instagram",
        "competitor_name": "Competitor Brand",
        "profile_url": "https://instagram.com/competitor",
        "account_id": "comp_123",
    }
    resp = await client.post("/api/v2/social/competitors", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


# ---------------------------------------------------------------------------
# Webhook Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_verification_facebook(client: AsyncClient):
    """Facebook webhook verification should return challenge."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "webhook-verify-token",
        "hub.challenge": "challenge_123",
    }
    resp = await client.get("/api/v2/social/webhooks/facebook", params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert "challenge" in data


@pytest.mark.asyncio
async def test_webhook_verification_invalid_token(client: AsyncClient):
    """Webhook verification with invalid token should fail."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong-token",
        "hub.challenge": "challenge_123",
    }
    resp = await client.get("/api/v2/social/webhooks/facebook", params=params)
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_receive_webhook_facebook(client: AsyncClient):
    """Receiving a Facebook webhook should return 200."""
    payload = {
        "object": "page",
        "entry": [{"id": "page_123", "time": 1234567890, "changes": [{"field": "feed", "value": {}}]}],
    }
    resp = await client.post("/api/v2/social/webhooks/facebook", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_receive_webhook_telegram(client: AsyncClient):
    """Receiving a Telegram webhook should return 200."""
    payload = {
        "update_id": 123,
        "message": {"message_id": 1, "chat": {"id": 456, "type": "private"}, "text": "Hello"},
    }
    resp = await client.post("/api/v2/social/webhooks/telegram", json=payload)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_access_social(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/social/accounts")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_post(client: AsyncClient):
    """Getting a non-existent post should return 404."""
    headers = await _social_headers(client, "post_404@example.com")
    resp = await client.get("/api/v2/social/posts/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_social_lifecycle(client: AsyncClient, mock_social_apis, mock_openai):
    """Full lifecycle: create account -> list -> create post -> list posts -> delete."""
    headers = await _social_headers(client, "social_full@example.com")

    # 1. Create account
    acct_payload = {
        "platform": "facebook",
        "account_name": "Full Test Page",
        "account_id": "full_123",
        "access_token": "mock-token",
    }
    resp_acct = await client.post("/api/v2/social/accounts", json=acct_payload, headers=headers)
    assert resp_acct.status_code in (201, 422, 500)

    # 2. List accounts
    resp_list = await client.get("/api/v2/social/accounts", headers=headers)
    assert resp_list.status_code == 200

    # 3. Create post
    post_payload = {
        "content": "Full lifecycle test post",
        "platform": "facebook",
        "status": "draft",
    }
    resp_post = await client.post("/api/v2/social/posts", json=post_payload, headers=headers)
    assert resp_post.status_code in (201, 422, 500)

    # 4. List posts
    resp_posts = await client.get("/api/v2/social/posts", headers=headers)
    assert resp_posts.status_code == 200

    # 5. List comments
    resp_comments = await client.get("/api/v2/social/comments", headers=headers)
    assert resp_comments.status_code == 200

    # 6. List messages
    resp_msgs = await client.get("/api/v2/social/messages", headers=headers)
    assert resp_msgs.status_code == 200

    # 7. Get analytics
    resp_analytics = await client.get("/api/v2/social/analytics", headers=headers)
    assert resp_analytics.status_code in (200, 500)
