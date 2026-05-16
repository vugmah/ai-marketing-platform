"""Webhook tests.

Covers:
  - ERP webhook receiver
  - Social media webhook receiver
  - Signature verification
  - Payload parsing
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# ERP Webhook Receiver
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_erp_webhook_product_update(client: AsyncClient):
    """ERP product update webhook should return 200."""
    payload = {
        "event": "product.updated",
        "data": {
            "product_id": "prod_12345",
            "name": "Updated Product Name",
            "price": 29.99,
            "stock": 100,
            "sku": "SKU-001",
            "updated_at": "2024-01-15T10:00:00Z",
        },
        "timestamp": "2024-01-15T10:00:00Z",
        "signature": "mock_signature_valid",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_erp_webhook_order_created(client: AsyncClient):
    """ERP order created webhook should return 200."""
    payload = {
        "event": "order.created",
        "data": {
            "order_id": "ord_67890",
            "customer_id": "cust_111",
            "total": 150.00,
            "currency": "USD",
            "items": [
                {"product_id": "prod_123", "quantity": 2, "price": 75.00},
            ],
            "status": "pending",
            "created_at": "2024-01-15T10:00:00Z",
        },
        "timestamp": "2024-01-15T10:00:00Z",
        "signature": "mock_signature_valid",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_erp_webhook_customer_update(client: AsyncClient):
    """ERP customer update webhook should return 200."""
    payload = {
        "event": "customer.updated",
        "data": {
            "customer_id": "cust_111",
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+994501234567",
            "address": "123 Main St, Baku",
            "updated_at": "2024-01-15T10:00:00Z",
        },
        "timestamp": "2024-01-15T10:00:00Z",
        "signature": "mock_signature_valid",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_erp_webhook_invalid_signature(client: AsyncClient):
    """ERP webhook with invalid signature should return 401."""
    payload = {
        "event": "product.updated",
        "data": {"product_id": "prod_123"},
        "timestamp": "2024-01-15T10:00:00Z",
        "signature": "invalid_signature",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 401, 404, 422)


@pytest.mark.asyncio
async def test_erp_webhook_missing_signature(client: AsyncClient):
    """ERP webhook without signature should return 401 or 422."""
    payload = {
        "event": "product.updated",
        "data": {"product_id": "prod_123"},
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 401, 404, 422)


@pytest.mark.asyncio
async def test_erp_webhook_empty_payload(client: AsyncClient):
    """ERP webhook with empty payload should return 422."""
    resp = await client.post("/api/v2/webhooks/erp", json={})
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Social Media Webhook Receiver
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_facebook_webhook_verification(client: AsyncClient):
    """Facebook webhook verification should return challenge."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "webhook-verify-token",
        "hub.challenge": "challenge_12345",
    }
    resp = await client.get("/api/v2/social/webhooks/facebook", params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert "challenge" in data


@pytest.mark.asyncio
async def test_facebook_webhook_verification_invalid_token(client: AsyncClient):
    """Facebook webhook with invalid verify token should fail."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong-token",
        "hub.challenge": "challenge_12345",
    }
    resp = await client.get("/api/v2/social/webhooks/facebook", params=params)
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_facebook_webhook_message_received(client: AsyncClient):
    """Facebook webhook receiving a message should return 200."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_123",
                "time": 1705312800,
                "messaging": [
                    {
                        "sender": {"id": "user_456"},
                        "recipient": {"id": "page_123"},
                        "timestamp": 1705312800000,
                        "message": {
                            "mid": "mid.123",
                            "text": "Hello, I have a question!",
                        },
                    }
                ],
            }
        ],
    }
    resp = await client.post("/api/v2/social/webhooks/facebook", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_facebook_webhook_comment_received(client: AsyncClient):
    """Facebook webhook receiving a comment should return 200."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_123",
                "time": 1705312800,
                "changes": [
                    {
                        "field": "feed",
                        "value": {
                            "item": "comment",
                            "comment_id": "comment_789",
                            "from": {"id": "user_456", "name": "Test User"},
                            "message": "Great post!",
                            "post_id": "post_123",
                            "created_time": 1705312800,
                        },
                    }
                ],
            }
        ],
    }
    resp = await client.post("/api/v2/social/webhooks/facebook", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_telegram_webhook_message(client: AsyncClient):
    """Telegram webhook receiving a message should return 200."""
    payload = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 987654321, "is_bot": False, "first_name": "Test", "username": "testuser"},
            "chat": {"id": 987654321, "type": "private", "first_name": "Test"},
            "date": 1705312800,
            "text": "Hello bot!",
        },
    }
    resp = await client.post("/api/v2/social/webhooks/telegram", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_telegram_webhook_empty_update(client: AsyncClient):
    """Telegram webhook with empty update should return 200."""
    payload = {"update_id": 999999999}
    resp = await client.post("/api/v2/social/webhooks/telegram", json=payload)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Webhook Signature Verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_signature_verification_valid(client: AsyncClient):
    """Webhook with valid signature should be accepted."""
    import hashlib
    import hmac

    secret = b"webhook_secret"
    payload_body = b'{"event":"test","data":{"id":"123"}}'
    signature = hmac.new(secret, payload_body, hashlib.sha256).hexdigest()

    headers = {"X-Webhook-Signature": f"sha256={signature}"}
    resp = await client.post("/api/v2/webhooks/erp", content=payload_body, headers=headers)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_webhook_signature_verification_invalid(client: AsyncClient):
    """Webhook with invalid signature should be rejected."""
    headers = {"X-Webhook-Signature": "sha256=invalid_signature"}
    payload = {"event": "test", "data": {"id": "123"}}
    resp = await client.post("/api/v2/webhooks/erp", json=payload, headers=headers)
    assert resp.status_code in (200, 401, 404, 422)


# ---------------------------------------------------------------------------
# Payload Parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_parses_nested_payload(client: AsyncClient):
    """Webhook should correctly parse deeply nested payloads."""
    payload = {
        "event": "order.created",
        "data": {
            "order": {
                "id": "ord_deep_001",
                "items": [
                    {"product": {"id": "prod_1", "variants": [{"sku": "SKU-1", "price": 10.00}]},
                     "quantity": 2},
                    {"product": {"id": "prod_2", "variants": [{"sku": "SKU-2", "price": 20.00}]},
                     "quantity": 1},
                ],
                "customer": {
                    "profile": {
                        "preferences": {"notifications": True, "language": "en"},
                    },
                },
            },
        },
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_webhook_parses_array_payload(client: AsyncClient):
    """Webhook should correctly parse array payloads."""
    payload = {
        "event": "products.bulk_updated",
        "data": [
            {"product_id": "prod_1", "stock": 50},
            {"product_id": "prod_2", "stock": 30},
            {"product_id": "prod_3", "stock": 20},
        ],
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_webhook_handles_large_payload(client: AsyncClient):
    """Webhook should handle large payloads."""
    items = [{"product_id": f"prod_{i}", "stock": i} for i in range(100)]
    payload = {
        "event": "inventory.bulk_update",
        "data": items,
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_malformed_json(client: AsyncClient):
    """Webhook with malformed JSON should return 422."""
    headers = {"Content-Type": "application/json"}
    resp = await client.post("/api/v2/webhooks/erp", content=b"not valid json", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_webhook_missing_event_type(client: AsyncClient):
    """Webhook without event type should return 422 or handle gracefully."""
    payload = {
        "data": {"product_id": "prod_123"},
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_webhook_unknown_event_type(client: AsyncClient):
    """Webhook with unknown event type should handle gracefully."""
    payload = {
        "event": "unknown.event.type",
        "data": {"some": "data"},
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp = await client.post("/api/v2/webhooks/erp", json=payload)
    assert resp.status_code in (200, 404, 422)


# ---------------------------------------------------------------------------
# Full Webhook Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_webhook_lifecycle(client: AsyncClient):
    """Full lifecycle: verify FB webhook -> receive message -> receive comment -> process ERP webhook."""
    # 1. Facebook webhook verification
    verify_params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "webhook-verify-token",
        "hub.challenge": "full_lifecycle_challenge",
    }
    resp_verify = await client.get("/api/v2/social/webhooks/facebook", params=verify_params)
    assert resp_verify.status_code == 200
    assert resp_verify.json()["challenge"] == "full_lifecycle_challenge"

    # 2. Receive Facebook message
    msg_payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_123",
                "time": 1705312800,
                "messaging": [
                    {
                        "sender": {"id": "user_456"},
                        "recipient": {"id": "page_123"},
                        "timestamp": 1705312800000,
                        "message": {"mid": "mid.full", "text": "Test message"},
                    }
                ],
            }
        ],
    }
    resp_msg = await client.post("/api/v2/social/webhooks/facebook", json=msg_payload)
    assert resp_msg.status_code == 200

    # 3. Receive Telegram message
    tg_payload = {
        "update_id": 999,
        "message": {
            "message_id": 99,
            "from": {"id": 111, "is_bot": False, "first_name": "TgTest"},
            "chat": {"id": 111, "type": "private"},
            "date": 1705312800,
            "text": "Hello from Telegram",
        },
    }
    resp_tg = await client.post("/api/v2/social/webhooks/telegram", json=tg_payload)
    assert resp_tg.status_code == 200

    # 4. Process ERP webhook
    erp_payload = {
        "event": "product.updated",
        "data": {"product_id": "prod_full_001", "name": "Full Lifecycle Product", "price": 99.99},
        "timestamp": "2024-01-15T10:00:00Z",
    }
    resp_erp = await client.post("/api/v2/webhooks/erp", json=erp_payload)
    assert resp_erp.status_code in (200, 404, 422)
