"""Incident Management & Recovery router - Phase 5."""

from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.governance.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incident Management"])


class IncidentCreate(BaseModel):
    incident_type: str
    severity: str = "medium"
    title: str
    description: str
    affected_services: List[str] = []
    company_id: Optional[int] = None


class TimelineEventCreate(BaseModel):
    event_type: str
    description: str


@router.post("/create")
async def create_incident(
    req: IncidentCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = IncidentService(db)
    incident = await svc.create_incident(
        req.incident_type, req.severity, req.title,
        req.description, req.affected_services, req.company_id or current_user.company_id,
    )
    return {"incident": incident}


@router.get("/list")
async def list_incidents(
    status: Optional[str] = None, severity: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = IncidentService(db)
    incidents = await svc.get_incidents(status, severity, current_user.company_id)
    return {"incidents": incidents, "count": len(incidents)}


@router.get("/{incident_id}/timeline")
async def get_timeline(
    incident_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = IncidentService(db)
    events = await svc.get_incident_timeline(incident_id)
    return {"events": events, "count": len(events)}


@router.post("/{incident_id}/timeline")
async def add_timeline_event(
    incident_id: int, req: TimelineEventCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    svc = IncidentService(db)
    event = await svc.add_timeline_event(incident_id, req.event_type, req.description, current_user.id)
    return {"event": event}


@router.get("/dashboard/recovery")
async def recovery_dashboard(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = IncidentService(db)
    return await svc.get_recovery_dashboard(current_user.company_id)


@router.get("/playbooks")
async def get_playbooks(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(["admin"])),
):
    svc = IncidentService(db)
    playbooks = await svc.get_playbooks()
    return {"playbooks": playbooks, "count": len(playbooks)}
