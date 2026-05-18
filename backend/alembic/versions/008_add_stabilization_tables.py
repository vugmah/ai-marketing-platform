"""Add stabilization tables (18 tables across 6 modules)

Revision ID: 008
Revises: 007
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stabilization tables for P1-P6 modules."""

    # --- P5: AI Cost ---
    op.create_table(
        "ai_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("period", sa.String(20), nullable=False, server_default=sa.text("'monthly'")),
        sa.Column("budget_usd", sa.Numeric(12, 4), nullable=False, server_default=sa.text('100.0')),
        sa.Column("spent_usd", sa.Numeric(12, 4), nullable=False, server_default=sa.text('0.0')),
        sa.Column("alert_threshold_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text('80.0')),
        sa.Column("hard_limit_usd", sa.Numeric(12, 4), nullable=False, server_default=sa.text('200.0')),
        sa.Column("model_tier", sa.String(20), nullable=False, server_default=sa.text("'balanced'")),
        sa.Column("fallback_model", sa.String(50), nullable=True, server_default=sa.text("'gpt-4o-mini'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_ab_company", "ai_budgets", ["company_id"])
    op.create_index("ix_ab_branch", "ai_budgets", ["branch_id"])

    # --- P3: AI Safety ---
    op.create_table(
        "ai_critical_action_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("requires_erp_verification", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("min_confidence_threshold", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.85')),
        sa.Column("auto_block_if_unverified", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_acap_company", "ai_critical_action_policies", ["company_id"])

    op.create_table(
        "ai_fact_check_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False, index=True),
        sa.Column("ai_response_id", sa.Integer(), nullable=False, index=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(50), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("erp_check_result", sa.JSON(), nullable=True),
        sa.Column("menu_check_result", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=False, server_default=sa.text('0.0')),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_afcl_conversation", "ai_fact_check_logs", ["conversation_id"])
    op.create_index("ix_afcl_status", "ai_fact_check_logs", ["verification_status"])

    # --- P5: AI Cost ---
    op.create_table(
        "ai_model_pricing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(50), nullable=False, unique=True),
        sa.Column("input_cost_per_1k", sa.Numeric(10, 6), nullable=False),
        sa.Column("output_cost_per_1k", sa.Numeric(10, 6), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("quality_tier", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_amp_model", "ai_model_pricing", ["model_name"])

    # --- P2: Localization ---
    op.create_table(
        "ai_prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default=sa.text("'tr'")),
        sa.Column("system_prompt", sa.String(4000), nullable=False),
        sa.Column("user_prompt_template", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_apt_key_lang", "ai_prompt_templates", ["template_key", "language"])

    # --- P5: AI Cost ---
    op.create_table(
        "ai_token_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=True, index=True),
        sa.Column("user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("request_id", sa.String(100), nullable=False, index=True),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=False, server_default=sa.text('0.0')),
        sa.Column("request_type", sa.String(50), nullable=False, server_default=sa.text("'chat'")),
        sa.Column("priority", sa.String(20), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_atu_company", "ai_token_usage", ["company_id"])
    op.create_index("ix_atu_branch", "ai_token_usage", ["branch_id"])
    op.create_index("ix_atu_model", "ai_token_usage", ["model_name"])
    op.create_index("ix_atu_date", "ai_token_usage", ["created_at"])

    # --- P1: API Versioning ---
    op.create_table(
        "api_changelog",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=True, index=True),
        sa.Column("version", sa.String(10), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("migration_required", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("migration_steps", sa.Text(), nullable=True),
        sa.Column("announced_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("effective_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_acl_version", "api_changelog", ["version"])
    op.create_index("ix_acl_company", "api_changelog", ["company_id"])

    op.create_table(
        "api_contract_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("endpoint_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("request_schema", sa.JSON(), nullable=True),
        sa.Column("response_schema", sa.JSON(), nullable=True),
        sa.Column("query_params", sa.JSON(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_acs_endpoint", "api_contract_snapshots", ["endpoint_id"])

    op.create_table(
        "api_endpoint_lifecycles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=True, index=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("version", sa.String(10), nullable=False, server_default=sa.text("'v2'")),
        sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default=sa.text("'stable'")),
        sa.Column("introduced_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("deprecated_at", sa.DateTime(), nullable=True),
        sa.Column("sunset_at", sa.DateTime(), nullable=True),
        sa.Column("removal_version", sa.String(10), nullable=True),
        sa.Column("alternative_endpoint", sa.String(500), nullable=True),
        sa.Column("breaking_changes", sa.JSON(), nullable=False),
        sa.Column("migration_guide", sa.Text(), nullable=True),
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_ael_endpoint", "api_endpoint_lifecycles", ["method", "path"])
    op.create_index("ix_ael_status", "api_endpoint_lifecycles", ["lifecycle_status"])
    op.create_index("ix_ael_company", "api_endpoint_lifecycles", ["company_id"])

    op.create_table(
        "api_version_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("current_version", sa.String(10), nullable=False, server_default=sa.text("'v2'")),
        sa.Column("min_supported_version", sa.String(10), nullable=False, server_default=sa.text("'v2'")),
        sa.Column("deprecation_notice_days", sa.Integer(), nullable=False, server_default=sa.text('90')),
        sa.Column("breaking_change_notification", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("auto_add_headers", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_avp_company", "api_version_policies", ["company_id"])

    # --- P2: Localization ---
    op.create_table(
        "branch_locale_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("branch_id", sa.Integer(), nullable=False, index=True),
        sa.Column("language", sa.String(5), nullable=False, server_default=sa.text("'tr'")),
        sa.Column("timezone", sa.String(100), nullable=False, server_default=sa.text("'Europe/Istanbul'")),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'TRY'")),
        sa.Column("date_format", sa.String(20), nullable=False, server_default=sa.text("'%d.%m.%Y'")),
        sa.Column("time_format", sa.String(20), nullable=False, server_default=sa.text("'%H:%M'")),
        sa.Column("number_format_decimal", sa.String(1), nullable=False, server_default=sa.text("','")),
        sa.Column("number_format_thousand", sa.String(1), nullable=False, server_default=sa.text("'.'")),
        sa.Column("first_day_of_week", sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_bls_branch", "branch_locale_settings", ["branch_id"])

    op.create_table(
        "localization_strings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("value", sa.String(2000), nullable=False),
        sa.Column("module", sa.String(50), nullable=False, server_default=sa.text("'general'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_ls_key_lang", "localization_strings", ["key", "language"])
    op.create_index("ix_ls_module", "localization_strings", ["module"])

    # --- P6: Support Ops ---
    op.create_table(
        "operator_workloads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("operator_id", sa.Integer(), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("active_tickets", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("max_capacity", sa.Integer(), nullable=False, server_default=sa.text('10')),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'online'")),
        sa.Column("avg_response_time_sec", sa.Integer(), nullable=True),
        sa.Column("satisfaction_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("last_assigned_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_ow_operator", "operator_workloads", ["operator_id"])

    # --- P4: Permissions ---
    op.create_table(
        "permission_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_pd_scope", "permission_definitions", ["scope"])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("role_id", sa.Integer(), nullable=False, index=True),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("branch_scope", sa.String(20), nullable=False, server_default=sa.text("'all'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_rp_role_perm", "role_permissions", ["role_id", "permission_id"])
    op.create_index("ix_rp_company", "role_permissions", ["company_id"])

    # --- P6: Support Ops ---
    op.create_table(
        "support_analytics_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("total_tickets", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("resolved_tickets", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("avg_resolution_time_min", sa.Integer(), nullable=True),
        sa.Column("sla_breach_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("avg_satisfaction", sa.Numeric(3, 2), nullable=True),
        sa.Column("ai_handled_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("escalated_count", sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_sad_company_date", "support_analytics_daily", ["company_id", "date"])

    op.create_table(
        "support_escalation_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("trigger_condition", sa.String(50), nullable=False),
        sa.Column("trigger_value", sa.String(200), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_operator_id", sa.Integer(), nullable=True),
        sa.Column("target_supervisor_id", sa.Integer(), nullable=True),
        sa.Column("notification_channels", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_ser_company", "support_escalation_rules", ["company_id"])

    # --- P4: Permissions ---
    op.create_table(
        "user_permission_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        schema=None,
    )
    op.create_index("ix_upo_user_perm", "user_permission_overrides", ["user_id", "permission_id"])



def downgrade() -> None:
    """Drop stabilization tables."""

    op.drop_table("user_permission_overrides", schema=None)
    op.drop_table("support_escalation_rules", schema=None)
    op.drop_table("support_analytics_daily", schema=None)
    op.drop_table("role_permissions", schema=None)
    op.drop_table("permission_definitions", schema=None)
    op.drop_table("operator_workloads", schema=None)
    op.drop_table("localization_strings", schema=None)
    op.drop_table("branch_locale_settings", schema=None)
    op.drop_table("api_version_policies", schema=None)
    op.drop_table("api_endpoint_lifecycles", schema=None)
    op.drop_table("api_contract_snapshots", schema=None)
    op.drop_table("api_changelog", schema=None)
    op.drop_table("ai_token_usage", schema=None)
    op.drop_table("ai_prompt_templates", schema=None)
    op.drop_table("ai_model_pricing", schema=None)
    op.drop_table("ai_fact_check_logs", schema=None)
    op.drop_table("ai_critical_action_policies", schema=None)
    op.drop_table("ai_budgets", schema=None)