"""Comprehensive tests for the Follower Intelligence module.

Covers bot detection, engagement quality, health scoring,
audience analysis, and AI recommendations.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.followers.constants import (
    BOT_THRESHOLDS,
    ENGAGEMENT_THRESHOLDS,
    HEALTH_SCORE_WEIGHTS,
    BotRiskLevel,
    EngagementTier,
    FollowerAlertType,
    FollowerHealthStatus,
    GenderEstimate,
    get_bot_risk_level,
    get_engagement_tier,
    get_health_status,
)
from app.followers.models import (
    AIAudienceRecommendation,
    AudienceDemographics,
    BotPattern,
    EngagementQuality,
    FollowerHealthScore,
    FollowerSnapshot,
    SuspiciousActivity,
)
from app.followers.service import (
    AIAudienceService,
    AudienceAnalysisService,
    BotDetectionService,
    EngagementQualityService,
    FollowerHealthService,
    FollowerSyncService,
    SuspiciousActivityService,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_follower_profiles() -> List[Dict[str, Any]]:
    """Sample follower profiles for testing."""
    return [
        {
            "username": "johndoe",
            "account_id": "12345",
            "post_count": 150,
            "follower_count": 500,
            "following_count": 200,
            "has_profile_pic": True,
            "bio_text": "Photography enthusiast | Travel lover",
            "is_private": False,
            "is_verified": False,
            "account_age_days": 730,
            "last_post_days": 5,
            "location": "New York",
            "language": "en",
            "content_keywords": ["photo", "travel"],
        },
        {
            "username": "user_12345678",
            "account_id": "67890",
            "post_count": 0,
            "follower_count": 10,
            "following_count": 1500,
            "has_profile_pic": False,
            "bio_text": None,
            "is_private": False,
            "is_verified": False,
            "account_age_days": 3,
            "last_post_days": None,
            "location": None,
            "language": None,
            "content_keywords": [],
        },
        {
            "username": "sarah_smith",
            "account_id": "11111",
            "post_count": 89,
            "follower_count": 1200,
            "following_count": 400,
            "has_profile_pic": True,
            "bio_text": "Food blogger | Recipe creator | Mom",
            "is_private": False,
            "is_verified": False,
            "account_age_days": 1095,
            "last_post_days": 2,
            "location": "London",
            "language": "en",
            "content_keywords": ["food", "recipe", "cooking"],
        },
        {
            "username": "bot_9876543210",
            "account_id": "99999",
            "post_count": 0,
            "follower_count": 0,
            "following_count": 5000,
            "has_profile_pic": False,
            "bio_text": None,
            "is_private": False,
            "is_verified": False,
            "account_age_days": 1,
            "last_post_days": None,
            "has_default_avatar": True,
        },
    ]


@pytest.fixture
def sample_snapshots() -> List[Dict[str, Any]]:
    """Sample follower snapshots for testing."""
    base_date = datetime.now(timezone.utc) - timedelta(days=30)
    snapshots = []
    for i in range(30):
        # Simulate some growth with a spike on day 20
        if i < 20:
            followers = 1000 + i * 10
        elif i == 20:
            followers = 1000 + i * 10 + 500  # Sudden spike
        else:
            followers = 1000 + i * 10 + 500
        snapshots.append({
            "follower_count": followers,
            "following_count": 500,
            "post_count": 50,
            "snapshot_date": base_date + timedelta(days=i),
        })
    return snapshots


# =============================================================================
# Unit Tests - Constants & Utility Functions
# =============================================================================


def test_get_bot_risk_level():
    """Test bot risk level classification."""
    assert get_bot_risk_level(0.85) == BotRiskLevel.CRITICAL
    assert get_bot_risk_level(0.65) == BotRiskLevel.HIGH
    assert get_bot_risk_level(0.45) == BotRiskLevel.MEDIUM
    assert get_bot_risk_level(0.20) == BotRiskLevel.LOW
    assert get_bot_risk_level(0.0) == BotRiskLevel.LOW
    assert get_bot_risk_level(1.0) == BotRiskLevel.CRITICAL


def test_get_engagement_tier():
    """Test engagement tier classification."""
    assert get_engagement_tier(8.0) == EngagementTier.ELITE
    assert get_engagement_tier(4.0) == EngagementTier.HIGH
    assert get_engagement_tier(2.0) == EngagementTier.AVERAGE
    assert get_engagement_tier(0.8) == EngagementTier.LOW
    assert get_engagement_tier(0.3) == EngagementTier.VERY_LOW


def test_get_health_status():
    """Test health status classification."""
    assert get_health_status(90) == FollowerHealthStatus.EXCELLENT
    assert get_health_status(75) == FollowerHealthStatus.GOOD
    assert get_health_status(60) == FollowerHealthStatus.MODERATE
    assert get_health_status(40) == FollowerHealthStatus.POOR
    assert get_health_status(15) == FollowerHealthStatus.CRITICAL
    assert get_health_status(0) == FollowerHealthStatus.CRITICAL
    assert get_health_status(100) == FollowerHealthStatus.EXCELLENT


def test_health_score_weights_sum():
    """Verify health score weights sum to 1.0."""
    total = sum(HEALTH_SCORE_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


# =============================================================================
# Unit Tests - Bot Detection Service
# =============================================================================


@pytest.mark.asyncio
async def test_bot_score_calculation(db_session: AsyncSession):
    """Test bot score calculation algorithm."""
    service = BotDetectionService(db_session)

    # Genuine account - should have low score
    score, signals = service._calculate_bot_score(
        post_count=150,
        follower_count=500,
        following_count=200,
        has_profile_pic=True,
        bio_text="Photography enthusiast",
        username="johndoe",
        is_private=False,
        is_verified=False,
        account_age_days=730,
        last_post_days=5,
    )
    assert score < 0.3, f"Genuine account scored too high: {score}"
    assert not signals["no_profile_pic"]
    assert not signals["zero_posts"]

    # Obvious bot - should have high score
    score, signals = service._calculate_bot_score(
        post_count=0,
        follower_count=0,
        following_count=5000,
        has_profile_pic=False,
        bio_text=None,
        username="bot_1234567890",
        is_private=False,
        is_verified=False,
        account_age_days=1,
        last_post_days=None,
        has_default_avatar=True,
    )
    assert score > 0.5, f"Bot account scored too low: {score}"
    assert signals["no_profile_pic"]
    assert signals["zero_posts"]
    assert signals["suspicious_username"]
    assert signals["default_avatar"]

    # Verified account - should have very low score
    score, signals = service._calculate_bot_score(
        post_count=100,
        follower_count=10000,
        following_count=100,
        has_profile_pic=True,
        bio_text="Official account",
        username="official",
        is_private=False,
        is_verified=True,
    )
    assert score < 0.1, f"Verified account scored too high: {score}"


@pytest.mark.asyncio
async def test_username_analysis(db_session: AsyncSession):
    """Test username pattern analysis."""
    service = BotDetectionService(db_session)

    # Normal username
    assert service._analyze_username("johndoe") < 0.1
    assert service._analyze_username("sarah_smith") < 0.15

    # Suspicious usernames
    assert service._analyze_username("user_12345678") > 0.1
    assert service._analyze_username("bot_9876543210") > 0.2
    assert service._analyze_username("abc1234567890xyz") > 0.1

    # Empty username
    assert service._analyze_username("") > 0.2


@pytest.mark.asyncio
async def test_bot_detection_single(db_session: AsyncSession):
    """Test single account bot detection."""
    service = BotDetectionService(db_session)

    result = await service.detect_bot(
        company_id=1,
        account_id=1,
        platform="instagram",
        username="suspicious_bot_12345",
        detected_account_id="bot_123",
        post_count=0,
        follower_count=0,
        following_count=3000,
        has_profile_pic=False,
        bio_text=None,
        is_private=False,
        is_verified=False,
        account_age_days=2,
        last_post_days=None,
        has_default_avatar=True,
    )

    assert result is not None
    assert float(result.bot_score) > 0.4
    assert result.risk_level in [BotRiskLevel.HIGH, BotRiskLevel.CRITICAL]
    assert result.signals["no_profile_pic"] is True
    assert result.signals["zero_posts"] is True
    assert result.signals["default_avatar"] is True


@pytest.mark.asyncio
async def test_batch_bot_detection(db_session: AsyncSession, sample_follower_profiles):
    """Test batch bot detection."""
    service = BotDetectionService(db_session)

    result = await service.batch_detect(
        company_id=1,
        account_id=1,
        platform="instagram",
        follower_profiles=sample_follower_profiles,
    )

    assert result.total_analyzed == 4
    assert result.bots_detected >= 1  # At least the obvious bot
    assert result.average_bot_score > 0
    assert len(result.risk_distribution) == 4
    assert len(result.top_signals) > 0


# =============================================================================
# Unit Tests - Follower Sync Service
# =============================================================================


@pytest.mark.asyncio
async def test_create_snapshot(db_session: AsyncSession):
    """Test creating a follower snapshot."""
    service = FollowerSyncService(db_session)

    from app.followers.schemas import FollowerSnapshotCreate

    data = FollowerSnapshotCreate(
        account_id=1,
        platform="instagram",
        external_account_id="test_account",
        follower_count=5000,
        following_count=500,
        post_count=100,
        snapshot_date=datetime.now(timezone.utc),
    )

    snapshot = await service.create_snapshot(company_id=1, data=data)

    assert snapshot.id is not None
    assert snapshot.follower_count == 5000
    assert snapshot.platform == "instagram"


@pytest.mark.asyncio
async def test_sync_follower_count(db_session: AsyncSession):
    """Test syncing follower count."""
    service = FollowerSyncService(db_session)

    summary = await service.sync_follower_count(
        company_id=1,
        account_id=1,
        external_account_id="test_account",
        platform="instagram",
        current_followers=5500,
        current_following=520,
        current_posts=110,
    )

    assert summary.new_follower_count == 5500
    assert summary.gained >= 0
    assert summary.snapshot_id > 0


@pytest.mark.asyncio
async def test_growth_trend(db_session: AsyncSession):
    """Test growth trend calculation."""
    service = FollowerSyncService(db_session)

    # Create multiple snapshots
    base_date = datetime.now(timezone.utc) - timedelta(days=10)
    for i in range(11):
        from app.followers.schemas import FollowerSnapshotCreate

        data = FollowerSnapshotCreate(
            account_id=1,
            platform="instagram",
            external_account_id="test_account",
            follower_count=1000 + i * 50,
            snapshot_date=base_date + timedelta(days=i),
        )
        await service.create_snapshot(company_id=1, data=data)

    trend = await service.calculate_growth_trend(1, 1, days=10)

    assert len(trend) > 0
    assert all("follower_count" in point for point in trend)
    assert all("daily_growth_rate" in point for point in trend)


# =============================================================================
# Unit Tests - Engagement Quality Service
# =============================================================================


@pytest.mark.asyncio
async def test_engagement_quality_calculation(db_session: AsyncSession):
    """Test engagement quality calculation."""
    service = EngagementQualityService(db_session)

    score, factors, tier = service.calculate_engagement_quality(
        likes=1000,
        comments=50,
        shares=20,
        reach=10000,
        impressions=15000,
        follower_count=5000,
        historical_rates=[2.5, 2.8, 3.0, 3.2, 3.5],
    )

    assert 0.0 <= score <= 1.0
    assert factors.engagement_rate_factor > 0
    assert tier in [
        EngagementTier.ELITE,
        EngagementTier.HIGH,
        EngagementTier.AVERAGE,
        EngagementTier.LOW,
        EngagementTier.VERY_LOW,
    ]


@pytest.mark.asyncio
async def test_engagement_tier_classification():
    """Test engagement tier boundary values."""
    assert get_engagement_tier(ENGAGEMENT_THRESHOLDS["elite_rate"]) == EngagementTier.ELITE
    assert get_engagement_tier(ENGAGEMENT_THRESHOLDS["high_rate"]) == EngagementTier.HIGH
    assert get_engagement_tier(ENGAGEMENT_THRESHOLDS["average_rate"]) == EngagementTier.AVERAGE
    assert get_engagement_tier(ENGAGEMENT_THRESHOLDS["low_rate"]) == EngagementTier.LOW
    assert get_engagement_tier(0.1) == EngagementTier.VERY_LOW


# =============================================================================
# Unit Tests - Audience Analysis Service
# =============================================================================


@pytest.mark.asyncio
async def test_gender_estimation(db_session: AsyncSession):
    """Test gender estimation from username."""
    service = AudienceAnalysisService(db_session)

    assert service.estimate_gender("johndoe", "Father of 2") == GenderEstimate.MALE
    assert service.estimate_gender("mary_smith", "Mom and wife") == GenderEstimate.FEMALE
    assert service.estimate_gender("unknown_user", None) == GenderEstimate.UNKNOWN
    assert service.estimate_gender("alex", "Developer") == GenderEstimate.UNKNOWN


@pytest.mark.asyncio
async def test_age_range_estimation(db_session: AsyncSession):
    """Test age range estimation."""
    service = AudienceAnalysisService(db_session)

    age = service.estimate_age_range("University student | 21", ["college", "study"])
    assert age in ["18-24", "25-34"]

    age = service.estimate_age_range("Retired veteran | Grandparent", ["family"])
    assert age in ["55-64", "65+"]


@pytest.mark.asyncio
async def test_demographics_analysis(db_session: AsyncSession, sample_follower_profiles):
    """Test audience demographics analysis."""
    service = AudienceAnalysisService(db_session)

    result = await service.analyze_demographics(
        company_id=1,
        account_id=1,
        platform="instagram",
        follower_profiles=sample_follower_profiles,
    )

    assert result is not None
    assert result.estimated_accounts == 4
    assert result.confidence_score > 0
    assert float(result.male_pct) + float(result.female_pct) + float(result.unknown_gender_pct) <= 100.1


# =============================================================================
# Unit Tests - Follower Health Service
# =============================================================================


@pytest.mark.asyncio
async def test_health_score_calculation(db_session: AsyncSession):
    """Test composite health score calculation."""
    service = FollowerHealthService(db_session)

    health = await service.calculate_health_score(
        company_id=1,
        account_id=1,
        platform="instagram",
        current_followers=5000,
        engagement_rate=4.5,
        bot_pct=5.0,
        inactive_pct=20.0,
        growth_rate=2.5,
    )

    assert 0 <= health.overall_score <= 100
    assert health.status in [
        FollowerHealthStatus.EXCELLENT,
        FollowerHealthStatus.GOOD,
        FollowerHealthStatus.MODERATE,
        FollowerHealthStatus.POOR,
        FollowerHealthStatus.CRITICAL,
    ]
    assert len(health.recommendations) > 0
    assert health.engagement_quality_score > 0
    assert health.bot_ratio_score > 0


@pytest.mark.asyncio
async def test_health_score_with_high_bot_pct(db_session: AsyncSession):
    """Test health score with high bot percentage."""
    service = FollowerHealthService(db_session)

    health = await service.calculate_health_score(
        company_id=1,
        account_id=1,
        platform="instagram",
        current_followers=5000,
        engagement_rate=1.0,
        bot_pct=40.0,
        inactive_pct=60.0,
        growth_rate=-5.0,
    )

    assert health.overall_score < 60  # Should be poor due to multiple issues
    assert any("bot" in rec.lower() for rec in health.recommendations)
    assert any("inactive" in rec.lower() for rec in health.recommendations)


# =============================================================================
# Unit Tests - Suspicious Activity Service
# =============================================================================


@pytest.mark.asyncio
async def test_sudden_spike_detection(db_session: AsyncSession, sample_snapshots):
    """Test sudden follower spike detection."""
    from app.followers.schemas import FollowerSnapshotCreate

    service = FollowerSyncService(db_session)

    # Create snapshots with a spike
    for snap in sample_snapshots:
        data = FollowerSnapshotCreate(
            account_id=1,
            platform="instagram",
            external_account_id="test",
            follower_count=snap["follower_count"],
            snapshot_date=snap["snapshot_date"],
        )
        await service.create_snapshot(company_id=1, data=data)

    activity_service = SuspiciousActivityService(db_session)
    snapshots_db = await service.get_snapshots_in_range(
        1, 1,
        datetime.now(timezone.utc) - timedelta(days=30),
        datetime.now(timezone.utc),
    )

    activity = await activity_service.detect_sudden_spike(
        company_id=1,
        account_id=1,
        platform="instagram",
        snapshots=snapshots_db,
    )

    assert activity is not None
    assert activity.alert_type == FollowerAlertType.SUDDEN_SPIKE
    assert activity.severity in ["medium", "high"]


# =============================================================================
# Unit Tests - AI Audience Service
# =============================================================================


@pytest.mark.asyncio
async def test_ai_content_suggestions(db_session: AsyncSession):
    """Test AI content suggestion generation."""
    service = AIAudienceService(db_session)

    suggestions = service._generate_content_suggestions(
        top_interests=["food", "photography"],
        engagement_rate=3.0,
    )

    assert len(suggestions) >= 3
    assert all("title" in s for s in suggestions)
    assert all("expected_engagement" in s for s in suggestions)


@pytest.mark.asyncio
async def test_ai_hashtag_suggestions(db_session: AsyncSession):
    """Test AI hashtag suggestion generation."""
    service = AIAudienceService(db_session)

    hashtags = service._generate_hashtag_suggestions(
        top_interests=["food", "travel"],
        platform="instagram",
    )

    assert len(hashtags) > 0
    assert all(tag.startswith("#") for tag in hashtags)


@pytest.mark.asyncio
async def test_ai_recommendation_generation(db_session: AsyncSession):
    """Test AI recommendation generation."""
    service = AIAudienceService(db_session)

    recommendations = await service.generate_recommendations(
        company_id=1,
        account_id=1,
        platform="instagram",
        engagement_rate=3.5,
        follower_count=5000,
        top_interests=["food", "fashion", "travel"],
    )

    assert len(recommendations) >= 3
    rec_types = [r.recommendation_type for r in recommendations]
    assert "demographics" in rec_types
    assert "content" in rec_types
    assert "timing" in rec_types


# =============================================================================
# API Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_snapshots_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test GET /api/v2/followers/snapshots endpoint."""
    response = await async_client.get("/api/v2/followers/snapshots", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_sync_followers_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test POST /api/v2/followers/sync endpoint."""
    response = await async_client.post(
        "/api/v2/followers/sync?account_id=1&external_account_id=test&platform=instagram&current_followers=1000",
        headers=auth_headers,
    )
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


@pytest.mark.asyncio
async def test_bot_detection_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test bot detection endpoint."""
    response = await async_client.get(
        "/api/v2/followers/bot-detection/patterns", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_health_score_list_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test GET /api/v2/followers/health-score endpoint."""
    response = await async_client.get("/api/v2/followers/health-score", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_ai_recommendations_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test GET /api/v2/followers/ai-recommendations endpoint."""
    response = await async_client.get(
        "/api/v2/followers/ai-recommendations", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_dashboard_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test GET /api/v2/followers/dashboard/{account_id} endpoint."""
    response = await async_client.get(
        "/api/v2/followers/dashboard/1?platform=instagram", headers=auth_headers
    )
    # May return 404 if no snapshots exist, but should not crash
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


@pytest.mark.asyncio
async def test_list_suspicious_activities_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test GET /api/v2/followers/suspicious-activity endpoint."""
    response = await async_client.get(
        "/api/v2/followers/suspicious-activity", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_engagement_quality_endpoint(
    async_client: AsyncClient, auth_headers: Dict[str, str]
):
    """Test GET /api/v2/followers/engagement-quality endpoint."""
    response = await async_client.get(
        "/api/v2/followers/engagement-quality", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total" in data
    assert "items" in data


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
async def test_batch_bot_detection_performance(db_session: AsyncSession):
    """Test batch bot detection performance with 100 profiles."""
    import time

    service = BotDetectionService(db_session)

    # Generate 100 profiles
    profiles = [
        {
            "username": f"user_{i}_{'bot' if i % 5 == 0 else 'real'}",
            "account_id": str(i),
            "post_count": 0 if i % 5 == 0 else random.randint(10, 200),
            "follower_count": random.randint(10, 1000),
            "following_count": random.randint(50, 2000),
            "has_profile_pic": i % 5 != 0,
            "bio_text": None if i % 5 == 0 else f"Bio for user {i}",
            "is_private": False,
            "is_verified": False,
        }
        for i in range(100)
    ]

    start = time.monotonic()
    result = await service.batch_detect(
        company_id=1,
        account_id=1,
        platform="instagram",
        follower_profiles=profiles,
    )
    elapsed = time.monotonic() - start

    assert result.total_analyzed == 100
    assert elapsed < 5.0, f"Batch detection took too long: {elapsed:.2f}s"
