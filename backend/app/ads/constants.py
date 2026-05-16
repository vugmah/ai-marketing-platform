"""Constants for the Ads Intelligence module.

Includes API base URLs, endpoints, industry benchmarks,
fatigue detection thresholds, and default configuration values.
"""

import enum
from datetime import timedelta
from typing import Dict


# =============================================================================
# Platform Types
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
# Google Ads API Configuration
# =============================================================================


class GoogleAdsConfig:
    """Google Ads API configuration."""

    BASE_URL = "https://googleads.googleapis.com/v13"
    AUTH_URL = "https://oauth2.googleapis.com/token"
    OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"

    # GAQL Endpoints
    CUSTOMER_CLIENTS_ENDPOINT = "/customers/{customer_id}/googleAds:searchStream"
    CAMPAIGNS_ENDPOINT = "/customers/{customer_id}/googleAds:searchStream"
    AD_GROUPS_ENDPOINT = "/customers/{customer_id}/googleAds:searchStream"
    AD_GROUP_ADS_ENDPOINT = "/customers/{customer_id}/googleAds:searchStream"

    # Resource types for GAQL
    RESOURCE_CAMPAIGN = "campaign"
    RESOURCE_AD_GROUP = "ad_group"
    RESOURCE_AD_GROUP_AD = "ad_group_ad"
    RESOURCE_AD_GROUP_CRITERION = "ad_group_criterion"
    RESOURCE_CUSTOMER = "customer"

    # Token refresh settings
    TOKEN_REFRESH_BUFFER_SECONDS = 300  # Refresh 5 min before expiry
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 2.0

    # Default GAQL queries
    CAMPAIGNS_QUERY = """
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.start_date,
            campaign.end_date,
            campaign_budget.amount_micros,
            campaign.target_cpa.target_cpa_micros,
            campaign.target_roas.target_roas,
            campaign.bidding_strategy_type,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_micros,
            metrics.ctr,
            metrics.average_cpc,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING LAST_30_DAYS
    """

    AD_GROUPS_QUERY = """
        SELECT
            ad_group.id,
            ad_group.name,
            ad_group.status,
            ad_group.cpc_bid_micros,
            ad_group.campaign,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_micros,
            metrics.ctr
        FROM ad_group
        WHERE segments.date DURING LAST_30_DAYS
    """

    ADS_QUERY = """
        SELECT
            ad_group_ad.ad.id,
            ad_group_ad.status,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group_ad.ad.final_urls,
            ad_group_ad.ad.type,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_micros,
            metrics.ctr
        FROM ad_group_ad
        WHERE segments.date DURING LAST_30_DAYS
    """

    KEYWORDS_QUERY = """
        SELECT
            ad_group_criterion.criterion_id,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.status,
            ad_group_criterion.effective_cpc_bid_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc,
            metrics.quality_score
        FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD'
        AND segments.date DURING LAST_30_DAYS
    """


# =============================================================================
# Meta Marketing API Configuration
# =============================================================================


