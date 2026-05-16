"""AI Evaluation & Quality Framework service - Phase 2."""

from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.evaluation_models import AIHallucinationScore, AIRecommendationQuality, AIPromptPerformance, AIConfidenceAnalytics


class AIEvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def score_hallucination(
        self, company_id: int, conversation_id: int, response_id: int,
        response_text: str, claims: list, verified: list, unverified: list
    ) -> AIHallucinationScore:
        total = len(claims) if claims else 1
        verified_count = len(verified) if verified else 0
        unverified_count = len(unverified) if unverified else 0
        factual = verified_count / total if total > 0 else 0
        hallucination = unverified_count / total if total > 0 else 0
        source_ver = verified_count / total if total > 0 else 0

        score = AIHallucinationScore(
            company_id=company_id,
            conversation_id=conversation_id,
            response_id=response_id,
            response_text=response_text,
            hallucination_score=round(hallucination, 4),
            factual_score=round(factual, 4),
            source_verification_score=round(source_ver, 4),
            detected_claims=claims or [],
            verified_claims=verified or [],
            unverified_claims=unverified or [],
            flagged=hallucination > 0.3,
        )
        self.db.add(score)
        await self.db.commit()
        await self.db.refresh(score)
        return score

    async def get_hallucination_stats(self, company_id: int) -> dict:
        result = await self.db.execute(
            select(func.avg(AIHallucinationScore.hallucination_score),
                   func.avg(AIHallucinationScore.factual_score),
                   func.count()).where(AIHallucinationScore.company_id == company_id)
        )
        avg_hall, avg_fact, count = result.one()
        return {
            "avg_hallucination_score": round(float(avg_hall or 0), 4),
            "avg_factual_score": round(float(avg_fact or 0), 4),
            "total_evaluated": int(count or 0),
            "flagged_count": int(count * (avg_hall or 0)) if count else 0,
        }

    async def track_recommendation_quality(
        self, company_id: int, rec_id: int, rec_type: str,
        user_feedback: str, helpfulness: float, accuracy: float, actionability: float
    ) -> AIRecommendationQuality:
        overall = (helpfulness + accuracy + actionability) / 3
        q = AIRecommendationQuality(
            company_id=company_id,
            recommendation_id=rec_id,
            recommendation_type=rec_type,
            user_feedback=user_feedback,
            helpfulness_score=helpfulness,
            accuracy_score=accuracy,
            actionability_score=actionability,
            overall_quality_score=round(overall, 4),
        )
        self.db.add(q)
        await self.db.commit()
        await self.db.refresh(q)
        return q

    async def get_quality_summary(self, company_id: int) -> dict:
        result = await self.db.execute(
            select(func.avg(AIRecommendationQuality.overall_quality_score),
                   func.count()).where(AIRecommendationQuality.company_id == company_id)
        )
        avg_score, count = result.one()
        return {
            "avg_quality_score": round(float(avg_score or 0), 4),
            "total_rated": int(count or 0),
        }

    async def get_confidence_analytics(self, company_id: int, date: str) -> Optional[AIConfidenceAnalytics]:
        result = await self.db.execute(
            select(AIConfidenceAnalytics).where(
                AIConfidenceAnalytics.company_id == company_id,
                AIConfidenceAnalytics.date == date
            )
        )
        return result.scalar_one_or_none()
