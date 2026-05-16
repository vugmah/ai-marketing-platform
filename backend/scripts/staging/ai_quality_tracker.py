"""AI Quality & Safety Tracking

Tracks AI behavior in real pilot usage. Measures quality, safety and cost metrics.
Usage: cd backend && python scripts/staging/ai_quality_tracker.py
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Simulated AI quality data from pilot tenants
PILOT_AI_DATA = {
    "pilot_001": {
        "tenant_name": "Demo Market",
        "period": "2026-05-10 to 2026-05-16",
        "interactions": 156,
        "escalations": 12,
        "approval_requests": 89,
        "approval_rejections": 8,
        "hallucination_flags": 3,
        "unsafe_output_blocks": 1,
        "operator_overrides": 7,
        "avg_confidence": 0.82,
        "avg_latency_ms": 1240,
        "total_tokens": 84200,
        "estimated_cost_usd": 0.42,
    },
    "pilot_002": {
        "tenant_name": "TechStore Istanbul",
        "period": "2026-05-12 to 2026-05-16",
        "interactions": 67,
        "escalations": 18,
        "approval_requests": 45,
        "approval_rejections": 11,
        "hallucination_flags": 7,
        "unsafe_output_blocks": 2,
        "operator_overrides": 9,
        "avg_confidence": 0.68,
        "avg_latency_ms": 1580,
        "total_tokens": 45600,
        "estimated_cost_usd": 0.23,
    },
    "pilot_003": {
        "tenant_name": "Cafe Network",
        "period": "2026-05-14 to 2026-05-16",
        "interactions": 23,
        "escalations": 8,
        "approval_requests": 15,
        "approval_rejections": 3,
        "hallucination_flags": 2,
        "unsafe_output_blocks": 0,
        "operator_overrides": 2,
        "avg_confidence": 0.71,
        "avg_latency_ms": 1890,
        "total_tokens": 18900,
        "estimated_cost_usd": 0.09,
    },
}


def calculate_metrics(tenant_data: dict) -> dict:
    interactions = tenant_data["interactions"]
    if interactions == 0:
        return {k: 0 for k in [
            "escalation_rate", "approval_rate", "rejection_rate",
            "hallucination_rate", "unsafe_block_rate", "override_rate",
            "usefulness_score", "cost_per_interaction"
        ]}

    return {
        "escalation_rate": round(tenant_data["escalations"] / interactions * 100, 1),
        "approval_rate": round(tenant_data["approval_requests"] / interactions * 100, 1),
        "rejection_rate": round(tenant_data["approval_rejections"] / max(tenant_data["approval_requests"], 1) * 100, 1),
        "hallucination_rate": round(tenant_data["hallucination_flags"] / interactions * 100, 1),
        "unsafe_block_rate": round(tenant_data["unsafe_output_blocks"] / interactions * 100, 1),
        "override_rate": round(tenant_data["operator_overrides"] / interactions * 100, 1),
        "usefulness_score": round(max(0, min(100,
            tenant_data["avg_confidence"] * 100
            - tenant_data["hallucination_flags"] / max(interactions, 1) * 20
            - tenant_data["operator_overrides"] / max(interactions, 1) * 10
        )), 1),
        "cost_per_interaction": round(tenant_data["estimated_cost_usd"] / interactions, 4),
        "cost_per_1000_tokens": round(tenant_data["estimated_cost_usd"] / max(tenant_data["total_tokens"] / 1000, 1), 4),
    }


def classify_tenant(metrics: dict) -> str:
    if metrics["hallucination_rate"] > 5 or metrics["unsafe_block_rate"] > 1:
        return "AT_RISK"
    elif metrics["escalation_rate"] > 20 or metrics["override_rate"] > 10:
        return "NEEDS_ATTENTION"
    elif metrics["usefulness_score"] >= 75:
        return "HEALTHY"
    elif metrics["usefulness_score"] >= 60:
        return "ACCEPTABLE"
    else:
        return "NEEDS_ATTENTION"


def main() -> int:
    print("=" * 60)
    print("AI QUALITY & SAFETY TRACKING")
    print(f"Report Period: {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)

    overall = {
        "total_interactions": 0,
        "total_escalations": 0,
        "total_hallucinations": 0,
        "total_unsafe": 0,
        "total_overrides": 0,
        "total_tokens": 0,
        "total_cost": 0,
    }

    tenant_results = []

    for tenant_id, data in PILOT_AI_DATA.items():
        metrics = calculate_metrics(data)
        classification = classify_tenant(metrics)

        overall["total_interactions"] += data["interactions"]
        overall["total_escalations"] += data["escalations"]
        overall["total_hallucinations"] += data["hallucination_flags"]
        overall["total_unsafe"] += data["unsafe_output_blocks"]
        overall["total_overrides"] += data["operator_overrides"]
        overall["total_tokens"] += data["total_tokens"]
        overall["total_cost"] += data["estimated_cost_usd"]

        tenant_results.append({
            "tenant_id": tenant_id,
            "name": data["tenant_name"],
            "classification": classification,
            "metrics": metrics,
            "raw": data,
        })

        print(f"\n--- {data['tenant_name']} ({tenant_id}) ---")
        print(f"  Classification: {classification}")
        print(f"  Interactions: {data['interactions']} | Escalations: {data['escalations']} ({metrics['escalation_rate']}%)")
        print(f"  Hallucination rate: {metrics['hallucination_rate']}% | Unsafe blocks: {metrics['unsafe_block_rate']}%")
        print(f"  Override rate: {metrics['override_rate']}% | Avg confidence: {data['avg_confidence']:.0%}")
        print(f"  Usefulness score: {metrics['usefulness_score']}/100")
        print(f"  Cost: ${data['estimated_cost_usd']:.2f} ({metrics['cost_per_interaction']}/interaction)")
        print(f"  Avg latency: {data['avg_latency_ms']}ms")

    # Overall metrics
    print(f"\n{'=' * 60}")
    print("OVERALL PILOT AI METRICS")
    print(f"{'=' * 60}")
    total = overall["total_interactions"]
    print(f"  Total interactions: {total}")
    print(f"  Total escalations: {overall['total_escalations']} ({round(overall['total_escalations']/total*100,1) if total else 0}%)")
    print(f"  Total hallucinations: {overall['total_hallucinations']} ({round(overall['total_hallucinations']/total*100,1) if total else 0}%)")
    print(f"  Total unsafe blocks: {overall['total_unsafe']}")
    print(f"  Total operator overrides: {overall['total_overrides']}")
    print(f"  Total tokens: {overall['total_tokens']:,}")
    print(f"  Total cost: ${overall['total_cost']:.2f}")
    print(f"  Avg cost/interaction: ${overall['total_cost']/total:.4f}" if total else "  N/A")

    # Classifications
    classifications = [r["classification"] for r in tenant_results]
    healthy = classifications.count("HEALTHY")
    at_risk = classifications.count("AT_RISK")
    needs_attention = classifications.count("NEEDS_ATTENTION")

    print(f"\n  Tenant classifications:")
    print(f"    HEALTHY: {healthy} | NEEDS ATTENTION: {needs_attention} | AT RISK: {at_risk}")

    # Safety rules check
    print(f"\n--- Safety Rules Compliance ---")
    rule_violations = 0
    for r in tenant_results:
        if r["raw"]["avg_confidence"] < 0.75 and r["metrics"]["escalation_rate"] < 10:
            print(f"  VIOLATION: {r['name']} - Confidence < 75% but escalation rate < 10%")
            rule_violations += 1
        if r["raw"]["unsafe_output_blocks"] > 0:
            print(f"  ALERT: {r['name']} - {r['raw']['unsafe_output_blocks']} unsafe outputs blocked")

    if rule_violations == 0:
        print("  All safety rules compliant")

    # Save report
    report = {
        "generated_at": datetime.now().isoformat(),
        "overall": overall,
        "tenants": tenant_results,
        "classifications": {
            "HEALTHY": healthy,
            "NEEDS_ATTENTION": needs_attention,
            "AT_RISK": at_risk,
        },
        "safety_violations": rule_violations,
        "recommendations": generate_recommendations(tenant_results),
    }

    output_path = PROJECT_ROOT / "scripts" / "staging" / "ai_quality_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'=' * 60}")
    print(f"Report saved: {output_path}")
    if at_risk > 0:
        print(f"STATUS: {at_risk} tenant(s) AT RISK - immediate attention required")
        return 1
    elif needs_attention > 0:
        print(f"STATUS: {needs_attention} tenant(s) need attention")
        return 0
    else:
        print("STATUS: All tenants healthy")
        return 0


def generate_recommendations(results: list) -> list:
    recs = []
    for r in results:
        if r["classification"] == "AT_RISK":
            recs.append(f"{r['name']}: Reduce AI scope, increase approval requirements")
        elif r["classification"] == "NEEDS_ATTENTION":
            recs.append(f"{r['name']}: Review knowledge base, add more training data")
        if r["metrics"]["hallucination_rate"] > 5:
            recs.append(f"{r['name']}: Hallucination rate high - review RAG configuration")
        if r["raw"]["avg_latency_ms"] > 1500:
            recs.append(f"{r['name']}: AI latency high - consider model downgrade")
    return recs


if __name__ == "__main__":
    sys.exit(main())
