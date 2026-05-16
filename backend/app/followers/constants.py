"""Constants, enums, and configuration for the Follower Intelligence module.

All thresholds and scoring parameters are centralized here for easy tuning.
"""

import enum
from typing import Dict, Final, Any


# =============================================================================
# Enums
# =============================================================================


class BotRiskLevel(str, enum.Enum):
    """Risk classification for bot/suspicious accounts."""

    LOW = "low"               # Likely genuine
    MEDIUM = "medium"         # Some suspicious signals
    HIGH = "high"             # Multiple bot indicators
    CRITICAL = "critical"     # Almost certainly fake/bot


class FollowerHealthStatus(str, enum.Enum):
    """Overall health status of a follower base."""

    EXCELLENT = "excellent"   # Score 85-100
    GOOD = "good"             # Score 70-84
    MODERATE = "moderate"     # Score 50-69
    POOR = "poor"             # Score 30-49
    CRITICAL = "critical"     # Score 0-29


class EngagementTier(str, enum.Enum):
    """Engagement quality tier classification."""

    ELITE = "elite"           # Top 5% engagement
    HIGH = "high"             # Above average
    AVERAGE = "average"       # Industry standard
    LOW = "low"               # Below average
    VERY_LOW = "very_low"     # Concerning engagement


class GenderEstimate(str, enum.Enum):
    """Estimated gender for audience demographics."""

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class FollowerAlertType(str, enum.Enum):
    """Types of alerts for follower anomalies."""

    SUDDEN_SPIKE = "sudden_spike"
    SUDDEN_DROP = "sudden_drop"
    BOT_INFLUX = "bot_influx"
    LOW_ENGAGEMENT = "low_engagement"
    INACTIVE_FOLLOWERS = "inactive_followers"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ESTIMATED_UNFOLLOW_SPIKE = "estimated_unfollow_spike"
    GHOST_FOLLOWER_DETECTED = "ghost_follower_detected"
    HIGH_VALUE_FOLLOWER = "high_value_follower"
    NEW_FOLLOWER_WAVE = "new_follower_wave"


class DeltaEventType(str, enum.Enum):
    """Types of follower delta events."""

    NEW_FOLLOWER = "new_follower"
    ESTIMATED_UNFOLLOW = "estimated_unfollow"
    SUSPICIOUS_DROP = "suspicious_drop"
    RECOVERED_FOLLOWER = "recovered_follower"
    GHOST_FOLLOWER = "ghost_follower"
    HIGH_VALUE = "high_value"


class EngagementEventType(str, enum.Enum):
    """Types of engagement events from followers."""

    NEW_DM = "new_dm"
    NEW_COMMENT = "new_comment"
    NEW_MENTION = "new_mention"
    NEW_STORY_REPLY = "new_story_reply"
    NEW_REEL_INTERACTION = "new_reel_interaction"
    NEW_LIKE = "new_like"
    NEW_SHARE = "new_share"
    NEW_SAVE = "new_save"
    NEW_WHATSAPP_MESSAGE = "new_whatsapp_message"
    NEW_TELEGRAM_MESSAGE = "new_telegram_message"
    CAMPAIGN_CLICK = "campaign_click"
    PROFILE_VISIT = "profile_visit"


class ReengagementType(str, enum.Enum):
    """Types of re-engagement recommendations."""

    WELCOME_NEW_FOLLOWER = "welcome_new_follower"
    CAMPAIGN_SUGGESTION = "campaign_suggestion"
    REENGAGEMENT_FOR_LOW = "reengagement_for_low"
    WIN_BACK_UNFOLLOW = "win_back_unfollow"
    DM_FOLLOW_UP = "dm_follow_up"
    LOCAL_BRANCH_CAMPAIGN = "local_branch_campaign"
    ENGAGEMENT_REWARD = "engagement_reward"


class ApprovalStatus(str, enum.Enum):
    """Status for outreach approval workflow."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageDirection(str, enum.Enum):
    """Direction of messaging."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class SafeMessagePolicy(str, enum.Enum):
    """Platform policy compliance status."""

    COMPLIANT = "compliant"
    NEEDS_REVIEW = "needs_review"
    VIOLATION = "violation"
    PLATFORM_LIMITED = "platform_limited"


