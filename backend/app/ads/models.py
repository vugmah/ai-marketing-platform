"""Ads Intelligence database models.

Contains 8 tables for managing advertising data:
- ad_platforms: Connected ad platform accounts
- ad_campaigns: Advertising campaigns
- ad_adsets: Ad sets / ad groups
- ad_creatives: Creative assets
- ad_metrics: Performance metrics
- ad_audiences: Target audiences
- ad_budget_recommendations: AI budget recommendations
- ad_creative_analysis: Creative performance analysis
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


# =============================================================================
# Enum Definitions
# =============================================================================


class AdPlatform(str, enum.Enum):
    """Supported advertising platforms."""

    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"


class CampaignStatus(str, enum.Enum):
    """Campaign lifecycle statuses."""

    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"
    PENDING = "PENDING"
    DRAFT = "DRAFT"


class CampaignObjective(str, enum.Enum):
    """Advertising campaign objectives."""

    AWARENESS = "awareness"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    LEADS = "leads"
    SALES = "sales"
    APP_PROMOTION = "app_promotion"
    LOCAL_AWARENESS = "local_awareness"
    VIDEO_VIEWS = "video_views"


class BidStrategy(str, enum.Enum):
    """Available bid strategies."""

    MANUAL_CPC = "manual_cpc"
    MANUAL_CPM = "manual_cpm"
    TARGET_CPA = "target_cpa"
    TARGET_ROAS = "target_roas"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    MAXIMIZE_CONVERSION_VALUE = "maximize_conversion_value"
    LOWEST_COST = "lowest_cost"
    COST_CAP = "cost_cap"
    BID_CAP = "bid_cap"
    LOWEST_COST_WITH_BID_CAP = "lowest_cost_with_bid_cap"


class CreativeType(str, enum.Enum):
    """Types of ad creatives."""

    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    COLLECTION = "collection"
    STORIES = "stories"
    REELS = "reels"


class CallToAction(str, enum.Enum):
    """Available call-to-action options."""

    LEARN_MORE = "learn_more"
    SHOP_NOW = "shop_now"
    SIGN_UP = "sign_up"
    DOWNLOAD = "download"
    BOOK_NOW = "book_now"
    ORDER_NOW = "order_now"
    CONTACT_US = "contact_us"
    GET_OFFER = "get_offer"
    SUBSCRIBE = "subscribe"
    WATCH_MORE = "watch_more"
    APPLY_NOW = "apply_now"
    GET_QUOTE = "get_quote"


class AudienceType(str, enum.Enum):
    """Types of ad audiences."""

    CUSTOM = "custom"
    LOOKALIKE = "lookalike"
    INTEREST = "interest"
    BEHAVIOR = "behavior"
    DEMOGRAPHIC = "demographic"
    RETARGETING = "retargeting"
    ENGAGEMENT = "engagement"


class AnalysisType(str, enum.Enum):
    """Types of creative analysis."""

    FATIGUE = "fatigue"
    SCORE = "score"
    AB_TEST = "ab_test"


class PlatformStatus(str, enum.Enum):
    """Ad platform connection status."""

    ACTIVE = "active"
    EXPIRED = "expired"
    ERROR = "error"
    SYNCING = "syncing"
    DISABLED = "disabled"


# =============================================================================
# 1. Ad Platforms
# =============================================================================


class AdPlatformAccount(Base):
    """
    Connected ad platform account (Google Ads or Meta Ads).

    Stores encrypted API credentials and account metadata.
    Each record is scoped to a company and optional branch.
    """

    __tablename__ = "ad_platforms"
    __table_args__ = {
        "schema": "public",
        "comment": "Connected ad platform accounts with encrypted credentials",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant isolation
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_platforms_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_ad_platforms_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Platform details
    platform = Column(
        Enum(AdPlatform, name="adplatformenum", create_type=True),
        nullable=False,
        index=True,
    )
    account_id = Column(String(255), nullable=False, index=True)
    account_name = Column(String(255), nullable=False)

    # Encrypted credentials (AES-256-GCM)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=False)
    developer_token_encrypted = Column(Text, nullable=True)

    # Account metadata
    currency = Column(String(3), nullable=False, default="USD")
    timezone = Column(String(100), nullable=False, default="America/New_York")
    status = Column(
        Enum(PlatformStatus, name="platformstatus", create_type=True),
        default=PlatformStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    last_sync_at = Column(DateTime, nullable=True)

    # Additional settings stored as JSON
    settings = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    campaigns = relationship(
        "AdCampaign",
        back_populates="platform_account",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    audiences = relationship(
        "AdAudience",
        back_populates="platform_account",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AdPlatformAccount(id={self.id}, platform='{self.platform}', "
            f"account_id='{self.account_id}', company_id={self.company_id})>"
        )


# =============================================================================
# 2. Ad Campaigns
# =============================================================================


class AdCampaign(Base):
    """
    Advertising campaign across connected platforms.

    Links to a connected platform account and stores campaign-level
    configuration, targeting, and performance metadata.
    """

    __tablename__ = "ad_campaigns"
    __table_args__ = {
        "schema": "public",
        "comment": "Advertising campaigns from Google Ads and Meta Ads",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant isolation
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_campaigns_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_ad_campaigns_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Platform
    platform = Column(
        Enum(AdPlatform, name="adcampaignplatform", create_type=True),
        nullable=False,
        index=True,
    )
    platform_campaign_id = Column(String(255), nullable=False, index=True)

    # Campaign details
    name = Column(String(500), nullable=False)
    objective = Column(
        Enum(CampaignObjective, name="campaignobjective", create_type=True),
        nullable=True,
    )
    status = Column(
        Enum(CampaignStatus, name="campaignstatus", create_type=True),
        default=CampaignStatus.ENABLED,
        nullable=False,
        index=True,
    )

    # Budget
    budget = Column(Numeric(12, 2), nullable=False, default=0.00)
    budget_type = Column(String(20), nullable=False, default="daily")

    # Schedule
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Targeting configuration
    targeting = Column(JSON, nullable=False, default=dict)

    # Bidding
    bid_strategy = Column(
        Enum(BidStrategy, name="bidstrategy", create_type=True),
        nullable=True,
    )

    # AI features
    performance_score = Column(Numeric(5, 2), nullable=True)
    ai_optimized = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    platform_account = relationship(
        "AdPlatformAccount",
        back_populates="campaigns",
    )
    adsets = relationship(
        "AdAdset",
        back_populates="campaign",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    creatives = relationship(
        "AdCreative",
        back_populates="campaign",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    metrics = relationship(
        "AdMetric",
        back_populates="campaign",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    budget_recommendations = relationship(
        "AdBudgetRecommendation",
        back_populates="campaign",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AdCampaign(id={self.id}, name='{self.name}', "
            f"platform='{self.platform}', status='{self.status}')>"
        )


# =============================================================================
# 3. Ad Adsets
# =============================================================================


class AdAdset(Base):
    """
    Ad set (Meta) or ad group (Google Ads) entity.

    Represents a collection of ads with shared targeting, budget,
    bidding, and schedule within a campaign.
    """

    __tablename__ = "ad_adsets"
    __table_args__ = {
        "schema": "public",
        "comment": "Ad sets and ad groups from advertising platforms",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Parent campaign
    campaign_id = Column(
        Integer,
        ForeignKey(
            "public.ad_campaigns.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_adsets_campaign_id",
        ),
        nullable=False,
        index=True,
    )

    platform_adset_id = Column(String(255), nullable=False, index=True)
    name = Column(String(500), nullable=False)

    # Targeting
    targeting = Column(JSON, nullable=False, default=dict)

    # Budget and bidding
    budget = Column(Numeric(12, 2), nullable=True)
    bid_amount = Column(Numeric(10, 4), nullable=True)

    status = Column(
        Enum(CampaignStatus, name="adsetstatus", create_type=True),
        default=CampaignStatus.ENABLED,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    campaign = relationship("AdCampaign", back_populates="adsets")
    metrics = relationship(
        "AdMetric",
        back_populates="adset",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AdAdset(id={self.id}, name='{self.name}', "
            f"campaign_id={self.campaign_id})>"
        )


# =============================================================================
# 4. Ad Creatives
# =============================================================================


class AdCreative(Base):
    """
    Ad creative asset (image, video, carousel, etc.).

    Stores creative metadata, copy, media URLs, and platform-specific IDs.
    Each creative belongs to a campaign and can be used across ad sets.
    """

    __tablename__ = "ad_creatives"
    __table_args__ = {
        "schema": "public",
        "comment": "Ad creative assets with metadata and copy",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant isolation
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_creatives_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_ad_creatives_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Parent campaign
    campaign_id = Column(
        Integer,
        ForeignKey(
            "public.ad_campaigns.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_creatives_campaign_id",
        ),
        nullable=False,
        index=True,
    )

    # Creative details
    name = Column(String(500), nullable=False)
    creative_type = Column(
        Enum(CreativeType, name="creativetype", create_type=True),
        nullable=False,
    )
    headline = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    call_to_action = Column(
        Enum(CallToAction, name="creativcta", create_type=True),
        nullable=True,
    )
    media_urls = Column(JSON, nullable=False, default=list)

    # Platform reference
    platform_creative_id = Column(String(255), nullable=True, index=True)
    status = Column(
        Enum(CampaignStatus, name="creativestatus", create_type=True),
        default=CampaignStatus.ENABLED,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    campaign = relationship("AdCampaign", back_populates="creatives")
    metrics = relationship(
        "AdMetric",
        back_populates="creative",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    creative_analysis = relationship(
        "AdCreativeAnalysis",
        back_populates="creative",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AdCreative(id={self.id}, name='{self.name}', "
            f"type='{self.creative_type}')>"
        )


# =============================================================================
# 5. Ad Metrics
# =============================================================================


class AdMetric(Base):
    """
    Daily performance metrics for campaigns, ad sets, and creatives.

    Stores aggregated impression, click, conversion, cost, and derived
    metrics (CTR, CPC, CPA, ROAS) at daily granularity.
    """

    __tablename__ = "ad_metrics"
    __table_args__ = {
        "schema": "public",
        "comment": "Daily ad performance metrics",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Parent references
    campaign_id = Column(
        Integer,
        ForeignKey(
            "public.ad_campaigns.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_metrics_campaign_id",
        ),
        nullable=False,
        index=True,
    )
    adset_id = Column(
        Integer,
        ForeignKey(
            "public.ad_adsets.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_metrics_adset_id",
        ),
        nullable=True,
        index=True,
    )
    creative_id = Column(
        Integer,
        ForeignKey(
            "public.ad_creatives.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_metrics_creative_id",
        ),
        nullable=True,
        index=True,
    )

    # Date for this metric row
    date = Column(Date, nullable=False, index=True)

    # Core metrics
    impressions = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    conversions = Column(Integer, default=0, nullable=False)
    cost = Column(Numeric(12, 2), default=0.00, nullable=False)

    # Derived metrics
    ctr = Column(Numeric(8, 4), nullable=True)
    cpc = Column(Numeric(10, 4), nullable=True)
    cpa = Column(Numeric(10, 4), nullable=True)
    roas = Column(Numeric(8, 4), nullable=True)
    conversion_value = Column(Numeric(12, 2), default=0.00, nullable=False)
    quality_score = Column(Numeric(4, 2), nullable=True)

    # Platform raw data
    raw_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    campaign = relationship("AdCampaign", back_populates="metrics")
    adset = relationship("AdAdset", back_populates="metrics")
    creative = relationship("AdCreative", back_populates="metrics")

    def __repr__(self) -> str:
        return (
            f"<AdMetric(id={self.id}, campaign_id={self.campaign_id}, "
            f"date={self.date}, impressions={self.impressions})>"
        )


# =============================================================================
# 6. Ad Audiences
# =============================================================================


class AdAudience(Base):
    """
    Target audience definitions for ad campaigns.

    Stores audience configuration, size estimates, targeting specs,
    and performance scores for audience optimization.
    """

    __tablename__ = "ad_audiences"
    __table_args__ = {
        "schema": "public",
        "comment": "Ad audience definitions and targeting specs",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant isolation
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_audiences_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_ad_audiences_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Platform
    platform = Column(
        Enum(AdPlatform, name="ad_audience_platform", create_type=True),
        nullable=False,
        index=True,
    )

    # Audience details
    name = Column(String(500), nullable=False)
    audience_type = Column(
        Enum(AudienceType, name="audiencetype", create_type=True),
        nullable=False,
    )
    size_estimate = Column(Integer, nullable=True)

    # Targeting specification
    targeting_spec = Column(JSON, nullable=False, default=dict)

    # Platform reference
    platform_audience_id = Column(String(255), nullable=True, index=True)

    # Performance
    performance_score = Column(Numeric(5, 2), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    platform_account = relationship(
        "AdPlatformAccount",
        primaryjoin="and_(AdAudience.company_id == AdPlatformAccount.company_id, "
                    "AdAudience.platform == AdPlatformAccount.platform)",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AdAudience(id={self.id}, name='{self.name}', "
            f"type='{self.audience_type}', platform='{self.platform}')>"
        )


# =============================================================================
# 7. Ad Budget Recommendations
# =============================================================================


class AdBudgetRecommendation(Base):
    """
    AI-powered budget recommendation for ad campaigns.

    Stores recommended budget changes with reasoning, expected
    improvement, and application status.
    """

    __tablename__ = "ad_budget_recommendations"
    __table_args__ = {
        "schema": "public",
        "comment": "AI-powered budget recommendations for campaigns",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant isolation
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_budget_rec_company_id",
        ),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_ad_budget_rec_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Platform and campaign reference
    platform = Column(
        Enum(AdPlatform, name="adbudgetrecplatform", create_type=True),
        nullable=False,
    )
    campaign_id = Column(
        Integer,
        ForeignKey(
            "public.ad_campaigns.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_budget_rec_campaign_id",
        ),
        nullable=False,
        index=True,
    )

    # Budget data
    current_budget = Column(Numeric(12, 2), nullable=False)
    recommended_budget = Column(Numeric(12, 2), nullable=False)

    # Recommendation details
    reason = Column(Text, nullable=False)
    expected_improvement = Column(Numeric(6, 4), nullable=True)
    confidence_score = Column(Numeric(4, 3), nullable=False)

    # Application status
    applied = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    campaign = relationship("AdCampaign", back_populates="budget_recommendations")

    def __repr__(self) -> str:
        return (
            f"<AdBudgetRecommendation(id={self.id}, "
            f"current={self.current_budget}, "
            f"recommended={self.recommended_budget})>"
        )


# =============================================================================
# 8. Ad Creative Analysis
# =============================================================================


class AdCreativeAnalysis(Base):
    """
    AI-generated analysis results for ad creatives.

    Stores fatigue detection, creative scoring, and A/B test results
    along with AI insights and actionable recommendations.
    """

    __tablename__ = "ad_creative_analysis"
    __table_args__ = {
        "schema": "public",
        "comment": "AI creative analysis results",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Parent creative
    creative_id = Column(
        Integer,
        ForeignKey(
            "public.ad_creatives.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_creative_analysis_creative_id",
        ),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ad_creative_analysis_company_id",
        ),
        nullable=False,
        index=True,
    )

    # Analysis details
    analysis_type = Column(
        Enum(AnalysisType, name="analysistype", create_type=True),
        nullable=False,
        index=True,
    )
    results = Column(JSON, nullable=False, default=dict)
    ai_insights = Column(Text, nullable=True)
    recommendations = Column(JSON, nullable=False, default=list)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    creative = relationship("AdCreative", back_populates="creative_analysis")

    def __repr__(self) -> str:
        return (
            f"<AdCreativeAnalysis(id={self.id}, "
            f"creative_id={self.creative_id}, "
            f"type='{self.analysis_type}')>"
        )
