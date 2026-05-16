"""Revenue Intelligence Layer router - Phase 5."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.analytics.revenue_service import RevenueIntelligenceService

router = APIRouter(prefix="/revenue-intelligence", tags=["Revenue Intelligence"])


class CampaignRevenueRecord(BaseModel):
    branch_id: int
    campaign_id: int
    campaign_type: str = "general"
    period: str = "daily"
    spend: float = 0
    revenue: float = 0
    orders: int = 0
    customers: int = 0


class BranchRevenueRecord(BaseModel):
    branch_id: int
    date: str
    total_revenue: float = 0
    campaign_revenue: float = 0
    organic_revenue: float = 0
    ad_spend: float = 0
    customer_count: int = 0


class PromotionRecord(BaseModel):
    branch_id: int
    promotion_id: int
    promotion_type: str = "discount"
    discount_pct: float = 0
    revenue_lift: float = 0
    units_lift: float = 0
    margin_impact: float = 0


@router.post("/campaign-revenue")
async def record_campaign_revenue(
    req: CampaignRevenueRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    rec = await svc.record_campaign_revenue(
        current_user.company_id, req.branch_id, req.campaign_id,
        req.campaign_type, req.period, req.spend, req.revenue,
        req.orders, req.customers,
    )
    return {"record": rec, "roi_pct": float(rec.roi_pct)}


@router.get("/campaign-roi-summary")
async def campaign_roi_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    return await svc.get_campaign_roi_summary(current_user.company_id)


@router.post("/branch-revenue")
async def record_branch_revenue(
    req: BranchRevenueRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    rec = await svc.record_branch_revenue(
        current_user.company_id, req.branch_id, req.date,
        req.total_revenue, req.campaign_revenue, req.organic_revenue,
        req.ad_spend, req.customer_count,
    )
    return {"record": rec}


@router.get("/branch-ranking/{date}")
async def branch_ranking(
    date: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    ranking = await svc.get_branch_ranking(current_user.company_id, date)
    return {"branches": ranking, "count": len(ranking)}


@router.post("/promotion-effectiveness")
async def record_promotion(
    req: PromotionRecord,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    rec = await svc.record_promotion_effectiveness(
        current_user.company_id, req.branch_id, req.promotion_id,
        req.promotion_type, req.discount_pct, req.revenue_lift,
        req.units_lift, req.margin_impact,
    )
    return {"record": rec, "score": float(rec.overall_score)}


@router.get("/top-promotions")
async def top_promotions(
    limit: int = 10,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    promos = await svc.get_top_promotions(current_user.company_id, limit)
    return {"promotions": promos, "count": len(promos)}


@router.get("/ltv-summary")
async def ltv_summary(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = RevenueIntelligenceService(db)
    return await svc.get_ltv_summary(current_user.company_id)
