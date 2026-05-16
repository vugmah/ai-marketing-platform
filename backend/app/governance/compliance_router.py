"""Enterprise Compliance Layer router - Phase 4."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.governance.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["Enterprise Compliance"])


class RetentionPolicyUpdate(BaseModel):
    data_category: str
    retention_days: int = 365
    auto_archive: bool = True
    auto_delete: bool = False


class LineageRecord(BaseModel):
    operation: str
    source_table: Optional[str] = None
    source_id: Optional[int] = None
    target_table: Optional[str] = None
    target_id: Optional[int] = None
    metadata: Optional[dict] = None


@router.get("/retention-policies")
async def get_policies(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ComplianceService(db)
    policies = await svc.get_retention_policies(current_user.company_id)
    return {"policies": policies}


@router.post("/retention-policies")
async def set_policy(
    req: RetentionPolicyUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ComplianceService(db)
    policy = await svc.set_retention_policy(
        current_user.company_id, req.data_category,
        req.retention_days, req.auto_archive, req.auto_delete,
    )
    return {"policy": policy}


@router.post("/lineage")
async def record_lineage(
    req: LineageRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = ComplianceService(db)
    record = await svc.record_lineage(
        current_user.company_id, req.operation,
        req.source_table, req.source_id,
        req.target_table, req.target_id,
        current_user.id, req.metadata,
    )
    return {"record": record}


@router.get("/lineage/{table_name}/{record_id}")
async def get_lineage(
    table_name: str, record_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ComplianceService(db)
    records = await svc.get_lineage(table_name, record_id)
    return {"records": records, "count": len(records)}


@router.get("/admin-actions")
async def admin_actions(
    admin_id: Optional[int] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ComplianceService(db)
    actions = await svc.get_admin_actions(current_user.company_id, admin_id)
    return {"actions": actions, "count": len(actions)}


@router.post("/reports")
async def generate_report(
    report_type: str, date: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = ComplianceService(db)
    report = await svc.generate_compliance_report(
        current_user.company_id, report_type, date, current_user.id,
    )
    return {"report": report}
