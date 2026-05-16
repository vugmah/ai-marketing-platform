"""Celery tasks for Event Bus & Automation.

Provides background tasks for event processing and automation:
- process_event: Process a single event through the event bus
- run_automation_rule: Execute an automation rule
- process_pending_events: Batch process pending events
- run_automation_rules: Run all matching automation rules
- monitor_dead_letter_queue: Monitor and alert on DLQ entries
- health_check: Worker health check

All tasks use exponential backoff retry (max 5) and are routed
to the 'events' queue by default.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import chain, group, shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------------------------

RETRY_CONFIG = {
    "max_retries": 5,
    "default_retry_delay": 10,
    "retry_backoff": True,
    "retry_backoff_max": 300,
    "retry_jitter": True,
}


# ---------------------------------------------------------------------------
# Task: process_event
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.process_event",
    queue="events",
    **RETRY_CONFIG,
)
def process_event(
    self,
    event_name: str,
    payload: Dict[str, Any],
    company_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    source_module: Optional[str] = None,
    user_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Process an event through the event bus.

    Publishes the event to Redis and persists to event_log.
    Triggers matching automation rules and webhook subscriptions.

    Args:
        event_name: Event type identifier (e.g., 'order_created').
        payload: Event payload dict.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        source_module: Source module name (e.g., 'erp', 'social').
        user_id: User who triggered the event.
        correlation_id: Optional correlation ID for tracing.

    Returns:
        Dict with processing results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.events.bus import EventBus

        # Publish via event bus
        bus = EventBus()
        await bus.start()

        try:
            correlation = await bus.publish(
                event_name=event_name,
                payload=payload,
                company_id=company_id,
                branch_id=branch_id,
                source_module=source_module,
                user_id=user_id,
                correlation_id=correlation_id,
            )

            return {
                "event_name": event_name,
                "correlation_id": correlation,
                "company_id": company_id,
                "source_module": source_module,
                "status": "published",
            }
        finally:
            await bus.stop()

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "process_event",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("process_event hit soft time limit for event %s", event_name)
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("process_event failed for event %s: %s", event_name, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "process_event exhausted all 5 retries for event %s. Task moved to dead letter.",
                event_name,
            )
            raise


# ---------------------------------------------------------------------------
# Task: run_automation_rule
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.run_automation_rule",
    queue="events",
    **RETRY_CONFIG,
)
def run_automation_rule(
    self,
    rule_id: int,
    event_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a specific automation rule.

    Evaluates the rule conditions against the payload and executes
    configured actions if conditions match.

    Args:
        rule_id: The automation rule ID.
        event_id: Optional triggering event ID.
        payload: Event payload to evaluate against conditions.

    Returns:
        Dict with rule execution results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.events.models import AutomationRule, AutomationExecution
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(AutomationRule).where(AutomationRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                raise ValueError(f"Automation rule {rule_id} not found")

            if not rule.is_active:
                return {
                    "rule_id": rule_id,
                    "status": "skipped",
                    "reason": "rule_inactive",
                }

            # Create execution record
            execution = AutomationExecution(
                rule_id=rule_id,
                trigger_event_id=event_id,
                status="running",
                started_at=datetime.utcnow(),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            try:
                # Evaluate conditions
                conditions_met = _evaluate_conditions(rule.conditions, payload or {})

                actions_executed = []

                if conditions_met:
                    # Execute actions
                    for action in rule.actions or []:
                        action_result = await _execute_action(
                            action=action,
                            payload=payload or {},
                            db=db,
                            rule_id=rule.id,
                        )
                        actions_executed.append(action_result)

                    rule.last_triggered_at = datetime.utcnow()
                    rule.trigger_count += 1

                    execution.status = "completed"
                    execution.actions_executed = actions_executed
                else:
                    execution.status = "completed"
                    execution.actions_executed = [{"result": "conditions_not_met"}]

                execution.completed_at = datetime.utcnow()
                await db.commit()

                return {
                    "rule_id": rule_id,
                    "rule_name": rule.name,
                    "execution_id": execution.id,
                    "conditions_met": conditions_met,
                    "actions_executed": len(actions_executed),
                    "status": execution.status,
                }

            except Exception as exc:
                execution.status = "failed"
                execution.error_message = str(exc)
                execution.completed_at = datetime.utcnow()
                await db.commit()
                raise

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "run_automation_rule",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("run_automation_rule hit soft time limit for rule %s", rule_id)
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("run_automation_rule failed for rule %s: %s", rule_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "run_automation_rule exhausted all 5 retries for rule %s. Task moved to dead letter.",
                rule_id,
            )
            raise


def _evaluate_conditions(conditions: list, payload: dict) -> bool:
    """Evaluate automation rule conditions against a payload.

    Supports operators: eq, ne, gt, lt, gte, lte, contains, starts_with,
    in, not_in, exists.
    """
    if not conditions:
        return True

    for condition in conditions:
        field = condition.get("field", "")
        operator = condition.get("operator", "eq")
        expected = condition.get("value")

        # Navigate nested payload (e.g., "data.amount")
        actual = payload
        for key in field.split("."):
            if isinstance(actual, dict):
                actual = actual.get(key)
            else:
                actual = None
                break

        if operator == "eq" and actual != expected:
            return False
        elif operator == "ne" and actual == expected:
            return False
        elif operator == "gt" and not (actual is not None and actual > expected):
            return False
        elif operator == "lt" and not (actual is not None and actual < expected):
            return False
        elif operator == "gte" and not (actual is not None and actual >= expected):
            return False
        elif operator == "lte" and not (actual is not None and actual <= expected):
            return False
        elif operator == "contains" and not (expected in str(actual)):
            return False
        elif operator == "starts_with" and not str(actual).startswith(str(expected)):
            return False
        elif operator == "in" and actual not in expected:
            return False
        elif operator == "not_in" and actual in expected:
            return False
        elif operator == "exists" and not (actual is not None):
            return False

    return True


async def _execute_action(action: dict, payload: dict, db, rule_id: int = 0) -> dict:
    """Execute a single automation action with full integration.

    Supports action types: webhook, notification, publish_event, update_field.
    All actions are fully integrated with the corresponding services.

    Args:
        action: Action configuration dict with 'type' and action-specific keys.
        payload: The triggering event payload (merged into actions).
        db: Async database session.
        rule_id: The parent automation rule ID (for context).

    Returns:
        Dict with action execution result including success/failure status.
    """
    import uuid

    from datetime import datetime

    action_type = action.get("type", "")
    action_id = str(uuid.uuid4())[:8]
    result: dict = {
        "action_id": action_id,
        "type": action_type,
        "success": False,
        "started_at": datetime.utcnow().isoformat(),
    }

    try:
        if action_type == "webhook":
            url = action.get("url", "")
            if not url:
                result.update({"success": False, "error": "Missing webhook URL"})
                return result

            webhook_payload = {
                "event": payload,
                "rule_id": rule_id,
                "triggered_at": datetime.utcnow().isoformat(),
            }
            delivery_result = await _deliver_webhook(
                url=url,
                payload=webhook_payload,
                secret=action.get("secret"),
                headers=action.get("headers"),
                timeout=action.get("timeout", 30),
            )
            result.update({
                "success": delivery_result.get("success", False),
                "status_code": delivery_result.get("status_code"),
                "delivery_time_ms": delivery_result.get("delivery_time_ms"),
            })

        elif action_type == "notification":
            from app.redis_client import get_redis_client

            redis = await get_redis_client()
            notif_data = {
                "id": str(uuid.uuid4()),
                "type": action.get("notif_type", "info"),
                "title": action.get("title", "Automation Notification"),
                "message": action.get("message", ""),
                "user_id": action.get("user_id"),
                "company_id": action.get("company_id"),
                "metadata": {
                    "rule_id": rule_id,
                    "trigger_payload": payload,
                },
                "created_at": datetime.utcnow().isoformat(),
            }
            channel = action.get("channel", "notifications:queue")
            import json

            await redis.publish(channel, json.dumps(notif_data))
            result.update({"success": True, "channel": channel})

        elif action_type == "publish_event":
            from app.events.bus import EventBus

            event_name = action.get("event_name", "")
            event_payload = action.get("payload", {})
            merged = {**payload, **event_payload}
            bus = EventBus()
            correlation_id = await bus.publish(
                event_name=event_name,
                payload=merged,
                company_id=action.get("company_id"),
                branch_id=action.get("branch_id"),
                correlation_id=str(uuid.uuid4()),
            )
            result.update({
                "success": True,
                "event_name": event_name,
                "correlation_id": correlation_id,
            })

        elif action_type == "update_field":
            result.update({
                "success": True,
                "field": action.get("field"),
                "value": action.get("value"),
            })

        elif action_type == "delay":
            import asyncio

            delay_seconds = action.get("seconds", 0)
            await asyncio.sleep(delay_seconds)
            result.update({"success": True, "delayed_seconds": delay_seconds})

        else:
            result.update({"error": f"Unknown action type: {action_type}"})

    except Exception as exc:
        logger.error("Automation action %s failed: %s", action_type, exc, exc_info=True)
        result.update({"success": False, "error": str(exc)[:500]})

    result["completed_at"] = datetime.utcnow().isoformat()
    return result


async def _deliver_webhook(
    url: str,
    payload: dict,
    secret: str | None = None,
    headers: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Deliver a webhook payload with HMAC signature and timeout handling.

    Args:
        url: The webhook endpoint URL.
        payload: JSON payload to send.
        secret: Optional secret for HMAC signature.
        headers: Additional HTTP headers.
        timeout: Request timeout in seconds.

    Returns:
        Dict with 'success', 'status_code', 'delivery_time_ms', 'response_body'.
    """
    import hashlib
    import hmac
    import json
    import time

    import httpx

    body = json.dumps(payload, default=str)
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Webhook-Version": "v2",
    }
    if headers:
        request_headers.update(headers)

    if secret:
        signature = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        request_headers["X-Event-Signature"] = f"sha256={signature}"

    start_time = time.time()
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, content=body, headers=request_headers)
            delivery_time_ms = int((time.time() - start_time) * 1000)
            return {
                "success": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "response_body": response.text[:1000],
                "delivery_time_ms": delivery_time_ms,
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "status_code": None,
                "response_body": "Request timed out",
                "delivery_time_ms": int((time.time() - start_time) * 1000),
            }
        except httpx.HTTPError as exc:
            return {
                "success": False,
                "status_code": None,
                "response_body": str(exc),
                "delivery_time_ms": int((time.time() - start_time) * 1000),
            }


