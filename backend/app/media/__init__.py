"""Creative Studio & Media Pipeline module."""

# Import Celery tasks for autodiscovery (optional - skip if celery not installed)
try:
    from app.media import tasks as media_tasks
except ImportError:
    pass  # Celery not available, skip task autodiscovery