class MetaAdsConfig:
    """Meta Marketing API configuration."""

    BASE_URL = "https://graph.facebook.com/v18.0"
    AUTH_URL = "https://graph.facebook.com/v18.0/oauth/access_token"

    # Endpoints
    ACCOUNTS_ENDPOINT = "/me/adaccounts"
    CAMPAIGNS_ENDPOINT = "/{account_id}/campaigns"
    ADSETS_ENDPOINT = "/{campaign_id}/adsets"
    ADS_ENDPOINT = "/{adset_id}/ads"
    INSIGHTS_ENDPOINT = "/{object_id}/insights"
    CUSTOM_AUDIENCES_ENDPOINT = "/{account_id}/customaudiences"
    LOOKALIKE_AUDIENCES_ENDPOINT = "/{audience_id}/lookalikes"
    CREATIVE_ENDPOINT = "/{creative_id}"

    # Fields for API requests
    CAMPAIGN_FIELDS = [
        "id",
        "name",
        "objective",
        "status",
        "daily_budget",
        "lifetime_budget",
        "bid_strategy",
        "pacing_type",
        "start_time",
        "stop_time",
        "created_time",
        "updated_time",
        "special_ad_categories",
    ]

    ADSET_FIELDS = [
        "id",
        "name",
        "status",
        "daily_budget",
        "lifetime_budget",
        "bid_amount",
        "bid_strategy",
        "targeting",
        "start_time",
        "end_time",
        "created_time",
        "updated_time",
    ]

    AD_FIELDS = [
        "id",
        "name",
        "status",
        "creative",
        "adset_id",
        "campaign_id",
        "created_time",
        "updated_time",
    ]

    INSIGHT_FIELDS = [
        "impressions",
        "clicks",
        "conversions",
        "spend",
        "ctr",
        "cpc",
        "cost_per_conversion",
        "purchase_roas",
        "conversion_values",
        "quality_score",
        "reach",
        "frequency",
    ]

    CREATIVE_FIELDS = [
        "id",
        "name",
        "object_type",
        "asset_spec",
        "thumbnail_url",
        "object_story_spec",
    ]

    # Token refresh settings
    TOKEN_REFRESH_BUFFER_SECONDS = 300
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 2.0

    # Insight breakdowns
    BREAKDOWN_DAILY = ["day"]
    BREAKDOWN_CAMPAIGN = ["campaign_id"]
    BREAKDOWN_ADSET = ["adset_id"]

    # Date presets
    DATE_PRESET_TODAY = "today"
    DATE_PRESET_YESTERDAY = "yesterday"
    DATE_PRESET_LAST_7D = "last_7d"
    DATE_PRESET_LAST_30D = "last_30d"
    DATE_PRESET_THIS_MONTH = "this_month"
    DATE_PRESET_LAST_MONTH = "last_month"
    DATE_PRESET_THIS_YEAR = "this_year"
    DATE_PRESET_LIFETIME = "lifetime"


# =============================================================================
# Industry Benchmarks
# =============================================================================


# Industry benchmark data: {industry: {metric: value}}
# CTR = click-through rate (%), CPC = cost per click ($), CPA = cost per acquisition ($)
INDUSTRY_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "restaurants": {
        "ctr": 1.25,
        "cpc": 1.25,
        "cpa": 18.50,
        "cvr": 3.2,
        "roas": 4.5,
    },
    "retail": {
        "ctr": 1.55,
        "cpc": 0.95,
        "cpa": 22.00,
        "cvr": 2.8,
        "roas": 3.8,
    },
    "ecommerce": {
        "ctr": 1.65,
        "cpc": 0.88,
        "cpa": 28.50,
        "cvr": 2.35,
        "roas": 4.2,
    },
    "healthcare": {
        "ctr": 1.10,
        "cpc": 2.75,
        "cpa": 55.00,
        "cvr": 2.1,
        "roas": 2.5,
    },
    "real_estate": {
        "ctr": 0.95,
        "cpc": 1.35,
        "cpa": 65.00,
        "cvr": 1.8,
        "roas": 3.0,
    },
    "finance": {
        "ctr": 0.85,
        "cpc": 3.20,
        "cpa": 85.00,
        "cvr": 1.5,
        "roas": 2.2,
    },
    "education": {
        "ctr": 1.15,
        "cpc": 2.10,
        "cpa": 42.00,
        "cvr": 2.5,
        "roas": 2.8,
    },
    "technology": {
        "ctr": 1.45,
        "cpc": 1.85,
        "cpa": 48.00,
        "cvr": 2.2,
        "roas": 3.5,
    },
    "travel": {
        "ctr": 1.20,
        "cpc": 1.10,
        "cpa": 35.00,
        "cvr": 1.9,
        "roas": 3.2,
    },
    "automotive": {
        "ctr": 1.05,
        "cpc": 1.55,
        "cpa": 52.00,
        "cvr": 1.6,
        "roas": 2.8,
    },
    "franchise": {
        "ctr": 1.15,
        "cpc": 1.40,
        "cpa": 32.00,
        "cvr": 2.6,
        "roas": 3.6,
    },
    "general": {
        "ctr": 1.35,
        "cpc": 1.15,
        "cpa": 30.00,
        "cvr": 2.5,
        "roas": 3.5,
    },
}

