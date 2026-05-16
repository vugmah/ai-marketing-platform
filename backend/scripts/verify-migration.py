#!/usr/bin/env python3
"""
Migration verification script for the AI Marketing Platform database.

Connects to MySQL/PostgreSQL using DATABASE_URL, verifies that all expected
tables exist, checks foreign key constraints, validates index existence,
and reports any missing or incorrect schema elements.

Usage:
    python verify-migration.py [--verbose] [--fix]

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Any

# Try SQLAlchemy async first, fall back to sync
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text as sql_text


# ---------------------------------------------------------------------------
# Expected schema definition
# ---------------------------------------------------------------------------

EXPECTED_TABLES: set[str] = {
    # Core tables (from 001_initial)
    "companies", "branches", "users",
    # ERP tables (from 002_erp_integration)
    "erp_connections", "erp_sync_jobs", "erp_sync_logs", "erp_field_mappings",
    "erp_products", "erp_inventory", "erp_sales_orders", "erp_customers",
    "erp_invoices", "erp_payments",
    # AI tables (from 003_consolidated)
    "ai_prompts", "ai_conversations", "ai_messages", "ai_suggestions",
    "ai_recommendations", "ai_usage_logs", "ai_cache",
    # Social tables
    "social_accounts", "social_posts", "social_comments", "social_messages",
    "social_analytics", "social_competitors", "social_webhooks",
    # Media tables
    "media_assets", "media_variants", "media_tags", "media_tag_mappings",
    "media_collections", "media_collection_items", "media_analytics",
    "ai_image_analysis",
    # Events tables
    "event_definitions", "event_subscriptions", "event_log", "event_handlers",
    "dead_letter_events", "automation_rules", "automation_executions",
    # Billing tables
    "subscription_plans", "company_subscriptions", "usage_records",
    "usage_quotas", "invoices", "feature_flags", "billing_events",
    # Audit tables
    "audit_logs", "security_events", "login_attempts", "api_keys",
    "data_access_logs",
}

EXPECTED_FOREIGN_KEYS: dict[str, list[str]] = {
    "users": ["fk_users_company_id", "fk_users_branch_id"],
    "branches": ["fk_branches_company_id"],
    "erp_connections": ["fk_erp_connections_company_id", "fk_erp_connections_branch_id"],
    "erp_sync_jobs": ["fk_erp_sync_jobs_company_id", "fk_erp_sync_jobs_branch_id", "fk_erp_sync_jobs_connection_id"],
    "erp_sync_logs": ["fk_erp_sync_logs_company_id", "fk_erp_sync_logs_job_id", "fk_erp_sync_logs_connection_id"],
    "erp_field_mappings": ["fk_erp_field_mappings_company_id", "fk_erp_field_mappings_connection_id"],
    "erp_products": ["fk_erp_products_company_id", "fk_erp_products_branch_id", "fk_erp_products_connection_id"],
    "erp_inventory": ["fk_erp_inventory_company_id", "fk_erp_inventory_branch_id", "fk_erp_inventory_connection_id", "fk_erp_inventory_product_id"],
    "erp_sales_orders": ["fk_erp_sales_orders_company_id", "fk_erp_sales_orders_branch_id", "fk_erp_sales_orders_connection_id"],
    "erp_customers": ["fk_erp_customers_company_id", "fk_erp_customers_branch_id", "fk_erp_customers_connection_id"],
    "erp_invoices": ["fk_erp_invoices_company_id", "fk_erp_invoices_branch_id", "fk_erp_invoices_connection_id", "fk_erp_invoices_sales_order_id"],
    "erp_payments": ["fk_erp_payments_company_id", "fk_erp_payments_branch_id", "fk_erp_payments_connection_id", "fk_erp_payments_invoice_id"],
    "ai_prompts": ["fk_ai_prompts_company_id", "fk_ai_prompts_branch_id"],
    "ai_conversations": ["fk_ai_conversations_company_id", "fk_ai_conversations_branch_id", "fk_ai_conversations_user_id", "fk_ai_conversations_prompt_id"],
    "ai_messages": ["fk_ai_messages_conversation_id"],
    "ai_suggestions": ["fk_ai_suggestions_company_id", "fk_ai_suggestions_branch_id"],
    "ai_recommendations": ["fk_ai_recommendations_company_id", "fk_ai_recommendations_branch_id"],
    "ai_usage_logs": ["fk_ai_usage_logs_company_id", "fk_ai_usage_logs_user_id"],
    "social_accounts": ["fk_social_accounts_company_id", "fk_social_accounts_branch_id"],
    "social_posts": ["fk_social_posts_company_id", "fk_social_posts_branch_id", "fk_social_posts_account_id"],
    "social_comments": ["fk_social_comments_company_id", "fk_social_comments_branch_id", "fk_social_comments_account_id", "fk_social_comments_post_id"],
    "social_messages": ["fk_social_messages_company_id", "fk_social_messages_branch_id", "fk_social_messages_account_id"],
    "social_analytics": ["fk_social_analytics_company_id", "fk_social_analytics_branch_id", "fk_social_analytics_account_id"],
    "social_competitors": ["fk_social_competitors_company_id", "fk_social_competitors_branch_id"],
    "social_webhooks": ["fk_social_webhooks_company_id", "fk_social_webhooks_account_id"],
    "media_assets": ["fk_media_assets_company_id", "fk_media_assets_branch_id", "fk_media_assets_created_by"],
    "media_variants": ["fk_media_variants_media_id"],
    "media_tags": ["fk_media_tags_company_id"],
    "media_tag_mappings": ["fk_media_tag_mappings_media_id", "fk_media_tag_mappings_tag_id"],
    "media_collections": ["fk_media_collections_company_id", "fk_media_collections_branch_id", "fk_media_collections_cover_media_id"],
    "media_collection_items": ["fk_media_collection_items_collection_id", "fk_media_collection_items_media_id"],
    "media_analytics": ["fk_media_analytics_media_id"],
    "ai_image_analysis": ["fk_ai_image_analysis_media_id", "fk_ai_image_analysis_company_id"],
    "event_definitions": ["fk_event_definitions_company_id"],
    "event_subscriptions": ["fk_event_subscriptions_company_id"],
    "event_log": ["fk_event_log_company_id", "fk_event_log_branch_id", "fk_event_log_source_user_id"],
    "event_handlers": ["fk_event_handlers_event_log_id"],
    "dead_letter_events": ["fk_dead_letter_events_event_log_id", "fk_dead_letter_events_resolved_by"],
    "automation_rules": ["fk_automation_rules_company_id", "fk_automation_rules_branch_id"],
    "automation_executions": ["fk_automation_executions_rule_id", "fk_automation_executions_trigger_event_id"],
    "company_subscriptions": ["fk_company_subscriptions_company_id", "fk_company_subscriptions_plan_id"],
    "usage_records": ["fk_usage_records_company_id"],
    "usage_quotas": ["fk_usage_quotas_company_id"],
    "invoices": ["fk_invoices_company_id"],
    "feature_flags": ["fk_feature_flags_company_id", "fk_feature_flags_enabled_by"],
    "billing_events": ["fk_billing_events_company_id"],
    "audit_logs": ["fk_audit_logs_company_id", "fk_audit_logs_branch_id", "fk_audit_logs_user_id"],
    "security_events": ["fk_security_events_company_id", "fk_security_events_user_id", "fk_security_events_resolved_by"],
    "login_attempts": ["fk_login_attempts_company_id"],
    "api_keys": ["fk_api_keys_company_id", "fk_api_keys_user_id"],
    "data_access_logs": ["fk_data_access_logs_company_id", "fk_data_access_logs_user_id"],
}

EXPECTED_INDEXES: dict[str, list[str]] = {
    "companies": ["ix_companies_id", "ix_companies_slug", "ix_companies_created_at"],
    "branches": ["ix_branches_id", "ix_branches_company_id", "ix_branches_type", "ix_branches_status", "ix_branches_created_at"],
    "users": ["ix_users_id", "ix_users_email", "ix_users_company_id", "ix_users_branch_id", "ix_users_created_at"],
    "ai_prompts": ["ix_ai_prompts_id", "ix_ai_prompts_company_id", "ix_ai_prompts_branch_id", "ix_ai_prompts_name", "ix_ai_prompts_created_at"],
    "ai_conversations": ["ix_ai_conversations_id", "ix_ai_conversations_company_id", "ix_ai_conversations_branch_id", "ix_ai_conversations_user_id", "ix_ai_conversations_prompt_id", "ix_ai_conversations_session_id", "ix_ai_conversations_created_at"],
    "ai_messages": ["ix_ai_messages_id", "ix_ai_messages_conversation_id", "ix_ai_messages_created_at"],
    "ai_suggestions": ["ix_ai_suggestions_id", "ix_ai_suggestions_company_id", "ix_ai_suggestions_branch_id", "ix_ai_suggestions_trigger_type", "ix_ai_suggestions_created_at"],
    "ai_recommendations": ["ix_ai_recommendations_id", "ix_ai_recommendations_company_id", "ix_ai_recommendations_branch_id", "ix_ai_recommendations_category", "ix_ai_recommendations_status", "ix_ai_recommendations_created_at"],
    "ai_usage_logs": ["ix_ai_usage_logs_id", "ix_ai_usage_logs_company_id", "ix_ai_usage_logs_user_id", "ix_ai_usage_logs_status", "ix_ai_usage_logs_created_at"],
    "ai_cache": ["ix_ai_cache_id", "ix_ai_cache_cache_key", "ix_ai_cache_prompt_hash", "ix_ai_cache_expires_at", "ix_ai_cache_created_at"],
    "social_accounts": ["ix_social_accounts_id", "ix_social_accounts_company_id", "ix_social_accounts_branch_id", "ix_social_accounts_platform", "ix_social_accounts_status", "ix_social_accounts_company_platform", "ix_social_accounts_branch", "ix_social_accounts_created_at"],
    "social_posts": ["ix_social_posts_id", "ix_social_posts_company_id", "ix_social_posts_branch_id", "ix_social_posts_account_id", "ix_social_posts_external_post_id", "ix_social_posts_status", "ix_social_posts_scheduled_at", "ix_social_posts_company_status", "ix_social_posts_account_status", "ix_social_posts_created_at"],
    "social_comments": ["ix_social_comments_id", "ix_social_comments_company_id", "ix_social_comments_branch_id", "ix_social_comments_account_id", "ix_social_comments_post_id", "ix_social_comments_external_comment_id", "ix_social_comments_status", "ix_social_comments_company_status", "ix_social_comments_post_created", "ix_social_comments_created_at"],
    "social_messages": ["ix_social_messages_id", "ix_social_messages_company_id", "ix_social_messages_branch_id", "ix_social_messages_account_id", "ix_social_messages_external_conversation_id", "ix_social_messages_external_message_id", "ix_social_messages_status", "ix_social_messages_company_conv", "ix_social_messages_account_created", "ix_social_messages_created_at"],
    "social_analytics": ["ix_social_analytics_id", "ix_social_analytics_company_id", "ix_social_analytics_branch_id", "ix_social_analytics_account_id", "ix_social_analytics_metric_date", "ix_social_analytics_account_date", "ix_social_analytics_company_date", "ix_social_analytics_created_at"],
    "social_competitors": ["ix_social_competitors_id", "ix_social_competitors_company_id", "ix_social_competitors_branch_id", "ix_social_competitors_platform", "ix_social_competitors_company", "ix_social_competitors_created_at"],
    "social_webhooks": ["ix_social_webhooks_id", "ix_social_webhooks_company_id", "ix_social_webhooks_account_id", "ix_social_webhooks_platform", "ix_social_webhooks_event_type", "ix_social_webhooks_processed", "ix_social_webhooks_company_processed", "ix_social_webhooks_platform_event", "ix_social_webhooks_created_at"],
    "media_assets": ["ix_media_assets_id", "ix_media_assets_company_id", "ix_media_assets_branch_id", "ix_media_assets_filename", "ix_media_assets_mime_type", "ix_media_assets_category", "ix_media_assets_status", "ix_media_assets_created_at"],
    "media_variants": ["ix_media_variants_media_id"],
    "media_tags": ["ix_media_tags_id", "ix_media_tags_company_id", "ix_media_tags_name"],
    "media_tag_mappings": [],
    "media_collections": ["ix_media_collections_id", "ix_media_collections_company_id", "ix_media_collections_branch_id"],
    "media_collection_items": [],
    "media_analytics": ["ix_media_analytics_id", "ix_media_analytics_media_id"],
    "ai_image_analysis": ["ix_ai_image_analysis_id", "ix_ai_image_analysis_media_id", "ix_ai_image_analysis_company_id"],
    "event_definitions": ["ix_event_definitions_id", "ix_event_definitions_company_id", "ix_event_definitions_event_name", "ix_event_definitions_category"],
    "event_subscriptions": ["ix_event_subscriptions_id", "ix_event_subscriptions_company_id", "ix_event_subscriptions_event_name", "ix_event_subscriptions_is_active", "ix_event_subscriptions_created_at"],
    "event_log": ["ix_event_log_id", "ix_event_log_company_id", "ix_event_log_branch_id", "ix_event_log_event_name", "ix_event_log_source_module", "ix_event_log_correlation_id", "ix_event_log_status", "ix_event_log_source_user_id", "ix_event_log_created_at"],
    "event_handlers": ["ix_event_handlers_id", "ix_event_handlers_event_log_id", "ix_event_handlers_status"],
    "dead_letter_events": ["ix_dead_letter_events_id", "ix_dead_letter_events_event_log_id", "ix_dead_letter_events_resolution_status", "ix_dead_letter_events_resolved_by", "ix_dead_letter_events_created_at"],
    "automation_rules": ["ix_automation_rules_id", "ix_automation_rules_company_id", "ix_automation_rules_branch_id", "ix_automation_rules_trigger_event", "ix_automation_rules_is_active", "ix_automation_rules_created_at"],
    "automation_executions": ["ix_automation_executions_id", "ix_automation_executions_rule_id", "ix_automation_executions_trigger_event_id", "ix_automation_executions_status", "ix_automation_executions_created_at"],
    "subscription_plans": ["ix_subscription_plans_id", "ix_subscription_plans_is_active", "ix_subscription_plans_created_at"],
    "company_subscriptions": ["ix_company_subscriptions_id", "ix_company_subscriptions_company_id", "ix_company_subscriptions_plan_id", "ix_company_subscriptions_status", "ix_company_subscriptions_created_at"],
    "usage_records": ["ix_usage_records_id", "ix_usage_records_company_id", "ix_usage_records_resource_type", "ix_usage_records_recorded_at"],
    "usage_quotas": ["ix_usage_quotas_id", "ix_usage_quotas_company_id", "ix_usage_quotas_resource_type", "ix_usage_quotas_created_at"],
    "invoices": ["ix_invoices_id", "ix_invoices_company_id", "ix_invoices_invoice_number", "ix_invoices_status", "ix_invoices_due_date", "ix_invoices_created_at"],
    "feature_flags": ["ix_feature_flags_id", "ix_feature_flags_company_id", "ix_feature_flags_feature_name", "ix_feature_flags_enabled", "ix_feature_flags_created_at"],
    "billing_events": ["ix_billing_events_id", "ix_billing_events_company_id", "ix_billing_events_event_type", "ix_billing_events_created_at"],
    "audit_logs": ["ix_audit_logs_id", "ix_audit_logs_company_id", "ix_audit_logs_branch_id", "ix_audit_logs_user_id", "ix_audit_logs_action", "ix_audit_logs_resource_type", "ix_audit_logs_ip_address", "ix_audit_logs_session_id", "ix_audit_logs_correlation_id", "ix_audit_logs_status", "ix_audit_logs_created_at"],
    "security_events": ["ix_security_events_id", "ix_security_events_company_id", "ix_security_events_event_type", "ix_security_events_severity", "ix_security_events_source_ip", "ix_security_events_user_id", "ix_security_events_resolved", "ix_security_events_created_at"],
    "login_attempts": ["ix_login_attempts_id", "ix_login_attempts_company_id", "ix_login_attempts_email", "ix_login_attempts_ip_address", "ix_login_attempts_status", "ix_login_attempts_created_at"],
    "api_keys": ["ix_api_keys_id", "ix_api_keys_company_id", "ix_api_keys_user_id", "ix_api_keys_expires_at", "ix_api_keys_is_active", "ix_api_keys_created_at"],
    "data_access_logs": ["ix_data_access_logs_id", "ix_data_access_logs_company_id", "ix_data_access_logs_user_id", "ix_data_access_logs_table_name", "ix_data_access_logs_record_id", "ix_data_access_logs_action", "ix_data_access_logs_created_at"],
}


# ---------------------------------------------------------------------------
# Results tracking
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    category: str
    name: str
    status: str  # "PASS", "FAIL", "WARN", "INFO"
    details: str = ""


class VerificationReport:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def add(self, category: str, name: str, status: str, details: str = "") -> None:
        self.results.append(CheckResult(category, name, status, details))
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        elif status == "WARN":
            self.warnings += 1

    def summary(self) -> str:
        total = len(self.results)
        return (
            f"\n{'='*70}\n"
            f"VERIFICATION SUMMARY: {self.passed} passed, {self.failed} failed, "
            f"{self.warnings} warnings out of {total} checks\n"
            f"{'='*70}"
        )

    def is_ok(self) -> bool:
        return self.failed == 0


# ---------------------------------------------------------------------------
# Verification functions
# ---------------------------------------------------------------------------

def get_db_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        sys.stderr.write("ERROR: DATABASE_URL environment variable not set\n")
        sys.exit(1)
    return url


def create_db_engine(db_url: str) -> Engine:
    """Create a synchronous database engine."""
    # Convert async URLs to sync equivalents for inspection
    sync_url = db_url.replace("+asyncpg", "").replace("+aiomysql", "").replace("+aiosqlite", "")
    return create_engine(sync_url, echo=False, future=True)


def verify_tables(engine: Engine, report: VerificationReport, verbose: bool) -> None:
    """Verify all expected tables exist."""
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names(schema="public"))

    missing = EXPECTED_TABLES - actual_tables
    extra = actual_tables - EXPECTED_TABLES

    for tbl in sorted(EXPECTED_TABLES):
        if tbl in missing:
            report.add("Tables", tbl, "FAIL", "Table is MISSING")
        else:
            report.add("Tables", tbl, "PASS", "Table exists")
            if verbose:
                columns = inspector.get_columns(tbl, schema="public")
                col_names = ", ".join(c["name"] for c in columns)
                report.add("Tables", f"  {tbl} columns", "INFO", f"{len(columns)} cols: {col_names[:100]}...")

    for tbl in sorted(extra):
        if not tbl.startswith(("pg_", "sql_")):
            report.add("Tables", tbl, "WARN", "Unexpected table found")


def verify_foreign_keys(engine: Engine, report: VerificationReport, verbose: bool) -> None:
    """Verify foreign key constraints exist."""
    inspector = inspect(engine)

    for table, expected_fks in EXPECTED_FOREIGN_KEYS.items():
        try:
            actual_fks = inspector.get_foreign_keys(table, schema="public")
            actual_fk_names = {fk["name"] for fk in actual_fks if fk["name"]}

            for fk_name in expected_fks:
                if fk_name in actual_fk_names:
                    report.add("Foreign Keys", f"{table}.{fk_name}", "PASS")
                else:
                    report.add("Foreign Keys", f"{table}.{fk_name}", "FAIL", "FK constraint missing")
        except Exception as e:
            report.add("Foreign Keys", table, "FAIL", str(e))


def verify_indexes(engine: Engine, report: VerificationReport, verbose: bool) -> None:
    """Verify expected indexes exist on each table."""
    inspector = inspect(engine)

    for table, expected_indexes in EXPECTED_INDEXES.items():
        try:
            actual_indexes = inspector.get_indexes(table, schema="public")
            actual_index_names = {idx["name"] for idx in actual_indexes}

            for idx_name in expected_indexes:
                if idx_name in actual_index_names:
                    report.add("Indexes", f"{table}.{idx_name}", "PASS")
                else:
                    report.add("Indexes", f"{table}.{idx_name}", "FAIL", "Index missing")

            if verbose:
                for idx in actual_indexes:
                    if idx["name"] not in set(expected_indexes):
                        cols = ", ".join(idx["column_names"])
                        report.add("Indexes", f"{table}.{idx['name']}", "INFO", f"Extra index on ({cols})")
        except Exception as e:
            report.add("Indexes", table, "FAIL", str(e))


def verify_table_row_counts(engine: Engine, report: VerificationReport) -> None:
    """Check approximate row counts for key tables."""
    with engine.connect() as conn:
        for table in ["companies", "subscription_plans"]:
            try:
                result = conn.execute(sql_text(f"SELECT COUNT(*) FROM public.{table}"))
                count = result.scalar()
                report.add("Row Counts", f"{table}", "INFO", f"{count} rows")
            except Exception as e:
                report.add("Row Counts", table, "WARN", str(e))


def verify_engine_charset(engine: Engine, report: VerificationReport) -> None:
    """Verify database charset/collation settings."""
    try:
        with engine.connect() as conn:
            result = conn.execute(sql_text("SHOW VARIABLES LIKE 'character_set_database'"))
            row = result.fetchone()
            if row:
                charset = row[1] if row else "unknown"
                if charset.lower() in ("utf8mb4", "utf-8", "utf8"):
                    report.add("Charset", "database_charset", "PASS", f"{charset}")
                else:
                    report.add("Charset", "database_charset", "WARN", f"{charset} (expected utf8mb4)")
            else:
                report.add("Charset", "database_charset", "INFO", "Check skipped (non-MySQL)")
    except Exception:
        report.add("Charset", "database_charset", "INFO", "Check skipped (non-MySQL)")


def run_verification(verbose: bool = False) -> VerificationReport:
    """Run full verification suite."""
    report = VerificationReport()
    db_url = get_db_url()

    report.add("Config", "DATABASE_URL", "INFO", db_url.split("@")[-1].split("/")[-1] if "@" in db_url else "connected")

    engine = create_db_engine(db_url)

    try:
        verify_tables(engine, report, verbose)
        verify_foreign_keys(engine, report, verbose)
        verify_indexes(engine, report, verbose)
        verify_table_row_counts(engine, report)
        verify_engine_charset(engine, report)
    finally:
        engine.dispose()

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify database migration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fix", action="store_true", help="Apply fixes (not yet implemented)")
    args = parser.parse_args()

    report = run_verification(verbose=args.verbose)

    if args.json:
        import json
        results = [
            {"category": r.category, "name": r.name, "status": r.status, "details": r.details}
            for r in report.results
        ]
        print(json.dumps({"results": results, "summary": {
            "passed": report.passed,
            "failed": report.failed,
            "warnings": report.warnings,
        }}, indent=2))
    else:
        for r in report.results:
            status_icon = {"PASS": "[OK]", "FAIL": "[!!]", "WARN": "[WW]", "INFO": "[--]"}.get(r.status, "[??]")
            line = f"{status_icon} {r.category:12s} | {r.name:50s}"
            if r.details:
                line += f" | {r.details}"
            print(line)
        print(report.summary())

    return 0 if report.is_ok() else 1


if __name__ == "__main__":
    sys.exit(main())