class AudienceLossType(str, enum.Enum):
    """Type of estimated audience loss."""

    ESTIMATED_UNFOLLOW = "estimated_unfollow"
    SUSPICIOUS_DROP = "suspicious_drop"
    PLATFORM_CLEANUP = "platform_cleanup"
    INACTIVE_REMOVAL = "inactive_removal"
    UNKNOWN = "unknown"


class FollowerValueTier(str, enum.Enum):
    """Value tier classification for followers."""

    HIGH_VALUE = "high_value"       # Frequent engager, high interaction quality
    MEDIUM_VALUE = "medium_value"   # Occasional engager
    LOW_VALUE = "low_value"         # Rare or no engagement
    GHOST = "ghost"                 # No activity, possibly inactive/bot
    NEW = "new"                     # Recently followed, not yet assessed


class AccountType(str, enum.Enum):
    """Estimated account type for audience analysis."""

    PERSONAL = "personal"
    BUSINESS = "business"
    CREATOR = "creator"
    BRAND = "brand"
    UNKNOWN = "unknown"


# =============================================================================
# Bot Detection Thresholds
# =============================================================================

BOT_THRESHOLDS: Final[Dict[str, float]] = {
    # Following-to-follower ratio thresholds
    "following_follower_ratio_bot": 50.0,      # >50:1 = likely bot
    "following_follower_ratio_suspicious": 20.0,  # >20:1 = suspicious
    "following_follower_ratio_low": 10.0,      # >10:1 = mildly suspicious

    # Minimum values for flagging
    "min_posts_genuine": 5,                    # <5 posts = suspicious
    "min_posts_bot": 0,                        # 0 posts = bot indicator

    # Username pattern scores
    "username_numbers_penalty": 0.15,          # Deduct per number suffix
    "username_random_penalty": 0.25,           # Deduct for random-looking username
    "username_length_bot_max": 15,             # Very long usernames
    "username_length_bot_min": 3,              # Very short usernames

    # Profile completeness
    "no_bio_penalty": 0.20,                    # No bio = penalty
    "no_profile_pic_penalty": 0.30,            # No profile picture = penalty
    "private_account_bonus": -0.10,            # Private = slightly less likely bot

    # Activity signals
    "recent_activity_days": 90,                # Days to check for recent activity
    "no_recent_activity_penalty": 0.15,        # No posts in 90 days
    "default_avatar_penalty": 0.25,            # Default platform avatar

    # Scoring thresholds
    "score_critical": 0.75,                    # >= 0.75 = critical
    "score_high": 0.55,                        # >= 0.55 = high
    "score_medium": 0.35,                      # >= 0.35 = medium
}


# =============================================================================
# Engagement Quality Thresholds
# =============================================================================

ENGAGEMENT_THRESHOLDS: Final[Dict[str, float]] = {
    # Engagement rate tiers (engagements / reach * 100)
    "elite_rate": 6.0,                         # >6% = elite
    "high_rate": 3.5,                          # >3.5% = high
    "average_rate": 1.5,                       # >1.5% = average
    "low_rate": 0.5,                           # >0.5% = low
    # Below 0.5% = very_low

    # Like-to-comment ratio thresholds
    "ideal_like_comment_min": 10.0,            # 10:1 to 50:1 is healthy
    "ideal_like_comment_max": 50.0,
    "low_comment_penalty": 0.10,               # Very few comments
    "extreme_ratio_penalty": 0.15,             # >100:1 or <3:1

    # Reach efficiency
    "reach_to_follower_healthy_min": 0.15,     # 15%+ of followers reached
    "reach_to_follower_healthy_max": 1.5,      # Up to 150% (viral)

    # Consistency (coefficient of variation)
    "cv_excellent": 0.15,                      # <15% variation = excellent
    "cv_good": 0.30,                           # <30% = good
    "cv_moderate": 0.50,                       # <50% = moderate
}


# =============================================================================
# Follower Health Score Weights (must sum to 1.0)
# =============================================================================

