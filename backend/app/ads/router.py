"""Ads Intelligence API router.

Provides endpoints for:
- Ad platform management (connect/disconnect/list)
- Campaign CRUD operations
- Creative management
- Audience management and analysis
- Performance metrics and dashboard
- Budget recommendations (AI-powered)
- Creative fatigue detection
- Local campaign recommendations
- ROAS and CPA analytics
- Data synchronization from ad platforms

Router is mounted at /api/v2/ads via main.py registration.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.constants import AdPlatform, INDUSTRY_BENCHMARKS, PlatformStatus
from app.ads.models import (
    AdAudience,
    AdBudgetRecommendation,
    AdCampaign,
    AdCreative,
    AdCreativeAnalysis,
    AdMetric,
    AdPlatformAccount,
    AnalysisType,
)
from app.ads.schemas import (
    ABTestResultResponse,
    AdAudienceCreate,
    AdAudienceListResponse,
    AdAudienceResponse,
    AdAudienceUpdate,
    AdBudgetRecommendationListResponse,
    AdBudgetRecommendationResponse,
    AdCampaignCreate,
    AdCampaignListResponse,
    AdCampaignMetricsResponse,
    AdCampaignResponse,
    AdCampaignUpdate,
    AdCreativeCreate,
    AdCreativeListResponse,
    AdCreativeResponse,
    AdCreativeUpdate,
    AdMetricListResponse,
    AdMetricResponse,
    AdPlatformCreate,
    AdPlatformCredentials,
    AdPlatformListResponse,
    AdPlatformResponse,
    AdPlatformUpdate,
    AggregatedMetricsResponse,
    AudienceOverlapResponse,
    CPAAnalysisResponse,
    CreativeFatigueResponse,
    DateRangeFilter,
    LocalRecommendationsResponse,
    PaginatedResponse,
    PerformanceDashboardResponse,
    ROASAnalysisResponse,
    SyncRequest,
    SyncResponse,
)
from app.ads.service import (
    AudienceAnalysisService,
    BudgetRecommendationService,
    CPAService,
    CreativeFatigueService,
    DataSyncService,
    GoogleAdsService,
    LocalCampaignService,
    MetaAdsService,
    ROASService,
)
from app.dependencies import get_current_user, get_db, require_role
from app.exceptions import NotFoundError, ValidationError
from app.utils.encryption import encrypt_api_credentials

router = APIRouter()


# =============================================================================
# Helper: Build tenant-filtered queries
# =============================================================================


def _apply_tenant_filter(query, current_user, model):
    """Apply company/branch tenant filter to a query."""
    if current_user.company_id:
        query = query.where(model.company_id == int(current_user.company_id))
    if current_user.branch_id:
        query = query.where(model.branch_id == int(current_user.branch_id))
    return query


def _check_tenant_access(current_user):
    """Verify user is associated with a company."""
    if not current_user.company_id:
        raise ValidationError(detail="User is not associated with a company")
    return int(current_user.company_id)


# =============================================================================
# Ad Platform Endpoints
# =============================================================================


@router.post(
    "/platforms",
    response_model=AdPlatformResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect an ad platform account",
)
async def connect_platform(
    data: AdPlatformCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdPlatformResponse:
    """Connect a Google Ads or Meta Ads account.

    Encrypts and stores OAuth credentials securely.
    """
    company_id = _check_tenant_access(current_user)

    # Encrypt credentials
    encrypted_access = encrypt_api_credentials(
        {"access_token": data.credentials.access_token}
    )
    encrypted_refresh = encrypt_api_credentials(
        {"refresh_token": data.credentials.refresh_token}
    )
    encrypted_dev = None
    if data.credentials.developer_token:
        encrypted_dev = encrypt_api_credentials(
            {"developer_token": data.credentials.developer_token}
        )

    platform_account = AdPlatformAccount(
        company_id=company_id,
        branch_id=data.branch_id,
        platform=data.platform,
        account_id=data.account_id,
        account_name=data.account_name,
        access_token_encrypted=encrypted_access,
        refresh_token_encrypted=encrypted_refresh,
        developer_token_encrypted=encrypted_dev,
        currency=data.currency,
        timezone=data.timezone,
        status=PlatformStatus.ACTIVE,
        settings=data.settings,
    )

    db.add(platform_account)
    await db.commit()
    await db.refresh(platform_account)

    return AdPlatformResponse.model_validate(platform_account)


@router.get(
    "/platforms",
    response_model=AdPlatformListResponse,
    status_code=status.HTTP_200_OK,
    summary="List connected ad platform accounts",
)
async def list_platforms(
    platform: Optional[AdPlatform] = Query(default=None, description="Filter by platform"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdPlatformListResponse:
    """List all connected ad platform accounts for the company."""
    company_id = _check_tenant_access(current_user)

    query = select(AdPlatformAccount).where(
        AdPlatformAccount.company_id == company_id
    ).order_by(desc(AdPlatformAccount.created_at))

    if platform:
        query = query.where(AdPlatformAccount.platform == platform)

    result = await db.execute(query)
    accounts = result.scalars().all()

    return AdPlatformListResponse(
        items=[AdPlatformResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.get(
    "/platforms/{platform_id}",
    response_model=AdPlatformResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ad platform account details",
)
async def get_platform(
    platform_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdPlatformResponse:
    """Get details of a specific connected ad platform account."""
    company_id = _check_tenant_access(current_user)

    query = select(AdPlatformAccount).where(
        and_(
            AdPlatformAccount.id == platform_id,
            AdPlatformAccount.company_id == company_id,
        )
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(detail=f"Platform account {platform_id} not found")

    return AdPlatformResponse.model_validate(account)


@router.put(
    "/platforms/{platform_id}",
    response_model=AdPlatformResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ad platform account",
)
async def update_platform(
    platform_id: int,
    data: AdPlatformUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdPlatformResponse:
    """Update a connected ad platform account."""
    company_id = _check_tenant_access(current_user)

    query = select(AdPlatformAccount).where(
        and_(
            AdPlatformAccount.id == platform_id,
            AdPlatformAccount.company_id == company_id,
        )
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(detail=f"Platform account {platform_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    account.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)

    return AdPlatformResponse.model_validate(account)


@router.delete(
    "/platforms/{platform_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect an ad platform account",
)
async def disconnect_platform(
    platform_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    """Disconnect an ad platform account and delete all associated data."""
    company_id = _check_tenant_access(current_user)

    query = select(AdPlatformAccount).where(
        and_(
            AdPlatformAccount.id == platform_id,
            AdPlatformAccount.company_id == company_id,
        )
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise NotFoundError(detail=f"Platform account {platform_id} not found")

    await db.delete(account)
    await db.commit()


# =============================================================================
# Campaign Endpoints
# =============================================================================


@router.get(
    "/campaigns",
    response_model=AdCampaignListResponse,
    status_code=status.HTTP_200_OK,
    summary="List ad campaigns",
)
async def list_campaigns(
    platform: Optional[AdPlatform] = Query(default=None, description="Filter by platform"),
    status_filter: Optional[str] = Query(default=None, description="Filter by status"),
    search: Optional[str] = Query(default=None, description="Search by name"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCampaignListResponse:
    """List all ad campaigns for the company."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCampaign).where(
        AdCampaign.company_id == company_id
    ).order_by(desc(AdCampaign.created_at))

    if platform:
        query = query.where(AdCampaign.platform == platform)
    if status_filter:
        query = query.where(AdCampaign.status == status_filter)
    if search:
        query = query.where(AdCampaign.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    campaigns = result.scalars().all()

    return AdCampaignListResponse(
        items=[AdCampaignResponse.model_validate(c) for c in campaigns],
        total=total,
    )


@router.get(
    "/campaigns/{campaign_id}",
    response_model=AdCampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Get campaign details",
)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCampaignResponse:
    """Get detailed information about a specific campaign."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCampaign).where(
        and_(
            AdCampaign.id == campaign_id,
            AdCampaign.company_id == company_id,
        )
    )
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise NotFoundError(detail=f"Campaign {campaign_id} not found")

    return AdCampaignResponse.model_validate(campaign)


@router.post(
    "/campaigns",
    response_model=AdCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ad campaign",
)
async def create_campaign(
    data: AdCampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCampaignResponse:
    """Create a new ad campaign."""
    company_id = _check_tenant_access(current_user)

    campaign = AdCampaign(
        company_id=company_id,
        branch_id=current_user.branch_id,
        platform=data.platform,
        platform_campaign_id=data.platform_campaign_id or "",
        name=data.name,
        objective=data.objective,
        status=data.status,
        budget=data.budget,
        budget_type=data.budget_type,
        start_date=data.start_date,
        end_date=data.end_date,
        targeting=data.targeting,
        bid_strategy=data.bid_strategy,
        ai_optimized=data.ai_optimized,
    )

    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return AdCampaignResponse.model_validate(campaign)


@router.put(
    "/campaigns/{campaign_id}",
    response_model=AdCampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ad campaign",
)
async def update_campaign(
    campaign_id: int,
    data: AdCampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCampaignResponse:
    """Update an existing ad campaign."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCampaign).where(
        and_(
            AdCampaign.id == campaign_id,
            AdCampaign.company_id == company_id,
        )
    )
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise NotFoundError(detail=f"Campaign {campaign_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    campaign.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)

    return AdCampaignResponse.model_validate(campaign)


@router.delete(
    "/campaigns/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ad campaign",
)
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    """Delete an ad campaign and all associated data."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCampaign).where(
        and_(
            AdCampaign.id == campaign_id,
            AdCampaign.company_id == company_id,
        )
    )
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise NotFoundError(detail=f"Campaign {campaign_id} not found")

    await db.delete(campaign)
    await db.commit()


@router.get(
    "/campaigns/{campaign_id}/metrics",
    response_model=AdCampaignMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get campaign metrics",
)
async def get_campaign_metrics(
    campaign_id: int,
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCampaignMetricsResponse:
    """Get aggregated metrics for a specific campaign."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCampaign).where(
        and_(
            AdCampaign.id == campaign_id,
            AdCampaign.company_id == company_id,
        )
    )
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise NotFoundError(detail=f"Campaign {campaign_id} not found")

    # Default date range: last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    date_range = DateRangeFilter(start_date=start_date, end_date=end_date)

    query = select(
        func.sum(AdMetric.impressions).label("total_impressions"),
        func.sum(AdMetric.clicks).label("total_clicks"),
        func.sum(AdMetric.conversions).label("total_conversions"),
        func.sum(AdMetric.cost).label("total_cost"),
        func.sum(AdMetric.conversion_value).label("total_value"),
    ).where(
        and_(
            AdMetric.campaign_id == campaign_id,
            AdMetric.date >= start_date,
            AdMetric.date <= end_date,
        )
    )

    result = await db.execute(query)
    row = result.one_or_none()

    impressions = int(row.total_impressions or 0) if row else 0
    clicks = int(row.total_clicks or 0) if row else 0
    conversions = float(row.total_conversions or 0) if row else 0
    cost = Decimal(str(row.total_cost or 0)) if row else Decimal("0")
    value = Decimal(str(row.total_value or 0)) if row else Decimal("0")

    ctr = (Decimal(str(clicks)) / Decimal(str(impressions)) * Decimal("100")) if impressions > 0 else None
    cpc = cost / Decimal(str(clicks)) if clicks > 0 else None
    cpa = cost / Decimal(str(conversions)) if conversions > 0 else None
    roas = value / cost if cost > 0 else None

    return AdCampaignMetricsResponse(
        campaign_id=campaign_id,
        campaign_name=campaign.name,
        platform=campaign.platform,
        date_range=date_range,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        cost=cost,
        ctr=round(ctr, 4) if ctr else None,
        cpc=round(cpc, 4) if cpc else None,
        cpa=round(cpa, 4) if cpa else None,
        roas=round(roas, 4) if roas else None,
        conversion_value=value,
    )


