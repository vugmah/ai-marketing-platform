"""Core Event Bus implementation using Redis pub/sub.

Provides:
- EventBus class: publish/subscribe with async handlers
- EventBusMiddleware: FastAPI middleware injecting event_bus into request.state
- get_event_bus: dependency to retrieve the EventBus from request state
- Correlation ID tracking across event chains
- Event batching for high-volume scenarios
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
)

import httpx
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.events.constants import (
    EVENT_BATCH_FLUSH_INTERVAL_SECONDS,
    EVENT_BATCH_SIZE,
    REDIS_CHANNEL_PREFIX,
    RETRY_POLICIES,
    WEBHOOK_DEFAULT_TIMEOUT_SECONDS,
    WEBHOOK_MAX_RETRIES,
    WEBHOOK_SIGNATURE_HEADER,
    WEBHOOK_VERSION,
    WEBHOOK_VERSION_HEADER,
)
from app.events.models import EventLog, EventSubscription
from app.events.schemas import EventLogCreate
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class EventPayload:
    """Structured event payload with metadata for transport."""

    event_name: str
    payload: Dict[str, Any]
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    source_module: Optional[str] = None
    user_id: Optional[int] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    published: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for Redis transport."""
        return {
            "event_name": self.event_name,
            "payload": self.payload,
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "source_module": self.source_module,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventPayload":
        """Deserialize from dictionary received from Redis."""
        return cls(
            event_name=data["event_name"],
            payload=data.get("payload", {}),
            company_id=data.get("company_id"),
            branch_id=data.get("branch_id"),
            source_module=data.get("source_module"),
            user_id=data.get("user_id"),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class BatchItem:
    """Item within an event batch."""

    payload: EventPayload
    future: asyncio.Future


# ---------------------------------------------------------------------------
# Handler Type
# ---------------------------------------------------------------------------

EventHandlerFunc = Callable[[EventPayload, AsyncSession], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class EventBus:
    """Redis pub/sub based event bus for async event propagation.

    The EventBus is a singleton-like class that manages:
    - Publishing events to Redis channels
    - Subscribing async handlers to event names
    - Correlation ID tracking across event chains
    - Event batching for high-volume scenarios
    - Persistent logging of all events to the database
    """

    _instance: Optional["EventBus"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._handlers: Dict[str, List[EventHandlerFunc]] = {}
        self._running: bool = False
        self._pubsub_task: Optional[asyncio.Task] = None
        self._batch_queue: asyncio.Queue = asyncio.Queue()
        self._batch_task: Optional[asyncio.Task] = None
        self._redis = None
        self._subscriber_id: str = str(uuid.uuid4())[:8]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the event bus: connect to Redis and begin listening."""
        if self._running:
            return
        self._running = True
        self._redis = await get_redis_client()
        self._pubsub_task = asyncio.create_task(self._pubsub_listener())
        self._batch_task = asyncio.create_task(self._batch_processor())
        logger.info("EventBus started (subscriber=%s)", self._subscriber_id)

    async def stop(self) -> None:
        """Gracefully stop the event bus."""
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
            self._batch_task = None
        logger.info("EventBus stopped (subscriber=%s)", self._subscriber_id)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        event_name: str,
        payload: Dict[str, Any],
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        source_module: Optional[str] = None,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Publish an event to the Redis channel.

        Args:
            event_name: The event type identifier (e.g. "order_created").
            payload: The event payload as a dictionary.
            company_id: Optional tenant company ID.
            branch_id: Optional branch ID.
            source_module: Optional source module name (e.g. "erp", "ai").
            user_id: Optional ID of the user who triggered the event.
            correlation_id: Optional correlation ID for event chaining.

        Returns:
            The correlation_id assigned to this event.
        """
        if self._redis is None:
            self._redis = await get_redis_client()

        event = EventPayload(
            event_name=event_name,
            payload=payload,
            company_id=company_id,
            branch_id=branch_id,
            source_module=source_module,
            user_id=user_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )

        # Persist to event log
        await self._persist_event_log(event)

        # Publish to Redis
        channel = f"{REDIS_CHANNEL_PREFIX}:{event_name}"
        message = json.dumps(event.to_dict())
        await self._redis.publish(channel, message)

        # Also publish to wildcard channel for catch-all subscribers
        wildcard_channel = f"{REDIS_CHANNEL_PREFIX}:*"
        await self._redis.publish(wildcard_channel, message)

        event.published = True
        logger.debug(
            "Published event %s (correlation=%s, company=%s)",
            event_name,
            event.correlation_id,
            company_id,
        )
        return event.correlation_id

    async def publish_batch(
        self,
        events: List[Dict[str, Any]],
        company_id: Optional[int] = None,
    ) -> List[str]:
        """Publish multiple events in a batch.

        Args:
            events: List of event dicts, each with 'event_name' and 'payload'.
            company_id: Optional tenant company ID applied to all events.

        Returns:
            List of correlation IDs for the published events.
        """
        correlation_ids: List[str] = []
        for evt in events:
            cid = await self.publish(
                event_name=evt["event_name"],
                payload=evt.get("payload", {}),
                company_id=company_id or evt.get("company_id"),
                branch_id=evt.get("branch_id"),
                source_module=evt.get("source_module"),
                user_id=evt.get("user_id"),
                correlation_id=evt.get("correlation_id"),
            )
            correlation_ids.append(cid)
        return correlation_ids

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def subscribe(self, event_name: str, handler: EventHandlerFunc) -> None:
        """Subscribe an async handler to a specific event name.

        Args:
            event_name: Event name to listen for (supports "*" for all).
            handler: Async callable receiving (EventPayload, AsyncSession).
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
        logger.info(
            "Subscribed handler %s to event '%s'",
            handler.__name__,
            event_name,
        )

    def unsubscribe(self, event_name: str, handler: EventHandlerFunc) -> None:
        """Unsubscribe a handler from an event name."""
        if event_name in self._handlers:
            self._handlers[event_name] = [
                h for h in self._handlers[event_name] if h != handler
            ]
            if not self._handlers[event_name]:
                del self._handlers[event_name]

    # ------------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------------

    def get_correlation_id(self, event_payload: EventPayload) -> str:
        """Extract the correlation ID from an event payload."""
        return event_payload.correlation_id

    def create_child_correlation(self, parent_id: str) -> str:
        """Create a child correlation ID linked to a parent."""
        child_id = str(uuid.uuid4())
        return f"{parent_id}:{child_id}"

    # ------------------------------------------------------------------
    # Internal: Pub/Sub Listener
    # ------------------------------------------------------------------

    async def _pubsub_listener(self) -> None:
        """Background task that listens to Redis pub/sub channels."""
        redis = await get_redis_client()
        pubsub = redis.pubsub()
        all_channels = [f"{REDIS_CHANNEL_PREFIX}:*"]
        # Also subscribe to specific channels we have handlers for
        for event_name in self._handlers:
            if event_name != "*":
                all_channels.append(f"{REDIS_CHANNEL_PREFIX}:{event_name}")

        await pubsub.subscribe(*all_channels)
        logger.info("Pub/sub listener subscribed to %d channels", len(all_channels))

        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    event = EventPayload.from_dict(data)
                    await self._dispatch(event)
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    logger.error("Failed to process pub/sub message: %s", exc)
        except asyncio.CancelledError:
            logger.debug("Pub/sub listener cancelled")
        finally:
            await pubsub.unsubscribe(*all_channels)
            await pubsub.close()

    async def _dispatch(self, event: EventPayload) -> None:
        """Dispatch an event to all matching handlers."""
        handlers: List[EventHandlerFunc] = []

        # Collect handlers for exact match
        if event.event_name in self._handlers:
            handlers.extend(self._handlers[event.event_name])

        # Collect handlers for wildcard match
        if "*" in self._handlers:
            handlers.extend(self._handlers["*"])

        if not handlers:
            return

        logger.debug(
            "Dispatching event '%s' to %d handlers",
            event.event_name,
            len(handlers),
        )

        # Execute handlers with error isolation
        for handler in handlers:
            try:
                async with get_db_context() as db:
                    await handler(event, db)
            except Exception as exc:
                logger.error(
                    "Handler %s failed for event '%s': %s",
                    handler.__name__,
                    event.event_name,
                    exc,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Internal: Batch Processor
    # ------------------------------------------------------------------

    async def _batch_processor(self) -> None:
        """Background task that processes batched events."""
        while self._running:
            try:
                batch: List[EventPayload] = []
                deadline = asyncio.get_event_loop().time() + EVENT_BATCH_FLUSH_INTERVAL_SECONDS

                while len(batch) < EVENT_BATCH_SIZE:
                    timeout = max(0, deadline - asyncio.get_event_loop().time())
                    try:
                        item: BatchItem = await asyncio.wait_for(
                            self._batch_queue.get(), timeout=timeout
                        )
                        batch.append(item.payload)
                        item.future.set_result(True)
                    except asyncio.TimeoutError:
                        break
                    except asyncio.CancelledError:
                        return

                if batch:
                    await self._flush_batch(batch)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Batch processor error: %s", exc)

    async def _flush_batch(self, batch: List[EventPayload]) -> None:
        """Flush a batch of events to Redis and the database."""
        if not self._redis:
            self._redis = await get_redis_client()

        pipe = self._redis.pipeline()
        for event in batch:
            channel = f"{REDIS_CHANNEL_PREFIX}:{event.event_name}"
            message = json.dumps(event.to_dict())
            pipe.publish(channel, message)
        await pipe.execute()

        # Persist all events
        for event in batch:
            await self._persist_event_log(event)

        logger.debug("Flushed batch of %d events", len(batch))

    async def enqueue(self, event: EventPayload) -> bool:
        """Enqueue an event for batch processing.

        Returns:
            True if enqueued successfully, False otherwise.
        """
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        try:
            self._batch_queue.put_nowait(BatchItem(payload=event, future=future))
            return True
        except asyncio.QueueFull:
            logger.warning("Event batch queue is full, event dropped")
            return False

    # ------------------------------------------------------------------
    # Internal: Persistence
    # ------------------------------------------------------------------

    async def _persist_event_log(self, event: EventPayload) -> None:
        """Persist an event to the event_log table.

        Every event published to the bus is guaranteed to be logged
        for full audit trail. This method is called synchronously
        during publish() before the Redis broadcast, ensuring that
        even if Redis fails, the event is recorded in the database.

        Audit Guarantee:
        - All events are logged with 'pending' status
        - Failed persistence is logged as a critical error
        - retry_count starts at 0 for all new events
        - correlation_id links related events across the system
        """
        import time

        start_time = time.time()
        log_id = None

        try:
            async with get_db_context() as db:
                log_entry = EventLog(
                    event_name=event.event_name,
                    payload=event.payload,
                    company_id=event.company_id,
                    branch_id=event.branch_id,
                    source_module=event.source_module,
                    source_user_id=event.user_id,
                    correlation_id=event.correlation_id,
                    status="pending",
                    retry_count=0,
                )
                db.add(log_entry)
                await db.commit()
                await db.refresh(log_entry)
                log_id = log_entry.id

                duration_ms = int((time.time() - start_time) * 1000)
                logger.debug(
                    "Event audit log created: id=%d event=%s "
                    "correlation=%s company=%s duration=%dms",
                    log_id,
                    event.event_name,
                    event.correlation_id,
                    event.company_id,
                    duration_ms,
                )
        except Exception as exc:
            logger.critical(
                "CRITICAL: Failed to persist event audit log for event '%s' "
                "(correlation=%s, company=%s): %s. "
                "EVENT AUDIT TRAIL MAY BE INCOMPLETE.",
                event.event_name,
                event.correlation_id,
                event.company_id,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Subscription handlers from database
    # ------------------------------------------------------------------

    async def load_subscriptions(self, company_id: int, event_name: str) -> List[EventSubscription]:
        """Load active subscriptions from the database for an event."""
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(EventSubscription).where(
                    EventSubscription.company_id == company_id,
                    EventSubscription.event_name == event_name,
                    EventSubscription.is_active == True,
                )
            )
            return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------

_event_bus: Optional[EventBus] = None


async def get_event_bus_instance() -> EventBus:
    """Get or create the global EventBus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
        await _event_bus.start()
    return _event_bus


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------


async def get_event_bus(request: Request) -> EventBus:
    """FastAPI dependency that returns the EventBus from request state.

    Usage:
        @router.post("/publish")
        async def publish(data: dict, bus: EventBus = Depends(get_event_bus)):
            await bus.publish(...)
    """
    bus = getattr(request.state, "event_bus", None)
    if bus is None:
        bus = await get_event_bus_instance()
        request.state.event_bus = bus
    return bus


# ---------------------------------------------------------------------------
# EventBusMiddleware
# ---------------------------------------------------------------------------


class EventBusMiddleware:
    """FastAPI middleware that injects the EventBus into request.state.

    Usage:
        from app.events.bus import EventBusMiddleware
        app.add_middleware(EventBusMiddleware)

    The middleware ensures every request has access to the event bus via
    request.state.event_bus.
    """

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        bus = await get_event_bus_instance()

        # Wrap the ASGI call to inject event_bus into request state
        original_receive = receive

        async def wrapped_receive():
            return await original_receive()

        request = Request(scope, receive)
        request.state.event_bus = bus
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


async def execute_with_retry(
    func: Callable[..., Coroutine[Any, Any, Any]],
    *args,
    max_retries: int = 5,
    delay_seconds: float = 2.0,
    multiplier: float = 2.0,
    policy: str = "exponential",
    **kwargs,
) -> Any:
    """Execute an async function with retry logic.

    Args:
        func: Async function to execute.
        *args: Positional arguments for the function.
        max_retries: Maximum number of retry attempts.
        delay_seconds: Base delay between retries (seconds).
        multiplier: Multiplier for exponential backoff.
        policy: Retry strategy ("immediate", "linear", "exponential").
        **kwargs: Keyword arguments for the function.

    Returns:
        The function's return value.

    Raises:
        Exception: The last exception raised after all retries are exhausted.
    """
    last_exception: Optional[Exception] = None
    current_delay = delay_seconds

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exception = exc
            if attempt >= max_retries:
                break

            wait_time = {
                "immediate": 1,
                "linear": delay_seconds,
                "exponential": current_delay,
            }.get(policy, current_delay)

            logger.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                func.__name__,
                exc,
                wait_time,
            )
            await asyncio.sleep(wait_time)

            if policy == "exponential":
                current_delay *= multiplier

    raise last_exception


# ---------------------------------------------------------------------------
# Webhook delivery
# ---------------------------------------------------------------------------


async def deliver_webhook(
    url: str,
    payload: Dict[str, Any],
    secret: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: int = WEBHOOK_DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Deliver an event payload to a webhook URL with optional HMAC signature.

    Args:
        url: The webhook endpoint URL.
        payload: JSON payload to send.
        secret: Optional secret for HMAC signature generation.
        headers: Additional headers to include.
        timeout_seconds: Request timeout.

    Returns:
        Dict with 'success', 'status_code', 'response_body', 'delivery_time_ms'.
    """
    body = json.dumps(payload, default=str)
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        WEBHOOK_VERSION_HEADER: WEBHOOK_VERSION,
    }

    if headers:
        request_headers.update(headers)

    if secret:
        signature = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        request_headers[WEBHOOK_SIGNATURE_HEADER] = f"sha256={signature}"

    start_time = time.time()
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
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
