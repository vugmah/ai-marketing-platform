"""AI Explainability service - Phase 4."""

from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.explainability_models import AIRecommendationExplanation, AIScoringFactor


class ExplainabilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def explain_recommendation(
        self, rec_id: int, rec_type: str, title: str, explanation: str,
        confidence: float, reasoning_steps: list, data_sources: list,
        key_factors: list, company_id: int, branch_id: Optional[int] = None,
    ) -> AIRecommendationExplanation:
        conf_reason = f"Confidence of {confidence:.1%} based on {len(data_sources)} verified data sources"
        if confidence >= 0.9:
            conf_reason += ". High agreement across all data signals."
        elif confidence >= 0.7:
            conf_reason += ". Good data coverage with minor gaps."
        else:
            conf_reason += ". Limited data - recommendation should be reviewed."

        exp = AIRecommendationExplanation(
            company_id=company_id,
            branch_id=branch_id,
            recommendation_id=rec_id,
            recommendation_type=rec_type,
            title=title,
            explanation=explanation,
            reasoning_steps=reasoning_steps,
            data_sources=data_sources,
            key_factors=key_factors,
            confidence_score=confidence,
            confidence_reason=conf_reason,
        )
        self.db.add(exp)
        await self.db.commit()
        await self.db.refresh(exp)
        return exp

    async def add_scoring_factor(
        self, rec_id: int, name: str, category: str, weight: float,
        score: float, data_source: Optional[str] = None, raw_value: Optional[str] = None,
    ) -> AIScoringFactor:
        factor = AIScoringFactor(
            recommendation_id=rec_id,
            factor_name=name,
            factor_category=category,
            weight=weight,
            score=score,
            weighted_score=weight * score,
            data_source=data_source,
            raw_value=raw_value,
            explanation=f"{name}: raw score {score} * weight {weight} = {weight * score:.4f}",
        )
        self.db.add(factor)
        await self.db.commit()
        await self.db.refresh(factor)
        return factor

    async def get_explanation(self, rec_id: int) -> Optional[AIRecommendationExplanation]:
        result = await self.db.execute(
            select(AIRecommendationExplanation).where(AIRecommendationExplanation.recommendation_id == rec_id)
            .order_by(desc(AIRecommendationExplanation.created_at))
        )
        return result.scalar_one_or_none()

    async def get_scoring_factors(self, rec_id: int) -> List[AIScoringFactor]:
        result = await self.db.execute(
            select(AIScoringFactor).where(AIScoringFactor.recommendation_id == rec_id)
        )
        return result.scalars().all()
