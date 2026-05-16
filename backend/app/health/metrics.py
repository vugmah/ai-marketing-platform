"""Prometheus metrics for the AI Marketing Platform.

Defines all application-level Prometheus metrics using the prometheus_client
library.  Metrics are collected via MetricsMiddleware and can be exposed
via the /metrics endpoint in the health router.

Usage:
    from app.health.metrics import request_count, db_query_duration

    # In a route handler or service:
    request_count.labels(method="GET", endpoint="/api/v2/campaigns", status="200").inc()
    db_query_duration.labels(query_type="select").observe(elapsed_seconds)
"""

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Info,
)

# ---------------------------------------------------------------------------
# Application info
# ---------------------------------------------------------------------------

app_info = Info(
    "aimp_app_info",
    "AI Marketing Platform application information",
    registry=REGISTRY,
)
app_info.info({
    "name": "ai-marketing-platform",
    "version": "2.0.0",
    "python_version": "3.11",
})

# ---------------------------------------------------------------------------
# HTTP Request metrics
# ---------------------------------------------------------------------------

request_count = Counter(
    "aimp_http_requests_total",
    "Total number of HTTP requests",
    labelnames=["method", "endpoint", "status"],
    registry=REGISTRY,
)

request_duration = Histogram(
    "aimp_http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "endpoint"],
    buckets=[
        0.005, 0.01, 0.025, 0.05, 0.075,
        0.1, 0.25, 0.5, 0.75, 1.0,
        2.5, 5.0, 7.5, 10.0, 30.0, 60.0,
    ],
    registry=REGISTRY,
)

