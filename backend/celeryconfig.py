"""Celery configuration for background task processing."""

from celery import Celery

from app.config import settings

# Create Celery application instance
celery_app = Celery("ai_marketing_platform")

# Broker and backend configuration
celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

# Serialization settings
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.result_serializer = "json"

# Task execution settings
celery_app.conf.task_track_started = True
celery_app.conf.task_time_limit = 3600  # 1 hour max per task
celery_app.conf.task_soft_time_limit = 3000  # 50 min soft limit
celery_app.conf.worker_prefetch_multiplier = 4

# Result settings
celery_app.conf.result_expires = 86400  # Results expire after 24 hours
celery_app.conf.result_extended = True

# Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    "health-check-every-60-seconds": {
        "task": "app.tasks.health_check",
        "schedule": 60.0,
    },
}

# Timezone settings
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

# Import tasks from registered modules
celery_app.autodiscover_tasks(["app.auth", "app.companies", "app.branches"])
