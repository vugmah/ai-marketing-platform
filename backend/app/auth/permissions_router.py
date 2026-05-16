"""Granular Permission System router."""

from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User

router = APIRouter(prefix="/permissions", tags=["Permissions"])


class PermissionGrant(BaseModel):
    role_id: int
    permission_ids: List[int]
    branch_scope: str = "all"


class PermissionCheck(BaseModel):
    resource: str
    action: str
    branch_id: Optional[int] = None


@router.get("/definitions")
async def list_permission_definitions(
    scope: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    scopes = ["feature", "branch", "channel", "approval", "export", "ai", "erp", "support"]
    resources = {
        "feature": ["ads", "analytics", "ai_chat", "reports", "settings"],
        "branch": ["read", "create", "update", "delete"],
        "channel": ["meta_ads", "google_ads", "instagram", "whatsapp"],
        "approval": ["view", "approve", "reject"],
        "export": ["csv", "pdf", "excel"],
        "ai": ["execute", "configure", "view_usage"],
        "erp": ["sync", "view", "configure"],
        "support": ["view_tickets", "assign", "escalate", "close"],
    }
    return {"scopes": scopes, "resources": resources, "filter": scope}


@router.post("/grant")
async def grant_permissions(
    req: PermissionGrant,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    return {
        "granted": True,
        "role_id": req.role_id,
        "permissions": req.permission_ids,
        "branch_scope": req.branch_scope,
    }


@router.post("/check")
async def check_permission(
    req: PermissionCheck,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "resource": req.resource,
        "action": req.action,
        "branch_id": req.branch_id,
        "granted": True,
        "source": "role",
    }


@router.get("/user/{user_id}")
async def get_user_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "user_id": user_id,
        "role": current_user.role,
        "permissions": ["read", "write", "execute"],
        "overrides": [],
    }


@router.get("/audit")
async def permission_audit(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    return {"message": "Permission audit log", "entries": []}
