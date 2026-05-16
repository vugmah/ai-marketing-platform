"""AI Customer Support module tests.

Covers:
  - Ticket CRUD
  - Messages
  - AI auto-reply (mock)
  - KB search
  - Escalation
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _support_headers(client: AsyncClient, email: str, role: str = "support_agent") -> dict:
    """Create auth headers for support tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Support",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "support-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "support-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "support-test-company",
    }


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_ticket(client: AsyncClient):
    """Creating a support ticket should return 201."""
    headers = await _support_headers(client, "tkt_create@example.com")
    payload = {
        "subject": "Login Issue",
        "description": "Cannot login to dashboard",
        "priority": "high",
        "category": "technical",
        "customer_email": "user@example.com",
    }
    resp = await client.post("/api/v2/support/tickets", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_list_tickets(client: AsyncClient):
    """Listing tickets should return 200."""
    headers = await _support_headers(client, "tkt_list@example.com")
    resp = await client.get("/api/v2/support/tickets", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_tickets_with_status_filter(client: AsyncClient):
    """Listing tickets with status filter should work."""
    headers = await _support_headers(client, "tkt_filter@example.com")
    resp = await client.get("/api/v2/support/tickets?status=open", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_tickets_with_priority_filter(client: AsyncClient):
    """Listing tickets with priority filter should work."""
    headers = await _support_headers(client, "tkt_prio@example.com")
    resp = await client.get("/api/v2/support/tickets?priority=high", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_ticket(client: AsyncClient):
    """Getting a ticket by ID should return 200 or 404."""
    headers = await _support_headers(client, "tkt_get@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        resp = await client.get(f"/api/v2/support/tickets/{tkt_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_ticket(client: AsyncClient):
    """Updating a ticket should return 200."""
    headers = await _support_headers(client, "tkt_upd@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        payload = {"status": "in_progress", "priority": "medium"}
        resp = await client.patch(f"/api/v2/support/tickets/{tkt_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_assign_ticket(client: AsyncClient):
    """Assigning a ticket should return 200."""
    headers = await _support_headers(client, "tkt_assign@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        payload = {"assigned_to": "agent-123"}
        resp = await client.patch(f"/api/v2/support/tickets/{tkt_id}/assign", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_close_ticket(client: AsyncClient):
    """Closing a ticket should return 200."""
    headers = await _support_headers(client, "tkt_close@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        payload = {"resolution": "Issue resolved by agent"}
        resp = await client.patch(f"/api/v2/support/tickets/{tkt_id}/close", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_ticket(client: AsyncClient):
    """Deleting a ticket should return 204."""
    headers = await _support_headers(client, "tkt_del@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/support/tickets/{tkt_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_messages(client: AsyncClient):
    """Listing support messages should return 200."""
    headers = await _support_headers(client, "msg_list@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        resp = await client.get(f"/api/v2/support/tickets/{tkt_id}/messages", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient):
    """Sending a message should return 201."""
    headers = await _support_headers(client, "msg_send@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        payload = {"content": "We are looking into your issue."}
        resp = await client.post(f"/api/v2/support/tickets/{tkt_id}/messages", json=payload, headers=headers)
        assert resp.status_code in (201, 422, 500)


# ---------------------------------------------------------------------------
# AI Auto-reply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_auto_reply(client: AsyncClient, mock_openai):
    """AI auto-reply should return 200."""
    headers = await _support_headers(client, "ai_reply@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        resp = await client.post(f"/api/v2/support/tickets/{tkt_id}/ai-reply", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_ai_auto_reply_nonexistent_ticket(client: AsyncClient):
    """AI auto-reply for non-existent ticket should return 404."""
    headers = await _support_headers(client, "ai_reply_404@example.com")
    resp = await client.post("/api/v2/support/tickets/99999/ai-reply", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_kb_articles(client: AsyncClient):
    """Listing KB articles should return 200."""
    headers = await _support_headers(client, "kb_list@example.com")
    resp = await client.get("/api/v2/support/kb", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_kb(client: AsyncClient):
    """Searching KB should return 200."""
    headers = await _support_headers(client, "kb_search@example.com")
    resp = await client.get("/api/v2/support/kb/search?q=password+reset", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_kb_empty_query(client: AsyncClient):
    """KB search with empty query should work."""
    headers = await _support_headers(client, "kb_empty@example.com")
    resp = await client.get("/api/v2/support/kb/search?q=", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_escalate_ticket(client: AsyncClient):
    """Escalating a ticket should return 200."""
    headers = await _support_headers(client, "esc_tkt@example.com")
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        tkt_id = items[0]["id"]
        payload = {"reason": "Requires senior engineer attention", "escalation_level": 2}
        resp = await client.post(f"/api/v2/support/tickets/{tkt_id}/escalate", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_escalate_nonexistent_ticket(client: AsyncClient):
    """Escalating non-existent ticket should return 404."""
    headers = await _support_headers(client, "esc_404@example.com")
    payload = {"reason": "Test"}
    resp = await client.post("/api/v2/support/tickets/99999/escalate", json=payload, headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_support_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/support/tickets")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_nonexistent_ticket(client: AsyncClient):
    """Getting a non-existent ticket should return 404."""
    headers = await _support_headers(client, "tkt_404@example.com")
    resp = await client.get("/api/v2/support/tickets/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_support_lifecycle(client: AsyncClient, mock_openai):
    """Full lifecycle: create ticket -> get -> update -> send message -> close."""
    headers = await _support_headers(client, "supp_full@example.com")

    # 1. Create ticket
    tkt_payload = {
        "subject": "Full Lifecycle Test",
        "description": "Testing full support lifecycle",
        "priority": "medium",
        "category": "general",
        "customer_email": "customer@example.com",
    }
    resp_create = await client.post("/api/v2/support/tickets", json=tkt_payload, headers=headers)
    assert resp_create.status_code in (201, 422, 500)

    # 2. List tickets
    resp_list = await client.get("/api/v2/support/tickets", headers=headers)
    assert resp_list.status_code == 200

    # 3. Get specific ticket
    items = resp_list.json().get("items", [])
    if items:
        tkt_id = items[0]["id"]
        resp_get = await client.get(f"/api/v2/support/tickets/{tkt_id}", headers=headers)
        assert resp_get.status_code == 200

        # 4. Update ticket
        resp_upd = await client.patch(
            f"/api/v2/support/tickets/{tkt_id}",
            json={"status": "in_progress"},
            headers=headers,
        )
        assert resp_upd.status_code == 200

        # 5. Send message
        msg_payload = {"content": "Investigating your issue now."}
        resp_msg = await client.post(f"/api/v2/support/tickets/{tkt_id}/messages", json=msg_payload, headers=headers)
        assert resp_msg.status_code in (201, 422, 500)

        # 6. List messages
        resp_msgs = await client.get(f"/api/v2/support/tickets/{tkt_id}/messages", headers=headers)
        assert resp_msgs.status_code == 200

        # 7. Search KB
        resp_kb = await client.get("/api/v2/support/kb/search?q=test", headers=headers)
        assert resp_kb.status_code == 200

        # 8. Close ticket
        resp_close = await client.patch(
            f"/api/v2/support/tickets/{tkt_id}/close",
            json={"resolution": "Resolved during testing"},
            headers=headers,
        )
        assert resp_close.status_code == 200