# Google Ads specific benchmarks by industry
GOOGLE_ADS_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "restaurants": {
        "search_ctr": 4.85,
        "display_ctr": 0.52,
        "search_cpc": 1.40,
        "display_cpc": 0.65,
        "quality_score": 7.2,
    },
    "retail": {
        "search_ctr": 5.20,
        "display_ctr": 0.48,
        "search_cpc": 1.10,
        "display_cpc": 0.55,
        "quality_score": 7.5,
    },
    "ecommerce": {
        "search_ctr": 5.50,
        "display_ctr": 0.55,
        "search_cpc": 0.95,
        "display_cpc": 0.50,
        "quality_score": 7.8,
    },
    "healthcare": {
        "search_ctr": 3.80,
        "display_ctr": 0.42,
        "search_cpc": 3.15,
        "display_cpc": 0.90,
        "quality_score": 6.8,
    },
    "real_estate": {
        "search_ctr": 3.60,
        "display_ctr": 0.45,
        "search_cpc": 1.55,
        "display_cpc": 0.75,
        "quality_score": 7.0,
    },
    "finance": {
        "search_ctr": 3.20,
        "display_ctr": 0.38,
        "search_cpc": 3.85,
        "display_cpc": 1.05,
        "quality_score": 6.5,
    },
    "general": {
        "search_ctr": 4.50,
        "display_ctr": 0.50,
        "search_cpc": 1.25,
        "display_cpc": 0.60,
        "quality_score": 7.3,
    },
}

# Meta Ads specific benchmarks by industry
META_ADS_BENCHMARKS: Dict[str, Dict[str, float]] = {
    "restaurants": {
        "feed_ctr": 1.35,
        "stories_ctr": 0.85,
        "reels_ctr": 0.65,
        "feed_cpc": 0.55,
        "stories_cpc": 0.45,
        "reels_cpc": 0.35,
    },
    "retail": {
        "feed_ctr": 1.65,
        "stories_ctr": 1.05,
        "reels_ctr": 0.80,
        "feed_cpc": 0.48,
        "stories_cpc": 0.40,
        "reels_cpc": 0.32,
    },
    "ecommerce": {
        "feed_ctr": 1.75,
        "stories_ctr": 1.10,
        "reels_ctr": 0.85,
        "feed_cpc": 0.42,
        "stories_cpc": 0.36,
        "reels_cpc": 0.28,
    },
    "healthcare": {
        "feed_ctr": 1.05,
        "stories_ctr": 0.70,
        "reels_ctr": 0.55,
        "feed_cpc": 1.20,
        "stories_cpc": 0.95,
        "reels_cpc": 0.75,
    },
    "general": {
        "feed_ctr": 1.55,
        "stories_ctr": 0.95,
        "reels_ctr": 0.75,
        "feed_cpc": 0.48,
        "stories_cpc": 0.40,
        "reels_cpc": 0.32,
    },
}


# =============================================================================
# Fatigue Detection Configuration
# =============================================================================


