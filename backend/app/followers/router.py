"""FastAPI router for the Follower Intelligence module.

All endpoints are prefixed with /api/v2/followers by main.py registration.
Provides follower sync, bot detection, engagement quality, audience analysis,
health scoring, and AI recommendation endpoints.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db

from .schemas import (
    AIAudienceRecommendationListResponse,
    AIAudienceRecommendationResponse,
    AudienceDemographicsCreate,
    AudienceDemographicsListResponse,
    AudienceDemographicsResponse,
    BotDetectionResult,
    BotPatternCreate,
    BotPatternListResponse,
    BotPatternResponse,
    EngagementEventCreate,
    EngagementEventListResponse,
    EngagementEventResponse,
    EngagementQualityCreate,
    EngagementQualityListResponse,
    EngagementQualityResponse,
    FollowerAlert,
    FollowerAnalysisRequest,
    FollowerAnalysisResponse,
    FollowerDashboard,
    FollowerDeltaEventListResponse,
    FollowerDeltaSummaryResponse,
    FollowerGrowthTrend,
    FollowerHealthCreate,
    FollowerHealthListResponse,
    FollowerHealthResponse,
    FollowerInsightCreate,
    FollowerInsightListResponse,
    FollowerInsightResponse,
    FollowerSnapshotCreate,
    FollowerSnapshotListResponse,
    FollowerSnapshotResponse,
    FollowerSyncSummary,
    FollowerValueScoreListResponse,
    FollowerValueSummaryResponse,
    GenerateReengagementRequest,
    NewEngagementSummaryResponse,
    OutreachApprovalListResponse,
    OutreachApprovalResponse,
    QualityMetrics,
    ReengagementRecommendationListResponse,
    ReengagementRecommendationResponse,
    ReviewApprovalRequest,
    SuspiciousActivityCreate,
    SuspiciousActivityListResponse,
    SuspiciousActivityResponse,
)
from .service import (
    AIAudienceService,
    AudienceAnalysisService,
    BotDetectionService,
    EngagementEventService,
    EngagementQualityService,
    FollowerDeltaService,
    FollowerHealthService,
    FollowerSyncService,
    FollowerValueService,
    ReengagementService,
    SuspiciousActivityService,
)

router = APIRouter(tags=["followers"])


# =============================================================================
# Follower Snapshot Endpoints
# =============================================================================


@router.post(
    "/snapshots",
    response_model=FollowerSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a follower snapshot",
    description="Record a new follower count snapshot for trend tracking.",
)
async def create_snapshot(
    data: FollowerSnapshotCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new follower snapshot."""
    service = FollowerSyncService(db)
    snapshot = await service.create_snapshot(
        company_id=user.company_id,
        data=data,
        branch_id=user.branch_id,
    )
    return snapshot


