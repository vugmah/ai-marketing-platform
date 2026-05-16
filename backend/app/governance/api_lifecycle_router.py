"""API Lifecycle & Versioning router."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.governance.api_lifecycle_service import APIVersioningService

router = APIRouter(prefix="/api-lifecycle", tags=["API Lifecycle"])


class VersionPolicyCreate(BaseModel):
    current_version: str = "v2"
    min_supported_version: str = "v2"
    deprecation_notice_days: int = 90


class DeprecateEndpointRequest(BaseModel):
    method: str
    path: str
    removal_version: str
    alternative_endpoint: Optional[str] = None
    migration_guide: Optional[str] = None


class ChangelogCreate(BaseModel):
    version: str
    change_type: str  # added, changed, deprecated, removed, fixed
    description: str
    endpoint: Optional[str] = None
    migration_required: bool = False


class ContractSnapshotRequest(BaseModel):
    endpoint_id: int
    request_schema: dict
    response_schema: dict
    query_params: Optional[dict] = None
    headers: Optional[dict] = None


@router.get("/version-policy")
async def get_version_policy(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    policy = await service.get_version_policy(current_user.company_id)
    return {"policy": policy}


@router.post("/version-policy")
async def set_version_policy(
    req: VersionPolicyCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    policy = await service.create_or_update_policy(
        current_user.company_id, req.current_version, req.min_supported_version
    )
    return {"policy": policy}


@router.post("/deprecate")
async def deprecate_endpoint(
    req: DeprecateEndpointRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    endpoint = await service.deprecate_endpoint(
        current_user.company_id,
        req.method,
        req.path,
        req.removal_version,
        req.alternative_endpoint,
        req.migration_guide,
    )
    # Auto-create changelog entry
    await service.add_changelog_entry(
        version=req.removal_version,
        change_type="deprecated",
        description=f"Endpoint {req.method.upper()} {req.path} deprecated",
        endpoint=f"{req.method.upper()} {req.path}",
        company_id=current_user.company_id,
    )
    return {"endpoint": endpoint, "message": "Endpoint deprecated"}


@router.get("/deprecated")
async def list_deprecated(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    endpoints = await service.get_deprecated_endpoints(current_user.company_id)
    return {"endpoints": endpoints, "count": len(endpoints)}


@router.get("/changelog")
async def get_changelog(
    version: Optional[str] = None,
    change_type: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    entries = await service.get_changelog(version, change_type, current_user.company_id)
    return {"entries": entries, "count": len(entries)}


@router.post("/changelog")
async def add_changelog(
    req: ChangelogCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    entry = await service.add_changelog_entry(
        req.version, req.change_type, req.description, req.endpoint, req.migration_required,
        current_user.company_id,
    )
    return {"entry": entry}


@router.post("/contract-snapshot")
async def snapshot_contract(
    req: ContractSnapshotRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    snapshot = await service.snapshot_contract(
        req.endpoint_id, req.request_schema, req.response_schema, req.query_params, req.headers
    )
    return {"snapshot": snapshot}


@router.post("/drift-check/{endpoint_id}")
async def check_drift(
    endpoint_id: int,
    current: dict,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    service = APIVersioningService(db)
    drift = await service.detect_contract_drift(
        endpoint_id, current.get("request", {}), current.get("response", {})
    )
    return drift or {"drift_detected": False}