class FatigueConfig:
    """Configuration for creative fatigue detection."""

    # Minimum impressions before fatigue analysis
    MIN_IMPRESSIONS = 5000

    # Minimum days of data before analysis
    MIN_DAYS = 7

    # CTR drop thresholds
    CTR_DROP_MILD = 0.10  # 10% drop = mild fatigue
    CTR_DROP_MODERATE = 0.20  # 20% drop = moderate fatigue
    CTR_DROP_SEVERE = 0.35  # 35% drop = severe fatigue

    # Frequency thresholds (impressions per unique user)
    FREQ_MILD = 3.0
    FREQ_MODERATE = 5.0
    FREQ_SEVERE = 8.0

    # Score thresholds
    SCORE_FRESH = 70  # Above this: fresh
    SCORE_MILD_FATIGUE = 50  # 50-70: mild fatigue
    SCORE_MODERATE_FATIGUE = 30  # 30-50: moderate fatigue
    SCORE_SEVERE = 0  # Below 30: severe fatigue

    # Weighting for fatigue score calculation
    WEIGHT_CTR_DROP = 0.45
    WEIGHT_FREQUENCY = 0.25
    WEIGHT_AGE_DAYS = 0.15
    WEIGHT_CONVERSION_DROP = 0.15

    # Recommended refresh intervals (days) by creative type
    REFRESH_INTERVAL_IMAGE = 30
    REFRESH_INTERVAL_VIDEO = 45
    REFRESH_INTERVAL_CAROUSEL = 35
    REFRESH_INTERVAL_STORIES = 21

    # Trend analysis window (days)
    TREND_WINDOW_DAYS = 14


# =============================================================================
# Budget Recommendation Configuration
# =============================================================================


class BudgetConfig:
    """Configuration for AI-powered budget recommendations."""

    # Minimum budget amount for recommendations
    MIN_BUDGET = 10.0

    # Maximum budget multiplier
    MAX_INCREASE_MULTIPLIER = 3.0
    MAX_DECREASE_MULTIPLIER = 0.3

    # Confidence score thresholds
    HIGH_CONFIDENCE = 0.80
    MEDIUM_CONFIDENCE = 0.60
    LOW_CONFIDENCE = 0.40

    # Minimum days of performance data needed
    MIN_PERFORMANCE_DAYS = 7

    # Budget change step sizes
    STEP_SMALL = 0.10  # 10%
    STEP_MEDIUM = 0.25  # 25%
    STEP_LARGE = 0.50  # 50%

    # ROAS thresholds for budget decisions
    ROAS_INCREASE = 3.0  # ROAS above this: increase budget
    ROAS_DECREASE = 1.0  # ROAS below this: decrease budget
    ROAS_MAINTAIN_LOW = 1.5  # Range for maintaining
    ROAS_MAINTAIN_HIGH = 3.0

    # CPA thresholds
    CPA_INCREASE_MULTIPLIER = 1.5  # CPA 50% above benchmark: decrease budget
    CPA_DECREASE_MULTIPLIER = 0.6  # CPA 40% below benchmark: can increase

    # Expected improvement per confidence level
    EXPECTED_LOW = 0.05
    EXPECTED_MEDIUM = 0.15
    EXPECTED_HIGH = 0.30


# =============================================================================
# Default Date Ranges
# =============================================================================


DEFAULT_DATE_RANGE_DAYS = 30
DEFAULT_TREND_WINDOW_DAYS = 14
DEFAULT_COMPARISON_PERIOD_DAYS = 30

# Date presets
DATE_RANGE_TODAY = timedelta(days=0)
DATE_RANGE_YESTERDAY = timedelta(days=1)
DATE_RANGE_LAST_7_DAYS = timedelta(days=7)
DATE_RANGE_LAST_30_DAYS = timedelta(days=30)
DATE_RANGE_LAST_90_DAYS = timedelta(days=90)
DATE_RANGE_LAST_YEAR = timedelta(days=365)


# =============================================================================
# ROAS and CPA Scoring
# =============================================================================


