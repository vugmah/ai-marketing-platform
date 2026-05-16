"""Support Operator Workspace router."""

from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter(prefix="/operators", tags=["Support Operators"])


class TicketCreate(BaseModel):
    customer_id: int
    title: str
    description: str
    priority: str = "medium"
    channel: str = "chat"
    branch_id: Optional[int] = None
    tags: List[str] = []


class TicketAssign(BaseModel):
    operator_id: Optional[int] = None
    status: Optional[str] = None


class EscalationRuleCreate(BaseModel):
    name: str
    trigger_condition: str
    trigger_value: Optional[str] = None
    action: str
    target_operator_id: Optional[int] = None
    target_supervisor_id: Optional[int] = None


@router.get("/inbox")
async def operator_inbox(
    status: Optional[str] = "open",
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "tickets": [],
        "total": 0,
        "by_status": {"open": 0, "assigned": 0, "waiting": 0, "resolved": 0},
        "sla_breaches": 0,
    }


@router.get("/supervisor-dashboard")
async def supervisor_dashboard(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "operators": [],
        "active_tickets": 0,
        "avg_response_time": None,
        "sla_compliance_pct": 100.0,
        "escalation_queue": [],
        "ai_handled_pct": 0.0,
    }


@router.post("/tickets")
async def create_ticket(
    req: TicketCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "ticket_id": None,
        "status": "open",
        "message": "Ticket created",
        "data": req.model_dump(),
    }


@router.post("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: int,
    req: TicketAssign,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {"ticket_id": ticket_id, "assigned_to": req.operator_id, "status": req.status or "assigned"}


@router.get("/tickets/{ticket_id}/ai-reply")
async def ai_suggested_reply(
    ticket_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {"ticket_id": ticket_id, "suggested_reply": None, "confidence": 0.0}


@router.post("/escalation-rules")
async def create_escalation_rule(
    req: EscalationRuleCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {"rule": req.model_dump(), "message": "Escalation rule created"}


@router.get("/analytics")
async def support_analytics(
    days: int = 7,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "period_days": days,
        "total_tickets": 0,
        "resolved": 0,
        "avg_resolution_min": None,
        "sla_breaches": 0,
        "satisfaction": None,
        "ai_handled": 0,
        "escalated": 0,
    }
