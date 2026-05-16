"""Router for the Event Bus & Automation module.

Provides REST endpoints for:
- Event definitions (CRUD)
- Event subscriptions (CRUD)
- Event log (list, detail, retry)
- Dead letter queue (list, resolve, retry)
- Automation rules (CRUD, toggle)
- Automation executions (list)
- Event statistics
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.events.bus import EventBus, get_event_bus
from app.events.constants import BUSINESS_EVENT_TYPES, SYSTEM_EVENT_TYPES
from app.events.schemas import (
    AutomationExecutionListResponse,
    AutomationExecutionResponse,
    AutomationRuleCreate,
    AutomationRuleListResponse,
    AutomationRuleResponse,
    AutomationRuleToggleResponse,
    AutomationRuleUpdate,
    DeadLetterEventListResponse,
    DeadLetterEventResponse,
    DeadLetterResolveRequest,
    DeadLetterResolveResponse,
    DeadLetterRetryResponse,
    EventDefinitionCreate,
    EventDefinitionListResponse,
    EventDefinitionResponse,
    EventDefinitionUpdate,
    EventLogListResponse,
    EventLogResponse,
    EventPublishRequest,
    EventPublishResponse,
    EventRetryRequest,
    EventRetryResponse,
    EventStatsResponse,
    EventSubscriptionCreate,
    EventSubscriptionListResponse,
    EventSubscriptionResponse,
    EventSubscriptionUpdate,
    PaginatedResponse,
)
from app.events.service import (
    AutomationRuleService,
    DeadLetterService,
    EventHandlerService,
    EventLogService,
    EventSubscriptionService,
)
from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tenant_filter(user: User) -> dict:
    """Build tenant filter dict based on user role."""
    filters = {}
    if user.company_id is not None:
        filters["company_id"] = user.company_id
    if user.branch_id is not None:
        filters["branch_id"] = user.branch_id
    return filters


# ---------------------------------------------------------------------------
# Event Definitions
# ---------------------------------------------------------------------------


@router.get(
    "/definitions",
    response_model=EventDefinitionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List event definitions",
)
async def list_event_definitions(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category (system/business/integration)"),
    is_system: Optional[bool] = Query(None, description="Filter system definitions"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventDefinitionListResponse:
    """List event definitions with optional filtering.

    Returns system event definitions plus any company-specific definitions.
    """
    service = EventLogService(db)

    from sqlalchemy import desc, or_
    from sqlalchemy import select as sa_select
    from app.events.models import EventDefinition

    query = sa_select(EventDefinition)
    count_query = sa_select(__import__("sqlalchemy").func.count()).select_from(EventDefinition)

    # Tenant isolation: show system events OR company-specific events
    if current_user.role not in ("super_admin",):
        if current_user.company_id:
            query = query.where(
                or_(
                    EventDefinition.is_system == True,
                    EventDefinition.company_id == current_user.company_id,
                )
            )
            count_query = count_query.where(
                or_(
                    EventDefinition.is_system == True,
                    EventDefinition.company_id == current_user.company_id,
                )
            )
    else:
        # Super admin sees all definitions
        pass

    if category:
        query = query.where(EventDefinition.category == category)
        count_query = count_query.where(EventDefinition.category == category)
    if is_system is not None:
        query = query.where(EventDefinition.is_system == is_system)
        count_query = count_query.where(EventDefinition.is_system == is_system)

    query = query.order_by(desc(EventDefinition.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    count_result = await db.execute(count_query)

    items = list(result.scalars().all())
    total = count_result.scalar() or 0

    return EventDefinitionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[EventDefinitionResponse.model_validate(item) for item in items],
    )


@router.post(
    "/definitions",
    response_model=EventDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event definition",
)
async def create_event_definition(
    request: Request,
    data: EventDefinitionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventDefinitionResponse:
    """Create a new event definition.

    Event definitions describe the schema and metadata for custom events.
    System events are pre-seeded and cannot be created through this endpoint.
    """
    from app.events.models import EventDefinition

    if data.is_system and current_user.role not in ("super_admin",):
        raise ValidationError(detail="Only super admins can create system event definitions")

    definition = EventDefinition(
        company_id=data.company_id or current_user.company_id,
        event_name=data.event_name,
        description=data.description,
        payload_schema=data.payload_schema,
        category=data.category,
        is_system=data.is_system,
    )
    db.add(definition)
    await db.commit()
    await db.refresh(definition)
    return EventDefinitionResponse.model_validate(definition)


# ---------------------------------------------------------------------------
# Event Subscriptions
# ---------------------------------------------------------------------------


@router.get(
    "/subscriptions",
    response_model=EventSubscriptionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List event subscriptions",
)
async def list_subscriptions(
    request: Request,
    event_name: Optional[str] = Query(None, description="Filter by event name"),
    handler_type: Optional[str] = Query(None, description="Filter by handler type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSubscriptionListResponse:
    """List event subscriptions for the current user's company."""
    service = EventSubscriptionService(db)

    company_id = current_user.company_id
    if not company_id:
        raise ValidationError(detail="User must belong to a company to manage subscriptions")

    items, total = await service.list_subscriptions(
        company_id=company_id,
        event_name=event_name,
        handler_type=handler_type,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return EventSubscriptionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[EventSubscriptionResponse.model_validate(item) for item in items],
    )


