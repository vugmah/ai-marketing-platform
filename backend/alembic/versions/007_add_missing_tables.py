"""Add missing tables (41 tables across 9 modules)

Revision ID: 007
Revises: 006
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all missing tables."""

    # --- ad_adsets (AdAdset) ---
    op.create_table(
        "ad_adsets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform_adset_id", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("targeting", sa.JSON(), nullable=False),
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("bid_amount", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, index=True, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_audiences (AdAudience) ---
    op.create_table(
        "ad_audiences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("platform", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("audience_type", sa.String(50), nullable=False),
        sa.Column("size_estimate", sa.Integer(), nullable=True),
        sa.Column("targeting_spec", sa.JSON(), nullable=False),
        sa.Column("platform_audience_id", sa.String(255), nullable=True, index=True),
        sa.Column("performance_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_budget_recommendations (AdBudgetRecommendation) ---
    op.create_table(
        "ad_budget_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False, index=True),
        sa.Column("current_budget", sa.Numeric(12, 2), nullable=False),
        sa.Column("recommended_budget", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_improvement", sa.Numeric(6, 4), nullable=True),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_campaigns (AdCampaign) ---
    op.create_table(
        "ad_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("platform", sa.String(50), nullable=False, index=True),
        sa.Column("platform_campaign_id", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("objective", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, index=True, server_default=sa.text("'active'")),
        sa.Column("budget", sa.Numeric(12, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("budget_type", sa.String(20), nullable=False, server_default=sa.text("'daily'")),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("targeting", sa.JSON(), nullable=False),
        sa.Column("bid_strategy", sa.String(50), nullable=True),
        sa.Column("performance_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_optimized", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_creative_analysis (AdCreativeAnalysis) ---
    op.create_table(
        "ad_creative_analysis",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("creative_id", sa.Integer(), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("analysis_type", sa.String(50), nullable=False, index=True),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("ai_insights", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_creatives (AdCreative) ---
    op.create_table(
        "ad_creatives",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("creative_type", sa.String(50), nullable=False),
        sa.Column("headline", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("call_to_action", sa.String(50), nullable=True),
        sa.Column("media_urls", sa.JSON(), nullable=False),
        sa.Column("platform_creative_id", sa.String(255), nullable=True, index=True),
        sa.Column("status", sa.String(50), nullable=False, index=True, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_metrics (AdMetric) ---
    op.create_table(
        "ad_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False, index=True),
        sa.Column("adset_id", sa.Integer(), nullable=True, index=True),
        sa.Column("creative_id", sa.Integer(), nullable=True, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("conversions", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("ctr", sa.Numeric(8, 4), nullable=True),
        sa.Column("cpc", sa.Numeric(10, 4), nullable=True),
        sa.Column("cpa", sa.Numeric(10, 4), nullable=True),
        sa.Column("roas", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_value", sa.Numeric(12, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("quality_score", sa.Numeric(4, 2), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ad_platforms (AdPlatformAccount) ---
    op.create_table(
        "ad_platforms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("platform", sa.String(50), nullable=False, index=True),
        sa.Column("account_id", sa.String(255), nullable=False, index=True),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("developer_token_encrypted", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("timezone", sa.String(100), nullable=False, server_default=sa.text("'America/New_York'")),
        sa.Column("status", sa.String(50), nullable=False, index=True, server_default=sa.text("'active'")),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- ai_audience_recommendations (AIAudienceRecommendation) ---
    op.create_table(
        "ai_audience_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("recommendation_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_demographics", sa.JSON(), nullable=False),
        sa.Column("suggested_hashtags", sa.JSON(), nullable=False),
        sa.Column("optimal_posting_times", sa.JSON(), nullable=True),
        sa.Column("content_suggestions", sa.JSON(), nullable=False),
        sa.Column("expected_impact", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("implemented", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("implementation_result", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_ai_rec_company", "ai_audience_recommendations", ["company_id", "recommendation_type"])
    op.create_index("ix_ai_rec_account", "ai_audience_recommendations", ["account_id", "generated_at"])

    # --- ai_reply_audit_logs (AIReplyAuditLog) ---
    op.create_table(
        "ai_reply_audit_logs",
        schema='public',
    )

    # --- analytics_snapshots (AnalyticsSnapshot) ---
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("report_type", sa.String(50), nullable=False, index=True, comment='Type of report (overview, conversions, campaigns, branches_kpi, erp, ai_insights, growth)'),
        sa.Column("snapshot_date", sa.Date(), nullable=False, index=True, comment='The date this snapshot represents'),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=False, comment='Serialized aggregation result'),
        sa.Column("computation_time_ms", sa.Integer(), nullable=True, comment='Time taken to compute this snapshot in milliseconds'),
        sa.Column("record_count", sa.Integer(), nullable=True, server_default=sa.text('0'), comment='Number of source records aggregated'),
        sa.Column("is_stale", sa.Integer(), nullable=False, index=True, server_default=sa.text('0'), comment='0=fresh, 1=stale (needs refresh)'),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("uq_analytics_snapshots_company_branch_report_date", "analytics_snapshots", ["company_id", "branch_id", "report_type", "snapshot_date"], unique=True)

    # --- approval_requests (ApprovalRequest) ---
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("request_type", sa.String(50), nullable=False, index=True, comment='ai_suggestion, campaign_change, budget_change, etc.'),
        sa.Column("requested_by", sa.Integer(), nullable=True, index=True),
        sa.Column("request_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True, server_default=sa.text("'pending'"), comment='pending, approved, rejected, edited'),
        sa.Column("approved_by", sa.Integer(), nullable=True, index=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("edited_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    # --- audience_demographics (AudienceDemographics) ---
    op.create_table(
        "audience_demographics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("age_13_17_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("age_18_24_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("age_25_34_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("age_35_44_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("age_45_54_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("age_55_64_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("age_65_plus_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("male_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("female_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("unknown_gender_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('100.0')),
        sa.Column("top_locations", sa.JSON(), nullable=False),
        sa.Column("top_languages", sa.JSON(), nullable=False),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("estimated_accounts", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("analysis_date", sa.DateTime(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_audience_demo_account", "audience_demographics", ["account_id", "analysis_date"])
    op.create_index("ix_audience_demo_company", "audience_demographics", ["company_id", "platform"])

    # --- bot_patterns (BotPattern) ---
    op.create_table(
        "bot_patterns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("detected_username", sa.String(255), nullable=False),
        sa.Column("detected_account_id", sa.String(255), nullable=False, index=True),
        sa.Column("bot_score", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("risk_level", sa.String(50), nullable=False, server_default=sa.text("'low'")),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("has_profile_pic", sa.Boolean(), nullable=True),
        sa.Column("post_count", sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column("follower_count", sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column("following_count", sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column("account_age_days", sa.Integer(), nullable=True),
        sa.Column("bio_text", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("review_result", sa.String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_bot_patterns_company_risk", "bot_patterns", ["company_id", "risk_level"])
    op.create_index("ix_bot_patterns_account", "bot_patterns", ["account_id", "detected_at"])
    op.create_index("ix_bot_patterns_score", "bot_patterns", ["bot_score"])

    # --- branch_brand_identities (BranchBrandIdentity) ---
    op.create_table(
        "branch_brand_identities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("branch_id", sa.Integer(), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("brand_name", sa.String(255), nullable=False),
        sa.Column("primary_color", sa.String(7), nullable=True, server_default=sa.text("'#6366F1'")),
        sa.Column("secondary_color", sa.String(7), nullable=True),
        sa.Column("accent_color", sa.String(7), nullable=True),
        sa.Column("brand_tone", sa.String(50), nullable=False, server_default=sa.text("'professional'")),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default=sa.text("'tr'")),
        sa.Column("font_style", sa.String(50), nullable=True),
        sa.Column("visual_style", sa.String(50), nullable=True),
        sa.Column("hashtags_always_include", sa.JSON(), nullable=True),
        sa.Column("hashtags_never_include", sa.JSON(), nullable=True),
        sa.Column("competitors_to_differentiate", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("uq_branch_brand_identity", "branch_brand_identities", ["branch_id"], unique=True)

    # --- brand_colors (BrandColor) ---
    op.create_table(
        "brand_colors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("hex_code", sa.String(7), nullable=False),
        sa.Column("color_name", sa.String(64), nullable=True),
        sa.Column("color_role", sa.String(32), nullable=True),
        sa.Column("usage_area", sa.String(128), nullable=True),
        sa.Column("usage_frequency", sa.Float(), server_default=sa.text('0.0')),
        sa.Column("confidence", sa.Float(), server_default=sa.text('0.5')),
        sa.Column("source", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("uq_brand_color", "brand_colors", ["company_id", "branch_id", "hex_code", "usage_area"], unique=True)

    # --- brand_profiles (BrandProfile) ---
    op.create_table(
        "brand_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("attribute_type", sa.String(32), nullable=False),
        sa.Column("attribute_key", sa.String(128), nullable=False),
        sa.Column("attribute_value", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default=sa.text('0.5')),
        sa.Column("source", sa.String(256), nullable=True),
        sa.Column("source_count", sa.Integer(), server_default=sa.text('1')),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_brand_company_type", "brand_profiles", ["company_id", "attribute_type"])
    op.create_index("uq_brand_attr", "brand_profiles", ["company_id", "branch_id", "attribute_type", "attribute_key"], unique=True)

    # --- campaign_insights (CampaignInsight) ---
    op.create_table(
        "campaign_insights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column("campaign_name", sa.String(256), nullable=False),
        sa.Column("campaign_type", sa.String(64), nullable=True),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("conversions", sa.Integer(), nullable=True),
        sa.Column("spend", sa.Float(), nullable=True),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("roas", sa.Float(), nullable=True),
        sa.Column("cpa", sa.Float(), nullable=True),
        sa.Column("success_factors", sa.JSON(), nullable=True),
        sa.Column("failure_factors", sa.JSON(), nullable=True),
        sa.Column("audience_insights", sa.JSON(), nullable=True),
        sa.Column("content_analysis", sa.JSON(), nullable=True),
        sa.Column("timing_insights", sa.JSON(), nullable=True),
        sa.Column("creative_analysis", sa.JSON(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("recommended_strategies", sa.JSON(), nullable=True),
        sa.Column("similar_campaigns", sa.JSON(), nullable=True),
        sa.Column("campaign_dates", sa.JSON(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_campaign_company_type", "campaign_insights", ["company_id", "campaign_type"])
    op.create_index("ix_campaign_platform", "campaign_insights", ["platform"])
    op.create_index("ix_campaign_kb", "campaign_insights", ["knowledge_base_id"])

    # --- creative_audits (CreativeAudit) ---
    op.create_table(
        "creative_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("media_id", sa.String(36), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("originality_score", sa.Integer(), nullable=True),
        sa.Column("fatigue_level", sa.String(50), nullable=False, server_default=sa.text("'none'")),
        sa.Column("fatigue_signals", sa.JSON(), nullable=True),
        sa.Column("trend_alignment", sa.JSON(), nullable=True),
        sa.Column("competitor_similarity_risk", sa.String(20), nullable=True),
        sa.Column("best_practices_checklist", sa.JSON(), nullable=True),
        sa.Column("refresh_recommendations", sa.JSON(), nullable=True),
        sa.Column("engagement_prediction", sa.JSON(), nullable=True),
        sa.Column("similar_media_ids", sa.JSON(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("uq_creative_audit_media", "creative_audits", ["media_id"], unique=True)

    # --- engagement_qualities (EngagementQuality) ---
    op.create_table(
        "engagement_qualities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True, index=True),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("engagement_rate", sa.Numeric(10, 4), nullable=False, server_default=sa.text('0.0')),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("share_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("reach_count", sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column("impression_count", sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column("like_to_comment_ratio", sa.Numeric(10, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("reach_to_follower_ratio", sa.Numeric(10, 4), nullable=False, server_default=sa.text('0.0')),
        sa.Column("consistency_score", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("quality_score", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("tier", sa.String(50), nullable=False, server_default=sa.text("'average'")),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_engagement_quality_account_period", "engagement_qualities", ["account_id", "period_start"])
    op.create_index("ix_engagement_quality_post", "engagement_qualities", ["post_id"])

    # --- escalation_rules (EscalationRule) ---
    op.create_table(
        "escalation_rules",
        schema='public',
    )

    # --- export_jobs (ExportJob) ---
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("job_type", sa.String(50), nullable=False, index=True, comment='analytics, campaign, social, erp, billing, followers, custom'),
        sa.Column("format", sa.String(10), nullable=False, index=True, comment='pdf, docx, xlsx, csv, json'),
        sa.Column("status", sa.String(20), nullable=False, index=True, server_default=sa.text("'pending'"), comment='pending, processing, completed, failed, cancelled'),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True, comment='File size in bytes'),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text('3')),
        sa.Column("report_title", sa.String(255), nullable=True),
        sa.Column("report_params", sa.JSON(), nullable=True),
        sa.Column("template_config", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        schema='public',
    )

    # --- follower_health_scores (FollowerHealthScore) ---
    op.create_table(
        "follower_health_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'moderate'")),
        sa.Column("engagement_quality_score", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("bot_ratio_score", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("growth_stability_score", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("audience_diversity_score", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("activity_recency_score", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("bot_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("inactive_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('0.0')),
        sa.Column("engagement_rate_pct", sa.Numeric(10, 4), nullable=False, server_default=sa.text('0.0')),
        sa.Column("growth_rate_pct", sa.Numeric(10, 4), nullable=False, server_default=sa.text('0.0')),
        sa.Column("score_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_follower_health_account_date", "follower_health_scores", ["account_id", "score_date"])
    op.create_index("ix_follower_health_company_status", "follower_health_scores", ["company_id", "status"])

    # --- follower_insights (FollowerInsight) ---
    op.create_table(
        "follower_insights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("follower_username", sa.String(255), nullable=False),
        sa.Column("follower_account_id", sa.String(255), nullable=False, index=True),
        sa.Column("estimated_gender", sa.String(50), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("estimated_age_range", sa.String(20), nullable=True),
        sa.Column("estimated_location", sa.String(255), nullable=True),
        sa.Column("account_type", sa.String(50), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
        sa.Column("engagement_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("bot_score", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("flag_reason", sa.String(255), nullable=True),
        sa.Column("raw_profile", sa.JSON(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_follower_insights_account", "follower_insights", ["account_id", "analyzed_at"])
    op.create_index("ix_follower_insights_bot", "follower_insights", ["bot_score"])
    op.create_index("ix_follower_insights_flagged", "follower_insights", ["is_flagged"])

    # --- follower_snapshots (FollowerSnapshot) ---
    op.create_table(
        "follower_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False, index=True),
        sa.Column("follower_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("following_count", sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column("post_count", sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column("snapshot_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_follower_snapshots_account_date", "follower_snapshots", ["account_id", "snapshot_date"])
    op.create_index("ix_follower_snapshots_company_platform", "follower_snapshots", ["company_id", "platform"])

    # --- ingestion_jobs (IngestionJob) ---
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("celery_task_id", sa.String(128), nullable=True, index=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("source_info", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("progress_percent", sa.Integer(), server_default=sa.text('0')),
        sa.Column("logs", sa.JSON(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_job_status_type", "ingestion_jobs", ["status", "job_type"])
    op.create_index("ix_job_company", "ingestion_jobs", ["company_id"])

    # --- knowledge_base_articles (KnowledgeBaseArticle) ---
    op.create_table(
        "knowledge_base_articles",
        schema='public',
    )

    # --- knowledge_base_categories (KnowledgeBaseCategory) ---
    op.create_table(
        "knowledge_base_categories",
        schema='public',
    )

    # --- knowledge_bases (KnowledgeBase) ---
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("source_type", sa.String(32), nullable=False, server_default=sa.text("'website'")),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("source_title", sa.String(512), nullable=True),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.LONGTEXT(), nullable=True),
        sa.Column("raw_content_hash", sa.String(64), nullable=True, index=True),
        sa.Column("content_metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text('0')),
        sa.Column("embedding_count", sa.Integer(), server_default=sa.text('0')),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("created_by", sa.Integer(), nullable=True),
        schema='public',
    )

    op.create_index("ix_kb_company_branch", "knowledge_bases", ["company_id", "branch_id"])
    op.create_index("ix_kb_status", "knowledge_bases", ["status"])
    op.create_index("ix_kb_source_type", "knowledge_bases", ["source_type"])

    # --- knowledge_chunks (KnowledgeChunk) ---
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("chunk_type", sa.String(32), nullable=False, server_default=sa.text("'paragraph'")),
        sa.Column("content", sa.MEDIUMTEXT(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("token_count", sa.Integer(), server_default=sa.text('0')),
        sa.Column("char_count", sa.Integer(), server_default=sa.text('0')),
        sa.Column("semantic_tags", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("source_section", sa.String(256), nullable=True),
        sa.Column("source_heading", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_chunk_kb_seq", "knowledge_chunks", ["knowledge_base_id", "sequence"])
    op.create_index("ix_chunk_company_type", "knowledge_chunks", ["company_id", "chunk_type"])

    # --- knowledge_embeddings (KnowledgeEmbedding) ---
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False, index=True),
        sa.Column("chunk_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("embedding_model", sa.String(128), nullable=False, server_default=sa.text("'all-MiniLM-L6-v2'")),
        sa.Column("embedding_version", sa.String(32), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False, server_default=sa.text('384')),
        sa.Column("vector_json", sa.JSON(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_emb_company_model", "knowledge_embeddings", ["company_id", "embedding_model"])
    op.create_index("ix_emb_kb_id", "knowledge_embeddings", ["knowledge_base_id"])

    # --- social_hashtag_intelligence (HashtagIntelligence) ---
    op.create_table(
        "social_hashtag_intelligence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("hashtag", sa.String(100), nullable=False),
        sa.Column("post_count", sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column("engagement_avg", sa.Numeric(10, 4), nullable=False, server_default=sa.text('0')),
        sa.Column("trend_direction", sa.String(20), nullable=False, server_default=sa.text("'stable'")),
        sa.Column("related_hashtags", sa.JSON(), nullable=False),
        sa.Column("suggested_for", sa.JSON(), nullable=False),
        sa.Column("last_analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_hashtag_intel_company", "social_hashtag_intelligence", ["company_id", "platform"])
    op.create_index("ix_hashtag_intel_trend", "social_hashtag_intelligence", ["trend_direction", "engagement_avg"])

    # --- social_listening (SocialListening) ---
    op.create_table(
        "social_listening",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("listen_type", sa.String(50), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, index=True, server_default=sa.text('TRUE')),
        sa.Column("last_result_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("results_summary", sa.JSON(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_social_listening_company", "social_listening", ["company_id", "is_active"])
    op.create_index("ix_social_listening_target", "social_listening", ["platform", "listen_type", "target"])

    # --- social_post_learning (SocialPostLearning) ---
    op.create_table(
        "social_post_learning",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("post_sample", sa.MEDIUMTEXT(), nullable=True),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("tone_label", sa.String(64), nullable=True),
        sa.Column("language_style", sa.String(64), nullable=True),
        sa.Column("emoji_usage", sa.String(32), nullable=True),
        sa.Column("hashtag_pattern", sa.JSON(), nullable=True),
        sa.Column("call_to_action_style", sa.String(64), nullable=True),
        sa.Column("engagement_score", sa.Float(), nullable=True),
        sa.Column("avg_sentence_length", sa.Float(), nullable=True),
        sa.Column("vocabulary_richness", sa.Float(), nullable=True),
        sa.Column("formality_score", sa.Float(), nullable=True),
        sa.Column("post_count_analyzed", sa.Integer(), server_default=sa.text('0')),
        sa.Column("date_range", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_social_company_tone", "social_post_learning", ["company_id", "tone_label"])
    op.create_index("ix_social_platform", "social_post_learning", ["platform"])

    # --- social_publishing_queue (PublishingQueue) ---
    op.create_table(
        "social_publishing_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("rate_limit_delay", sa.Integer(), nullable=False, server_default=sa.text('60')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_publishing_queue_company_status", "social_publishing_queue", ["company_id", "status"])
    op.create_index("ix_publishing_queue_scheduled", "social_publishing_queue", ["scheduled_at", "status"])

    # --- support_analytics (SupportAnalytics) ---
    op.create_table(
        "support_analytics",
        schema='public',
    )

    # --- support_macros (SupportMacro) ---
    op.create_table(
        "support_macros",
        schema='public',
    )

    # --- support_messages (SupportMessage) ---
    op.create_table(
        "support_messages",
        schema='public',
    )

    # --- support_tickets (SupportTicket) ---
    op.create_table(
        "support_tickets",
        schema='public',
    )

    # --- suspicious_activities (SuspiciousActivity) ---
    op.create_table(
        "suspicious_activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("account_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_followers", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("actual_value", sa.Float(), nullable=True),
        sa.Column("deviation_pct", sa.Numeric(10, 2), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema='public',
    )

    op.create_index("ix_suspicious_activity_company", "suspicious_activities", ["company_id", "alert_type"])
    op.create_index("ix_suspicious_activity_account", "suspicious_activities", ["account_id", "start_date"])
    op.create_index("ix_suspicious_activity_severity", "suspicious_activities", ["severity"])

    # --- visual_assets (VisualAsset) ---
    op.create_table(
        "visual_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.String(2048), nullable=False),
        sa.Column("image_hash", sa.String(64), nullable=True, index=True),
        sa.Column("image_type", sa.String(64), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dominant_colors", sa.JSON(), nullable=True),
        sa.Column("detected_objects", sa.JSON(), nullable=True),
        sa.Column("detected_text", sa.Text(), nullable=True),
        sa.Column("brand_elements", sa.JSON(), nullable=True),
        sa.Column("composition_analysis", sa.JSON(), nullable=True),
        sa.Column("style_tags", sa.JSON(), nullable=True),
        sa.Column("is_brand_asset", sa.Integer(), server_default=sa.text('0')),
        sa.Column("brand_relevance_score", sa.Float(), server_default=sa.text('0.0')),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        schema='public',
    )

    op.create_index("ix_visual_company_brand", "visual_assets", ["company_id", "is_brand_asset"])
    op.create_index("ix_visual_kb", "visual_assets", ["knowledge_base_id"])



def downgrade() -> None:
    """Drop all created tables (reverse order)."""

    op.drop_table("visual_assets", schema="public")
    op.drop_table("suspicious_activities", schema="public")
    op.drop_table("support_tickets", schema="public")
    op.drop_table("support_messages", schema="public")
    op.drop_table("support_macros", schema="public")
    op.drop_table("support_analytics", schema="public")
    op.drop_table("social_publishing_queue", schema="public")
    op.drop_table("social_post_learning", schema="public")
    op.drop_table("social_listening", schema="public")
    op.drop_table("social_hashtag_intelligence", schema="public")
    op.drop_table("knowledge_embeddings", schema="public")
    op.drop_table("knowledge_chunks", schema="public")
    op.drop_table("knowledge_bases", schema="public")
    op.drop_table("knowledge_base_categories", schema="public")
    op.drop_table("knowledge_base_articles", schema="public")
    op.drop_table("ingestion_jobs", schema="public")
    op.drop_table("follower_snapshots", schema="public")
    op.drop_table("follower_insights", schema="public")
    op.drop_table("follower_health_scores", schema="public")
    op.drop_table("export_jobs", schema="public")
    op.drop_table("escalation_rules", schema="public")
    op.drop_table("engagement_qualities", schema="public")
    op.drop_table("creative_audits", schema="public")
    op.drop_table("campaign_insights", schema="public")
    op.drop_table("brand_profiles", schema="public")
    op.drop_table("brand_colors", schema="public")
    op.drop_table("branch_brand_identities", schema="public")
    op.drop_table("bot_patterns", schema="public")
    op.drop_table("audience_demographics", schema="public")
    op.drop_table("approval_requests", schema="public")
    op.drop_table("analytics_snapshots", schema="public")
    op.drop_table("ai_reply_audit_logs", schema="public")
    op.drop_table("ai_audience_recommendations", schema="public")
    op.drop_table("ad_platforms", schema="public")
    op.drop_table("ad_metrics", schema="public")
    op.drop_table("ad_creatives", schema="public")
    op.drop_table("ad_creative_analysis", schema="public")
    op.drop_table("ad_campaigns", schema="public")
    op.drop_table("ad_budget_recommendations", schema="public")
    op.drop_table("ad_audiences", schema="public")
    op.drop_table("ad_adsets", schema="public")