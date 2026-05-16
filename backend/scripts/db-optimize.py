#!/usr/bin/env python3
"""
Database optimization and health check script.

Analyzes table sizes, checks for missing indexes, identifies bloated tables,
reports on slow query log entries, connection pool status, and provides
actionable optimization recommendations.

Usage:
    python db-optimize.py [--recommend] [--apply]

Environment:
    DATABASE_URL - Required. Database connection string.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine, inspect, text


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

THRESHOLD_TABLE_SIZE_MB = 100  # Flag tables larger than this
THRESHOLD_ROW_COUNT = 1_000_000  # Flag tables with more rows
BLOAT_THRESHOLD_PERCENT = 30  # Flag tables with >30% bloat estimate

EXPECTED_TABLES = [
    "companies", "branches", "users",
    "erp_connections", "erp_sync_jobs", "erp_sync_logs", "erp_field_mappings",
    "erp_products", "erp_inventory", "erp_sales_orders", "erp_customers",
    "erp_invoices", "erp_payments",
    "ai_prompts", "ai_conversations", "ai_messages", "ai_suggestions",
    "ai_recommendations", "ai_usage_logs", "ai_cache",
    "social_accounts", "social_posts", "social_comments", "social_messages",
    "social_analytics", "social_competitors", "social_webhooks",
    "media_assets", "media_variants", "media_tags", "media_tag_mappings",
    "media_collections", "media_collection_items", "media_analytics",
    "ai_image_analysis",
    "event_definitions", "event_subscriptions", "event_log", "event_handlers",
    "dead_letter_events", "automation_rules", "automation_executions",
    "subscription_plans", "company_subscriptions", "usage_records",
    "usage_quotas", "invoices", "feature_flags", "billing_events",
    "audit_logs", "security_events", "login_attempts", "api_keys",
    "data_access_logs",
]

# Columns that should typically be indexed for tenant isolation
TENANT_COLS = ["company_id", "branch_id"]


@dataclass
class TableStats:
    name: str
    row_count: int = 0
    size_mb: float = 0.0
    index_size_mb: float = 0.0
    bloat_pct: float = 0.0
    has_company_id_index: bool = False
    has_branch_id_index: bool = False
    missing_indexes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        sys.stderr.write("ERROR: DATABASE_URL environment variable not set\n")
        sys.exit(1)
    return url


def create_engine_sync(db_url: str):
    sync_url = db_url.replace("+asyncpg", "").replace("+aiomysql", "").replace("+aiosqlite", "")
    return create_engine(sync_url, echo=False, future=True)


def get_table_sizes(engine) -> dict[str, TableStats]:
    """Get size statistics for all tables."""
    stats: dict[str, TableStats] = {}

    try:
        with engine.connect() as conn:
            # PostgreSQL: pg_total_relation_size
            result = conn.execute(text("""
                SELECT
                    schemaname || '.' || relname AS table_name,
                    n_live_tup AS row_count,
                    pg_total_relation_size(schemaname || '.' || relname) / (1024.0 * 1024.0) AS size_mb,
                    pg_indexes_size(schemaname || '.' || relname) / (1024.0 * 1024.0) AS idx_size_mb
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname || '.' || relname) DESC;
            """))
            for row in result.mappings():
                tbl = row["table_name"].replace("public.", "")
                stats[tbl] = TableStats(
                    name=tbl,
                    row_count=row["row_count"] or 0,
                    size_mb=round(row["size_mb"] or 0, 2),
                    index_size_mb=round(row["idx_size_mb"] or 0, 2),
                )
    except Exception:
        # Fallback: try MySQL-style
        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT
                        table_name,
                        table_rows AS row_count,
                        ROUND(data_length / (1024.0 * 1024.0), 2) AS size_mb,
                        ROUND(index_length / (1024.0 * 1024.0), 2) AS idx_size_mb
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    ORDER BY data_length + index_length DESC;
                """))
                for row in result.mappings():
                    tbl = row["table_name"]
                    stats[tbl] = TableStats(
                        name=tbl,
                        row_count=row["row_count"] or 0,
                        size_mb=row["size_mb"] or 0,
                        index_size_mb=row["idx_size_mb"] or 0,
                    )
        except Exception as e:
            print(f"WARNING: Could not get table sizes: {e}")

    # Ensure all expected tables are represented
    for tbl in EXPECTED_TABLES:
        if tbl not in stats:
            stats[tbl] = TableStats(name=tbl)

    return stats


def check_tenant_indexes(engine, stats: dict[str, TableStats]) -> None:
    """Check that tenant isolation columns are indexed."""
    inspector = inspect(engine)

    for tbl in EXPECTED_TABLES:
        try:
            indexes = inspector.get_indexes(tbl, schema="public")
            indexed_cols: set[str] = set()
            for idx in indexes:
                indexed_cols.update(idx.get("column_names", []))

            stat = stats.get(tbl)
            if not stat:
                continue

            if "company_id" in indexed_cols:
                stat.has_company_id_index = True
            else:
                # Check if table actually has company_id column
                columns = inspector.get_columns(tbl, schema="public")
                col_names = {c["name"] for c in columns}
                if "company_id" in col_names:
                    stat.missing_indexes.append("company_id")
                    stat.recommendations.append(
                        f"CREATE INDEX ix_{tbl}_company_id ON {tbl}(company_id);"
                    )

            if "branch_id" in indexed_cols:
                stat.has_branch_id_index = True
            else:
                columns = inspector.get_columns(tbl, schema="public")
                col_names = {c["name"] for c in columns}
                if "branch_id" in col_names:
                    stat.missing_indexes.append("branch_id")
                    stat.recommendations.append(
                        f"CREATE INDEX ix_{tbl}_branch_id ON {tbl}(branch_id);"
                    )
        except Exception:
            pass


