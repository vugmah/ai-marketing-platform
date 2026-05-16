"""Observability Intelligence service - Phase 1."""

from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.health.observability_models import (
    EndpointHealthScore,
    QueueBottleneck,
    AILatencyAnalytics,
    ExternalAPIReliability,
    WebhookFailureLog,
    WorkerHealthScore,
)


class ObservabilityService:
    """Operational observability service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_endpoint_health(
        self, method: str, path: str, latency_ms: float,
        is_error: bool, company_id: Optional[int] = None
    ) -> EndpointHealthScore:
        score = EndpointHealthScore(
            company_id=company_id,
            method=method,
            path=path,
            avg_latency_ms=latency_ms,
            p95_latency_ms=latency_ms,
            p99_latency_ms=latency_ms,
            error_rate_pct=100.0 if is_error else 0.0,
            request_count=1,
            error_count=1 if is_error else 0,
            health_score=0 if is_error else max(0, 100 - latency_ms * 0.1),
            status="critical" if is_error else "healthy" if latency_ms < 500 else "degraded",
        )
        self.db.add(score)
        await self.db.commit()
        await self.db.refresh(score)
        return score

    async def get_unstable_endpoints(
        self, min_error_rate: float = 5.0, limit: int = 20
    ) -> List[EndpointHealthScore]:
        result = await self.db.execute(
            select(EndpointHealthScore)
            .where(EndpointHealthScore.error_rate_pct >= min_error_rate)
            .order_by(desc(EndpointHealthScore.error_rate_pct))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_operational_health_score(self) -> dict:
        ep_result = await self.db.execute(
            select(func.avg(EndpointHealthScore.health_score))
        )
        ep_avg = ep_result.scalar() or 100

        api_result = await self.db.execute(
            select(func.avg(ExternalAPIReliability.reliability_score))
        )
        api_avg = api_result.scalar() or 100

        q_result = await self.db.execute(
            select(func.count()).where(QueueBottleneck.is_congested == True)
        )
        congested = q_result.scalar() or 0

        queue_health = max(0, 100 - congested * 20)
        overall = round((ep_avg + api_avg + queue_health) / 3, 1)

        return {
            "overall_score": overall,
            "endpoint_health": round(float(ep_avg), 1),
            "api_reliability": round(float(api_avg), 1),
            "queue_health": queue_health,
            "congested_queues": congested,
            "status": "healthy" if overall >= 80 else "degraded" if overall >= 50 else "critical",
        }

    async def record_queue_bottleneck(
        self, queue_name: str, depth: int, consumers: int, avg_wait: int
    ) -> QueueBottleneck:
        severity = "none"
        is_congested = False
        if depth > 1000 and consumers == 0:
            severity, is_congested = "critical", True
        elif depth > 500:
            severity, is_congested = "high", True
        elif depth > 100:
            severity, is_congested = "medium", depth > 10 * consumers if consumers else True

        bn = QueueBottleneck(
            queue_name=queue_name,
            depth=depth,
            consumer_count=consumers,
            avg_wait_time_sec=avg_wait,
            is_congested=is_congested,
            bottleneck_severity=severity,
        )
        self.db.add(bn)
        await self.db.commit()
        await self.db.refresh(bn)
        return bn

    async def get_queue_alerts(self) -> List[QueueBottleneck]:
        result = await self.db.execute(
            select(QueueBottleneck)
            .where(QueueBottleneck.is_congested == True)
            .order_by(desc(QueueBottleneck.depth))
            .limit(20)
        )
        return result.scalars().all()

    async def record_ai_latency(
        self, model_name: str, request_type: str, latency_ms: float,
        tokens: int, cost_usd: float, company_id: Optional[int] = None
    ) -> AILatencyAnalytics:
        entry = AILatencyAnalytics(
            company_id=company_id,
            model_name=model_name,
            request_type=request_type,
            avg_latency_ms=latency_ms,
            p95_latency_ms=latency_ms,
            p99_latency_ms=latency_ms,
            token_count=tokens,
            estimated_cost_usd=cost_usd,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_ai_latency_summary(self, model_name: Optional[str] = None) -> dict:
        query = select(
            func.avg(AILatencyAnalytics.avg_latency_ms),
            func.avg(AILatencyAnalytics.estimated_cost_usd),
            func.sum(AILatencyAnalytics.token_count),
        )
        if model_name:
            query = query.where(AILatencyAnalytics.model_name == model_name)
        result = await self.db.execute(query)
        avg_lat, avg_cost, total_tokens = result.one()
        return {
            "avg_latency_ms": round(float(avg_lat or 0), 2),
            "avg_cost_usd": round(float(avg_cost or 0), 6),
            "total_tokens": int(total_tokens or 0),
        }

    async def record_api_reliability(
        self, provider: str, endpoint: str, success: bool,
        latency_ms: float, error: Optional[str] = None
    ) -> ExternalAPIReliability:
        entry = ExternalAPIReliability(
            provider_name=provider,
            endpoint=endpoint,
            success_count=1 if success else 0,
            error_count=0 if success else 1,
            avg_latency_ms=latency_ms,
            reliability_score=100 if success else 0,
            status="operational" if success else "degraded",
            last_error=error,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_degraded_apis(self) -> List[ExternalAPIReliability]:
        result = await self.db.execute(
            select(ExternalAPIReliability)
            .where(ExternalAPIReliability.status != "operational")
            .order_by(desc(ExternalAPIReliability.measured_at))
            .limit(20)
        )
        return result.scalars().all()

    async def record_webhook_failure(
        self, webhook_id: int, url: str, event_type: str,
        status: Optional[int] = None, error: Optional[str] = None
    ) -> WebhookFailureLog:
        entry = WebhookFailureLog(
            webhook_id=webhook_id,
            webhook_url=url,
            event_type=event_type,
            http_status=status,
            error_message=error or "Unknown error",
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def record_worker_health(
        self, worker_name: str, queue: str, tasks: int, failed: int,
        duration_ms: float, memory_mb: Optional[int] = None, cpu: Optional[float] = None
    ) -> WorkerHealthScore:
        score = max(0, 100 - failed * 5 - (duration_ms / 1000) * 2)
        entry = WorkerHealthScore(
            worker_name=worker_name,
            queue_name=queue,
            tasks_processed=tasks,
            tasks_failed=failed,
            avg_task_duration_ms=duration_ms,
            memory_usage_mb=memory_mb,
            cpu_usage_pct=cpu,
            health_score=score,
            status="healthy" if score >= 80 else "degraded" if score >= 50 else "critical",
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry
