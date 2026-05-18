"""
Performance indexes migration: composite and covering indexes.

Revision ID: 004
Revises: 003
Create Date: 2025-04-15 00:00:00.000000

Adds performance-optimized composite indexes for the most common query patterns
across all modules. These indexes support tenant-scoped filtering, time-range
queries, and status-based lookups that are used by the API layer.
"""

from sqlalchemy import inspect
from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


# =============================================================================
# Idempotent helpers (MySQL-safe: skip if index already exists / already gone)
# =============================================================================

def _index_exists(table_name: str, index_name: str, schema=None) -> bool:
    """Return True if *index_name* already exists on *table_name*."""
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
        indexes = inspector.get_indexes(table_name, schema=schema)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _columns_exist(table_name: str, columns: list, schema=None) -> bool:
    """Return True if all requested *columns* exist on *table_name*."""
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
        cols = inspector.get_columns(table_name, schema=schema)
    except Exception:
        return False
    existing = {c.get("name") for c in cols}
    return all(col in existing for col in columns)


def _create_index_if_not_exists(
    index_name: str,
    table_name: str,
    columns: list,
    unique: bool = False,
    schema=None,
) -> None:
    """Create an index only when it does not already exist and all columns are present."""
    if _index_exists(table_name, index_name, schema=schema):
        return
    if not _columns_exist(table_name, columns, schema=schema):
        return
    op.create_index(index_name, table_name, columns, unique=unique, schema=schema)


def _drop_index_if_exists(
    index_name: str,
    table_name: str,
    schema=None,
) -> None:
    """Drop an index only when it exists."""
    if not _index_exists(table_name, index_name, schema=schema):
        return
    op.drop_index(index_name, table_name=table_name, schema=schema)


# =============================================================================
# UPGRADE
# =============================================================================

