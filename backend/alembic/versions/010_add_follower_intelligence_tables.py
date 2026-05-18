"""010_add_follower_intelligence_tables

Revision ID: 010
Revises: 009
Create Date: 2026-05-16

Follower intelligence tables:
- follower_delta_events (snapshot comparison)
- engagement_events (new interaction tracking)
- reengagement_recommendations (AI re-engagement)
- safe_message_templates (policy-safe templates)
- outreach_approval_requests (approval workflow)
- audience_loss_estimates (estimated unfollow tracking)
- follower_retention_metrics (retention analytics)
- follower_value_scores (per-follower value classification)
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # follower_delta_events
    # ================================================================
    op.create_table(
        "follower_delta_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("previous_snapshot_id", sa.Integer, nullable=False),
        sa.Column("current_snapshot_id", sa.Integer, nullable=False),
        sa.Column("follower_delta", sa.Integer, nullable=False),
        sa.Column("estimated_new", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("estimated_unfollow", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), server_default=sa.text("0.5"), nullable=False),
        sa.Column("confidence_reason", sa.String(255), nullable=True),
        sa.Column("is_suspicious", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("event_date", sa.DateTime, nullable=False),
        sa.Column("details", sa.JSON, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_delta_event_account_date", "follower_delta_events", ["account_id", "event_date"], schema=None)
    op.create_index("ix_delta_event_company_type", "follower_delta_events", ["company_id", "event_type"], schema=None)
    op.create_index("ix_delta_event_platform", "follower_delta_events", ["company_id", "platform", "event_date"], schema=None)

    # ================================================================
    # engagement_events
    # ================================================================
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("follower_account_id", sa.String(255), nullable=True),
        sa.Column("follower_username", sa.String(255), nullable=True),
        sa.Column("post_id", sa.String(255), nullable=True),
        sa.Column("message_preview", sa.String(500), nullable=True),
        sa.Column("sentiment", sa.String(20), server_default=sa.text("'neutral'"), nullable=False),
        sa.Column("is_new_lead", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("lead_score", sa.Numeric(4, 3), server_default=sa.text("0.0"), nullable=False),
        sa.Column("campaign_id", sa.String(255), nullable=True),
        sa.Column("event_date", sa.DateTime, nullable=False),
        sa.Column("raw_data", sa.JSON, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_engagement_event_account_date", "engagement_events", ["account_id", "event_date"], schema=None)
    op.create_index("ix_engagement_event_type", "engagement_events", ["company_id", "event_type", "event_date"], schema=None)
    op.create_index("ix_engagement_event_follower", "engagement_events", ["follower_account_id", "event_date"], schema=None)

    # ================================================================
    # reengagement_recommendations
    # ================================================================
    op.create_table(
        "reengagement_recommendations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("reengagement_type", sa.String(50), nullable=False),
        sa.Column("target_follower_id", sa.String(255), nullable=True),
        sa.Column("target_follower_username", sa.String(255), nullable=True),
        sa.Column("target_segment", sa.String(100), nullable=True),
        sa.Column("ai_suggested_message", sa.Text, nullable=True),
        sa.Column("ai_suggested_subject", sa.String(255), nullable=True),
        sa.Column("confidence_score", sa.Numeric(4, 3), server_default=sa.text("0.0"), nullable=False),
        sa.Column("expected_response_rate", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("approval_status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("rejection_reason", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("sent_result", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_reengagement_account", "reengagement_recommendations", ["account_id", "created_at"], schema=None)
    op.create_index("ix_reengagement_company_type", "reengagement_recommendations", ["company_id", "reengagement_type"], schema=None)
    op.create_index("ix_reengagement_status", "reengagement_recommendations", ["approval_status"], schema=None)

    # ================================================================
    # safe_message_templates
    # ================================================================
    op.create_table(
        "safe_message_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subject_template", sa.String(500), nullable=True),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("variables", sa.JSON, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("policy_status", sa.String(50), server_default=sa.text("'needs_review'"), nullable=False),
        sa.Column("policy_review_notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE"), nullable=False),
        sa.Column("use_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("avg_response_rate", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_safe_template_company_platform", "safe_message_templates", ["company_id", "platform"], schema=None)
    op.create_index("ix_safe_template_type", "safe_message_templates", ["template_type", "platform"], schema=None)

    # ================================================================
    # outreach_approval_requests
    # ================================================================
    op.create_table(
        "outreach_approval_requests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reengagement_id", sa.Integer, sa.ForeignKey("reengagement_recommendations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("recipient_account_id", sa.String(255), nullable=True),
        sa.Column("recipient_username", sa.String(255), nullable=True),
        sa.Column("message_subject", sa.String(500), nullable=True),
        sa.Column("message_body", sa.Text, nullable=False),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("policy_check_result", sa.String(50), server_default=sa.text("'needs_review'"), nullable=False),
        sa.Column("policy_check_details", sa.Text, nullable=True),
        sa.Column("requested_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("review_notes", sa.String(500), nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("sent_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("send_result", sa.String(255), nullable=True),
        sa.Column("rate_limit_applied", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_outreach_approval_company", "outreach_approval_requests", ["company_id", "status"], schema=None)
    op.create_index("ix_outreach_approval_requester", "outreach_approval_requests", ["requested_by", "created_at"], schema=None)
    op.create_index("ix_outreach_approval_platform", "outreach_approval_requests", ["platform", "status"], schema=None)

    # ================================================================
    # audience_loss_estimates
    # ================================================================
    op.create_table(
        "audience_loss_estimates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("loss_type", sa.String(50), nullable=False),
        sa.Column("estimated_loss_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), server_default=sa.text("0.5"), nullable=False),
        sa.Column("confidence_reason", sa.String(255), nullable=True),
        sa.Column("previous_follower_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("current_follower_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("net_change", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("is_suspicious", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("triggered_alert", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("snapshot_ids", sa.JSON, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("estimate_date", sa.DateTime, nullable=False),
        sa.Column("details", sa.JSON, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_audience_loss_account_date", "audience_loss_estimates", ["account_id", "estimate_date"], schema=None)
    op.create_index("ix_audience_loss_company_type", "audience_loss_estimates", ["company_id", "loss_type"], schema=None)

    # ================================================================
    # follower_retention_metrics
    # ================================================================
    op.create_table(
        "follower_retention_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("period_start", sa.DateTime, nullable=False),
        sa.Column("period_end", sa.DateTime, nullable=False),
        sa.Column("period_days", sa.Integer, server_default=sa.text("7"), nullable=False),
        sa.Column("starting_followers", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("ending_followers", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("new_followers_estimated", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("lost_followers_estimated", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("retention_rate", sa.Numeric(5, 2), server_default=sa.text("100.0"), nullable=False),
        sa.Column("churn_rate", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("growth_rate", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("recovery_rate", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("net_growth", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("high_value_retained", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("ghost_followers_removed", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("inactive_identified", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("engagement_quality_score", sa.Numeric(4, 3), server_default=sa.text("0.0"), nullable=False),
        sa.Column("branch_comparison", sa.JSON, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("details", sa.JSON, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_retention_account_period", "follower_retention_metrics", ["account_id", "period_start"], schema=None)
    op.create_index("ix_retention_company_platform", "follower_retention_metrics", ["company_id", "platform", "period_start"], schema=None)

    # ================================================================
    # follower_value_scores
    # ================================================================
    op.create_table(
        "follower_value_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("follower_account_id", sa.String(255), nullable=False),
        sa.Column("follower_username", sa.String(255), nullable=True),
        sa.Column("value_tier", sa.String(50), nullable=False),
        sa.Column("engagement_frequency", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("last_engagement_at", sa.DateTime, nullable=True),
        sa.Column("total_engagements", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("engagement_quality_avg", sa.Numeric(4, 3), server_default=sa.text("0.0"), nullable=False),
        sa.Column("days_since_engagement", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("value_score", sa.Numeric(5, 2), server_default=sa.text("0.0"), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3), server_default=sa.text("0.5"), nullable=False),
        sa.Column("is_inactive", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("is_ghost", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("scored_at", sa.DateTime, nullable=False),
        sa.Column("details", sa.JSON, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        schema=None,
    )
    op.create_index("ix_value_score_account", "follower_value_scores", ["account_id", "value_tier"], schema=None)
    op.create_index("ix_value_score_follower", "follower_value_scores", ["follower_account_id", "scored_at"], schema=None)


def downgrade() -> None:
    op.drop_table("follower_value_scores", schema=None)
    op.drop_table("follower_retention_metrics", schema=None)
    op.drop_table("audience_loss_estimates", schema=None)
    op.drop_table("outreach_approval_requests", schema=None)
    op.drop_table("safe_message_templates", schema=None)
    op.drop_table("reengagement_recommendations", schema=None)
    op.drop_table("engagement_events", schema=None)
    op.drop_table("follower_delta_events", schema=None)
