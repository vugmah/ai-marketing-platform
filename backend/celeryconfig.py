"""Celery configuration for background task processing.

Configures broker (Redis), result backend (Redis), task serialization,
beat schedule, retry policies, dead letter queue, and worker settings.

All settings use uppercase names so Celery's config_from_object()
can automatically pick them up and apply them to the app instance.

Environment Variables:
    CELERY_BROKER_URL: Redis URL for task broker (default: redis://redis:6379/1)
    CELERY_RESULT_BACKEND: Redis URL for result storage (default: redis://redis:6379/2)
"""

import os

# ---------------------------------------------------------------------------
# Broker & Backend
# ---------------------------------------------------------------------------

def _redis_url_with_db(env_url: str, db: int) -> str:
    import re
    if not env_url:
        return f"redis://localhost:6379/{db}"
    base = re.sub(r'/[0-9]+$', '', env_url)
    return f"{base}/{db}"

_broker = os.environ.get("CELERY_BROKER_URL", "")
_backend = os.environ.get("CELERY_RESULT_BACKEND", "")
_redis = os.environ.get("REDIS_URL", "")

broker_url = _broker if _broker else (_redis_url_with_db(_redis, 1) if _redis else "redis://localhost:6379/1")
result_backend = _backend if _backend else (_redis_url_with_db(_redis, 2) if _redis else "redis://localhost:6379/2")

# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"

# ---------------------------------------------------------------------------
# Task Execution
# ---------------------------------------------------------------------------

task_track_started = True
task_time_limit = 3600  # 1 hour hard limit
task_soft_time_limit = 3000  # 50 min soft limit
worker_prefetch_multiplier = 1  # Fair task distribution
worker_concurrency = 4
task_acks_late = True  # Only ack after task completes

# ---------------------------------------------------------------------------
# Result Settings
# ---------------------------------------------------------------------------

result_expires = 86400  # Results expire after 24 hours
result_extended = True
result_backend_always_retry = True
result_backend_max_retries = 5

# ---------------------------------------------------------------------------
# Retry & Dead Letter Configuration
# ---------------------------------------------------------------------------

# Default retry settings for all tasks
task_default_retry_delay = 10  # Base delay in seconds
task_max_retries = 5  # Maximum retry attempts

# Exponential backoff: 10s, 20s, 40s, 80s, 160s
# (calculated as: retry_delay * 2^attempt)

# Dead Letter Queue configuration
task_reject_on_worker_lost = True
task_routes = {
    "app.events.tasks.process_event": {"queue": "events"},
    "app.events.tasks.run_automation_rule": {"queue": "events"},
    "app.events.tasks.retry_dead_letter_item": {"queue": "events"},
    "app.events.tasks.monitor_dead_letter_queue": {"queue": "events"},
    "app.events.tasks.health_check": {"queue": "events"},
    "app.events.tasks.process_pending_events": {"queue": "events"},
    "app.events.tasks.run_automation_rules": {"queue": "events"},
    "app.ai.tasks.generate_embedding": {"queue": "ai"},
    "app.ai.tasks.analyze_sentiment": {"queue": "ai"},
    "app.ai.tasks.batch_analyze_sentiment": {"queue": "ai"},
    "app.ai.tasks.generate_suggestions": {"queue": "ai"},
    "app.ai.tasks.generate_recommendations": {"queue": "ai"},
    # --- RAG Re-index Tasks ---
    "app.ai.reindex_tasks.reindex_entity_type": {"queue": "ai"},
    "app.ai.reindex_tasks.reindex_company": {"queue": "ai"},
    "app.ai.reindex_tasks.vector_health_check": {"queue": "ai"},
    "app.ai.reindex_tasks.cleanup_orphaned_vectors": {"queue": "ai"},
    "app.ai.reindex_tasks.periodic_reindex": {"queue": "ai"},
    "app.media.tasks.generate_thumbnail": {"queue": "media"},
    "app.media.tasks.optimize_image": {"queue": "media"},
    "app.media.tasks.process_media_upload": {"queue": "media"},
    "app.media.tasks.cleanup_orphaned_media": {"queue": "media"},
    "app.erp.tasks.sync_inventory": {"queue": "erp"},
    "app.erp.tasks.sync_products": {"queue": "erp"},
    "app.erp.tasks.sync_customers": {"queue": "erp"},
    "app.erp.tasks.sync_invoices": {"queue": "erp"},
    "app.erp.tasks.sync_sales_orders": {"queue": "erp"},
    "app.erp.tasks.sync_payments": {"queue": "erp"},
    "app.erp.tasks.run_full_sync": {"queue": "erp"},
    "app.social.tasks.sync_posts": {"queue": "social"},
    "app.social.tasks.sync_comments": {"queue": "social"},
    "app.social.tasks.sync_messages": {"queue": "social"},
    "app.social.tasks.sync_analytics": {"queue": "social"},
    "app.social.tasks.publish_scheduled_post": {"queue": "social"},

    # --- Report Exports ---
    "app.reports.tasks.process_export_job": {"queue": "reports"},
    "app.reports.tasks.cleanup_old_exports": {"queue": "reports"},
    "app.reports.tasks.retry_failed_exports": {"queue": "reports"},
}

