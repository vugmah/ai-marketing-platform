"""SQLAlchemy models for the Follower Intelligence module.

All models include company_id and branch_id for multi-tenant isolation.
Models support soft-delete via ArchiveMixin from app.database.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import ArchiveMixin, Base

from .constants import (
    BotRiskLevel,
    EngagementTier,
    FollowerAlertType,
    FollowerHealthStatus,
    GenderEstimate,
)


# =============================================================================
# Follower Snapshot (Historical follower count tracking)
# =============================================================================


class FollowerSnapshot(Base):
    """Historical snapshot of follower counts for social accounts.

    Captures daily (or periodic) follower/following counts to enable
    trend analysis, growth rate calculation, and anomaly detection.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Social media platform.
        external_account_id: Platform-specific account/page ID.
        follower_count: Total followers at snapshot time.
        following_count: Total accounts being followed.
        post_count: Total posts/media count (if available).
        snapshot_date: Timestamp of the snapshot.
        raw_data: Full platform API response JSON.
        created_at: Record creation timestamp.
    """

    __tablename__ = "follower_snapshots"
    __table_args__ = (
        Index(
            "ix_follower_snapshots_account_date",
            "account_id",
            "snapshot_date",
        ),
        Index(
            "ix_follower_snapshots_company_platform",
            "company_id",
            "platform",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="follower_platform_enum", create_type=True),
        nullable=False,
    )
    external_account_id = Column(String(255), nullable=False, index=True)
    follower_count = Column(Integer, default=0, nullable=False)
    following_count = Column(Integer, default=0, nullable=True)
    post_count = Column(Integer, default=0, nullable=True)
    snapshot_date = Column(DateTime, nullable=False, index=True)
    raw_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    account = relationship("SocialAccount", back_populates="follower_snapshots")

    def __repr__(self) -> str:
        return (
            f"<FollowerSnapshot(id={self.id}, account={self.external_account_id}, "
            f"followers={self.follower_count}, date='{self.snapshot_date}')>"
        )


# =============================================================================
# Bot Pattern (Detected bot/fake account patterns)
# =============================================================================


class BotPattern(Base):
    """Detected bot or suspicious account patterns.

    Stores individual bot detection results with signal breakdown.
    Each record represents one flagged account with scoring details.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account (our account).
        platform: Social media platform.
        detected_username: Username of the suspected bot account.
        detected_account_id: Platform ID of the suspected account.
        bot_score: Probability score 0.0-1.0.
        risk_level: LOW, MEDIUM, HIGH, CRITICAL.
        signals: JSON breakdown of detection signals.
        has_profile_pic: Whether the account has a profile picture.
        post_count: Number of posts from the account.
        follower_count: Follower count of the suspected account.
        following_count: Following count of the suspected account.
        account_age_days: Estimated account age in days.
        bio_text: Bio/description text of the account.
        is_verified: Whether the account is verified.
        is_private: Whether the account is private.
        detected_at: When this pattern was detected.
        reviewed: Whether a human has reviewed this detection.
        review_result: Human reviewer decision.
        created_at: Record creation timestamp.
    """

    __tablename__ = "bot_patterns"
    __table_args__ = (
        Index("ix_bot_patterns_company_risk", "company_id", "risk_level"),
        Index("ix_bot_patterns_account", "account_id", "detected_at"),
        Index("ix_bot_patterns_score", "bot_score"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="bot_platform_enum", create_type=False),
        nullable=False,
    )
    detected_username = Column(String(255), nullable=False)
    detected_account_id = Column(String(255), nullable=False, index=True)
    bot_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    risk_level = Column(
        Enum(BotRiskLevel, name="botrisklevel", create_type=True),
        default=BotRiskLevel.LOW,
        nullable=False,
    )
    # Relationship back to SocialAccount
    account = relationship(
        "app.social.models.SocialAccount",
        back_populates="bot_patterns",
        lazy="selectin",
    )
    signals = Column(
        JSON,
        default=lambda: {
            "following_ratio": 0.0,
            "no_profile_pic": False,
            "zero_posts": False,
            "suspicious_username": False,
            "no_bio": False,
            "no_recent_activity": False,
            "private_account": False,
            "default_avatar": False,
        },
        nullable=False,
    )
    has_profile_pic = Column(Boolean, nullable=True)
    post_count = Column(Integer, default=0, nullable=True)
    follower_count = Column(Integer, default=0, nullable=True)
    following_count = Column(Integer, default=0, nullable=True)
    account_age_days = Column(Integer, nullable=True)
    bio_text = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    detected_at = Column(DateTime, nullable=False)
    reviewed = Column(Boolean, default=False, nullable=False)
    review_result = Column(
        Enum("confirmed_bot", "false_positive", "uncertain", "pending",
             name="bot_review_result", create_type=True),
        default="pending",
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<BotPattern(id={self.id}, user='{self.detected_username}', "
            f"score={self.bot_score}, risk='{self.risk_level}')>"
        )


# =============================================================================
# Suspicious Activity (Anomaly detection results)
# =============================================================================


class SuspiciousActivity(Base):
    """Detected suspicious follower activity and anomalies.

    Stores alerts for sudden spikes, drops, bot influxes, and other
    unusual follower patterns.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Social media platform.
        alert_type: Type of suspicious activity.
        severity: Severity level (low, medium, high, critical).
        description: Human-readable description of the anomaly.
        affected_followers: Estimated number of affected followers.
        baseline_value: Normal/expected value for comparison.
        actual_value: Actual observed value.
        deviation_pct: Percentage deviation from baseline.
        evidence: JSON supporting data and evidence.
        start_date: When the activity started.
        end_date: When the activity ended (if resolved).
        resolved: Whether the alert has been resolved.
        created_at: Record creation timestamp.
    """

    __tablename__ = "suspicious_activities"
    __table_args__ = (
        Index("ix_suspicious_activity_company", "company_id", "alert_type"),
        Index("ix_suspicious_activity_account", "account_id", "start_date"),
        Index("ix_suspicious_activity_severity", "severity"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="suspicious_platform_enum", create_type=False),
        nullable=False,
    )
    alert_type = Column(
        Enum(FollowerAlertType, name="followeralerttype", create_type=True),
        nullable=False,
    )
    severity = Column(
        Enum("low", "medium", "high", "critical",
             name="suspicious_severity", create_type=True),
        nullable=False,
    )
    description = Column(Text, nullable=False)
    affected_followers = Column(Integer, default=0, nullable=False)
    baseline_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    deviation_pct = Column(Numeric(10, 2), nullable=True)
    evidence = Column(JSON, default=dict, nullable=False)
    start_date = Column(DateTime, nullable=False)
    # Relationship back to SocialAccount
    account = relationship(
        "app.social.models.SocialAccount",
        back_populates="suspicious_activities",
        lazy="selectin",
    )
    end_date = Column(DateTime, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SuspiciousActivity(id={self.id}, type='{self.alert_type}', "
            f"severity='{self.severity}', affected={self.affected_followers})>"
        )


# =============================================================================
# Audience Demographics (Estimated audience breakdown)
# =============================================================================


class AudienceDemographics(Base):
    """Estimated audience demographic breakdown.

    Aggregated demographic data inferred from follower interactions,
    profile data, and engagement patterns. Updated periodically.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Social media platform.
        age_13_17_pct: Percentage of followers aged 13-17.
        age_18_24_pct: Percentage of followers aged 18-24.
        age_25_34_pct: Percentage of followers aged 25-34.
        age_35_44_pct: Percentage of followers aged 35-44.
        age_45_54_pct: Percentage of followers aged 45-54.
        age_55_64_pct: Percentage of followers aged 55-64.
        age_65_plus_pct: Percentage of followers aged 65+.
        male_pct: Percentage male followers.
        female_pct: Percentage female followers.
        unknown_gender_pct: Percentage with unknown gender.
        top_locations: JSON of top cities/countries with percentages.
        top_languages: JSON of top languages with percentages.
        interests: JSON of inferred interest categories.
        estimated_accounts: Number of accounts used for estimation.
        confidence_score: Confidence level 0.0-1.0.
        analysis_date: When demographics were last analyzed.
        raw_data: Full analysis data JSON.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "audience_demographics"
    __table_args__ = (
        Index("ix_audience_demo_account", "account_id", "analysis_date"),
        Index("ix_audience_demo_company", "company_id", "platform"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="demo_platform_enum", create_type=False),
        nullable=False,
    )
    # Age distribution (percentages, should sum to ~100)
    age_13_17_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    age_18_24_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    age_25_34_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    age_35_44_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    age_45_54_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    age_55_64_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    age_65_plus_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    # Gender distribution
    male_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    female_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    unknown_gender_pct = Column(Numeric(5, 2), default=100.0, nullable=False)
    # Location & language
    top_locations = Column(
        JSON,
        default=lambda: {"cities": [], "countries": []},
        nullable=False,
    )
    top_languages = Column(
        JSON,
        default=lambda: [],
        nullable=False,
    )
    interests = Column(
        JSON,
        default=lambda: [],
        nullable=False,
    )
    estimated_accounts = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    analysis_date = Column(DateTime, nullable=False)
    raw_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AudienceDemographics(id={self.id}, account={self.account_id}, "
            f"confidence={self.confidence_score}, date='{self.analysis_date}')>"
        )


