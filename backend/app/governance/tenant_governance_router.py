"""Multi-Tenant Resource Governance router - Phase 3."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.governance.tenant_governance_service import TenantGovernanceService

router = APIRouter(prefix="/tenant-governance", tags=["Tenant Governance"])


class QuotaUpdate(BaseModel):
    max_ai_tokens_per_hour: Optional[int] = None
    max_ai_tokens_per_day: Optional[int] = None
    max_queue_jobs_per_hour: Optional[int] = None
    throttling_enabled: Optional[bool] = None


class UsageRecord(BaseModel):
    ai_tokens_used_hour: int = 0
    ai_tokens_used_day: int = 0
    queue_jobs_processed_hour: int = 0
    webhook_calls_min: int = 0


@router.get("/quota")
async def get_quota(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = TenantGovernanceService(db)
    quota = await svc.get_or_create_quota(current_user.company_id)
    return {"quota": quota}


@router.post("/quota")
async def update_quota(
    req: QuotaUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = TenantGovernanceService(db)
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    quota = await svc.update_quota(current_user.company_id, **data)
    return {"quota": quota}


@router.get("/quota/check")
async def check_quota(
    resource_type: str, requested: int = 1,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = TenantGovernanceService(db)
    return await svc.check_quota(current_user.company_id, resource_type, requested)


@router.post("/usage")
async def record_usage(
    req: UsageRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = TenantGovernanceService(db)
    usage = await svc.record_usage(current_user.company_id, **req.model_dump())
    return {"usage": usage}


@router.get("/branch-quota/{branch_id}")
async def get_branch_quota(
    branch_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = TenantGovernanceService(db)
    quota = await svc.get_branch_quota(branch_id)
    return {"quota": quota}


@router.post("/branch-quota/{branch_id}")
async def set_branch_quota(
    branch_id: int, max_ai_tokens_per_hour: int = 10000, max_concurrent_jobs: int = 5,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = TenantGovernanceService(db)
    quota = await svc.set_branch_quota(
        current_user.company_id, branch_id,
        max_ai_tokens_per_hour=max_ai_tokens_per_hour,
        max_concurrent_jobs=max_concurrent_jobs,
    )
    return {"quota": quota}
