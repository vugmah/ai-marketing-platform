"""Observability Intelligence router - Phase 1."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.health.observability_service import ObservabilityService

router = APIRouter(prefix="/observability", tags=["Observability"])


class EndpointHealthRecord(BaseModel):
    method: str
    path: str
    latency_ms: float
    is_error: bool = False


class QueueBottleneckRecord(BaseModel):
    queue_name: str
    depth: int
    consumers: int = 0
    avg_wait_sec: int = 0


class AILatencyRecord(BaseModel):
    model_name: str
    request_type: str = "chat"
    latency_ms: float = 0
    tokens: int = 0
    cost_usd: float = 0


class APIReliabilityRecord(BaseModel):
    provider: str
    endpoint: str
    success: bool = True
    latency_ms: float = 0
    error: Optional[str] = None


@router.get("/health-score")
async def get_health_score(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = ObservabilityService(db)
    return await svc.get_operational_health_score()


@router.get("/unstable-endpoints")
async def unstable_endpoints(
    min_error_rate: float = 5.0,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    endpoints = await svc.get_unstable_endpoints(min_error_rate)
    return {"endpoints": endpoints, "count": len(endpoints)}


@router.post("/record-endpoint")
async def record_endpoint(
    req: EndpointHealthRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    rec = await svc.record_endpoint_health(req.method, req.path, req.latency_ms, req.is_error)
    return {"recorded": rec.id}


@router.get("/queue-alerts")
async def queue_alerts(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = ObservabilityService(db)
    alerts = await svc.get_queue_alerts()
    return {"alerts": alerts, "count": len(alerts)}


@router.post("/record-queue")
async def record_queue(
    req: QueueBottleneckRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    rec = await svc.record_queue_bottleneck(req.queue_name, req.depth, req.consumers, req.avg_wait_sec)
    return {"recorded": rec.id, "congested": rec.is_congested, "severity": rec.bottleneck_severity}


@router.get("/ai-latency")
async def ai_latency_summary(
    model: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = ObservabilityService(db)
    return await svc.get_ai_latency_summary(model)


@router.post("/record-ai-latency")
async def record_ai_latency(
    req: AILatencyRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    rec = await svc.record_ai_latency(req.model_name, req.request_type, req.latency_ms, req.tokens, req.cost_usd)
    return {"recorded": rec.id}


@router.get("/degraded-apis")
async def degraded_apis(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = ObservabilityService(db)
    apis = await svc.get_degraded_apis()
    return {"apis": apis, "count": len(apis)}


@router.post("/record-api-reliability")
async def record_api_reliability(
    req: APIReliabilityRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    rec = await svc.record_api_reliability(req.provider, req.endpoint, req.success, req.latency_ms, req.error)
    return {"recorded": rec.id}


@router.post("/record-webhook-failure")
async def record_webhook_failure(
    webhook_id: int, url: str, event_type: str,
    status: Optional[int] = None, error: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    rec = await svc.record_webhook_failure(webhook_id, url, event_type, status, error)
    return {"recorded": rec.id}


@router.post("/record-worker-health")
async def record_worker(
    worker_name: str, queue: str, tasks: int = 0, failed: int = 0,
    duration_ms: float = 0, memory_mb: Optional[int] = None, cpu: Optional[float] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ObservabilityService(db)
    rec = await svc.record_worker_health(worker_name, queue, tasks, failed, duration_ms, memory_mb, cpu)
    return {"recorded": rec.id, "health_score": float(rec.health_score), "status": rec.status}
