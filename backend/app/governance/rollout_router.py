"""Release & Rollout Management router - Phase 2."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.governance.rollout_service import RolloutService

router = APIRouter(prefix="/rollout", tags=["Rollout Management"])


class FlagToggle(BaseModel):
    enabled: bool


class RolloutAdjust(BaseModel):
    percentage: float


@router.get("/flags")
async def get_flags(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = RolloutService(db)
    flags = await svc.get_feature_flags(current_user.company_id)
    return {"flags": flags, "count": len(flags)}


@router.post("/flags/{flag_id}/toggle")
async def toggle_flag(
    flag_id: int, req: FlagToggle,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = RolloutService(db)
    flag = await svc.toggle_flag(flag_id, req.enabled, current_user.id)
    return {"flag": flag}


@router.post("/flags/{flag_id}/rollout")
async def adjust_rollout(
    flag_id: int, req: RolloutAdjust,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = RolloutService(db)
    flag = await svc.adjust_rollout(flag_id, req.percentage, current_user.id)
    return {"flag": flag}


@router.post("/flags/{flag_id}/rollback")
async def rollback_flag(
    flag_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = RolloutService(db)
    flag = await svc.rollback_flag(flag_id, current_user.id)
    return {"flag": flag, "message": "Feature rolled back"}


@router.get("/cohorts")
async def get_cohorts(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = RolloutService(db)
    cohorts = await svc.get_cohorts(current_user.company_id)
    return {"cohorts": cohorts, "count": len(cohorts)}


@router.get("/release-notes")
async def get_release_notes(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RolloutService(db)
    notes = await svc.get_release_notes(current_user.company_id)
    return {"notes": notes, "count": len(notes)}