# =============================================================================
# Creative Endpoints
# =============================================================================


@router.get(
    "/creatives",
    response_model=AdCreativeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List ad creatives",
)
async def list_creatives(
    campaign_id: Optional[int] = Query(default=None, description="Filter by campaign"),
    creative_type: Optional[str] = Query(default=None, description="Filter by type"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCreativeListResponse:
    """List all ad creatives for the company."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCreative).where(
        AdCreative.company_id == company_id
    ).order_by(desc(AdCreative.created_at))

    if campaign_id:
        query = query.where(AdCreative.campaign_id == campaign_id)
    if creative_type:
        query = query.where(AdCreative.creative_type == creative_type)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    creatives = result.scalars().all()

    return AdCreativeListResponse(
        items=[AdCreativeResponse.model_validate(c) for c in creatives],
        total=total,
    )


@router.get(
    "/creatives/{creative_id}",
    response_model=AdCreativeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get creative details",
)
async def get_creative(
    creative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCreativeResponse:
    """Get details of a specific ad creative."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCreative).where(
        and_(
            AdCreative.id == creative_id,
            AdCreative.company_id == company_id,
        )
    )
    result = await db.execute(query)
    creative = result.scalar_one_or_none()

    if not creative:
        raise NotFoundError(detail=f"Creative {creative_id} not found")

    return AdCreativeResponse.model_validate(creative)


@router.put(
    "/creatives/{creative_id}",
    response_model=AdCreativeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ad creative",
)
async def update_creative(
    creative_id: int,
    data: AdCreativeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdCreativeResponse:
    """Update an existing ad creative."""
    company_id = _check_tenant_access(current_user)

    query = select(AdCreative).where(
        and_(
            AdCreative.id == creative_id,
            AdCreative.company_id == company_id,
        )
    )
    result = await db.execute(query)
    creative = result.scalar_one_or_none()

    if not creative:
        raise NotFoundError(detail=f"Creative {creative_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(creative, field, value)

    creative.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(creative)

    return AdCreativeResponse.model_validate(creative)


# =============================================================================
# Metrics Endpoints
# =============================================================================


@router.get(
    "/metrics",
    response_model=AggregatedMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated metrics",
)
async def get_metrics(
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    platform: Optional[AdPlatform] = Query(default=None, description="Filter by platform"),
    campaign_id: Optional[int] = Query(default=None, description="Filter by campaign"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AggregatedMetricsResponse:
    """Get aggregated ad metrics with optional filtering."""
    company_id = _check_tenant_access(current_user)

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    date_range = DateRangeFilter(start_date=start_date, end_date=end_date)

    # Build the query
    query = (
        select(
            func.sum(AdMetric.impressions).label("total_impressions"),
            func.sum(AdMetric.clicks).label("total_clicks"),
            func.sum(AdMetric.conversions).label("total_conversions"),
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.conversion_value).label("total_value"),
            func.avg(AdMetric.ctr).label("avg_ctr"),
            func.avg(AdMetric.cpc).label("avg_cpc"),
            func.avg(AdMetric.cpa).label("avg_cpa"),
            func.avg(AdMetric.roas).label("avg_roas"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
    )

    if platform:
        query = query.where(AdCampaign.platform == platform)
    if campaign_id:
        query = query.where(AdMetric.campaign_id == campaign_id)

    result = await db.execute(query)
    row = result.one_or_none()

    impressions = int(row.total_impressions or 0) if row else 0
    clicks = int(row.total_clicks or 0) if row else 0
    conversions = float(row.total_conversions or 0) if row else 0
    total_cost = Decimal(str(row.total_cost or 0)) if row else Decimal("0")
    total_value = Decimal(str(row.total_value or 0)) if row else Decimal("0")

    # Get daily breakdown
    daily_query = (
        select(AdMetric)
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .order_by(AdMetric.date)
    )

    if platform:
        daily_query = daily_query.where(AdCampaign.platform == platform)
    if campaign_id:
        daily_query = daily_query.where(AdMetric.campaign_id == campaign_id)

    daily_result = await db.execute(daily_query)
    daily_metrics = daily_result.scalars().all()

    return AggregatedMetricsResponse(
        date_range=date_range,
        platform=platform,
        campaign_id=campaign_id,
        total_impressions=impressions,
        total_clicks=clicks,
        total_conversions=conversions,
        total_cost=total_cost,
        total_conversion_value=total_value,
        avg_ctr=round(Decimal(str(row.avg_ctr or 0)), 4) if row and row.avg_ctr else None,
        avg_cpc=round(Decimal(str(row.avg_cpc or 0)), 4) if row and row.avg_cpc else None,
        avg_cpa=round(Decimal(str(row.avg_cpa or 0)), 4) if row and row.avg_cpa else None,
        avg_roas=round(Decimal(str(row.avg_roas or 0)), 4) if row and row.avg_roas else None,
        daily_breakdown=[AdMetricResponse.model_validate(m) for m in daily_metrics],
    )


# =============================================================================
# Audience Endpoints
# =============================================================================


@router.get(
    "/audiences",
    response_model=AdAudienceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List ad audiences",
)
async def list_audiences(
    platform: Optional[AdPlatform] = Query(default=None, description="Filter by platform"),
    audience_type: Optional[str] = Query(default=None, description="Filter by type"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdAudienceListResponse:
    """List all ad audiences for the company."""
    company_id = _check_tenant_access(current_user)

    query = select(AdAudience).where(
        AdAudience.company_id == company_id
    ).order_by(desc(AdAudience.created_at))

    if platform:
        query = query.where(AdAudience.platform == platform)
    if audience_type:
        query = query.where(AdAudience.audience_type == audience_type)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    audiences = result.scalars().all()

    return AdAudienceListResponse(
        items=[AdAudienceResponse.model_validate(a) for a in audiences],
        total=total,
    )


@router.post(
    "/audiences",
    response_model=AdAudienceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ad audience",
)
async def create_audience(
    data: AdAudienceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdAudienceResponse:
    """Create a new ad audience definition."""
    company_id = _check_tenant_access(current_user)

    audience = AdAudience(
        company_id=company_id,
        branch_id=data.branch_id,
        platform=data.platform,
        name=data.name,
        audience_type=data.audience_type,
        size_estimate=data.size_estimate,
        targeting_spec=data.targeting_spec,
        platform_audience_id=data.platform_audience_id,
        performance_score=data.performance_score,
    )

    db.add(audience)
    await db.commit()
    await db.refresh(audience)

    return AdAudienceResponse.model_validate(audience)


@router.get(
    "/audiences/{audience_id}",
    response_model=AdAudienceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audience details",
)
async def get_audience(
    audience_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdAudienceResponse:
    """Get details of a specific audience."""
    company_id = _check_tenant_access(current_user)

    query = select(AdAudience).where(
        and_(
            AdAudience.id == audience_id,
            AdAudience.company_id == company_id,
        )
    )
    result = await db.execute(query)
    audience = result.scalar_one_or_none()

    if not audience:
        raise NotFoundError(detail=f"Audience {audience_id} not found")

    return AdAudienceResponse.model_validate(audience)


@router.put(
    "/audiences/{audience_id}",
    response_model=AdAudienceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update ad audience",
)
async def update_audience(
    audience_id: int,
    data: AdAudienceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdAudienceResponse:
    """Update an existing ad audience."""
    company_id = _check_tenant_access(current_user)

    query = select(AdAudience).where(
        and_(
            AdAudience.id == audience_id,
            AdAudience.company_id == company_id,
        )
    )
    result = await db.execute(query)
    audience = result.scalar_one_or_none()

    if not audience:
        raise NotFoundError(detail=f"Audience {audience_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(audience, field, value)

    audience.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(audience)

    return AdAudienceResponse.model_validate(audience)


@router.delete(
    "/audiences/{audience_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete ad audience",
)
async def delete_audience(
    audience_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    """Delete an ad audience."""
    company_id = _check_tenant_access(current_user)

    query = select(AdAudience).where(
        and_(
            AdAudience.id == audience_id,
            AdAudience.company_id == company_id,
        )
    )
    result = await db.execute(query)
    audience = result.scalar_one_or_none()

    if not audience:
        raise NotFoundError(detail=f"Audience {audience_id} not found")

    await db.delete(audience)
    await db.commit()


@router.get(
    "/audiences/{audience_id}/performance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get audience performance analysis",
)
async def get_audience_performance(
    audience_id: int,
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Analyze performance for a specific audience."""
    company_id = _check_tenant_access(current_user)

    # Verify audience belongs to company
    query = select(AdAudience).where(
        and_(
            AdAudience.id == audience_id,
            AdAudience.company_id == company_id,
        )
    )
    result = await db.execute(query)
    audience = result.scalar_one_or_none()

    if not audience:
        raise NotFoundError(detail=f"Audience {audience_id} not found")

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    date_range = DateRangeFilter(start_date=start_date, end_date=end_date)
    return await AudienceAnalysisService.analyze_audience_performance(
        db, audience_id, date_range
    )


# =============================================================================
# Performance Dashboard
# =============================================================================


@router.get(
    "/performance",
    response_model=PerformanceDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get performance dashboard data",
)
async def get_performance_dashboard(
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> PerformanceDashboardResponse:
    """Get performance dashboard data for the company."""
    company_id = _check_tenant_access(current_user)

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    date_range = DateRangeFilter(start_date=start_date, end_date=end_date)

    # Summary metrics
    summary_query = (
        select(
            func.sum(AdMetric.impressions).label("total_impressions"),
            func.sum(AdMetric.clicks).label("total_clicks"),
            func.sum(AdMetric.conversions).label("total_conversions"),
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.conversion_value).label("total_value"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
    )
    summary_result = await db.execute(summary_query)
    summary_row = summary_result.one_or_none()

    impressions = int(summary_row.total_impressions or 0) if summary_row else 0
    clicks = int(summary_row.total_clicks or 0) if summary_row else 0
    conversions = float(summary_row.total_conversions or 0) if summary_row else 0
    cost = Decimal(str(summary_row.total_cost or 0)) if summary_row else Decimal("0")
    value = Decimal(str(summary_row.total_value or 0)) if summary_row else Decimal("0")

    ctr = (Decimal(str(clicks)) / Decimal(str(impressions)) * Decimal("100")) if impressions > 0 else Decimal("0")
    cpc = cost / Decimal(str(clicks)) if clicks > 0 else Decimal("0")
    roas = value / cost if cost > 0 else Decimal("0")

    # Platform breakdown
    platform_query = (
        select(
            AdCampaign.platform,
            func.sum(AdMetric.impressions).label("impressions"),
            func.sum(AdMetric.clicks).label("clicks"),
            func.sum(AdMetric.cost).label("cost"),
            func.sum(AdMetric.conversion_value).label("value"),
        )
        .join(AdMetric, AdCampaign.id == AdMetric.campaign_id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdCampaign.platform)
    )
    platform_result = await db.execute(platform_query)
    platform_breakdown = [
        {
            "platform": row.platform.value,
            "impressions": int(row.impressions or 0),
            "clicks": int(row.clicks or 0),
            "cost": float(Decimal(str(row.cost or 0))),
            "conversion_value": float(Decimal(str(row.value or 0))),
        }
        for row in platform_result.all()
    ]

    # Top campaigns
    campaign_query = (
        select(
            AdCampaign.id,
            AdCampaign.name,
            AdCampaign.platform,
            func.sum(AdMetric.impressions).label("impressions"),
            func.sum(AdMetric.clicks).label("clicks"),
            func.sum(AdMetric.conversions).label("conversions"),
            func.sum(AdMetric.cost).label("cost"),
            func.sum(AdMetric.conversion_value).label("value"),
        )
        .join(AdMetric, AdCampaign.id == AdMetric.campaign_id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdCampaign.id, AdCampaign.name, AdCampaign.platform)
        .order_by(desc(func.sum(AdMetric.conversion_value)))
        .limit(10)
    )
    campaign_result = await db.execute(campaign_query)
    campaign_performance = [
        {
            "campaign_id": row.id,
            "campaign_name": row.name,
            "platform": row.platform.value,
            "impressions": int(row.impressions or 0),
            "clicks": int(row.clicks or 0),
            "conversions": float(row.conversions or 0),
            "cost": float(Decimal(str(row.cost or 0))),
            "conversion_value": float(Decimal(str(row.value or 0))),
            "roas": round(
                Decimal(str(row.value or 0)) / Decimal(str(row.cost or 1)), 4
            ),
        }
        for row in campaign_result.all()
    ]

    # Trends (last 14 days daily)
    trends_start = end_date - timedelta(days=14)
    trends_query = (
        select(
            AdMetric.date,
            func.sum(AdMetric.impressions).label("impressions"),
            func.sum(AdMetric.clicks).label("clicks"),
            func.sum(AdMetric.cost).label("cost"),
            func.sum(AdMetric.conversion_value).label("value"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= trends_start,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdMetric.date)
        .order_by(AdMetric.date)
    )
    trends_result = await db.execute(trends_query)
    trends_daily = [
        {
            "date": row.date.isoformat(),
            "impressions": int(row.impressions or 0),
            "clicks": int(row.clicks or 0),
            "cost": float(Decimal(str(row.cost or 0))),
            "conversion_value": float(Decimal(str(row.value or 0))),
        }
        for row in trends_result.all()
    ]

    return PerformanceDashboardResponse(
        date_range=date_range,
        summary={
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "cost": float(cost),
            "conversion_value": float(value),
            "ctr": round(float(ctr), 4),
            "cpc": round(float(cpc), 4),
            "roas": round(float(roas), 4),
        },
        platform_breakdown=platform_breakdown,
        campaign_performance=campaign_performance,
        trends={"daily": trends_daily},
    )


# =============================================================================
# Budget Recommendations
# =============================================================================


@router.get(
    "/recommendations/budget",
    response_model=AdBudgetRecommendationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get budget recommendations",
)
async def get_budget_recommendations(
    applied: Optional[bool] = Query(default=None, description="Filter by applied status"),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdBudgetRecommendationListResponse:
    """Get AI-powered budget recommendations."""
    company_id = _check_tenant_access(current_user)

    recommendations = await BudgetRecommendationService.list_recommendations(
        db, company_id, applied=applied, limit=limit
    )

    return AdBudgetRecommendationListResponse(
        items=[
            AdBudgetRecommendationResponse.model_validate(r)
            for r in recommendations
        ],
        total=len(recommendations),
    )


@router.post(
    "/recommendations/budget/generate",
    response_model=AdBudgetRecommendationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate new budget recommendations",
)
async def generate_budget_recommendations(
    industry: str = Query(default="general", description="Industry for benchmarks"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdBudgetRecommendationListResponse:
    """Generate fresh AI-powered budget recommendations."""
    company_id = _check_tenant_access(current_user)

    recommendations = await BudgetRecommendationService.generate_recommendations(
        db, company_id, industry=industry
    )

    return AdBudgetRecommendationListResponse(
        items=[
            AdBudgetRecommendationResponse.model_validate(r)
            for r in recommendations
        ],
        total=len(recommendations),
    )


@router.post(
    "/recommendations/budget/{recommendation_id}/apply",
    response_model=AdBudgetRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply budget recommendation",
)
async def apply_budget_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> AdBudgetRecommendationResponse:
    """Mark a budget recommendation as applied."""
    company_id = _check_tenant_access(current_user)

    recommendation = await BudgetRecommendationService.apply_recommendation(
        db, recommendation_id, company_id
    )

    return AdBudgetRecommendationResponse.model_validate(recommendation)


# =============================================================================
# Creative Recommendations
# =============================================================================


@router.get(
    "/recommendations/creative",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get creative refresh recommendations",
)
async def get_creative_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get creative fatigue alerts and refresh recommendations."""
    company_id = _check_tenant_access(current_user)

    alerts = await CreativeFatigueService.get_fatigue_alerts(db, company_id)

    return {
        "total_alerts": len(alerts),
        "severe": len([a for a in alerts if a["fatigue_level"] == "severe"]),
        "moderate": len([a for a in alerts if a["fatigue_level"] == "moderate"]),
        "creatives": alerts,
        "generated_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Local Campaign Recommendations
# =============================================================================


@router.get(
    "/recommendations/local",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get local campaign recommendations",
)
async def get_local_recommendations(
    industry: str = Query(default="restaurants", description="Industry type"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get geo-targeted local campaign recommendations for branches."""
    company_id = _check_tenant_access(current_user)

    return await LocalCampaignService.generate_local_recommendations(
        db, company_id, industry=industry
    )


# =============================================================================
# Analytics - ROAS
# =============================================================================


@router.get(
    "/analytics/roas",
    response_model=ROASAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ROAS analysis",
)
async def get_roas_analysis(
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    campaign_id: Optional[int] = Query(default=None, description="Filter by campaign"),
    industry: str = Query(default="general", description="Industry for benchmarks"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ROASAnalysisResponse:
    """Get ROAS analysis with trend and benchmark comparison."""
    company_id = _check_tenant_access(current_user)

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    date_range = DateRangeFilter(start_date=start_date, end_date=end_date)

    # Overall ROAS
    query = (
        select(
            func.sum(AdMetric.conversion_value).label("total_value"),
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.conversions).label("total_conversions"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
    )

    if campaign_id:
        query = query.where(AdMetric.campaign_id == campaign_id)

    result = await db.execute(query)
    row = result.one_or_none()

    total_value = Decimal(str(row.total_value or 0)) if row else Decimal("0")
    total_cost = Decimal(str(row.total_cost or 0)) if row else Decimal("0")
    total_conversions = float(row.total_conversions or 0) if row else 0
    total_roas = total_value / total_cost if total_cost > 0 else None

    # ROAS by campaign
    campaign_query = (
        select(
            AdCampaign.id,
            AdCampaign.name,
            AdCampaign.platform,
            func.sum(AdMetric.conversion_value).label("value"),
            func.sum(AdMetric.cost).label("cost"),
        )
        .join(AdMetric, AdCampaign.id == AdMetric.campaign_id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdCampaign.id, AdCampaign.name, AdCampaign.platform)
        .order_by(desc(func.sum(AdMetric.conversion_value)))
    )
    campaign_result = await db.execute(campaign_query)
    roas_by_campaign = [
        {
            "campaign_id": row.id,
            "campaign_name": row.name,
            "platform": row.platform.value,
            "roas": round(
                Decimal(str(row.value or 0)) / Decimal(str(row.cost or 1)), 4
            ),
            "conversion_value": float(Decimal(str(row.value or 0))),
            "cost": float(Decimal(str(row.cost or 0))),
        }
        for row in campaign_result.all()
    ]

    # ROAS by platform
    platform_query = (
        select(
            AdCampaign.platform,
            func.sum(AdMetric.conversion_value).label("value"),
            func.sum(AdMetric.cost).label("cost"),
        )
        .join(AdMetric, AdCampaign.id == AdMetric.campaign_id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdCampaign.platform)
    )
    platform_result = await db.execute(platform_query)
    roas_by_platform = [
        {
            "platform": row.platform.value,
            "roas": round(
                Decimal(str(row.value or 0)) / Decimal(str(row.cost or 1)), 4
            ),
            "conversion_value": float(Decimal(str(row.value or 0))),
            "cost": float(Decimal(str(row.cost or 0))),
        }
        for row in platform_result.all()
    ]

    # ROAS trend (daily)
    trend_query = (
        select(
            AdMetric.date,
            func.sum(AdMetric.conversion_value).label("value"),
            func.sum(AdMetric.cost).label("cost"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdMetric.date)
        .order_by(AdMetric.date)
    )
    trend_result = await db.execute(trend_query)
    roas_trend = [
        {
            "date": row.date.isoformat(),
            "roas": round(
                Decimal(str(row.value or 0)) / Decimal(str(row.cost or 1)), 4
            ),
            "conversion_value": float(Decimal(str(row.value or 0))),
            "cost": float(Decimal(str(row.cost or 0))),
        }
        for row in trend_result.all()
    ]

    # Benchmark comparison
    benchmark = INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["general"])
    benchmark_comparison = {
        "industry": industry,
        "benchmark_roas": benchmark["roas"],
        "actual_roas": round(float(total_roas or 0), 4),
        "difference_pct": round(
            ((float(total_roas or 0) - benchmark["roas"]) / benchmark["roas"]) * 100, 2
        ),
        "status": (
            "above_benchmark" if (total_roas and total_roas > Decimal(str(benchmark["roas"])))
            else "below_benchmark" if total_roas
            else "unknown"
        ),
    }

    # Recommendations
    recommendations = []
    if total_roas and total_roas < Decimal("1.5"):
        recommendations.append(
            "ROAS is below profitable threshold. Review targeting and creative performance."
        )
    if total_roas and total_roas > Decimal("5"):
        recommendations.append(
            "Excellent ROAS! Consider increasing budget to scale positive results."
        )

    return ROASAnalysisResponse(
        date_range=date_range,
        total_roas=round(total_roas, 4) if total_roas else None,
        total_conversion_value=total_value,
        total_spend=total_cost,
        roas_by_campaign=roas_by_campaign,
        roas_by_platform=roas_by_platform,
        roas_trend=roas_trend,
        benchmark_comparison=benchmark_comparison,
        recommendations=recommendations,
    )


# =============================================================================
# Analytics - CPA
# =============================================================================


@router.get(
    "/analytics/cpa",
    response_model=CPAAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get CPA analysis",
)
async def get_cpa_analysis(
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date"),
    campaign_id: Optional[int] = Query(default=None, description="Filter by campaign"),
    industry: str = Query(default="general", description="Industry for benchmarks"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CPAAnalysisResponse:
    """Get CPA analysis with trend and benchmark comparison."""
    company_id = _check_tenant_access(current_user)

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    date_range = DateRangeFilter(start_date=start_date, end_date=end_date)

    # Overall CPA
    query = (
        select(
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.conversions).label("total_conversions"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
    )

    if campaign_id:
        query = query.where(AdMetric.campaign_id == campaign_id)

    result = await db.execute(query)
    row = result.one_or_none()

    total_cost = Decimal(str(row.total_cost or 0)) if row else Decimal("0")
    total_conversions = float(row.total_conversions or 0) if row else 0
    total_cpa = total_cost / Decimal(str(total_conversions)) if total_conversions > 0 else None

    # CPA by campaign
    campaign_query = (
        select(
            AdCampaign.id,
            AdCampaign.name,
            AdCampaign.platform,
            func.sum(AdMetric.cost).label("cost"),
            func.sum(AdMetric.conversions).label("conversions"),
        )
        .join(AdMetric, AdCampaign.id == AdMetric.campaign_id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdCampaign.id, AdCampaign.name, AdCampaign.platform)
        .order_by(desc(func.sum(AdMetric.conversions)))
    )
    campaign_result = await db.execute(campaign_query)
    cpa_by_campaign = [
        {
            "campaign_id": row.id,
            "campaign_name": row.name,
            "platform": row.platform.value,
            "cpa": round(
                Decimal(str(row.cost or 0)) / Decimal(str(row.conversions or 1)), 4
            ),
            "cost": float(Decimal(str(row.cost or 0))),
            "conversions": float(row.conversions or 0),
        }
        for row in campaign_result.all()
    ]

    # CPA by platform
    platform_query = (
        select(
            AdCampaign.platform,
            func.sum(AdMetric.cost).label("cost"),
            func.sum(AdMetric.conversions).label("conversions"),
        )
        .join(AdMetric, AdCampaign.id == AdMetric.campaign_id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdCampaign.platform)
    )
    platform_result = await db.execute(platform_query)
    cpa_by_platform = [
        {
            "platform": row.platform.value,
            "cpa": round(
                Decimal(str(row.cost or 0)) / Decimal(str(row.conversions or 1)), 4
            ),
            "cost": float(Decimal(str(row.cost or 0))),
            "conversions": float(row.conversions or 0),
        }
        for row in platform_result.all()
    ]

    # CPA trend (daily)
    trend_query = (
        select(
            AdMetric.date,
            func.sum(AdMetric.cost).label("cost"),
            func.sum(AdMetric.conversions).label("conversions"),
        )
        .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
        .where(
            and_(
                AdCampaign.company_id == company_id,
                AdMetric.date >= start_date,
                AdMetric.date <= end_date,
            )
        )
        .group_by(AdMetric.date)
        .order_by(AdMetric.date)
    )
    trend_result = await db.execute(trend_query)
    cpa_trend = [
        {
            "date": row.date.isoformat(),
            "cpa": round(
                Decimal(str(row.cost or 0)) / Decimal(str(row.conversions or 1)), 4
            ),
            "cost": float(Decimal(str(row.cost or 0))),
            "conversions": float(row.conversions or 0),
        }
        for row in trend_result.all()
    ]

    # Benchmark comparison
    benchmark = INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["general"])
    benchmark_comparison = {
        "industry": industry,
        "benchmark_cpa": benchmark["cpa"],
        "actual_cpa": round(float(total_cpa or 0), 4),
        "difference_pct": round(
            ((float(total_cpa or 0) - benchmark["cpa"]) / benchmark["cpa"]) * 100, 2
        ),
        "status": (
            "below_benchmark" if (total_cpa and total_cpa < Decimal(str(benchmark["cpa"])))
            else "above_benchmark" if total_cpa
            else "unknown"
        ),
    }

    # Recommendations
    recommendations = []
    if total_cpa and total_cpa > Decimal(str(benchmark["cpa"])) * Decimal("1.5"):
        recommendations.append(
            f"CPA is significantly above industry benchmark ({benchmark['cpa']}). "
            "Review audience targeting and ad relevance."
        )
    if total_cpa and total_cpa < Decimal(str(benchmark["cpa"])) * Decimal("0.6"):
        recommendations.append(
            "CPA is well below benchmark. Opportunity to scale budget efficiently."
        )

    return CPAAnalysisResponse(
        date_range=date_range,
        total_cpa=round(total_cpa, 4) if total_cpa else None,
        total_conversions=int(total_conversions),
        total_cost=total_cost,
        cpa_by_campaign=cpa_by_campaign,
        cpa_by_platform=cpa_by_platform,
        cpa_trend=cpa_trend,
        benchmark_comparison=benchmark_comparison,
        recommendations=recommendations,
    )


# =============================================================================
# Creative Fatigue Endpoint
# =============================================================================


@router.get(
    "/creatives/{creative_id}/fatigue",
    response_model=CreativeFatigueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get creative fatigue analysis",
)
async def get_creative_fatigue(
    creative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CreativeFatigueResponse:
    """Analyze a creative for fatigue indicators."""
    company_id = _check_tenant_access(current_user)

    # Verify creative belongs to company
    query = select(AdCreative).where(
        and_(
            AdCreative.id == creative_id,
            AdCreative.company_id == company_id,
        )
    )
    result = await db.execute(query)
    creative = result.scalar_one_or_none()

    if not creative:
        raise NotFoundError(detail=f"Creative {creative_id} not found")

    analysis = await CreativeFatigueService.analyze_creative_fatigue(db, creative_id)

    return CreativeFatigueResponse(
        creative_id=analysis["creative_id"],
        creative_name=analysis["creative_name"],
        fatigue_score=analysis["fatigue_score"],
        fatigue_level=analysis["fatigue_level"],
        days_since_launch=analysis["days_since_launch"],
        total_impressions=analysis["total_impressions"],
        frequency=analysis.get("frequency"),
        ctr_trend=analysis.get("ctr_trend"),
        conversion_trend=analysis.get("conversion_trend"),
        recommendation=analysis["recommendation"],
        recommended_refresh_date=analysis.get("recommended_refresh_date"),
    )


# =============================================================================
# Audience Overlap Endpoint
# =============================================================================


@router.get(
    "/audiences/overlap",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get audience overlap detection",
)
async def get_audience_overlap(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Detect overlap between audiences for the company."""
    company_id = _check_tenant_access(current_user)

    overlaps = await AudienceAnalysisService.detect_audience_overlap(db, company_id)

    return {
        "total_overlaps": len(overlaps),
        "overlaps": overlaps,
    }


@router.get(
    "/audiences/lookalikes",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get lookalike audience suggestions",
)
async def get_lookalike_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get lookalike audience suggestions based on high-performing audiences."""
    company_id = _check_tenant_access(current_user)

    suggestions = await AudienceAnalysisService.suggest_lookalike_audiences(
        db, company_id
    )

    return {
        "total_suggestions": len(suggestions),
        "suggestions": suggestions,
    }


# =============================================================================
# Sync Endpoints
# =============================================================================


@router.post(
    "/sync/{platform}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Sync data from ad platform",
)
async def sync_platform_data(
    platform: AdPlatform,
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Sync data from a connected ad platform.

    Pulls campaigns, metrics, and optionally audiences from the platform API.
    """
    company_id = _check_tenant_access(current_user)

    # Find the platform account
    if request.platform_account_id:
        query = select(AdPlatformAccount).where(
            and_(
                AdPlatformAccount.id == request.platform_account_id,
                AdPlatformAccount.company_id == company_id,
                AdPlatformAccount.platform == platform,
            )
        )
    else:
        query = select(AdPlatformAccount).where(
            and_(
                AdPlatformAccount.company_id == company_id,
                AdPlatformAccount.platform == platform,
            )
        )

    result = await db.execute(query)
    platform_account = result.scalar_one_or_none()

    if not platform_account:
        raise NotFoundError(
            detail=f"No connected {platform.value} account found for this company"
        )

    # Update status to syncing
    platform_account.status = PlatformStatus.SYNCING
    await db.commit()

    # Perform sync
    sync_result = await DataSyncService.sync_platform(
        db=db,
        platform_account=platform_account,
        date_range_days=request.date_range_days,
        sync_campaigns=request.sync_campaigns,
        sync_metrics=request.sync_metrics,
        sync_audiences=request.sync_audiences,
    )

    return sync_result


# All imports are at the top of the file
