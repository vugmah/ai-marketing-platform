"""Pilot Feedback Collector

Collects and analyzes pilot customer feedback to identify product improvements.
Usage: cd backend && python scripts/staging/pilot_feedback_collector.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Simulated pilot feedback data
PILOT_FEEDBACK = {
    "pilot_001": {
        "name": "Demo Market",
        "feature_usage": {
            "ai_chat": 89,
            "ai_support": 45,
            "analytics_dashboard": 34,
            "follower_intelligence": 12,
            "social_media_connect": 8,
            "whatsapp_integration": 67,
            "erp_sync": 23,
            "campaign_management": 15,
            "creative_studio": 5,
            "reports_export": 28,
            "knowledge_base": 19,
            "branch_management": 3,
        },
        "error_flows": [
            {"flow": "WhatsApp QR reconnect", "count": 4, "severity": "medium"},
            {"flow": "ERP date format", "count": 2, "severity": "low"},
            {"flow": "AI knowledge upload", "count": 1, "severity": "low"},
        ],
        "satisfaction_scores": {
            "overall": 8,
            "ai_quality": 7,
            "support_quality": 9,
            "onboarding": 8,
            "erp_integration": 6,
            "social_connect": 7,
        },
        "free_text_feedback": [
            "AI responses are good but sometimes slow",
            "WhatsApp connection is unstable, needs reconnect often",
            "Reports are helpful, need more templates",
            "ERP sync works but date formats are confusing",
        ],
    },
    "pilot_002": {
        "name": "TechStore Istanbul",
        "feature_usage": {
            "ai_chat": 34,
            "ai_support": 12,
            "analytics_dashboard": 56,
            "follower_intelligence": 8,
            "social_media_connect": 23,
            "whatsapp_integration": 15,
            "erp_sync": 45,
            "campaign_management": 3,
            "creative_studio": 2,
            "reports_export": 34,
            "knowledge_base": 8,
            "branch_management": 2,
        },
        "error_flows": [
            {"flow": "Instagram auth expire", "count": 6, "severity": "high"},
            {"flow": "ERP connection timeout", "count": 3, "severity": "medium"},
            {"flow": "AI low confidence escalation", "count": 8, "severity": "medium"},
        ],
        "satisfaction_scores": {
            "overall": 6,
            "ai_quality": 5,
            "support_quality": 7,
            "onboarding": 5,
            "erp_integration": 7,
            "social_connect": 4,
        },
        "free_text_feedback": [
            "Instagram disconnects every 2 days, very frustrating",
            "AI needs more training on tech products",
            "ERP integration is the most valuable feature",
            "Support team is responsive but AI quality needs work",
        ],
    },
    "pilot_003": {
        "name": "Cafe Network",
        "feature_usage": {
            "ai_chat": 12,
            "ai_support": 8,
            "analytics_dashboard": 15,
            "follower_intelligence": 5,
            "social_media_connect": 12,
            "whatsapp_integration": 23,
            "erp_sync": 8,
            "campaign_management": 2,
            "creative_studio": 0,
            "reports_export": 10,
            "knowledge_base": 5,
            "branch_management": 1,
        },
        "error_flows": [
            {"flow": "Knowledge upload fail", "count": 2, "severity": "medium"},
            {"flow": "User invite not received", "count": 1, "severity": "low"},
        ],
        "satisfaction_scores": {
            "overall": 7,
            "ai_quality": 6,
            "support_quality": 8,
            "onboarding": 6,
            "erp_integration": 5,
            "social_connect": 7,
        },
        "free_text_feedback": [
            "Good start but too many features for a small cafe",
            "Need simpler onboarding for small businesses",
            "WhatsApp order taking is promising",
            "Want easier campaign creation templates",
        ],
    },
}


def analyze_feature_usage(feedback: dict) -> dict:
    """Analyze which features are most/least used."""
    all_features = {}
    for tenant_id, data in feedback.items():
        for feature, count in data["feature_usage"].items():
            if feature not in all_features:
                all_features[feature] = {"total": 0, "tenants": 0}
            all_features[feature]["total"] += count
            if count > 0:
                all_features[feature]["tenants"] += 1

    sorted_features = sorted(all_features.items(), key=lambda x: -x[1]["total"])
    return {
        "most_used": sorted_features[:5],
        "least_used": sorted_features[-5:],
        "unused_by_all": [f for f, d in sorted_features if d["tenants"] == 0],
        "all": sorted_features,
    }


def analyze_errors(feedback: dict) -> dict:
    """Analyze error flows across tenants."""
    all_errors = {}
    for tenant_id, data in feedback.items():
        for error in data["error_flows"]:
            flow = error["flow"]
            if flow not in all_errors:
                all_errors[flow] = {"total": 0, "tenants": 0, "max_severity": "low"}
            all_errors[flow]["total"] += error["count"]
            all_errors[flow]["tenants"] += 1
            if error["severity"] == "high":
                all_errors[flow]["max_severity"] = "high"
            elif error["severity"] == "medium" and all_errors[flow]["max_severity"] == "low":
                all_errors[flow]["max_severity"] = "medium"

    return {
        "total_errors": sum(e["total"] for e in all_errors.values()),
        "flows": sorted(all_errors.items(), key=lambda x: -x[1]["total"]),
        "critical_flows": [f for f, d in all_errors.items() if d["max_severity"] == "high"],
    }


def analyze_satisfaction(feedback: dict) -> dict:
    """Analyze satisfaction scores."""
    categories = {}
    for tenant_id, data in feedback.items():
        for category, score in data["satisfaction_scores"].items():
            if category not in categories:
                categories[category] = []
            categories[category].append(score)

    avg_scores = {
        cat: round(sum(scores) / len(scores), 1)
        for cat, scores in categories.items()
    }
    return {
        "averages": sorted(avg_scores.items(), key=lambda x: -x[1]),
        "lowest": min(avg_scores.items(), key=lambda x: x[1]),
        "highest": max(avg_scores.items(), key=lambda x: x[1]),
    }


def generate_improvements(feature_analysis, error_analysis, satisfaction) -> dict:
    """Generate product improvement list."""
    improvements = []

    # From least used features
    for feature, data in feature_analysis["least_used"][:3]:
        if data["tenants"] <= 1:
            improvements.append({
                "type": "UX_SIMPLIFICATION",
                "feature": feature,
                "issue": f"Low adoption: only {data['tenants']} tenant(s) use it",
                "recommendation": f"Simplify {feature} or merge with related feature",
                "priority": "medium",
            })

    # From error flows
    for flow, data in error_analysis["flows"][:5]:
        improvements.append({
            "type": "BUG_FIX",
            "feature": flow,
            "issue": f"{data['total']} errors across {data['tenants']} tenant(s)",
            "recommendation": f"Fix {flow} reliability",
            "priority": "high" if data["max_severity"] == "high" else "medium",
        })

    # From satisfaction scores
    lowest_cat = satisfaction["lowest"]
    improvements.append({
        "type": "AI_IMPROVEMENT" if "ai" in lowest_cat[0] else "FEATURE_IMPROVEMENT",
        "feature": lowest_cat[0],
        "issue": f"Lowest satisfaction: {lowest_cat[1]}/10",
        "recommendation": f"Investigate {lowest_cat[0]} pain points",
        "priority": "high",
    })

    # From feedback text
    improvements.append({
        "type": "OPERATIONAL",
        "feature": "onboarding",
        "issue": "Small businesses find onboarding complex",
        "recommendation": "Create simplified onboarding for < 5 user businesses",
        "priority": "high",
    })

    return improvements


def main() -> int:
    print("=" * 60)
    print("PILOT FEEDBACK COLLECTOR & ANALYZER")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)

    # Feature usage analysis
    print("\n--- Feature Usage Analysis ---")
    feature_analysis = analyze_feature_usage(PILOT_FEEDBACK)
    print(f"\n  Most used features:")
    for feature, data in feature_analysis["most_used"]:
        print(f"    {feature}: {data['total']} uses ({data['tenants']} tenant(s))")
    print(f"\n  Least used features:")
    for feature, data in feature_analysis["least_used"]:
        print(f"    {feature}: {data['total']} uses ({data['tenants']} tenant(s))")
    if feature_analysis["unused_by_all"]:
        print(f"\n  Unused by all tenants: {', '.join(feature_analysis['unused_by_all'])}")

    # Error analysis
    print(f"\n--- Error Flow Analysis ---")
    error_analysis = analyze_errors(PILOT_FEEDBACK)
    print(f"  Total errors: {error_analysis['total_errors']}")
    print(f"  Critical flows: {', '.join(error_analysis['critical_flows']) if error_analysis['critical_flows'] else 'None'}")
    for flow, data in error_analysis["flows"]:
        print(f"    {flow}: {data['total']} errors ({data['tenants']} tenant(s)) [{data['max_severity']}]")

    # Satisfaction analysis
    print(f"\n--- Satisfaction Scores ---")
    satisfaction = analyze_satisfaction(PILOT_FEEDBACK)
    for category, score in satisfaction["averages"]:
        print(f"    {category}: {score}/10")

    # Improvement list
    print(f"\n--- Generated Improvements ---")
    improvements = generate_improvements(feature_analysis, error_analysis, satisfaction)
    for i, imp in enumerate(improvements, 1):
        print(f"\n  {i}. [{imp['priority'].upper()}] {imp['type']}: {imp['feature']}")
        print(f"     Issue: {imp['issue']}")
        print(f"     Action: {imp['recommendation']}")

    # Save report
    report = {
        "generated_at": datetime.now().isoformat(),
        "tenant_count": len(PILOT_FEEDBACK),
        "feature_analysis": {
            "most_used": feature_analysis["most_used"],
            "least_used": feature_analysis["least_used"],
        },
        "error_analysis": {
            "total": error_analysis["total_errors"],
            "critical_flows": error_analysis["critical_flows"],
            "flows": error_analysis["flows"],
        },
        "satisfaction": satisfaction["averages"],
        "improvements": improvements,
    }

    output = PROJECT_ROOT / "scripts" / "staging" / "pilot_feedback_report.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n{'=' * 60}")
    print(f"Report saved: {output}")
    print(f"Total improvements: {len(improvements)}")
    print(f"Critical: {sum(1 for i in improvements if i['priority'] == 'high')}")
    print(f"Status: FEEDBACK ANALYZED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
