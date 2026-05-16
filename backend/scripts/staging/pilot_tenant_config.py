"""Pilot Tenant Configuration

Defines pilot tenant isolation, feature flags, rate limits and AI quotas.
Run to generate pilot tenant configuration.

Usage: cd backend && python scripts/staging/pilot_tenant_config.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PILOT_TENANT_TEMPLATE = {
    "tenant_id": "pilot_{index}",
    "tier": "pilot",
    "isolation_level": "shared_db_schema",  # Options: shared_db_schema, dedicated_schema, dedicated_db
    "rate_limits": {
        "requests_per_minute": 120,
        "requests_per_hour": 3000,
        "ai_requests_per_minute": 30,
        "ai_requests_per_hour": 500,
        "webhook_calls_per_minute": 60,
        "erp_sync_per_hour": 50,
        "exports_per_day": 20,
        "reports_per_day": 50,
        "media_uploads_per_hour": 20,
    },
    "ai_quotas": {
        "tokens_per_hour": 100000,
        "tokens_per_day": 500000,
        "max_context_window": 4000,
        "allowed_models": ["gpt-4o-mini"],
        "blocked_models": ["gpt-4", "gpt-4o", "claude-sonnet"],
        "temperature_max": 0.7,
        "require_approval_for": [
            "email_send",
            "campaign_publish",
            "bulk_message",
            "erp_write",
            "customer_delete",
        ],
        "auto_send_enabled": False,  # CRITICAL: AI auto-send disabled for pilot
        "escalation_threshold": 0.75,  # Confidence below 75% triggers escalation
    },
    "feature_flags": {
        "ai_chat": True,
        "ai_support": True,
        "analytics_dashboard": True,
        "follower_intelligence": True,
        "social_media_connect": True,
        "whatsapp_integration": True,
        "erp_sync": True,  # ERP enabled but with verified flow only
        "erp_write": False,  # ERP write disabled - read-only sync
        "campaign_management": True,
        "creative_studio": True,
        "reports_export": True,
        "knowledge_base": True,
        "branch_management": True,
        "user_management": True,
        "billing": False,  # Billing disabled for pilot
        "revenue_intelligence": True,
        "ai_safety_approval": True,
        "tenant_governance": True,
        "observability": True,
    },
    "pilot_constraints": {
        "max_users": 5,
        "max_branches": 2,
        "max_campaigns": 10,
        "max_media_files": 100,
        "max_knowledge_docs": 50,
        "data_retention_days": 90,
    },
    "support_config": {
        "support_tier": "white_glove",
        "response_time_sla_hours": 4,
        "dedicated_channel": True,
        "weekly_review": True,
        "escalation_path": "l1_support -> l2_tech -> l3_engineering",
    },
}


def generate_pilot_configs(count: int = 5) -> list:
    """Generate pilot tenant configurations."""
    configs = []
    for i in range(1, count + 1):
        config = json.loads(json.dumps(PILOT_TENANT_TEMPLATE))
        config["tenant_id"] = f"pilot_{i:03d}"
        config["name"] = f"Pilot Customer {i}"
        config["description"] = f"Pilot cohort tenant #{i}"
        configs.append(config)
    return configs


def validate_config(config: dict) -> list:
    """Validate pilot configuration safety."""
    issues = []

    # AI auto-send must be disabled
    if config["ai_quotas"]["auto_send_enabled"]:
        issues.append("CRITICAL: AI auto-send is enabled - must be False for pilot")

    # ERP write must be disabled
    if config["feature_flags"]["erp_write"]:
        issues.append("CRITICAL: ERP write is enabled - must be False for pilot")

    # Billing must be disabled
    if config["feature_flags"]["billing"]:
        issues.append("CRITICAL: Billing is enabled - must be False for pilot")

    # Rate limits must be reasonable
    if config["rate_limits"]["ai_requests_per_hour"] > 1000:
        issues.append("WARNING: AI requests/hour exceeds 1000")

    # Approval required list must not be empty
    if not config["ai_quotas"]["require_approval_for"]:
        issues.append("WARNING: No approval-required actions defined")

    # Escalation threshold must be set
    if config["ai_quotas"]["escalation_threshold"] < 0.5:
        issues.append("WARNING: Escalation threshold below 50%")

    return issues


def main() -> int:
    print("=" * 60)
    print("PILOT TENANT CONFIGURATION GENERATOR")
    print("=" * 60)

    # Generate configs for 5 pilot customers
    configs = generate_pilot_configs(5)
    print(f"\n--- Generated {len(configs)} pilot tenant configs ---")

    all_issues = []
    for config in configs:
        print(f"\n  Tenant: {config['tenant_id']} ({config['name']})")
        issues = validate_config(config)
        if issues:
            for issue in issues:
                severity = "CRITICAL" if "CRITICAL" in issue else "WARNING"
                print(f"    [{severity}] {issue}")
            all_issues.extend(issues)
        else:
            print(f"    [OK] All safety checks passed")

    # Save config
    output_path = PROJECT_ROOT / "scripts" / "staging" / "pilot_tenant_configs.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "pilots": configs,
            "cohort_size": len(configs),
            "created_at": "2026-05-16",
            "safety_validated": len(all_issues) == 0,
        }, f, indent=2, ensure_ascii=False)

    # Summary
    critical = sum(1 for i in all_issues if "CRITICAL" in i)
    warnings = sum(1 for i in all_issues if "WARNING" in i)

    print(f"\n{'=' * 60}")
    print(f"Tenants: {len(configs)}")
    print(f"Critical issues: {critical}")
    print(f"Warnings: {warnings}")
    print(f"Config saved: {output_path}")

    if critical > 0:
        print(f"\nSTATUS: UNSAFE - {critical} critical issue(s) must be fixed")
        return 1
    elif warnings > 0:
        print(f"\nSTATUS: ACCEPTABLE with {warnings} warning(s)")
        return 0
    else:
        print(f"\nSTATUS: SAFE - All pilot tenant configs validated")
        return 0


if __name__ == "__main__":
    sys.exit(main())
