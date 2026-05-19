"""Celery application instance for background task processing.

This module provides the shared Celery app instance used by all
task modules. It is configured via celeryconfig.py.

Usage:
    from app.celery_app import celery_app
    from app.erp.tasks import sync_inventory

    # Send a task
    sync_inventory.delay(connection_id=1)
"""

from celery import Celery
from celery.signals import task_failure

# Create Celery application instance
# Configuration is loaded from celeryconfig.py (pure config module)
celery_app = Celery("ai_marketing_platform")
celery_app.config_from_object("celeryconfig")

# Auto-discover tasks from all app modules
celery_app.autodiscover_tasks(
    [
        "app.erp",
        "app.social",
        "app.media",
        "app.ai",
        "app.events",
        "app.reports",
    ]
)


# ---------------------------------------------------------------------------
# Dead Letter Queue Signal Handler
# ---------------------------------------------------------------------------

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """Log failed tasks to the dead letter queue for manual inspection.

    When a task exhausts all retries, it is routed to the dead letter queue.
    This handler persists the failure information to the database for
    troubleshooting and potential reprocessing.
    """
    import logging

    logger = logging.getLogger("celery.dead_letter")

    task_name = sender.name if sender else "unknown"
    exc_str = str(exception) if exception else "Unknown error"

    logger.error(
        "Dead letter task: task_id=%s task_name=%s exception=%s",
        task_id,
        task_name,
        exc_str,
    )

    # Attempt to persist to database (best-effort)
    try:
        import asyncio
        from datetime import datetime

        from app.database import get_db_context
        from app.events.models import DeadLetterEvent

        async def _persist():
            async with get_db_context() as db:
                dlq_entry = DeadLetterEvent(
                    event_log_id=None,  # Unlinked - from Celery task failure
                    failure_reason=f"Celery task failure: {task_name}",
                    last_error=f"{exc_str}\nTask ID: {task_id}",
                    retry_exhausted_at=datetime.utcnow(),
                    original_payload={
                        "task_id": task_id,
                        "task_name": task_name,
                        "exception": exc_str,
                    },
                    resolution_status="unresolved",
                )
                db.add(dlq_entry)
                await db.commit()

        try:
            asyncio.get_event_loop().create_task(_persist())
        except RuntimeError:
            # No event loop available, skip async persistence
            pass
    except Exception:
        pass  # Don't let DLQ logging break the worker
