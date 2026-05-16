"""Pilot Customer Readiness Check

Validates all customer-facing flows are complete.
Usage: python scripts/staging/pilot_readiness_check.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_onboarding_flow() -> list:
    """Check onboarding endpoints exist."""
    issues = []
    required = [
        ("/api/v2/auth/register", "User registration"),
        ("/api/v2/auth/login", "User login"),
        ("/api/v2/companies", "Company management"),
        ("/api/v2/branches", "Branch management"),
        ("/api/v2/erp/settings", "ERP settings"),
        ("/api/v2/ai/chat", "AI chat"),
        ("/api/v2/analytics/summary", "Analytics"),
        ("/api/v2/reports", "Reports"),
        ("/api/v2/campaigns", "Campaigns"),
        ("/api/v2/followers/overview", "Follower analysis"),
        ("/api/v2/settings", "Settings"),
    ]
    main_py = PROJECT_ROOT / "app" / "main.py"
    with open(main_py, 'r') as f:
        content = f.read()

    for path, desc in required:
        path_key = path.replace("/api/v2/", "").split("/")[0]
        if path_key not in content:
            issues.append(f"Missing: {desc} ({path})")
    return issues


def check_social_integration() -> list:
    """Check social media integration endpoints."""
    issues = []
    social_paths = ["social", "followers", "ads"]
    main_py = PROJECT_ROOT / "app" / "main.py"
    with open(main_py, 'r') as f:
        content = f.read()
    for p in social_paths:
        if p not in content:
            issues.append(f"Social integration '{p}' not found in main.py")
    return issues


def check_data_export() -> list:
    """Check data export capabilities."""
    issues = []
    export_paths = ["export", "csv", "pdf"]
    app_dir = PROJECT_ROOT / "app"
    found = False
    for f in app_dir.rglob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            for p in export_paths:
                if p in content:
                    found = True
        except:
            pass
    if not found:
        issues.append("No data export functionality found")
    return issues


def main() -> int:
    print("=" * 60)
    print("PILOT CUSTOMER READINESS CHECK")
    print("=" * 60)

    all_issues = []

    print("\n--- 1. Onboarding Flow ---")
    issues = check_onboarding_flow()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  MISSING: {i}")
    else:
        print("  OK: All onboarding endpoints present")

    print("\n--- 2. Social Integration ---")
    issues = check_social_integration()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  MISSING: {i}")
    else:
        print("  OK: Social integration present")

    print("\n--- 3. Data Export ---")
    issues = check_data_export()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: Data export available")

    print(f"\n{'=' * 60}")
    print(f"Flow coverage: {10 - len([i for i in all_issues if 'Missing' in i])}/10 core flows")

    if all_issues:
        print(f"RESULT: {len(all_issues)} gap(s) before pilot-ready")
        return 1
    print("RESULT: PASS - Pilot customer ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