active_connections = Gauge(
    "aimp_http_active_connections",
    "Number of currently active HTTP connections",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Error metrics
# ---------------------------------------------------------------------------

error_count = Counter(
    "aimp_errors_total",
    "Total number of application errors",
    labelnames=["error_type"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Database query metrics
# ---------------------------------------------------------------------------

db_query_duration = Histogram(
    "aimp_db_query_duration_seconds",
    "Database query duration in seconds",
    labelnames=["query_type"],
    buckets=[
        0.001, 0.005, 0.01, 0.025, 0.05,
        0.1, 0.25, 0.5, 1.0, 2.5, 5.0,
    ],
    registry=REGISTRY,
)

db_connection_pool = Gauge(
    "aimp_db_connection_pool_size",
    "Current database connection pool statistics",
    labelnames=["state"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Redis operation metrics
# ---------------------------------------------------------------------------

redis_operation_duration = Histogram(
    "aimp_redis_operation_duration_seconds",
    "Redis operation duration in seconds",
    labelnames=["operation"],
    buckets=[
        0.001, 0.005, 0.01, 0.025, 0.05,
        0.1, 0.25, 0.5, 1.0,
    ],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# AI / LLM request metrics
# ---------------------------------------------------------------------------

ai_request_count = Counter(
    "aimp_ai_requests_total",
    "Total number of AI/LLM API requests",
    labelnames=["model", "status"],
    registry=REGISTRY,
)

ai_tokens_used = Counter(
    "aimp_ai_tokens_used_total",
    "Total number of tokens consumed from AI APIs",
    labelnames=["model", "token_type"],
    registry=REGISTRY,
)

ai_request_duration = Histogram(
    "aimp_ai_request_duration_seconds",
    "AI/LLM API request duration in seconds",
    labelnames=["model"],
    buckets=[
        0.1, 0.25, 0.5, 1.0, 2.5,
        5.0, 10.0, 30.0, 60.0, 120.0,
    ],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Social media API metrics
# ---------------------------------------------------------------------------

social_api_requests = Counter(
    "aimp_social_api_requests_total",
    "Total number of social media API requests",
    labelnames=["platform", "status"],
    registry=REGISTRY,
)

social_api_duration = Histogram(
    "aimp_social_api_duration_seconds",
    "Social media API request duration in seconds",
    labelnames=["platform"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# ERP sync metrics
# ---------------------------------------------------------------------------

erp_sync_count = Counter(
    "aimp_erp_sync_total",
    "Total number of ERP synchronization operations",
    labelnames=["status"],
    registry=REGISTRY,
)

erp_sync_duration = Histogram(
    "aimp_erp_sync_duration_seconds",
    "ERP synchronization duration in seconds",
    labelnames=["entity_type"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# User session metrics
# ---------------------------------------------------------------------------

user_sessions = Gauge(
    "aimp_user_sessions_active",
    "Number of currently active user sessions",
    registry=REGISTRY,
)

user_login_count = Counter(
    "aimp_user_logins_total",
    "Total number of user login events",
    labelnames=["status"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Background job metrics
# ---------------------------------------------------------------------------

background_jobs = Gauge(
    "aimp_background_jobs",
    "Number of background jobs by status",
    labelnames=["status"],
    registry=REGISTRY,
)

background_job_duration = Histogram(
    "aimp_background_job_duration_seconds",
    "Background job execution duration in seconds",
    labelnames=["job_type"],
    buckets=[
        1.0, 5.0, 10.0, 30.0, 60.0,
        120.0, 300.0, 600.0, 1800.0, 3600.0,
    ],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Notification metrics
# ---------------------------------------------------------------------------

notification_count = Counter(
    "aimp_notifications_total",
    "Total number of notifications sent",
    labelnames=["channel", "status"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Rate limiting metrics
# ---------------------------------------------------------------------------

rate_limit_hits = Counter(
    "aimp_rate_limit_hits_total",
    "Total number of rate-limited requests",
    labelnames=["endpoint"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Scheduled task metrics
# ---------------------------------------------------------------------------

scheduled_task_duration = Histogram(
    "aimp_scheduled_task_duration_seconds",
    "Scheduled task execution duration",
    labelnames=["task_name"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Helper functions for recording metrics
# ---------------------------------------------------------------------------


def record_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """Record HTTP request metrics.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Request path
        status_code: HTTP response status code
        duration: Request duration in seconds
    """
    status = str(status_code)
    request_count.labels(method=method, endpoint=endpoint, status=status).inc()
    request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def record_db_query(query_type: str, duration: float) -> None:
    """Record database query duration.

    Args:
        query_type: Type of query (select, insert, update, delete, etc.)
        duration: Query duration in seconds
    """
    db_query_duration.labels(query_type=query_type).observe(duration)


def record_redis_operation(operation: str, duration: float) -> None:
    """Record Redis operation duration.

    Args:
        operation: Redis command name (get, set, etc.)
        duration: Operation duration in seconds
    """
    redis_operation_duration.labels(operation=operation).observe(duration)


def record_error(error_type: str) -> None:
    """Record an application error.

    Args:
        error_type: Classification of the error (db, redis, validation, etc.)
    """
    error_count.labels(error_type=error_type).inc()


def record_ai_request(model: str, status: str, duration: float, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    """Record AI/LLM API request metrics.

    Args:
        model: Model identifier (gpt-4, gpt-3.5-turbo, etc.)
        status: Request status (success, error, timeout)
        duration: Request duration in seconds
        prompt_tokens: Number of prompt tokens used
        completion_tokens: Number of completion tokens used
    """
    ai_request_count.labels(model=model, status=status).inc()
    ai_request_duration.labels(model=model).observe(duration)
    if prompt_tokens > 0:
        ai_tokens_used.labels(model=model, token_type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        ai_tokens_used.labels(model=model, token_type="completion").inc(completion_tokens)


def record_social_api_request(platform: str, status: str, duration: float) -> None:
    """Record social media API request metrics.

    Args:
        platform: Platform name (facebook, instagram, google_ads, etc.)
        status: Request status (success, error, rate_limited)
        duration: Request duration in seconds
    """
    social_api_requests.labels(platform=platform, status=status).inc()
    social_api_duration.labels(platform=platform).observe(duration)


def record_erp_sync(status: str, duration: float) -> None:
    """Record ERP sync operation metrics.

    Args:
        status: Sync status (success, error, partial)
        duration: Sync duration in seconds
    """
    erp_sync_count.labels(status=status).inc()


def set_user_sessions(count: int) -> None:
    """Set the current number of active user sessions.

    Args:
        count: Number of active sessions
    """
    user_sessions.set(count)


def set_background_jobs(status: str, count: int) -> None:
    """Set background job count for a given status.

    Args:
        status: Job status (queued, running, failed, succeeded)
        count: Number of jobs in this status
    """
    background_jobs.labels(status=status).set(count)
