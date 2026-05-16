"""Revenue Intelligence Layer service - Phase 5."""

from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.revenue_models import (
    CampaignRevenueCorrelation,
    BranchRevenueAttribution,
    InventoryCampaignAnalysis,
    PromotionEffectiveness,
    CustomerLifetimeValue,
)


class RevenueIntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_campaign_revenue(
        self, company_id: int, branch_id: int, campaign_id: int,
        campaign_type: str, period: str, spend: float, revenue: float,
        orders: int, customers: int
    ) -> CampaignRevenueCorrelation:
        cpa = spend / customers if customers > 0 else 0
        roi = ((revenue - spend) / spend * 100) if spend > 0 else 0
        cor = CampaignRevenueCorrelation(
            company_id=company_id, branch_id=branch_id,
            campaign_id=campaign_id, campaign_type=campaign_type, period=period,
            campaign_spend=spend, attributed_revenue=revenue,
            attributed_orders=orders, attributed_customers=customers,
            roi_pct=round(roi, 2), cost_per_acquisition=round(cpa, 2),
            correlation_strength=round(min(1.0, revenue / (spend * 3)), 2) if spend > 0 else 0,
        )
        self.db.add(cor)
        await self.db.commit()
        await self.db.refresh(cor)
        return cor

    async def get_campaign_roi_summary(self, company_id: int) -> dict:
        result = await self.db.execute(
            select(func.avg(CampaignRevenueCorrelation.roi_pct),
                   func.sum(CampaignRevenueCorrelation.attributed_revenue),
                   func.sum(CampaignRevenueCorrelation.campaign_spend),
                   func.count()).where(CampaignRevenueCorrelation.company_id == company_id)
        )
        avg_roi, total_rev, total_spend, count = result.one()
        return {
            "avg_roi_pct": round(float(avg_roi or 0), 2),
            "total_attributed_revenue": float(total_rev or 0),
            "total_campaign_spend": float(total_spend or 0),
            "total_campaigns": int(count or 0),
            "net_return": float((total_rev or 0) - (total_spend or 0)),
        }

    async def record_branch_revenue(
        self, company_id: int, branch_id: int, date: str,
        total_revenue: float, campaign_rev: float, organic_rev: float,
        ad_spend: float, customer_count: int
    ) -> BranchRevenueAttribution:
        margin = ((total_revenue - ad_spend) / total_revenue * 100) if total_revenue > 0 else 0
        aov = total_revenue / customer_count if customer_count > 0 else 0
        bra = BranchRevenueAttribution(
            company_id=company_id, branch_id=branch_id, date=date,
            total_revenue=total_revenue, campaign_attributed_revenue=campaign_rev,
            organic_revenue=organic_rev, ad_spend=ad_spend,
            profit_margin_pct=round(margin, 2),
            customer_count=customer_count, avg_order_value=round(aov, 2),
        )
        self.db.add(bra)
        await self.db.commit()
        await self.db.refresh(bra)
        return bra

    async def get_branch_ranking(self, company_id: int, date: str) -> List[BranchRevenueAttribution]:
        result = await self.db.execute(
            select(BranchRevenueAttribution).where(
                BranchRevenueAttribution.company_id == company_id,
                BranchRevenueAttribution.date == date
            ).order_by(desc(BranchRevenueAttribution.total_revenue))
        )
        return result.scalars().all()

    async def record_promotion_effectiveness(
        self, company_id: int, branch_id: int, promotion_id: int,
        promo_type: str, discount_pct: float, revenue_lift: float,
        units_lift: float, margin_impact: float
    ) -> PromotionEffectiveness:
        score = (revenue_lift * 0.4 + units_lift * 0.3 + (100 + margin_impact) * 0.3)
        pe = PromotionEffectiveness(
            company_id=company_id, branch_id=branch_id,
            promotion_id=promotion_id, promotion_type=promo_type,
            discount_pct=discount_pct, revenue_lift_pct=round(revenue_lift, 2),
            units_lift_pct=round(units_lift, 2), margin_impact_pct=round(margin_impact, 2),
            overall_score=round(min(100, max(0, score)), 2),
        )
        self.db.add(pe)
        await self.db.commit()
        await self.db.refresh(pe)
        return pe

    async def get_top_promotions(self, company_id: int, limit: int = 10) -> List[PromotionEffectiveness]:
        result = await self.db.execute(
            select(PromotionEffectiveness).where(
                PromotionEffectiveness.company_id == company_id
            ).order_by(desc(PromotionEffectiveness.overall_score)).limit(limit)
        )
        return result.scalars().all()

    async def get_ltv_summary(self, company_id: int) -> dict:
        result = await self.db.execute(
            select(func.avg(CustomerLifetimeValue.total_revenue),
                   func.avg(CustomerLifetimeValue.predicted_ltv),
                   func.count()).where(CustomerLifetimeValue.company_id == company_id)
        )
        avg_rev, avg_ltv, count = result.one()
        return {
            "total_customers": int(count or 0),
            "avg_customer_revenue": round(float(avg_rev or 0), 2),
            "avg_predicted_ltv": round(float(avg_ltv or 0), 2) if avg_ltv else None,
        }
