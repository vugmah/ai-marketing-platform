"""Release & Rollout Management service - Phase 2."""

from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.rollout_models import FeatureFlag, RolloutCohort, ReleaseNote, RolloutEvent


class RolloutService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_feature_flags(self, company_id: int) -> List[FeatureFlag]:
        result = await self.db.execute(
            select(FeatureFlag).where(FeatureFlag.company_id == company_id).order_by(FeatureFlag.flag_key)
        )
        return result.scalars().all()

    async def toggle_flag(self, flag_id: int, enabled: bool, performed_by: int) -> FeatureFlag:
        result = await self.db.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))
        flag = result.scalar_one()
        flag.enabled = enabled
        flag.rollout_pct = 100.0 if enabled else 0.0
        event = RolloutEvent(flag_id=flag_id, event_type="enable" if enabled else "disable",
                             old_value=str(not enabled), new_value=str(enabled), performed_by=performed_by)
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(flag)
        return flag

    async def adjust_rollout(self, flag_id: int, pct: float, performed_by: int) -> FeatureFlag:
        result = await self.db.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))
        flag = result.scalar_one()
        old = str(flag.rollout_pct)
        flag.rollout_pct = pct
        event = RolloutEvent(flag_id=flag_id, event_type="pct_change", old_value=old,
                             new_value=str(pct), performed_by=performed_by)
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(flag)
        return flag

    async def rollback_flag(self, flag_id: int, performed_by: int) -> FeatureFlag:
        result = await self.db.execute(select(FeatureFlag).where(FeatureFlag.id == flag_id))
        flag = result.scalar_one()
        event = RolloutEvent(flag_id=flag_id, event_type="rollback",
                             old_value=str(flag.rollout_pct), new_value="0", performed_by=performed_by)
        self.db.add(event)
        flag.enabled = False
        flag.rollout_pct = 0
        await self.db.commit()
        await self.db.refresh(flag)
        return flag

    async def get_release_notes(self, company_id: Optional[int] = None, limit: int = 50) -> List[ReleaseNote]:
        query = select(ReleaseNote).order_by(desc(ReleaseNote.created_at)).limit(limit)
        if company_id:
            query = query.where(ReleaseNote.company_id == company_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_cohorts(self, company_id: int) -> List[RolloutCohort]:
        result = await self.db.execute(
            select(RolloutCohort).where(RolloutCohort.company_id == company_id)
        )
        return result.scalars().all()
