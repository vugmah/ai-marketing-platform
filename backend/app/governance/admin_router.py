"""Internal Admin & Ops Console router - Phase 3."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import require_role
from app.auth.models import User
from app.governance.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin & Ops"])


class ModerateRequest(BaseModel):
    decision: str
    notes: str = ""


@router.get("/system-status")
async def system_status(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = AdminService(db)
    status = await svc.get_system_status()
    return {"status": status or {"message": "No snapshot recorded yet"}}


@router.get("/failed-jobs")
async def failed_jobs(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = AdminService(db)
    jobs = await svc.get_failed_jobs(status)
    return {"jobs": jobs, "count": len(jobs)}


@router.post("/failed-jobs/{job_id}/retry")
async def retry_job(
    job_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = AdminService(db)
    job = await svc.retry_failed_job(job_id)
    return {"job": job, "message": "Retry triggered" if job else "Job not found"}


@router.get("/moderation-queue")
async def moderation_queue(
    status: Optional[str] = None, severity: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = AdminService(db)
    items = await svc.get_moderation_queue(status, severity)
    return {"items": items, "count": len(items)}


@router.post("/moderation-queue/{item_id}/review")
async def review_moderation(
    item_id: int, req: ModerateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = AdminService(db)
    item = await svc.moderate_item(item_id, req.decision, req.notes, current_user.id)
    return {"item": item, "message": "Moderated" if item else "Not found"}