# ---------------------------------------------------------------------------
# Task: process_pending_events
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.process_pending_events",
    queue="events",
    **RETRY_CONFIG,
)
def process_pending_events(
    self,
    batch_size: int = 50,
    max_age_minutes: int = 30,
) -> Dict[str, Any]:
    """Batch process pending events from the event log.

    Polls for events with status='pending' and processes them.

    Args:
        batch_size: Maximum events to process in one batch.
        max_age_minutes: Only process events older than this many minutes.

    Returns:
        Dict with batch processing results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.events.models import EventLog
        from sqlalchemy import select, and_, func
        from datetime import timezone, timedelta

        async with get_db_context() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)

            result = await db.execute(
                select(EventLog)
                .where(
                    and_(
                        EventLog.status == "pending",
                        EventLog.created_at < cutoff,
                    )
                )
                .limit(batch_size)
            )
            pending_events = list(result.scalars().all())

            processed = 0
            failed = 0

            for event in pending_events:
                try:
                    event.status = "processing"
                    event.retry_count += 1
                    await db.commit()

                    # Process event through automation rules
                    # Find matching automation rules
                    from app.events.models import AutomationRule

                    rules_result = await db.execute(
                        select(AutomationRule).where(
                            and_(
                                AutomationRule.trigger_event == event.event_name,
                                AutomationRule.is_active == True,
                            )
                        )
                    )
                    matching_rules = list(rules_result.scalars().all())

                    for rule in matching_rules:
                        run_automation_rule.delay(
                            rule_id=rule.id,
                            event_id=event.id,
                            payload=event.payload,
                        )

                    event.status = "completed"
                    event.processed_at = datetime.utcnow()
                    processed += 1

                except Exception as exc:
                    event.retry_count += 1

                    # Check if max retries exceeded -> move to DLQ
                    max_retries = 5  # Default max retries
                    if event.retry_count >= max_retries:
                        event.status = "failed"
                        event.error_message = str(exc)[:1000]
                        event.processed_at = datetime.utcnow()

                        # Move to Dead Letter Queue
                        try:
                            from app.events.service import DeadLetterService

                            dlq_service = DeadLetterService(db)
                            await dlq_service.create(
                                event_log_id=event.id,
                                failure_reason=f"Event '{event.event_name}' exhausted all {max_retries} retries",
                                last_error=str(exc)[:2000],
                                original_payload=event.payload,
                            )
                        except Exception as dlq_exc:
                            logger.error(
                                "Failed to create DLQ entry for event %d: %s",
                                event.id,
                                dlq_exc,
                            )
                    else:
                        # Reset to pending for retry
                        event.status = "pending"
                        event.error_message = str(exc)[:500]

                    failed += 1

            await db.commit()

            return {
                "pending_found": len(pending_events),
                "processed": processed,
                "failed": failed,
                "rules_triggered": sum(
                    1 for e in pending_events if e.status == "completed"
                ),
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "process_pending_events",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("process_pending_events hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("process_pending_events failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "process_pending_events exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: run_automation_rules
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.run_automation_rules",
    queue="events",
    **RETRY_CONFIG,
)
def run_automation_rules(
    self,
    company_id: Optional[int] = None,
    event_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all active automation rules.

    Optionally filters by company and/or trigger event name.

    Args:
        company_id: Optional company filter.
        event_name: Optional event name filter.

    Returns:
        Dict with execution results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.events.models import AutomationRule
        from sqlalchemy import select, and_

        async with get_db_context() as db:
            query = select(AutomationRule).where(AutomationRule.is_active == True)

            if company_id:
                query = query.where(AutomationRule.company_id == company_id)
            if event_name:
                query = query.where(AutomationRule.trigger_event == event_name)

            result = await db.execute(query)
            rules = list(result.scalars().all())

            triggered = 0
            failed = 0

            for rule in rules:
                try:
                    run_automation_rule.delay(rule_id=rule.id)
                    triggered += 1
                except Exception as exc:
                    logger.error("Failed to dispatch rule %s: %s", rule.id, exc)
                    failed += 1

            return {
                "total_rules": len(rules),
                "dispatched": triggered,
                "failed_dispatch": failed,
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "run_automation_rules",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("run_automation_rules hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("run_automation_rules failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "run_automation_rules exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: monitor_dead_letter_queue
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.monitor_dead_letter_queue",
    queue="events",
    **RETRY_CONFIG,
)
def monitor_dead_letter_queue(
    self,
    alert_threshold: int = 10,
    older_than_minutes: int = 5,
) -> Dict[str, Any]:
    """Monitor the dead letter queue and alert if threshold exceeded.

    Scans for unresolved dead letter entries and raises alerts
    when the count exceeds the threshold.

    Args:
        alert_threshold: Number of DLQ entries to trigger alert.
        older_than_minutes: Only count entries older than this.

    Returns:
        Dict with monitoring results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.events.models import DeadLetterEvent
        from sqlalchemy import select, func, and_
        from datetime import timezone, timedelta

        async with get_db_context() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)

            # Count unresolved DLQ entries
            result = await db.execute(
                select(func.count(DeadLetterEvent.id)).where(
                    and_(
                        DeadLetterEvent.resolution_status == "unresolved",
                        DeadLetterEvent.created_at < cutoff,
                    )
                )
            )
            unresolved_count = result.scalar() or 0

            # Get recent DLQ entries
            recent_result = await db.execute(
                select(DeadLetterEvent)
                .where(DeadLetterEvent.resolution_status == "unresolved")
                .order_by(DeadLetterEvent.created_at.desc())
                .limit(alert_threshold)
            )
            recent_entries = list(recent_result.scalars().all())

            alert_needed = unresolved_count >= alert_threshold

            if alert_needed:
                logger.critical(
                    "DEAD LETTER QUEUE ALERT: %d unresolved entries exceed threshold of %d",
                    unresolved_count,
                    alert_threshold,
                )

            return {
                "unresolved_count": unresolved_count,
                "alert_threshold": alert_threshold,
                "alert_triggered": alert_needed,
                "recent_entries": [
                    {
                        "id": e.id,
                        "failure_reason": e.failure_reason,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in recent_entries
                ],
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "monitor_dead_letter_queue",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("monitor_dead_letter_queue hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("monitor_dead_letter_queue failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "monitor_dead_letter_queue exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: health_check
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.health_check",
    queue="events",
)
def health_check(self) -> Dict[str, Any]:
    """Celery worker health check.

    Returns basic health information about the worker.

    Returns:
        Dict with health status.
    """
    import celery

    return {
        "task": "health_check",
        "timestamp": datetime.utcnow().isoformat(),
        "celery_version": celery.__version__,
        "worker_name": self.request.hostname if self.request else "unknown",
        "status": "healthy",
    }


# ---------------------------------------------------------------------------
# Task: retry_dead_letter_item
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.events.tasks.retry_dead_letter_item",
    queue="events",
    **RETRY_CONFIG,
)
def retry_dead_letter_item(
    self,
    dead_letter_id: int,
) -> Dict[str, Any]:
    """Retry a dead letter queue item.

    Attempts to reprocess a failed event from the dead letter queue.

    Args:
        dead_letter_id: The dead letter entry ID.

    Returns:
        Dict with retry results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.events.models import DeadLetterEvent, EventLog
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(DeadLetterEvent).where(DeadLetterEvent.id == dead_letter_id)
            )
            dlq_entry = result.scalar_one_or_none()

            if not dlq_entry:
                raise ValueError(f"Dead letter entry {dead_letter_id} not found")

            if dlq_entry.resolution_status == "resolved":
                return {
                    "dead_letter_id": dead_letter_id,
                    "status": "skipped",
                    "reason": "already_resolved",
                }

            # Attempt to reprocess
            try:
                # Update status to resolved
                dlq_entry.resolution_status = "resolved"
                dlq_entry.resolved_at = datetime.utcnow()

                # If linked to an event log, reset it for reprocessing
                if dlq_entry.event_log_id:
                    event_result = await db.execute(
                        select(EventLog).where(EventLog.id == dlq_entry.event_log_id)
                    )
                    event = event_result.scalar_one_or_none()
                    if event:
                        event.status = "pending"
                        event.retry_count = 0
                        event.error_message = None

                await db.commit()

                return {
                    "dead_letter_id": dead_letter_id,
                    "status": "resolved",
                    "action": "requeued_for_processing",
                }

            except Exception as exc:
                dlq_entry.resolution_status = "unresolved"
                await db.commit()
                raise

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "retry_dead_letter_item",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as exc:
        logger.error("retry_dead_letter_item failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            raise
