"""AI Safety & Approval Validation

Validates AI safety systems are properly configured.
Usage: python scripts/staging/ai_safety_check.py
"""

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_ai_safety_models() -> list:
    """Check AI safety models exist and have required fields."""
    issues = []
    safety_models = [
        "app/ai/safety_models.py",
        "app/ai/evaluation_models.py",
    ]
    for model_file in safety_models:
        path = PROJECT_ROOT / model_file
        if not path.exists():
            issues.append(f"Missing safety model: {model_file}")
            continue
        with open(path, 'r') as f:
            content = f.read()
        if 'company_id' not in content:
            issues.append(f"{model_file} missing company_id (tenant isolation)")
    return issues


def check_ai_approval_workflow() -> list:
    """Check AI approval workflow endpoints."""
    issues = []
    required_endpoints = [
        "/api/v2/ai-safety/policies",
        "/api/v2/ai-safety/fact-check",
        "/api/v2/ai-evaluation/hallucination-stats",
        "/api/v2/ai-evaluation/quality-summary",
        "/api/v2/ai-explain",
        "/api/v2/ai-cost/budget",
    ]
    main_py = PROJECT_ROOT / "app" / "main.py"
    with open(main_py, 'r') as f:
        main_content = f.read()
    for endpoint in required_endpoints:
        path_part = endpoint.replace("/api/v2/", "").split("/")[0]
        if path_part not in main_content:
            issues.append(f"AI safety router '{path_part}' not registered in main.py")
    return issues


def check_forbidden_patterns() -> list:
    """Check for unsafe patterns in AI code."""
    issues = []
    ai_dir = PROJECT_ROOT / "app" / "ai"
    if not ai_dir.exists():
        return ["AI directory not found"]

    dangerous = [
        ("eval(", "Dangerous eval() usage"),
        ("exec(", "Dangerous exec() usage"),
        ("subprocess", "Subprocess call in AI code"),
        ("os.system", "os.system call in AI code"),
    ]

    for f in ai_dir.rglob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            for pattern, msg in dangerous:
                if pattern in content:
                    rel = str(f.relative_to(PROJECT_ROOT))
                    issues.append(f"{msg} in {rel}")
        except:
            pass

    return issues


def main() -> int:
    print("=" * 60)
    print("AI SAFETY & APPROVAL VALIDATION")
    print("=" * 60)

    all_issues = []

    print("\n--- 1. Safety Models ---")
    issues = check_ai_safety_models()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: All safety models present with tenant isolation")

    print("\n--- 2. Approval Workflow ---")
    issues = check_ai_approval_workflow()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: All AI safety endpoints registered")

    print("\n--- 3. Security Patterns ---")
    issues = check_forbidden_patterns()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  CRITICAL: {i}")
    else:
        print("  OK: No dangerous patterns found")

    print(f"\n{'=' * 60}")
    if all_issues:
        print(f"RESULT: {len(all_issues)} issue(s) found")
        return 1
    print("RESULT: PASS - AI safety systems validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
