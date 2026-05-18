"""
Performance indexes migration: composite and covering indexes.

Revision ID: 004
Revises: 003
Create Date: 2025-04-15 00:00:00.000000

Adds performance-optimized composite indexes for the most common query patterns
across all modules. These indexes support tenant-scoped filtering, time-range
queries, and status-based lookups that are used by the API layer.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create composite performance indexes."""

    # ========================================================================
    # 1. TENANT-SCOPED COMPOSITE INDEXES (company_id + created_at)
    #    Most common query pattern: list records for a company ordered by date
    # ========================================================================

    TENANT_DATE_TABLES = [
        "ai_prompts", "ai_conversations", "ai_suggestions", "ai_recommendations",
        "ai_usage_logs",
        "social_accounts", "social_posts", "social_comments", "social_messages",
        "social_analytics", "social_competitors", "social_webhooks",
        "media_assets", "media_collections",
        "event_log", "event_subscriptions", "automation_rules",
        "subscription_plans", "company_subscriptions", "usage_records",
        "usage_quotas", "invoices", "feature_flags", "billing_events",
        "audit_logs", "security_events", "login_attempts",
    ]
    for tbl in TENANT_DATE_TABLES:
        op.create_index(
            f"ix_{tbl}_company_created",
            tbl, ["company_id", "created_at"],
            unique=False, schema=None,
            comment="Tenant-scoped date range queries",
        )

    # -- company_subscriptions special case ----------------------------------
    op.create_index(
        "ix_company_subscriptions_company_status",
        "company_subscriptions", ["company_id", "status"],
        unique=False, schema=None,
    )

    # -- invoices special case -----------------------------------------------
    op.create_index(
        "ix_invoices_company_status",
        "invoices", ["company_id", "status"],
        unique=False, schema=None,
    )

    # -- usage_quotas special case -------------------------------------------
    op.create_index(
        "ix_usage_quotas_company_resource",
        "usage_quotas", ["company_id", "resource_type"],
        unique=False, schema=None,
    )

    # -- feature_flags special case ------------------------------------------
    op.create_index(
        "ix_feature_flags_company_enabled",
        "feature_flags", ["company_id", "enabled"],
        unique=False, schema=None,
    )

    # -- audit_logs special case ---------------------------------------------
    op.create_index(
        "ix_audit_logs_company_action",
        "audit_logs", ["company_id", "action"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_audit_logs_company_resource",
        "audit_logs", ["company_id", "resource_type"],
        unique=False, schema=None,
    )

    # -- security_events special case ----------------------------------------
    op.create_index(
        "ix_security_events_company_severity",
        "security_events", ["company_id", "severity"],
        unique=False, schema=None,
    )

    # -- login_attempts special case -----------------------------------------
    op.create_index(
        "ix_login_attempts_email_status",
        "login_attempts", ["email", "status"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 2. AI MODULE
    # ========================================================================

    op.create_index(
        "ix_ai_prompts_company_active",
        "ai_prompts", ["company_id", "is_active"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_ai_conversations_user_status",
        "ai_conversations", ["user_id", "status"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_ai_messages_conv_created",
        "ai_messages", ["conversation_id", "created_at"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_ai_suggestions_company_applied",
        "ai_suggestions", ["company_id", "was_applied"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_ai_usage_logs_company_model",
        "ai_usage_logs", ["company_id", "model"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 3. SOCIAL MODULE
    # ========================================================================

    op.create_index(
        "ix_social_posts_company_scheduled",
        "social_posts", ["company_id", "scheduled_at"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_social_posts_company_platform",
        "social_posts", ["company_id", "platform"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_social_comments_company_sentiment",
        "social_comments", ["company_id", "sentiment"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_social_messages_company_direction",
        "social_messages", ["company_id", "direction"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_social_analytics_company_platform_date",
        "social_analytics", ["company_id", "platform", "metric_date"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_social_competitors_company_name",
        "social_competitors", ["company_id", "competitor_name"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_social_webhooks_company_created",
        "social_webhooks", ["company_id", "created_at"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 4. MEDIA MODULE
    # ========================================================================

    op.create_index(
        "ix_media_assets_company_status",
        "media_assets", ["company_id", "status"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_media_assets_company_mime",
        "media_assets", ["company_id", "mime_type"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_media_tags_company_name",
        "media_tags", ["company_id", "name"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 5. EVENTS MODULE
    # ========================================================================

    op.create_index(
        "ix_event_log_company_event_status",
        "event_log", ["company_id", "event_name", "status"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_event_log_company_status_created",
        "event_log", ["company_id", "status", "created_at"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_event_handlers_log_status",
        "event_handlers", ["event_log_id", "status"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_automation_rules_company_active",
        "automation_rules", ["company_id", "is_active"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_automation_executions_rule_status",
        "automation_executions", ["rule_id", "status"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 6. BILLING MODULE
    # ========================================================================

    op.create_index(
        "ix_subscription_plans_active_order",
        "subscription_plans", ["is_active", "sort_order"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_company_subscriptions_status_period",
        "company_subscriptions", ["status", "current_period_end"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_usage_records_resource_recorded",
        "usage_records", ["resource_type", "recorded_at"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_usage_records_company_resource_recorded",
        "usage_records", ["company_id", "resource_type", "recorded_at"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_invoices_company_due",
        "invoices", ["company_id", "due_date"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_billing_events_company_type_created",
        "billing_events", ["company_id", "event_type", "created_at"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 7. AUDIT MODULE
    # ========================================================================

    op.create_index(
        "ix_audit_logs_user_created",
        "audit_logs", ["user_id", "created_at"],
        unique=False, schema=None,
    )
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs", schema=None)
    op.create_index(
        "ix_audit_logs_company_resource_id",
        "audit_logs", ["company_id", "resource_type", "resource_id"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_security_events_type_severity",
        "security_events", ["event_type", "severity"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_login_attempts_ip_status",
        "login_attempts", ["ip_address", "status"],
        unique=False, schema=None,
    )
    op.create_index(
        "ix_login_attempts_ip_created",
        "login_attempts", ["ip_address", "created_at"],
        unique=False, schema=None,
    )

    # ========================================================================
    # 8. FULL-TEXT INDEXES (for searchable text columns)
    # ========================================================================

    # ai_prompts: search by name and description
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_prompts_name_fulltext
        ON ai_prompts USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));
        """
    )

    # social_posts: search by content
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_social_posts_content_fulltext
        ON social_posts USING gin(to_tsvector('english', content));
        """
    )

    # social_comments: search by content
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_social_comments_content_fulltext
        ON social_comments USING gin(to_tsvector('english', content));
        """
    )

    # ai_suggestions: search by response
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_suggestions_response_fulltext
        ON ai_suggestions USING gin(to_tsvector('english', response));
        """
    )

    # media_assets: search by filename
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_media_assets_filename_fulltext
        ON media_assets USING gin(to_tsvector('english', filename || ' ' || original_filename));
        """
    )


def downgrade() -> None:
    """Drop all composite performance indexes."""

    # -- Full-text indexes ---------------------------------------------------
    op.execute("DROP INDEX IF EXISTS ix_media_assets_filename_fulltext;")
    op.execute("DROP INDEX IF EXISTS ix_ai_suggestions_response_fulltext;")
    op.execute("DROP INDEX IF EXISTS ix_social_comments_content_fulltext;")
    op.execute("DROP INDEX IF EXISTS ix_social_posts_content_fulltext;")
    op.execute("DROP INDEX IF EXISTS ix_ai_prompts_name_fulltext;")

    # -- Audit module composite indexes --------------------------------------
    op.drop_index("ix_login_attempts_ip_created", table_name="login_attempts", schema=None)
    op.drop_index("ix_login_attempts_ip_status", table_name="login_attempts", schema=None)
    op.drop_index("ix_security_events_type_severity", table_name="security_events", schema=None)
    op.drop_index("ix_audit_logs_company_resource_id", table_name="audit_logs", schema=None)
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False, schema=None)
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs", schema=None)
    op.drop_index("ix_audit_logs_company_action", table_name="audit_logs", schema=None)
    op.drop_index("ix_audit_logs_company_resource", table_name="audit_logs", schema=None)
    op.drop_index("ix_audit_logs_company_created", table_name="audit_logs", schema=None)
    op.drop_index("ix_login_attempts_email_status", table_name="login_attempts", schema=None)
    op.drop_index("ix_security_events_company_severity", table_name="security_events", schema=None)

    # -- Billing module composite indexes ------------------------------------
    op.drop_index("ix_billing_events_company_type_created", table_name="billing_events", schema=None)
    op.drop_index("ix_invoices_company_due", table_name="invoices", schema=None)
    op.drop_index("ix_usage_records_company_resource_recorded", table_name="usage_records", schema=None)
    op.drop_index("ix_usage_records_resource_recorded", table_name="usage_records", schema=None)
    op.drop_index("ix_company_subscriptions_status_period", table_name="company_subscriptions", schema=None)
    op.drop_index("ix_subscription_plans_active_order", table_name="subscription_plans", schema=None)
    op.drop_index("ix_billing_events_company_created", table_name="billing_events", schema=None)
    op.drop_index("ix_feature_flags_company_enabled", table_name="feature_flags", schema=None)
    op.drop_index("ix_usage_quotas_company_resource", table_name="usage_quotas", schema=None)
    op.drop_index("ix_invoices_company_status", table_name="invoices", schema=None)
    op.drop_index("ix_company_subscriptions_company_status", table_name="company_subscriptions", schema=None)

    # -- Events module composite indexes -------------------------------------
    op.drop_index("ix_automation_executions_rule_status", table_name="automation_executions", schema=None)
    op.drop_index("ix_automation_rules_company_active", table_name="automation_rules", schema=None)
    op.drop_index("ix_event_handlers_log_status", table_name="event_handlers", schema=None)
    op.drop_index("ix_event_log_company_status_created", table_name="event_log", schema=None)
    op.drop_index("ix_event_log_company_event_status", table_name="event_log", schema=None)
    op.drop_index("ix_automation_rules_company_created", table_name="automation_rules", schema=None)
    op.drop_index("ix_automation_executions_company_created", table_name="automation_executions", schema=None)
    op.drop_index("ix_event_subscriptions_company_created", table_name="event_subscriptions", schema=None)
    op.drop_index("ix_event_log_company_created", table_name="event_log", schema=None)
    op.drop_index("ix_dead_letter_events_company_created", table_name="dead_letter_events", schema=None)

    # -- Media module composite indexes --------------------------------------
    op.drop_index("ix_media_tags_company_name", table_name="media_tags", schema=None)
    op.drop_index("ix_media_assets_company_mime", table_name="media_assets", schema=None)
    op.drop_index("ix_media_assets_company_status", table_name="media_assets", schema=None)
    op.drop_index("ix_media_collections_company_created", table_name="media_collections", schema=None)
    op.drop_index("ix_media_assets_company_created", table_name="media_assets", schema=None)

    # -- Social module composite indexes -------------------------------------
    op.drop_index("ix_social_webhooks_company_created", table_name="social_webhooks", schema=None)
    op.drop_index("ix_social_competitors_company_name", table_name="social_competitors", schema=None)
    op.drop_index("ix_social_analytics_company_platform_date", table_name="social_analytics", schema=None)
    op.drop_index("ix_social_messages_company_direction", table_name="social_messages", schema=None)
    op.drop_index("ix_social_comments_company_sentiment", table_name="social_comments", schema=None)
    op.drop_index("ix_social_posts_company_platform", table_name="social_posts", schema=None)
    op.drop_index("ix_social_posts_company_scheduled", table_name="social_posts", schema=None)
    op.drop_index("ix_social_webhooks_company_created", table_name="social_webhooks", schema=None)
    op.drop_index("ix_social_competitors_company_created", table_name="social_competitors", schema=None)
    op.drop_index("ix_social_analytics_company_created", table_name="social_analytics", schema=None)
    op.drop_index("ix_social_messages_company_created", table_name="social_messages", schema=None)
    op.drop_index("ix_social_comments_company_created", table_name="social_comments", schema=None)
    op.drop_index("ix_social_posts_company_created", table_name="social_posts", schema=None)
    op.drop_index("ix_social_accounts_company_created", table_name="social_accounts", schema=None)

    # -- AI module composite indexes -----------------------------------------
    op.drop_index("ix_ai_usage_logs_company_model", table_name="ai_usage_logs", schema=None)
    op.drop_index("ix_ai_suggestions_company_applied", table_name="ai_suggestions", schema=None)
    op.drop_index("ix_ai_messages_conv_created", table_name="ai_messages", schema=None)
    op.drop_index("ix_ai_conversations_user_status", table_name="ai_conversations", schema=None)
    op.drop_index("ix_ai_prompts_company_active", table_name="ai_prompts", schema=None)
    op.drop_index("ix_ai_cache_company_created", table_name="ai_cache", schema=None)
    op.drop_index("ix_ai_usage_logs_company_created", table_name="ai_usage_logs", schema=None)
    op.drop_index("ix_ai_recommendations_company_created", table_name="ai_recommendations", schema=None)
    op.drop_index("ix_ai_suggestions_company_created", table_name="ai_suggestions", schema=None)
    op.drop_index("ix_ai_messages_company_created", table_name="ai_messages", schema=None)
    op.drop_index("ix_ai_conversations_company_created", table_name="ai_conversations", schema=None)
    op.drop_index("ix_ai_prompts_company_created", table_name="ai_prompts", schema=None)