def upgrade() -> None:
    """Create composite performance indexes (idempotent for MySQL)."""

    # ====================================================================
    # 1. TENANT-SCOPED COMPOSITE INDEXES (company_id + created_at)
    # ====================================================================

    TENANT_DATE_TABLES = [
        "ai_prompts", "ai_conversations", "ai_suggestions", "ai_recommendations",
        "ai_usage_logs",
        "social_accounts", "social_posts", "social_comments", "social_messages",
        "social_analytics", "social_competitors", "social_webhooks",
        "media_assets", "media_collections",
        "event_log", "event_subscriptions", "automation_rules",
        "company_subscriptions", "usage_records",
        "usage_quotas", "invoices", "feature_flags", "billing_events",
        "audit_logs", "security_events", "login_attempts",
    ]
    for tbl in TENANT_DATE_TABLES:
        _create_index_if_not_exists(
            f"ix_{tbl}_company_created",
            tbl, ["company_id", "created_at"],
            unique=False, schema=None,
        )

    # -- company_subscriptions special case ----------------------------------
    _create_index_if_not_exists(
        "ix_company_subscriptions_company_status",
        "company_subscriptions", ["company_id", "status"],
        unique=False, schema=None,
    )

    # -- invoices special case -----------------------------------------------
    _create_index_if_not_exists(
        "ix_invoices_company_status",
        "invoices", ["company_id", "status"],
        unique=False, schema=None,
    )

    # -- usage_quotas special case -------------------------------------------
    _create_index_if_not_exists(
        "ix_usage_quotas_company_resource",
        "usage_quotas", ["company_id", "resource_type"],
        unique=False, schema=None,
    )

    # -- feature_flags special case ------------------------------------------
    _create_index_if_not_exists(
        "ix_feature_flags_company_enabled",
        "feature_flags", ["company_id", "enabled"],
        unique=False, schema=None,
    )

    # -- audit_logs special case ---------------------------------------------
    _create_index_if_not_exists(
        "ix_audit_logs_company_action",
        "audit_logs", ["company_id", "action"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_audit_logs_company_resource",
        "audit_logs", ["company_id", "resource_type"],
        unique=False, schema=None,
    )

    # -- security_events special case ----------------------------------------
    _create_index_if_not_exists(
        "ix_security_events_company_severity",
        "security_events", ["company_id", "severity"],
        unique=False, schema=None,
    )

    # -- login_attempts special case -----------------------------------------
    _create_index_if_not_exists(
        "ix_login_attempts_email_status",
        "login_attempts", ["email", "status"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 2. AI MODULE
    # ====================================================================

    _create_index_if_not_exists(
        "ix_ai_prompts_company_active",
        "ai_prompts", ["company_id", "is_active"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_ai_conversations_user_status",
        "ai_conversations", ["user_id", "status"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_ai_messages_conv_created",
        "ai_messages", ["conversation_id", "created_at"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_ai_suggestions_company_applied",
        "ai_suggestions", ["company_id", "was_applied"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_ai_usage_logs_company_model",
        "ai_usage_logs", ["company_id", "model"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 3. SOCIAL MODULE
    # ====================================================================

    _create_index_if_not_exists(
        "ix_social_posts_company_scheduled",
        "social_posts", ["company_id", "scheduled_at"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_social_posts_company_platform",
        "social_posts", ["company_id", "platform"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_social_comments_company_sentiment",
        "social_comments", ["company_id", "sentiment"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_social_messages_company_direction",
        "social_messages", ["company_id", "direction"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_social_analytics_company_platform_date",
        "social_analytics", ["company_id", "platform", "metric_date"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_social_competitors_company_name",
        "social_competitors", ["company_id", "competitor_name"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_social_webhooks_company_created",
        "social_webhooks", ["company_id", "created_at"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 4. MEDIA MODULE
    # ====================================================================

    _create_index_if_not_exists(
        "ix_media_assets_company_status",
        "media_assets", ["company_id", "status"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_media_assets_company_mime",
        "media_assets", ["company_id", "mime_type"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_media_tags_company_name",
        "media_tags", ["company_id", "name"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 5. EVENTS MODULE
    # ====================================================================

    _create_index_if_not_exists(
        "ix_event_log_company_event_status",
        "event_log", ["company_id", "event_name", "status"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_event_log_company_status_created",
        "event_log", ["company_id", "status", "created_at"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_event_handlers_log_status",
        "event_handlers", ["event_log_id", "status"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_automation_rules_company_active",
        "automation_rules", ["company_id", "is_active"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_automation_executions_rule_status",
        "automation_executions", ["rule_id", "status"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 6. BILLING MODULE
    # ====================================================================

    _create_index_if_not_exists(
        "ix_subscription_plans_active_order",
        "subscription_plans", ["is_active", "sort_order"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_company_subscriptions_status_period",
        "company_subscriptions", ["status", "current_period_end"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_usage_records_resource_recorded",
        "usage_records", ["resource_type", "recorded_at"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_usage_records_company_resource_recorded",
        "usage_records", ["company_id", "resource_type", "recorded_at"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_invoices_company_due",
        "invoices", ["company_id", "due_date"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_billing_events_company_type_created",
        "billing_events", ["company_id", "event_type", "created_at"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 7. AUDIT MODULE
    # ====================================================================

    _create_index_if_not_exists(
        "ix_audit_logs_user_created",
        "audit_logs", ["user_id", "created_at"],
        unique=False, schema=None,
    )
    _drop_index_if_exists("ix_audit_logs_resource_id", "audit_logs", schema=None)
    _create_index_if_not_exists(
        "ix_audit_logs_company_resource_id",
        "audit_logs", ["company_id", "resource_type", "resource_id"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_security_events_type_severity",
        "security_events", ["event_type", "severity"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_login_attempts_ip_status",
        "login_attempts", ["ip_address", "status"],
        unique=False, schema=None,
    )
    _create_index_if_not_exists(
        "ix_login_attempts_ip_created",
        "login_attempts", ["ip_address", "created_at"],
        unique=False, schema=None,
    )

    # ====================================================================
    # 8. FULL-TEXT INDEXES (PostgreSQL GIN - skipped on MySQL)
    # ====================================================================

    # NOTE: Full-text indexes use PostgreSQL-specific GIN/to_tsvector syntax.
    # On MySQL these are silently skipped. A future MySQL-specific migration
    # can add equivalent FULLTEXT indexes where needed.
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_ai_prompts_name_fulltext
            ON ai_prompts USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_social_posts_content_fulltext
            ON social_posts USING gin(to_tsvector('english', content));
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_social_comments_content_fulltext
            ON social_comments USING gin(to_tsvector('english', content));
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_ai_suggestions_response_fulltext
            ON ai_suggestions USING gin(to_tsvector('english', response));
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_media_assets_filename_fulltext
            ON media_assets USING gin(to_tsvector('english', filename || ' ' || original_filename));
            """
        )


# =============================================================================
# DOWNGRADE
# =============================================================================

def downgrade() -> None:
    """Drop all composite performance indexes (idempotent for MySQL)."""

    # -- Full-text indexes (PostgreSQL only) ---------------------------------
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_media_assets_filename_fulltext;")
        op.execute("DROP INDEX IF EXISTS ix_ai_suggestions_response_fulltext;")
        op.execute("DROP INDEX IF EXISTS ix_social_comments_content_fulltext;")
        op.execute("DROP INDEX IF EXISTS ix_social_posts_content_fulltext;")
        op.execute("DROP INDEX IF EXISTS ix_ai_prompts_name_fulltext;")

    # -- Audit module composite indexes --------------------------------------
    _drop_index_if_exists("ix_login_attempts_ip_created", "login_attempts", schema=None)
    _drop_index_if_exists("ix_login_attempts_ip_status", "login_attempts", schema=None)
    _drop_index_if_exists("ix_security_events_type_severity", "security_events", schema=None)
    _drop_index_if_exists("ix_audit_logs_company_resource_id", "audit_logs", schema=None)
    _create_index_if_not_exists("ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False, schema=None)
    _drop_index_if_exists("ix_audit_logs_user_created", "audit_logs", schema=None)
    _drop_index_if_exists("ix_audit_logs_company_action", "audit_logs", schema=None)
    _drop_index_if_exists("ix_audit_logs_company_resource", "audit_logs", schema=None)
    _drop_index_if_exists("ix_audit_logs_company_created", "audit_logs", schema=None)
    _drop_index_if_exists("ix_login_attempts_email_status", "login_attempts", schema=None)
    _drop_index_if_exists("ix_security_events_company_severity", "security_events", schema=None)

    # -- Billing module composite indexes ------------------------------------
    _drop_index_if_exists("ix_billing_events_company_type_created", "billing_events", schema=None)
    _drop_index_if_exists("ix_invoices_company_due", "invoices", schema=None)
    _drop_index_if_exists("ix_usage_records_company_resource_recorded", "usage_records", schema=None)
    _drop_index_if_exists("ix_usage_records_resource_recorded", "usage_records", schema=None)
    _drop_index_if_exists("ix_company_subscriptions_status_period", "company_subscriptions", schema=None)
    _drop_index_if_exists("ix_subscription_plans_active_order", "subscription_plans", schema=None)
    _drop_index_if_exists("ix_billing_events_company_created", "billing_events", schema=None)
    _drop_index_if_exists("ix_feature_flags_company_enabled", "feature_flags", schema=None)
    _drop_index_if_exists("ix_usage_quotas_company_resource", "usage_quotas", schema=None)
    _drop_index_if_exists("ix_invoices_company_status", "invoices", schema=None)
    _drop_index_if_exists("ix_company_subscriptions_company_status", "company_subscriptions", schema=None)

    # -- Events module composite indexes -------------------------------------
    _drop_index_if_exists("ix_automation_executions_rule_status", "automation_executions", schema=None)
    _drop_index_if_exists("ix_automation_rules_company_active", "automation_rules", schema=None)
    _drop_index_if_exists("ix_event_handlers_log_status", "event_handlers", schema=None)
    _drop_index_if_exists("ix_event_log_company_status_created", "event_log", schema=None)
    _drop_index_if_exists("ix_event_log_company_event_status", "event_log", schema=None)
    _drop_index_if_exists("ix_automation_rules_company_created", "automation_rules", schema=None)
    _drop_index_if_exists("ix_automation_executions_company_created", "automation_executions", schema=None)
    _drop_index_if_exists("ix_event_subscriptions_company_created", "event_subscriptions", schema=None)
    _drop_index_if_exists("ix_event_log_company_created", "event_log", schema=None)
    _drop_index_if_exists("ix_dead_letter_events_company_created", "dead_letter_events", schema=None)

    # -- Media module composite indexes --------------------------------------
    _drop_index_if_exists("ix_media_tags_company_name", "media_tags", schema=None)
    _drop_index_if_exists("ix_media_assets_company_mime", "media_assets", schema=None)
    _drop_index_if_exists("ix_media_assets_company_status", "media_assets", schema=None)
    _drop_index_if_exists("ix_media_collections_company_created", "media_collections", schema=None)
    _drop_index_if_exists("ix_media_assets_company_created", "media_assets", schema=None)

    # -- Social module composite indexes -------------------------------------
    _drop_index_if_exists("ix_social_webhooks_company_created", "social_webhooks", schema=None)
    _drop_index_if_exists("ix_social_competitors_company_name", "social_competitors", schema=None)
    _drop_index_if_exists("ix_social_analytics_company_platform_date", "social_analytics", schema=None)
    _drop_index_if_exists("ix_social_messages_company_direction", "social_messages", schema=None)
    _drop_index_if_exists("ix_social_comments_company_sentiment", "social_comments", schema=None)
    _drop_index_if_exists("ix_social_posts_company_platform", "social_posts", schema=None)
    _drop_index_if_exists("ix_social_posts_company_scheduled", "social_posts", schema=None)
    _drop_index_if_exists("ix_social_webhooks_company_created", "social_webhooks", schema=None)
    _drop_index_if_exists("ix_social_competitors_company_created", "social_competitors", schema=None)
    _drop_index_if_exists("ix_social_analytics_company_created", "social_analytics", schema=None)
    _drop_index_if_exists("ix_social_messages_company_created", "social_messages", schema=None)
    _drop_index_if_exists("ix_social_comments_company_created", "social_comments", schema=None)
    _drop_index_if_exists("ix_social_posts_company_created", "social_posts", schema=None)
    _drop_index_if_exists("ix_social_accounts_company_created", "social_accounts", schema=None)

    # -- AI module composite indexes -----------------------------------------
    _drop_index_if_exists("ix_ai_usage_logs_company_model", "ai_usage_logs", schema=None)
    _drop_index_if_exists("ix_ai_suggestions_company_applied", "ai_suggestions", schema=None)
    _drop_index_if_exists("ix_ai_messages_conv_created", "ai_messages", schema=None)
    _drop_index_if_exists("ix_ai_conversations_user_status", "ai_conversations", schema=None)
    _drop_index_if_exists("ix_ai_prompts_company_active", "ai_prompts", schema=None)
    _drop_index_if_exists("ix_ai_cache_company_created", "ai_cache", schema=None)
    _drop_index_if_exists("ix_ai_usage_logs_company_created", "ai_usage_logs", schema=None)
    _drop_index_if_exists("ix_ai_recommendations_company_created", "ai_recommendations", schema=None)
    _drop_index_if_exists("ix_ai_suggestions_company_created", "ai_suggestions", schema=None)
    _drop_index_if_exists("ix_ai_messages_company_created", "ai_messages", schema=None)
    _drop_index_if_exists("ix_ai_conversations_company_created", "ai_conversations", schema=None)
    _drop_index_if_exists("ix_ai_prompts_company_created", "ai_prompts", schema=None)