@router.post(
    "/subscriptions",
    response_model=EventSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event subscription",
)
async def create_subscription(
    request: Request,
    data: EventSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSubscriptionResponse:
    """Create a new event subscription.

    Subscriptions link event names to handler configurations. When an event
    matching the subscription is published, the configured handler is invoked.
    """
    service = EventSubscriptionService(db)

    if data.company_id != current_user.company_id and current_user.role != "super_admin":
        raise ValidationError(detail="Cannot create subscriptions for other companies")

    subscription = await service.create(data)
    return EventSubscriptionResponse.model_validate(subscription)


@router.put(
    "/subscriptions/{subscription_id}",
    response_model=EventSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an event subscription",
)
async def update_subscription(
    request: Request,
    subscription_id: int,
    data: EventSubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSubscriptionResponse:
    """Update an existing event subscription."""
    service = EventSubscriptionService(db)

    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        raise NotFoundError(detail=f"Subscription {subscription_id} not found")

    if (
        subscription.company_id != current_user.company_id
        and current_user.role != "super_admin"
    ):
        raise ValidationError(detail="Cannot update subscriptions for other companies")

    updated = await service.update(subscription_id, data)
    if updated is None:
        raise NotFoundError(detail=f"Subscription {subscription_id} not found")
    return EventSubscriptionResponse.model_validate(updated)


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event subscription",
)
async def delete_subscription(
    request: Request,
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an event subscription by ID."""
    service = EventSubscriptionService(db)

    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        raise NotFoundError(detail=f"Subscription {subscription_id} not found")

    if (
        subscription.company_id != current_user.company_id
        and current_user.role != "super_admin"
    ):
        raise ValidationError(detail="Cannot delete subscriptions for other companies")

    await service.delete(subscription_id)


# ---------------------------------------------------------------------------
# Event Log
# ---------------------------------------------------------------------------


@router.get(
    "/log",
    response_model=EventLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List event log entries",
)
async def list_event_log(
    request: Request,
    event_name: Optional[str] = Query(None, description="Filter by event name"),
    status: Optional[str] = Query(None, description="Filter by status (pending/processing/completed/failed)"),
    source_module: Optional[str] = Query(None, description="Filter by source module"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    start_date: Optional[datetime] = Query(None, description="Filter from date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter to date (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventLogListResponse:
    """List event log entries with filtering and pagination.

    Results are scoped to the current user's company and optionally branch.
    """
    service = EventLogService(db)

    company_id = current_user.company_id
    branch_id = current_user.branch_id

    if current_user.role == "super_admin":
        company_id = None  # Super admin sees all
        branch_id = None

    items, total = await service.list_events(
        company_id=company_id,
        branch_id=branch_id,
        event_name=event_name,
        status=status,
        source_module=source_module,
        correlation_id=correlation_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )

    return EventLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[EventLogResponse.model_validate(item) for item in items],
    )


@router.get(
    "/log/{log_id}",
    response_model=EventLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get event log detail",
)
async def get_event_log(
    request: Request,
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventLogResponse:
    """Get a single event log entry with its handler executions."""
    service = EventLogService(db)

    log_entry = await service.get_by_id(log_id)
    if log_entry is None:
        raise NotFoundError(detail=f"Event log {log_id} not found")

    # Tenant isolation check
    if (
        current_user.role != "super_admin"
        and log_entry.company_id is not None
        and log_entry.company_id != current_user.company_id
    ):
        raise ValidationError(detail="Access denied for this event log entry")

    return EventLogResponse.model_validate(log_entry)


@router.post(
    "/log/{log_id}/retry",
    response_model=EventRetryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry a failed event",
)
async def retry_event_log(
    request: Request,
    log_id: int,
    retry_request: Optional[EventRetryRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventRetryResponse:
    """Retry a failed event by republishing it to the event bus.

    Only events with status 'failed' can be retried.
    """
    service = EventLogService(db)

    log_entry = await service.get_by_id(log_id)
    if log_entry is None:
        raise NotFoundError(detail=f"Event log {log_id} not found")

    if (
        current_user.role != "super_admin"
        and log_entry.company_id is not None
        and log_entry.company_id != current_user.company_id
    ):
        raise ValidationError(detail="Access denied for this event log entry")

    if log_entry.status != "failed":
        raise ValidationError(
            detail=f"Cannot retry event with status '{log_entry.status}'. Only 'failed' events can be retried."
        )

    result = await service.retry_event(log_id, retry_request)
    if result is None:
        raise NotFoundError(detail=f"Event log {log_id} not found or not retryable")

    return EventRetryResponse(
        success=True,
        message=f"Event {log_id} queued for retry",
        event_log_id=log_id,
    )


# ---------------------------------------------------------------------------
# Dead Letter Queue
# ---------------------------------------------------------------------------


@router.get(
    "/dead-letter",
    response_model=DeadLetterEventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List dead letter events",
)
async def list_dead_letters(
    request: Request,
    resolution_status: Optional[str] = Query(None, description="Filter by resolution status (unresolved/resolved/ignored)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeadLetterEventListResponse:
    """List dead letter events with optional filtering.

    Dead letter events are failed events that have exhausted all retries.
    They require manual inspection and resolution.
    """
    service = DeadLetterService(db)

    # Note: Dead letter entries are linked to event logs which have company_id
    # For now, we list all and filter at the service level
    items, total = await service.list_dead_letters(
        resolution_status=resolution_status,
        page=page,
        page_size=page_size,
    )

    return DeadLetterEventListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[DeadLetterEventResponse.model_validate(item) for item in items],
    )


@router.post(
    "/dead-letter/{dl_id}/resolve",
    response_model=DeadLetterResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a dead letter event",
)
async def resolve_dead_letter(
    request: Request,
    dl_id: int,
    data: DeadLetterResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeadLetterResolveResponse:
    """Resolve or ignore a dead letter event.

    - "resolved": Mark the event as resolved (do not retry)
    - "ignored": Mark the event as ignored (do not retry)
    """
    service = DeadLetterService(db)

    dl = await service.get_by_id(dl_id)
    if dl is None:
        raise NotFoundError(detail=f"Dead letter event {dl_id} not found")

    if data.resolution not in ("resolved", "ignored"):
        raise ValidationError(detail="Resolution must be 'resolved' or 'ignored'")

    resolved = await service.resolve(dl_id, data, resolved_by=current_user.id)
    if resolved is None:
        raise NotFoundError(detail=f"Dead letter event {dl_id} not found")

    return DeadLetterResolveResponse(
        success=True,
        message=f"Dead letter event {dl_id} marked as {data.resolution}",
        dead_letter_id=dl_id,
        resolution_status=data.resolution,
    )


@router.post(
    "/dead-letter/{dl_id}/retry",
    response_model=DeadLetterRetryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry a dead letter event",
)
async def retry_dead_letter(
    request: Request,
    dl_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeadLetterRetryResponse:
    """Retry a dead letter event by republishing it to the event bus.

    This creates a new event log entry with fresh retry count.
    """
    service = DeadLetterService(db)

    dl = await service.get_by_id(dl_id)
    if dl is None:
        raise NotFoundError(detail=f"Dead letter event {dl_id} not found")

    result = await service.retry_dead_letter(dl_id)
    if result is None:
        raise NotFoundError(detail=f"Dead letter event {dl_id} could not be retried")

    return DeadLetterRetryResponse(
        success=True,
        message=f"Dead letter event {dl_id} queued for retry",
        dead_letter_id=dl_id,
        new_event_log_id=result.id,
    )


# ---------------------------------------------------------------------------
# Automation Rules
# ---------------------------------------------------------------------------


@router.get(
    "/automation-rules",
    response_model=AutomationRuleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List automation rules",
)
async def list_automation_rules(
    request: Request,
    trigger_event: Optional[str] = Query(None, description="Filter by trigger event name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleListResponse:
    """List automation rules for the current user's company."""
    service = AutomationRuleService(db)

    company_id = current_user.company_id
    branch_id = current_user.branch_id

    if current_user.role == "super_admin":
        company_id = company_id  # Keep company context even for super admin
        branch_id = None

    if not company_id:
        raise ValidationError(detail="User must belong to a company to manage automation rules")

    items, total = await service.list_rules(
        company_id=company_id,
        branch_id=branch_id,
        trigger_event=trigger_event,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return AutomationRuleListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AutomationRuleResponse.model_validate(item) for item in items],
    )


@router.post(
    "/automation-rules",
    response_model=AutomationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an automation rule",
)
async def create_automation_rule(
    request: Request,
    data: AutomationRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    """Create a new automation rule.

    Automation rules define trigger events, conditions, and actions.
    When an event matches the trigger and conditions pass, all actions
    are executed sequentially.
    """
    service = AutomationRuleService(db)

    if data.company_id != current_user.company_id and current_user.role != "super_admin":
        raise ValidationError(detail="Cannot create rules for other companies")

    rule = await service.create(data)
    return AutomationRuleResponse.model_validate(rule)


@router.put(
    "/automation-rules/{rule_id}",
    response_model=AutomationRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an automation rule",
)
async def update_automation_rule(
    request: Request,
    rule_id: int,
    data: AutomationRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    """Update an existing automation rule."""
    service = AutomationRuleService(db)

    rule = await service.get_by_id(rule_id)
    if rule is None:
        raise NotFoundError(detail=f"Automation rule {rule_id} not found")

    if (
        rule.company_id != current_user.company_id
        and current_user.role != "super_admin"
    ):
        raise ValidationError(detail="Cannot update rules for other companies")

    updated = await service.update(rule_id, data)
    if updated is None:
        raise NotFoundError(detail=f"Automation rule {rule_id} not found")
    return AutomationRuleResponse.model_validate(updated)


@router.delete(
    "/automation-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an automation rule",
)
async def delete_automation_rule(
    request: Request,
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an automation rule and its execution history."""
    service = AutomationRuleService(db)

    rule = await service.get_by_id(rule_id)
    if rule is None:
        raise NotFoundError(detail=f"Automation rule {rule_id} not found")

    if (
        rule.company_id != current_user.company_id
        and current_user.role != "super_admin"
    ):
        raise ValidationError(detail="Cannot delete rules for other companies")

    await service.delete(rule_id)


@router.post(
    "/automation-rules/{rule_id}/toggle",
    response_model=AutomationRuleToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle automation rule active state",
)
async def toggle_automation_rule(
    request: Request,
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleToggleResponse:
    """Toggle an automation rule between active and inactive."""
    service = AutomationRuleService(db)

    rule = await service.get_by_id(rule_id)
    if rule is None:
        raise NotFoundError(detail=f"Automation rule {rule_id} not found")

    if (
        rule.company_id != current_user.company_id
        and current_user.role != "super_admin"
    ):
        raise ValidationError(detail="Cannot toggle rules for other companies")

    updated = await service.toggle(rule_id)
    if updated is None:
        raise NotFoundError(detail=f"Automation rule {rule_id} not found")

    return AutomationRuleToggleResponse(
        success=True,
        rule_id=rule_id,
        is_active=updated.is_active,
        message=f"Rule {rule_id} is now {'active' if updated.is_active else 'inactive'}",
    )


# ---------------------------------------------------------------------------
# Automation Executions
# ---------------------------------------------------------------------------


@router.get(
    "/automation-executions",
    response_model=AutomationExecutionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List automation executions",
)
async def list_automation_executions(
    request: Request,
    rule_id: Optional[int] = Query(None, description="Filter by rule ID"),
    status: Optional[str] = Query(None, description="Filter by execution status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutomationExecutionListResponse:
    """List automation execution history with optional filtering."""
    service = AutomationRuleService(db)

    items, total = await service.list_executions(
        rule_id=rule_id,
        status=status,
        page=page,
        page_size=page_size,
    )

    return AutomationExecutionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AutomationExecutionResponse.model_validate(item) for item in items],
    )


# ---------------------------------------------------------------------------
# Event Statistics
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=EventStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get event statistics",
)
async def get_event_stats(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventStatsResponse:
    """Get event statistics for the specified time period.

    Returns aggregate counts by status, event name, and other key metrics.
    """
    service = EventLogService(db)

    company_id = current_user.company_id
    if current_user.role == "super_admin":
        company_id = None

    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()

    stats = await service.get_stats(
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
    )

    return EventStatsResponse(**stats)


# ---------------------------------------------------------------------------
# Event Publishing (for testing/admin)
# ---------------------------------------------------------------------------


@router.post(
    "/publish",
    response_model=EventPublishResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish an event to the event bus",
)
async def publish_event(
    request: Request,
    data: EventPublishRequest,
    bus: EventBus = Depends(get_event_bus),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventPublishResponse:
    """Publish an event directly to the event bus.

    This endpoint is primarily for testing and admin use.
    In production, events should be published by the respective modules.
    """
    company_id = data.company_id or current_user.company_id
    branch_id = data.branch_id or current_user.branch_id

    correlation_id = await bus.publish(
        event_name=data.event_name,
        payload=data.payload,
        company_id=company_id,
        branch_id=branch_id,
        source_module=data.source_module,
        user_id=current_user.id,
        correlation_id=data.correlation_id,
    )

    return EventPublishResponse(
        success=True,
        correlation_id=correlation_id,
        message=f"Event '{data.event_name}' published successfully",
    )


# ---------------------------------------------------------------------------
# System Event Types
# ---------------------------------------------------------------------------


@router.get(
    "/event-types",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List all available event types",
)
async def list_event_types(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all system and business event types available in the platform."""
    return {
        "success": True,
        "data": {
            "system": SYSTEM_EVENT_TYPES,
            "business": BUSINESS_EVENT_TYPES,
            "all": SYSTEM_EVENT_TYPES + BUSINESS_EVENT_TYPES,
        },
    }