HEALTH_SCORE_WEIGHTS: Final[Dict[str, float]] = {
    "engagement_quality": 0.30,
    "bot_ratio": 0.25,
    "growth_stability": 0.20,
    "audience_diversity": 0.15,
    "activity_recency": 0.10,
}

# Validate weights sum to 1.0
assert abs(sum(HEALTH_SCORE_WEIGHTS.values()) - 1.0) < 0.001, (
    "HEALTH_SCORE_WEIGHTS must sum to 1.0"
)


# =============================================================================
# Suspicious Activity Detection
# =============================================================================

SUSPICIOUS_ACTIVITY_THRESHOLDS: Final[Dict[str, float]] = {
    # Sudden spike detection
    "spike_multiplier": 3.0,                   # 3x average daily growth = spike
    "spike_absolute_min": 100,                 # At least 100 new followers

    # Sudden drop detection
    "drop_multiplier": 2.5,                    # 2.5x average daily loss = drop
    "drop_absolute_min": 50,                   # At least 50 lost followers

    # Inactive follower thresholds
    "inactive_days": 180,                      # 6 months = inactive
    "highly_inactive_days": 365,               # 1 year = highly inactive
    "inactive_warning_pct": 30.0,              # 30%+ inactive = warning
    "inactive_critical_pct": 60.0,             # 60%+ inactive = critical

    # Growth stability
    "max_daily_growth_variation": 5.0,         # 5x variation from mean
    "consecutive_anomaly_days": 3,             # 3+ days of anomalies
}


# =============================================================================
# AI Audience Recommendation Defaults
# =============================================================================

AI_AUDIENCE_CONFIG: Final[Dict[str, Any]] = {
    "min_engagement_posts": 10,               # Minimum posts for analysis
    "lookback_days": 90,                      # Days of data to analyze
    "top_hashtags_count": 20,                 # Top N hashtags to consider
    "peak_hours_window": 3,                   # Hours window for peak time
    "competitor_comparison_count": 5,         # N closest competitors to compare
    "demographics_confidence_threshold": 0.6,  # Min confidence for recommendations
}


# =============================================================================
# Scoring Utility Functions
# =============================================================================


def get_bot_risk_level(score: float) -> BotRiskLevel:
    """Convert a bot score (0.0-1.0) to a risk level enum.

    Args:
        score: Bot probability score between 0.0 and 1.0.

    Returns:
        Corresponding BotRiskLevel.
    """
    if score >= BOT_THRESHOLDS["score_critical"]:
        return BotRiskLevel.CRITICAL
    if score >= BOT_THRESHOLDS["score_high"]:
        return BotRiskLevel.HIGH
    if score >= BOT_THRESHOLDS["score_medium"]:
        return BotRiskLevel.MEDIUM
    return BotRiskLevel.LOW


def get_engagement_tier(rate: float) -> EngagementTier:
    """Convert an engagement rate to a tier classification.

    Args:
        rate: Engagement rate as percentage (e.g., 3.5 = 3.5%).

    Returns:
        Corresponding EngagementTier.
    """
    if rate >= ENGAGEMENT_THRESHOLDS["elite_rate"]:
        return EngagementTier.ELITE
    if rate >= ENGAGEMENT_THRESHOLDS["high_rate"]:
        return EngagementTier.HIGH
    if rate >= ENGAGEMENT_THRESHOLDS["average_rate"]:
        return EngagementTier.AVERAGE
    if rate >= ENGAGEMENT_THRESHOLDS["low_rate"]:
        return EngagementTier.LOW
    return EngagementTier.VERY_LOW


def get_health_status(score: int) -> FollowerHealthStatus:
    """Convert a health score (0-100) to a status enum.

    Args:
        score: Integer health score from 0 to 100.

    Returns:
        Corresponding FollowerHealthStatus.
    """
    if score >= 85:
        return FollowerHealthStatus.EXCELLENT
    if score >= 70:
        return FollowerHealthStatus.GOOD
    if score >= 50:
        return FollowerHealthStatus.MODERATE
    if score >= 30:
        return FollowerHealthStatus.POOR
    return FollowerHealthStatus.CRITICAL