# =============================================================================
# Engagement Quality (Per-post and aggregate engagement scoring)
# =============================================================================


class EngagementQuality(Base):
    """Engagement quality scores for posts and aggregate periods.

    Tracks like-to-comment ratios, reach efficiency, engagement rates,
    and consistency metrics.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Social media platform.
        post_id: Optional linked social post.
        period_start: Start of aggregation period.
        period_end: End of aggregation period.
        engagement_rate: Engagement rate percentage.
        like_count: Number of likes.
        comment_count: Number of comments.
        share_count: Number of shares.
        reach_count: Reach/unique impressions.
        impression_count: Total impressions.
        like_to_comment_ratio: Likes per comment.
        reach_to_follower_ratio: Reach as percentage of followers.
        consistency_score: Consistency metric (0.0-1.0).
        quality_score: Overall quality score (0.0-1.0).
        tier: Engagement tier classification.
        factors: JSON breakdown of quality factors.
        created_at: Record creation timestamp.
    """

    __tablename__ = "engagement_qualities"
    __table_args__ = (
        Index("ix_engagement_quality_account_period", "account_id", "period_start"),
        Index("ix_engagement_quality_post", "post_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="engagement_platform_enum", create_type=False),
        nullable=False,
    )
    post_id = Column(
        Integer,
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    engagement_rate = Column(Numeric(10, 4), default=0.0, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    share_count = Column(Integer, default=0, nullable=False)
    reach_count = Column(BigInteger, default=0, nullable=False)
    impression_count = Column(BigInteger, default=0, nullable=False)
    like_to_comment_ratio = Column(Numeric(10, 2), default=0.0, nullable=False)
    reach_to_follower_ratio = Column(Numeric(10, 4), default=0.0, nullable=False)
    consistency_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    quality_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    tier = Column(
        Enum(EngagementTier, name="engagementtier", create_type=True),
        default=EngagementTier.AVERAGE,
        nullable=False,
    )
    factors = Column(
        JSON,
        default=lambda: {
            "engagement_rate_factor": 0.0,
            "comment_quality_factor": 0.0,
            "reach_efficiency_factor": 0.0,
            "consistency_factor": 0.0,
            "share_ratio_factor": 0.0,
        },
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<EngagementQuality(id={self.id}, account={self.account_id}, "
            f"rate={self.engagement_rate}, tier='{self.tier}')>"
        )


# =============================================================================
# Follower Health Score (Composite health score)
# =============================================================================


class FollowerHealthScore(Base):
    """Composite follower health score (0-100) with component breakdown.

    Aggregates engagement quality, bot ratio, growth stability,
    audience diversity, and activity recency into a single score.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Social media platform.
        overall_score: Composite score 0-100.
        status: Health status classification.
        engagement_quality_score: Engagement quality sub-score 0-100.
        bot_ratio_score: Bot-free ratio sub-score 0-100.
        growth_stability_score: Growth stability sub-score 0-100.
        audience_diversity_score: Audience diversity sub-score 0-100.
        activity_recency_score: Recent activity sub-score 0-100.
        bot_pct: Percentage of followers flagged as bots.
        inactive_pct: Percentage of inactive followers.
        engagement_rate_pct: Current engagement rate.
        growth_rate_pct: Follower growth rate.
        score_date: Date of the score calculation.
        recommendations: JSON array of improvement recommendations.
        created_at: Record creation timestamp.
    """

    __tablename__ = "follower_health_scores"
    __table_args__ = (
        Index("ix_follower_health_account_date", "account_id", "score_date"),
        Index("ix_follower_health_company_status", "company_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="health_platform_enum", create_type=False),
        nullable=False,
    )
    overall_score = Column(Integer, default=0, nullable=False)
    status = Column(
        Enum(FollowerHealthStatus, name="followerhealthstatus", create_type=True),
        default=FollowerHealthStatus.MODERATE,
        nullable=False,
    )
    # Component scores (0-100 each)
    engagement_quality_score = Column(Integer, default=0, nullable=False)
    bot_ratio_score = Column(Integer, default=0, nullable=False)
    growth_stability_score = Column(Integer, default=0, nullable=False)
    audience_diversity_score = Column(Integer, default=0, nullable=False)
    activity_recency_score = Column(Integer, default=0, nullable=False)
    # Current metrics
    bot_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    inactive_pct = Column(Numeric(5, 2), default=0.0, nullable=False)
    engagement_rate_pct = Column(Numeric(10, 4), default=0.0, nullable=False)
    growth_rate_pct = Column(Numeric(10, 4), default=0.0, nullable=False)
    # Period info
    score_date = Column(DateTime, nullable=False, index=True)
    # Recommendations
    recommendations = Column(
        JSON,
        default=lambda: [],
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<FollowerHealthScore(id={self.id}, account={self.account_id}, "
            f"score={self.overall_score}, status='{self.status}')>"
        )


# =============================================================================
# Follower Insight (Per-follower analysis cache)
# =============================================================================


class FollowerInsight(Base):
    """Cached analysis data for individual followers.

    Stores processed follower data including estimated demographics,
    activity status, and engagement patterns. Updated periodically.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account (our account).
        platform: Social media platform.
        follower_username: Username of the follower.
        follower_account_id: Platform ID of the follower.
        estimated_gender: Estimated gender.
        estimated_age_range: Estimated age range string.
        estimated_location: Estimated city/country.
        account_type: Estimated account type.
        is_active: Whether the follower is recently active.
        last_activity_at: Last known activity timestamp.
        engagement_count: Number of engagements with our content.
        bot_score: Bot probability 0.0-1.0.
        is_flagged: Whether the follower is flagged.
        flag_reason: Reason for flagging.
        raw_profile: Full profile data JSON.
        analyzed_at: When this data was last analyzed.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "follower_insights"
    __table_args__ = (
        Index("ix_follower_insights_account", "account_id", "analyzed_at"),
        Index("ix_follower_insights_bot", "bot_score"),
        Index("ix_follower_insights_flagged", "is_flagged"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="insight_platform_enum", create_type=False),
        nullable=False,
    )
    follower_username = Column(String(255), nullable=False)
    follower_account_id = Column(String(255), nullable=False, index=True)
    estimated_gender = Column(
        Enum(GenderEstimate, name="genderestimate", create_type=True),
        default=GenderEstimate.UNKNOWN,
        nullable=False,
    )
    estimated_age_range = Column(String(20), nullable=True)  # e.g., "18-24"
    estimated_location = Column(String(255), nullable=True)
    account_type = Column(
        Enum("personal", "business", "creator", "brand", "unknown",
             name="follower_account_type", create_type=True),
        default="unknown",
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity_at = Column(DateTime, nullable=True)
    engagement_count = Column(Integer, default=0, nullable=False)
    bot_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(String(255), nullable=True)
    raw_profile = Column(JSON, default=dict, nullable=False)
    analyzed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<FollowerInsight(id={self.id}, user='{self.follower_username}', "
            f"active={self.is_active}, bot_score={self.bot_score})>"
        )


# =============================================================================
# AI Audience Recommendation (AI-generated target audience suggestions)
# =============================================================================


class AIAudienceRecommendation(Base):
    """AI-generated audience recommendations and target suggestions.

    Stores recommendations for content strategy, posting times,
    target demographics, and growth opportunities.

    Attributes:
        id: Primary key.
        company_id: Tenant company ID.
        branch_id: Optional branch ID.
        account_id: Linked social account.
        platform: Social media platform.
        recommendation_type: Type of recommendation.
        title: Short title of the recommendation.
        description: Detailed recommendation text.
        target_demographics: JSON of suggested target demographics.
        suggested_hashtags: JSON array of recommended hashtags.
        optimal_posting_times: JSON of recommended posting schedules.
        content_suggestions: JSON of content ideas.
        expected_impact: Expected impact score 0-100.
        confidence: AI confidence 0.0-1.0.
        implemented: Whether the recommendation was acted upon.
        implementation_result: Result notes after implementation.
        generated_at: When the recommendation was generated.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "ai_audience_recommendations"
    __table_args__ = (
        Index("ix_ai_rec_company", "company_id", "recommendation_type"),
        Index("ix_ai_rec_account", "account_id", "generated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="ai_rec_platform_enum", create_type=False),
        nullable=False,
    )
    recommendation_type = Column(
        Enum("demographics", "content", "timing", "growth", "retention", "engagement",
             name="ai_rec_type", create_type=True),
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    target_demographics = Column(
        JSON,
        default=lambda: {
            "age_ranges": [],
            "genders": [],
            "locations": [],
            "interests": [],
        },
        nullable=False,
    )
    suggested_hashtags = Column(
        JSON,
        default=lambda: [],
        nullable=False,
    )
    optimal_posting_times = Column(
        JSON,
        default=lambda: {"weekdays": {}, "weekends": {}},
        nullable=False,
    )
    content_suggestions = Column(
        JSON,
        default=lambda: [],
        nullable=False,
    )
    expected_impact = Column(Integer, default=0, nullable=False)
    confidence = Column(Numeric(4, 3), default=0.0, nullable=False)
    implemented = Column(Boolean, default=False, nullable=False)
    implementation_result = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AIAudienceRecommendation(id={self.id}, type='{self.recommendation_type}', "
            f"title='{self.title}', impact={self.expected_impact})>"
        )


# =============================================================================
# Follower Delta Event (Snapshot-based follower change detection)
# =============================================================================


class FollowerDeltaEvent(Base):
    """Detected follower changes between consecutive snapshots.

    Tracks new followers, estimated unfollows, and suspicious changes
    by comparing snapshot data. Uses confidence scores for estimations.
    All counts are estimates, not definitive counts.
    """

    __tablename__ = "follower_delta_events"
    __table_args__ = (
        Index("ix_delta_event_account_date", "account_id", "event_date"),
        Index("ix_delta_event_company_type", "company_id", "event_type"),
        Index("ix_delta_event_platform", "company_id", "platform", "event_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="delta_platform_enum", create_type=False),
        nullable=False,
    )
    event_type = Column(
        Enum("new_follower", "estimated_unfollow", "suspicious_drop",
             "recovered_follower", "ghost_follower", "high_value",
             name="delta_event_type", create_type=True),
        nullable=False,
    )
    previous_snapshot_id = Column(Integer, nullable=False, index=True)
    current_snapshot_id = Column(Integer, nullable=False, index=True)
    follower_delta = Column(Integer, nullable=False)
    estimated_new = Column(Integer, default=0, nullable=False)
    estimated_unfollow = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Numeric(4, 3), default=0.5, nullable=False)
    confidence_reason = Column(String(255), nullable=True)
    is_suspicious = Column(Boolean, default=False, nullable=False)
    event_date = Column(DateTime, nullable=False, index=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<FollowerDeltaEvent(id={self.id}, type='{self.event_type}', "
            f"delta={self.follower_delta}, confidence={self.confidence_score})>"
        )


# =============================================================================
# Engagement Event (New interaction tracking)
# =============================================================================


class EngagementEvent(Base):
    """Individual engagement events from followers.

    Tracks every new DM, comment, mention, story interaction, reel view,
    WhatsApp message, Telegram message, and campaign click.
    """

    __tablename__ = "engagement_events"
    __table_args__ = (
        Index("ix_engagement_event_account_date", "account_id", "event_date"),
        Index("ix_engagement_event_type", "company_id", "event_type", "event_date"),
        Index("ix_engagement_event_follower", "follower_account_id", "event_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps",
             name="engagement_platform_enum2", create_type=False),
        nullable=False,
    )
    event_type = Column(
        Enum("new_dm", "new_comment", "new_mention", "new_story_reply",
             "new_reel_interaction", "new_like", "new_share", "new_save",
             "new_whatsapp_message", "new_telegram_message",
             "campaign_click", "profile_visit",
             name="engagement_event_type", create_type=True),
        nullable=False,
    )
    follower_account_id = Column(String(255), nullable=True, index=True)
    follower_username = Column(String(255), nullable=True)
    post_id = Column(String(255), nullable=True)
    message_preview = Column(String(500), nullable=True)
    sentiment = Column(
        Enum("positive", "neutral", "negative", "mixed",
             name="engagement_sentiment", create_type=True),
        default="neutral",
        nullable=False,
    )
    is_new_lead = Column(Boolean, default=False, nullable=False)
    lead_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    campaign_id = Column(String(255), nullable=True)
    event_date = Column(DateTime, nullable=False, index=True)
    raw_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<EngagementEvent(id={self.id}, type='{self.event_type}', "
            f"follower='{self.follower_username}', lead={self.is_new_lead})>"
        )


# =============================================================================
# Reengagement Recommendation (AI-powered re-engagement suggestions)
# =============================================================================


class ReengagementRecommendation(Base):
    """AI-generated re-engagement recommendations.

    Suggestions for welcome messages, campaign offers, win-back attempts,
    and follow-up messages. All require approval before sending.
    """

    __tablename__ = "reengagement_recommendations"
    __table_args__ = (
        Index("ix_reengagement_account", "account_id", "created_at"),
        Index("ix_reengagement_company_type", "company_id", "reengagement_type"),
        Index("ix_reengagement_status", "approval_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram",
             name="reengagement_platform_enum", create_type=False),
        nullable=False,
    )
    reengagement_type = Column(
        Enum("welcome_new_follower", "campaign_suggestion", "reengagement_for_low",
             "win_back_unfollow", "dm_follow_up", "local_branch_campaign",
             "engagement_reward",
             name="reengagement_type_enum", create_type=True),
        nullable=False,
    )
    target_follower_id = Column(String(255), nullable=True)
    target_follower_username = Column(String(255), nullable=True)
    target_segment = Column(String(100), nullable=True)
    ai_suggested_message = Column(Text, nullable=True)
    ai_suggested_subject = Column(String(255), nullable=True)
    confidence_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    expected_response_rate = Column(Numeric(5, 2), default=0.0, nullable=False)
    approval_status = Column(
        Enum("pending", "approved", "rejected", "sent", "failed", "cancelled",
             name="reengagement_approval_status", create_type=True),
        default="pending",
        nullable=False,
    )
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    sent_result = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ReengagementRecommendation(id={self.id}, type='{self.reengagement_type}', "
            f"status='{self.approval_status}', confidence={self.confidence_score})>"
        )


# =============================================================================
# Safe Message Template (Pre-approved safe message templates)
# =============================================================================


class SafeMessageTemplate(Base):
    """Pre-approved, policy-safe message templates.

    Templates are reviewed for platform policy compliance before approval.
    Used as the foundation for AI-generated re-engagement messages.
    """

    __tablename__ = "safe_message_templates"
    __table_args__ = (
        Index("ix_safe_template_company_platform", "company_id", "platform"),
        Index("ix_safe_template_type", "template_type", "platform"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram",
             name="safe_msg_platform_enum", create_type=False),
        nullable=False,
    )
    template_type = Column(
        Enum("welcome", "reengagement", "win_back", "follow_up",
             "campaign_offer", "branch_promo", "thank_you",
             name="safe_template_type", create_type=True),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    subject_template = Column(String(500), nullable=True)
    body_template = Column(Text, nullable=False)
    variables = Column(JSON, default=list, nullable=False)
    policy_status = Column(
        Enum("compliant", "needs_review", "violation",
             name="safe_msg_policy_status", create_type=True),
        default="needs_review",
        nullable=False,
    )
    policy_review_notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    use_count = Column(Integer, default=0, nullable=False)
    avg_response_rate = Column(Numeric(5, 2), default=0.0, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SafeMessageTemplate(id={self.id}, platform='{self.platform}', "
            f"type='{self.template_type}', status='{self.policy_status}')>"
        )


# =============================================================================
# Outreach Approval Request (Safe messaging approval workflow)
# =============================================================================


class OutreachApprovalRequest(Base):
    """Approval requests for outbound messages to followers.

    Every outbound message must go through approval before sending.
    Tracks the full approval lifecycle from pending to sent/failed.
    """

    __tablename__ = "outreach_approval_requests"
    __table_args__ = (
        Index("ix_outreach_approval_company", "company_id", "status"),
        Index("ix_outreach_approval_requester", "requested_by", "created_at"),
        Index("ix_outreach_approval_platform", "platform", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reengagement_id = Column(
        Integer,
        ForeignKey("reengagement_recommendations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram",
             name="outreach_platform_enum", create_type=False),
        nullable=False,
    )
    recipient_account_id = Column(String(255), nullable=True)
    recipient_username = Column(String(255), nullable=True)
    message_subject = Column(String(500), nullable=True)
    message_body = Column(Text, nullable=False)
    message_type = Column(
        Enum("welcome", "reengagement", "win_back", "follow_up",
             "campaign_offer", "branch_promo", "thank_you",
             name="outreach_message_type", create_type=True),
        nullable=False,
    )
    status = Column(
        Enum("pending", "approved", "rejected", "sent", "failed", "cancelled",
             name="outreach_status_enum", create_type=True),
        default="pending",
        nullable=False,
    )
    policy_check_result = Column(
        Enum("compliant", "needs_review", "violation", "platform_limited",
             name="outreach_policy_result", create_type=True),
        default="needs_review",
        nullable=False,
    )
    policy_check_details = Column(Text, nullable=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime, server_default=func.now(), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(String(500), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    sent_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    send_result = Column(String(255), nullable=True)
    rate_limit_applied = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<OutreachApprovalRequest(id={self.id}, platform='{self.platform}', "
            f"status='{self.status}', policy='{self.policy_check_result}')>"
        )


# =============================================================================
# Audience Loss Estimate (Estimated unfollow/audience loss tracking)
# =============================================================================


class AudienceLossEstimate(Base):
    """Estimated audience loss based on snapshot analysis.

    Tracks unfollow estimates with confidence scores. Uses "estimated"
    language - never claims definitive unfollow counts since platform
    APIs typically don't provide individual unfollow data.
    """

    __tablename__ = "audience_loss_estimates"
    __table_args__ = (
        Index("ix_audience_loss_account_date", "account_id", "estimate_date"),
        Index("ix_audience_loss_company_type", "company_id", "loss_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram",
             name="loss_platform_enum", create_type=False),
        nullable=False,
    )
    loss_type = Column(
        Enum("estimated_unfollow", "suspicious_drop", "platform_cleanup",
             "inactive_removal", "unknown",
             name="audience_loss_type", create_type=True),
        nullable=False,
    )
    estimated_loss_count = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Numeric(4, 3), default=0.5, nullable=False)
    confidence_reason = Column(String(255), nullable=True)
    previous_follower_count = Column(Integer, default=0, nullable=False)
    current_follower_count = Column(Integer, default=0, nullable=False)
    net_change = Column(Integer, default=0, nullable=False)
    is_suspicious = Column(Boolean, default=False, nullable=False)
    triggered_alert = Column(Boolean, default=False, nullable=False)
    snapshot_ids = Column(JSON, default=list, nullable=False)
    estimate_date = Column(DateTime, nullable=False, index=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AudienceLossEstimate(id={self.id}, type='{self.loss_type}', "
            f"loss={self.estimated_loss_count}, confidence={self.confidence_score})>"
        )


# =============================================================================
# Follower Retention Metric (Retention analytics)
# =============================================================================


class FollowerRetentionMetric(Base):
    """Follower retention metrics per account/branch/platform.

    Tracks retention rates, churn estimates, and recovery metrics.
    Aggregated periodically from delta events and loss estimates.
    """

    __tablename__ = "follower_retention_metrics"
    __table_args__ = (
        Index("ix_retention_account_period", "account_id", "period_start"),
        Index("ix_retention_company_platform", "company_id", "platform", "period_start"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram",
             name="retention_platform_enum", create_type=False),
        nullable=False,
    )
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)
    period_days = Column(Integer, default=7, nullable=False)
    starting_followers = Column(Integer, default=0, nullable=False)
    ending_followers = Column(Integer, default=0, nullable=False)
    new_followers_estimated = Column(Integer, default=0, nullable=False)
    lost_followers_estimated = Column(Integer, default=0, nullable=False)
    retention_rate = Column(Numeric(5, 2), default=100.0, nullable=False)
    churn_rate = Column(Numeric(5, 2), default=0.0, nullable=False)
    growth_rate = Column(Numeric(5, 2), default=0.0, nullable=False)
    recovery_rate = Column(Numeric(5, 2), default=0.0, nullable=False)
    net_growth = Column(Integer, default=0, nullable=False)
    high_value_retained = Column(Integer, default=0, nullable=False)
    ghost_followers_removed = Column(Integer, default=0, nullable=False)
    inactive_identified = Column(Integer, default=0, nullable=False)
    engagement_quality_score = Column(Numeric(4, 3), default=0.0, nullable=False)
    branch_comparison = Column(JSON, default=dict, nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<FollowerRetentionMetric(id={self.id}, retention={self.retention_rate}%, "
            f"churn={self.churn_rate}%, growth={self.growth_rate}%)>"
        )


# =============================================================================
# Follower Value Score (Per-follower value classification)
# =============================================================================


class FollowerValueScore(Base):
    """Value score and classification for individual followers.

    Classifies followers into tiers: high_value, medium_value, low_value,
    ghost, or new. Based on engagement frequency, recency, and quality.
    """

    __tablename__ = "follower_value_scores"
    __table_args__ = (
        Index("ix_value_score_account", "account_id", "value_tier"),
        Index("ix_value_score_follower", "follower_account_id", "scored_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(
        Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram",
             name="value_platform_enum", create_type=False),
        nullable=False,
    )
    follower_account_id = Column(String(255), nullable=False, index=True)
    follower_username = Column(String(255), nullable=True)
    value_tier = Column(
        Enum("high_value", "medium_value", "low_value", "ghost", "new",
             name="follower_value_tier", create_type=True),
        nullable=False,
    )
    engagement_frequency = Column(Numeric(5, 2), default=0.0, nullable=False)
    last_engagement_at = Column(DateTime, nullable=True)
    total_engagements = Column(Integer, default=0, nullable=False)
    engagement_quality_avg = Column(Numeric(4, 3), default=0.0, nullable=False)
    days_since_engagement = Column(Integer, default=0, nullable=False)
    value_score = Column(Numeric(5, 2), default=0.0, nullable=False)
    confidence_score = Column(Numeric(4, 3), default=0.5, nullable=False)
    is_inactive = Column(Boolean, default=False, nullable=False)
    is_ghost = Column(Boolean, default=False, nullable=False)
    scored_at = Column(DateTime, nullable=False, index=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<FollowerValueScore(id={self.id}, tier='{self.value_tier}', "
            f"score={self.value_score}, inactive={self.is_inactive})>"
        )
