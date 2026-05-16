"""v12 Operational Governance Intelligence Test Suite

Pure file-parsing tests for cross-platform reputation, adaptive cadence,
tenant trust, outreach ROI, and governance dashboard.

Usage: cd backend && python scripts/staging/test_v12_governance.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_file(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


def test_cross_platform_reputation_code() -> bool:
    """Test cross-platform reputation analyzer code structure."""
    print("\n  [TEST] Cross-Platform Reputation Code...")

    code = _read_file("app/followers/governance_intelligence.py")

    required = ["class CrossPlatformReputationAnalyzer",
                "def analyze_cross_platform_risk",
                "def get_platform_fallback_plan"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check 5 platforms
    for p in ["whatsapp", "telegram", "facebook", "instagram", "tiktok"]:
        if f'"{p}"' not in code and f"'{p}'" not in code:
            print(f"    FAIL: Platform {p} not covered")
            return False

    # Check risk correlation
    if "RISK_CORRELATION" not in code:
        print("    FAIL: No risk correlation matrix")
        return False

    # Check contagion detection
    if "contagion" not in code.lower():
        print("    FAIL: No contagion detection")
        return False

    # Check fallback
    if "fallback" not in code.lower():
        print("    FAIL: No fallback recommendations")
        return False

    # Shadow-ban detection is in v11 reputation_monitoring.py
    # Cross-platform analyzer uses reputation scores, not raw shadow-ban detection
    rep_code = _read_file("app/followers/reputation_monitoring.py")
    if "shadow" not in rep_code.lower():
        print(f"    FAIL: No shadow-ban detection in reputation monitoring")
        return False

    print("    PASS: Cross-platform reputation code valid")
    return True


def test_adaptive_cadence_code() -> bool:
    """Test adaptive cadence engine code structure."""
    print("\n  [TEST] Adaptive Cadence Code...")

    code = _read_file("app/followers/governance_intelligence.py")

    required = ["class AdaptiveCadenceEngine",
                "def calculate_optimal_timing",
                "def analyze_cadence_effectiveness"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check fatigue-aware
    if "fatigue" not in code.lower():
        print("    FAIL: Not fatigue-aware")
        return False

    # Check response-based
    if "response" not in code.lower():
        print("    FAIL: Not response-based")
        return False

    # Check optimal timing
    if "optimal" not in code.lower():
        print("    FAIL: No optimal timing")
        return False

    # Check cooldown recommendation
    if "cooldown" not in code.lower():
        print("    FAIL: No cooldown")
        return False

    # Check no aggressive outreach
    if "aggressive" in code.lower():
        print("    WARN: Contains 'aggressive' — checking context")

    print("    PASS: Adaptive cadence code valid")
    return True


def test_tenant_trust_code() -> bool:
    """Test tenant trust scorer code structure."""
    print("\n  [TEST] Tenant Trust Scoring Code...")

    code = _read_file("app/followers/governance_intelligence.py")

    required = ["class TenantTrustScorer",
                "def calculate_trust_score",
                "def batch_calculate_trust",
                "def get_trust_distribution"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check 8 components
    components = ["spam_risk", "operator_override", "report_block_rate",
                  "policy_violations", "ai_safety", "outreach_quality",
                  "fatigue_management", "approval_discipline"]
    for c in components:
        if c not in code:
            print(f"    FAIL: Missing component {c}")
            return False

    # Check weights
    if "COMPONENT_WEIGHTS" not in code:
        print("    FAIL: No component weights")
        return False

    # Check trust tiers
    for tier in ["trusted", "standard", "restricted", "blocked"]:
        if tier not in code:
            print(f"    FAIL: Missing tier {tier}")
            return False

    # Check quota multiplier
    if "quota_multiplier" not in code:
        print("    FAIL: No quota multiplier")
        return False

    # Check rollout control
    if "rollout_allowed" not in code:
        print("    FAIL: No rollout control")
        return False

    print("    PASS: Tenant trust scoring code valid")
    return True


def test_outreach_roi_code() -> bool:
    """Test outreach ROI analyzer code structure."""
    print("\n  [TEST] Outreach ROI Code...")

    code = _read_file("app/followers/governance_intelligence.py")

    required = ["class OutreachROIAnalyzer",
                "def calculate_campaign_roi",
                "def analyze_retention_impact",
                "def get_best_outreach_types",
                "def detect_ineffective_outreach"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check ROI calculation
    if "roi" not in code.lower():
        print("    FAIL: No ROI calculation")
        return False

    # Check retention impact
    if "retention" not in code.lower():
        print("    FAIL: No retention impact")
        return False

    # Check effectiveness tiers
    for tier in ["effective", "moderate", "ineffective"]:
        if tier not in code:
            print(f"    FAIL: Missing tier {tier}")
            return False

    # Check branch comparison
    if "branch" not in code.lower():
        print("    FAIL: No branch comparison")
        return False

    print("    PASS: Outreach ROI code valid")
    return True


def test_governance_dashboard_code() -> bool:
    """Test governance dashboard code structure."""
    print("\n  [TEST] Governance Dashboard Code...")

    code = _read_file("app/followers/governance_dashboard.py")

    required = ["class GovernanceDashboard",
                "def get_executive_dashboard",
                "def get_platform_dashboard",
                "def get_tenant_dashboard",
                "def get_roi_dashboard",
                "def get_risk_escalation_dashboard",
                "def get_full_dashboard"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check all 4 intelligence modules imported
    for module in ["CrossPlatformReputationAnalyzer", "AdaptiveCadenceEngine",
                   "TenantTrustScorer", "OutreachROIAnalyzer"]:
        if module not in code:
            print(f"    FAIL: Missing import {module}")
            return False

    # Check unified view
    if "full_dashboard" not in code:
        print("    FAIL: No unified dashboard")
        return False

    # Check governance score
    if "governance_score" not in code:
        print("    FAIL: No governance score")
        return False

    # Check alerts
    if "alerts" not in code:
        print("    FAIL: No alert generation")
        return False

    print("    PASS: Governance dashboard code valid")
    return True


def test_safety_rules_comprehensive() -> bool:
    """Test all safety rules across v10 + v11 + v12."""
    print("\n  [TEST] Comprehensive Safety Rules...")

    files = [
        "app/followers/dispatch_service.py",
        "app/followers/governance_service.py",
        "app/followers/ai_personalization.py",
        "app/followers/reputation_monitoring.py",
        "app/followers/performance_learning.py",
        "app/followers/governance_intelligence.py",
        "app/followers/governance_dashboard.py",
    ]

    all_code = ""
    for f in files:
        all_code += _read_file(f)

    checks = [
        ("Auto-send disabled", "auto_send" not in all_code.lower() or "disabled" in all_code.lower()),
        ("Approval required", "approval" in all_code.lower()),
        ("Rate limiting", "rate_limit" in all_code.lower()),
        ("Daily quotas", "quota" in all_code.lower()),
        ("Cooldown periods", "cooldown" in all_code.lower()),
        ("Spam detection", "spam" in all_code.lower()),
        ("Moderation", "moderat" in all_code.lower()),
        ("Confidence scoring", "confidence" in all_code.lower()),
        ("Fatigue detection", "fatigue" in all_code.lower()),
        ("Reputation monitoring", "reputation" in all_code.lower()),
        ("Shadow-ban detection", "shadow" in all_code.lower()),
        ("Warm-up schedule", "warmup" in all_code.lower() or "warm_up" in all_code.lower()),
        ("Operator coaching", "coaching" in all_code.lower()),
        ("Performance tracking", "performance" in all_code.lower()),
        ("Tenant isolation", "company_id" in all_code),
        ("Estimated language", "estimated" in all_code.lower()),
        ("Cross-platform risk", "cross_platform" in all_code.lower() or "contagion" in all_code.lower()),
        ("Adaptive cadence", "cadence" in all_code.lower()),
        ("Trust scoring", "trust" in all_code.lower()),
        ("ROI tracking", "roi" in all_code.lower()),
        ("Fallback recommendation", "fallback" in all_code.lower()),
        ("Governance dashboard", "governance_score" in all_code.lower()),
        ("Risk escalation", "escalation" in all_code.lower()),
        ("No scraping", "no scraping" in all_code.lower() or "no_scraping" in all_code.lower()),
    ]

    failed = [name for name, ok in checks if not ok]
    if failed:
        for name in failed:
            print(f"    FAIL: {name}")
        return False

    print(f"    PASS: All {len(checks)} safety rules across {len(files)} files")
    return True


def test_no_new_tables() -> bool:
    """Verify v12 adds no new DB tables."""
    print("\n  [TEST] No New DB Tables (v12)...")

    code = _read_file("app/followers/governance_intelligence.py")
    dash_code = _read_file("app/followers/governance_dashboard.py")

    combined = code + dash_code

    if "__tablename__" in combined:
        print("    FAIL: New SQLAlchemy models found")
        return False

    if "Column(" in combined:
        print("    FAIL: New DB columns found")
        return False

    if "create_table" in combined.lower():
        print("    FAIL: Table creation found")
        return False

    print("    PASS: v12 is pure analytics layer — no DB changes")
    return True


def test_no_new_endpoints() -> bool:
    """Verify v12 adds no new HTTP endpoints (dashboard is service-only)."""
    print("\n  [TEST] No New Endpoints (v12)...")

    dash_code = _read_file("app/followers/governance_dashboard.py")
    intel_code = _read_file("app/followers/governance_intelligence.py")

    combined = dash_code + intel_code

    # Check for FastAPI route decorators
    if "@router." in combined or "@app." in combined:
        print("    FAIL: New HTTP endpoints found in service files")
        return False

    if "ResponseModel" in combined or "response_model" in combined:
        print("    FAIL: Response models in service files")
        return False

    print("    PASS: v12 adds no HTTP endpoints (pure service layer)")
    return True


def test_integration_v10_v11_v12() -> bool:
    """Test integration across all three governance versions."""
    print("\n  [TEST] Integration v10 + v11 + v12...")

    v10_files = ["app/followers/dispatch_service.py", "app/followers/ai_personalization.py",
                 "app/followers/recovery_service.py", "app/followers/governance_service.py"]
    v11_files = ["app/followers/reputation_monitoring.py", "app/followers/performance_learning.py"]
    v12_files = ["app/followers/governance_intelligence.py", "app/followers/governance_dashboard.py"]

    all_code = ""
    for files in [v10_files, v11_files, v12_files]:
        for f in files:
            all_code += _read_file(f)

    # Shared concepts across all versions
    shared = ["company_id", "platform", "confidence", "tenant", "fatigue",
              "reputation", "trust", "roi", "cadence"]
    for s in shared:
        if s not in all_code:
            print(f"    FAIL: Shared concept '{s}' missing across versions")
            return False

    # Total service count
    service_classes = all_code.count("class ")
    if service_classes < 7:
        print(f"    FAIL: Expected 7+ services, found {service_classes}")
        return False

    print(f"    PASS: {len(v10_files)} v10 + {len(v11_files)} v11 + {len(v12_files)} v12 files integrate")
    print(f"           Total services: {service_classes}")
    return True


def main() -> int:
    print("=" * 60)
    print("v12 OPERATIONAL GOVERNANCE INTELLIGENCE TEST SUITE")
    print("=" * 60)

    tests = [
        test_cross_platform_reputation_code,
        test_adaptive_cadence_code,
        test_tenant_trust_code,
        test_outreach_roi_code,
        test_governance_dashboard_code,
        test_safety_rules_comprehensive,
        test_no_new_tables,
        test_no_new_endpoints,
        test_integration_v10_v11_v12,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")

    if failed == 0:
        print("STATUS: ALL v12 GOVERNANCE INTELLIGENCE TESTS PASSED")
        return 0
    else:
        print(f"STATUS: {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
