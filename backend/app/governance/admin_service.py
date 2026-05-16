"""Internal Admin & Ops Console service - Phase 3."""

from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.admin_models import SystemStatusSnapshot, FailedJobRecovery, ModerationQueueItem, AuditExplorerQuery


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_system_status(self) -> Optional[SystemStatusSnapshot]:
        result = await self.db.execute(
            select(SystemStatusSnapshot).order_by(desc(SystemStatusSnapshot.snapshot_at)).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_failed_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[FailedJobRecovery]:
        query = select(FailedJobRecovery).order_by(desc(FailedJobRecovery.created_at)).limit(limit)
        if status:
            query = query.where(FailedJobRecovery.status == status)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def retry_failed_job(self, job_id: int) -> Optional[FailedJobRecovery]:
        result = await self.db.execute(select(FailedJobRecovery).where(FailedJobRecovery.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return None
        job.retry_count += 1
        if job.retry_count >= job.max_retries:
            job.status = "failed"
        else:
            job.status = "retried"
            job.recovered_at = func.now()
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_moderation_queue(
        self, status: Optional[str] = None, severity: Optional[str] = None, limit: int = 50
    ) -> List[ModerationQueueItem]:
        query = select(ModerationQueueItem).order_by(desc(ModerationQueueItem.created_at)).limit(limit)
        if status:
            query = query.where(ModerationQueueItem.status == status)
        if severity:
            query = query.where(ModerationQueueItem.severity == severity)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def moderate_item(self, item_id: int, decision: str, notes: str, reviewer_id: int) -> Optional[ModerationQueueItem]:
        result = await self.db.execute(select(ModerationQueueItem).where(ModerationQueueItem.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            return None
        item.status = decision
        item.reviewed_by = reviewer_id
        item.review_notes = notes
        await self.db.commit()
        await self.db.refresh(item)
        return item
