"""Pilot Tenant Setup

3 pilot tenant olusturur:
- Tenant konfigurasyonu
- Feature flags
- Rate limits
- AI quotas
- Social connections
- Onboarding templates
- Pilot constraints

Kurallar:
- auto-send KAPALI
- approval ZORUNLU
- ERP write KAPALI
- dusuk outreach limitleri
- rollout feature flags aktif

Usage: cd backend && python scripts/staging/pilot_tenant_setup.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


PILOT_TENANTS = [
    {
        "tenant_id": "pilot_001",
        "name": "Pilot Musteri Alpha",
        "description": "Perakende sektoru pilot musterisi - AI support + analytics",
        "sector": "retail",
        "branches": [
            {"branch_id": "alpha_main", "name": "Alpha Ana Sube", "timezone": "Europe/Istanbul"},
            {"branch_id": "alpha_online", "name": "Alpha Online", "timezone": "Europe/Istanbul"},
        ],
        "contacts": {
            "primary": "alpha@pilot.example.com",
            "technical": "tech-alpha@pilot.example.com",
        },
    },
    {
        "tenant_id": "pilot_002",
        "name": "Pilot Musteri Beta",
        "description": "Hizmet sektoru pilot musterisi - campaigns + creative studio",
        "sector": "services",
        "branches": [
            {"branch_id": "beta_main", "name": "Beta Merkez", "timezone": "Europe/Istanbul"},
        ],
        "contacts": {
            "primary": "beta@pilot.example.com",
            "technical": "tech-beta@pilot.example.com",
        },
    },
    {
        "tenant_id": "pilot_003",
        "name": "Pilot Musteri Gamma",
        "description": "Uretim sektoru pilot musterisi - ERP sync + governance dashboards",
        "sector": "manufacturing",
        "branches": [
            {"branch_id": "gamma_main", "name": "Gamma Fabrika", "timezone": "Europe/Istanbul"},
            {"branch_id": "gamma_depot", "name": "Gamma Depo", "timezone": "Europe/Istanbul"},
        ],
        "contacts": {
            "primary": "gamma@pilot.example.com",
            "technical": "tech-gamma@pilot.example.com",
        },
    },
]


def get_pilot_config(tenant_index: int) -> dict:
    """Get pilot configuration for a tenant."""
    tenant = PILOT_TENANTS[tenant_index]

    return {
        "tenant": tenant,
        "config_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),

        # Feature flags - pilot kisitlamalari
        "feature_flags": {
            "ai_chat": True,
            "ai_support": True,
            "ai_safety_approval": True,
            "analytics_dashboard": True,
            "follower_intelligence": True,
            "social_media_connect": True,
            "whatsapp_integration": True,
            "campaign_management": tenant_index >= 1,  # Alpha: False, Beta/Gamma: True
            "creative_studio": tenant_index >= 1,
            "reports_export": True,
            "knowledge_base": True,
            "branch_management": True,
            "user_management": True,
            "erp_sync": True,
            "erp_write": False,  # KAPALI
            "billing": False,  # KAPALI
            "revenue_intelligence": True,
            "tenant_governance": True,
            "observability": True,
            "governance_dashboards": tenant_index >= 2,  # Sadece Gamma
        },

        # Rate limits - dusuk pilot limitleri
        "rate_limits": {
            "requests_per_minute": 60,
            "requests_per_hour": 1500,
            "ai_requests_per_minute": 15,
            "ai_requests_per_hour": 200,
            "webhook_calls_per_minute": 30,
            "erp_sync_per_hour": 20,
            "exports_per_day": 10,
            "reports_per_day": 25,
            "media_uploads_per_hour": 10,
            # Follower intelligence rate limits
            "follower_sync_per_hour": 5,
            "outreach_per_day": 20,
            "whatsapp_per_day": 50,
            "telegram_per_day": 30,
        },

        # AI quotas - dusuk pilot limitleri
        "ai_quotas": {
            "tokens_per_hour": 50000,
            "tokens_per_day": 200000,
            "max_context_window": 4000,
            "allowed_models": ["gpt-4o-mini"],
            "blocked_models": ["gpt-4", "gpt-4o", "claude-sonnet", "claude-opus"],
            "temperature_max": 0.7,
            "auto_send_enabled": False,  # KAPALI - KRITIK
            "escalation_threshold": 0.75,
            "require_approval_for": [
                "email_send",
                "campaign_publish",
                "bulk_message",
                "erp_write",
                "customer_delete",
                "whatsapp_message",
                "follower_outreach",
                "ai_message_send",
            ],
            "max_concurrent_ai_requests": 3,
            "response_timeout_seconds": 30,
        },

        # Follower intelligence config
        "follower_intelligence": {
            "enabled": True,
            "auto_sync_interval_hours": 24,
            "engagement_decay_days": 14,
            "bot_detection_enabled": True,
            "approval_required_for": [
                "reengagement_message",
                "outreach_send",
                "bulk_sync",
            ],
            # Platform dispatch rate limits
            "platform_limits": {
                "instagram": {"messages_per_minute": 5, "messages_per_hour": 50, "cooldown_seconds": 120},
                "facebook": {"messages_per_minute": 10, "messages_per_hour": 100, "cooldown_seconds": 60},
                "tiktok": {"messages_per_minute": 3, "messages_per_hour": 30, "cooldown_seconds": 300},
                "whatsapp": {"messages_per_minute": 15, "messages_per_hour": 200, "cooldown_seconds": 30},
                "telegram": {"messages_per_minute": 20, "messages_per_hour": 300, "cooldown_seconds": 30},
            },
            # Warm-up schedule (8 gun)
            "warmup_schedule": {
                "enabled": True,
                "day_1": 0.2,
                "day_2": 0.3,
                "day_3": 0.4,
                "day_4": 0.5,
                "day_5": 0.6,
                "day_6": 0.7,
                "day_7": 0.8,
                "day_8": 1.0,
            },
            # Governance
            "governance": {
                "daily_quota": 20,
                "cooldown_hours": 24,
                "spam_risk_threshold": 0.7,
                "fatigue_threshold": 0.5,
                "reputation_threshold": 60,
                "confidence_threshold": 0.5,
            },
        },

        # Pilot constraints
        "pilot_constraints": {
            "max_users": 5,
            "max_branches": len(tenant["branches"]),
            "max_campaigns": 5,
            "max_media_files": 50,
            "max_knowledge_docs": 25,
            "data_retention_days": 90,
            "max_daily_outreach": 20,
            "max_weekly_outreach": 100,
        },

        # Support config
        "support_config": {
            "support_tier": "white_glove",
            "response_time_sla_hours": 4,
            "dedicated_channel": True,
            "weekly_review": True,
            "ai_support_available": True,
            "onboarding_assistance": True,
            "escalation_path": "l1_support -> l2_tech -> l3_engineering",
        },

        # Rollout flags
        "rollout_flags": {
            "phase": "pilot_week_1" if tenant_index == 0 else "pilot_week_2" if tenant_index == 1 else "pilot_week_3",
            "features_enabled": ["ai_support", "analytics", "reports", "whatsapp_support", "follower_intelligence"],
            "features_pending": ["campaigns", "creative_studio"] if tenant_index == 0 else ["erp_sync"] if tenant_index == 1 else [],
            "abort_criteria_active": True,
            "auto_escalation_enabled": True,
        },

        # Monitoring
        "monitoring": {
            "ai_cost_alerts": True,
            "spam_risk_alerts": True,
            "fatigue_alerts": True,
            "webhook_failure_alerts": True,
            "queue_latency_alerts": True,
            "tenant_health_dashboard": True,
            "alert_severity": "medium",
            "critical_alerts_channel": "pilot-ops-critical",
            "standard_alerts_channel": "pilot-ops",
        },
    }


def validate_pilot_config(config: dict) -> list[str]:
    """Validate pilot configuration safety."""
    issues = []

    # Kritik guvenlik kontrolleri
    if config["ai_quotas"]["auto_send_enabled"]:
        issues.append("KRITIK: AI auto-send ACILK - KAPALI olmali")

    if config["feature_flags"]["erp_write"]:
        issues.append("KRITIK: ERP write ACILK - KAPALI olmali")

    if config["feature_flags"]["billing"]:
        issues.append("KRITIK: Billing ACILK - KAPALI olmali")

    if not config["ai_quotas"]["require_approval_for"]:
        issues.append("KRITIK: Onay listesi bos - mesaj onayi ZORUNLU")

    # Limit kontrolleri
    if config["rate_limits"]["ai_requests_per_hour"] > 1000:
        issues.append("UYARI: AI istek limiti cok yuksek")

    if config["pilot_constraints"]["max_daily_outreach"] > 100:
        issues.append("UYARI: Gunluk outreach limiti cok yuksek")

    # Onay kontrolu
    required_approvals = ["ai_message_send", "whatsapp_message", "follower_outreach"]
    for req in required_approvals:
        if req not in config["ai_quotas"]["require_approval_for"]:
            issues.append(f"UYARI: {req} onay listesinde degil")

    return issues


def main() -> int:
    print("=" * 70)
    print("  PILOT TENANT SETUP")
    print("  Target: 3 pilot tenants with safety constraints")
    print("=" * 70)

    all_configs = []
    all_issues = []

    for i in range(3):
        tenant_info = PILOT_TENANTS[i]
        print(f"\n--- Tenant {i+1}: {tenant_info['tenant_id']} ({tenant_info['name']}) ---")

        config = get_pilot_config(i)
        all_configs.append(config)

        # Validate
        issues = validate_pilot_config(config)
        all_issues.extend(issues)

        if issues:
            for issue in issues:
                severity = "KRITIK" if "KRITIK" in issue else "UYARI"
                print(f"    [{severity}] {issue}")
        else:
            print("    [OK] Tum guvenlik kontrolleri gecti")

        # Print summary
        print(f"    Branches: {len(config['tenant']['branches'])}")
        print(f"    Features: {sum(1 for v in config['feature_flags'].values() if v)}/{len(config['feature_flags'])}")
        print(f"    Outreach limit: {config['pilot_constraints']['max_daily_outreach']}/gun")
        print(f"    AI approval: {'ACIK' if config['ai_quotas']['require_approval_for'] else 'KAPALI'}")
        print(f"    Auto-send: {'ACIK' if config['ai_quotas']['auto_send_enabled'] else 'KAPALI'}")
        print(f"    Phase: {config['rollout_flags']['phase']}")

    # Save configs
    output_path = PROJECT_ROOT / "scripts" / "staging" / "pilot_tenant_configs.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "pilots": all_configs,
            "cohort_size": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "safety_validated": len([i for i in all_issues if "KRITIK" in i]) == 0,
            "critical_issues": len([i for i in all_issues if "KRITIK" in i]),
            "warnings": len([i for i in all_issues if "UYARI" in i]),
        }, f, indent=2, ensure_ascii=False)

    # Summary
    critical = len([i for i in all_issues if "KRITIK" in i])
    warnings = len([i for i in all_issues if "UYARI" in i])

    print(f"\n{'=' * 70}")
    print(f"  OZET")
    print(f"{'=' * 70}")
    print(f"  Pilot tenant: 3")
    print(f"  Kritik issue: {critical}")
    print(f"  Uyari: {warnings}")
    print(f"  Config: {output_path}")

    if critical > 0:
        print(f"\n  DURUM: GUVENLIK RISKI - {critical} kritik issue duzeltilmeli")
        return 1
    elif warnings > 0:
        print(f"\n  DURUM: KABUL EDILEBILIR - {warnings} uyari var")
        return 0
    else:
        print(f"\n  DURUM: GUVENLI - 3 pilot tenant hazir")
        return 0


if __name__ == "__main__":
    sys.exit(main())