class PerformanceScoring:
    """Configuration for performance scoring."""

    # ROAS scoring thresholds
    ROAS_EXCELLENT = 5.0
    ROAS_GOOD = 3.0
    ROAS_ACCEPTABLE = 1.5
    ROAS_POOR = 1.0

    # Score weights for overall performance score (0-100)
    WEIGHT_ROAS = 0.35
    WEIGHT_CPA = 0.25
    WEIGHT_CTR = 0.20
    WEIGHT_QUALITY = 0.20

    # Quality score thresholds (0-10 scale)
    QUALITY_EXCELLENT = 9
    QUALITY_GOOD = 7
    QUALITY_ACCEPTABLE = 5
    QUALITY_POOR = 3

    # CPA performance multipliers vs benchmark
    CPA_EXCELLENT_MULTIPLIER = 0.5  # 50% below benchmark
    CPA_GOOD_MULTIPLIER = 0.75  # 25% below benchmark
    CPA_ACCEPTABLE_MULTIPLIER = 1.0  # At benchmark
    CPA_POOR_MULTIPLIER = 1.5  # 50% above benchmark

    # CTR performance vs benchmark
    CTR_EXCELLENT_MULTIPLIER = 1.5
    CTR_GOOD_MULTIPLIER = 1.2
    CTR_ACCEPTABLE_MULTIPLIER = 0.8
    CTR_POOR_MULTIPLIER = 0.5


# =============================================================================
# Local Campaign Configuration
# =============================================================================


class LocalCampaignConfig:
    """Configuration for local/geo-targeted campaign recommendations."""

    # Default radius in miles for local targeting
    DEFAULT_RADIUS_MILES = 5.0

    # Radius options
    RADIUS_OPTIONS = [1.0, 3.0, 5.0, 10.0, 15.0, 25.0]

    # Franchise-specific settings
    FRANCHISE_MIN_BUDGET_PER_LOCATION = 15.0
    FRANCHISE_MAX_BUDGET_PER_LOCATION = 200.0

    # Restaurant-specific settings
    RESTAURANT_PEAK_HOURS = [11, 12, 13, 17, 18, 19, 20]
    RESTAURANT_OFF_PEAK_MULTIPLIER = 0.6

    # Daypart bid modifiers
    BID_MODIFIER_EARLY_MORNING = 0.7  # 5-9 AM
    BID_MODIFIER_MORNING = 0.9  # 9-12 PM
    BID_MODIFIER_LUNCH = 1.2  # 12-2 PM
    BID_MODIFIER_AFTERNOON = 0.85  # 2-5 PM
    BID_MODIFIER_DINNER = 1.3  # 5-9 PM
    BID_MODIFIER_EVENING = 0.75  # 9-12 AM
    BID_MODIFIER_NIGHT = 0.4  # 12-5 AM

    # Local keywords for restaurants
    RESTAURANT_KEYWORDS = [
        "near me",
        "open now",
        "delivery",
        "takeout",
        "reservation",
        "best restaurant",
        "local food",
    ]

    # Local keywords for franchises
    FRANCHISE_KEYWORDS = [
        "near me",
        "location",
        "hours",
        "open now",
        "directions",
        "local store",
    ]


# =============================================================================
# Sync Configuration
# =============================================================================


class SyncConfig:
    """Configuration for ad platform data synchronization."""

    # Sync interval in minutes
    DEFAULT_SYNC_INTERVAL_MINUTES = 60

    # Rate limiting
    REQUESTS_PER_SECOND_GOOGLE = 10
    REQUESTS_PER_SECOND_META = 200

    # Batch sizes
    GOOGLE_BATCH_SIZE = 1000
    META_BATCH_SIZE = 500

    # Maximum lookback days for sync
    MAX_SYNC_LOOKBACK_DAYS = 90

    # Retry configuration
    MAX_SYNC_RETRIES = 5
    SYNC_RETRY_BACKOFF_BASE = 2.0
    SYNC_RETRY_MAX_DELAY = 60.0

    # Cache TTL for synced data (seconds)
    CACHE_TTL_CAMPAIGNS = 1800  # 30 min
    CACHE_TTL_METRICS = 900  # 15 min
    CACHE_TTL_AUDIENCES = 3600  # 60 min