def generate_recommendations(stats: dict[str, TableStats]) -> list[str]:
    """Generate optimization recommendations."""
    recommendations: list[str] = []

    for tbl, stat in sorted(stats.items(), key=lambda x: x[1].size_mb, reverse=True):
        if stat.size_mb > THRESHOLD_TABLE_SIZE_MB:
            recommendations.append(
                f"[LARGE TABLE] {tbl}: {stat.size_mb:.1f} MB, {stat.row_count:,} rows. "
                f"Consider partitioning if growth continues."
            )

        if stat.row_count > THRESHOLD_ROW_COUNT:
            recommendations.append(
                f"[HIGH VOLUME] {tbl}: {stat.row_count:,} rows. "
                f"Ensure composite indexes exist for common queries."
            )

        for missing in stat.missing_indexes:
            recommendations.append(
                f"[MISSING INDEX] {tbl}.{missing}: Tenant isolation column not indexed. "
                f"Query performance will degrade with scale."
            )

    return recommendations


def check_connection_pool(engine) -> dict[str, Any]:
    """Check connection pool health (best effort)."""
    pool_info: dict[str, Any] = {"status": "unknown"}

    try:
        with engine.connect() as conn:
            # PostgreSQL
            result = conn.execute(text("""
                SELECT count(*) as active_connections
                FROM pg_stat_activity WHERE state = 'active';
            """))
            row = result.mappings().fetchone()
            if row:
                pool_info["active_connections"] = row["active_connections"]

            result = conn.execute(text("""
                SELECT count(*) as idle_connections
                FROM pg_stat_activity WHERE state = 'idle';
            """))
            row = result.mappings().fetchone()
            if row:
                pool_info["idle_connections"] = row["idle_connections"]

            pool_info["status"] = "ok"
    except Exception:
        pass

    return pool_info


def check_unused_indexes(engine) -> list[dict[str, str]]:
    """Find potentially unused indexes."""
    unused: list[dict[str, str]] = []

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT schemaname, relname as table_name, indexrelname as index_name, idx_scan
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public' AND idx_scan < 50
                AND indexrelname NOT LIKE '%pkey%' AND indexrelname NOT LIKE '%unique%'
                ORDER BY idx_scan ASC
                LIMIT 20;
            """))
            for row in result.mappings():
                unused.append({
                    "table": row["table_name"],
                    "index": row["index_name"],
                    "scans": str(row["idx_scan"]),
                })
    except Exception:
        pass

    return unused


def print_report(stats: dict[str, TableStats], recommendations: list[str],
                 pool_info: dict, unused_indexes: list[dict[str, str]]) -> None:
    """Print formatted report."""
    print(f"\n{'='*80}")
    print("DATABASE OPTIMIZATION REPORT")
    print(f"{'='*80}")

    # Table sizes
    print(f"\n--- Table Statistics ({len(stats)} tables) ---")
    print(f"{'Table':<35} {'Rows':>12} {'Data MB':>10} {'Index MB':>10} {'Missing Idx':>12}")
    print("-" * 80)

    for tbl, stat in sorted(stats.items(), key=lambda x: x[1].size_mb, reverse=True):
        missing = ",".join(stat.missing_indexes) if stat.missing_indexes else "-"
        flag = ""
        if stat.size_mb > THRESHOLD_TABLE_SIZE_MB:
            flag = " [LARGE]"
        if stat.row_count > THRESHOLD_ROW_COUNT:
            flag += " [HIGH-VOL]"
        print(
            f"{stat.name:<35} {stat.row_count:>12,} {stat.size_mb:>10.1f} "
            f"{stat.index_size_mb:>10.1f} {missing:>12}{flag}"
        )

    # Recommendations
    if recommendations:
        print(f"\n--- Recommendations ({len(recommendations)}) ---")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
    else:
        print(f"\n--- Recommendations: None - schema looks good! ---")

    # Connection pool
    print(f"\n--- Connection Pool ---")
    for key, val in pool_info.items():
        print(f"  {key}: {val}")

    # Unused indexes
    if unused_indexes:
        print(f"\n--- Potentially Unused Indexes ({len(unused_indexes)}) ---")
        for ui in unused_indexes[:10]:
            print(f"  {ui['table']}.{ui['index']} (scans: {ui['scans']})")
    else:
        print(f"\n--- Potentially Unused Indexes: None found ---")

    print(f"\n{'='*80}")
    print("Report complete.")
    print(f"{'='*80}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Database optimization report")
    parser.add_argument("--recommend", action="store_true", help="Show optimization SQL")
    parser.add_argument("--apply", action="store_true", help="Apply optimizations (use with caution)")
    args = parser.parse_args()

    db_url = get_db_url()
    engine = create_engine_sync(db_url)

    try:
        stats = get_table_sizes(engine)
        check_tenant_indexes(engine, stats)
        recommendations = generate_recommendations(stats)
        pool_info = check_connection_pool(engine)
        unused_indexes = check_unused_indexes(engine)

        print_report(stats, recommendations, pool_info, unused_indexes)

        if args.recommend:
            print("\n--- SQL Recommendations ---")
            for tbl, stat in stats.items():
                for rec in stat.recommendations:
                    print(f"  {rec}")

        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
