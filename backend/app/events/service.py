"""Service layer for the Event Bus & Automation module.

Provides seven services:
- EventLogService: Event logging, querying, and statistics
- EventSubscriptionService: CRUD for event subscriptions
- EventHandlerService: Execute handlers with retry logic
- DeadLetterService: Manage dead letter queue and resolution
- AutomationRuleService: CRUD and execution engine for automation rules
- NotificationTriggerService: Trigger notifications on events
- WebhookDeliveryService: Deliver webhooks with signature and retry
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import EventBus, deliver_webhook, execute_with_retry
from app.events.constants import (
    CATEGORY_MAX_RETRIES,
    DEFAULT_RETRY_POLICY,
    RETRY_POLICIES,
    WEBHOOK_DEFAULT_TIMEOUT_SECONDS,
    WEBHOOK_MAX_RETRIES,
)
from app.events.models import (
    AutomationExecution,
    AutomationRule,
    DeadLetterEvent,
    EventDefinition,
    EventHandler,
    EventLog,
    EventSubscription,
)
from app.events.schemas import (
    AutomationExecutionCreate,
    AutomationRuleCreate,
    AutomationRuleUpdate,
    DeadLetterResolveRequest,
    EventDefinitionCreate,
    EventDefinitionUpdate,
    EventLogCreate,
    EventRetryRequest,
    EventSubscriptionCreate,
    EventSubscriptionUpdate,
)
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventLogService
# ---------------------------------------------------------------------------


class EventLogService:
    """Service for managing the event log: create, query, retry, and statistics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: EventLogCreate) -> EventLog:
        """Create a new event log entry."""
        log_entry = EventLog(
            event_name=data.event_name,
            payload=data.payload,
            company_id=data.company_id,
            branch_id=data.branch_id,
            source_module=data.source_module,
            source_user_id=data.source_user_id,
            correlation_id=data.correlation_id or str(uuid.uuid4()),
            status=data.status or "pending",
            retry_count=0,
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry

    async def get_by_id(self, log_id: int) -> Optional[EventLog]:
        """Get an event log entry by ID with its handlers."""
        result = await self.db.execute(
            select(EventLog).where(EventLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def list_events(
        self,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        event_name: Optional[str] = None,
        status: Optional[str] = None,
        source_module: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[EventLog], int]:
        """List event log entries with optional filtering.

        Returns:
            Tuple of (list of EventLog, total count).
        """
        query = select(EventLog)
        count_query = select(func.count()).select_from(EventLog)

        if company_id is not None:
            query = query.where(EventLog.company_id == company_id)
            count_query = count_query.where(EventLog.company_id == company_id)
        if branch_id is not None:
            query = query.where(EventLog.branch_id == branch_id)
            count_query = count_query.where(EventLog.branch_id == branch_id)
        if event_name:
            query = query.where(EventLog.event_name == event_name)
            count_query = count_query.where(EventLog.event_name == event_name)
        if status:
            query = query.where(EventLog.status == status)
            count_query = count_query.where(EventLog.status == status)
        if source_module:
            query = query.where(EventLog.source_module == source_module)
            count_query = count_query.where(EventLog.source_module == source_module)
        if correlation_id:
            query = query.where(EventLog.correlation_id == correlation_id)
            count_query = count_query.where(EventLog.correlation_id == correlation_id)
        if start_date:
            query = query.where(EventLog.created_at >= start_date)
            count_query = count_query.where(EventLog.created_at >= start_date)
        if end_date:
            query = query.where(EventLog.created_at <= end_date)
            count_query = count_query.where(EventLog.created_at <= end_date)

        query = query.order_by(desc(EventLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        total_result = await self.db.execute(count_query)

        return list(result.scalars().all()), total_result.scalar() or 0

    async def update_status(
        self,
        log_id: int,
        status: str,
        error_message: Optional[str] = None,
        increment_retry: bool = False,
    ) -> Optional[EventLog]:
        """Update the status of an event log entry."""
        log_entry = await self.get_by_id(log_id)
        if log_entry is None:
            return None

        log_entry.status = status
        if error_message is not None:
            log_entry.error_message = error_message
        if increment_retry:
            log_entry.retry_count += 1
        if status in ("completed", "failed"):
            log_entry.processed_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry

    async def retry_event(
        self,
        log_id: int,
        request: Optional[EventRetryRequest] = None,
    ) -> Optional[EventLog]:
        """Retry a failed event by resetting its status and incrementing retry count."""
        log_entry = await self.get_by_id(log_id)
        if log_entry is None:
            return None

        if log_entry.status != "failed":
            logger.warning("Cannot retry event %d with status '%s'", log_id, log_entry.status)
            return None

        log_entry.status = "pending"
        log_entry.error_message = None
        log_entry.processed_at = None

        await self.db.commit()
        await self.db.refresh(log_entry)

        # Republish to event bus
        bus = EventBus()
        await bus.publish(
            event_name=log_entry.event_name,
            payload=log_entry.payload,
            company_id=log_entry.company_id,
            branch_id=log_entry.branch_id,
            source_module=log_entry.source_module,
            user_id=log_entry.source_user_id,
            correlation_id=log_entry.correlation_id,
        )

        return log_entry

    async def get_stats(
        self,
        company_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get event statistics for a time period."""
        start_date = start_date or (datetime.utcnow() - timedelta(days=7))
        end_date = end_date or datetime.utcnow()

        base_filter = [
            EventLog.created_at >= start_date,
            EventLog.created_at <= end_date,
        ]
        if company_id:
            base_filter.append(EventLog.company_id == company_id)

        # Total events
        total_result = await self.db.execute(
            select(func.count()).select_from(EventLog).where(*base_filter)
        )
        total_events = total_result.scalar() or 0

        # By status
        status_result = await self.db.execute(
            select(EventLog.status, func.count())
            .select_from(EventLog)
            .where(*base_filter)
            .group_by(EventLog.status)
        )
        total_by_status = {row[0]: row[1] for row in status_result.all()}

        # By event name (top 20)
        name_result = await self.db.execute(
            select(EventLog.event_name, func.count())
            .select_from(EventLog)
            .where(*base_filter)
            .group_by(EventLog.event_name)
            .order_by(desc(func.count()))
            .limit(20)
        )
        total_by_event_name = {row[0]: row[1] for row in name_result.all()}

        # Failed count
        failed_count = total_by_status.get("failed", 0)

        # Dead letter count
        dl_result = await self.db.execute(
            select(func.count()).select_from(DeadLetterEvent)
        )
        total_dead_letter = dl_result.scalar() or 0

        # Automation triggers
        auto_result = await self.db.execute(
            select(func.count()).select_from(AutomationExecution).where(
                AutomationExecution.created_at >= start_date,
                AutomationExecution.created_at <= end_date,
            )
        )
        total_automation = auto_result.scalar() or 0

        return {
            "total_events": total_events,
            "total_by_status": total_by_status,
            "total_by_event_name": total_by_event_name,
            "total_failed": failed_count,
            "total_dead_letter": total_dead_letter,
            "total_automation_rules_triggered": total_automation,
            "total_webhooks_delivered": total_by_status.get("completed", 0),
            "period_start": start_date,
            "period_end": end_date,
        }


# ---------------------------------------------------------------------------
# EventSubscriptionService
# ---------------------------------------------------------------------------


class EventSubscriptionService:
    """Service for managing event subscriptions: CRUD and matching."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: EventSubscriptionCreate) -> EventSubscription:
        """Create a new event subscription."""
        subscription = EventSubscription(
            company_id=data.company_id,
            event_name=data.event_name,
            handler_type=data.handler_type,
            handler_config=data.handler_config,
            filter_conditions=data.filter_conditions,
            is_active=data.is_active,
            retry_policy=data.retry_policy,
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def get_by_id(self, subscription_id: int) -> Optional[EventSubscription]:
        """Get a subscription by ID."""
        result = await self.db.execute(
            select(EventSubscription).where(EventSubscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def list_subscriptions(
        self,
        company_id: int,
        event_name: Optional[str] = None,
        handler_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[EventSubscription], int]:
        """List subscriptions with filtering."""
        query = select(EventSubscription).where(EventSubscription.company_id == company_id)
        count_query = select(func.count()).select_from(EventSubscription).where(
            EventSubscription.company_id == company_id
        )

        if event_name:
            query = query.where(EventSubscription.event_name == event_name)
            count_query = count_query.where(EventSubscription.event_name == event_name)
        if handler_type:
            query = query.where(EventSubscription.handler_type == handler_type)
            count_query = count_query.where(EventSubscription.handler_type == handler_type)
        if is_active is not None:
            query = query.where(EventSubscription.is_active == is_active)
            count_query = count_query.where(EventSubscription.is_active == is_active)

        query = query.order_by(EventSubscription.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)
        return list(result.scalars().all()), count_result.scalar() or 0

    async def update(
        self,
        subscription_id: int,
        data: EventSubscriptionUpdate,
    ) -> Optional[EventSubscription]:
        """Update an event subscription."""
        subscription = await self.get_by_id(subscription_id)
        if subscription is None:
            return None

        update_fields = ["event_name", "handler_type", "handler_config", "filter_conditions", "is_active", "retry_policy"]
        for field in update_fields:
            value = getattr(data, field, None)
            if value is not None:
                setattr(subscription, field, value)

        subscription.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def delete(self, subscription_id: int) -> bool:
        """Delete a subscription by ID."""
        subscription = await self.get_by_id(subscription_id)
        if subscription is None:
            return False
        await self.db.delete(subscription)
        await self.db.commit()
        return True

    async def find_matching(
        self,
        company_id: int,
        event_name: str,
        payload: Dict[str, Any],
    ) -> List[EventSubscription]:
        """Find all active subscriptions matching an event and payload."""
        result = await self.db.execute(
            select(EventSubscription).where(
                EventSubscription.company_id == company_id,
                EventSubscription.event_name.in_([event_name, "*"]),
                EventSubscription.is_active == True,
            )
        )
        subscriptions = list(result.scalars().all())

        # Apply filter conditions
        matched: List[EventSubscription] = []
        for sub in subscriptions:
            if sub.filter_conditions:
                if self._matches_filter(payload, sub.filter_conditions):
                    matched.append(sub)
            else:
                matched.append(sub)

        return matched

    def _matches_filter(
        self,
        payload: Dict[str, Any],
        conditions: Dict[str, Any],
    ) -> bool:
        """Evaluate filter conditions against a payload.

        Supports simple key=value matching and operators:
        - {field: value} -> equality check
        - {field: {"$eq": value}} -> equality
        - {field: {"$ne": value}} -> not equal
        - {field: {"$gt": value}} -> greater than
        - {field: {"$lt": value}} -> less than
        - {field: {"$in": [values]}} -> contains
        """
        for field, expected in conditions.items():
            actual = payload.get(field)

            if isinstance(expected, dict):
                operator = list(expected.keys())[0] if expected else None
                operand = expected.get(operator)

                if operator == "$eq" and actual != operand:
                    return False
                elif operator == "$ne" and actual == operand:
                    return False
                elif operator == "$gt" and (actual is None or actual <= operand):
                    return False
                elif operator == "$lt" and (actual is None or actual >= operand):
                    return False
                elif operator == "$in" and actual not in operand:
                    return False
            else:
                if actual != expected:
                    return False

        return True


# ---------------------------------------------------------------------------
# EventHandlerService
# ---------------------------------------------------------------------------


class EventHandlerService:
    """Service for executing event handlers with retry and status tracking."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_handler(
        self,
        event_log_id: int,
        handler_type: str,
        handler_name: str,
    ) -> EventHandler:
        """Create a new handler execution record."""
        handler = EventHandler(
            event_log_id=event_log_id,
            handler_type=handler_type,
            handler_name=handler_name,
            status="pending",
            retry_count=0,
        )
        self.db.add(handler)
        await self.db.commit()
        await self.db.refresh(handler)
        return handler

    async def get_handler(self, handler_id: int) -> Optional[EventHandler]:
        """Get a handler execution record by ID."""
        result = await self.db.execute(
            select(EventHandler).where(EventHandler.id == handler_id)
        )
        return result.scalar_one_or_none()

    async def update_handler_status(
        self,
        handler_id: int,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[EventHandler]:
        """Update handler execution status."""
        handler = await self.get_handler(handler_id)
        if handler is None:
            return None

        handler.status = status
        if status == "running" and handler.started_at is None:
            handler.started_at = datetime.utcnow()
        if status in ("completed", "failed"):
            handler.completed_at = datetime.utcnow()
        if output is not None:
            handler.output = output
        if error_message is not None:
            handler.error_message = error_message

        await self.db.commit()
        await self.db.refresh(handler)
        return handler

    async def execute_with_retry(
        self,
        handler: EventHandler,
        exec_func,
        *args,
        **kwargs,
    ) -> bool:
        """Execute a handler function with retry logic.

        Args:
            handler: The EventHandler record to update.
            exec_func: Async function to execute.
            *args, **kwargs: Arguments for the function.

        Returns:
            True if execution succeeded, False if all retries exhausted.
        """
        await self.update_handler_status(handler.id, "running")

        retry_policy = handler.retry_policy if hasattr(handler, "retry_policy") and handler.retry_policy else RETRY_POLICIES["exponential"]
        max_retries = retry_policy.get("max_retries", 5)
        delay = retry_policy.get("delay_seconds", 2)
        multiplier = retry_policy.get("multiplier", 2)
        policy_type = retry_policy.get("type", "exponential")

        current_delay = delay

        for attempt in range(max_retries + 1):
            try:
                result = await exec_func(*args, **kwargs)
                await self.update_handler_status(
                    handler.id, "completed", output=result if isinstance(result, dict) else None
                )
                return True
            except Exception as exc:
                handler.retry_count += 1
                await self.db.commit()

                if attempt >= max_retries:
                    await self.update_handler_status(
                        handler.id, "failed", error_message=str(exc)[:1000]
                    )
                    logger.error(
                        "Handler %s exhausted all %d retries: %s. Moving to DLQ.",
                        handler.handler_name,
                        max_retries,
                        exc,
                    )
                    # Move to Dead Letter Queue after all retries exhausted
                    try:
                        dlq_service = DeadLetterService(self.db)
                        event_log = await self.db.get(EventLog, handler.event_log_id)
                        if event_log:
                            await dlq_service.create(
                                event_log_id=event_log.id,
                                failure_reason=f"Handler '{handler.handler_name}' exhausted all {max_retries} retries",
                                last_error=str(exc)[:2000],
                                original_payload=event_log.payload,
                            )
                            # Update event log status to failed
                            event_log.status = "failed"
                            event_log.error_message = f"Handler exhausted retries: {str(exc)[:500]}"
                            await self.db.commit()
                    except Exception as dlq_exc:
                        logger.error(
                            "Failed to create DLQ entry for handler %s: %s",
                            handler.handler_name,
                            dlq_exc,
                        )
                    return False

                wait_time = 1 if policy_type == "immediate" else current_delay
                logger.warning(
                    "Handler %s attempt %d/%d failed: %s. Retrying in %.1fs",
                    handler.handler_name,
                    attempt + 1,
                    max_retries + 1,
                    exc,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

                if policy_type == "exponential":
                    current_delay *= multiplier

        return False


# ---------------------------------------------------------------------------
# DeadLetterService
# ---------------------------------------------------------------------------


class DeadLetterService:
    """Service for managing the dead letter queue: create, list, resolve, retry."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        event_log_id: int,
        failure_reason: str,
        last_error: Optional[str] = None,
        original_payload: Optional[Dict[str, Any]] = None,
    ) -> DeadLetterEvent:
        """Create a dead letter event entry from a failed event log."""
        log_entry = await self.db.get(EventLog, event_log_id)
        if log_entry is None:
            raise ValueError(f"EventLog {event_log_id} not found")

        dl = DeadLetterEvent(
            event_log_id=event_log_id,
            failure_reason=failure_reason,
            last_error=last_error,
            original_payload=original_payload or log_entry.payload,
            resolution_status="unresolved",
        )
        self.db.add(dl)
        await self.db.commit()
        await self.db.refresh(dl)
        return dl

    async def get_by_id(self, dl_id: int) -> Optional[DeadLetterEvent]:
        """Get a dead letter event by ID."""
        result = await self.db.execute(
            select(DeadLetterEvent).where(DeadLetterEvent.id == dl_id)
        )
        return result.scalar_one_or_none()

    async def list_dead_letters(
        self,
        company_id: Optional[int] = None,
        resolution_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[DeadLetterEvent], int]:
        """List dead letter events with filtering."""
        query = select(DeadLetterEvent)
        count_query = select(func.count()).select_from(DeadLetterEvent)

        if resolution_status:
            query = query.where(DeadLetterEvent.resolution_status == resolution_status)
            count_query = count_query.where(
                DeadLetterEvent.resolution_status == resolution_status
            )

        query = query.order_by(desc(DeadLetterEvent.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)
        return list(result.scalars().all()), count_result.scalar() or 0

    async def resolve(
        self,
        dl_id: int,
        request: DeadLetterResolveRequest,
        resolved_by: Optional[int] = None,
    ) -> Optional[DeadLetterEvent]:
        """Resolve or ignore a dead letter event."""
        dl = await self.get_by_id(dl_id)
        if dl is None:
            return None

        dl.resolution_status = request.resolution
        dl.resolved_at = datetime.utcnow()
        dl.resolved_by = resolved_by

        # Update the parent event log status
        if dl.event_log:
            if request.resolution == "resolved":
                dl.event_log.status = "completed"
            elif request.resolution == "ignored":
                dl.event_log.status = "failed"
            dl.event_log.processed_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(dl)
        return dl

    async def retry_dead_letter(self, dl_id: int) -> Optional[EventLog]:
        """Retry a dead letter event by republishing it."""
        dl = await self.get_by_id(dl_id)
        if dl is None:
            return None

        log_entry = await self.db.get(EventLog, dl.event_log_id)
        if log_entry is None:
            return None

        # Reset the event log
        log_entry.status = "pending"
        log_entry.error_message = None
        log_entry.processed_at = None
        log_entry.retry_count = 0
        await self.db.commit()

        # Mark dead letter as resolved
        dl.resolution_status = "resolved"
        dl.resolved_at = datetime.utcnow()
        await self.db.commit()

        # Republish to event bus
        bus = EventBus()
        await bus.publish(
            event_name=log_entry.event_name,
            payload=log_entry.payload,
            company_id=log_entry.company_id,
            branch_id=log_entry.branch_id,
            source_module=log_entry.source_module,
            user_id=log_entry.source_user_id,
            correlation_id=log_entry.correlation_id,
        )

        return log_entry


# ---------------------------------------------------------------------------
# AutomationRuleService
# ---------------------------------------------------------------------------


class AutomationRuleService:
    """Service for automation rules: CRUD, condition evaluation, action execution."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: AutomationRuleCreate) -> AutomationRule:
        """Create a new automation rule."""
        rule = AutomationRule(
            company_id=data.company_id,
            branch_id=data.branch_id,
            name=data.name,
            description=data.description,
            trigger_event=data.trigger_event,
            conditions=data.conditions,
            actions=data.actions,
            is_active=data.is_active,
            trigger_count=0,
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def get_by_id(self, rule_id: int) -> Optional[AutomationRule]:
        """Get an automation rule by ID with its executions."""
        result = await self.db.execute(
            select(AutomationRule).where(AutomationRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        trigger_event: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AutomationRule], int]:
        """List automation rules with filtering."""
        query = select(AutomationRule).where(AutomationRule.company_id == company_id)
        count_query = select(func.count()).select_from(AutomationRule).where(
            AutomationRule.company_id == company_id
        )

        if branch_id is not None:
            query = query.where(AutomationRule.branch_id == branch_id)
            count_query = count_query.where(AutomationRule.branch_id == branch_id)
        if trigger_event:
            query = query.where(AutomationRule.trigger_event == trigger_event)
            count_query = count_query.where(AutomationRule.trigger_event == trigger_event)
        if is_active is not None:
            query = query.where(AutomationRule.is_active == is_active)
            count_query = count_query.where(AutomationRule.is_active == is_active)

        query = query.order_by(AutomationRule.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)
        return list(result.scalars().all()), count_result.scalar() or 0

    async def update(
        self,
        rule_id: int,
        data: AutomationRuleUpdate,
    ) -> Optional[AutomationRule]:
        """Update an automation rule."""
        rule = await self.get_by_id(rule_id)
        if rule is None:
            return None

        update_fields = ["name", "description", "trigger_event", "conditions", "actions", "is_active"]
        for field in update_fields:
            value = getattr(data, field, None)
            if value is not None:
                setattr(rule, field, value)

        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete(self, rule_id: int) -> bool:
        """Delete an automation rule and its executions."""
        rule = await self.get_by_id(rule_id)
        if rule is None:
            return False
        await self.db.delete(rule)
        await self.db.commit()
        return True

    async def toggle(self, rule_id: int) -> Optional[AutomationRule]:
        """Toggle an automation rule's active state."""
        rule = await self.get_by_id(rule_id)
        if rule is None:
            return None
        rule.is_active = not rule.is_active
        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def find_matching_rules(
        self,
        company_id: int,
        event_name: str,
        branch_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> List[AutomationRule]:
        """Find active automation rules matching an event."""
        query = select(AutomationRule).where(
            AutomationRule.company_id == company_id,
            AutomationRule.trigger_event == event_name,
            AutomationRule.is_active == True,
        )
        if branch_id is not None:
            query = query.where(
                (AutomationRule.branch_id == branch_id) | (AutomationRule.branch_id.is_(None))
            )

        result = await self.db.execute(query)
        rules = list(result.scalars().all())

        # Evaluate conditions
        if payload is not None:
            matched: List[AutomationRule] = []
            for rule in rules:
                if self._evaluate_conditions(rule.conditions, payload):
                    matched.append(rule)
            return matched
        return rules

    def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> bool:
        """Evaluate a list of conditions against a payload.

        Each condition is a dict with:
        - field: dot-notation path in payload (e.g. "order.amount")
        - operator: eq, ne, gt, lt, gte, lte, in, contains, exists
        - value: the comparison value
        - logical: and/or (default: and)
        """
        if not conditions:
            return True  # No conditions = always match

        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "eq")
            value = condition.get("value")
            logical = condition.get("logical", "and")

            actual = self._get_nested_value(payload, field)
            result = self._compare(operator, actual, value)

            if logical == "or" and result:
                return True  # OR: first match wins
            if logical == "and" and not result:
                return False  # AND: first failure fails

        return True

    def _get_nested_value(self, payload: Dict[str, Any], field: str) -> Any:
        """Extract a value from payload using dot notation."""
        parts = field.split(".")
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _compare(self, operator: str, actual: Any, expected: Any) -> bool:
        """Compare actual value against expected using the given operator."""
        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "gt":
            return actual is not None and expected is not None and actual > expected
        elif operator == "lt":
            return actual is not None and expected is not None and actual < expected
        elif operator == "gte":
            return actual is not None and expected is not None and actual >= expected
        elif operator == "lte":
            return actual is not None and expected is not None and actual <= expected
        elif operator == "in":
            return actual in expected if expected is not None else False
        elif operator == "contains":
            return expected in actual if actual is not None else False
        elif operator == "exists":
            return actual is not None
        return False

    async def execute_actions(
        self,
        rule: AutomationRule,
        trigger_event_id: Optional[int],
        payload: Dict[str, Any],
    ) -> AutomationExecution:
        """Execute the actions of an automation rule.

        Returns:
            AutomationExecution record tracking the execution.
        """
        execution = AutomationExecution(
            rule_id=rule.id,
            trigger_event_id=trigger_event_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)

        from app.events.bus import EventBus

        actions_executed: List[Dict[str, Any]] = []
        has_error = False

        for action in rule.actions:
            action_type = action.get("type", "")
            action_result: Dict[str, Any] = {"type": action_type, "success": False}

            try:
                if action_type == "webhook":
                    url = action.get("url", "")
                    webhook_payload = {
                        "event": payload,
                        "rule": rule.name,
                        "triggered_at": datetime.utcnow().isoformat(),
                    }
                    result = await deliver_webhook(
                        url=url,
                        payload=webhook_payload,
                        secret=action.get("secret"),
                        headers=action.get("headers"),
                        timeout_seconds=action.get("timeout", 30),
                    )
                    action_result["success"] = result["success"]
                    action_result["detail"] = result

                elif action_type == "notification":
                    # Queue a notification via Redis
                    redis = await get_redis_client()
                    notif_data = {
                        "type": action.get("notif_type", "info"),
                        "title": action.get("title", f"Automation: {rule.name}"),
                        "message": action.get("message", ""),
                        "user_id": action.get("user_id"),
                        "company_id": rule.company_id,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    channel = action.get("channel", "notifications:queue")
                    await redis.publish(channel, __import__("json").dumps(notif_data))
                    action_result["success"] = True

                elif action_type == "publish_event":
                    event_name = action.get("event_name", "")
                    event_payload = action.get("payload", {})
                    # Merge with trigger payload
                    merged = {**payload, **event_payload}
                    bus = EventBus()
                    correlation_id = await bus.publish(
                        event_name=event_name,
                        payload=merged,
                        company_id=rule.company_id,
                        branch_id=rule.branch_id,
                        correlation_id=str(uuid.uuid4()),
                    )
                    action_result["success"] = True
                    action_result["correlation_id"] = correlation_id

                elif action_type == "delay":
                    delay_seconds = action.get("seconds", 0)
                    await asyncio.sleep(delay_seconds)
                    action_result["success"] = True

                else:
                    action_result["error"] = f"Unknown action type: {action_type}"

            except Exception as exc:
                action_result["success"] = False
                action_result["error"] = str(exc)
                has_error = True
                logger.error(
                    "Automation action failed for rule %d: %s",
                    rule.id,
                    exc,
                )

            actions_executed.append(action_result)

        execution.status = "failed" if has_error else "completed"
        execution.completed_at = datetime.utcnow()
        execution.actions_executed = actions_executed

        # Update rule stats
        rule.last_triggered_at = datetime.utcnow()
        rule.trigger_count += 1

        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    async def list_executions(
        self,
        rule_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AutomationExecution], int]:
        """List automation executions with filtering."""
        query = select(AutomationExecution)
        count_query = select(func.count()).select_from(AutomationExecution)

        if rule_id:
            query = query.where(AutomationExecution.rule_id == rule_id)
            count_query = count_query.where(AutomationExecution.rule_id == rule_id)
        if status:
            query = query.where(AutomationExecution.status == status)
            count_query = count_query.where(AutomationExecution.status == status)

        query = query.order_by(desc(AutomationExecution.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)
        return list(result.scalars().all()), count_result.scalar() or 0


# ---------------------------------------------------------------------------
# NotificationTriggerService
# ---------------------------------------------------------------------------


class NotificationTriggerService:
    """Service for triggering notifications on event occurrences.

    Integrates with the existing notifications module by pushing notification
    data to a Redis queue that the notifications worker consumes.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger(
        self,
        notif_type: str,
        title: str,
        message: str,
        user_id: Optional[int] = None,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Trigger a notification by publishing to Redis.

        Args:
            notif_type: Notification type (info, warning, success, error).
            title: Notification title.
            message: Notification body.
            user_id: Target user ID (None = broadcast to company).
            company_id: Target company ID.
            branch_id: Target branch ID.
            metadata: Additional data to attach.

        Returns:
            True if the notification was queued successfully.
        """
        try:
            redis = await get_redis_client()
            notif_data = {
                "id": str(uuid.uuid4()),
                "type": notif_type,
                "title": title,
                "message": message,
                "user_id": user_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "metadata": metadata or {},
                "is_read": False,
                "created_at": datetime.utcnow().isoformat(),
            }
            await redis.publish("notifications:queue", __import__("json").dumps(notif_data))

            # Also store in user's notification list if user_id provided
            if user_id:
                key = f"notifications:{user_id}"
                await redis.lpush(key, __import__("json").dumps(notif_data))
                await redis.ltrim(key, 0, 99)  # Keep last 100

            return True
        except Exception as exc:
            logger.error("Failed to trigger notification: %s", exc)
            return False

    async def trigger_on_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
    ) -> bool:
        """Trigger a contextual notification based on an event type.

        Maps common events to human-readable notification messages.
        """
        event_templates = {
            "erp_sync_completed": {
                "type": "success",
                "title": "ERP Sync Completed",
                "message": "ERP synchronization completed successfully.",
            },
            "erp_sync_failed": {
                "type": "error",
                "title": "ERP Sync Failed",
                "message": "ERP synchronization failed. Check the event log for details.",
            },
            "review_received": {
                "type": "info",
                "title": "New Review Received",
                "message": "A new customer review has been received.",
            },
            "inventory_low": {
                "type": "warning",
                "title": "Low Inventory Alert",
                "message": "Inventory levels are running low for one or more items.",
            },
            "order_created": {
                "type": "success",
                "title": "New Order",
                "message": "A new order has been placed.",
            },
            "payment_received": {
                "type": "success",
                "title": "Payment Received",
                "message": "A new payment has been received.",
            },
            "campaign_created": {
                "type": "info",
                "title": "Campaign Created",
                "message": "A new marketing campaign has been created.",
            },
            "ai_request_completed": {
                "type": "success",
                "title": "AI Request Complete",
                "message": "Your AI content generation request is complete.",
            },
        }

        template = event_templates.get(event_name)
        if template is None:
            return False

        return await self.trigger(
            notif_type=template["type"],
            title=template["title"],
            message=template["message"],
            company_id=company_id,
            branch_id=branch_id,
            metadata={"event_name": event_name, "payload": payload},
        )


# ---------------------------------------------------------------------------
# WebhookDeliveryService
# ---------------------------------------------------------------------------


class WebhookDeliveryService:
    """Service for delivering webhooks with signature verification,
    retry logic, and timeout handling.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def deliver(
        self,
        url: str,
        payload: Dict[str, Any],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout_seconds: int = WEBHOOK_DEFAULT_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        """Deliver a webhook payload to a URL.

        Args:
            url: The webhook endpoint URL.
            payload: JSON payload to send.
            secret: Optional HMAC secret for signature.
            headers: Additional HTTP headers.
            timeout_seconds: Request timeout.

        Returns:
            Dict with delivery result information.
        """
        return await deliver_webhook(
            url=url,
            payload=payload,
            secret=secret,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )

    async def deliver_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout_seconds: int = WEBHOOK_DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = WEBHOOK_MAX_RETRIES,
        delay_seconds: float = 2.0,
    ) -> Dict[str, Any]:
        """Deliver a webhook with automatic retry on failure.

        Uses exponential backoff for retries.
        """
        for attempt in range(max_retries + 1):
            result = await self.deliver(
                url=url,
                payload=payload,
                secret=secret,
                headers=headers,
                timeout_seconds=timeout_seconds,
            )

            if result["success"]:
                return {**result, "attempts": attempt + 1}

            if attempt >= max_retries:
                return {**result, "attempts": attempt + 1, "retries_exhausted": True}

            wait_time = delay_seconds * (2 ** attempt)
            logger.warning(
                "Webhook delivery to %s failed (attempt %d/%d). Retrying in %.1fs",
                url,
                attempt + 1,
                max_retries + 1,
                wait_time,
            )
            await asyncio.sleep(wait_time)

        return {**result, "attempts": max_retries + 1, "retries_exhausted": True}

    async def verify_signature(
        self,
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify an incoming webhook signature.

        Args:
            payload: The raw request body as a string.
            signature: The signature header value (e.g. "sha256=abc123").
            secret: The shared secret used to generate the signature.

        Returns:
            True if the signature is valid.
        """
        import hmac
        import hashlib

        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        provided = signature[7:]  # Remove "sha256=" prefix
        return hmac.compare_digest(expected, provided)
