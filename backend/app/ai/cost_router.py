"""AI Cost Governance router."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter(prefix="/ai-cost", tags=["AI Cost Governance"])


class BudgetUpdate(BaseModel):
    budget_usd: float
    alert_threshold_pct: float = 80.0
    hard_limit_usd: Optional[float] = None
    model_tier: str = "balanced"
    fallback_model: str = "gpt-4o-mini"


class TokenUsageFilter(BaseModel):
    model_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.get("/usage")
async def get_usage(
    days: int = 30,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "period_days": days,
        "total_requests": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "by_model": [],
        "by_day": [],
    }


@router.get("/budget")
async def get_budget(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "budget_usd": 100.0,
        "spent_usd": 0.0,
        "remaining_usd": 100.0,
        "alert_threshold_pct": 80.0,
        "hard_limit_usd": 200.0,
        "model_tier": "balanced",
        "fallback_model": "gpt-4o-mini",
        "period": "monthly",
    }


@router.post("/budget")
async def set_budget(
    req: BudgetUpdate,
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "budget_usd": req.budget_usd,
        "alert_threshold_pct": req.alert_threshold_pct,
        "hard_limit_usd": req.hard_limit_usd or req.budget_usd * 2,
        "model_tier": req.model_tier,
        "fallback_model": req.fallback_model,
        "branch_id": branch_id,
    }


@router.get("/models")
async def list_models(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "models": [
            {"name": "gpt-4o-mini", "tier": "cheap", "input_cost": 0.00015, "output_cost": 0.0006, "context": 128000},
            {"name": "gpt-4o", "tier": "premium", "input_cost": 0.0025, "output_cost": 0.01, "context": 128000},
            {"name": "gpt-4", "tier": "premium", "input_cost": 0.03, "output_cost": 0.06, "context": 8192},
        ]
    }


@router.get("/forecast")
async def cost_forecast(
    days: int = 30,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "forecast_days": days,
        "projected_cost_usd": 0.0,
        "projected_tokens": 0,
        "confidence": "low",
        "recommendation": "Not enough data for forecast. Minimum 7 days usage required.",
    }


@router.get("/roi")
async def ai_roi(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    return {
        "total_cost_usd": 0.0,
        "total_interactions": 0,
        "avg_cost_per_interaction": 0.0,
        "time_saved_hours": 0,
        "roi_multiplier": None,
        "recommendation": "Not enough data",
    }
