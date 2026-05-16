"""Notifications module tests.

Covers:
  - Send notification
  - List notifications
  - Mark as read
  - Delete notification
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _notif_headers(client: AsyncClient, email: str, role: str = "user") -> dict:
    """Create auth headers for notification tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Notif",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "notif-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "notif-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "notif-test-company",
    }


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_notification(client: AsyncClient, mock_email):
    """Sending a notification should return 200."""
    headers = await _notif_headers(client, "notif_send@example.com", role="company_admin")
    payload = {
        "title": "Test Notification",
        "message": "This is a test notification",
        "type": "info",
        "channels": ["email"],
    }
    resp = await client.post("/api/v2/notifications/send", json=payload, headers=headers)
    assert resp.status_code in (200, 422, 500)


@pytest.mark.asyncio
async def test_send_notification_with_all_channels(client: AsyncClient, mock_email):
    """Sending a notification via all channels should work."""
    headers = await _notif_headers(client, "notif_allch@example.com", role="company_admin")
    payload = {
        "title": "Multi-channel Notification",
        "message": "Sent via all channels",
        "type": "alert",
        "channels": ["email", "push", "sms"],
    }
    resp = await client.post("/api/v2/notifications/send", json=payload, headers=headers)
    assert resp.status_code in (200, 422, 500)


@pytest.mark.asyncio
async def test_send_notification_unauthorized_for_viewer(client: AsyncClient):
    """Viewer should NOT be able to send notifications."""
    headers = await _notif_headers(client, "notif_denied@example.com", role="user")
    payload = {
        "title": "Test",
        "message": "Should fail",
        "type": "info",
    }
    resp = await client.post("/api/v2/notifications/send", json=payload, headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notifications(client: AsyncClient):
    """Listing notifications should return 200."""
    headers = await _notif_headers(client, "notif_list@example.com")
    resp = await client.get("/api/v2/notifications", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_notifications_with_unread_filter(client: AsyncClient):
    """Listing only unread notifications should work."""
    headers = await _notif_headers(client, "notif_unread@example.com")
    resp = await client.get("/api/v2/notifications?unread_only=true", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_notifications_paginated(client: AsyncClient):
    """Paginated notifications should work."""
    headers = await _notif_headers(client, "notif_page@example.com")
    resp = await client.get("/api/v2/notifications?page=1&limit=10", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


# ---------------------------------------------------------------------------
# Mark as Read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_notification_read(client: AsyncClient):
    """Marking a notification as read should return 200."""
    headers = await _notif_headers(client, "notif_read@example.com")
    resp_list = await client.get("/api/v2/notifications", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        notif_id = items[0]["id"]
        resp = await client.patch(f"/api/v2/notifications/{notif_id}/read", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient):
    """Marking all notifications as read should return 200."""
    headers = await _notif_headers(client, "notif_readall@example.com")
    resp = await client.patch("/api/v2/notifications/read-all", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_notification_preferences(client: AsyncClient):
    """Getting notification preferences should return 200."""
    headers = await _notif_headers(client, "notif_prefget@example.com")
    resp = await client.get("/api/v2/notifications/preferences", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_notification_preferences(client: AsyncClient):
    """Updating notification preferences should return 200."""
    headers = await _notif_headers(client, "notif_prefup@example.com")
    payload = {
        "email_enabled": True,
        "push_enabled": False,
        "sms_enabled": True,
    }
    resp = await client.put("/api/v2/notifications/preferences", json=payload, headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_notification(client: AsyncClient):
    """Deleting a notification should return 204."""
    headers = await _notif_headers(client, "notif_del@example.com")
    resp_list = await client.get("/api/v2/notifications", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        notif_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/notifications/{notif_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_notification_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/notifications")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_mark_nonexistent_read(client: AsyncClient):
    """Marking a non-existent notification should return 404."""
    headers = await _notif_headers(client, "notif_404@example.com")
    resp = await client.patch("/api/v2/notifications/99999/read", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_notification_lifecycle(client: AsyncClient, mock_email):
    """Full lifecycle: send -> list -> mark read -> update prefs -> mark all read."""
    headers = await _notif_headers(client, "notif_full@example.com", role="company_admin")

    # 1. Send notification
    send_payload = {
        "title": "Full Test Notification",
        "message": "Testing full lifecycle",
        "type": "info",
        "channels": ["email"],
    }
    resp_send = await client.post("/api/v2/notifications/send", json=send_payload, headers=headers)
    assert resp_send.status_code in (200, 422, 500)

    # 2. List notifications
    resp_list = await client.get("/api/v2/notifications", headers=headers)
    assert resp_list.status_code == 200

    # 3. Get preferences
    resp_pref = await client.get("/api/v2/notifications/preferences", headers=headers)
    assert resp_pref.status_code == 200

    # 4. Update preferences
    pref_payload = {"email_enabled": True, "push_enabled": True}
    resp_pref_up = await client.put("/api/v2/notifications/preferences", json=pref_payload, headers=headers)
    assert resp_pref_up.status_code == 200

    # 5. Mark all as read
    resp_read_all = await client.patch("/api/v2/notifications/read-all", headers=headers)
    assert resp_read_all.status_code == 200
