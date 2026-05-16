"""AI Evaluation & Quality Framework router - Phase 2."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.ai.evaluation_service import AIEvaluationService

router = APIRouter(prefix="/ai-evaluation", tags=["AI Evaluation"])


class HallucinationScoreRequest(BaseModel):
    conversation_id: int
    response_id: int
    response_text: str
    claims: list = []
    verified_claims: list = []
    unverified_claims: list = []


class QualityTrackRequest(BaseModel):
    recommendation_id: int
    recommendation_type: str
    user_feedback: str = "neutral"
    helpfulness: float = 0.5
    accuracy: float = 0.5
    actionability: float = 0.5


@router.post("/hallucination-score")
async def score_hallucination(
    req: HallucinationScoreRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = AIEvaluationService(db)
    score = await svc.score_hallucination(
        current_user.company_id, req.conversation_id, req.response_id,
        req.response_text, req.claims, req.verified_claims, req.unverified_claims,
    )
    return {"score": score, "flagged": score.flagged}


@router.get("/hallucination-stats")
async def hallucination_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = AIEvaluationService(db)
    return await svc.get_hallucination_stats(current_user.company_id)


@router.post("/recommendation-quality")
async def track_quality(
    req: QualityTrackRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = AIEvaluationService(db)
    q = await svc.track_recommendation_quality(
        current_user.company_id, req.recommendation_id, req.recommendation_type,
        req.user_feedback, req.helpfulness, req.accuracy, req.actionability,
    )
    return {"quality": q}


@router.get("/quality-summary")
async def quality_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = AIEvaluationService(db)
    return await svc.get_quality_summary(current_user.company_id)


@router.get("/confidence-analytics")
async def confidence_analytics(
    date: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = AIEvaluationService(db)
    analytics = await svc.get_confidence_analytics(current_user.company_id, date)
    return {"analytics": analytics}
