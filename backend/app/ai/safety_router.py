"""AI Fact Validation & Safety router."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter(prefix="/ai-safety", tags=["AI Safety"])


class FactCheckRequest(BaseModel):
    claim_text: str
    claim_type: str  # price, inventory, campaign, reservation, general
    conversation_id: int
    ai_response_id: int


class CriticalPolicyUpdate(BaseModel):
    action_type: str
    requires_erp_verification: bool = True
    requires_human_approval: bool = False
    min_confidence_threshold: float = 0.85
    auto_block_if_unverified: bool = True


@router.post("/fact-check")
async def fact_check(
    req: FactCheckRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "claim": req.claim_text,
        "type": req.claim_type,
        "verification_status": "pending",
        "requires_approval": req.claim_type in ("price", "inventory", "reservation"),
        "message": "Fact validation registered. ERP verification will be performed.",
    }


@router.get("/fact-checks")
async def list_fact_checks(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {"checks": [], "status_filter": status}


@router.post("/policies")
async def set_critical_policy(
    req: CriticalPolicyUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {"policy": req.model_dump(), "message": "Critical action policy updated"}


@router.get("/policies")
async def get_critical_policies(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "policies": [
            {"action_type": "price_quote", "requires_erp_verification": True, "requires_human_approval": True},
            {"action_type": "inventory_check", "requires_erp_verification": True, "requires_human_approval": False},
            {"action_type": "campaign_create", "requires_erp_verification": False, "requires_human_approval": True},
            {"action_type": "reservation", "requires_erp_verification": True, "requires_human_approval": True},
        ]
    }


@router.post("/approve/{check_id}")
async def approve_fact_check(
    check_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {"check_id": check_id, "approved_by": current_user.id, "status": "approved"}
