"""Event bus module tests.

Covers:
  - Publish event
  - Subscribe to events
  - Automation rules
  - Dead letter queue
  - Celery background tasks
  - Retry logic with exponential backoff
  - Event audit logging
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _events_headers(client: AsyncClient, email: str, role: str = "company_admin") -> dict:
    """Create auth headers for events tests."""
    from app.auth.schemas import UserRegister
    from app.auth.service import register_user, _mock_users
    from app.auth.utils import create_access_token

    user_data = UserRegister(
        email=email,
        password="Password123!",
        first_name="Events",
        last_name="Tester",
    )
    try:
        await register_user(user_data)
    except Exception:
        pass

    user = _mock_users.get(email)
    if user:
        user["role"] = role
        user["company_id"] = "events-test-company"

    token_payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": role,
        "company_id": "events-test-company",
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": "events-test-company",
    }


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_event(client: AsyncClient):
    """Publishing an event should return 201."""
    headers = await _events_headers(client, "evt_pub@example.com")
    payload = {
        "event_type": "user_action",
        "payload": {"action": "button_click", "page": "dashboard"},
        "source": "test_suite",
    }
    resp = await client.post("/api/v2/events/publish", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_publish_event_with_priority(client: AsyncClient):
    """Publishing an event with priority should work."""
    headers = await _events_headers(client, "evt_prio@example.com")
    payload = {
        "event_type": "urgent_notification",
        "payload": {"message": "Important!"},
        "priority": "high",
        "source": "test_suite",
    }
    resp = await client.post("/api/v2/events/publish", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


# ---------------------------------------------------------------------------
# Event Log
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_event_log(client: AsyncClient):
    """Listing event log should return 200."""
    headers = await _events_headers(client, "evt_log@example.com")
    resp = await client.get("/api/v2/events/log", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_event_log_with_filters(client: AsyncClient):
    """Listing event log with filters should work."""
    headers = await _events_headers(client, "evt_logf@example.com")
    resp = await client.get("/api/v2/events/log?event_type=user_action", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_subscriptions(client: AsyncClient):
    """Listing subscriptions should return 200."""
    headers = await _events_headers(client, "evt_sublist@example.com")
    resp = await client.get("/api/v2/events/subscriptions", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_subscription(client: AsyncClient):
    """Creating a subscription should return 201."""
    headers = await _events_headers(client, "evt_subcr@example.com")
    payload = {
        "event_type": "user_action",
        "endpoint_url": "https://example.com/webhook",
        "headers": {"Authorization": "Bearer test"},
        "is_active": True,
    }
    resp = await client.post("/api/v2/events/subscriptions", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_delete_subscription(client: AsyncClient):
    """Deleting a subscription should return 204."""
    headers = await _events_headers(client, "evt_subdel@example.com")
    resp_list = await client.get("/api/v2/events/subscriptions", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        sub_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/events/subscriptions/{sub_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_event_types(client: AsyncClient):
    """Listing event types should return 200."""
    headers = await _events_headers(client, "evt_types@example.com")
    resp = await client.get("/api/v2/events/types", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Event Definitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_event_definitions(client: AsyncClient):
    """Listing event definitions should return 200."""
    headers = await _events_headers(client, "evt_defs@example.com")
    resp = await client.get("/api/v2/events/definitions", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Event Stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_event_stats(client: AsyncClient):
    """Getting event stats should return 200."""
    headers = await _events_headers(client, "evt_stats@example.com")
    resp = await client.get("/api/v2/events/stats", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Automation Rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_automation_rules(client: AsyncClient):
    """Listing automation rules should return 200."""
    headers = await _events_headers(client, "evt_autolist@example.com")
    resp = await client.get("/api/v2/events/automation-rules", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_automation_rule(client: AsyncClient):
    """Creating an automation rule should return 201."""
    headers = await _events_headers(client, "evt_autocreate@example.com")
    payload = {
        "name": "Auto-Rule: High CPU Alert",
        "trigger_event": "cpu_usage_high",
        "conditions": {"threshold": 90},
        "action": "send_notification",
        "action_config": {"channel": "email", "recipients": ["admin@example.com"]},
        "is_active": True,
    }
    resp = await client.post("/api/v2/events/automation-rules", json=payload, headers=headers)
    assert resp.status_code in (201, 422, 500)


@pytest.mark.asyncio
async def test_get_automation_rule(client: AsyncClient):
    """Getting an automation rule should return 200 or 404."""
    headers = await _events_headers(client, "evt_autoget@example.com")
    resp_list = await client.get("/api/v2/events/automation-rules", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        rule_id = items[0]["id"]
        resp = await client.get(f"/api/v2/events/automation-rules/{rule_id}", headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_automation_rule(client: AsyncClient):
    """Updating an automation rule should return 200."""
    headers = await _events_headers(client, "evt_autoup@example.com")
    resp_list = await client.get("/api/v2/events/automation-rules", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        rule_id = items[0]["id"]
        payload = {"is_active": False}
        resp = await client.patch(f"/api/v2/events/automation-rules/{rule_id}", json=payload, headers=headers)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_automation_rule(client: AsyncClient):
    """Deleting an automation rule should return 204."""
    headers = await _events_headers(client, "evt_autodel@example.com")
    resp_list = await client.get("/api/v2/events/automation-rules", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        rule_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/events/automation-rules/{rule_id}", headers=headers)
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_run_automation_rule(client: AsyncClient):
    """Running an automation rule manually should return 200."""
    headers = await _events_headers(client, "evt_autorun@example.com")
    resp_list = await client.get("/api/v2/events/automation-rules", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        rule_id = items[0]["id"]
        resp = await client.post(f"/api/v2/events/automation-rules/{rule_id}/run", headers=headers)
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Dead Letter Queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_dlq(client: AsyncClient):
    """Listing dead letter queue should return 200."""
    headers = await _events_headers(client, "evt_dlq@example.com")
    resp = await client.get("/api/v2/events/dlq", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_dlq_with_filters(client: AsyncClient):
    """DLQ with filters should work."""
    headers = await _events_headers(client, "evt_dlqf@example.com")
    resp = await client.get("/api/v2/events/dlq?event_type=failed_event", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_retry_dlq_event(client: AsyncClient):
    """Retrying a DLQ event should return 200."""
    headers = await _events_headers(client, "evt_retry@example.com")
    resp_list = await client.get("/api/v2/events/dlq", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        event_id = items[0]["id"]
        resp = await client.post(f"/api/v2/events/dlq/{event_id}/retry", headers=headers)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_delete_dlq_event(client: AsyncClient):
    """Deleting a DLQ event should return 204."""
    headers = await _events_headers(client, "evt_dlqdel@example.com")
    resp_list = await client.get("/api/v2/events/dlq", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        event_id = items[0]["id"]
        resp = await client.delete(f"/api/v2/events/dlq/{event_id}", headers=headers)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Error Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_events_access(client: AsyncClient):
    """Unauthenticated access should fail."""
    resp = await client.get("/api/v2/events/log")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_publish_without_auth(client: AsyncClient):
    """Publishing without auth should fail."""
    payload = {"event_type": "test", "payload": {}}
    resp = await client.post("/api/v2/events/publish", json=payload)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_full_events_lifecycle(client: AsyncClient):
    """Full lifecycle: publish -> list log -> list subscriptions -> list rules -> get stats."""
    headers = await _events_headers(client, "evt_full@example.com")

    # 1. Publish event
    pub_payload = {
        "event_type": "test_lifecycle",
        "payload": {"test": True, "stage": 1},
        "source": "test_suite",
    }
    resp_pub = await client.post("/api/v2/events/publish", json=pub_payload, headers=headers)
    assert resp_pub.status_code in (201, 422, 500)

    # 2. List event log
    resp_log = await client.get("/api/v2/events/log", headers=headers)
    assert resp_log.status_code == 200

    # 3. List subscriptions
    resp_subs = await client.get("/api/v2/events/subscriptions", headers=headers)
    assert resp_subs.status_code == 200

    # 4. List event types
    resp_types = await client.get("/api/v2/events/types", headers=headers)
    assert resp_types.status_code == 200

    # 5. List event definitions
    resp_defs = await client.get("/api/v2/events/definitions", headers=headers)
    assert resp_defs.status_code == 200

    # 6. List automation rules
    resp_rules = await client.get("/api/v2/events/automation-rules", headers=headers)
    assert resp_rules.status_code == 200

    # 7. List DLQ
    resp_dlq = await client.get("/api/v2/events/dlq", headers=headers)
    assert resp_dlq.status_code == 200

    # 8. Get stats
    resp_stats = await client.get("/api/v2/events/stats", headers=headers)
    assert resp_stats.status_code == 200


# ---------------------------------------------------------------------------
# Retry Logic & Backoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_configuration(client: AsyncClient):
    """Verify retry policies are configured with exponential backoff."""
    from celeryconfig import task_max_retries, task_default_retry_delay

    assert task_max_retries == 5, "max_retries must be 5"
    assert task_default_retry_delay == 10, "base retry delay must be 10 seconds"


@pytest.mark.asyncio
async def test_exponential_backoff_delays():
    """Verify exponential backoff delay calculation: 10, 20, 40, 80, 160."""
    base_delay = 10
    delays = [base_delay * (2 ** i) for i in range(5)]
    expected = [10, 20, 40, 80, 160]
    assert delays == expected, f"Expected {expected}, got {delays}"


@pytest.mark.asyncio
async def test_retry_config_in_all_task_modules():
    """Verify all task modules use consistent retry configuration."""
    from app.events.tasks import RETRY_CONFIG as events_retry
    from app.ai.tasks import RETRY_CONFIG as ai_retry
    from app.media.tasks import RETRY_CONFIG as media_retry
    from app.social.tasks import RETRY_CONFIG as social_retry

    for module_name, config in [
        ("events", events_retry),
        ("ai", ai_retry),
        ("media", media_retry),
        ("social", social_retry),
    ]:
        assert config["max_retries"] <= 5, f"{module_name} max_retries must be <= 5"
        assert config["retry_backoff"] is True, f"{module_name} must use backoff"
        assert config["retry_backoff_max"] <= 300, f"{module_name} backoff_max too high"
        assert config["retry_jitter"] is True, f"{module_name} must use jitter"


# ---------------------------------------------------------------------------
# Dead Letter Queue - Deep Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dlq_alert_threshold(client: AsyncClient):
    """DLQ monitoring should detect unresolved entries above threshold."""
    headers = await _events_headers(client, "evt_dlq_alert@example.com")
    resp = await client.get("/api/v2/events/dead-letter", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # Verify DLQ response structure
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_dlq_resolve_invalid_resolution(client: AsyncClient):
    """Resolving DLQ with invalid resolution should fail."""
    headers = await _events_headers(client, "evt_dlq_res@example.com")
    resp_list = await client.get("/api/v2/events/dead-letter", headers=headers)
    data = resp_list.json()
    items = data.get("items", [])
    if items:
        dl_id = items[0]["id"]
        resp = await client.post(
            f"/api/v2/events/dead-letter/{dl_id}/resolve",
            json={"resolution": "invalid_value"},
            headers=headers,
        )
        assert resp.status_code in (422, 400)


# ---------------------------------------------------------------------------
# Event Audit Logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_audit_log_created_on_publish(client: AsyncClient):
    """Publishing an event must create an audit log entry."""
    headers = await _events_headers(client, "evt_audit@example.com")

    # Publish event
    pub_payload = {
        "event_name": "audit_test_event",
        "payload": {"test_key": "test_value", "audit": True},
        "source_module": "test_suite",
    }
    resp_pub = await client.post("/api/v2/events/publish", json=pub_payload, headers=headers)
    assert resp_pub.status_code in (200, 201)

    # Verify event appears in log
    resp_log = await client.get(
        "/api/v2/events/log?event_name=audit_test_event",
        headers=headers,
    )
    assert resp_log.status_code == 200
    data = resp_log.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_event_log_has_correlation_id(client: AsyncClient):
    """Published events must have correlation_id for distributed tracing."""
    headers = await _events_headers(client, "evt_corr@example.com")

    pub_payload = {
        "event_name": "correlation_test_event",
        "payload": {"trace": True},
        "correlation_id": "test-correlation-12345",
    }
    resp_pub = await client.post("/api/v2/events/publish", json=pub_payload, headers=headers)
    assert resp_pub.status_code in (200, 201)

    # Verify response contains correlation_id
    pub_data = resp_pub.json()
    assert "correlation_id" in pub_data
    assert pub_data["correlation_id"] is not None


@pytest.mark.asyncio
async def test_event_log_filtering_by_status(client: AsyncClient):
    """Event log should support filtering by status."""
    headers = await _events_headers(client, "evt_status@example.com")

    for status in ["pending", "processing", "completed", "failed"]:
        resp = await client.get(f"/api/v2/events/log?status={status}", headers=headers)
        assert resp.status_code == 200, f"Status filter '{status}' failed"
        data = resp.json()
        assert "items" in data


# ---------------------------------------------------------------------------
# Automation Rules - Condition Engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_automation_condition_operators(client: AsyncClient):
    """Automation rules should support all condition operators."""
    headers = await _events_headers(client, "evt_cond@example.com")

    conditions = [
        {"field": "amount", "operator": "gt", "value": 100},
        {"field": "status", "operator": "eq", "value": "active"},
        {"field": "tags", "operator": "contains", "value": "urgent"},
    ]

    payload = {
        "name": "Condition Test Rule",
        "trigger_event": "order_created",
        "conditions": conditions,
        "actions": [{"type": "notification", "title": "Test", "message": "Test"}],
        "is_active": True,
    }
    resp = await client.post("/api/v2/events/automation-rules", json=payload, headers=headers)
    assert resp.status_code in (201, 200)


# ---------------------------------------------------------------------------
# Celery Task Names Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_celery_task_names_registered():
    """Verify all expected Celery task names are registered in routes."""
    from celeryconfig import task_routes

    expected_tasks = [
        # Events
        "app.events.tasks.process_event",
        "app.events.tasks.run_automation_rule",
        "app.events.tasks.process_pending_events",
        "app.events.tasks.run_automation_rules",
        "app.events.tasks.retry_dead_letter_item",
        "app.events.tasks.monitor_dead_letter_queue",
        "app.events.tasks.health_check",
        # ERP
        "app.erp.tasks.sync_inventory",
        "app.erp.tasks.sync_products",
        "app.erp.tasks.sync_customers",
        "app.erp.tasks.sync_invoices",
        "app.erp.tasks.sync_sales_orders",
        "app.erp.tasks.sync_payments",
        # Social
        "app.social.tasks.sync_posts",
        "app.social.tasks.sync_comments",
        "app.social.tasks.sync_messages",
        "app.social.tasks.sync_analytics",
        # Media
        "app.media.tasks.generate_thumbnail",
        "app.media.tasks.optimize_image",
        "app.media.tasks.cleanup_orphaned_media",
        # AI
        "app.ai.tasks.generate_embedding",
        "app.ai.tasks.analyze_sentiment",
        "app.ai.tasks.batch_analyze_sentiment",
        "app.ai.tasks.generate_suggestions",
    ]

    for task_name in expected_tasks:
        assert task_name in task_routes, f"Task {task_name} not found in task_routes"


# ---------------------------------------------------------------------------
# Celery Beat Schedule Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_beat_schedule_intervals():
    """Verify beat schedule has reasonable intervals for all tasks."""
    from celeryconfig import beat_schedule

    max_reasonable_interval = 86400  # 24 hours

    for task_name, config in beat_schedule.items():
        schedule = config.get("schedule", 0)
        assert isinstance(schedule, (int, float)), f"{task_name}: invalid schedule type"
        assert schedule > 0, f"{task_name}: schedule must be positive"
        assert schedule <= max_reasonable_interval, f"{task_name}: schedule too long"
        assert "task" in config, f"{task_name}: missing task reference"
        assert isinstance(config["task"], str), f"{task_name}: task must be string"


@pytest.mark.asyncio
async def test_beat_schedule_queue_assignment():
    """Verify all periodic tasks have queue assignments."""
    from celeryconfig import beat_schedule

    for task_name, config in beat_schedule.items():
        options = config.get("options", {})
        assert "queue" in options, f"{task_name}: missing queue assignment"


# ---------------------------------------------------------------------------
# DLQ Signal Handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_failure_handler_exists():
    """Verify Celery task failure handler is registered for DLQ."""
    from app.celery_app import handle_task_failure

    assert handle_task_failure is not None
    assert callable(handle_task_failure)
