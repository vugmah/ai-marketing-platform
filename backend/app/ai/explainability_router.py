"""AI Explainability router - Phase 4."""

from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.ai.explainability_service import ExplainabilityService

router = APIRouter(prefix="/ai-explain", tags=["AI Explainability"])


class ExplainRequest(BaseModel):
    recommendation_id: int
    recommendation_type: str
    title: str
    explanation: str
    confidence: float
    reasoning_steps: List[str] = []
    data_sources: List[str] = []
    key_factors: List[str] = []
    branch_id: Optional[int] = None


class FactorRequest(BaseModel):
    recommendation_id: int
    name: str
    category: str = "general"
    weight: float = 1.0
    score: float = 0.0
    data_source: Optional[str] = None
    raw_value: Optional[str] = None


@router.post("/explain")
async def explain(
    req: ExplainRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = ExplainabilityService(db)
    exp = await svc.explain_recommendation(
        req.recommendation_id, req.recommendation_type, req.title,
        req.explanation, req.confidence, req.reasoning_steps,
        req.data_sources, req.key_factors, current_user.company_id, req.branch_id,
    )
    return {"explanation": exp}


@router.get("/explain/{rec_id}")
async def get_explanation(
    rec_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = ExplainabilityService(db)
    exp = await svc.get_explanation(rec_id)
    factors = await svc.get_scoring_factors(rec_id) if exp else []
    return {
        "explanation": exp,
        "scoring_factors": factors,
        "confidence": float(exp.confidence_score) if exp else 0,
        "reason": exp.confidence_reason if exp else None,
    }


@router.post("/factors")
async def add_factor(
    req: FactorRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = ExplainabilityService(db)
    f = await svc.add_scoring_factor(
        req.recommendation_id, req.name, req.category,
        req.weight, req.score, req.data_source, req.raw_value,
    )
    return {"factor": f}
