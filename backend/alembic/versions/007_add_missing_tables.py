"""Add missing tables (41 tables across 9 modules)

Revision ID: 007
Revises: 006
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str, schema=None) -> bool:
    """Return True if *table_name* already exists."""
    bind = op.get_bind()
    try:
        return bind.dialect.has_table(bind, table_name, schema=schema)
    except Exception:
        return False


def _create_table_if_not_exists(name, *args, **kwargs):
    """Create table only if it does not already exist."""
    if _table_exists(name):
        return
    op.create_table(name, *args, **kwargs)


def _drop_table_if_exists(name, **kwargs):
    """Drop table only if it exists."""
    if not _table_exists(name):
        return
    op.drop_table(name, **kwargs)


def _index_exists(table_name: str, index_name: str, schema=None) -> bool:
    """Return True if *index_name* already exists on *table_name*."""
    bind = op.get_bind()
    try:
        indexes = inspect(bind).get_indexes(table_name, schema=schema)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _create_index_if_not_exists(index_name, table_name, columns, unique=False, schema=None):
    """Create an index only when it does not already exist."""
    if _index_exists(table_name, index_name, schema=schema):
        return
    op.create_index(index_name, table_name, columns, unique=unique, schema=schema)


def _drop_index_if_exists(index_name, table_name, schema=None):
    """Drop an index only when it exists."""
    if not _index_exists(table_name, index_name, schema=schema):
        return
    op.drop_index(index_name, table_name=table_name, schema=schema)


def upgrade() -> None:
    """Create all missing tables."""

    # --- ad_adsets (AdAdset) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ad_audiences (AdAudience) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ad_budget_recommendations (AdBudgetRecommendation) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ad_campaigns (AdCampaign) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ad_creative_analysis (AdCreativeAnalysis) ---
    _create_table_if_not_exists(
        "ad_creative_analysis",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("creative_id", sa.Integer(), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("analysis_type", sa.String(50), nullable=False, index=True),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("ai_insights", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )

    # --- ad_creatives (AdCreative) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ad_metrics (AdMetric) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ad_platforms (AdPlatformAccount) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- ai_audience_recommendations (AIAudienceRecommendation) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_ai_rec_company", "ai_audience_recommendations", ["company_id", "recommendation_type"])
    _create_index_if_not_exists("ix_ai_rec_account", "ai_audience_recommendations", ["account_id", "generated_at"])

    # --- ai_reply_audit_logs (AIReplyAuditLog) ---
    _create_table_if_not_exists(
        "ai_reply_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=True),
        sa.Column("ai_reply", sa.Text(), nullable=True),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- analytics_snapshots (AnalyticsSnapshot) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("uq_analytics_snapshots_company_branch_report_date", "analytics_snapshots", ["company_id", "branch_id", "report_type", "snapshot_date"], unique=True)

    # --- approval_requests (ApprovalRequest) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- audience_demographics (AudienceDemographics) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_audience_demo_account", "audience_demographics", ["account_id", "analysis_date"])
    _create_index_if_not_exists("ix_audience_demo_company", "audience_demographics", ["company_id", "platform"])

    # --- bot_patterns (BotPattern) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_bot_patterns_company_risk", "bot_patterns", ["company_id", "risk_level"])
    _create_index_if_not_exists("ix_bot_patterns_account", "bot_patterns", ["account_id", "detected_at"])
    _create_index_if_not_exists("ix_bot_patterns_score", "bot_patterns", ["bot_score"])

    # --- branch_brand_identities (BranchBrandIdentity) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("uq_branch_brand_identity", "branch_brand_identities", ["branch_id"], unique=True)

    # --- brand_colors (BrandColor) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("uq_brand_color", "brand_colors", ["company_id", "branch_id", "hex_code", "usage_area"], unique=True)

    # --- brand_profiles (BrandProfile) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_brand_company_type", "brand_profiles", ["company_id", "attribute_type"])
    _create_index_if_not_exists("uq_brand_attr", "brand_profiles", ["company_id", "branch_id", "attribute_type", "attribute_key"], unique=True)

    # --- campaign_insights (CampaignInsight) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_campaign_company_type", "campaign_insights", ["company_id", "campaign_type"])
    _create_index_if_not_exists("ix_campaign_platform", "campaign_insights", ["platform"])
    _create_index_if_not_exists("ix_campaign_kb", "campaign_insights", ["knowledge_base_id"])

    # --- creative_audits (CreativeAudit) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("uq_creative_audit_media", "creative_audits", ["media_id"], unique=True)

    # --- engagement_qualities (EngagementQuality) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_engagement_quality_account_period", "engagement_qualities", ["account_id", "period_start"])
    _create_index_if_not_exists("ix_engagement_quality_post", "engagement_qualities", ["post_id"])

    # --- escalation_rules (EscalationRule) ---
    _create_table_if_not_exists(
        "escalation_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- export_jobs (ExportJob) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    # --- follower_health_scores (FollowerHealthScore) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_follower_health_account_date", "follower_health_scores", ["account_id", "score_date"])
    _create_index_if_not_exists("ix_follower_health_company_status", "follower_health_scores", ["company_id", "status"])

    # --- follower_insights (FollowerInsight) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_follower_insights_account", "follower_insights", ["account_id", "analyzed_at"])
    _create_index_if_not_exists("ix_follower_insights_bot", "follower_insights", ["bot_score"])
    _create_index_if_not_exists("ix_follower_insights_flagged", "follower_insights", ["is_flagged"])

    # --- follower_snapshots (FollowerSnapshot) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_follower_snapshots_account_date", "follower_snapshots", ["account_id", "snapshot_date"])
    _create_index_if_not_exists("ix_follower_snapshots_company_platform", "follower_snapshots", ["company_id", "platform"])

    # --- ingestion_jobs (IngestionJob) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_job_status_type", "ingestion_jobs", ["status", "job_type"])
    _create_index_if_not_exists("ix_job_company", "ingestion_jobs", ["company_id"])

    # --- knowledge_base_articles (KnowledgeBaseArticle) ---
    _create_table_if_not_exists(
        "knowledge_base_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("category_id", sa.Integer(), nullable=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- knowledge_base_categories (KnowledgeBaseCategory) ---
    _create_table_if_not_exists(
        "knowledge_base_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- knowledge_bases (KnowledgeBase) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_kb_company_branch", "knowledge_bases", ["company_id", "branch_id"])
    _create_index_if_not_exists("ix_kb_status", "knowledge_bases", ["status"])
    _create_index_if_not_exists("ix_kb_source_type", "knowledge_bases", ["source_type"])

    # --- knowledge_chunks (KnowledgeChunk) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_chunk_kb_seq", "knowledge_chunks", ["knowledge_base_id", "sequence"])
    _create_index_if_not_exists("ix_chunk_company_type", "knowledge_chunks", ["company_id", "chunk_type"])

    # --- knowledge_embeddings (KnowledgeEmbedding) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_emb_company_model", "knowledge_embeddings", ["company_id", "embedding_model"])
    _create_index_if_not_exists("ix_emb_kb_id", "knowledge_embeddings", ["knowledge_base_id"])

    # --- social_hashtag_intelligence (HashtagIntelligence) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_hashtag_intel_company", "social_hashtag_intelligence", ["company_id", "platform"])
    _create_index_if_not_exists("ix_hashtag_intel_trend", "social_hashtag_intelligence", ["trend_direction", "engagement_avg"])

    # --- social_listening (SocialListening) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_social_listening_company", "social_listening", ["company_id", "is_active"])
    _create_index_if_not_exists("ix_social_listening_target", "social_listening", ["platform", "listen_type", "target"])

    # --- social_post_learning (SocialPostLearning) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_social_company_tone", "social_post_learning", ["company_id", "tone_label"])
    _create_index_if_not_exists("ix_social_platform", "social_post_learning", ["platform"])

    # --- social_publishing_queue (PublishingQueue) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_publishing_queue_company_status", "social_publishing_queue", ["company_id", "status"])
    _create_index_if_not_exists("ix_publishing_queue_scheduled", "social_publishing_queue", ["scheduled_at", "status"])

    # --- support_analytics (SupportAnalytics) ---
    _create_table_if_not_exists(
        "support_analytics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- support_macros (SupportMacro) ---
    _create_table_if_not_exists(
        "support_macros",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("shortcut", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- support_messages (SupportMessage) ---
    _create_table_if_not_exists(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("ticket_id", sa.Integer(), nullable=False, index=True),
        sa.Column("sender_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- support_tickets (SupportTicket) ---
    _create_table_if_not_exists(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'open'")),
        sa.Column("priority", sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("requester_email", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema=None,
    )

    # --- suspicious_activities (SuspiciousActivity) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_suspicious_activity_company", "suspicious_activities", ["company_id", "alert_type"])
    _create_index_if_not_exists("ix_suspicious_activity_account", "suspicious_activities", ["account_id", "start_date"])
    _create_index_if_not_exists("ix_suspicious_activity_severity", "suspicious_activities", ["severity"])

    # --- visual_assets (VisualAsset) ---
    _create_table_if_not_exists(
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
        schema=None,
    )

    _create_index_if_not_exists("ix_visual_company_brand", "visual_assets", ["company_id", "is_brand_asset"])
    _create_index_if_not_exists("ix_visual_kb", "visual_assets", ["knowledge_base_id"])



def downgrade() -> None:
    """Drop all created tables (reverse order)."""

    _drop_table_if_exists("visual_assets", schema=None)
    _drop_table_if_exists("suspicious_activities", schema=None)
    _drop_table_if_exists("support_tickets", schema=None)
    _drop_table_if_exists("support_messages", schema=None)
    _drop_table_if_exists("support_macros", schema=None)
    _drop_table_if_exists("support_analytics", schema=None)
    _drop_table_if_exists("social_publishing_queue", schema=None)
    _drop_table_if_exists("social_post_learning", schema=None)
    _drop_table_if_exists("social_listening", schema=None)
    _drop_table_if_exists("social_hashtag_intelligence", schema=None)
    _drop_table_if_exists("knowledge_embeddings", schema=None)
    _drop_table_if_exists("knowledge_chunks", schema=None)
    _drop_table_if_exists("knowledge_bases", schema=None)
    _drop_table_if_exists("knowledge_base_categories", schema=None)
    _drop_table_if_exists("knowledge_base_articles", schema=None)
    _drop_table_if_exists("ingestion_jobs", schema=None)
    _drop_table_if_exists("follower_snapshots", schema=None)
    _drop_table_if_exists("follower_insights", schema=None)
    _drop_table_if_exists("follower_health_scores", schema=None)
    _drop_table_if_exists("export_jobs", schema=None)
    _drop_table_if_exists("escalation_rules", schema=None)
    _drop_table_if_exists("engagement_qualities", schema=None)
    _drop_table_if_exists("creative_audits", schema=None)
    _drop_table_if_exists("campaign_insights", schema=None)
    _drop_table_if_exists("brand_profiles", schema=None)
    _drop_table_if_exists("brand_colors", schema=None)
    _drop_table_if_exists("branch_brand_identities", schema=None)
    _drop_table_if_exists("bot_patterns", schema=None)
    _drop_table_if_exists("audience_demographics", schema=None)
    _drop_table_if_exists("approval_requests", schema=None)
    _drop_table_if_exists("analytics_snapshots", schema=None)
    _drop_table_if_exists("ai_reply_audit_logs", schema=None)
    _drop_table_if_exists("ai_audience_recommendations", schema=None)
    _drop_table_if_exists("ad_platforms", schema=None)
    _drop_table_if_exists("ad_metrics", schema=None)
    _drop_table_if_exists("ad_creatives", schema=None)
    _drop_table_if_exists("ad_creative_analysis", schema=None)
    _drop_table_if_exists("ad_campaigns", schema=None)
    _drop_table_if_exists("ad_budget_recommendations", schema=None)
    _drop_table_if_exists("ad_audiences", schema=None)
    _drop_table_if_exists("ad_adsets", schema=None)