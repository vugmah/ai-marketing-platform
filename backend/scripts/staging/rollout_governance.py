"""Controlled Rollout Governance

Manages pilot rollout phases with abort criteria and feature flags.
Usage: cd backend && python scripts/staging/rollout_governance.py
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Rollout phases
ROLLOUT_PHASES = [
    {
        "week": 1,
        "name": "Core Validation",
        "customer_limit": 3,
        "features_enabled": [
            "ai_chat", "ai_support", "analytics_dashboard",
            "social_media_connect", "whatsapp_integration",
            "reports_export", "knowledge_base",
        ],
        "features_disabled": [
            "campaign_management", "creative_studio",
            "erp_write", "billing", "revenue_intelligence",
        ],
        "criteria": {
            "min_onboarding_completion": 80,
            "max_p1_incidents": 0,
            "max_p2_incidents": 1,
            "min_ai_confidence": 0.70,
            "max_avg_latency_ms": 2000,
        },
    },
    {
        "week": 2,
        "name": "Feature Expansion",
        "customer_limit": 5,
        "features_enabled": [
            "ai_chat", "ai_support", "analytics_dashboard",
            "social_media_connect", "whatsapp_integration",
            "reports_export", "knowledge_base",
            "campaign_management", "creative_studio",
            "follower_intelligence",
        ],
        "features_disabled": [
            "erp_write", "billing", "revenue_intelligence",
        ],
        "criteria": {
            "min_onboarding_completion": 75,
            "max_p1_incidents": 0,
            "max_p2_incidents": 2,
            "min_ai_confidence": 0.72,
            "max_avg_latency_ms": 1800,
        },
    },
    {
        "week": 3,
        "name": "Integration Testing",
        "customer_limit": 8,
        "features_enabled": [
            "ai_chat", "ai_support", "analytics_dashboard",
            "social_media_connect", "whatsapp_integration",
            "reports_export", "knowledge_base",
            "campaign_management", "creative_studio",
            "follower_intelligence", "revenue_intelligence",
            "erp_sync",
        ],
        "features_disabled": [
            "erp_write", "billing",
        ],
        "criteria": {
            "min_onboarding_completion": 70,
            "max_p1_incidents": 1,
            "max_p2_incidents": 2,
            "min_ai_confidence": 0.75,
            "max_avg_latency_ms": 1500,
        },
    },
    {
        "week": 4,
        "name": "Full Pilot",
        "customer_limit": 10,
        "features_enabled": [
            "ai_chat", "ai_support", "analytics_dashboard",
            "social_media_connect", "whatsapp_integration",
            "reports_export", "knowledge_base",
            "campaign_management", "creative_studio",
            "follower_intelligence", "revenue_intelligence",
            "erp_sync", "branch_management", "user_management",
        ],
        "features_disabled": [
            "erp_write", "billing",
        ],
        "criteria": {
            "min_onboarding_completion": 65,
            "max_p1_incidents": 1,
            "max_p2_incidents": 3,
            "min_ai_confidence": 0.75,
            "max_avg_latency_ms": 1500,
        },
    },
]

# Abort criteria
ABORT_CRITERIA = [
    {
        "id": "ABORT-1",
        "name": "P1 Incident Spike",
        "condition": "> 3 P1 incidents in any 7-day period",
        "action": "Halt new tenant onboarding, investigate root cause",
        "escalation": "Immediate L3 + Product",
    },
    {
        "id": "ABORT-2",
        "name": "Data Loss",
        "condition": "Any confirmed data loss event",
        "action": "Immediate rollback, freeze all writes",
        "escalation": "Immediate L3 + Engineering Lead",
    },
    {
        "id": "ABORT-3",
        "name": "Queue Corruption",
        "condition": "Celery queue corrupted or tasks lost",
        "action": "Restart workers, drain and rebuild queue",
        "escalation": "L2 + DevOps",
    },
    {
        "id": "ABORT-4",
        "name": "Migration Failure",
        "condition": "Alembic migration rollback required",
        "action": "Stop deployment pipeline, restore DB",
        "escalation": "L3 + DBA",
    },
    {
        "id": "ABORT-5",
        "name": "AI Safety Violation",
        "condition": "Unsafe AI output delivered to customer",
        "action": "Disable AI for affected tenant, review safety filters",
        "escalation": "Immediate L3 + Product + Engineering Lead",
    },
    {
        "id": "ABORT-6",
        "name": "Redis Saturation",
        "condition": "Redis memory > 95% for > 10 minutes",
        "action": "Restart Redis, review cache TTL policies",
        "escalation": "L2 + DevOps",
    },
    {
        "id": "ABORT-7",
        "name": "Webhook Failure Spike",
        "condition": "Webhook delivery success < 90% for > 1 hour",
        "action": "Pause webhook triggers, investigate external services",
        "escalation": "L2 + Engineering",
    },
]


def check_phase_eligibility(week: int, metrics: dict) -> dict:
    """Check if rollout can proceed to next phase."""
    phase = ROLLOUT_PHASES[week - 1]
    criteria = phase["criteria"]

    results = []
    passed = True

    # Check onboarding completion
    if metrics.get("onboarding_completion", 0) < criteria["min_onboarding_completion"]:
        results.append({
            "check": "Onboarding completion",
            "required": f">= {criteria['min_onboarding_completion']}%",
            "actual": f"{metrics.get('onboarding_completion', 0)}%",
            "pass": False,
        })
        passed = False
    else:
        results.append({"check": "Onboarding completion", "pass": True})

    # Check P1 incidents
    p1_count = metrics.get("p1_incidents_7d", 0)
    if p1_count > criteria["max_p1_incidents"]:
        results.append({
            "check": "P1 incidents (7d)",
            "required": f"<= {criteria['max_p1_incidents']}",
            "actual": str(p1_count),
            "pass": False,
        })
        passed = False
    else:
        results.append({"check": "P1 incidents", "pass": True})

    # Check P2 incidents
    p2_count = metrics.get("p2_incidents_7d", 0)
    if p2_count > criteria["max_p2_incidents"]:
        results.append({
            "check": "P2 incidents (7d)",
            "required": f"<= {criteria['max_p2_incidents']}",
            "actual": str(p2_count),
            "pass": False,
        })
        passed = False
    else:
        results.append({"check": "P2 incidents", "pass": True})

    # Check AI confidence
    if metrics.get("avg_ai_confidence", 0) < criteria["min_ai_confidence"]:
        results.append({
            "check": "AI confidence",
            "required": f">= {criteria['min_ai_confidence']}",
            "actual": f"{metrics.get('avg_ai_confidence', 0):.2f}",
            "pass": False,
        })
        passed = False
    else:
        results.append({"check": "AI confidence", "pass": True})

    # Check latency
    if metrics.get("avg_latency_ms", 0) > criteria["max_avg_latency_ms"]:
        results.append({
            "check": "Avg latency",
            "required": f"<= {criteria['max_avg_latency_ms']}ms",
            "actual": f"{metrics.get('avg_latency_ms', 0)}ms",
            "pass": False,
        })
        passed = False
    else:
        results.append({"check": "Avg latency", "pass": True})

    return {
        "phase": phase["name"],
        "week": week,
        "passed": passed,
        "checks": results,
    }


def main() -> int:
    print("=" * 60)
    print("CONTROLLED ROLLOUT GOVERNANCE")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)

    # Show phases
    print(f"\n--- Rollout Phases ---")
    for phase in ROLLOUT_PHASES:
        print(f"\n  Week {phase['week']}: {phase['name']}")
        print(f"    Customer limit: {phase['customer_limit']}")
        print(f"    Features: {len(phase['features_enabled'])} enabled, {len(phase['features_disabled'])} disabled")
        print(f"    Criteria:")
        for k, v in phase["criteria"].items():
            print(f"      {k}: {v}")

    # Show abort criteria
    print(f"\n{'=' * 60}")
    print(f"--- Abort Criteria ({len(ABORT_CRITERIA)} total) ---")
    for abort in ABORT_CRITERIA:
        print(f"\n  {abort['id']}: {abort['name']}")
        print(f"    Condition: {abort['condition']}")
        print(f"    Action: {abort['action']}")
        print(f"    Escalation: {abort['escalation']}")

    # Simulate week 1 eligibility check with actual pilot data
    print(f"\n{'=' * 60}")
    print(f"--- Week 1 Eligibility Check ---")
    week1_metrics = {
        "onboarding_completion": 67,
        "p1_incidents_7d": 0,
        "p2_incidents_7d": 1,
        "avg_ai_confidence": 0.74,
        "avg_latency_ms": 1570,
    }
    result = check_phase_eligibility(1, week1_metrics)
    print(f"\n  Phase: {result['phase']} (Week {result['week']})")
    for check in result["checks"]:
        status = "PASS" if check["pass"] else "FAIL"
        print(f"    [{status}] {check['check']}")
        if not check["pass"]:
            print(f"           Required: {check.get('required', 'N/A')}")
            print(f"           Actual: {check.get('actual', 'N/A')}")
    print(f"\n  Overall: {'PROCEED' if result['passed'] else 'DO NOT PROCEED'}")

    # Save rollout plan
    rollout_plan = {
        "created_at": datetime.now().isoformat(),
        "phases": ROLLOUT_PHASES,
        "abort_criteria": ABORT_CRITERIA,
        "current_week": 1,
        "current_metrics": week1_metrics,
        "week1_eligibility": result,
    }

    output = PROJECT_ROOT / "scripts" / "staging" / "rollout_plan.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rollout_plan, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Rollout plan saved: {output}")
    print(f"Phases: {len(ROLLOUT_PHASES)} | Abort criteria: {len(ABORT_CRITERIA)}")
    print(f"Status: PLAN GENERATED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
