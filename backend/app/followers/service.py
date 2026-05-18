"""Service layer for the Follower Intelligence module.

Provides:
- FollowerSyncService: Historical follower count tracking and sync
- BotDetectionService: Bot/suspicious account detection algorithms
- EngagementQualityService: Engagement quality scoring
- AudienceAnalysisService: Demographics estimation
- FollowerHealthService: Composite health score calculation
- AIAudienceService: AI-powered audience recommendations
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError

from .constants import (
    AI_AUDIENCE_CONFIG,
    BOT_THRESHOLDS,
    ENGAGEMENT_THRESHOLDS,
    HEALTH_SCORE_WEIGHTS,
    SUSPICIOUS_ACTIVITY_THRESHOLDS,
    AccountType,
    BotRiskLevel,
    EngagementTier,
    FollowerAlertType,
    FollowerHealthStatus,
    GenderEstimate,
    get_bot_risk_level,
    get_engagement_tier,
    get_health_status,
)
from .models import (
    AIAudienceRecommendation,
    AudienceDemographics,
    BotPattern,
    EngagementQuality,
    FollowerHealthScore,
    FollowerInsight,
    FollowerSnapshot,
    SuspiciousActivity,
)
from .schemas import (
    AgeDistribution,
    BotDetectionResult,
    BotPatternCreate,
    EngagementQualityCreate,
    FollowerAlert,
    FollowerAnalysisRequest,
    FollowerHealthDetail,
    FollowerSnapshotCreate,
    FollowerSyncSummary,
    GenderDistribution,
    QualityFactors,
    QualityMetrics,
    TargetAudienceSuggestion,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Follower Sync Service
# =============================================================================


class FollowerSyncService:
    """Service for syncing and tracking follower counts over time."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_snapshot(
        self, company_id: int, data: FollowerSnapshotCreate, branch_id: Optional[int] = None
    ) -> FollowerSnapshot:
        """Create a new follower snapshot.

        Args:
            company_id: Tenant company ID.
            data: Snapshot data.
            branch_id: Optional branch ID.

        Returns:
            Created FollowerSnapshot record.
        """
        snapshot = FollowerSnapshot(
            company_id=company_id,
            branch_id=branch_id,
            account_id=data.account_id,
            platform=data.platform,
            external_account_id=data.external_account_id,
            follower_count=data.follower_count,
            following_count=data.following_count or 0,
            post_count=data.post_count or 0,
            snapshot_date=data.snapshot_date,
            raw_data=data.raw_data,
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def get_latest_snapshot(
        self, account_id: int, company_id: int
    ) -> Optional[FollowerSnapshot]:
        """Get the most recent follower snapshot for an account.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.

        Returns:
            Latest FollowerSnapshot or None.
        """
        result = await self.db.execute(
            select(FollowerSnapshot)
            .where(
                FollowerSnapshot.account_id == account_id,
                FollowerSnapshot.company_id == company_id,
            )
            .order_by(desc(FollowerSnapshot.snapshot_date))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_snapshots_in_range(
        self,
        account_id: int,
        company_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[FollowerSnapshot]:
        """Get all snapshots for an account within a date range.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.
            start_date: Range start.
            end_date: Range end.

        Returns:
            List of FollowerSnapshot records.
        """
        result = await self.db.execute(
            select(FollowerSnapshot)
            .where(
                FollowerSnapshot.account_id == account_id,
                FollowerSnapshot.company_id == company_id,
                FollowerSnapshot.snapshot_date >= start_date,
                FollowerSnapshot.snapshot_date <= end_date,
            )
            .order_by(FollowerSnapshot.snapshot_date)
        )
        return list(result.scalars().all())

    async def list_snapshots(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List follower snapshots with pagination.

        Args:
            company_id: Tenant company ID.
            account_id: Optional account filter.
            platform: Optional platform filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated result dict.
        """
        query = select(FollowerSnapshot).where(FollowerSnapshot.company_id == company_id)

        if account_id:
            query = query.where(FollowerSnapshot.account_id == account_id)
        if platform:
            query = query.where(FollowerSnapshot.platform == platform)

        # Count
        count_result = await self.db.execute(
            select(func.count())
            .select_from(FollowerSnapshot)
            .where(FollowerSnapshot.company_id == company_id)
        )
        total = count_result.scalar() or 0

        # Paginated query
        query = query.order_by(desc(FollowerSnapshot.snapshot_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def sync_follower_count(
        self,
        company_id: int,
        account_id: int,
        external_account_id: str,
        platform: str,
        current_followers: int,
        current_following: int = 0,
        current_posts: int = 0,
        branch_id: Optional[int] = None,
        raw_data: Optional[Dict[str, object]] = None,
    ) -> FollowerSyncSummary:
        """Sync current follower count and create a snapshot.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            external_account_id: Platform account ID.
            platform: Social platform.
            current_followers: Current follower count.
            current_following: Current following count.
            current_posts: Current post count.
            branch_id: Optional branch ID.
            raw_data: Optional raw API data.

        Returns:
            FollowerSyncSummary with change information.
        """
        latest = await self.get_latest_snapshot(account_id, company_id)

        snapshot = FollowerSnapshot(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            external_account_id=external_account_id,
            follower_count=current_followers,
            following_count=current_following,
            post_count=current_posts,
            snapshot_date=datetime.now(timezone.utc),
            raw_data=raw_data or {},
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)

        old_count = latest.follower_count if latest else current_followers
        gained = max(0, current_followers - old_count)
        lost = max(0, old_count - current_followers)

        return FollowerSyncSummary(
            account_id=account_id,
            platform=platform,
            old_follower_count=old_count,
            new_follower_count=current_followers,
            gained=gained,
            lost=lost,
            snapshot_id=snapshot.id,
            sync_date=snapshot.snapshot_date,
        )

    async def calculate_growth_trend(
        self, account_id: int, company_id: int, days: int = 30
    ) -> List[Dict[str, object]]:
        """Calculate daily follower growth trend.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.
            days: Number of days to analyze.

        Returns:
            List of daily trend data points.
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        snapshots = await self.get_snapshots_in_range(
            account_id, company_id, start_date, end_date
        )

        if len(snapshots) < 2:
            return []

        trend = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            net_change = curr.follower_count - prev.follower_count
            days_diff = max(
                1,
                (curr.snapshot_date - prev.snapshot_date).total_seconds() / 86400,
            )
            daily_rate = (net_change / prev.follower_count * 100) / days_diff if prev.follower_count > 0 else 0

            trend.append({
                "date": curr.snapshot_date.isoformat(),
                "follower_count": curr.follower_count,
                "following_count": curr.following_count or 0,
                "net_change": net_change,
                "daily_growth_rate": round(daily_rate, 4),
            })

        return trend


# =============================================================================
# Bot Detection Service
# =============================================================================


class BotDetectionService:
    """Service for detecting bot and suspicious accounts.

    Uses a multi-signal scoring algorithm combining profile signals,
    ratio analysis, username patterns, and activity indicators.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _calculate_bot_score(
        self,
        post_count: int,
        follower_count: int,
        following_count: int,
        has_profile_pic: bool,
        bio_text: Optional[str],
        username: str,
        is_private: bool,
        is_verified: bool,
        account_age_days: Optional[int] = None,
        last_post_days: Optional[int] = None,
        has_default_avatar: bool = False,
    ) -> Tuple[float, Dict[str, object]]:
        """Calculate bot probability score from account signals.

        Args:
            post_count: Number of posts.
            follower_count: Number of followers.
            following_count: Number of accounts being followed.
            has_profile_pic: Whether the account has a profile picture.
            bio_text: Bio/description text.
            username: Account username.
            is_private: Whether the account is private.
            is_verified: Whether the account is verified.
            account_age_days: Estimated account age in days.
            last_post_days: Days since last post.
            has_default_avatar: Whether using a default avatar.

        Returns:
            Tuple of (score 0.0-1.0, signals dict).
        """
        score = 0.0
        signals: Dict[str, Any] = {
            "following_ratio": False,
            "no_profile_pic": False,
            "zero_posts": False,
            "suspicious_username": False,
            "no_bio": False,
            "no_recent_activity": False,
            "private_account": False,
            "default_avatar": False,
            "verified": False,
        }

        # 1. Following-to-follower ratio analysis
        if follower_count > 0:
            ratio = following_count / follower_count
        elif following_count > 0:
            ratio = float("inf")
        else:
            ratio = 0.0

        if ratio > BOT_THRESHOLDS["following_follower_ratio_bot"]:
            score += 0.25
            signals["following_ratio"] = True
        elif ratio > BOT_THRESHOLDS["following_follower_ratio_suspicious"]:
            score += 0.15
            signals["following_ratio"] = True
        elif ratio > BOT_THRESHOLDS["following_follower_ratio_low"]:
            score += 0.05
            signals["following_ratio"] = True

        # 2. Profile picture analysis
        if not has_profile_pic:
            score += BOT_THRESHOLDS["no_profile_pic_penalty"]
            signals["no_profile_pic"] = True

        if has_default_avatar:
            score += BOT_THRESHOLDS["default_avatar_penalty"]
            signals["default_avatar"] = True

        # 3. Post count analysis
        if post_count == 0:
            score += 0.20
            signals["zero_posts"] = True
        elif post_count < BOT_THRESHOLDS["min_posts_genuine"]:
            score += 0.05

        # 4. Username pattern analysis
        username_score = self._analyze_username(username)
        score += username_score
        if username_score > 0:
            signals["suspicious_username"] = True

        # 5. Bio analysis
        if not bio_text or len(bio_text.strip()) == 0:
            score += BOT_THRESHOLDS["no_bio_penalty"]
            signals["no_bio"] = True

        # 6. Account age
        if account_age_days is not None and account_age_days < 7:
            score += 0.10  # Very new accounts are more suspicious

        # 7. Activity recency
        if last_post_days is not None and last_post_days > BOT_THRESHOLDS["recent_activity_days"]:
            score += BOT_THRESHOLDS["no_recent_activity_penalty"]
            signals["no_recent_activity"] = True

        # 8. Private account (slightly reduces suspicion)
        if is_private:
            score += BOT_THRESHOLDS["private_account_bonus"]
            signals["private_account"] = True

        # 9. Verified accounts are highly unlikely to be bots
        if is_verified:
            score = max(0.0, score - 0.5)
            signals["verified"] = True

        # Clamp score
        score = max(0.0, min(1.0, score))

        return score, signals

    def _analyze_username(self, username: str) -> float:
        """Analyze username for bot patterns.

        Args:
            username: Account username.

        Returns:
            Suspicion score contribution.
        """
        score = 0.0

        if not username:
            return 0.3

        # Long usernames with many numbers
        digit_count = sum(c.isdigit() for c in username)
        if digit_count > 4:
            score += BOT_THRESHOLDS["username_numbers_penalty"] * min(digit_count - 4, 5)

        # Very long or very short usernames
        if len(username) > BOT_THRESHOLDS["username_length_bot_max"]:
            score += 0.05
        if len(username) < BOT_THRESHOLDS["username_length_bot_min"]:
            score += 0.05

        # Random-looking patterns (mix of letters and numbers in specific patterns)
        if re.search(r"[a-z]+\d{4,}", username, re.IGNORECASE):
            score += BOT_THRESHOLDS["username_random_penalty"]

        # Underscore + number suffix pattern
        if re.search(r"_\d{2,}$", username):
            score += 0.10

        return min(score, 0.5)

    async def detect_bot(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        username: str,
        detected_account_id: str,
        post_count: int = 0,
        follower_count: int = 0,
        following_count: int = 0,
        has_profile_pic: bool = True,
        bio_text: Optional[str] = None,
        is_private: bool = False,
        is_verified: bool = False,
        account_age_days: Optional[int] = None,
        last_post_days: Optional[int] = None,
        has_default_avatar: bool = False,
        branch_id: Optional[int] = None,
    ) -> BotPattern:
        """Run bot detection on a single account and store result.

        Args:
            company_id: Tenant company ID.
            account_id: Our social account ID.
            platform: Social platform.
            username: Suspected account username.
            detected_account_id: Suspected account platform ID.
            Various account metadata fields.

        Returns:
            Created BotPattern record.
        """
        score, signals = self._calculate_bot_score(
            post_count=post_count,
            follower_count=follower_count,
            following_count=following_count,
            has_profile_pic=has_profile_pic,
            bio_text=bio_text,
            username=username,
            is_private=is_private,
            is_verified=is_verified,
            account_age_days=account_age_days,
            last_post_days=last_post_days,
            has_default_avatar=has_default_avatar,
        )

        risk_level = get_bot_risk_level(score)

        pattern = BotPattern(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            detected_username=username,
            detected_account_id=detected_account_id,
            bot_score=score,
            risk_level=risk_level,
            signals=signals,
            has_profile_pic=has_profile_pic,
            post_count=post_count,
            follower_count=follower_count,
            following_count=following_count,
            account_age_days=account_age_days,
            bio_text=bio_text,
            is_verified=is_verified,
            is_private=is_private,
            detected_at=datetime.now(timezone.utc),
        )
        self.db.add(pattern)
        await self.db.commit()
        await self.db.refresh(pattern)
        return pattern

    async def batch_detect(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        follower_profiles: List[Dict[str, object]],
        branch_id: Optional[int] = None,
    ) -> BotDetectionResult:
        """Run bot detection on a batch of follower profiles.

        Args:
            company_id: Tenant company ID.
            account_id: Our social account ID.
            platform: Social platform.
            follower_profiles: List of follower profile dicts.
            branch_id: Optional branch ID.

        Returns:
            BotDetectionResult with aggregated results.
        """
        total_analyzed = len(follower_profiles)
        bots_detected = 0
        risk_distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        signal_counts: Dict[str, int] = {}
        total_score = 0.0
        detected_records: List[BotPattern] = []

        for profile in follower_profiles:
            score, signals = self._calculate_bot_score(
                post_count=profile.get("post_count", 0),
                follower_count=profile.get("follower_count", 0),
                following_count=profile.get("following_count", 0),
                has_profile_pic=profile.get("has_profile_pic", True),
                bio_text=profile.get("bio_text"),
                username=profile.get("username", ""),
                is_private=profile.get("is_private", False),
                is_verified=profile.get("is_verified", False),
                account_age_days=profile.get("account_age_days"),
                last_post_days=profile.get("last_post_days"),
                has_default_avatar=profile.get("has_default_avatar", False),
            )

            risk_level = get_bot_risk_level(score)
            total_score += score

            if score >= BOT_THRESHOLDS["score_medium"]:
                bots_detected += 1

            risk_distribution[risk_level.value] += 1

            # Count signals
            for signal, detected in signals.items():
                if detected:
                    signal_counts[signal] = signal_counts.get(signal, 0) + 1

            # Store high-risk detections
            if score >= BOT_THRESHOLDS["score_medium"]:
                pattern = BotPattern(
                    company_id=company_id,
                    branch_id=branch_id,
                    account_id=account_id,
                    platform=platform,
                    detected_username=profile.get("username", "unknown"),
                    detected_account_id=profile.get("account_id", ""),
                    bot_score=score,
                    risk_level=risk_level,
                    signals=signals,
                    has_profile_pic=profile.get("has_profile_pic", True),
                    post_count=profile.get("post_count", 0),
                    follower_count=profile.get("follower_count", 0),
                    following_count=profile.get("following_count", 0),
                    account_age_days=profile.get("account_age_days"),
                    bio_text=profile.get("bio_text"),
                    is_verified=profile.get("is_verified", False),
                    is_private=profile.get("is_private", False),
                    detected_at=datetime.now(timezone.utc),
                )
                self.db.add(pattern)
                detected_records.append(pattern)

        await self.db.commit()
        for r in detected_records:
            await self.db.refresh(r)

        avg_score = total_score / total_analyzed if total_analyzed > 0 else 0.0
        bot_pct = (bots_detected / total_analyzed * 100) if total_analyzed > 0 else 0.0

        # Top signals
        top_signals = sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return BotDetectionResult(
            account_id=account_id,
            platform=platform,
            total_analyzed=total_analyzed,
            bots_detected=bots_detected,
            high_risk_count=risk_distribution["high"] + risk_distribution["critical"],
            medium_risk_count=risk_distribution["medium"],
            low_risk_count=risk_distribution["low"],
            bot_percentage=round(bot_pct, 2),
            average_bot_score=round(avg_score, 4),
            risk_distribution=risk_distribution,
            top_signals=[s[0] for s in top_signals],
        )

    async def list_bot_patterns(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        risk_level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List bot detection results with pagination.

        Args:
            company_id: Tenant company ID.
            account_id: Optional account filter.
            risk_level: Optional risk level filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated result dict.
        """
        query = select(BotPattern).where(BotPattern.company_id == company_id)

        if account_id:
            query = query.where(BotPattern.account_id == account_id)
        if risk_level:
            query = query.where(BotPattern.risk_level == risk_level)

        # Count
        count_result = await self.db.execute(
            select(func.count())
            .select_from(BotPattern)
            .where(BotPattern.company_id == company_id)
        )
        total = count_result.scalar() or 0

        # Summary stats
        avg_score_result = await self.db.execute(
            select(func.avg(BotPattern.bot_score))
            .where(BotPattern.company_id == company_id)
        )
        avg_score = avg_score_result.scalar() or 0.0

        # Risk distribution
        risk_counts = {}
        for level in ["low", "medium", "high", "critical"]:
            c = await self.db.execute(
                select(func.count())
                .select_from(BotPattern)
                .where(BotPattern.company_id == company_id, BotPattern.risk_level == level)
            )
            risk_counts[level] = c.scalar() or 0

        query = query.order_by(desc(BotPattern.bot_score))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "summary": {
                "average_bot_score": round(float(avg_score), 4) if avg_score else 0.0,
                "risk_distribution": risk_counts,
            },
        }


# =============================================================================
# Suspicious Activity Detection Service
# =============================================================================


class SuspiciousActivityService:
    """Service for detecting and managing suspicious follower activity."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def detect_sudden_spike(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        snapshots: List[FollowerSnapshot],
        branch_id: Optional[int] = None,
    ) -> Optional[SuspiciousActivity]:
        """Detect sudden follower spikes.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            snapshots: Historical snapshots.
            branch_id: Optional branch ID.

        Returns:
            SuspiciousActivity record if spike detected, None otherwise.
        """
        if len(snapshots) < 3:
            return None

        # Calculate average daily change (excluding most recent)
        changes = []
        for i in range(1, len(snapshots)):
            change = snapshots[i].follower_count - snapshots[i - 1].follower_count
            days_diff = max(
                1,
                (snapshots[i].snapshot_date - snapshots[i - 1].snapshot_date).total_seconds() / 86400,
            )
            daily_change = change / days_diff
            changes.append(daily_change)

        if len(changes) < 2:
            return None

        avg_change = statistics.mean(changes[:-1])
        std_dev = statistics.stdev(changes[:-1]) if len(changes) > 2 else avg_change * 0.5
        latest_change = changes[-1]

        if avg_change > 0 and latest_change > avg_change * SUSPICIOUS_ACTIVITY_THRESHOLDS["spike_multiplier"]:
            if latest_change >= SUSPICIOUS_ACTIVITY_THRESHOLDS["spike_absolute_min"]:
                deviation_pct = ((latest_change - avg_change) / avg_change * 100) if avg_change > 0 else 0
                severity = "high" if latest_change > avg_change * 5 else "medium"

                activity = SuspiciousActivity(
                    company_id=company_id,
                    branch_id=branch_id,
                    account_id=account_id,
                    platform=platform,
                    alert_type=FollowerAlertType.SUDDEN_SPIKE,
                    severity=severity,
                    description=(
                        f"Sudden follower spike detected: +{int(latest_change)} followers "
                        f"(average: {int(avg_change)}). Possible bot influx or viral content."
                    ),
                    affected_followers=int(latest_change),
                    baseline_value=avg_change,
                    actual_value=latest_change,
                    deviation_pct=round(deviation_pct, 2),
                    evidence={
                        "daily_changes": [round(c, 2) for c in changes[-7:]],
                        "standard_deviation": round(std_dev, 2),
                    },
                    start_date=snapshots[-1].snapshot_date,
                )
                self.db.add(activity)
                await self.db.commit()
                await self.db.refresh(activity)
                return activity

        return None

    async def detect_sudden_drop(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        snapshots: List[FollowerSnapshot],
        branch_id: Optional[int] = None,
    ) -> Optional[SuspiciousActivity]:
        """Detect sudden follower drops.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            snapshots: Historical snapshots.
            branch_id: Optional branch ID.

        Returns:
            SuspiciousActivity record if drop detected, None otherwise.
        """
        if len(snapshots) < 3:
            return None

        changes = []
        for i in range(1, len(snapshots)):
            change = snapshots[i].follower_count - snapshots[i - 1].follower_count
            changes.append(change)

        avg_change = statistics.mean(changes[:-1])
        latest_change = changes[-1]

        if latest_change < 0 and abs(latest_change) > abs(avg_change) * SUSPICIOUS_ACTIVITY_THRESHOLDS["drop_multiplier"]:
            if abs(latest_change) >= SUSPICIOUS_ACTIVITY_THRESHOLDS["drop_absolute_min"]:
                deviation_pct = ((abs(latest_change) - abs(avg_change)) / max(abs(avg_change), 1) * 100)
                severity = "high" if abs(latest_change) > abs(avg_change) * 5 else "medium"

                activity = SuspiciousActivity(
                    company_id=company_id,
                    branch_id=branch_id,
                    account_id=account_id,
                    platform=platform,
                    alert_type=FollowerAlertType.SUDDEN_DROP,
                    severity=severity,
                    description=(
                        f"Sudden follower drop detected: {int(latest_change)} followers "
                        f"(average change: {int(avg_change)}). Possible mass unfollow event."
                    ),
                    affected_followers=int(abs(latest_change)),
                    baseline_value=avg_change,
                    actual_value=latest_change,
                    deviation_pct=round(deviation_pct, 2),
                    evidence={"recent_changes": changes[-7:]},
                    start_date=snapshots[-1].snapshot_date,
                )
                self.db.add(activity)
                await self.db.commit()
                await self.db.refresh(activity)
                return activity

        return None

    async def list_activities(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        alert_type: Optional[str] = None,
        resolved: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List suspicious activities with pagination.

        Args:
            company_id: Tenant company ID.
            account_id: Optional account filter.
            alert_type: Optional alert type filter.
            resolved: Optional resolved filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated result dict with active alerts summary.
        """
        query = select(SuspiciousActivity).where(SuspiciousActivity.company_id == company_id)

        if account_id:
            query = query.where(SuspiciousActivity.account_id == account_id)
        if alert_type:
            query = query.where(SuspiciousActivity.alert_type == alert_type)
        if resolved is not None:
            query = query.where(SuspiciousActivity.resolved == resolved)

        # Count
        count_result = await self.db.execute(
            select(func.count())
            .select_from(SuspiciousActivity)
            .where(SuspiciousActivity.company_id == company_id)
        )
        total = count_result.scalar() or 0

        # Active alerts summary
        alert_summary = []
        for atype in [
            FollowerAlertType.SUDDEN_SPIKE,
            FollowerAlertType.SUDDEN_DROP,
            FollowerAlertType.BOT_INFLUX,
            FollowerAlertType.LOW_ENGAGEMENT,
            FollowerAlertType.INACTIVE_FOLLOWERS,
        ]:
            c = await self.db.execute(
                select(func.count())
                .select_from(SuspiciousActivity)
                .where(
                    SuspiciousActivity.company_id == company_id,
                    SuspiciousActivity.alert_type == atype,
                    SuspiciousActivity.resolved == False,
                )
            )
            count_val = c.scalar() or 0
            if count_val > 0:
                alert_summary.append({
                    "alert_type": atype.value,
                    "severity": "medium",
                    "count": count_val,
                })

        query = query.order_by(desc(SuspiciousActivity.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "active_alerts": alert_summary,
        }

    async def resolve_activity(self, activity_id: int, company_id: int) -> SuspiciousActivity:
        """Mark a suspicious activity as resolved.

        Args:
            activity_id: Activity ID.
            company_id: Tenant company ID.

        Returns:
            Updated SuspiciousActivity.
        """
        result = await self.db.execute(
            select(SuspiciousActivity).where(
                SuspiciousActivity.id == activity_id,
                SuspiciousActivity.company_id == company_id,
            )
        )
        activity = result.scalar_one_or_none()
        if not activity:
            raise NotFoundError("Suspicious activity not found")

        activity.resolved = True
        activity.end_date = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(activity)
        return activity


# =============================================================================
# Engagement Quality Service
# =============================================================================


class EngagementQualityService:
    """Service for calculating and tracking engagement quality."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def calculate_engagement_quality(
        self,
        likes: int,
        comments: int,
        shares: int,
        reach: int,
        impressions: int,
        follower_count: int,
        historical_rates: Optional[List[float]] = None,
    ) -> Tuple[float, QualityFactors, EngagementTier]:
        """Calculate engagement quality score.

        Args:
            likes: Number of likes.
            comments: Number of comments.
            shares: Number of shares.
            reach: Unique reach.
            impressions: Total impressions.
            follower_count: Current follower count.
            historical_rates: Previous engagement rates for consistency.

        Returns:
            Tuple of (quality_score 0.0-1.0, factors, tier).
        """
        factors = QualityFactors()

        # 1. Engagement rate factor
        engagement_rate = (likes + comments + shares) / reach * 100 if reach > 0 else 0.0
        if engagement_rate >= ENGAGEMENT_THRESHOLDS["elite_rate"]:
            factors.engagement_rate_factor = 1.0
        elif engagement_rate >= ENGAGEMENT_THRESHOLDS["high_rate"]:
            factors.engagement_rate_factor = 0.8
        elif engagement_rate >= ENGAGEMENT_THRESHOLDS["average_rate"]:
            factors.engagement_rate_factor = 0.6
        elif engagement_rate >= ENGAGEMENT_THRESHOLDS["low_rate"]:
            factors.engagement_rate_factor = 0.3
        else:
            factors.engagement_rate_factor = 0.1

        # 2. Comment quality factor (like-to-comment ratio)
        like_comment_ratio = likes / comments if comments > 0 else float("inf")
        if (
            ENGAGEMENT_THRESHOLDS["ideal_like_comment_min"]
            <= like_comment_ratio
            <= ENGAGEMENT_THRESHOLDS["ideal_like_comment_max"]
        ):
            factors.comment_quality_factor = 1.0
        elif like_comment_ratio < 3 or like_comment_ratio > 100:
            factors.comment_quality_factor = 0.2
        else:
            factors.comment_quality_factor = 0.6

        # 3. Reach efficiency factor
        reach_ratio = reach / follower_count if follower_count > 0 else 0
        if (
            ENGAGEMENT_THRESHOLDS["reach_to_follower_healthy_min"]
            <= reach_ratio
            <= ENGAGEMENT_THRESHOLDS["reach_to_follower_healthy_max"]
        ):
            factors.reach_efficiency_factor = 1.0
        elif reach_ratio > 0:
            factors.reach_efficiency_factor = min(1.0, reach_ratio * 2)
        else:
            factors.reach_efficiency_factor = 0.0

        # 4. Consistency factor
        if historical_rates and len(historical_rates) >= 2:
            mean_rate = statistics.mean(historical_rates)
            std_dev = statistics.stdev(historical_rates) if len(historical_rates) > 2 else 0
            cv = std_dev / mean_rate if mean_rate > 0 else 0
            if cv <= ENGAGEMENT_THRESHOLDS["cv_excellent"]:
                factors.consistency_factor = 1.0
            elif cv <= ENGAGEMENT_THRESHOLDS["cv_good"]:
                factors.consistency_factor = 0.8
            elif cv <= ENGAGEMENT_THRESHOLDS["cv_moderate"]:
                factors.consistency_factor = 0.5
            else:
                factors.consistency_factor = 0.2
        else:
            factors.consistency_factor = 0.5  # Default when no history

        # 5. Share ratio factor
        total_engagements = likes + comments + shares
        share_ratio = shares / total_engagements if total_engagements > 0 else 0
        if share_ratio > 0.1:
            factors.share_ratio_factor = 1.0
        elif share_ratio > 0.05:
            factors.share_ratio_factor = 0.7
        elif share_ratio > 0:
            factors.share_ratio_factor = 0.4
        else:
            factors.share_ratio_factor = 0.2

        # Weighted quality score
        weights = {
            "engagement_rate": 0.35,
            "comment_quality": 0.20,
            "reach_efficiency": 0.20,
            "consistency": 0.15,
            "share_ratio": 0.10,
        }
        quality_score = (
            factors.engagement_rate_factor * weights["engagement_rate"]
            + factors.comment_quality_factor * weights["comment_quality"]
            + factors.reach_efficiency_factor * weights["reach_efficiency"]
            + factors.consistency_factor * weights["consistency"]
            + factors.share_ratio_factor * weights["share_ratio"]
        )

        tier = get_engagement_tier(engagement_rate)

        return round(quality_score, 4), factors, tier

    async def create_quality_record(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        data: EngagementQualityCreate,
        branch_id: Optional[int] = None,
    ) -> EngagementQuality:
        """Create an engagement quality record.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            data: Quality data.
            branch_id: Optional branch ID.

        Returns:
            Created EngagementQuality record.
        """
        record = EngagementQuality(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            post_id=data.post_id,
            period_start=data.period_start,
            period_end=data.period_end,
            engagement_rate=data.engagement_rate,
            like_count=data.like_count,
            comment_count=data.comment_count,
            share_count=data.share_count,
            reach_count=data.reach_count,
            impression_count=data.impression_count,
            like_to_comment_ratio=data.like_to_comment_ratio,
            reach_to_follower_ratio=data.reach_to_follower_ratio,
            consistency_score=data.consistency_score,
            quality_score=data.quality_score,
            tier=EngagementTier(data.tier),
            factors=data.factors,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_quality_summary(
        self, account_id: int, company_id: int, days: int = 30
    ) -> QualityMetrics:
        """Get aggregated engagement quality summary.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.
            days: Lookback period in days.

        Returns:
            QualityMetrics summary.
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            select(EngagementQuality)
            .where(
                EngagementQuality.account_id == account_id,
                EngagementQuality.company_id == company_id,
                EngagementQuality.period_start >= start_date,
            )
            .order_by(EngagementQuality.period_start)
        )
        records = list(result.scalars().all())

        if not records:
            return QualityMetrics(
                average_engagement_rate=0.0,
                average_like_to_comment_ratio=0.0,
                average_reach_to_follower_ratio=0.0,
                consistency_score=0.0,
                overall_quality_score=0.0,
                tier="average",
                trend_direction="stable",
            )

        rates = [float(r.engagement_rate) for r in records]
        ratios = [float(r.like_to_comment_ratio) for r in records if float(r.like_to_comment_ratio) > 0]
        reach_ratios = [float(r.reach_to_follower_ratio) for r in records]
        scores = [float(r.quality_score) for r in records]

        avg_rate = statistics.mean(rates)
        avg_ratio = statistics.mean(ratios) if ratios else 0.0
        avg_reach = statistics.mean(reach_ratios)
        avg_score = statistics.mean(scores)

        # Trend direction
        if len(scores) >= 3:
            first_half = statistics.mean(scores[: len(scores) // 2])
            second_half = statistics.mean(scores[len(scores) // 2 :])
            if second_half > first_half * 1.1:
                trend = "improving"
            elif second_half < first_half * 0.9:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        tier = get_engagement_tier(avg_rate)

        return QualityMetrics(
            average_engagement_rate=round(avg_rate, 4),
            average_like_to_comment_ratio=round(avg_ratio, 2),
            average_reach_to_follower_ratio=round(avg_reach, 4),
            consistency_score=round(1.0 - (statistics.stdev(scores) / avg_score if avg_score > 0 else 0), 4),
            overall_quality_score=round(avg_score, 4),
            tier=tier.value,
            trend_direction=trend,
        )

    async def list_quality_records(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List engagement quality records with pagination.

        Args:
            company_id: Tenant company ID.
            account_id: Optional account filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated result dict.
        """
        query = select(EngagementQuality).where(EngagementQuality.company_id == company_id)

        if account_id:
            query = query.where(EngagementQuality.account_id == account_id)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(EngagementQuality)
            .where(EngagementQuality.company_id == company_id)
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(EngagementQuality.period_start))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        # Summary
        summary = await self.get_quality_summary(account_id, company_id) if account_id else None

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "summary": summary,
        }


# =============================================================================
# Audience Analysis Service
# =============================================================================


class AudienceAnalysisService:
    """Service for estimating audience demographics and characteristics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def estimate_gender(self, username: str, bio_text: Optional[str] = None) -> GenderEstimate:
        """Estimate gender from username and bio signals.

        This is a heuristic estimation and should be used as a rough guide only.

        Args:
            username: Account username.
            bio_text: Optional bio text.

        Returns:
            Estimated GenderEstimate.
        """
        text = f"{username} {bio_text or ''}".lower()

        male_indicators = ["mr", "man", "guy", "boy", "father", "dad", "brother", "son", "him", "his"]
        female_indicators = ["ms", "mrs", "woman", "girl", "mother", "mom", "sister", "daughter", "her", "she"]

        male_score = sum(1 for ind in male_indicators if ind in text)
        female_score = sum(1 for ind in female_indicators if ind in text)

        if male_score > female_score:
            return GenderEstimate.MALE
        if female_score > male_score:
            return GenderEstimate.FEMALE
        return GenderEstimate.UNKNOWN

    def estimate_age_range(
        self,
        bio_text: Optional[str] = None,
        content_keywords: Optional[List[str]] = None,
    ) -> str:
        """Estimate age range from bio and content signals.

        Args:
            bio_text: Optional bio text.
            content_keywords: Optional content keywords.

        Returns:
            Estimated age range string.
        """
        text = (bio_text or "").lower()
        keywords = [k.lower() for k in (content_keywords or [])]
        all_text = f"{text} {' '.join(keywords)}"

        # Keywords that indicate age groups
        teen_indicators = ["student", "high school", "teen", "16", "17", "18", "uni", "college freshman"]
        young_adult_indicators = ["university", "grad", "22", "23", "24", "25", "startup", "entry-level"]
        adult_indicators = ["professional", "manager", "married", "parent", "homeowner", "35", "40"]
        senior_indicators = ["retired", "grandparent", "50+", "veteran", "senior"]

        scores = {
            "13-17": sum(1 for ind in teen_indicators if ind in all_text),
            "18-24": sum(1 for ind in young_adult_indicators if ind in all_text) + (2 if "college" in all_text or "uni" in all_text else 0),
            "25-34": sum(1 for ind in adult_indicators if ind in all_text),
            "35-44": sum(1 for ind in adult_indicators if ind in all_text),
            "45-54": sum(1 for ind in senior_indicators if ind in all_text),
            "55-64": sum(1 for ind in senior_indicators if ind in all_text),
            "65+": sum(1 for ind in senior_indicators if ind in all_text),
        }

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "18-24"  # Default for social media

    async def analyze_demographics(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        follower_profiles: List[Dict[str, object]],
        branch_id: Optional[int] = None,
    ) -> AudienceDemographics:
        """Analyze audience demographics from follower profiles.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            follower_profiles: List of follower profile dicts.
            branch_id: Optional branch ID.

        Returns:
            Created AudienceDemographics record.
        """
        total = len(follower_profiles)
        if total == 0:
            demo = AudienceDemographics(
                company_id=company_id,
                branch_id=branch_id,
                account_id=account_id,
                platform=platform,
                analysis_date=datetime.now(timezone.utc),
            )
            self.db.add(demo)
            await self.db.commit()
            return demo

        # Gender counts
        gender_counts = {"male": 0, "female": 0, "unknown": 0}
        age_counts = {
            "13-17": 0, "18-24": 0, "25-34": 0, "35-44": 0,
            "45-54": 0, "55-64": 0, "65+": 0,
        }
        location_counts: Dict[str, int] = {}
        language_counts: Dict[str, int] = {}
        interest_counts: Dict[str, int] = {}

        for profile in follower_profiles:
            # Gender estimation
            gender = self.estimate_gender(
                profile.get("username", ""),
                profile.get("bio_text"),
            )
            gender_counts[gender.value] += 1

            # Age estimation
            age_range = self.estimate_age_range(
                profile.get("bio_text"),
                profile.get("content_keywords"),
            )
            if age_range in age_counts:
                age_counts[age_range] += 1

            # Location
            location = profile.get("location")
            if location:
                location_counts[location] = location_counts.get(location, 0) + 1

            # Language
            language = profile.get("language")
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1

            # Interests from bio
            bio = (profile.get("bio_text") or "").lower()
            interest_keywords = {
                "food": ["food", "restaurant", "cooking", "chef", "recipe"],
                "fashion": ["fashion", "style", "outfit", "clothing", "brand"],
                "travel": ["travel", "wanderlust", "adventure", "trip", "vacation"],
                "tech": ["tech", "developer", "coding", "software", "ai", "startup"],
                "fitness": ["fitness", "gym", "workout", "health", "yoga"],
                "music": ["music", "singer", "artist", "song", "concert"],
                "sports": ["sports", "football", "basketball", "soccer", "game"],
                "photography": ["photo", "photography", "camera", "photographer"],
                "business": ["business", "entrepreneur", "ceo", "founder"],
                "lifestyle": ["lifestyle", "blogger", "influencer", "content"],
            }
            for interest, keywords in interest_keywords.items():
                if any(kw in bio for kw in keywords):
                    interest_counts[interest] = interest_counts.get(interest, 0) + 1

        # Calculate percentages
        male_pct = (gender_counts["male"] / total * 100) if total > 0 else 0
        female_pct = (gender_counts["female"] / total * 100) if total > 0 else 0
        unknown_gender_pct = 100.0 - male_pct - female_pct

        age_pcts = {
            k: (v / total * 100) if total > 0 else 0
            for k, v in age_counts.items()
        }

        # Top locations
        top_cities = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_langs = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_interests = sorted(interest_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Confidence score based on sample size
        confidence = min(1.0, total / 1000) * 0.8 + 0.1

        demo = AudienceDemographics(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            age_13_17_pct=round(age_pcts["13-17"], 2),
            age_18_24_pct=round(age_pcts["18-24"], 2),
            age_25_34_pct=round(age_pcts["25-34"], 2),
            age_35_44_pct=round(age_pcts["35-44"], 2),
            age_45_54_pct=round(age_pcts["45-54"], 2),
            age_55_64_pct=round(age_pcts["55-64"], 2),
            age_65_plus_pct=round(age_pcts["65+"], 2),
            male_pct=round(male_pct, 2),
            female_pct=round(female_pct, 2),
            unknown_gender_pct=round(max(0, unknown_gender_pct), 2),
            top_locations={
                "cities": [{"name": name, "count": count} for name, count in top_cities],
                "countries": [],
            },
            top_languages=[{"language": name, "count": count} for name, count in top_langs],
            interests=[{"name": name, "count": count} for name, count in top_interests],
            estimated_accounts=total,
            confidence_score=round(confidence, 3),
            analysis_date=datetime.now(timezone.utc),
        )
        self.db.add(demo)
        await self.db.commit()
        await self.db.refresh(demo)
        return demo

    async def get_latest_demographics(
        self, account_id: int, company_id: int
    ) -> Optional[AudienceDemographics]:
        """Get the most recent demographics for an account.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.

        Returns:
            Latest AudienceDemographics or None.
        """
        result = await self.db.execute(
            select(AudienceDemographics)
            .where(
                AudienceDemographics.account_id == account_id,
                AudienceDemographics.company_id == company_id,
            )
            .order_by(desc(AudienceDemographics.analysis_date))
            .limit(1)
        )
        return result.scalar_one_or_none()


# =============================================================================
# Follower Health Service
# =============================================================================


class FollowerHealthService:
    """Service for calculating composite follower health scores."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.bot_service = BotDetectionService(db)
        self.engagement_service = EngagementQualityService(db)
        self.activity_service = SuspiciousActivityService(db)

    async def calculate_health_score(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        current_followers: int,
        engagement_rate: float,
        bot_pct: float,
        inactive_pct: float,
        growth_rate: float,
        branch_id: Optional[int] = None,
    ) -> FollowerHealthScore:
        """Calculate composite follower health score.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            current_followers: Current follower count.
            engagement_rate: Current engagement rate.
            bot_pct: Percentage of bot followers.
            inactive_pct: Percentage of inactive followers.
            growth_rate: Growth rate percentage.
            branch_id: Optional branch ID.

        Returns:
            Created FollowerHealthScore record.
        """
        # 1. Engagement quality score (0-100)
        if engagement_rate >= ENGAGEMENT_THRESHOLDS["elite_rate"]:
            engagement_score = 100
        elif engagement_rate >= ENGAGEMENT_THRESHOLDS["high_rate"]:
            engagement_score = 85
        elif engagement_rate >= ENGAGEMENT_THRESHOLDS["average_rate"]:
            engagement_score = 65
        elif engagement_rate >= ENGAGEMENT_THRESHOLDS["low_rate"]:
            engagement_score = 40
        else:
            engagement_score = 20

        # 2. Bot ratio score (0-100, lower bot % = higher score)
        bot_score = max(0, 100 - int(bot_pct * 5))

        # 3. Growth stability score (0-100)
        if growth_rate > 5:  # Very high growth might be suspicious
            growth_score = 60
        elif growth_rate > 2:
            growth_score = 85
        elif growth_rate > 0:
            growth_score = 75
        elif growth_rate > -2:
            growth_score = 60
        else:
            growth_score = 40

        # 4. Audience diversity score (0-100)
        # Based on inactive percentage - more active = more diverse engagement
        diversity_score = max(0, 100 - int(inactive_pct * 1.5))

        # 5. Activity recency score (0-100)
        activity_score = max(0, 100 - int(inactive_pct))

        # Weighted composite score
        overall = int(
            engagement_score * HEALTH_SCORE_WEIGHTS["engagement_quality"]
            + bot_score * HEALTH_SCORE_WEIGHTS["bot_ratio"]
            + growth_score * HEALTH_SCORE_WEIGHTS["growth_stability"]
            + diversity_score * HEALTH_SCORE_WEIGHTS["audience_diversity"]
            + activity_score * HEALTH_SCORE_WEIGHTS["activity_recency"]
        )

        status = get_health_status(overall)

        # Generate recommendations
        recommendations: List[str] = []
        if engagement_score < 50:
            recommendations.append(
                "Engagement rate is low. Try posting more interactive content like polls, "
                "questions, and stories to boost audience participation."
            )
        if bot_score < 60:
            recommendations.append(
                f"High bot percentage detected ({bot_pct:.1f}%). Consider running a "
                f"follower cleanup campaign to remove fake accounts."
            )
        if inactive_pct > 30:
            recommendations.append(
                f"{inactive_pct:.1f}% of followers are inactive. Re-engagement campaigns "
                f"or giveaways may help reactivate dormant followers."
            )
        if growth_rate < 0:
            recommendations.append(
                "Negative growth rate detected. Review content strategy and posting frequency."
            )
        if not recommendations:
            recommendations.append(
                "Follower health is good. Continue current strategy and monitor for changes."
            )

        health = FollowerHealthScore(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            overall_score=overall,
            status=status,
            engagement_quality_score=engagement_score,
            bot_ratio_score=bot_score,
            growth_stability_score=growth_score,
            audience_diversity_score=diversity_score,
            activity_recency_score=activity_score,
            bot_pct=round(bot_pct, 2),
            inactive_pct=round(inactive_pct, 2),
            engagement_rate_pct=round(engagement_rate, 4),
            growth_rate_pct=round(growth_rate, 4),
            score_date=datetime.now(timezone.utc),
            recommendations=recommendations,
        )
        self.db.add(health)
        await self.db.commit()
        await self.db.refresh(health)
        return health

    async def get_latest_health_score(
        self, account_id: int, company_id: int
    ) -> Optional[FollowerHealthScore]:
        """Get the most recent health score for an account.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.

        Returns:
            Latest FollowerHealthScore or None.
        """
        result = await self.db.execute(
            select(FollowerHealthScore)
            .where(
                FollowerHealthScore.account_id == account_id,
                FollowerHealthScore.company_id == company_id,
            )
            .order_by(desc(FollowerHealthScore.score_date))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_health_scores(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List health scores with pagination.

        Args:
            company_id: Tenant company ID.
            account_id: Optional account filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated result dict.
        """
        query = select(FollowerHealthScore).where(FollowerHealthScore.company_id == company_id)

        if account_id:
            query = query.where(FollowerHealthScore.account_id == account_id)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(FollowerHealthScore)
            .where(FollowerHealthScore.company_id == company_id)
        )
        total = count_result.scalar() or 0

        # Average score
        avg_result = await self.db.execute(
            select(func.avg(FollowerHealthScore.overall_score))
            .where(FollowerHealthScore.company_id == company_id)
        )
        avg_score = avg_result.scalar() or 0.0

        query = query.order_by(desc(FollowerHealthScore.score_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "average_score": round(float(avg_score), 2) if avg_score else 0.0,
        }


# =============================================================================
# AI Audience Service
# =============================================================================


class AIAudienceService:
    """Service for generating AI-powered audience recommendations.

    Combines follower data, engagement patterns, demographics, and
    industry benchmarks to generate actionable recommendations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _generate_content_suggestions(
        self,
        top_interests: List[str],
        engagement_rate: float,
        demographics: Optional[AudienceDemographics] = None,
    ) -> List[Dict[str, object]]:
        """Generate content suggestions based on audience analysis.

        Args:
            top_interests: Top audience interests.
            engagement_rate: Current engagement rate.
            demographics: Optional demographics data.

        Returns:
            List of content suggestion dicts.
        """
        suggestions = []

        interest_content_map = {
            "food": [
                {"type": "carousel", "title": "Behind-the-scenes recipe content", "expected_engagement": 1.5},
                {"type": "reel", "title": "Quick cooking tutorials", "expected_engagement": 2.0},
            ],
            "fashion": [
                {"type": "carousel", "title": "Outfit of the day / style guides", "expected_engagement": 1.8},
                {"type": "story", "title": "Fashion poll and Q&A", "expected_engagement": 1.2},
            ],
            "travel": [
                {"type": "reel", "title": "Destination highlight videos", "expected_engagement": 2.2},
                {"type": "carousel", "title": "Travel tips and guides", "expected_engagement": 1.6},
            ],
            "fitness": [
                {"type": "reel", "title": "Workout routines and challenges", "expected_engagement": 1.9},
                {"type": "story", "title": "Fitness progress tracking", "expected_engagement": 1.3},
            ],
            "tech": [
                {"type": "carousel", "title": "Product reviews and comparisons", "expected_engagement": 1.4},
                {"type": "reel", "title": "Tech tips and tutorials", "expected_engagement": 1.7},
            ],
            "business": [
                {"type": "carousel", "title": "Industry insights and tips", "expected_engagement": 1.3},
                {"type": "story", "title": "Day-in-the-life content", "expected_engagement": 1.1},
            ],
            "photography": [
                {"type": "carousel", "title": "Photo series and editing tips", "expected_engagement": 2.0},
                {"type": "reel", "title": "Before/after editing videos", "expected_engagement": 2.3},
            ],
            "music": [
                {"type": "reel", "title": "Music recommendations and playlists", "expected_engagement": 1.8},
                {"type": "story", "title": "Behind the music content", "expected_engagement": 1.4},
            ],
        }

        for interest in top_interests[:3]:
            if interest in interest_content_map:
                for suggestion in interest_content_map[interest]:
                    suggestion["description"] = (
                        f"Create {suggestion['type']} content about {interest} "
                        f"to engage your {interest}-interested audience segment."
                    )
                    suggestion["expected_engagement"] = round(
                        suggestion["expected_engagement"] * (engagement_rate / 100 + 1), 2
                    )
                    suggestions.append(suggestion)

        # Add generic suggestions if few interest-based ones
        if len(suggestions) < 3:
            generic = [
                {
                    "type": "story",
                    "title": "Interactive polls and quizzes",
                    "description": "Boost engagement with interactive story content that encourages audience participation.",
                    "expected_engagement": round(1.2 * (engagement_rate / 100 + 1), 2),
                },
                {
                    "type": "reel",
                    "title": "Trending audio and challenges",
                    "description": "Leverage trending audio and participate in viral challenges to increase reach.",
                    "expected_engagement": round(2.0 * (engagement_rate / 100 + 1), 2),
                },
                {
                    "type": "carousel",
                    "title": "Educational carousel posts",
                    "description": "Create value-packed carousel posts that followers will save and share.",
                    "expected_engagement": round(1.5 * (engagement_rate / 100 + 1), 2),
                },
            ]
            suggestions.extend(generic[: 3 - len(suggestions)])

        return suggestions

    def _generate_optimal_posting_times(
        self, demographics: Optional[AudienceDemographics] = None
    ) -> Dict[str, object]:
        """Generate optimal posting time recommendations.

        Args:
            demographics: Optional demographics data.

        Returns:
            Dict with weekday and weekend posting time recommendations.
        """
        # Default recommendations based on general social media patterns
        # These can be refined with actual audience activity data
        return {
            "weekdays": {
                "morning": {"time": "08:00-09:00", "confidence": 0.75, "reason": "Morning commute scroll"},
                "lunch": {"time": "12:00-13:00", "confidence": 0.85, "reason": "Peak lunch break activity"},
                "evening": {"time": "18:00-20:00", "confidence": 0.90, "reason": "Post-work peak engagement"},
            },
            "weekends": {
                "morning": {"time": "09:00-10:00", "confidence": 0.70, "reason": "Relaxed morning browsing"},
                "afternoon": {"time": "14:00-16:00", "confidence": 0.80, "reason": "Weekend leisure time"},
                "evening": {"time": "19:00-21:00", "confidence": 0.85, "reason": "Weekend evening peak"},
            },
        }

    def _generate_hashtag_suggestions(
        self, top_interests: List[str], platform: str
    ) -> List[str]:
        """Generate hashtag suggestions based on audience interests.

        Args:
            top_interests: Top audience interests.
            platform: Social platform.

        Returns:
            List of suggested hashtags.
        """
        hashtag_map = {
            "food": ["#foodie", "#foodphotography", "#instafood", "#homemade", "#yummy"],
            "fashion": ["#fashion", "#ootd", "#style", "#outfit", "#fashionista"],
            "travel": ["#travel", "#wanderlust", "#adventure", "#explore", "#travelgram"],
            "fitness": ["#fitness", "#workout", "#gym", "#health", "#fitlife"],
            "tech": ["#tech", "#technology", "#innovation", "#gadgets", "#digital"],
            "photography": ["#photography", "#photo", "#photooftheday", "#capture", "#photographer"],
            "music": ["#music", "#musician", "#songs", "#playlist", "#newmusic"],
            "business": ["#business", "#entrepreneur", "#success", "#marketing", "#startup"],
            "lifestyle": ["#lifestyle", "#life", "#daily", "#motivation", "#inspiration"],
            "sports": ["#sports", "#fitness", "#training", "#athlete", "#game"],
        }

        hashtags = []
        for interest in top_interests[:3]:
            if interest in hashtag_map:
                hashtags.extend(hashtag_map[interest])

        # Platform-specific additions
        if platform == "instagram":
            hashtags.extend(["#instagood", "#instadaily", "#reels"])
        elif platform == "tiktok":
            hashtags.extend(["#fyp", "#foryou", "#viral"])
        elif platform == "facebook":
            hashtags.extend(["#trending", "#viral"])

        return list(set(hashtags))[:15]

    async def generate_recommendations(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        engagement_rate: float,
        follower_count: int,
        top_interests: List[str],
        demographics: Optional[AudienceDemographics] = None,
        branch_id: Optional[int] = None,
    ) -> List[AIAudienceRecommendation]:
        """Generate AI audience recommendations.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            engagement_rate: Current engagement rate.
            follower_count: Current follower count.
            top_interests: Top audience interests.
            demographics: Optional demographics data.
            branch_id: Optional branch ID.

        Returns:
            List of created AIAudienceRecommendation records.
        """
        recommendations: List[AIAudienceRecommendation] = []
        now = datetime.now(timezone.utc)

        # 1. Demographics recommendation
        if demographics:
            age_groups = []
            for attr, label in [
                ("age_18_24_pct", "18-24"),
                ("age_25_34_pct", "25-34"),
                ("age_35_44_pct", "35-44"),
                ("age_13_17_pct", "13-17"),
                ("age_45_54_pct", "45-54"),
                ("age_55_64_pct", "55-64"),
                ("age_65_plus_pct", "65+"),
            ]:
                val = float(getattr(demographics, attr, 0))
                if val > 10:
                    age_groups.append(label)

            genders = []
            if float(demographics.male_pct) > 30:
                genders.append("male")
            if float(demographics.female_pct) > 30:
                genders.append("female")

            rec = AIAudienceRecommendation(
                company_id=company_id,
                branch_id=branch_id,
                account_id=account_id,
                platform=platform,
                recommendation_type="demographics",
                title="Optimize content for your core audience",
                description=(
                    f"Your largest audience segments are ages {', '.join(age_groups[:3])}. "
                    f"Tailor content themes, tone, and visual style to resonate with these "
                    f"demographics. Consider creating age-specific content series."
                ),
                target_demographics={
                    "age_ranges": age_groups,
                    "genders": genders,
                    "locations": [],
                    "interests": top_interests[:5],
                },
                suggested_hashtags=self._generate_hashtag_suggestions(top_interests, platform),
                optimal_posting_times=self._generate_optimal_posting_times(demographics),
                content_suggestions=self._generate_content_suggestions(top_interests, engagement_rate, demographics),
                expected_impact=min(100, int(engagement_rate * 10 + 30)),
                confidence=round(float(demographics.confidence_score), 3) if demographics else 0.5,
                generated_at=now,
            )
            self.db.add(rec)
            recommendations.append(rec)

        # 2. Content recommendation
        content_rec = AIAudienceRecommendation(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            recommendation_type="content",
            title="Content strategy optimization",
            description=(
                f"Based on your audience's interest in {', '.join(top_interests[:3])}, "
                f"focus on creating more content around these themes. Your current engagement "
                f"rate is {engagement_rate:.2f}%. Target a {engagement_rate * 1.5:.2f}% engagement "
                f"rate with optimized content."
            ),
            target_demographics={
                "age_ranges": [],
                "genders": [],
                "locations": [],
                "interests": top_interests[:5],
            },
            suggested_hashtags=self._generate_hashtag_suggestions(top_interests, platform),
            optimal_posting_times=self._generate_optimal_posting_times(demographics),
            content_suggestions=self._generate_content_suggestions(top_interests, engagement_rate, demographics),
            expected_impact=min(100, int(engagement_rate * 12 + 25)),
            confidence=0.7,
            generated_at=now,
        )
        self.db.add(content_rec)
        recommendations.append(content_rec)

        # 3. Timing recommendation
        timing_rec = AIAudienceRecommendation(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            recommendation_type="timing",
            title="Optimal posting schedule",
            description=(
                "Post during peak engagement hours to maximize reach. "
                "Weekday lunch hours (12:00-13:00) and evenings (18:00-20:00) "
                "typically show highest engagement rates. Test weekend posting "
                "for additional reach."
            ),
            target_demographics={
                "age_ranges": [],
                "genders": [],
                "locations": [],
                "interests": [],
            },
            suggested_hashtags=[],
            optimal_posting_times=self._generate_optimal_posting_times(demographics),
            content_suggestions=[],
            expected_impact=40,
            confidence=0.65,
            generated_at=now,
        )
        self.db.add(timing_rec)
        recommendations.append(timing_rec)

        # 4. Growth recommendation
        if follower_count < 10000:
            growth_rec = AIAudienceRecommendation(
                company_id=company_id,
                branch_id=branch_id,
                account_id=account_id,
                platform=platform,
                recommendation_type="growth",
                title=f"Accelerate growth to {follower_count * 2:,} followers",
                description=(
                    f"With {follower_count:,} current followers, focus on collaboration "
                    f"posts, influencer partnerships, and cross-promotion. Engage actively "
                    f"with accounts in your niche to increase visibility."
                ),
                target_demographics={
                    "age_ranges": [],
                    "genders": [],
                    "locations": [],
                    "interests": top_interests[:5],
                },
                suggested_hashtags=self._generate_hashtag_suggestions(top_interests, platform),
                optimal_posting_times={},
                content_suggestions=[
                    {
                        "type": "collaboration",
                        "title": "Partner with similar-sized accounts",
                        "description": "Cross-promote with accounts in your niche for mutual growth.",
                        "expected_engagement": 2.5,
                    }
                ],
                expected_impact=50,
                confidence=0.6,
                generated_at=now,
            )
            self.db.add(growth_rec)
            recommendations.append(growth_rec)

        await self.db.commit()
        for rec in recommendations:
            await self.db.refresh(rec)
        return recommendations

    async def list_recommendations(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        rec_type: Optional[str] = None,
        implemented: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List AI recommendations with pagination.

        Args:
            company_id: Tenant company ID.
            account_id: Optional account filter.
            rec_type: Optional recommendation type filter.
            implemented: Optional implementation status filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated result dict.
        """
        query = select(AIAudienceRecommendation).where(
            AIAudienceRecommendation.company_id == company_id
        )

        if account_id:
            query = query.where(AIAudienceRecommendation.account_id == account_id)
        if rec_type:
            query = query.where(AIAudienceRecommendation.recommendation_type == rec_type)
        if implemented is not None:
            query = query.where(AIAudienceRecommendation.implemented == implemented)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(AIAudienceRecommendation)
            .where(AIAudienceRecommendation.company_id == company_id)
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(AIAudienceRecommendation.generated_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def mark_implemented(
        self, rec_id: int, company_id: int, result_notes: Optional[str] = None
    ) -> AIAudienceRecommendation:
        """Mark a recommendation as implemented.

        Args:
            rec_id: Recommendation ID.
            company_id: Tenant company ID.
            result_notes: Optional implementation result notes.

        Returns:
            Updated AIAudienceRecommendation.
        """
        result = await self.db.execute(
            select(AIAudienceRecommendation).where(
                AIAudienceRecommendation.id == rec_id,
                AIAudienceRecommendation.company_id == company_id,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            raise NotFoundError("Recommendation not found")

        rec.implemented = True
        rec.implementation_result = result_notes
        await self.db.commit()
        await self.db.refresh(rec)
        return rec


# =============================================================================
# Follower Delta Service (Snapshot comparison, estimated unfollow detection)
# =============================================================================


class FollowerDeltaService:
    """Service for detecting follower changes between snapshots.

    Uses snapshot comparison to estimate new followers, unfollows,
    and suspicious changes. All counts are estimates with confidence scores.
    Never claims definitive unfollow counts.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _estimate_confidence(self, snapshot_count: int, days_between: int) -> float:
        """Calculate confidence based on sample size and freshness.

        More snapshots and shorter gaps = higher confidence.
        """
        sample_confidence = min(1.0, snapshot_count / 7)  # Max at 7+ snapshots
        freshness_confidence = max(0.3, 1.0 - (days_between - 1) * 0.1)  # Degrades with age
        return round(sample_confidence * freshness_confidence, 3)

    def _classify_delta(
        self, follower_delta: int, avg_daily_change: float, std_dev: float
    ) -> Tuple[str, bool, str]:
        """Classify a follower delta into an event type.

        Returns:
            Tuple of (event_type, is_suspicious, confidence_reason).
        """
        threshold = max(2, std_dev * 2) if std_dev > 0 else max(2, abs(avg_daily_change) * 3)

        if follower_delta > 0:
            if follower_delta > threshold * 3:
                return "new_follower", True, f"Large gain: {follower_delta} (threshold: {threshold:.1f})"
            return "new_follower", False, f"Normal gain: {follower_delta}"
        elif follower_delta < 0:
            if abs(follower_delta) > threshold * 3:
                return "estimated_unfollow", True, f"Significant drop: {follower_delta} (threshold: {threshold:.1f})"
            elif abs(follower_delta) > threshold:
                return "estimated_unfollow", False, f"Moderate drop: {follower_delta}"
            return "estimated_unfollow", False, f"Small decline: {follower_delta}"
        return "recovered_follower", False, "No change"

    async def detect_delta(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        previous_snapshot: FollowerSnapshot,
        current_snapshot: FollowerSnapshot,
        branch_id: Optional[int] = None,
    ) -> Optional[FollowerDeltaEvent]:
        """Detect follower delta between two snapshots.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            platform: Social platform.
            previous_snapshot: Previous snapshot.
            current_snapshot: Current snapshot.
            branch_id: Optional branch ID.

        Returns:
            FollowerDeltaEvent record if significant change detected.
        """
        follower_delta = int(current_snapshot.follower_count) - int(previous_snapshot.follower_count)

        # Get historical snapshots for baseline
        end_date = current_snapshot.snapshot_date
        start_date = end_date - timedelta(days=30)

        result = await self.db.execute(
            select(FollowerSnapshot)
            .where(
                FollowerSnapshot.account_id == account_id,
                FollowerSnapshot.platform == platform,
                FollowerSnapshot.snapshot_date >= start_date,
                FollowerSnapshot.snapshot_date < end_date,
            )
            .order_by(FollowerSnapshot.snapshot_date)
        )
        historical = list(result.scalars().all())

        # Calculate baseline
        if len(historical) >= 2:
            changes = []
            for i in range(1, len(historical)):
                delta = int(historical[i].follower_count) - int(historical[i - 1].follower_count)
                days_diff = max(1, (historical[i].snapshot_date - historical[i - 1].snapshot_date).total_seconds() / 86400)
                changes.append(delta / days_diff)
            avg_change = statistics.mean(changes)
            std_dev = statistics.stdev(changes) if len(changes) > 2 else abs(avg_change) * 0.3
        else:
            avg_change = 0.0
            std_dev = 1.0

        days_between = max(1, (current_snapshot.snapshot_date - previous_snapshot.snapshot_date).total_seconds() / 86400)
        normalized_delta = follower_delta / days_between

        event_type, is_suspicious, confidence_reason = self._classify_delta(
            follower_delta, avg_change, std_dev
        )

        # Estimate new vs unfollow
        if follower_delta > 0:
            estimated_new = follower_delta
            estimated_unfollow = 0
        elif follower_delta < 0:
            estimated_new = 0
            estimated_unfollow = abs(follower_delta)
        else:
            estimated_new = 0
            estimated_unfollow = 0

        confidence = self._estimate_confidence(len(historical) + 1, days_between)

        # Only create event if significant change or suspicious
        if abs(follower_delta) < 2 and not is_suspicious:
            return None

        delta_event = FollowerDeltaEvent(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            event_type=event_type,
            previous_snapshot_id=previous_snapshot.id,
            current_snapshot_id=current_snapshot.id,
            follower_delta=follower_delta,
            estimated_new=estimated_new,
            estimated_unfollow=estimated_unfollow,
            confidence_score=confidence,
            confidence_reason=confidence_reason,
            is_suspicious=is_suspicious,
            event_date=current_snapshot.snapshot_date,
            details={
                "baseline_avg": round(avg_change, 2),
                "std_dev": round(std_dev, 2),
                "days_between": round(days_between, 1),
                "normalized_delta": round(normalized_delta, 2),
                "historical_snapshots": len(historical),
            },
        )
        self.db.add(delta_event)

        # Also create audience loss estimate if unfollow detected
        if estimated_unfollow > 0:
            loss = AudienceLossEstimate(
                company_id=company_id,
                branch_id=branch_id,
                account_id=account_id,
                platform=platform,
                loss_type="estimated_unfollow" if not is_suspicious else "suspicious_drop",
                estimated_loss_count=estimated_unfollow,
                confidence_score=confidence,
                confidence_reason=confidence_reason,
                previous_follower_count=int(previous_snapshot.follower_count),
                current_follower_count=int(current_snapshot.follower_count),
                net_change=follower_delta,
                is_suspicious=is_suspicious,
                snapshot_ids=[previous_snapshot.id, current_snapshot.id],
                estimate_date=current_snapshot.snapshot_date,
            )
            self.db.add(loss)

        await self.db.commit()
        await self.db.refresh(delta_event)
        return delta_event

    async def list_delta_events(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        event_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List follower delta events with pagination."""
        query = select(FollowerDeltaEvent).where(FollowerDeltaEvent.company_id == company_id)

        if account_id:
            query = query.where(FollowerDeltaEvent.account_id == account_id)
        if event_type:
            query = query.where(FollowerDeltaEvent.event_type == event_type)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(FollowerDeltaEvent)
            .where(FollowerDeltaEvent.company_id == company_id)
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(FollowerDeltaEvent.event_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def get_delta_summary(self, company_id: int, account_id: int, days: int = 30) -> Dict[str, object]:
        """Get delta summary for an account."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            select(FollowerDeltaEvent)
            .where(
                FollowerDeltaEvent.company_id == company_id,
                FollowerDeltaEvent.account_id == account_id,
                FollowerDeltaEvent.event_date >= start_date,
            )
        )
        events = list(result.scalars().all())

        total_new = sum(e.estimated_new for e in events)
        total_unfollow = sum(e.estimated_unfollow for e in events)
        suspicious_count = sum(1 for e in events if e.is_suspicious)
        avg_confidence = statistics.mean([float(e.confidence_score) for e in events]) if events else 0.0

        return {
            "period_days": days,
            "total_events": len(events),
            "estimated_new_followers": total_new,
            "estimated_unfollows": total_unfollow,
            "net_change": total_new - total_unfollow,
            "suspicious_events": suspicious_count,
            "average_confidence": round(avg_confidence, 3),
            "note": "All unfollow counts are estimates, not definitive data.",
        }


# =============================================================================
# Engagement Event Service
# =============================================================================


class EngagementEventService:
    """Service for tracking and managing follower engagement events."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_event(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        event_type: str,
        follower_account_id: Optional[str] = None,
        follower_username: Optional[str] = None,
        post_id: Optional[str] = None,
        message_preview: Optional[str] = None,
        sentiment: str = "neutral",
        is_new_lead: bool = False,
        lead_score: float = 0.0,
        campaign_id: Optional[str] = None,
        event_date: Optional[datetime] = None,
        raw_data: Optional[Dict[str, object]] = None,
        branch_id: Optional[int] = None,
    ) -> EngagementEvent:
        """Record a new engagement event."""
        event = EngagementEvent(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            event_type=event_type,
            follower_account_id=follower_account_id,
            follower_username=follower_username,
            post_id=post_id,
            message_preview=message_preview,
            sentiment=sentiment,
            is_new_lead=is_new_lead,
            lead_score=lead_score,
            campaign_id=campaign_id,
            event_date=event_date or datetime.now(timezone.utc),
            raw_data=raw_data or {},
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def list_events(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        event_type: Optional[str] = None,
        platform: Optional[str] = None,
        is_new_lead: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List engagement events with pagination."""
        query = select(EngagementEvent).where(EngagementEvent.company_id == company_id)

        if account_id:
            query = query.where(EngagementEvent.account_id == account_id)
        if event_type:
            query = query.where(EngagementEvent.event_type == event_type)
        if platform:
            query = query.where(EngagementEvent.platform == platform)
        if is_new_lead is not None:
            query = query.where(EngagementEvent.is_new_lead == is_new_lead)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(EngagementEvent)
            .where(EngagementEvent.company_id == company_id)
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(EngagementEvent.event_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def get_new_engagement_summary(
        self, company_id: int, account_id: int, days: int = 7
    ) -> Dict[str, object]:
        """Get summary of new engagements."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        result = await self.db.execute(
            select(EngagementEvent)
            .where(
                EngagementEvent.company_id == company_id,
                EngagementEvent.account_id == account_id,
                EngagementEvent.event_date >= start_date,
            )
        )
        events = list(result.scalars().all())

        by_type: Dict[str, int] = {}
        new_leads = 0
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            if e.is_new_lead:
                new_leads += 1

        return {
            "period_days": days,
            "total_events": len(events),
            "new_leads": new_leads,
            "events_by_type": by_type,
        }


# =============================================================================
# Reengagement Service
# =============================================================================


class ReengagementService:
    """Service for generating and managing AI-powered re-engagement recommendations.

    All outbound messages require approval before sending.
    Auto-send is disabled by default.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _generate_welcome_message(self, username: str, platform: str) -> Dict[str, str]:
        """Generate a welcome message for a new follower."""
        templates = {
            "instagram": f"Merhaba @{username}! Bizi takip ettiginiz icin tesekkurler. Yeni iceriklerimizi kacirmamak icin bildirimleri acabilirsiniz.",
            "facebook": f"Merhaba {username}! Sayfamiza hos geldiniz. Yeni urun ve kampanyalarimizdan haberdar olmak icin takipte kalin.",
            "tiktok": f"Hey @{username}! Iceriklerimizi begendiginiz icin tesekkurler. Yeni videolar icin takipte kalin!",
            "whatsapp": f"Merhaba {username}! Bize yazdiginiz icin tesekkurler. Size nasil yardimci olabiliriz?",
        }
        return {
            "subject": "Hos Geldiniz!",
            "body": templates.get(platform, f"Merhaba {username}! Bize katildiginiz icin tesekkurler."),
        }

    def _generate_campaign_suggestion(
        self, username: str, platform: str, interests: List[str]
    ) -> Dict[str, str]:
        """Generate a campaign suggestion message."""
        interest_str = ", ".join(interests[:2]) if interests else "ozel urunlerimiz"
        return {
            "subject": "Ozel Kampanya",
            "body": f"Merhaba {username}! {interest_str} ile ilgili ozel bir kampanyamiz var. Ilgilenir misiniz?",
        }

    def _generate_reengagement_message(self, username: str, platform: str) -> Dict[str, str]:
        """Generate a re-engagement message for inactive followers."""
        templates = {
            "instagram": f"Merhaba @{username}! Sizi ozledik. Yeni iceriklerimizi kacirmayin, aramiza tekrar katilin.",
            "facebook": f"Merhaba {username}! Yeni kampanyalarimiz basladi. Sizi aramizda gormek isteriz.",
            "tiktok": f"Hey @{username}! Yeni videolarimiz yayinda. Goz atmak ister misin?",
            "whatsapp": f"Merhaba {username}! Size ozel bir teklifimiz var. Ilgilenir misiniz?",
        }
        return {
            "subject": "Sizi Ozledik",
            "body": templates.get(platform, f"Merhaba {username}! Yeniden etkilesime gecmek isteriz."),
        }

    async def generate_recommendation(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        reengagement_type: str,
        target_follower_id: Optional[str] = None,
        target_username: Optional[str] = None,
        target_segment: Optional[str] = None,
        interests: Optional[List[str]] = None,
        confidence: float = 0.0,
        branch_id: Optional[int] = None,
    ) -> ReengagementRecommendation:
        """Generate a re-engagement recommendation with AI-suggested message.

        All messages are generated as suggestions only - approval required.
        """
        username = target_username or "degerli musterimiz"

        # Generate message based on type
        if reengagement_type == "welcome_new_follower":
            msg = self._generate_welcome_message(username, platform)
            expected_rate = 25.0
        elif reengagement_type == "campaign_suggestion":
            msg = self._generate_campaign_suggestion(username, platform, interests or [])
            expected_rate = 15.0
        elif reengagement_type == "reengagement_for_low":
            msg = self._generate_reengagement_message(username, platform)
            expected_rate = 10.0
        elif reengagement_type == "win_back_unfollow":
            msg = {
                "subject": "Tekrar Hos Geldiniz",
                "body": f"Merhaba {username}! Sizi tekrar aramizda gormek isteriz. Size ozel bir teklifimiz var.",
            }
            expected_rate = 8.0
        elif reengagement_type == "dm_follow_up":
            msg = {
                "subject": "Takip",
                "body": f"Merhaba {username}! Onceki konusmamiza devam etmek ister misiniz?",
            }
            expected_rate = 20.0
        elif reengagement_type == "local_branch_campaign":
            msg = {
                "subject": "Sube Ozel Kampanya",
                "body": f"Merhaba {username}! Yakin subemizde ozel bir kampanya var. Kacirmayin!",
            }
            expected_rate = 12.0
        else:
            msg = {
                "subject": "Ozel Mesaj",
                "body": f"Merhaba {username}! Size ozel bir teklifimiz var.",
            }
            expected_rate = 10.0

        rec = ReengagementRecommendation(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            reengagement_type=reengagement_type,
            target_follower_id=target_follower_id,
            target_follower_username=target_username,
            target_segment=target_segment,
            ai_suggested_message=msg["body"],
            ai_suggested_subject=msg["subject"],
            confidence_score=confidence or 0.65,
            expected_response_rate=expected_rate,
            approval_status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.db.add(rec)
        await self.db.commit()
        await self.db.refresh(rec)
        return rec

    async def request_approval(
        self, rec_id: int, company_id: int, requested_by: int
    ) -> OutreachApprovalRequest:
        """Create an approval request for a re-engagement message.

        Args:
            rec_id: Reengagement recommendation ID.
            company_id: Tenant company ID.
            requested_by: User ID requesting approval.

        Returns:
            Created OutreachApprovalRequest.
        """
        result = await self.db.execute(
            select(ReengagementRecommendation).where(
                ReengagementRecommendation.id == rec_id,
                ReengagementRecommendation.company_id == company_id,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            raise NotFoundError("Recommendation not found")

        # Update recommendation status
        rec.approval_status = "pending"
        await self.db.commit()

        # Create approval request
        approval = OutreachApprovalRequest(
            company_id=company_id,
            branch_id=rec.branch_id,
            reengagement_id=rec.id,
            platform=rec.platform,
            recipient_account_id=rec.target_follower_id,
            recipient_username=rec.target_follower_username,
            message_subject=rec.ai_suggested_subject,
            message_body=rec.ai_suggested_message,
            message_type=rec.reengagement_type,
            status="pending",
            policy_check_result="needs_review",
            requested_by=requested_by,
        )
        self.db.add(approval)
        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def review_approval(
        self,
        approval_id: int,
        company_id: int,
        reviewed_by: int,
        approved: bool,
        notes: Optional[str] = None,
    ) -> OutreachApprovalRequest:
        """Review an approval request.

        Args:
            approval_id: Approval request ID.
            company_id: Tenant company ID.
            reviewed_by: User ID reviewing.
            approved: Whether to approve or reject.
            notes: Optional review notes.

        Returns:
            Updated OutreachApprovalRequest.
        """
        result = await self.db.execute(
            select(OutreachApprovalRequest).where(
                OutreachApprovalRequest.id == approval_id,
                OutreachApprovalRequest.company_id == company_id,
            )
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise NotFoundError("Approval request not found")

        approval.reviewed_by = reviewed_by
        approval.reviewed_at = datetime.now(timezone.utc)
        approval.review_notes = notes

        if approved:
            approval.status = "approved"
            approval.policy_check_result = "compliant"

            # Update recommendation
            if approval.reengagement_id:
                rec_result = await self.db.execute(
                    select(ReengagementRecommendation).where(
                        ReengagementRecommendation.id == approval.reengagement_id
                    )
                )
                rec = rec_result.scalar_one_or_none()
                if rec:
                    rec.approval_status = "approved"
                    rec.approved_by = reviewed_by
                    rec.approved_at = datetime.now(timezone.utc)
        else:
            approval.status = "rejected"

            if approval.reengagement_id:
                rec_result = await self.db.execute(
                    select(ReengagementRecommendation).where(
                        ReengagementRecommendation.id == approval.reengagement_id
                    )
                )
                rec = rec_result.scalar_one_or_none()
                if rec:
                    rec.approval_status = "rejected"
                    rec.rejection_reason = notes

        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def send_approved_message(
        self,
        approval_id: int,
        company_id: int,
        sent_by: int,
    ) -> OutreachApprovalRequest:
        """Mark an approved message as sent.

        Note: This does NOT actually send the message - it records that the
        message was approved and is ready to be sent via the platform's API.
        Actual sending is handled by the platform-specific service.

        Args:
            approval_id: Approval request ID.
            company_id: Tenant company ID.
            sent_by: User ID sending.

        Returns:
            Updated OutreachApprovalRequest.
        """
        result = await self.db.execute(
            select(OutreachApprovalRequest).where(
                OutreachApprovalRequest.id == approval_id,
                OutreachApprovalRequest.company_id == company_id,
                OutreachApprovalRequest.status == "approved",
            )
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise NotFoundError("Approved request not found")

        approval.status = "sent"
        approval.sent_at = datetime.now(timezone.utc)
        approval.sent_by = sent_by
        approval.send_result = "queued_for_delivery"

        # Update recommendation
        if approval.reengagement_id:
            rec_result = await self.db.execute(
                select(ReengagementRecommendation).where(
                    ReengagementRecommendation.id == approval.reengagement_id
                )
            )
            rec = rec_result.scalar_one_or_none()
            if rec:
                rec.approval_status = "sent"
                rec.sent_at = datetime.now(timezone.utc)
                rec.sent_result = "queued_for_delivery"

        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def list_recommendations(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List re-engagement recommendations with pagination."""
        query = select(ReengagementRecommendation).where(
            ReengagementRecommendation.company_id == company_id
        )

        if account_id:
            query = query.where(ReengagementRecommendation.account_id == account_id)
        if status:
            query = query.where(ReengagementRecommendation.approval_status == status)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(ReengagementRecommendation)
            .where(ReengagementRecommendation.company_id == company_id)
        )
        total = count_result.scalar() or 0

        # Pending count
        pending_result = await self.db.execute(
            select(func.count())
            .select_from(ReengagementRecommendation)
            .where(
                ReengagementRecommendation.company_id == company_id,
                ReengagementRecommendation.approval_status == "pending",
            )
        )
        pending = pending_result.scalar() or 0

        query = query.order_by(desc(ReengagementRecommendation.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {"total": total, "pending": pending, "page": page, "page_size": page_size, "items": items}

    async def list_approvals(
        self,
        company_id: int,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List outreach approval requests with pagination."""
        query = select(OutreachApprovalRequest).where(
            OutreachApprovalRequest.company_id == company_id
        )

        if status:
            query = query.where(OutreachApprovalRequest.status == status)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(OutreachApprovalRequest)
            .where(OutreachApprovalRequest.company_id == company_id)
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(OutreachApprovalRequest.requested_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {"total": total, "page": page, "page_size": page_size, "items": items}


# =============================================================================
# Follower Value Service
# =============================================================================


class FollowerValueService:
    """Service for scoring and classifying follower value tiers.

    Classifies followers into tiers based on engagement patterns:
    high_value, medium_value, low_value, ghost, new.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _calculate_value_score(
        self,
        engagement_frequency: float,
        days_since_engagement: int,
        total_engagements: int,
        engagement_quality: float,
    ) -> Tuple[float, str, bool, bool]:
        """Calculate follower value score and classification.

        Returns:
            Tuple of (value_score, tier, is_inactive, is_ghost).
        """
        # Recency score (0-40)
        if days_since_engagement <= 3:
            recency_score = 40
        elif days_since_engagement <= 7:
            recency_score = 30
        elif days_since_engagement <= 14:
            recency_score = 20
        elif days_since_engagement <= 30:
            recency_score = 10
        else:
            recency_score = 0

        # Frequency score (0-30)
        freq_score = min(30, engagement_frequency * 3)

        # Quality score (0-20)
        quality_score = min(20, engagement_quality * 20)

        # Volume score (0-10)
        volume_score = min(10, total_engagements / 10)

        total = recency_score + freq_score + quality_score + volume_score

        # Classify
        is_inactive = days_since_engagement > 30
        is_ghost = days_since_engagement > 60 and total_engagements < 3

        if is_ghost:
            tier = "ghost"
        elif total >= 70:
            tier = "high_value"
        elif total >= 40:
            tier = "medium_value"
        elif is_inactive:
            tier = "low_value"
        else:
            tier = "new" if total_engagements < 3 else "low_value"

        return round(total, 2), tier, is_inactive, is_ghost

    async def score_follower(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        follower_account_id: str,
        follower_username: Optional[str] = None,
        engagement_frequency: float = 0.0,
        last_engagement_at: Optional[datetime] = None,
        total_engagements: int = 0,
        engagement_quality_avg: float = 0.0,
        days_since_engagement: int = 0,
        branch_id: Optional[int] = None,
    ) -> FollowerValueScore:
        """Score and classify a follower."""
        value_score, tier, is_inactive, is_ghost = self._calculate_value_score(
            engagement_frequency=engagement_frequency,
            days_since_engagement=days_since_engagement,
            total_engagements=total_engagements,
            engagement_quality=engagement_quality_avg,
        )

        confidence = min(1.0, (total_engagements / 10) + 0.3)

        score = FollowerValueScore(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            platform=platform,
            follower_account_id=follower_account_id,
            follower_username=follower_username,
            value_tier=tier,
            engagement_frequency=engagement_frequency,
            last_engagement_at=last_engagement_at,
            total_engagements=total_engagements,
            engagement_quality_avg=engagement_quality_avg,
            days_since_engagement=days_since_engagement,
            value_score=value_score,
            confidence_score=confidence,
            is_inactive=is_inactive,
            is_ghost=is_ghost,
            scored_at=datetime.now(timezone.utc),
        )
        self.db.add(score)
        await self.db.commit()
        await self.db.refresh(score)
        return score

    async def get_value_summary(
        self, company_id: int, account_id: int
    ) -> Dict[str, object]:
        """Get follower value summary for an account."""
        result = await self.db.execute(
            select(FollowerValueScore)
            .where(
                FollowerValueScore.company_id == company_id,
                FollowerValueScore.account_id == account_id,
            )
            .order_by(desc(FollowerValueScore.scored_at))
        )
        scores = list(result.scalars().all())

        tier_counts: Dict[str, int] = {}
        inactive_count = 0
        ghost_count = 0
        total_score = 0.0

        for s in scores:
            tier_counts[s.value_tier] = tier_counts.get(s.value_tier, 0) + 1
            if s.is_inactive:
                inactive_count += 1
            if s.is_ghost:
                ghost_count += 1
            total_score += float(s.value_score)

        avg_score = round(total_score / len(scores), 2) if scores else 0.0

        return {
            "total_scored": len(scores),
            "tier_distribution": tier_counts,
            "inactive_count": inactive_count,
            "ghost_count": ghost_count,
            "high_value_count": tier_counts.get("high_value", 0),
            "average_value_score": avg_score,
        }

    async def list_value_scores(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        tier: Optional[str] = None,
        is_inactive: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, object]:
        """List follower value scores with pagination."""
        query = select(FollowerValueScore).where(
            FollowerValueScore.company_id == company_id
        )

        if account_id:
            query = query.where(FollowerValueScore.account_id == account_id)
        if tier:
            query = query.where(FollowerValueScore.value_tier == tier)
        if is_inactive is not None:
            query = query.where(FollowerValueScore.is_inactive == is_inactive)

        count_result = await self.db.execute(
            select(func.count())
            .select_from(FollowerValueScore)
            .where(FollowerValueScore.company_id == company_id)
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(FollowerValueScore.value_score))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return {"total": total, "page": page, "page_size": page_size, "items": items}


# =============================================================================
# Ghost / Inactive Follower Detection Service
# =============================================================================


class GhostFollowerDetectionService:
    """Service for detecting ghost, inactive, and dormant followers."""

    GHOST_THRESHOLD_DAYS: Final[int] = 180
    DORMANT_THRESHOLD_DAYS: Final[int] = 90
    INACTIVE_THRESHOLD_DAYS: Final[int] = 30

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def detect_ghost_followers(
        self, company_id: int, account_id: int,
        platform: Optional[str] = None,
        inactivity_threshold_days: int = 90,
        min_confidence: float = 0.5,
        branch_id: Optional[int] = None,
    ) -> Dict[str, object]:
        from sqlalchemy import select, func, desc

        snapshot_query = (
            select(FollowerSnapshot)
            .where(FollowerSnapshot.company_id == company_id)
            .where(FollowerSnapshot.account_id == account_id)
            .order_by(desc(FollowerSnapshot.snapshot_date))
            .limit(1)
        )
        snapshot_result = await self.db.execute(snapshot_query)
        latest_snapshot = snapshot_result.scalar_one_or_none()
        total_followers = latest_snapshot.follower_count if latest_snapshot else 0

        event_query = (
            select(EngagementEvent)
            .where(EngagementEvent.company_id == company_id)
            .where(EngagementEvent.account_id == account_id)
            .order_by(desc(EngagementEvent.created_at))
            .limit(1000)
        )
        event_result = await self.db.execute(event_query)
        events = list(event_result.scalars().all())

        bot_query = (
            select(BotPattern)
            .where(BotPattern.company_id == company_id)
            .where(BotPattern.account_id == account_id)
        )
        bot_result = await self.db.execute(bot_query)
        bot_patterns = list(bot_result.scalars().all())

        high_risk_bots = [b for b in bot_patterns
                         if b.risk_level in (BotRiskLevel.HIGH, BotRiskLevel.CRITICAL)]

        if total_followers > 0 and len(events) > 0:
            unique_engagers = len({e.follower_username for e in events if e.follower_username})
            engagement_ratio = unique_engagers / total_followers if total_followers > 0 else 0
            ghost_estimate = int(total_followers * (1 - engagement_ratio) * 0.35)
            dormant_estimate = int(total_followers * (1 - engagement_ratio) * 0.40)
            inactive_estimate = int(total_followers * (1 - engagement_ratio) * 0.25)
            known_bot_count = len(bot_patterns)
            ghost_estimate = max(ghost_estimate - known_bot_count, 0)
            data_completeness = min(len(events) / max(total_followers * 0.1, 100), 1.0)
            confidence = min(0.3 + (data_completeness * 0.5) + (0.2 if known_bot_count > 0 else 0), 0.95)
        else:
            ghost_estimate = dormant_estimate = inactive_estimate = 0
            confidence = data_completeness = 0.0

        ghost_pct = (ghost_estimate / total_followers * 100) if total_followers > 0 else 0
        risk_level = "high" if ghost_pct > 20 else "medium" if ghost_pct > 10 else "low"

        recommendations = []
        if confidence < 0.3:
            recommendations.append("Limited engagement data. Connect social media API for more accurate detection.")
        if ghost_estimate > 100:
            recommendations.append(f"Consider re-engagement campaign for dormant followers (~{dormant_estimate} accounts).")
        if len(high_risk_bots) > 0:
            recommendations.append(f"{len(high_risk_bots)} high-risk suspected bot accounts detected.")
        if not recommendations:
            recommendations.append("No significant issues detected. Continue monitoring.")

        return {
            "total_followers": total_followers,
            "inactive_count": inactive_estimate, "ghost_count": ghost_estimate,
            "dormant_count": dormant_estimate,
            "inactive_percentage": round((inactive_estimate / total_followers * 100), 2) if total_followers else 0,
            "ghost_percentage": round(ghost_pct, 2),
            "dormant_percentage": round((dormant_estimate / total_followers * 100), 2) if total_followers else 0,
            "confidence_score": round(confidence, 2),
            "risk_assessment": risk_level,
            "breakdown": {
                "known_bot_patterns": len(bot_patterns),
                "high_risk_suspected": len(high_risk_bots),
                "data_completeness": round(data_completeness, 2),
                "engaged_accounts": len({e.follower_username for e in events if e.follower_username}) if events else 0,
            },
            "recommendations": recommendations,
            "detected_at": datetime.now(timezone.utc),
        }


# =============================================================================
# Export Service
# =============================================================================


class ExportService:
    """Service for generating follower analysis export reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_report(self, company_id: int, account_id: int,
        report_type: str, format: str, date_range_days: int = 30,
        platform: Optional[str] = None, branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import select, desc
        report_data: Dict[str, Any] = {"meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "company_id": company_id, "account_id": account_id,
            "platform": platform or "all", "date_range_days": date_range_days,
            "report_type": report_type, "data_quality": "partial",
            "disclaimer": "This report is based on available data. Connect social media APIs for more comprehensive analysis.",
        }}

        snapshot_query = (
            select(FollowerSnapshot).where(FollowerSnapshot.company_id == company_id)
            .where(FollowerSnapshot.account_id == account_id)
            .order_by(desc(FollowerSnapshot.snapshot_date)).limit(1)
        )
        snapshot_result = await self.db.execute(snapshot_query)
        latest_snapshot = snapshot_result.scalar_one_or_none()

        if latest_snapshot:
            report_data["follower_summary"] = {
                "total_followers": latest_snapshot.follower_count,
                "following_count": latest_snapshot.following_count,
                "post_count": latest_snapshot.post_count,
                "last_updated": latest_snapshot.snapshot_date.isoformat() if latest_snapshot.snapshot_date else None,
            }
            report_data["meta"]["data_quality"] = "available"
        else:
            report_data["follower_summary"] = {"total_followers": 0, "following_count": 0, "post_count": 0, "last_updated": None}
            report_data["meta"]["data_quality"] = "no_data"

        bot_query = (
            select(BotPattern).where(BotPattern.company_id == company_id)
            .where(BotPattern.account_id == account_id).order_by(desc(BotPattern.bot_score))
        )
        bot_result = await self.db.execute(bot_query)
        bot_patterns = list(bot_result.scalars().all())
        report_data["bot_analysis"] = {"total_flagged": len(bot_patterns), "by_risk_level": {}, "high_risk_accounts": []}
        for bp in bot_patterns:
            level = bp.risk_level.value if hasattr(bp.risk_level, 'value') else str(bp.risk_level)
            report_data["bot_analysis"]["by_risk_level"][level] = report_data["bot_analysis"]["by_risk_level"].get(level, 0) + 1
            if level in ("high", "critical"):
                report_data["bot_analysis"]["high_risk_accounts"].append({
                    "username": bp.detected_username, "score": float(bp.bot_score) if bp.bot_score else 0,
                    "risk_level": level, "detected_at": bp.detected_at.isoformat() if bp.detected_at else None,
                })

        quality_query = (
            select(EngagementQuality).where(EngagementQuality.company_id == company_id)
            .where(EngagementQuality.account_id == account_id).order_by(desc(EngagementQuality.analysis_date)).limit(1)
        )
        quality_result = await self.db.execute(quality_query)
        latest_quality = quality_result.scalar_one_or_none()
        report_data["engagement_quality"] = {
            "quality_score": float(latest_quality.quality_score) if latest_quality and latest_quality.quality_score else 0,
            "engagement_rate": float(latest_quality.engagement_rate) if latest_quality and latest_quality.engagement_rate else 0,
            "reach_count": latest_quality.reach_count if latest_quality else 0,
            "impression_count": latest_quality.impression_count if latest_quality else 0,
        } if latest_quality else None

        health_query = (
            select(FollowerHealth).where(FollowerHealth.company_id == company_id)
            .where(FollowerHealth.account_id == account_id).order_by(desc(FollowerHealth.analysis_date)).limit(1)
        )
        health_result = await self.db.execute(health_query)
        latest_health = health_result.scalar_one_or_none()
        report_data["health_score"] = {
            "overall_score": float(latest_health.overall_score) if latest_health and latest_health.overall_score else 0,
            "health_status": str(latest_health.health_status) if latest_health else None,
        } if latest_health else None

        total_followers = report_data["follower_summary"]["total_followers"]
        bot_count = report_data["bot_analysis"]["total_flagged"]
        bot_pct = (bot_count / total_followers * 100) if total_followers > 0 else 0
        overall_risk = "critical" if bot_pct > 15 else "high" if bot_pct > 8 else "medium" if bot_pct > 3 else "low"
        quality_score = max(0, 100 - (bot_pct * 3))
        if latest_health and latest_health.overall_score:
            quality_score = (quality_score + float(latest_health.overall_score)) / 2

        report_data["overall"] = {
            "quality_score": round(quality_score, 1), "risk_level": overall_risk,
            "bot_suspected_percentage": round(bot_pct, 2),
            "genuine_estimate": max(0, total_followers - bot_count),
            "confidence_score": round(0.5 + (0.3 if len(bot_patterns) > 0 else 0) + (0.2 if latest_health else 0), 2),
            "recommendations": self._generate_recommendations(total_followers, bot_count, bot_pct, latest_health, latest_quality),
        }

        if format == "json":
            return {"format": "json", "data": report_data}
        elif format == "csv":
            return {"format": "csv", "data": report_data, "note": "CSV conversion client-side or with pandas"}
        elif format == "xlsx":
            return {"format": "xlsx", "data": report_data, "note": "Install: pip install openpyxl"}
        elif format == "pdf":
            return {"format": "pdf", "data": report_data, "note": "Install: pip install reportlab"}
        return {"format": format, "data": report_data}

    def _generate_recommendations(self, total_followers: int, bot_count: int,
        bot_pct: float, health: Optional[FollowerHealth],
        quality: Optional[EngagementQuality],
    ) -> List[str]:
        recommendations = []
        if total_followers == 0:
            recommendations.append("No follower data available. Connect your social media account.")
            return recommendations
        if bot_pct > 10:
            recommendations.append(f"High suspected bot rate ({bot_pct:.1f}%). Review flagged accounts.")
        elif bot_pct > 5:
            recommendations.append(f"Moderate bot activity ({bot_pct:.1f}%). Monitor patterns.")
        if health and health.overall_score and float(health.overall_score) < 50:
            recommendations.append(f"Health score low ({float(health.overall_score):.0f}/100). Improve audience quality.")
        if quality and quality.engagement_rate and float(quality.engagement_rate) < 1.0:
            recommendations.append("Engagement rate below 1%. Focus on content quality.")
        if not recommendations:
            recommendations.append("Follower quality appears healthy. Continue monitoring.")
        recommendations.append("Analysis based on available data. Connect APIs for deeper insights.")
        return recommendations

    async def get_quality_report(self, company_id: int, account_id: int,
        platform: Optional[str] = None,
    ) -> Dict[str, Any]:
        report = await self.generate_report(company_id, account_id, "audience_quality", "json", platform=platform)
        return report.get("data", {}).get("overall", {})
