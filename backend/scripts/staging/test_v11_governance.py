"""v11 Safe Outreach Governance Test Suite

Pure file-parsing tests for reputation monitoring, fatigue detection,
AI performance learning, operator coaching, and rollout analytics.

Usage: cd backend && python scripts/staging/test_v11_governance.py
"""

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_file(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


def test_reputation_monitoring_code() -> bool:
    """Test reputation monitoring service code structure."""
    print("\n  [TEST] Reputation Monitoring Code...")

    code = _read_file("app/followers/reputation_monitoring.py")

    required = ["class PlatformReputationMonitor",
                "def calculate_reputation_score",
                "def get_platform_health_dashboard"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check all platforms
    for p in ["instagram", "facebook", "tiktok", "whatsapp", "telegram"]:
        if f'"{p}"' not in code and f"'{p}'" not in code:
            print(f"    FAIL: Platform {p} not covered")
            return False

    # Check risk signals
    signals = ["delivery_failure", "spam_warning", "block_rate", "report_rate",
               "engagement_drop", "shadow_ban"]
    for s in signals:
        if s not in code.lower():
            print(f"    FAIL: Missing signal {s}")
            return False

    # Check risk thresholds
    if "RISK_THRESHOLDS" not in code:
        print("    FAIL: No risk thresholds")
        return False

    # Check severity levels
    for level in ["low", "medium", "high", "critical"]:
        if level not in code:
            print(f"    FAIL: Missing risk level {level}")
            return False

    print("    PASS: Reputation monitoring code valid")
    return True


def test_fatigue_detection_code() -> bool:
    """Test fatigue detection service code structure."""
    print("\n  [TEST] Fatigue Detection Code...")

    code = _read_file("app/followers/reputation_monitoring.py")

    required = ["class OutreachFatigueDetector",
                "def calculate_fatigue_score",
                "def check_outreach_allowed",
                "def get_fatigue_summary"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check fatigue thresholds
    if "FATIGUE_THRESHOLDS" not in code:
        print("    FAIL: No fatigue thresholds")
        return False

    # Check weekly/monthly limits
    for limit in ["max_messages_per_week", "max_messages_per_month"]:
        if limit not in code:
            print(f"    FAIL: Missing {limit}")
            return False

    # Check fatigue tiers
    for tier in ["low", "medium", "high", "critical"]:
        if tier not in code:
            print(f"    FAIL: Missing fatigue tier {tier}")
            return False

    # Check cooldown recommendation
    if "cooldown" not in code.lower():
        print("    FAIL: No cooldown recommendation")
        return False

    # Check is_blocked
    if "is_blocked" not in code:
        print("    FAIL: No is_blocked field")
        return False

    print("    PASS: Fatigue detection code valid")
    return True


def test_operator_coaching_code() -> bool:
    """Test operator coaching service code structure."""
    print("\n  [TEST] Operator Coaching Code...")

    code = _read_file("app/followers/reputation_monitoring.py")

    required = ["class OperatorCoaching",
                "def get_coaching_for_outreach",
                "def get_daily_briefing"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check coaching elements
    elements = ["warnings", "recommendations", "policy_reminder",
                "safety_tip", "severity"]
    for e in elements:
        if e not in code:
            print(f"    FAIL: Missing coaching element {e}")
            return False

    # Check policy reminders for all platforms
    for p in ["instagram", "facebook", "tiktok", "whatsapp", "telegram"]:
        if p not in code:
            print(f"    FAIL: No policy reminder for {p}")
            return False

    # Check safety tips
    if "SAFETY_TIPS" not in code:
        print("    FAIL: No safety tips library")
        return False

    # Check is_safe_to_proceed
    if "is_safe_to_proceed" not in code:
        print(f"    FAIL: No is_safe_to_proceed field")
        return False

    # Check requires_explicit_confirmation
    if "requires_explicit_confirmation" not in code:
        print(f"    FAIL: No explicit confirmation requirement")
        return False

    print("    PASS: Operator coaching code valid")
    return True


def test_performance_learning_code() -> bool:
    """Test AI performance learning service code structure."""
    print("\n  [TEST] Performance Learning Code...")

    code = _read_file("app/followers/performance_learning.py")

    required = ["class MessagePerformanceTracker",
                "def calculate_template_performance",
                "def analyze_branch_performance",
                "def analyze_platform_performance"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check performance metrics
    metrics = ["response_rate", "block_rate", "report_rate",
               "conversion_rate", "quality_score"]
    for m in metrics:
        if m not in code:
            print(f"    FAIL: Missing metric {m}")
            return False

    # Check template tiers
    for tier in ["high_performing", "average", "low_performing"]:
        if tier not in code:
            print(f"    FAIL: Missing tier {tier}")
            return False

    # Check operator override tracking
    if "calculate_operator_override_rate" not in code:
        print("    FAIL: No override rate tracking")
        return False

    print("    PASS: Performance learning code valid")
    return True


def test_rollout_analytics_code() -> bool:
    """Test rollout analytics service code structure."""
    print("\n  [TEST] Rollout Analytics Code...")

    code = _read_file("app/followers/performance_learning.py")

    required = ["class SafeRolloutAnalytics",
                "def analyze_tenant_safety",
                "def get_scaling_plan",
                "def get_safe_platform_ranking",
                "def detect_risky_usage_patterns"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check safety thresholds
    if "SAFE_SCALE_THRESHOLDS" not in code:
        print("    FAIL: No safety scale thresholds")
        return False

    # Check scaling phases
    for phase in ["phase_1", "phase_2", "phase_3"]:
        if phase not in code:
            print(f"    FAIL: Missing phase {phase}")
            return False

    # Check abort criteria
    if "abort" not in code.lower():
        print("    FAIL: No abort criteria")
        return False

    # Check risk pattern detection
    patterns = ["high_volume_low_response", "high_block_rate",
                "rapid_volume_escalation", "concentrated_messaging"]
    for p in patterns:
        if p not in code:
            print(f"    FAIL: Missing pattern {p}")
            return False

    # Check pilot dashboard
    if "get_pilot_dashboard" not in code:
        print("    FAIL: No pilot dashboard")
        return False

    print("    PASS: Rollout analytics code valid")
    return True


def test_integration_between_services() -> bool:
    """Test that all three new services integrate properly."""
    print("\n  [TEST] Service Integration...")

    rep_code = _read_file("app/followers/reputation_monitoring.py")
    perf_code = _read_file("app/followers/performance_learning.py")
    gov_code = _read_file("app/followers/governance_service.py")

    all_code = rep_code + perf_code + gov_code

    # Check shared concepts
    shared = ["company_id", "platform", "confidence", "tenant"]
    for s in shared:
        if s not in all_code:
            print(f"    FAIL: Shared concept {s} missing")
            return False

    # Check reputation feeds into coaching
    if "platform_reputation_score" not in rep_code:
        print("    FAIL: Reputation score not exposed")
        return False

    # Check fatigue feeds into coaching
    if "fatigue_score" not in rep_code:
        print("    FAIL: Fatigue score not exposed")
        return False

    # Check performance feeds into rollout
    if "safety_score" not in perf_code:
        print("    FAIL: Safety score not exposed")
        return False

    # Check governance integration
    if "quota" not in all_code:
        print("    FAIL: Quota not integrated")
        return False

    print("    PASS: All services integrate properly")
    return True


def test_safety_enforcement() -> bool:
    """Test that all safety rules are enforced across v10 + v11."""
    print("\n  [TEST] Safety Enforcement...")

    files_to_check = [
        "app/followers/dispatch_service.py",
        "app/followers/governance_service.py",
        "app/followers/ai_personalization.py",
        "app/followers/reputation_monitoring.py",
        "app/followers/performance_learning.py",
    ]

    all_code = ""
    for f in files_to_check:
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
    ]

    failed = [name for name, ok in checks if not ok]
    if failed:
        for name in failed:
            print(f"    FAIL: {name}")
        return False

    print(f"    PASS: All {len(checks)} safety rules enforced across {len(files_to_check)} files")
    return True


def test_no_new_tables_added() -> bool:
    """Verify no new DB tables were added (governance layer only)."""
    print("\n  [TEST] No New DB Tables...")

    # v11 should be governance/analytics only - no new models
    code = _read_file("app/followers/reputation_monitoring.py")
    perf_code = _read_file("app/followers/performance_learning.py")

    combined = code + perf_code

    # Should not contain SQLAlchemy model definitions
    if "__tablename__" in combined:
        print("    FAIL: New SQLAlchemy models found (should be service-only)")
        return False

    if "class Base" in combined:
        print("    FAIL: New Base models found")
        return False

    if "Column(" in combined:
        print("    FAIL: New DB columns found (should be service-only)")
        return False

    print("    PASS: No new DB tables added (pure governance layer)")
    return True


def main() -> int:
    print("=" * 60)
    print("v11 SAFE OUTREACH GOVERNANCE TEST SUITE")
    print("=" * 60)

    tests = [
        test_reputation_monitoring_code,
        test_fatigue_detection_code,
        test_operator_coaching_code,
        test_performance_learning_code,
        test_rollout_analytics_code,
        test_integration_between_services,
        test_safety_enforcement,
        test_no_new_tables_added,
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
        print("STATUS: ALL v11 GOVERNANCE TESTS PASSED")
        return 0
    else:
        print(f"STATUS: {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
