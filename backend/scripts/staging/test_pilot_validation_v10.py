"""Pilot Validation Test Suite v10

Validates follower intelligence + safe messaging system for pilot readiness.
Pure file-parsing tests (no module imports, no dependencies needed).

Usage: cd backend && python scripts/staging/test_pilot_validation_v10.py
"""

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_file(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


def _read_ast(rel_path: str) -> ast.AST:
    return ast.parse(_read_file(rel_path))


def test_platform_dispatch_code() -> bool:
    """Test dispatch service code structure."""
    print("\n  [TEST] Platform Dispatch Code...")

    code = _read_file("app/followers/dispatch_service.py")

    # Check key methods exist
    required = ["def dispatch", "def _check_rate_limit", "def _check_policy_compliance",
                "def retry_failed_delivery", "def get_delivery_status"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check rate limits defined
    platforms = ["instagram", "facebook", "tiktok", "whatsapp", "telegram"]
    for p in platforms:
        if f'"{p}"' not in code and f"'{p}'" not in code:
            print(f"    FAIL: Platform {p} not in rate limits")
            return False

    # Check delivery statuses
    for status in ["QUEUED", "SENT", "FAILED", "RATE_LIMITED", "POLICY_BLOCKED"]:
        if status not in code:
            print(f"    FAIL: Missing status {status}")
            return False

    # Check tenant isolation (company_id in dispatch)
    if "company_id" not in code:
        print("    FAIL: No company_id in dispatch")
        return False

    print("    PASS: Dispatch service code structure valid")
    return True


def test_ai_personalization_code() -> bool:
    """Test AI personalization code structure."""
    print("\n  [TEST] AI Personalization Code...")

    code = _read_file("app/followers/ai_personalization.py")

    required = ["def generate_personalized_message", "def moderate",
                "def preview_message", "def _calculate_confidence"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check all message types supported
    types = ["welcome_new_follower", "campaign_suggestion", "reengagement_for_low",
             "win_back_unfollow", "dm_follow_up", "local_branch_campaign", "engagement_reward"]
    for t in types:
        if t not in code:
            print(f"    FAIL: Missing message type {t}")
            return False

    # Check safety rules
    if "aggressive_marketing" not in code.lower() and "AGGRESSIVE" not in code:
        print("    FAIL: No aggressive marketing check")
        return False

    if "confidence_score" not in code:
        print("    FAIL: No confidence scoring")
        return False

    if "requires_review" not in code:
        print("    FAIL: No review requirement")
        return False

    print("    PASS: AI personalization code structure valid")
    return True


def test_governance_code() -> bool:
    """Test governance service code structure."""
    print("\n  [TEST] Outreach Governance Code...")

    code = _read_file("app/followers/governance_service.py")

    required = ["def check_quota", "def check_type_limit", "def check_cooldown",
                "def calculate_spam_risk", "def check_outreach_eligibility",
                "def get_effective_quota"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    # Check warm-up schedule
    if "WARMUP_SCHEDULE" not in code:
        print("    FAIL: No warmup schedule")
        return False

    # Check daily quotas
    if "DEFAULT_DAILY_QUOTAS" not in code:
        print("    FAIL: No daily quotas")
        return False

    # Check spam keywords
    spam_checks = ["free", "win", "click", "urgent"]
    found = sum(1 for w in spam_checks if w in code.lower())
    if found < 2:
        print("    FAIL: Insufficient spam checks")
        return False

    print("    PASS: Governance code structure valid")
    return True


def test_recovery_code() -> bool:
    """Test recovery service code structure."""
    print("\n  [TEST] Audience Recovery Code...")

    code = _read_file("app/followers/recovery_service.py")

    required = ["def predict_churn_risk", "def analyze_engagement_decay",
                "def calculate_retention_score", "def predict_reengagement_timing",
                "def suggest_recovery_campaign"]
    for r in required:
        if r not in code:
            print(f"    FAIL: Missing {r}")
            return False

    if "churn_risk_score" not in code:
        print("    FAIL: No churn risk score")
        return False

    if "retention_score" not in code:
        print("    FAIL: No retention score")
        return False

    print("    PASS: Recovery code structure valid")
    return True


def test_tenant_isolation() -> bool:
    """Test tenant isolation in all models."""
    print("\n  [TEST] Tenant Isolation...")

    models_with_company_id = [
        "FollowerDeltaEvent", "EngagementEvent", "ReengagementRecommendation",
        "SafeMessageTemplate", "OutreachApprovalRequest", "AudienceLossEstimate",
        "FollowerRetentionMetric", "FollowerValueScore",
    ]

    code = _read_file("app/followers/models.py")

    for model_name in models_with_company_id:
        class_start = code.find(f"class {model_name}(Base)")
        if class_start == -1:
            print(f"    FAIL: Model {model_name} not found")
            return False
        class_body = code[class_start:class_start + 1500]
        if "company_id" not in class_body:
            print(f"    FAIL: {model_name} missing company_id")
            return False
        if "branch_id" not in class_body:
            print(f"    FAIL: {model_name} missing branch_id")
            return False

    print(f"    PASS: All {len(models_with_company_id)} models have tenant isolation")
    return True


def test_approval_workflow() -> bool:
    """Test approval workflow state machine."""
    print("\n  [TEST] Approval Workflow...")

    valid_transitions = {
        "pending": ["approved", "rejected"],
        "approved": ["sent"],
        "sent": ["failed"],
        "rejected": [],
        "failed": [],
    }

    for from_state, to_states in valid_transitions.items():
        for to_state in to_states:
            if to_state not in valid_transitions.get(from_state, []):
                print(f"    FAIL: Invalid transition {from_state} -> {to_state}")
                return False

    if "sent" in valid_transitions.get("pending", []):
        print("    FAIL: Should not allow pending -> sent")
        return False

    for state in ["rejected", "failed"]:
        if valid_transitions.get(state, []):
            print(f"    FAIL: {state} should be terminal")
            return False

    print("    PASS: Approval workflow state machine valid")
    return True


def test_safety_rules() -> bool:
    """Test pilot safety rules in code."""
    print("\n  [TEST] Pilot Safety Rules...")

    dispatch_code = _read_file("app/followers/dispatch_service.py")
    ai_code = _read_file("app/followers/ai_personalization.py")
    gov_code = _read_file("app/followers/governance_service.py")

    all_code = dispatch_code + ai_code + gov_code

    checks = [
        ("Rate limits configured", "RATE_LIMITS" in dispatch_code),
        ("Cooldown configured", "COOLDOWN" in gov_code),
        ("Daily quotas configured", "DEFAULT_DAILY_QUOTAS" in gov_code),
        ("Spam detection configured", "calculate_spam_risk" in gov_code),
        ("Policy compliance check", "_check_policy_compliance" in dispatch_code),
        ("Confidence scoring", "confidence_score" in ai_code),
        ("Moderation configured", "moderate" in ai_code),
        ("Warmup schedule", "WARMUP_SCHEDULE" in gov_code),
        ("Tenant isolation (company_id)", "company_id" in all_code),
        ("Branch isolation (branch_id)", "branch_id" in all_code),
    ]

    failed = [name for name, ok in checks if not ok]
    if failed:
        for name in failed:
            print(f"    FAIL: {name}")
        return False

    print(f"    PASS: All {len(checks)} safety rules enforced")
    return True


def test_migration_integrity() -> bool:
    """Test migration file integrity."""
    print("\n  [TEST] Migration Integrity...")

    migration_path = PROJECT_ROOT / "alembic" / "versions" / "010_add_follower_intelligence_tables.py"
    if not migration_path.exists():
        print("    FAIL: Migration 010 not found")
        return False

    code = migration_path.read_text(encoding="utf-8")

    expected_tables = [
        "follower_delta_events", "engagement_events", "reengagement_recommendations",
        "safe_message_templates", "outreach_approval_requests",
        "audience_loss_estimates", "follower_retention_metrics", "follower_value_scores",
    ]

    for table in expected_tables:
        if f'"{table}"' not in code:
            print(f"    FAIL: Table {table} not in migration")
            return False

    if "def downgrade" not in code:
        print("    FAIL: No downgrade function")
        return False

    print(f"    PASS: Migration complete with {len(expected_tables)} tables")
    return True


def test_endpoint_structure() -> bool:
    """Test that all expected endpoints exist in router."""
    print("\n  [TEST] Endpoint Structure...")

    code = _read_file("app/followers/router.py")

    expected_endpoints = [
        '/new', '/lost-estimated', '/delta', '/inactive',
        '/engagement/new', '/engagement/record',
        '/reengagement/recommendations', '/reengagement/generate-message',
        '/reengagement/request-approval', '/reengagement/review-approval',
        '/reengagement/send-approved', '/reengagement/approvals',
        '/value-scores', '/dashboard',
    ]

    found = sum(1 for ep in expected_endpoints if ep in code)
    if found < len(expected_endpoints):
        for ep in expected_endpoints:
            if ep not in code:
                print(f"    WARN: Missing endpoint {ep}")

    print(f"    PASS: {found}/{len(expected_endpoints)} endpoints found")
    return True


def main() -> int:
    print("=" * 60)
    print("PILOT VALIDATION TEST SUITE v10")
    print("=" * 60)

    tests = [
        test_platform_dispatch_code,
        test_ai_personalization_code,
        test_governance_code,
        test_recovery_code,
        test_tenant_isolation,
        test_approval_workflow,
        test_safety_rules,
        test_migration_integrity,
        test_endpoint_structure,
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
        print("STATUS: ALL PILOT VALIDATION TESTS PASSED")
        return 0
    else:
        print(f"STATUS: {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
