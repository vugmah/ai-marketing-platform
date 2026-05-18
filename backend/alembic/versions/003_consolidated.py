"""
Consolidated migration: AI, Social, Media, Events, Billing, and Audit tables.

Revision ID: 003
Revises: 002
Create Date: 2025-04-01 00:00:00.000000

Creates 41 tables across 6 modules:
- AI (7): ai_prompts, ai_conversations, ai_messages, ai_suggestions, ai_recommendations, ai_usage_logs, ai_cache
- Social (7): social_accounts, social_posts, social_comments, social_messages, social_analytics, social_competitors, social_webhooks
- Media (8): media_assets, media_variants, media_tags, media_tag_mappings, media_collections, media_collection_items, media_analytics, ai_image_analysis
- Events (7): event_definitions, event_subscriptions, event_log, event_handlers, dead_letter_events, automation_rules, automation_executions
- Billing (7): subscription_plans, company_subscriptions, usage_records, usage_quotas, invoices, feature_flags, billing_events
- Audit (5): audit_logs, security_events, login_attempts, api_keys, data_access_logs

All tables use InnoDB engine, utf8mb4 charset, and include proper tenant isolation.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _create_enum(name: str, values: list[str]) -> sa.Enum:
    """Create a database ENUM type."""
    e = sa.Enum(*values, name=name)
    e.create(op.get_bind(), checkfirst=True)
    return e


def _drop_enum(name: str) -> None:
    """Drop a database ENUM type."""
    sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)


def _common_tenant_cols(nullable_company: bool = False) -> list:
    """Return common tenant isolation columns used on most tables."""
    return [
        sa.Column("company_id", sa.Integer(), nullable=nullable_company),
        sa.Column("branch_id", sa.Integer(), nullable=True),
    ]


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    """Create all consolidated module tables with indexes and constraints."""

    # ========================================================================
    # 1. ENUM TYPES
    # ========================================================================

    # -- AI module enums -----------------------------------------------------
    aimodelname = _create_enum("aimodelname", ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"])
    messagerole = _create_enum("messagerole", ["user", "assistant", "system", "tool"])
    conversationstatus = _create_enum("conversationstatus", ["active", "archived", "deleted"])
    suggestiontriggertype = _create_enum(
        "suggestiontriggertype",
        ["content_idea", "timing_optimization", "audience_targeting",
         "channel_selection", "budget_allocation", "campaign_optimization"],
    )
    recommendationcategory = _create_enum(
        "recommendationcategory",
        ["content", "timing", "audience", "channel", "budget", "creative"],
    )
    recommendationstatus = _create_enum(
        "recommendationstatus", ["pending", "applied", "dismissed"]
    )
    userfeedback = _create_enum(
        "userfeedback", ["helpful", "not_helpful", "applied", "dismissed"]
    )

    # -- Social module enums -------------------------------------------------
    socialplatform = _create_enum(
        "socialplatform",
        ["instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps"],
    )
    accountstatus = _create_enum(
        "accountstatus", ["active", "disconnected", "error"]
    )
    poststatus = _create_enum(
        "poststatus", ["draft", "scheduled", "published", "failed"]
    )
    commentstatus = _create_enum(
        "commentstatus", ["new", "read", "replied"]
    )
    commentsentiment = _create_enum(
        "commentsentiment", ["positive", "negative", "neutral"]
    )
    messagedirection = _create_enum(
        "messagedirection", ["inbound", "outbound"]
    )
    messagestatus = _create_enum(
        "messagestatus", ["new", "read", "replied"]
    )

    # -- Media module enums --------------------------------------------------
    storageprovider = _create_enum(
        "storageprovider", ["local", "s3", "r2"]
    )
    mediastatus = _create_enum(
        "mediastatus", ["uploading", "processing", "ready", "error", "deleted"]
    )
    varianttype = _create_enum(
        "varianttype",
        ["thumbnail", "webp", "optimized", "resized", "small", "medium",
         "large", "video_thumbnail"],
    )
    analysistype = _create_enum(
        "analysistype", ["caption", "hashtag", "score", "objects"]
    )

    # -- Events module enums -------------------------------------------------
    eventcategory_enum = _create_enum(
        "eventcategory_enum", ["system", "business", "integration"]
    )
    handler_type_enum = _create_enum(
        "handler_type_enum", ["webhook", "function", "notification"]
    )
    eventlog_status_enum = _create_enum(
        "eventlog_status_enum", ["pending", "processing", "completed", "failed"]
    )
    handler_type_exec_enum = _create_enum(
        "handler_type_exec_enum", ["webhook", "function", "notification"]
    )
    handler_status_enum = _create_enum(
        "handler_status_enum", ["pending", "running", "completed", "failed"]
    )
    resolution_status_enum = _create_enum(
        "resolution_status_enum", ["unresolved", "resolved", "ignored"]
    )
    automation_execution_status_enum = _create_enum(
        "automation_execution_status_enum",
        ["pending", "running", "completed", "failed"],
    )

    # -- Billing module enums ------------------------------------------------
    substatus = _create_enum(
        "substatus", ["trial", "active", "cancelled", "past_due", "expired"]
    )
    billingcycle = _create_enum(
        "billingcycle", ["monthly", "yearly"]
    )
    usageresourcetype = _create_enum(
        "usageresourcetype",
        ["ai_request", "social_post", "storage", "api_call", "sms", "email"],
    )
    quotaperiod = _create_enum(
        "quotaperiod", ["daily", "monthly"]
    )
    invoicestatus = _create_enum(
        "invoicestatus", ["draft", "open", "paid", "void"]
    )
    featurename = _create_enum(
        "featurename",
        ["ai_content", "social_api", "webhook", "automation",
         "advanced_analytics", "erp_integration", "multi_branch",
         "custom_branding", "priority_support", "api_access"],
    )
    billingeventtype = _create_enum(
        "billingeventtype",
        ["subscription_created", "subscription_renewed", "subscription_cancelled",
         "subscription_upgraded", "subscription_downgraded", "usage_threshold",
         "quota_exceeded", "quota_warning", "invoice_generated", "invoice_paid",
         "invoice_overdue", "payment_failed", "payment_succeeded",
         "feature_enabled", "feature_disabled"],
    )
    quotaresourcetype = _create_enum(
        "quotaresourcetype",
        ["ai_request", "social_post", "storage", "api_call", "sms", "email"],
    )

    # -- Audit module enums --------------------------------------------------
    auditaction = _create_enum(
        "auditaction",
        ["create", "read", "update", "delete", "login", "logout",
         "export", "import", "api_call", "permission_denied", "token_refresh",
         "password_change", "mfa_enabled", "mfa_disabled", "role_changed",
         "settings_changed"],
    )
    resourcetype_audit = _create_enum(
        "resourcetype_audit",
        ["user", "company", "branch", "campaign", "audience", "template",
         "analytics", "integration", "api_key", "settings", "auth",
         "data_export", "data_import", "notification"],
    )
    securityeventtype = _create_enum(
        "securityeventtype",
        ["suspicious_login", "rate_limit_exceeded", "permission_denied",
         "data_exfiltration", "unusual_activity", "brute_force_attempt",
         "off_hours_access", "geo_anomaly", "token_reuse", "account_lockout",
         "privilege_escalation", "tenant_leak", "secret_leak",
         "xss_attempt", "sql_injection_attempt"],
    )
    severitylevel = _create_enum(
        "severitylevel", ["low", "medium", "high", "critical"]
    )
    loginstatus = _create_enum(
        "loginstatus", ["success", "failed", "blocked"]
    )
    dataaccessaction = _create_enum(
        "dataaccessaction", ["read", "create", "update", "delete"]
    )

    # ========================================================================
    # 2. AI MODULE TABLES (7 tables)
    # ========================================================================

    # -- ai_prompts ----------------------------------------------------------
    op.create_table(
        "ai_prompts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column(
            "model_name",
            sa.Enum("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", name="aimodelname"),
            server_default="gpt-4o-mini",
            nullable=False,
        ),
        sa.Column("temperature", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default="2048", nullable=False),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_prompts")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_ai_prompts_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_ai_prompts_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Reusable AI prompt templates with variable support",
    )
    op.create_index(op.f("ix_ai_prompts_id"), "ai_prompts", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_prompts_company_id"), "ai_prompts", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_prompts_branch_id"), "ai_prompts", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_prompts_name"), "ai_prompts", ["name"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_prompts_created_at"), "ai_prompts", ["created_at"], unique=False, schema=None)

    # -- ai_conversations ----------------------------------------------------
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "model",
            sa.Enum("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", name="aimodelname"),
            nullable=False,
        ),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "archived", "deleted", name="conversationstatus"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_conversations")),
        sa.UniqueConstraint("session_id", name=op.f("uq_ai_conversations_session_id")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_ai_conversations_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_ai_conversations_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_ai_conversations_user_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_id"], ["ai_prompts.id"],
            name=op.f("fk_ai_conversations_prompt_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="AI chat conversation sessions",
    )
    op.create_index(op.f("ix_ai_conversations_id"), "ai_conversations", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_conversations_company_id"), "ai_conversations", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_conversations_branch_id"), "ai_conversations", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_conversations_user_id"), "ai_conversations", ["user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_conversations_prompt_id"), "ai_conversations", ["prompt_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_conversations_session_id"), "ai_conversations", ["session_id"], unique=True, schema=None)
    op.create_index(op.f("ix_ai_conversations_created_at"), "ai_conversations", ["created_at"], unique=False, schema=None)

    # -- ai_messages ---------------------------------------------------------
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", "system", "tool", name="messagerole"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "model",
            sa.Enum("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", name="aimodelname"),
            nullable=True,
        ),
        sa.Column("finish_reason", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_messages")),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"],
            name=op.f("fk_ai_messages_conversation_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Individual messages within AI conversations",
    )
    op.create_index(op.f("ix_ai_messages_id"), "ai_messages", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_messages_conversation_id"), "ai_messages", ["conversation_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_messages_created_at"), "ai_messages", ["created_at"], unique=False, schema=None)

    # -- ai_suggestions ------------------------------------------------------
    op.create_table(
        "ai_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column(
            "trigger_type",
            sa.Enum(
                "content_idea", "timing_optimization", "audience_targeting",
                "channel_selection", "budget_allocation", "campaign_optimization",
                name="suggestiontriggertype",
            ),
            nullable=False,
        ),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("prompt_used", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "model",
            sa.Enum("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", name="aimodelname"),
            nullable=False,
        ),
        sa.Column("was_applied", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "user_feedback",
            sa.Enum("helpful", "not_helpful", "applied", "dismissed", name="userfeedback"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_suggestions")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_ai_suggestions_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_ai_suggestions_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="AI-generated marketing suggestions with feedback tracking",
    )
    op.create_index(op.f("ix_ai_suggestions_id"), "ai_suggestions", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_suggestions_company_id"), "ai_suggestions", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_suggestions_branch_id"), "ai_suggestions", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_suggestions_trigger_type"), "ai_suggestions", ["trigger_type"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_suggestions_created_at"), "ai_suggestions", ["created_at"], unique=False, schema=None)

    # -- ai_recommendations --------------------------------------------------
    op.create_table(
        "ai_recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column(
            "category",
            sa.Enum("content", "timing", "audience", "channel", "budget", "creative", name="recommendationcategory"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("data_source", sa.String(length=255), nullable=True),
        sa.Column("action_items", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "applied", "dismissed", name="recommendationstatus"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_recommendations")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_ai_recommendations_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_ai_recommendations_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Data-driven marketing recommendations",
    )
    op.create_index(op.f("ix_ai_recommendations_id"), "ai_recommendations", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_recommendations_company_id"), "ai_recommendations", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_recommendations_branch_id"), "ai_recommendations", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_recommendations_category"), "ai_recommendations", ["category"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_recommendations_status"), "ai_recommendations", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_recommendations_created_at"), "ai_recommendations", ["created_at"], unique=False, schema=None)

    # -- ai_usage_logs -------------------------------------------------------
    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "model",
            sa.Enum("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", name="aimodelname"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("tokens_input", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_output", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_estimate", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_logs")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_ai_usage_logs_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_ai_usage_logs_user_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="AI API usage logs for cost and token tracking",
    )
    op.create_index(op.f("ix_ai_usage_logs_id"), "ai_usage_logs", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_usage_logs_company_id"), "ai_usage_logs", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_usage_logs_user_id"), "ai_usage_logs", ["user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_usage_logs_status"), "ai_usage_logs", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_usage_logs_created_at"), "ai_usage_logs", ["created_at"], unique=False, schema=None)

    # -- ai_cache ------------------------------------------------------------
    op.create_table(
        "ai_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column(
            "model",
            sa.Enum("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", name="aimodelname"),
            nullable=False,
        ),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_cache")),
        sa.UniqueConstraint("cache_key", name=op.f("uq_ai_cache_cache_key")),
        schema=None,
        comment="Cache of AI completion responses",
    )
    op.create_index(op.f("ix_ai_cache_id"), "ai_cache", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_cache_cache_key"), "ai_cache", ["cache_key"], unique=True, schema=None)
    op.create_index(op.f("ix_ai_cache_prompt_hash"), "ai_cache", ["prompt_hash"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_cache_expires_at"), "ai_cache", ["expires_at"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_cache_created_at"), "ai_cache", ["created_at"], unique=False, schema=None)

    # ========================================================================
    # 3. SOCIAL MODULE TABLES (7 tables)
    # ========================================================================

    # -- social_accounts -----------------------------------------------------
    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column(
            "platform",
            sa.Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps", name="socialplatform"),
            nullable=False,
        ),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_id", sa.String(length=255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("profile_url", sa.String(length=500), nullable=True),
        sa.Column("follower_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "disconnected", "error", name="accountstatus"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_accounts")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_accounts_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_social_accounts_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Connected social media account credentials and metadata",
    )
    op.create_index(op.f("ix_social_accounts_id"), "social_accounts", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_accounts_company_id"), "social_accounts", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_accounts_branch_id"), "social_accounts", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_accounts_platform"), "social_accounts", ["platform"], unique=False, schema=None)
    op.create_index(op.f("ix_social_accounts_status"), "social_accounts", ["status"], unique=False, schema=None)
    op.create_index("ix_social_accounts_company_platform", "social_accounts", ["company_id", "platform"], unique=False, schema=None)
    op.create_index("ix_social_accounts_branch", "social_accounts", ["branch_id", "company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_accounts_created_at"), "social_accounts", ["created_at"], unique=False, schema=None)

    # -- social_posts --------------------------------------------------------
    op.create_table(
        "social_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps", name="socialplatform"),
            nullable=False,
        ),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("media_urls", sa.JSON(), nullable=False),
        sa.Column("hashtags", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "scheduled", "published", "failed", name="poststatus"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("engagement_stats", sa.JSON(), nullable=False),
        sa.Column("ai_generated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_posts")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_posts_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_social_posts_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["social_accounts.id"],
            name=op.f("fk_social_posts_account_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Social media post content and scheduling",
    )
    op.create_index(op.f("ix_social_posts_id"), "social_posts", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_company_id"), "social_posts", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_branch_id"), "social_posts", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_account_id"), "social_posts", ["account_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_external_post_id"), "social_posts", ["external_post_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_status"), "social_posts", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_scheduled_at"), "social_posts", ["scheduled_at"], unique=False, schema=None)
    op.create_index("ix_social_posts_company_status", "social_posts", ["company_id", "status"], unique=False, schema=None)
    op.create_index("ix_social_posts_account_status", "social_posts", ["account_id", "status"], unique=False, schema=None)
    op.create_index(op.f("ix_social_posts_created_at"), "social_posts", ["created_at"], unique=False, schema=None)

    # -- social_comments -----------------------------------------------------
    op.create_table(
        "social_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("external_comment_id", sa.String(length=255), nullable=True),
        sa.Column("parent_comment_id", sa.String(length=255), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=False),
        sa.Column("author_id", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "sentiment",
            sa.Enum("positive", "negative", "neutral", name="commentsentiment"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("new", "read", "replied", name="commentstatus"),
            server_default="new",
            nullable=False,
        ),
        sa.Column("replied_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_comments")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_comments_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_social_comments_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["social_accounts.id"],
            name=op.f("fk_social_comments_account_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"], ["social_posts.id"],
            name=op.f("fk_social_comments_post_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Comments on social media posts",
    )
    op.create_index(op.f("ix_social_comments_id"), "social_comments", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_company_id"), "social_comments", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_branch_id"), "social_comments", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_account_id"), "social_comments", ["account_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_post_id"), "social_comments", ["post_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_external_comment_id"), "social_comments", ["external_comment_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_status"), "social_comments", ["status"], unique=False, schema=None)
    op.create_index("ix_social_comments_company_status", "social_comments", ["company_id", "status"], unique=False, schema=None)
    op.create_index("ix_social_comments_post_created", "social_comments", ["post_id", "created_at"], unique=False, schema=None)
    op.create_index(op.f("ix_social_comments_created_at"), "social_comments", ["created_at"], unique=False, schema=None)

    # -- social_messages -----------------------------------------------------
    op.create_table(
        "social_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps", name="socialplatform"),
            nullable=False,
        ),
        sa.Column("external_conversation_id", sa.String(length=255), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("sender_name", sa.String(length=255), nullable=False),
        sa.Column("sender_id", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "direction",
            sa.Enum("inbound", "outbound", name="messagedirection"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("new", "read", "replied", name="messagestatus"),
            server_default="new",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_messages")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_messages_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_social_messages_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["social_accounts.id"],
            name=op.f("fk_social_messages_account_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Direct/conversation messages from social platforms",
    )
    op.create_index(op.f("ix_social_messages_id"), "social_messages", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_company_id"), "social_messages", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_branch_id"), "social_messages", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_account_id"), "social_messages", ["account_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_external_conversation_id"), "social_messages", ["external_conversation_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_external_message_id"), "social_messages", ["external_message_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_status"), "social_messages", ["status"], unique=False, schema=None)
    op.create_index("ix_social_messages_company_conv", "social_messages", ["company_id", "external_conversation_id"], unique=False, schema=None)
    op.create_index("ix_social_messages_account_created", "social_messages", ["account_id", "created_at"], unique=False, schema=None)
    op.create_index(op.f("ix_social_messages_created_at"), "social_messages", ["created_at"], unique=False, schema=None)

    # -- social_analytics ----------------------------------------------------
    op.create_table(
        "social_analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps", name="socialplatform"),
            nullable=False,
        ),
        sa.Column("metric_date", sa.DateTime(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("reach", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("engagement", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("clicks", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("shares", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("comments", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("likes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("followers_gained", sa.Integer(), server_default="0", nullable=False),
        sa.Column("followers_lost", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_analytics")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_analytics_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_social_analytics_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["social_accounts.id"],
            name=op.f("fk_social_analytics_account_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Daily social media analytics snapshots",
    )
    op.create_index(op.f("ix_social_analytics_id"), "social_analytics", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_analytics_company_id"), "social_analytics", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_analytics_branch_id"), "social_analytics", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_analytics_account_id"), "social_analytics", ["account_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_analytics_metric_date"), "social_analytics", ["metric_date"], unique=False, schema=None)
    op.create_index("ix_social_analytics_account_date", "social_analytics", ["account_id", "metric_date"], unique=False, schema=None)
    op.create_index("ix_social_analytics_company_date", "social_analytics", ["company_id", "metric_date"], unique=False, schema=None)
    op.create_index(op.f("ix_social_analytics_created_at"), "social_analytics", ["created_at"], unique=False, schema=None)

    # -- social_competitors --------------------------------------------------
    op.create_table(
        "social_competitors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column(
            "platform",
            sa.Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps", name="socialplatform"),
            nullable=False,
        ),
        sa.Column("competitor_name", sa.String(length=255), nullable=False),
        sa.Column("competitor_account_id", sa.String(length=255), nullable=False),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("post_count", sa.Integer(), nullable=True),
        sa.Column("avg_engagement", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("last_analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("metrics_history", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_competitors")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_competitors_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_social_competitors_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Tracked competitor accounts for competitive analysis",
    )
    op.create_index(op.f("ix_social_competitors_id"), "social_competitors", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_competitors_company_id"), "social_competitors", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_competitors_branch_id"), "social_competitors", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_competitors_platform"), "social_competitors", ["platform"], unique=False, schema=None)
    op.create_index("ix_social_competitors_company", "social_competitors", ["company_id", "platform"], unique=False, schema=None)
    op.create_index(op.f("ix_social_competitors_created_at"), "social_competitors", ["created_at"], unique=False, schema=None)

    # -- social_webhooks -----------------------------------------------------
    op.create_table(
        "social_webhooks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column(
            "platform",
            sa.Enum("instagram", "facebook", "tiktok", "whatsapp", "telegram", "google_maps", name="socialplatform"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_webhooks")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_social_webhooks_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["social_accounts.id"],
            name=op.f("fk_social_webhooks_account_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Received webhook events from social media platforms",
    )
    op.create_index(op.f("ix_social_webhooks_id"), "social_webhooks", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_webhooks_company_id"), "social_webhooks", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_webhooks_account_id"), "social_webhooks", ["account_id"], unique=False, schema=None)
    op.create_index(op.f("ix_social_webhooks_platform"), "social_webhooks", ["platform"], unique=False, schema=None)
    op.create_index(op.f("ix_social_webhooks_event_type"), "social_webhooks", ["event_type"], unique=False, schema=None)
    op.create_index(op.f("ix_social_webhooks_processed"), "social_webhooks", ["processed"], unique=False, schema=None)
    op.create_index("ix_social_webhooks_company_processed", "social_webhooks", ["company_id", "processed"], unique=False, schema=None)
    op.create_index("ix_social_webhooks_platform_event", "social_webhooks", ["platform", "event_type"], unique=False, schema=None)
    op.create_index(op.f("ix_social_webhooks_created_at"), "social_webhooks", ["created_at"], unique=False, schema=None)

    # ========================================================================
    # 4. MEDIA MODULE TABLES (8 tables)
    # ========================================================================

    # -- media_assets --------------------------------------------------------
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column(
            "storage_provider",
            sa.Enum("local", "s3", "r2", name="storageprovider"),
            server_default="local",
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("uploading", "processing", "ready", "error", "deleted", name="mediastatus"),
            server_default="uploading",
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
        sa.UniqueConstraint("filename", name=op.f("uq_media_assets_filename")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_media_assets_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_media_assets_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_media_assets_created_by"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Core media assets (images, videos, documents)",
    )
    op.create_index(op.f("ix_media_assets_id"), "media_assets", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_assets_company_id"), "media_assets", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_assets_branch_id"), "media_assets", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_assets_filename"), "media_assets", ["filename"], unique=True, schema=None)
    op.create_index(op.f("ix_media_assets_mime_type"), "media_assets", ["mime_type"], unique=False, schema=None)
    op.create_index(op.f("ix_media_assets_category"), "media_assets", ["category"], unique=False, schema=None)
    op.create_index(op.f("ix_media_assets_status"), "media_assets", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_media_assets_created_at"), "media_assets", ["created_at"], unique=False, schema=None)

    # -- media_variants ------------------------------------------------------
    op.create_table(
        "media_variants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("media_id", sa.String(length=36), nullable=False),
        sa.Column(
            "variant_type",
            sa.Enum(
                "thumbnail", "webp", "optimized", "resized", "small", "medium",
                "large", "video_thumbnail", name="varianttype",
            ),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quality", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_variants")),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media_assets.id"],
            name=op.f("fk_media_variants_media_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Derived media variants (thumbnails, webp, optimized)",
    )
    op.create_index(op.f("ix_media_variants_media_id"), "media_variants", ["media_id"], unique=False, schema=None)

    # -- media_tags ----------------------------------------------------------
    op.create_table(
        "media_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), server_default="#6366F1", nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_tags")),
        sa.UniqueConstraint("company_id", "name", name=op.f("uq_media_tags_company_name")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_media_tags_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Company-scoped tags for media organization",
    )
    op.create_index(op.f("ix_media_tags_id"), "media_tags", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_tags_company_id"), "media_tags", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_tags_name"), "media_tags", ["name"], unique=False, schema=None)

    # -- media_tag_mappings --------------------------------------------------
    op.create_table(
        "media_tag_mappings",
        sa.Column("media_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("media_id", "tag_id", name=op.f("pk_media_tag_mappings")),
        sa.UniqueConstraint("media_id", "tag_id", name=op.f("uq_media_tag_mapping")),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media_assets.id"],
            name=op.f("fk_media_tag_mappings_media_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["media_tags.id"],
            name=op.f("fk_media_tag_mappings_tag_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Media asset to tag mappings",
    )

    # -- media_collections ---------------------------------------------------
    op.create_table(
        "media_collections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_media_id", sa.String(length=36), nullable=True),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_collections")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_media_collections_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_media_collections_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cover_media_id"], ["media_assets.id"],
            name=op.f("fk_media_collections_cover_media_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Named collections of media assets",
    )
    op.create_index(op.f("ix_media_collections_id"), "media_collections", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_collections_company_id"), "media_collections", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_collections_branch_id"), "media_collections", ["branch_id"], unique=False, schema=None)

    # -- media_collection_items ----------------------------------------------
    op.create_table(
        "media_collection_items",
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("added_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("collection_id", "media_id", name=op.f("pk_media_collection_items")),
        sa.UniqueConstraint("collection_id", "media_id", name=op.f("uq_collection_media_item")),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["media_collections.id"],
            name=op.f("fk_media_collection_items_collection_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media_assets.id"],
            name=op.f("fk_media_collection_items_media_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Ordered items within media collections",
    )

    # -- media_analytics -----------------------------------------------------
    op.create_table(
        "media_analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("media_id", sa.String(length=36), nullable=False),
        sa.Column("views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("downloads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_analytics")),
        sa.UniqueConstraint("media_id", name=op.f("uq_media_analytics_media_id")),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media_assets.id"],
            name=op.f("fk_media_analytics_media_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="View and download counters per media asset",
    )
    op.create_index(op.f("ix_media_analytics_id"), "media_analytics", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_media_analytics_media_id"), "media_analytics", ["media_id"], unique=True, schema=None)

    # -- ai_image_analysis ---------------------------------------------------
    op.create_table(
        "ai_image_analysis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("media_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "analysis_type",
            sa.Enum("caption", "hashtag", "score", "objects", name="analysistype"),
            nullable=False,
        ),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_image_analysis")),
        sa.UniqueConstraint("media_id", "analysis_type", name=op.f("uq_ai_analysis_media_type")),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media_assets.id"],
            name=op.f("fk_ai_image_analysis_media_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_ai_image_analysis_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="AI-generated analysis results for media assets",
    )
    op.create_index(op.f("ix_ai_image_analysis_id"), "ai_image_analysis", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_image_analysis_media_id"), "ai_image_analysis", ["media_id"], unique=False, schema=None)
    op.create_index(op.f("ix_ai_image_analysis_company_id"), "ai_image_analysis", ["company_id"], unique=False, schema=None)

    # ========================================================================
    # 5. EVENTS MODULE TABLES (7 tables)
    # ========================================================================

    # -- event_definitions ---------------------------------------------------
    op.create_table(
        "event_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload_schema", sa.JSON(), nullable=True),
        sa.Column(
            "category",
            sa.Enum("system", "business", "integration", name="eventcategory_enum"),
            server_default="system",
            nullable=False,
        ),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_definitions")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_event_definitions_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Registry of event types and schemas",
    )
    op.create_index(op.f("ix_event_definitions_id"), "event_definitions", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_definitions_company_id"), "event_definitions", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_definitions_event_name"), "event_definitions", ["event_name"], unique=False, schema=None)
    op.create_index(op.f("ix_event_definitions_category"), "event_definitions", ["category"], unique=False, schema=None)

    # -- event_subscriptions -------------------------------------------------
    op.create_table(
        "event_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column(
            "handler_type",
            sa.Enum("webhook", "function", "notification", name="handler_type_enum"),
            nullable=False,
        ),
        sa.Column("handler_config", sa.JSON(), nullable=False),
        sa.Column("filter_conditions", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("retry_policy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_subscriptions")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_event_subscriptions_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Subscriptions linking events to handler configurations",
    )
    op.create_index(op.f("ix_event_subscriptions_id"), "event_subscriptions", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_subscriptions_company_id"), "event_subscriptions", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_subscriptions_event_name"), "event_subscriptions", ["event_name"], unique=False, schema=None)
    op.create_index(op.f("ix_event_subscriptions_is_active"), "event_subscriptions", ["is_active"], unique=False, schema=None)
    op.create_index(op.f("ix_event_subscriptions_created_at"), "event_subscriptions", ["created_at"], unique=False, schema=None)

    # -- event_log -----------------------------------------------------------
    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_module", sa.String(length=64), nullable=True),
        sa.Column("source_user_id", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="eventlog_status_enum"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_log")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_event_log_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_event_log_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_user_id"], ["users.id"],
            name=op.f("fk_event_log_source_user_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Immutable log of all published events",
    )
    op.create_index(op.f("ix_event_log_id"), "event_log", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_company_id"), "event_log", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_branch_id"), "event_log", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_event_name"), "event_log", ["event_name"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_source_module"), "event_log", ["source_module"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_correlation_id"), "event_log", ["correlation_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_status"), "event_log", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_source_user_id"), "event_log", ["source_user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_log_created_at"), "event_log", ["created_at"], unique=False, schema=None)

    # -- event_handlers ------------------------------------------------------
    op.create_table(
        "event_handlers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_log_id", sa.Integer(), nullable=False),
        sa.Column(
            "handler_type",
            sa.Enum("webhook", "function", "notification", name="handler_type_exec_enum"),
            nullable=False,
        ),
        sa.Column("handler_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="handler_status_enum"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_handlers")),
        sa.ForeignKeyConstraint(
            ["event_log_id"], ["event_log.id"],
            name=op.f("fk_event_handlers_event_log_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Individual handler execution records",
    )
    op.create_index(op.f("ix_event_handlers_id"), "event_handlers", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_handlers_event_log_id"), "event_handlers", ["event_log_id"], unique=False, schema=None)
    op.create_index(op.f("ix_event_handlers_status"), "event_handlers", ["status"], unique=False, schema=None)

    # -- dead_letter_events --------------------------------------------------
    op.create_table(
        "dead_letter_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_log_id", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("retry_exhausted_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("original_payload", sa.JSON(), nullable=False),
        sa.Column(
            "resolution_status",
            sa.Enum("unresolved", "resolved", "ignored", name="resolution_status_enum"),
            server_default="unresolved",
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dead_letter_events")),
        sa.UniqueConstraint("event_log_id", name=op.f("uq_dead_letter_events_event_log_id")),
        sa.ForeignKeyConstraint(
            ["event_log_id"], ["event_log.id"],
            name=op.f("fk_dead_letter_events_event_log_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["users.id"],
            name=op.f("fk_dead_letter_events_resolved_by"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Dead letter queue for failed events",
    )
    op.create_index(op.f("ix_dead_letter_events_id"), "dead_letter_events", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_dead_letter_events_event_log_id"), "dead_letter_events", ["event_log_id"], unique=True, schema=None)
    op.create_index(op.f("ix_dead_letter_events_resolution_status"), "dead_letter_events", ["resolution_status"], unique=False, schema=None)
    op.create_index(op.f("ix_dead_letter_events_resolved_by"), "dead_letter_events", ["resolved_by"], unique=False, schema=None)
    op.create_index(op.f("ix_dead_letter_events_created_at"), "dead_letter_events", ["created_at"], unique=False, schema=None)

    # -- automation_rules ----------------------------------------------------
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_event", sa.String(length=128), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_rules")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_automation_rules_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_automation_rules_branch_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Automation rules: trigger-event -> conditions -> actions",
    )
    op.create_index(op.f("ix_automation_rules_id"), "automation_rules", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_rules_company_id"), "automation_rules", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_rules_branch_id"), "automation_rules", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_rules_trigger_event"), "automation_rules", ["trigger_event"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_rules_is_active"), "automation_rules", ["is_active"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_rules_created_at"), "automation_rules", ["created_at"], unique=False, schema=None)

    # -- automation_executions -----------------------------------------------
    op.create_table(
        "automation_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("trigger_event_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="automation_execution_status_enum"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("actions_executed", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_executions")),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["automation_rules.id"],
            name=op.f("fk_automation_executions_rule_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_event_id"], ["event_log.id"],
            name=op.f("fk_automation_executions_trigger_event_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Execution audit trail for automation rules",
    )
    op.create_index(op.f("ix_automation_executions_id"), "automation_executions", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_executions_rule_id"), "automation_executions", ["rule_id"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_executions_trigger_event_id"), "automation_executions", ["trigger_event_id"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_executions_status"), "automation_executions", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_automation_executions_created_at"), "automation_executions", ["created_at"], unique=False, schema=None)

    # ========================================================================
    # 6. BILLING MODULE TABLES (7 tables)
    # ========================================================================

    # -- subscription_plans --------------------------------------------------
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_monthly", sa.Numeric(precision=10, scale=2), server_default="0.00", nullable=False),
        sa.Column("price_yearly", sa.Numeric(precision=10, scale=2), server_default="0.00", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_plans")),
        schema=None,
        comment="Available subscription plan tiers with pricing and limits",
    )
    op.create_index(op.f("ix_subscription_plans_id"), "subscription_plans", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_subscription_plans_is_active"), "subscription_plans", ["is_active"], unique=False, schema=None)
    op.create_index(op.f("ix_subscription_plans_created_at"), "subscription_plans", ["created_at"], unique=False, schema=None)

    # -- company_subscriptions -----------------------------------------------
    op.create_table(
        "company_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("trial", "active", "cancelled", "past_due", "expired", name="substatus"),
            server_default="trial",
            nullable=False,
        ),
        sa.Column(
            "billing_cycle",
            sa.Enum("monthly", "yearly", name="billingcycle"),
            server_default="monthly",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("current_period_start", sa.DateTime(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("payment_method_id", sa.String(length=255), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_subscriptions")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_company_subscriptions_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["subscription_plans.id"],
            name=op.f("fk_company_subscriptions_plan_id"),
            ondelete="RESTRICT", onupdate="CASCADE",
        ),
        schema=None,
        comment="Company subscription records with lifecycle tracking",
    )
    op.create_index(op.f("ix_company_subscriptions_id"), "company_subscriptions", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_company_subscriptions_company_id"), "company_subscriptions", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_company_subscriptions_plan_id"), "company_subscriptions", ["plan_id"], unique=False, schema=None)
    op.create_index(op.f("ix_company_subscriptions_status"), "company_subscriptions", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_company_subscriptions_created_at"), "company_subscriptions", ["created_at"], unique=False, schema=None)

    # -- usage_records -------------------------------------------------------
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum("ai_request", "social_post", "storage", "api_call", "sms", "email", name="usageresourcetype"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("cost", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_records")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_usage_records_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Resource usage records for billing and analytics",
    )
    op.create_index(op.f("ix_usage_records_id"), "usage_records", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_usage_records_company_id"), "usage_records", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_usage_records_resource_type"), "usage_records", ["resource_type"], unique=False, schema=None)
    op.create_index(op.f("ix_usage_records_recorded_at"), "usage_records", ["recorded_at"], unique=False, schema=None)

    # -- usage_quotas --------------------------------------------------------
    op.create_table(
        "usage_quotas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum("ai_request", "social_post", "storage", "api_call", "sms", "email", name="quotaresourcetype"),
            nullable=False,
        ),
        sa.Column("limit_amount", sa.Integer(), nullable=False),
        sa.Column("current_usage", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "period",
            sa.Enum("daily", "monthly", name="quotaperiod"),
            server_default="monthly",
            nullable=False,
        ),
        sa.Column("reset_at", sa.DateTime(), nullable=False),
        sa.Column("warning_sent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_quotas")),
        sa.UniqueConstraint("company_id", "resource_type", "period", name=op.f("uq_usage_quotas_company_resource_period")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_usage_quotas_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Per-company resource usage quotas and current consumption",
    )
    op.create_index(op.f("ix_usage_quotas_id"), "usage_quotas", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_usage_quotas_company_id"), "usage_quotas", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_usage_quotas_resource_type"), "usage_quotas", ["resource_type"], unique=False, schema=None)
    op.create_index(op.f("ix_usage_quotas_created_at"), "usage_quotas", ["created_at"], unique=False, schema=None)

    # -- invoices ------------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "open", "paid", "void", name="invoicestatus"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("total", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("line_items", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("invoice_number", name=op.f("uq_invoices_invoice_number")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_invoices_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Customer invoices with line items and payment tracking",
    )
    op.create_index(op.f("ix_invoices_id"), "invoices", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_invoices_company_id"), "invoices", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_invoices_invoice_number"), "invoices", ["invoice_number"], unique=True, schema=None)
    op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_invoices_due_date"), "invoices", ["due_date"], unique=False, schema=None)
    op.create_index(op.f("ix_invoices_created_at"), "invoices", ["created_at"], unique=False, schema=None)

    # -- feature_flags -------------------------------------------------------
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "feature_name",
            sa.Enum(
                "ai_content", "social_api", "webhook", "automation",
                "advanced_analytics", "erp_integration", "multi_branch",
                "custom_branding", "priority_support", "api_access",
                name="featurename",
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enabled_by", sa.Integer(), nullable=True),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_flags")),
        sa.UniqueConstraint("company_id", "feature_name", name=op.f("uq_feature_flags_company_feature")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_feature_flags_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["enabled_by"], ["users.id"],
            name=op.f("fk_feature_flags_enabled_by"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Per-company feature enablement flags",
    )
    op.create_index(op.f("ix_feature_flags_id"), "feature_flags", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_feature_flags_company_id"), "feature_flags", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_feature_flags_feature_name"), "feature_flags", ["feature_name"], unique=False, schema=None)
    op.create_index(op.f("ix_feature_flags_enabled"), "feature_flags", ["enabled"], unique=False, schema=None)
    op.create_index(op.f("ix_feature_flags_created_at"), "feature_flags", ["created_at"], unique=False, schema=None)

    # -- billing_events ------------------------------------------------------
    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "subscription_created", "subscription_renewed", "subscription_cancelled",
                "subscription_upgraded", "subscription_downgraded", "usage_threshold",
                "quota_exceeded", "quota_warning", "invoice_generated", "invoice_paid",
                "invoice_overdue", "payment_failed", "payment_succeeded",
                "feature_enabled", "feature_disabled",
                name="billingeventtype",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_events")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_billing_events_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Billing event audit log",
    )
    op.create_index(op.f("ix_billing_events_id"), "billing_events", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_billing_events_company_id"), "billing_events", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_billing_events_event_type"), "billing_events", ["event_type"], unique=False, schema=None)
    op.create_index(op.f("ix_billing_events_created_at"), "billing_events", ["created_at"], unique=False, schema=None)

    # ========================================================================
    # 7. AUDIT MODULE TABLES (5 tables)
    # ========================================================================

    # -- audit_logs ----------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "create", "read", "update", "delete", "login", "logout",
                "export", "import", "api_call", "permission_denied", "token_refresh",
                "password_change", "mfa_enabled", "mfa_disabled", "role_changed",
                "settings_changed",
                name="auditaction",
            ),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.Enum(
                "user", "company", "branch", "campaign", "audience", "template",
                "analytics", "integration", "api_key", "settings", "auth",
                "data_export", "data_import", "notification",
                name="resourcetype_audit",
            ),
            nullable=False,
        ),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="success", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_audit_logs_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"],
            name=op.f("fk_audit_logs_branch_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_audit_logs_user_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Audit trail for all operations",
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_company_id"), "audit_logs", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_branch_id"), "audit_logs", ["branch_id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_resource_type"), "audit_logs", ["resource_type"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_resource_id"), "audit_logs", ["resource_id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_ip_address"), "audit_logs", ["ip_address"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_session_id"), "audit_logs", ["session_id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_correlation_id"), "audit_logs", ["correlation_id"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_status"), "audit_logs", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False, schema=None)

    # -- security_events -----------------------------------------------------
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "suspicious_login", "rate_limit_exceeded", "permission_denied",
                "data_exfiltration", "unusual_activity", "brute_force_attempt",
                "off_hours_access", "geo_anomaly", "token_reuse", "account_lockout",
                "privilege_escalation", "tenant_leak", "secret_leak",
                "xss_attempt", "sql_injection_attempt",
                name="securityeventtype",
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="severitylevel"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_security_events_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_security_events_user_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["users.id"],
            name=op.f("fk_security_events_resolved_by"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Security events and alerts",
    )
    op.create_index(op.f("ix_security_events_id"), "security_events", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_company_id"), "security_events", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_event_type"), "security_events", ["event_type"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_severity"), "security_events", ["severity"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_source_ip"), "security_events", ["source_ip"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_user_id"), "security_events", ["user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_resolved"), "security_events", ["resolved"], unique=False, schema=None)
    op.create_index(op.f("ix_security_events_created_at"), "security_events", ["created_at"], unique=False, schema=None)

    # -- login_attempts ------------------------------------------------------
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("success", "failed", "blocked", name="loginstatus"),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_login_attempts_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Login attempts tracking",
    )
    op.create_index(op.f("ix_login_attempts_id"), "login_attempts", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_login_attempts_company_id"), "login_attempts", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_login_attempts_email"), "login_attempts", ["email"], unique=False, schema=None)
    op.create_index(op.f("ix_login_attempts_ip_address"), "login_attempts", ["ip_address"], unique=False, schema=None)
    op.create_index(op.f("ix_login_attempts_status"), "login_attempts", ["status"], unique=False, schema=None)
    op.create_index(op.f("ix_login_attempts_created_at"), "login_attempts", ["created_at"], unique=False, schema=None)

    # -- api_keys ------------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_api_keys_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_api_keys_user_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        schema=None,
        comment="Scoped API keys",
    )
    op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_api_keys_company_id"), "api_keys", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_api_keys_expires_at"), "api_keys", ["expires_at"], unique=False, schema=None)
    op.create_index(op.f("ix_api_keys_is_active"), "api_keys", ["is_active"], unique=False, schema=None)
    op.create_index(op.f("ix_api_keys_created_at"), "api_keys", ["created_at"], unique=False, schema=None)

    # -- data_access_logs ----------------------------------------------------
    op.create_table(
        "data_access_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=False),
        sa.Column(
            "action",
            sa.Enum("read", "create", "update", "delete", name="dataaccessaction"),
            nullable=False,
        ),
        sa.Column("accessed_fields", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_access_logs")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_data_access_logs_company_id"),
            ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_data_access_logs_user_id"),
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        schema=None,
        comment="Data access logs for compliance",
    )
    op.create_index(op.f("ix_data_access_logs_id"), "data_access_logs", ["id"], unique=False, schema=None)
    op.create_index(op.f("ix_data_access_logs_company_id"), "data_access_logs", ["company_id"], unique=False, schema=None)
    op.create_index(op.f("ix_data_access_logs_user_id"), "data_access_logs", ["user_id"], unique=False, schema=None)
    op.create_index(op.f("ix_data_access_logs_table_name"), "data_access_logs", ["table_name"], unique=False, schema=None)
    op.create_index(op.f("ix_data_access_logs_record_id"), "data_access_logs", ["record_id"], unique=False, schema=None)
    op.create_index(op.f("ix_data_access_logs_action"), "data_access_logs", ["action"], unique=False, schema=None)
    op.create_index(op.f("ix_data_access_logs_created_at"), "data_access_logs", ["created_at"], unique=False, schema=None)

    # ========================================================================
    # 8. SEED DATA
    # ========================================================================

    # Seed default subscription plans
    op.bulk_insert(
        sa.table(
            "subscription_plans",
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("price_monthly", sa.Numeric),
            sa.column("price_yearly", sa.Numeric),
            sa.column("currency", sa.String),
            sa.column("features", sa.JSON),
            sa.column("limits", sa.JSON),
            sa.column("is_active", sa.Boolean),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "name": "Starter",
                "description": "Basic plan for small businesses getting started with AI marketing.",
                "price_monthly": 29.00,
                "price_yearly": 290.00,
                "currency": "USD",
                "features": '{"ai_content": true, "social_api": true, "webhook": false, "automation": false, "advanced_analytics": false, "erp_integration": false, "multi_branch": false, "custom_branding": false, "priority_support": false, "api_access": false}',
                "limits": '{"max_branches": 1, "max_users": 2, "ai_requests_monthly": 500, "social_posts_monthly": 50, "storage_gb": 5}',
                "is_active": True,
                "sort_order": 1,
            },
            {
                "name": "Pro",
                "description": "Professional plan for growing businesses with advanced needs.",
                "price_monthly": 99.00,
                "price_yearly": 990.00,
                "currency": "USD",
                "features": '{"ai_content": true, "social_api": true, "webhook": true, "automation": true, "advanced_analytics": true, "erp_integration": true, "multi_branch": true, "custom_branding": true, "priority_support": false, "api_access": false}',
                "limits": '{"max_branches": 5, "max_users": 10, "ai_requests_monthly": 5000, "social_posts_monthly": 500, "storage_gb": 50}',
                "is_active": True,
                "sort_order": 2,
            },
            {
                "name": "Enterprise",
                "description": "Full-featured plan for large organizations with custom requirements.",
                "price_monthly": 299.00,
                "price_yearly": 2990.00,
                "currency": "USD",
                "features": '{"ai_content": true, "social_api": true, "webhook": true, "automation": true, "advanced_analytics": true, "erp_integration": true, "multi_branch": true, "custom_branding": true, "priority_support": true, "api_access": true}',
                "limits": '{"max_branches": 50, "max_users": 100, "ai_requests_monthly": 50000, "social_posts_monthly": 5000, "storage_gb": 500}',
                "is_active": True,
                "sort_order": 3,
            },
        ],
    )


def downgrade() -> None:
    """Drop all consolidated tables and ENUMs in reverse dependency order."""

    # -- Drop tables: AUDIT module (5) ---------------------------------------
    op.drop_index(op.f("ix_data_access_logs_created_at"), table_name="data_access_logs", schema=None)
    op.drop_index(op.f("ix_data_access_logs_action"), table_name="data_access_logs", schema=None)
    op.drop_index(op.f("ix_data_access_logs_record_id"), table_name="data_access_logs", schema=None)
    op.drop_index(op.f("ix_data_access_logs_table_name"), table_name="data_access_logs", schema=None)
    op.drop_index(op.f("ix_data_access_logs_user_id"), table_name="data_access_logs", schema=None)
    op.drop_index(op.f("ix_data_access_logs_company_id"), table_name="data_access_logs", schema=None)
    op.drop_index(op.f("ix_data_access_logs_id"), table_name="data_access_logs", schema=None)
    op.drop_table("data_access_logs", schema=None)

    op.drop_index(op.f("ix_api_keys_created_at"), table_name="api_keys", schema=None)
    op.drop_index(op.f("ix_api_keys_is_active"), table_name="api_keys", schema=None)
    op.drop_index(op.f("ix_api_keys_expires_at"), table_name="api_keys", schema=None)
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys", schema=None)
    op.drop_index(op.f("ix_api_keys_company_id"), table_name="api_keys", schema=None)
    op.drop_index(op.f("ix_api_keys_id"), table_name="api_keys", schema=None)
    op.drop_table("api_keys", schema=None)

    op.drop_index(op.f("ix_login_attempts_created_at"), table_name="login_attempts", schema=None)
    op.drop_index(op.f("ix_login_attempts_status"), table_name="login_attempts", schema=None)
    op.drop_index(op.f("ix_login_attempts_ip_address"), table_name="login_attempts", schema=None)
    op.drop_index(op.f("ix_login_attempts_email"), table_name="login_attempts", schema=None)
    op.drop_index(op.f("ix_login_attempts_company_id"), table_name="login_attempts", schema=None)
    op.drop_index(op.f("ix_login_attempts_id"), table_name="login_attempts", schema=None)
    op.drop_table("login_attempts", schema=None)

    op.drop_index(op.f("ix_security_events_created_at"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_resolved"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_user_id"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_source_ip"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_severity"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_event_type"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_company_id"), table_name="security_events", schema=None)
    op.drop_index(op.f("ix_security_events_id"), table_name="security_events", schema=None)
    op.drop_table("security_events", schema=None)

    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_status"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_correlation_id"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_session_id"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_ip_address"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_resource_id"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_resource_type"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_branch_id"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_company_id"), table_name="audit_logs", schema=None)
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs", schema=None)
    op.drop_table("audit_logs", schema=None)

    # -- Drop tables: BILLING module (7) -------------------------------------
    op.drop_index(op.f("ix_billing_events_created_at"), table_name="billing_events", schema=None)
    op.drop_index(op.f("ix_billing_events_event_type"), table_name="billing_events", schema=None)
    op.drop_index(op.f("ix_billing_events_company_id"), table_name="billing_events", schema=None)
    op.drop_index(op.f("ix_billing_events_id"), table_name="billing_events", schema=None)
    op.drop_table("billing_events", schema=None)

    op.drop_index(op.f("ix_feature_flags_created_at"), table_name="feature_flags", schema=None)
    op.drop_index(op.f("ix_feature_flags_enabled"), table_name="feature_flags", schema=None)
    op.drop_index(op.f("ix_feature_flags_feature_name"), table_name="feature_flags", schema=None)
    op.drop_index(op.f("ix_feature_flags_company_id"), table_name="feature_flags", schema=None)
    op.drop_index(op.f("ix_feature_flags_id"), table_name="feature_flags", schema=None)
    op.drop_table("feature_flags", schema=None)

    op.drop_index(op.f("ix_invoices_created_at"), table_name="invoices", schema=None)
    op.drop_index(op.f("ix_invoices_due_date"), table_name="invoices", schema=None)
    op.drop_index(op.f("ix_invoices_status"), table_name="invoices", schema=None)
    op.drop_index(op.f("ix_invoices_invoice_number"), table_name="invoices", schema=None)
    op.drop_index(op.f("ix_invoices_company_id"), table_name="invoices", schema=None)
    op.drop_index(op.f("ix_invoices_id"), table_name="invoices", schema=None)
    op.drop_table("invoices", schema=None)

    op.drop_index(op.f("ix_usage_quotas_created_at"), table_name="usage_quotas", schema=None)
    op.drop_index(op.f("ix_usage_quotas_resource_type"), table_name="usage_quotas", schema=None)
    op.drop_index(op.f("ix_usage_quotas_company_id"), table_name="usage_quotas", schema=None)
    op.drop_index(op.f("ix_usage_quotas_id"), table_name="usage_quotas", schema=None)
    op.drop_table("usage_quotas", schema=None)

    op.drop_index(op.f("ix_usage_records_recorded_at"), table_name="usage_records", schema=None)
    op.drop_index(op.f("ix_usage_records_resource_type"), table_name="usage_records", schema=None)
    op.drop_index(op.f("ix_usage_records_company_id"), table_name="usage_records", schema=None)
    op.drop_index(op.f("ix_usage_records_id"), table_name="usage_records", schema=None)
    op.drop_table("usage_records", schema=None)

    op.drop_index(op.f("ix_company_subscriptions_created_at"), table_name="company_subscriptions", schema=None)
    op.drop_index(op.f("ix_company_subscriptions_status"), table_name="company_subscriptions", schema=None)
    op.drop_index(op.f("ix_company_subscriptions_plan_id"), table_name="company_subscriptions", schema=None)
    op.drop_index(op.f("ix_company_subscriptions_company_id"), table_name="company_subscriptions", schema=None)
    op.drop_index(op.f("ix_company_subscriptions_id"), table_name="company_subscriptions", schema=None)
    op.drop_table("company_subscriptions", schema=None)

    op.drop_index(op.f("ix_subscription_plans_created_at"), table_name="subscription_plans", schema=None)
    op.drop_index(op.f("ix_subscription_plans_is_active"), table_name="subscription_plans", schema=None)
    op.drop_index(op.f("ix_subscription_plans_id"), table_name="subscription_plans", schema=None)
    op.drop_table("subscription_plans", schema=None)

    # -- Drop tables: EVENTS module (7) --------------------------------------
    op.drop_index(op.f("ix_automation_executions_created_at"), table_name="automation_executions", schema=None)
    op.drop_index(op.f("ix_automation_executions_status"), table_name="automation_executions", schema=None)
    op.drop_index(op.f("ix_automation_executions_trigger_event_id"), table_name="automation_executions", schema=None)
    op.drop_index(op.f("ix_automation_executions_rule_id"), table_name="automation_executions", schema=None)
    op.drop_index(op.f("ix_automation_executions_id"), table_name="automation_executions", schema=None)
    op.drop_table("automation_executions", schema=None)

    op.drop_index(op.f("ix_automation_rules_created_at"), table_name="automation_rules", schema=None)
    op.drop_index(op.f("ix_automation_rules_is_active"), table_name="automation_rules", schema=None)
    op.drop_index(op.f("ix_automation_rules_trigger_event"), table_name="automation_rules", schema=None)
    op.drop_index(op.f("ix_automation_rules_branch_id"), table_name="automation_rules", schema=None)
    op.drop_index(op.f("ix_automation_rules_company_id"), table_name="automation_rules", schema=None)
    op.drop_index(op.f("ix_automation_rules_id"), table_name="automation_rules", schema=None)
    op.drop_table("automation_rules", schema=None)

    op.drop_index(op.f("ix_dead_letter_events_created_at"), table_name="dead_letter_events", schema=None)
    op.drop_index(op.f("ix_dead_letter_events_resolved_by"), table_name="dead_letter_events", schema=None)
    op.drop_index(op.f("ix_dead_letter_events_resolution_status"), table_name="dead_letter_events", schema=None)
    op.drop_index(op.f("ix_dead_letter_events_event_log_id"), table_name="dead_letter_events", schema=None)
    op.drop_index(op.f("ix_dead_letter_events_id"), table_name="dead_letter_events", schema=None)
    op.drop_table("dead_letter_events", schema=None)

    op.drop_index(op.f("ix_event_handlers_status"), table_name="event_handlers", schema=None)
    op.drop_index(op.f("ix_event_handlers_event_log_id"), table_name="event_handlers", schema=None)
    op.drop_index(op.f("ix_event_handlers_id"), table_name="event_handlers", schema=None)
    op.drop_table("event_handlers", schema=None)

    op.drop_index(op.f("ix_event_log_created_at"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_status"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_correlation_id"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_source_module"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_event_name"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_branch_id"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_company_id"), table_name="event_log", schema=None)
    op.drop_index(op.f("ix_event_log_id"), table_name="event_log", schema=None)
    op.drop_table("event_log", schema=None)

    op.drop_index(op.f("ix_event_subscriptions_created_at"), table_name="event_subscriptions", schema=None)
    op.drop_index(op.f("ix_event_subscriptions_is_active"), table_name="event_subscriptions", schema=None)
    op.drop_index(op.f("ix_event_subscriptions_event_name"), table_name="event_subscriptions", schema=None)
    op.drop_index(op.f("ix_event_subscriptions_company_id"), table_name="event_subscriptions", schema=None)
    op.drop_index(op.f("ix_event_subscriptions_id"), table_name="event_subscriptions", schema=None)
    op.drop_table("event_subscriptions", schema=None)

    op.drop_index(op.f("ix_event_definitions_category"), table_name="event_definitions", schema=None)
    op.drop_index(op.f("ix_event_definitions_event_name"), table_name="event_definitions", schema=None)
    op.drop_index(op.f("ix_event_definitions_company_id"), table_name="event_definitions", schema=None)
    op.drop_index(op.f("ix_event_definitions_id"), table_name="event_definitions", schema=None)
    op.drop_table("event_definitions", schema=None)

    # -- Drop tables: MEDIA module (8) ---------------------------------------
    op.drop_index(op.f("ix_ai_image_analysis_company_id"), table_name="ai_image_analysis", schema=None)
    op.drop_index(op.f("ix_ai_image_analysis_media_id"), table_name="ai_image_analysis", schema=None)
    op.drop_index(op.f("ix_ai_image_analysis_id"), table_name="ai_image_analysis", schema=None)
    op.drop_table("ai_image_analysis", schema=None)

    op.drop_index(op.f("ix_media_analytics_media_id"), table_name="media_analytics", schema=None)
    op.drop_index(op.f("ix_media_analytics_id"), table_name="media_analytics", schema=None)
    op.drop_table("media_analytics", schema=None)

    op.drop_table("media_collection_items", schema=None)

    op.drop_index(op.f("ix_media_collections_branch_id"), table_name="media_collections", schema=None)
    op.drop_index(op.f("ix_media_collections_company_id"), table_name="media_collections", schema=None)
    op.drop_index(op.f("ix_media_collections_id"), table_name="media_collections", schema=None)
    op.drop_table("media_collections", schema=None)

    op.drop_table("media_tag_mappings", schema=None)

    op.drop_index(op.f("ix_media_tags_name"), table_name="media_tags", schema=None)
    op.drop_index(op.f("ix_media_tags_company_id"), table_name="media_tags", schema=None)
    op.drop_index(op.f("ix_media_tags_id"), table_name="media_tags", schema=None)
    op.drop_table("media_tags", schema=None)

    op.drop_index(op.f("ix_media_variants_media_id"), table_name="media_variants", schema=None)
    op.drop_table("media_variants", schema=None)

    op.drop_index(op.f("ix_media_assets_created_at"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_status"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_category"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_mime_type"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_filename"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_branch_id"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_company_id"), table_name="media_assets", schema=None)
    op.drop_index(op.f("ix_media_assets_id"), table_name="media_assets", schema=None)
    op.drop_table("media_assets", schema=None)

    # -- Drop tables: SOCIAL module (7) --------------------------------------
    op.drop_index(op.f("ix_social_webhooks_created_at"), table_name="social_webhooks", schema=None)
    op.drop_index("ix_social_webhooks_platform_event", table_name="social_webhooks", schema=None)
    op.drop_index("ix_social_webhooks_company_processed", table_name="social_webhooks", schema=None)
    op.drop_index(op.f("ix_social_webhooks_processed"), table_name="social_webhooks", schema=None)
    op.drop_index(op.f("ix_social_webhooks_event_type"), table_name="social_webhooks", schema=None)
    op.drop_index(op.f("ix_social_webhooks_platform"), table_name="social_webhooks", schema=None)
    op.drop_index(op.f("ix_social_webhooks_account_id"), table_name="social_webhooks", schema=None)
    op.drop_index(op.f("ix_social_webhooks_company_id"), table_name="social_webhooks", schema=None)
    op.drop_index(op.f("ix_social_webhooks_id"), table_name="social_webhooks", schema=None)
    op.drop_table("social_webhooks", schema=None)

    op.drop_index(op.f("ix_social_competitors_created_at"), table_name="social_competitors", schema=None)
    op.drop_index("ix_social_competitors_company", table_name="social_competitors", schema=None)
    op.drop_index(op.f("ix_social_competitors_platform"), table_name="social_competitors", schema=None)
    op.drop_index(op.f("ix_social_competitors_branch_id"), table_name="social_competitors", schema=None)
    op.drop_index(op.f("ix_social_competitors_company_id"), table_name="social_competitors", schema=None)
    op.drop_index(op.f("ix_social_competitors_id"), table_name="social_competitors", schema=None)
    op.drop_table("social_competitors", schema=None)

    op.drop_index(op.f("ix_social_analytics_created_at"), table_name="social_analytics", schema=None)
    op.drop_index("ix_social_analytics_company_date", table_name="social_analytics", schema=None)
    op.drop_index("ix_social_analytics_account_date", table_name="social_analytics", schema=None)
    op.drop_index(op.f("ix_social_analytics_metric_date"), table_name="social_analytics", schema=None)
    op.drop_index(op.f("ix_social_analytics_account_id"), table_name="social_analytics", schema=None)
    op.drop_index(op.f("ix_social_analytics_branch_id"), table_name="social_analytics", schema=None)
    op.drop_index(op.f("ix_social_analytics_company_id"), table_name="social_analytics", schema=None)
    op.drop_index(op.f("ix_social_analytics_id"), table_name="social_analytics", schema=None)
    op.drop_table("social_analytics", schema=None)

    op.drop_index(op.f("ix_social_messages_created_at"), table_name="social_messages", schema=None)
    op.drop_index("ix_social_messages_account_created", table_name="social_messages", schema=None)
    op.drop_index("ix_social_messages_company_conv", table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_status"), table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_external_message_id"), table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_external_conversation_id"), table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_account_id"), table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_branch_id"), table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_company_id"), table_name="social_messages", schema=None)
    op.drop_index(op.f("ix_social_messages_id"), table_name="social_messages", schema=None)
    op.drop_table("social_messages", schema=None)

    op.drop_index(op.f("ix_social_comments_created_at"), table_name="social_comments", schema=None)
    op.drop_index("ix_social_comments_post_created", table_name="social_comments", schema=None)
    op.drop_index("ix_social_comments_company_status", table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_status"), table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_external_comment_id"), table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_post_id"), table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_account_id"), table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_branch_id"), table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_company_id"), table_name="social_comments", schema=None)
    op.drop_index(op.f("ix_social_comments_id"), table_name="social_comments", schema=None)
    op.drop_table("social_comments", schema=None)

    op.drop_index(op.f("ix_social_posts_created_at"), table_name="social_posts", schema=None)
    op.drop_index("ix_social_posts_account_status", table_name="social_posts", schema=None)
    op.drop_index("ix_social_posts_company_status", table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_scheduled_at"), table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_status"), table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_external_post_id"), table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_account_id"), table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_branch_id"), table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_company_id"), table_name="social_posts", schema=None)
    op.drop_index(op.f("ix_social_posts_id"), table_name="social_posts", schema=None)
    op.drop_table("social_posts", schema=None)

    op.drop_index(op.f("ix_social_accounts_created_at"), table_name="social_accounts", schema=None)
    op.drop_index("ix_social_accounts_branch", table_name="social_accounts", schema=None)
    op.drop_index("ix_social_accounts_company_platform", table_name="social_accounts", schema=None)
    op.drop_index(op.f("ix_social_accounts_status"), table_name="social_accounts", schema=None)
    op.drop_index(op.f("ix_social_accounts_platform"), table_name="social_accounts", schema=None)
    op.drop_index(op.f("ix_social_accounts_branch_id"), table_name="social_accounts", schema=None)
    op.drop_index(op.f("ix_social_accounts_company_id"), table_name="social_accounts", schema=None)
    op.drop_index(op.f("ix_social_accounts_id"), table_name="social_accounts", schema=None)
    op.drop_table("social_accounts", schema=None)

    # -- Drop tables: AI module (7) ------------------------------------------
    op.drop_index(op.f("ix_ai_cache_created_at"), table_name="ai_cache", schema=None)
    op.drop_index(op.f("ix_ai_cache_expires_at"), table_name="ai_cache", schema=None)
    op.drop_index(op.f("ix_ai_cache_prompt_hash"), table_name="ai_cache", schema=None)
    op.drop_index(op.f("ix_ai_cache_cache_key"), table_name="ai_cache", schema=None)
    op.drop_index(op.f("ix_ai_cache_id"), table_name="ai_cache", schema=None)
    op.drop_table("ai_cache", schema=None)

    op.drop_index(op.f("ix_ai_usage_logs_created_at"), table_name="ai_usage_logs", schema=None)
    op.drop_index(op.f("ix_ai_usage_logs_status"), table_name="ai_usage_logs", schema=None)
    op.drop_index(op.f("ix_ai_usage_logs_user_id"), table_name="ai_usage_logs", schema=None)
    op.drop_index(op.f("ix_ai_usage_logs_company_id"), table_name="ai_usage_logs", schema=None)
    op.drop_index(op.f("ix_ai_usage_logs_id"), table_name="ai_usage_logs", schema=None)
    op.drop_table("ai_usage_logs", schema=None)

    op.drop_index(op.f("ix_ai_recommendations_created_at"), table_name="ai_recommendations", schema=None)
    op.drop_index(op.f("ix_ai_recommendations_status"), table_name="ai_recommendations", schema=None)
    op.drop_index(op.f("ix_ai_recommendations_category"), table_name="ai_recommendations", schema=None)
    op.drop_index(op.f("ix_ai_recommendations_branch_id"), table_name="ai_recommendations", schema=None)
    op.drop_index(op.f("ix_ai_recommendations_company_id"), table_name="ai_recommendations", schema=None)
    op.drop_index(op.f("ix_ai_recommendations_id"), table_name="ai_recommendations", schema=None)
    op.drop_table("ai_recommendations", schema=None)

    op.drop_index(op.f("ix_ai_suggestions_created_at"), table_name="ai_suggestions", schema=None)
    op.drop_index(op.f("ix_ai_suggestions_trigger_type"), table_name="ai_suggestions", schema=None)
    op.drop_index(op.f("ix_ai_suggestions_branch_id"), table_name="ai_suggestions", schema=None)
    op.drop_index(op.f("ix_ai_suggestions_company_id"), table_name="ai_suggestions", schema=None)
    op.drop_index(op.f("ix_ai_suggestions_id"), table_name="ai_suggestions", schema=None)
    op.drop_table("ai_suggestions", schema=None)

    op.drop_index(op.f("ix_ai_messages_created_at"), table_name="ai_messages", schema=None)
    op.drop_index(op.f("ix_ai_messages_conversation_id"), table_name="ai_messages", schema=None)
    op.drop_index(op.f("ix_ai_messages_id"), table_name="ai_messages", schema=None)
    op.drop_table("ai_messages", schema=None)

    op.drop_index(op.f("ix_ai_conversations_created_at"), table_name="ai_conversations", schema=None)
    op.drop_index(op.f("ix_ai_conversations_session_id"), table_name="ai_conversations", schema=None)
    op.drop_index(op.f("ix_ai_conversations_prompt_id"), table_name="ai_conversations", schema=None)
    op.drop_index(op.f("ix_ai_conversations_user_id"), table_name="ai_conversations", schema=None)
    op.drop_index(op.f("ix_ai_conversations_branch_id"), table_name="ai_conversations", schema=None)
    op.drop_index(op.f("ix_ai_conversations_company_id"), table_name="ai_conversations", schema=None)
    op.drop_index(op.f("ix_ai_conversations_id"), table_name="ai_conversations", schema=None)
    op.drop_table("ai_conversations", schema=None)

    op.drop_index(op.f("ix_ai_prompts_created_at"), table_name="ai_prompts", schema=None)
    op.drop_index(op.f("ix_ai_prompts_name"), table_name="ai_prompts", schema=None)
    op.drop_index(op.f("ix_ai_prompts_branch_id"), table_name="ai_prompts", schema=None)
    op.drop_index(op.f("ix_ai_prompts_company_id"), table_name="ai_prompts", schema=None)
    op.drop_index(op.f("ix_ai_prompts_id"), table_name="ai_prompts", schema=None)
    op.drop_table("ai_prompts", schema=None)

    # ========================================================================
    # 8. DROP ENUM TYPES (reverse order)
    # ========================================================================

    # Audit enums
    _drop_enum("dataaccessaction")
    _drop_enum("loginstatus")
    _drop_enum("severitylevel")
    _drop_enum("securityeventtype")
    _drop_enum("resourcetype_audit")
    _drop_enum("auditaction")

    # Billing enums
    _drop_enum("billingeventtype")
    _drop_enum("featurename")
    _drop_enum("invoicestatus")
    _drop_enum("quotaperiod")
    _drop_enum("quotaresourcetype")
    _drop_enum("usageresourcetype")
    _drop_enum("billingcycle")
    _drop_enum("substatus")

    # Events enums
    _drop_enum("automation_execution_status_enum")
    _drop_enum("resolution_status_enum")
    _drop_enum("handler_status_enum")
    _drop_enum("handler_type_exec_enum")
    _drop_enum("eventlog_status_enum")
    _drop_enum("handler_type_enum")
    _drop_enum("eventcategory_enum")

    # Media enums
    _drop_enum("analysistype")
    _drop_enum("varianttype")
    _drop_enum("mediastatus")
    _drop_enum("storageprovider")

    # Social enums
    _drop_enum("messagestatus")
    _drop_enum("messagedirection")
    _drop_enum("commentsentiment")
    _drop_enum("commentstatus")
    _drop_enum("poststatus")
    _drop_enum("accountstatus")
    _drop_enum("socialplatform")

    # AI enums
    _drop_enum("userfeedback")
    _drop_enum("recommendationstatus")
    _drop_enum("recommendationcategory")
    _drop_enum("suggestiontriggertype")
    _drop_enum("conversationstatus")
    _drop_enum("messagerole")
    _drop_enum("aimodelname")
