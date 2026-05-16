"""Multi-Tenant Resource Governance service - Phase 3."""

from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.tenant_governance_models import TenantResourceQuota, TenantResourceUsage, BranchResourceQuota


class TenantGovernanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_quota(self, company_id: int) -> TenantResourceQuota:
        result = await self.db.execute(
            select(TenantResourceQuota).where(TenantResourceQuota.company_id == company_id)
        )
        quota = result.scalar_one_or_none()
        if not quota:
            quota = TenantResourceQuota(company_id=company_id)
            self.db.add(quota)
            await self.db.commit()
            await self.db.refresh(quota)
        return quota

    async def update_quota(self, company_id: int, **kwargs) -> TenantResourceQuota:
        quota = await self.get_or_create_quota(company_id)
        for k, v in kwargs.items():
            if hasattr(quota, k) and v is not None:
                setattr(quota, k, v)
        await self.db.commit()
        await self.db.refresh(quota)
        return quota

    async def check_quota(self, company_id: int, resource_type: str, requested: int = 1) -> dict:
        """Check if a tenant has sufficient quota for a resource."""
        quota = await self.get_or_create_quota(company_id)
        
        limits = {
            "ai_tokens_hour": quota.max_ai_tokens_per_hour,
            "ai_tokens_day": quota.max_ai_tokens_per_day,
            "queue_jobs": quota.max_queue_jobs_per_hour,
            "webhooks": quota.max_webhook_calls_per_min,
            "branches": quota.max_branches,
            "users": quota.max_users,
        }
        
        limit = limits.get(resource_type, 0)
        allowed = limit == 0 or requested <= limit
        
        return {
            "company_id": company_id,
            "resource_type": resource_type,
            "requested": requested,
            "limit": limit,
            "allowed": allowed,
            "throttled": quota.throttling_enabled and not allowed,
        }

    async def record_usage(self, company_id: int, **kwargs) -> TenantResourceUsage:
        usage = TenantResourceUsage(company_id=company_id, **kwargs)
        self.db.add(usage)
        await self.db.commit()
        await self.db.refresh(usage)
        return usage

    async def get_branch_quota(self, branch_id: int) -> Optional[BranchResourceQuota]:
        result = await self.db.execute(
            select(BranchResourceQuota).where(BranchResourceQuota.branch_id == branch_id)
        )
        return result.scalar_one_or_none()

    async def set_branch_quota(self, company_id: int, branch_id: int, **kwargs) -> BranchResourceQuota:
        quota = await self.get_branch_quota(branch_id)
        if not quota:
            quota = BranchResourceQuota(company_id=company_id, branch_id=branch_id, **kwargs)
            self.db.add(quota)
        else:
            for k, v in kwargs.items():
                if hasattr(quota, k) and v is not None:
                    setattr(quota, k, v)
        await self.db.commit()
        await self.db.refresh(quota)
        return quota