@router.get(
    "/snapshots",
    response_model=FollowerSnapshotListResponse,
    summary="List follower snapshots",
    description="List follower snapshots with optional filters.",
)
async def list_snapshots(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List follower snapshots."""
    service = FollowerSyncService(db)
    result = await service.list_snapshots(
        company_id=user.company_id,
        account_id=account_id,
        platform=platform,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=FollowerSnapshotResponse,
    summary="Get a snapshot by ID",
)
async def get_snapshot(
    snapshot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a follower snapshot by ID."""
    # Implementation uses the service to fetch by ID
    from sqlalchemy import select
    from .models import FollowerSnapshot

    result = await db.execute(
        select(FollowerSnapshot).where(
            FollowerSnapshot.id == snapshot_id,
            FollowerSnapshot.company_id == user.company_id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        from app.exceptions import NotFoundError
        raise NotFoundError("Snapshot not found")
    return snapshot


@router.post(
    "/sync",
    response_model=FollowerSyncSummary,
    summary="Sync follower count",
    description="Sync current follower count and create a snapshot with change tracking.",
)
async def sync_followers(
    account_id: int = Query(..., description="Social account ID"),
    external_account_id: str = Query(..., description="Platform account ID"),
    platform: str = Query(..., description="Social platform"),
    current_followers: int = Query(..., ge=0, description="Current follower count"),
    current_following: int = Query(0, ge=0, description="Current following count"),
    current_posts: int = Query(0, ge=0, description="Current post count"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sync current follower count and return change summary."""
    service = FollowerSyncService(db)
    summary = await service.sync_follower_count(
        company_id=user.company_id,
        account_id=account_id,
        external_account_id=external_account_id,
        platform=platform,
        current_followers=current_followers,
        current_following=current_following,
        current_posts=current_posts,
        branch_id=user.branch_id,
    )
    return summary


@router.get(
    "/growth-trend/{account_id}",
    response_model=List[dict[str, object]],
    summary="Get follower growth trend",
    description="Get daily follower growth trend for an account.",
)
async def get_growth_trend(
    account_id: int,
    days: int = Query(30, ge=7, le=365, description="Days to analyze"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get follower growth trend."""
    service = FollowerSyncService(db)
    trend = await service.calculate_growth_trend(
        account_id=account_id,
        company_id=user.company_id,
        days=days,
    )
    return trend


# =============================================================================
# Bot Detection Endpoints
# =============================================================================


@router.post(
    "/bot-detection/detect",
    response_model=BotPatternResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Detect bot on single account",
    description="Run bot detection on a single follower account.",
)
async def detect_bot_single(
    account_id: int = Query(..., description="Our social account ID"),
    platform: str = Query(..., description="Social platform"),
    username: str = Query(..., description="Suspected account username"),
    detected_account_id: str = Query(..., description="Suspected account platform ID"),
    post_count: int = Query(0, ge=0, description="Post count"),
    follower_count: int = Query(0, ge=0, description="Follower count"),
    following_count: int = Query(0, ge=0, description="Following count"),
    has_profile_pic: bool = Query(True, description="Has profile picture"),
    bio_text: Optional[str] = Query(None, description="Bio text"),
    is_private: bool = Query(False, description="Is private account"),
    is_verified: bool = Query(False, description="Is verified"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run bot detection on a single account."""
    service = BotDetectionService(db)
    result = await service.detect_bot(
        company_id=user.company_id,
        account_id=account_id,
        platform=platform,
        username=username,
        detected_account_id=detected_account_id,
        post_count=post_count,
        follower_count=follower_count,
        following_count=following_count,
        has_profile_pic=has_profile_pic,
        bio_text=bio_text,
        is_private=is_private,
        is_verified=is_verified,
        branch_id=user.branch_id,
    )
    return result


@router.post(
    "/bot-detection/batch",
    response_model=BotDetectionResult,
    summary="Batch bot detection",
    description="Run bot detection on a batch of follower profiles.",
)
async def detect_bot_batch(
    data: dict[str, object],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run batch bot detection.

    Request body:
    {
        "account_id": 1,
        "platform": "instagram",
        "follower_profiles": [
            {"username": "...", "post_count": 0, ...}
        ]
    }
    """
    service = BotDetectionService(db)
    result = await service.batch_detect(
        company_id=user.company_id,
        account_id=data["account_id"],
        platform=data["platform"],
        follower_profiles=data.get("follower_profiles", []),
        branch_id=user.branch_id,
    )
    return result


@router.get(
    "/bot-detection/patterns",
    response_model=BotPatternListResponse,
    summary="List bot patterns",
    description="List detected bot/suspicious account patterns.",
)
async def list_bot_patterns(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List bot detection patterns."""
    service = BotDetectionService(db)
    result = await service.list_bot_patterns(
        company_id=user.company_id,
        account_id=account_id,
        risk_level=risk_level,
        page=page,
        page_size=page_size,
    )
    return result


# =============================================================================
# Suspicious Activity Endpoints
# =============================================================================


@router.get(
    "/suspicious-activity",
    response_model=SuspiciousActivityListResponse,
    summary="List suspicious activities",
    description="List detected suspicious follower activities and anomalies.",
)
async def list_suspicious_activities(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List suspicious activities."""
    service = SuspiciousActivityService(db)
    result = await service.list_activities(
        company_id=user.company_id,
        account_id=account_id,
        alert_type=alert_type,
        resolved=resolved,
        page=page,
        page_size=page_size,
    )
    return result


@router.post(
    "/suspicious-activity/{activity_id}/resolve",
    response_model=SuspiciousActivityResponse,
    summary="Resolve suspicious activity",
    description="Mark a suspicious activity alert as resolved.",
)
async def resolve_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a suspicious activity as resolved."""
    service = SuspiciousActivityService(db)
    activity = await service.resolve_activity(activity_id, user.company_id)
    return activity


# =============================================================================
# Audience Demographics Endpoints
# =============================================================================


@router.post(
    "/demographics/analyze",
    response_model=AudienceDemographicsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze audience demographics",
    description="Analyze audience demographics from follower profiles.",
)
async def analyze_demographics(
    data: dict[str, object],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Analyze audience demographics.

    Request body:
    {
        "account_id": 1,
        "platform": "instagram",
        "follower_profiles": [
            {"username": "...", "bio_text": "...", "location": "..."}
        ]
    }
    """
    service = AudienceAnalysisService(db)
    result = await service.analyze_demographics(
        company_id=user.company_id,
        account_id=data["account_id"],
        platform=data["platform"],
        follower_profiles=data.get("follower_profiles", []),
        branch_id=user.branch_id,
    )
    return result


@router.get(
    "/demographics",
    response_model=AudienceDemographicsListResponse,
    summary="List audience demographics",
    description="List audience demographic records.",
)
async def list_demographics(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List audience demographics."""
    from sqlalchemy import select, func, desc
    from .models import AudienceDemographics

    query = select(AudienceDemographics).where(
        AudienceDemographics.company_id == user.company_id
    )

    if account_id:
        query = query.where(AudienceDemographics.account_id == account_id)
    if platform:
        query = query.where(AudienceDemographics.platform == platform)

    count_result = await db.execute(
        select(func.count())
        .select_from(AudienceDemographics)
        .where(AudienceDemographics.company_id == user.company_id)
    )
    total = count_result.scalar() or 0

    query = query.order_by(desc(AudienceDemographics.analysis_date))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = list(result.scalars().all())

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get(
    "/demographics/{account_id}/latest",
    response_model=Optional[AudienceDemographicsResponse],
    summary="Get latest demographics",
    description="Get the most recent audience demographics for an account.",
)
async def get_latest_demographics(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get latest audience demographics."""
    service = AudienceAnalysisService(db)
    demo = await service.get_latest_demographics(account_id, user.company_id)
    return demo


# =============================================================================
# Engagement Quality Endpoints
# =============================================================================


@router.post(
    "/engagement-quality",
    response_model=EngagementQualityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create engagement quality record",
    description="Record engagement quality metrics.",
)
async def create_engagement_quality(
    data: EngagementQualityCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create engagement quality record."""
    service = EngagementQualityService(db)
    record = await service.create_quality_record(
        company_id=user.company_id,
        account_id=data.account_id,
        platform=data.platform,
        data=data,
        branch_id=user.branch_id,
    )
    return record


@router.get(
    "/engagement-quality",
    response_model=EngagementQualityListResponse,
    summary="List engagement quality records",
    description="List engagement quality records with optional filters.",
)
async def list_engagement_quality(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List engagement quality records."""
    service = EngagementQualityService(db)
    result = await service.list_quality_records(
        company_id=user.company_id,
        account_id=account_id,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/engagement-quality/{account_id}/summary",
    response_model=QualityMetrics,
    summary="Get engagement quality summary",
    description="Get aggregated engagement quality metrics for an account.",
)
async def get_engagement_summary(
    account_id: int,
    days: int = Query(30, ge=7, le=365, description="Days to analyze"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get engagement quality summary."""
    service = EngagementQualityService(db)
    summary = await service.get_quality_summary(account_id, user.company_id, days=days)
    return summary


# =============================================================================
# Follower Health Score Endpoints
# =============================================================================


@router.post(
    "/health-score/calculate",
    response_model=FollowerHealthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate health score",
    description="Calculate composite follower health score for an account.",
)
async def calculate_health_score(
    data: dict[str, object],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Calculate follower health score.

    Request body:
    {
        "account_id": 1,
        "platform": "instagram",
        "current_followers": 5000,
        "engagement_rate": 3.5,
        "bot_pct": 5.2,
        "inactive_pct": 25.0,
        "growth_rate": 2.1
    }
    """
    service = FollowerHealthService(db)
    health = await service.calculate_health_score(
        company_id=user.company_id,
        account_id=data["account_id"],
        platform=data["platform"],
        current_followers=data.get("current_followers", 0),
        engagement_rate=data.get("engagement_rate", 0.0),
        bot_pct=data.get("bot_pct", 0.0),
        inactive_pct=data.get("inactive_pct", 0.0),
        growth_rate=data.get("growth_rate", 0.0),
        branch_id=user.branch_id,
    )
    return health


@router.get(
    "/health-score",
    response_model=FollowerHealthListResponse,
    summary="List health scores",
    description="List follower health scores with optional filters.",
)
async def list_health_scores(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List health scores."""
    service = FollowerHealthService(db)
    result = await service.list_health_scores(
        company_id=user.company_id,
        account_id=account_id,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/health-score/{account_id}/latest",
    response_model=Optional[FollowerHealthResponse],
    summary="Get latest health score",
    description="Get the most recent health score for an account.",
)
async def get_latest_health_score(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get latest health score."""
    service = FollowerHealthService(db)
    health = await service.get_latest_health_score(account_id, user.company_id)
    return health


# =============================================================================
# AI Audience Recommendation Endpoints
# =============================================================================


@router.post(
    "/ai-recommendations/generate",
    response_model=List[AIAudienceRecommendationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI recommendations",
    description="Generate AI-powered audience recommendations for an account.",
)
async def generate_ai_recommendations(
    data: dict[str, object],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate AI audience recommendations.

    Request body:
    {
        "account_id": 1,
        "platform": "instagram",
        "engagement_rate": 3.5,
        "follower_count": 5000,
        "top_interests": ["food", "fashion", "travel"],
        "demographics_id": 5  # Optional
    }
    """
    service = AIAudienceService(db)

    # Optionally load demographics
    demographics = None
    demo_id = data.get("demographics_id")
    if demo_id:
        aud_service = AudienceAnalysisService(db)
        demographics = await aud_service.get_latest_demographics(
            data["account_id"], user.company_id
        )

    recommendations = await service.generate_recommendations(
        company_id=user.company_id,
        account_id=data["account_id"],
        platform=data["platform"],
        engagement_rate=data.get("engagement_rate", 0.0),
        follower_count=data.get("follower_count", 0),
        top_interests=data.get("top_interests", []),
        demographics=demographics,
        branch_id=user.branch_id,
    )
    return recommendations


@router.get(
    "/ai-recommendations",
    response_model=AIAudienceRecommendationListResponse,
    summary="List AI recommendations",
    description="List AI audience recommendations with optional filters.",
)
async def list_ai_recommendations(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    rec_type: Optional[str] = Query(None, description="Filter by type"),
    implemented: Optional[bool] = Query(None, description="Filter by implementation"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List AI recommendations."""
    service = AIAudienceService(db)
    result = await service.list_recommendations(
        company_id=user.company_id,
        account_id=account_id,
        rec_type=rec_type,
        implemented=implemented,
        page=page,
        page_size=page_size,
    )
    return result


@router.post(
    "/ai-recommendations/{rec_id}/implement",
    response_model=AIAudienceRecommendationResponse,
    summary="Mark recommendation as implemented",
    description="Mark an AI recommendation as implemented with result notes.",
)
async def implement_recommendation(
    rec_id: int,
    result_notes: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark an AI recommendation as implemented."""
    service = AIAudienceService(db)
    rec = await service.mark_implemented(rec_id, user.company_id, result_notes)
    return rec


# =============================================================================
# Dashboard Endpoints
# =============================================================================


@router.get(
    "/dashboard/{account_id}",
    response_model=FollowerDashboard,
    summary="Follower intelligence dashboard",
    description="Get comprehensive follower intelligence dashboard for an account.",
)
async def get_dashboard(
    account_id: int,
    platform: str = Query(..., description="Social platform"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get comprehensive follower intelligence dashboard."""
    import time

    start_time = time.monotonic()

    sync_service = FollowerSyncService(db)
    health_service = FollowerHealthService(db)
    bot_service = BotDetectionService(db)
    engagement_service = EngagementQualityService(db)
    aud_service = AudienceAnalysisService(db)
    ai_service = AIAudienceService(db)
    activity_service = SuspiciousActivityService(db)

    # Get latest snapshot
    latest_snapshot = await sync_service.get_latest_snapshot(account_id, user.company_id)
    current_followers = latest_snapshot.follower_count if latest_snapshot else 0

    # Get 7d and 30d snapshots for change calculation
    end_date = datetime.now(timezone.utc)
    snapshots_7d = await sync_service.get_snapshots_in_range(
        account_id, user.company_id, end_date - timedelta(days=7), end_date
    )
    snapshots_30d = await sync_service.get_snapshots_in_range(
        account_id, user.company_id, end_date - timedelta(days=30), end_date
    )

    followers_7d_change = 0
    if len(snapshots_7d) >= 2:
        followers_7d_change = snapshots_7d[-1].follower_count - snapshots_7d[0].follower_count

    followers_30d_change = 0
    if len(snapshots_30d) >= 2:
        followers_30d_change = snapshots_30d[-1].follower_count - snapshots_30d[0].follower_count

    # Growth rate
    growth_rate = 0.0
    if len(snapshots_30d) >= 2 and snapshots_30d[0].follower_count > 0:
        growth_rate = (
            (snapshots_30d[-1].follower_count - snapshots_30d[0].follower_count)
            / snapshots_30d[0].follower_count
            * 100
        )

    # Health score
    health = await health_service.get_latest_health_score(account_id, user.company_id)
    health_score = health.overall_score if health else 50
    health_status = health.status.value if health else "moderate"

    # Bot detection summary
    bot_result = await bot_service.list_bot_patterns(
        company_id=user.company_id, account_id=account_id, page_size=1
    )
    bot_summary = bot_result.get("summary", {})
    bot_pct = bot_summary.get("average_bot_score", 0.0) * 100

    # Engagement quality
    quality = await engagement_service.get_quality_summary(account_id, user.company_id)

    # Inactive percentage (from health score if available)
    inactive_pct = float(health.inactive_pct) if health else 0.0

    # Top bot signals
    top_signals = bot_summary.get("risk_distribution", {})

    # Recent alerts
    activity_result = await activity_service.list_activities(
        company_id=user.company_id, account_id=account_id, resolved=False, page_size=5
    )
    alerts = activity_result.get("active_alerts", [])

    # Demographics
    demographics = await aud_service.get_latest_demographics(account_id, user.company_id)

    # AI recommendations
    ai_result = await ai_service.list_recommendations(
        company_id=user.company_id, account_id=account_id, page_size=5
    )
    ai_recs = ai_result.get("items", [])

    processing_time = time.monotonic() - start_time

    return {
        "account_id": account_id,
        "platform": platform,
        "current_followers": current_followers,
        "followers_7d_change": followers_7d_change,
        "followers_30d_change": followers_30d_change,
        "growth_rate": round(growth_rate, 4),
        "health_score": health_score,
        "health_status": health_status,
        "bot_percentage": round(bot_pct, 2),
        "inactive_percentage": round(inactive_pct, 2),
        "engagement_rate": round(quality.average_engagement_rate, 4) if quality else 0.0,
        "engagement_tier": quality.tier if quality else "average",
        "top_bot_signals": list(top_signals.keys()),
        "recent_alerts": alerts,
        "demographics_summary": demographics,
        "ai_recommendations": ai_recs,
    }


# =============================================================================
# Comprehensive Analysis Endpoint
# =============================================================================


@router.post(
    "/analyze",
    response_model=FollowerAnalysisResponse,
    summary="Run comprehensive follower analysis",
    description="Run a comprehensive follower analysis combining all modules.",
)
async def run_comprehensive_analysis(
    data: FollowerAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run comprehensive follower analysis.

    Performs bot detection, demographics analysis, engagement quality scoring,
    health score calculation, and AI recommendation generation.
    """
    import time

    start_time = time.monotonic()

    sync_service = FollowerSyncService(db)
    bot_service = BotDetectionService(db)
    engagement_service = EngagementQualityService(db)
    aud_service = AudienceAnalysisService(db)
    health_service = FollowerHealthService(db)
    ai_service = AIAudienceService(db)
    activity_service = SuspiciousActivityService(db)

    response: dict[str, object] = {
        "account_id": data.account_id,
        "platform": data.platform,
        "analysis_date": datetime.now(timezone.utc),
        "bot_detection": None,
        "demographics": None,
        "engagement_quality": None,
        "health_score": None,
        "suspicious_activities": [],
        "ai_recommendations": [],
        "processing_time_seconds": 0.0,
    }

    # Get snapshots for analysis
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=data.lookback_days)
    snapshots = await sync_service.get_snapshots_in_range(
        data.account_id, user.company_id, start_date, end_date
    )

    latest_snapshot = snapshots[-1] if snapshots else None
    current_followers = latest_snapshot.follower_count if latest_snapshot else 0

    # Bot detection
    if "bot_detection" in data.analysis_types and data.follower_profiles:
        bot_result = await bot_service.batch_detect(
            company_id=user.company_id,
            account_id=data.account_id,
            platform="instagram",  # Default, should come from request
            follower_profiles=data.follower_profiles,
            branch_id=user.branch_id,
        )
        response["bot_detection"] = bot_result

    # Demographics
    if "demographics" in data.analysis_types and data.follower_profiles:
        demographics = await aud_service.analyze_demographics(
            company_id=user.company_id,
            account_id=data.account_id,
            platform="instagram",
            follower_profiles=data.follower_profiles,
            branch_id=user.branch_id,
        )
        response["demographics"] = demographics

    # Engagement quality (requires post data)
    if "engagement_quality" in data.analysis_types:
        quality = await engagement_service.get_quality_summary(
            data.account_id, user.company_id, days=data.lookback_days
        )
        response["engagement_quality"] = quality

    # Health score
    if "health_score" in data.analysis_types:
        bot_pct = response["bot_detection"].bot_percentage if response["bot_detection"] else 0.0
        engagement_rate = response["engagement_quality"].average_engagement_rate if response["engagement_quality"] else 0.0

        health = await health_service.calculate_health_score(
            company_id=user.company_id,
            account_id=data.account_id,
            platform="instagram",
            current_followers=current_followers,
            engagement_rate=engagement_rate,
            bot_pct=bot_pct,
            inactive_pct=0.0,  # Would need actual data
            growth_rate=0.0,  # Would need historical data
            branch_id=user.branch_id,
        )
        response["health_score"] = health

    # AI recommendations
    if "ai_recommendations" in data.analysis_types:
        top_interests = []
        if response["demographics"]:
            top_interests = [i["name"] for i in response["demographics"].interests[:5]]

        engagement_rate = (
            response["engagement_quality"].average_engagement_rate
            if response["engagement_quality"]
            else 0.0
        )

        ai_recs = await ai_service.generate_recommendations(
            company_id=user.company_id,
            account_id=data.account_id,
            platform="instagram",
            engagement_rate=engagement_rate,
            follower_count=current_followers,
            top_interests=top_interests or ["general"],
            demographics=response["demographics"] if response["demographics"] else None,
            branch_id=user.branch_id,
        )
        response["ai_recommendations"] = ai_recs

    response["processing_time_seconds"] = round(time.monotonic() - start_time, 3)

    return response


# =============================================================================
# Follower Delta / Estimated Unfollow Endpoints (P1)
# =============================================================================


@router.get(
    "/new",
    response_model=FollowerDeltaEventListResponse,
    summary="Get new follower detection events",
    description="List follower delta events showing new follower acquisitions.",
)
async def get_new_followers(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get new follower delta events."""
    service = FollowerDeltaService(db)
    return await service.list_delta_events(
        company_id=user.company_id,
        account_id=account_id,
        event_type="new_follower",
        page=page,
        page_size=page_size,
    )


@router.get(
    "/lost-estimated",
    response_model=FollowerDeltaEventListResponse,
    summary="Get estimated unfollow events",
    description=(
        "List follower delta events showing estimated unfollows. "
        "These are estimates based on snapshot comparison, not definitive data. "
        "Confidence scores are provided for each estimate."
    ),
)
async def get_estimated_unfollows(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get estimated unfollow events with confidence scores."""
    service = FollowerDeltaService(db)
    return await service.list_delta_events(
        company_id=user.company_id,
        account_id=account_id,
        event_type="estimated_unfollow",
        page=page,
        page_size=page_size,
    )


@router.get(
    "/delta",
    response_model=FollowerDeltaSummaryResponse,
    summary="Get follower delta summary",
    description=(
        "Get a summary of follower changes over a period. "
        "Includes estimated new followers, estimated unfollows, and net change. "
        "All counts are estimates with confidence scores."
    ),
)
async def get_delta_summary(
    account_id: int = Query(..., description="Social account ID"),
    days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get follower delta summary with estimated changes."""
    service = FollowerDeltaService(db)
    return await service.get_delta_summary(
        company_id=user.company_id,
        account_id=account_id,
        days=days,
    )


@router.get(
    "/inactive",
    response_model=FollowerValueScoreListResponse,
    summary="Get inactive followers",
    description="List followers classified as inactive or ghost (no engagement > 30 days).",
)
async def get_inactive_followers(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get inactive/ghost followers."""
    service = FollowerValueService(db)
    return await service.list_value_scores(
        company_id=user.company_id,
        account_id=account_id,
        is_inactive=True,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# New Engagement Detection Endpoints (P2)
# =============================================================================


@router.get(
    "/engagement/new",
    response_model=EngagementEventListResponse,
    summary="Get new engagement events",
    description=(
        "List new engagement events: DMs, comments, mentions, story interactions, "
        "reel views, WhatsApp/Telegram messages, and campaign clicks."
    ),
)
async def get_new_engagements(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    event_type: Optional[str] = Query(None, description="Filter by event type (new_dm, new_comment, new_mention, etc.)"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    is_new_lead: Optional[bool] = Query(None, description="Filter by lead status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get new engagement events across all platforms."""
    service = EngagementEventService(db)
    return await service.list_events(
        company_id=user.company_id,
        account_id=account_id,
        event_type=event_type,
        platform=platform,
        is_new_lead=is_new_lead,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/engagement/record",
    response_model=EngagementEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an engagement event",
    description="Record a new engagement event from a follower.",
)
async def record_engagement(
    data: EngagementEventCreate,
    account_id: int = Query(..., description="Social account ID"),
    platform: str = Query(..., description="Platform (instagram, facebook, tiktok, whatsapp, telegram)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a new engagement event."""
    service = EngagementEventService(db)
    return await service.record_event(
        company_id=user.company_id,
        account_id=account_id,
        platform=platform,
        event_type=data.event_type,
        follower_account_id=data.follower_account_id,
        follower_username=data.follower_username,
        post_id=data.post_id,
        message_preview=data.message_preview,
        sentiment=data.sentiment,
        is_new_lead=data.is_new_lead,
        lead_score=data.lead_score,
        campaign_id=data.campaign_id,
        event_date=data.event_date,
        raw_data=data.raw_data,
        branch_id=user.branch_id,
    )


# =============================================================================
# Re-engagement Endpoints (P3)
# =============================================================================


@router.get(
    "/reengagement/recommendations",
    response_model=ReengagementRecommendationListResponse,
    summary="Get re-engagement recommendations",
    description=(
        "List AI-generated re-engagement recommendations. "
        "Includes welcome messages, campaign suggestions, win-back offers. "
        "All messages require approval before sending."
    ),
)
async def get_reengagement_recommendations(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected, sent)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get re-engagement recommendations."""
    service = ReengagementService(db)
    return await service.list_recommendations(
        company_id=user.company_id,
        account_id=account_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/reengagement/generate-message",
    response_model=ReengagementRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate re-engagement message",
    description=(
        "Generate an AI-suggested re-engagement message. "
        "The message is a suggestion only - approval is required before sending. "
        "Auto-send is disabled by default."
    ),
)
async def generate_reengagement_message(
    data: GenerateReengagementRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a re-engagement message suggestion."""
    service = ReengagementService(db)
    return await service.generate_recommendation(
        company_id=user.company_id,
        account_id=data.account_id,
        platform=data.platform,
        reengagement_type=data.reengagement_type,
        target_follower_id=data.target_follower_id,
        target_username=data.target_username,
        target_segment=data.target_segment,
        interests=data.interests,
        confidence=data.confidence,
        branch_id=user.branch_id,
    )


@router.post(
    "/reengagement/request-approval",
    response_model=OutreachApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request approval for a message",
    description="Create an approval request for a re-engagement message. Approval is mandatory.",
)
async def request_approval(
    reengagement_id: int = Query(..., description="Re-engagement recommendation ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request approval for a re-engagement message."""
    service = ReengagementService(db)
    return await service.request_approval(
        rec_id=reengagement_id,
        company_id=user.company_id,
        requested_by=user.id,
    )


@router.post(
    "/reengagement/review-approval/{approval_id}",
    response_model=OutreachApprovalResponse,
    summary="Review an approval request",
    description="Approve or reject a pending outreach approval request.",
)
async def review_approval(
    approval_id: int,
    data: ReviewApprovalRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Review an approval request (approve or reject)."""
    service = ReengagementService(db)
    return await service.review_approval(
        approval_id=approval_id,
        company_id=user.company_id,
        reviewed_by=user.id,
        approved=data.approved,
        notes=data.notes,
    )


@router.post(
    "/reengagement/send-approved",
    response_model=OutreachApprovalResponse,
    summary="Send an approved message",
    description=(
        "Mark an approved message as sent. "
        "Note: This records the send intent. Actual delivery is handled by platform-specific services. "
        "Rate limits are enforced automatically."
    ),
)
async def send_approved_message(
    approval_id: int = Query(..., description="Approval request ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send an approved message (records send intent)."""
    service = ReengagementService(db)
    return await service.send_approved_message(
        approval_id=approval_id,
        company_id=user.company_id,
        sent_by=user.id,
    )


# =============================================================================
# Approval Queue Endpoints
# =============================================================================


@router.get(
    "/reengagement/approvals",
    response_model=OutreachApprovalListResponse,
    summary="Get outreach approval queue",
    description="List outreach approval requests with optional status filter.",
)
async def get_approval_queue(
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected, sent, failed)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get outreach approval queue."""
    service = ReengagementService(db)
    return await service.list_approvals(
        company_id=user.company_id,
        status=status,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Follower Value Score Endpoints
# =============================================================================


@router.get(
    "/value-scores",
    response_model=FollowerValueScoreListResponse,
    summary="Get follower value scores",
    description="List follower value scores (high/medium/low value, ghost, inactive).",
)
async def get_value_scores(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    tier: Optional[str] = Query(None, description="Filter by tier (high_value, medium_value, low_value, ghost, new)"),
    is_inactive: Optional[bool] = Query(None, description="Filter by inactive status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get follower value scores."""
    service = FollowerValueService(db)
    return await service.list_value_scores(
        company_id=user.company_id,
        account_id=account_id,
        tier=tier,
        is_inactive=is_inactive,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Dashboard Summary Endpoint
# =============================================================================


@router.get(
    "/dashboard",
    response_model=dict[str, object],
    summary="Follower intelligence dashboard",
    description=(
        "Combined dashboard with new followers, estimated unfollows, "
        "inactive followers, high-value followers, engagement events, "
        "re-engagement opportunities, and pending approvals."
    ),
)
async def get_dashboard(
    account_id: int = Query(..., description="Social account ID"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get combined follower intelligence dashboard."""
    delta_service = FollowerDeltaService(db)
    engagement_service = EngagementEventService(db)
    value_service = FollowerValueService(db)
    reengagement_service = ReengagementService(db)

    # Get delta summary
    delta = await delta_service.get_delta_summary(
        company_id=user.company_id,
        account_id=account_id,
        days=30,
    )

    # Get engagement summary
    engagements = await engagement_service.get_new_engagement_summary(
        company_id=user.company_id,
        account_id=account_id,
        days=7,
    )

    # Get value summary
    values = await value_service.get_value_summary(
        company_id=user.company_id,
        account_id=account_id,
    )

    # Get pending approvals
    approvals = await reengagement_service.list_approvals(
        company_id=user.company_id,
        status="pending",
        page=1,
        page_size=5,
    )

    # Get pending recommendations
    recs = await reengagement_service.list_recommendations(
        company_id=user.company_id,
        account_id=account_id,
        status="pending",
        page=1,
        page_size=5,
    )

    return {
        "account_id": account_id,
        "platform": platform,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "follower_delta": delta,
        "engagements": engagements,
        "follower_values": values,
        "pending_approvals": approvals,
        "pending_recommendations": recs,
        "disclaimer": {
            "estimated_unfollows": "All unfollow counts are estimates based on snapshot comparison, not definitive data.",
            "confidence_scores": "Confidence scores indicate estimation reliability. Higher = more reliable.",
            "auto_send": "Auto-send is disabled by default. All outbound messages require approval.",
        },
    }