# ---------------------------------------------------------------------------
# Beat Schedule (Periodic Tasks)
# ---------------------------------------------------------------------------

beat_schedule = {
    # --- Health Check ---
    "health-check-every-60-seconds": {
        "task": "app.events.tasks.health_check",
        "schedule": 60.0,
    },

    # --- ERP Sync (DISABLED — will be enabled after explicit approval) ---
    # "erp-sync-inventory": {
    #     "task": "app.erp.tasks.sync_inventory",
    #     "schedule": 300.0,
    #     "kwargs": {"connection_id": None, "sync_type": "incremental"},
    #     "options": {"queue": "erp"},
    # },
    # "erp-sync-products": {
    #     "task": "app.erp.tasks.sync_products",
    #     "schedule": 300.0,
    #     "kwargs": {"connection_id": None, "sync_type": "incremental"},
    #     "options": {"queue": "erp"},
    # },
    # "erp-sync-customers": {
    #     "task": "app.erp.tasks.sync_customers",
    #     "schedule": 300.0,
    #     "kwargs": {"connection_id": None, "sync_type": "incremental"},
    #     "options": {"queue": "erp"},
    # },
    # "erp-sync-sales-orders": {
    #     "task": "app.erp.tasks.sync_sales_orders",
    #     "schedule": 600.0,
    #     "kwargs": {"connection_id": None, "sync_type": "incremental"},
    #     "options": {"queue": "erp"},
    # },
    # "erp-sync-invoices": {
    #     "task": "app.erp.tasks.sync_invoices",
    #     "schedule": 600.0,
    #     "kwargs": {"connection_id": None, "sync_type": "incremental"},
    #     "options": {"queue": "erp"},
    # },

    # --- Social Media Sync (every 10 minutes) ---
    "social-sync-posts": {
        "task": "app.social.tasks.sync_posts",
        "schedule": 600.0,
        "kwargs": {"account_id": None},
        "options": {"queue": "social"},
    },
    "social-sync-comments": {
        "task": "app.social.tasks.sync_comments",
        "schedule": 600.0,
        "kwargs": {"account_id": None},
        "options": {"queue": "social"},
    },
    "social-sync-messages": {
        "task": "app.social.tasks.sync_messages",
        "schedule": 600.0,
        "kwargs": {"account_id": None},
        "options": {"queue": "social"},
    },

    # --- AI Tasks (every 15 minutes) ---
    "ai-generate-embeddings": {
        "task": "app.ai.tasks.generate_embedding",
        "schedule": 900.0,
        "kwargs": {"entity_type": "product", "entity_ids": None},
        "options": {"queue": "ai"},
    },

    # --- RAG Periodic Re-index (DISABLED — will be enabled after explicit approval) ---
    # "rag-periodic-reindex": {
    #     "task": "app.ai.reindex_tasks.periodic_reindex",
    #     "schedule": 21600.0,  # 6 hours
    #     "kwargs": {"entity_types": ["product", "post", "prompt"]},
    #     "options": {"queue": "ai"},
    # },

    # --- RAG Vector Health Check (DISABLED — will be enabled after explicit approval) ---
    # "rag-vector-health-check": {
    #     "task": "app.ai.reindex_tasks.vector_health_check",
    #     "schedule": 1800.0,  # 30 minutes
    #     "kwargs": {},
    #     "options": {"queue": "ai"},
    # },

    # --- Event Processing (every 30 seconds) ---
    "events-process-pending": {
        "task": "app.events.tasks.process_pending_events",
        "schedule": 30.0,
        "kwargs": {"batch_size": 50},
        "options": {"queue": "events"},
    },
    "events-run-automation-rules": {
        "task": "app.events.tasks.run_automation_rules",
        "schedule": 60.0,
        "kwargs": {},
        "options": {"queue": "events"},
    },

    # --- Media Cleanup (every hour) ---
    "media-cleanup-orphaned": {
        "task": "app.media.tasks.cleanup_orphaned_media",
        "schedule": 3600.0,
        "kwargs": {"older_than_hours": 24},
        "options": {"queue": "media"},
    },

    # --- Export Cleanup (every hour) ---
    "reports-cleanup-old-exports": {
        "task": "app.reports.tasks.cleanup_old_exports",
        "schedule": 3600.0,
        "kwargs": {"older_than_days": 7},
        "options": {"queue": "reports"},
    },

    # --- Retry Failed Exports (every 30 minutes) ---
    "reports-retry-failed": {
        "task": "app.reports.tasks.retry_failed_exports",
        "schedule": 1800.0,
        "kwargs": {"max_age_hours": 24},
        "options": {"queue": "reports"},
    },
}
 