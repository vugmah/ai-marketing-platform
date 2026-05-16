"""Health check router for the AI Marketing Platform.

Provides REST endpoints for health monitoring, readiness/liveness probes,
and Prometheus-compatible metrics.

Router registration in main.py:
    from app.health import router as health_router_v2
    app.include_router(health_router_v2, prefix="/api/v2/health", tags=["Health"])

This router does NOT define its own prefix so main.py can control it.
"""

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.health.metrics import REGISTRY
from app.health.service import HealthAggregator

router = APIRouter()

# Shared aggregator instance (stateless, safe to reuse)
_aggregator = HealthAggregator()


@router.get(
    "/",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Returns 200 OK if the API is running. For detailed checks use /detailed.",
)
async def basic_health() -> dict:
    """Return basic health status.

    Returns:
        Simple status object with service info.
    """
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "AI Marketing Platform API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/detailed",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
    description="Runs all health checks (database, Redis, external services, disk, memory) and returns aggregated results.",
)
async def detailed_health() -> dict:
    """Return detailed health status for all components.

    Returns:
        Aggregated health check results with per-component details.
    """
    result = await _aggregator.check_all()
    return result


@router.get(
    "/db",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Database health check",
    description="Check MySQL connectivity, query latency, and connection pool status.",
)
async def db_health() -> dict:
    """Return database-specific health status.

    Returns:
        Database health check result with connection pool stats.
    """
    result = await _aggregator.check_database()
    return result


@router.get(
    "/redis",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Redis health check",
    description="Check Redis connectivity, latency, and memory usage.",
)
async def redis_health() -> dict:
    """Return Redis-specific health status.

    Returns:
        Redis health check result with memory info.
    """
    result = await _aggregator.check_redis()
    return result


@router.get(
    "/ready",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Kubernetes-style readiness probe. Returns 200 only when database and Redis are accessible. Returns 503 if dependencies are not ready.",
)
async def readiness_probe(response: Response) -> dict:
    """Kubernetes readiness probe endpoint.

    Checks core dependencies (database, Redis). Returns 503 if any
    critical dependency is unhealthy.

    Args:
        response: FastAPI Response object for status code manipulation.

    Returns:
        Readiness check result with dependency statuses.
    """
    result = await _aggregator.check_readiness()
    if result.get("status") in ("unhealthy", "unknown"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif result.get("status") == "degraded":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get(
    "/live",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Kubernetes-style liveness probe. Always returns 200 if the process is running.",
)
async def liveness_probe() -> dict:
    """Kubernetes liveness probe endpoint.

    Lightweight check that the application process is alive.

    Returns:
        Liveness check result with process info.
    """
    result = await _aggregator.check_liveness()
    return result


@router.get(
    "/metrics",
    response_class=Response,
    summary="Prometheus metrics",
    description="Prometheus-compatible metrics endpoint. Returns metrics in exposition format for scraping by Prometheus.",
)
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns application metrics in Prometheus text exposition format.
    Configure Prometheus to scrape this endpoint.

    Returns:
        Response with Content-Type text/plain; version=0.0.4
    """
    data = generate_latest(REGISTRY)
    return Response(
        content=data,
        media_type=CONTENT_TYPE_LATEST,
    )
